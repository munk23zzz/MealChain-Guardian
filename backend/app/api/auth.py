"""Auth JWT (S3-01) — login DB-backed + proteksi endpoint.

Tiga role final (Schema.md): sppg_head | sppg_nutritionist | bgn_monitor.
bgn_monitor read-only. JWT HS256 dari .env (JWT_SECRET, JWT_ALGORITHM,
JWT_EXPIRE_MINUTES).
"""

import os
import time
from uuid import UUID

import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core import rate_limit
from app.models import Location, User

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)

#: Host yang dianggap "lokal" untuk pintu autofill demo. `testclient` muncul dari
#: TestClient in-process (tidak pernah lewat jaringan). Semua host lain = remote.
_HOST_LOKAL = frozenset(
    {"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1", "testclient"}
)


def _ip_gateway() -> str | None:
    """IP gateway default container (di Docker Desktop = host yang menjalankan browser).

    Browser demo di laptop host menghubungi `localhost:8000`; dari dalam container
    paket itu masuk dengan alamat gateway bridge (terukur `172.20.0.1`), bukan
    `127.0.0.1`. Jadi "lokal" harus mencakup gateway, tetapi **tidak** seluruh
    RFC1918 — klien LAN punya alamat sendiri dan tetap ditolak.
    """
    try:
        with open("/proc/net/route", encoding="ascii") as berkas:
            next(berkas)
            for baris in berkas:
                kolom = baris.split()
                if len(kolom) > 2 and kolom[1] == "00000000":
                    nilai = int(kolom[2], 16)
                    return ".".join(str((nilai >> geser) & 0xFF) for geser in (0, 8, 16, 24))
    except (OSError, StopIteration, ValueError):
        return None
    return None


def boleh_autofill_dari(request: object | None) -> bool:
    """True bila pemanggil `GET /auth/demo-login` boleh menerima sandi demo.

    Audit 2026-10-29 (AUD-005): dua flag (`DEMO_MODE` + `DEMO_LOGIN_AUTOFILL`)
    hanya menjawab "apakah demo mengizinkan autofill", bukan "siapa yang boleh
    bertanya". Endpoint ini tanpa token, dan dev compose mem-publish
    `0.0.0.0:8000`, jadi siapa pun di LAN/jaringan demo bisa membaca sandi
    ketiga peran. Penjaga ketiga di sini: **hanya pemanggil lokal** (loopback,
    TestClient in-process, atau gateway container = host).

    Override eksplisit untuk demo yang sengaja dibuka lebar:
    `DEMO_LOGIN_ALLOW_REMOTE=true` (didokumentasikan di `.env.example`).

    Parameter sengaja `object` (duck-typed): hanya `.client.host` yang dibaca,
    sehingga aturan ini bisa diuji tanpa membangun `Request` asli.
    """
    if (os.environ.get("DEMO_LOGIN_ALLOW_REMOTE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    klien = getattr(request, "client", None)
    host = getattr(klien, "host", None) if klien is not None else None
    if (host or "") in _HOST_LOKAL:
        return True
    gateway = _ip_gateway()
    return bool(gateway) and host == gateway


# Hash bcrypt dummy untuk timing konsisten saat email tidak dikenal.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode()


class LoginRequest(BaseModel):
    email: str
    password: str


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET belum diset")
    return secret


def _algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


#: Batas umur token. 24 jam = cukup untuk satu hari demo, tetap jauh di bawah
#: "praktis selamanya" yang dulu dipakai (5.256.000 menit ≈ 10 tahun, SEC-02).
UMUR_MAKS_MENIT = 1440
UMUR_MIN_MENIT = 5


def _expire_minutes() -> int:
    """Umur token dalam menit, DIJEPIT ke rentang yang masuk akal.

    SEC-02 (audit 24 Okt 2026): `.env` berisi 5256000 menit (±10 tahun). Token
    yang tidak pernah kedaluwarsa membuat satu kebocoran token berlaku selamanya.
    Nilai di luar rentang tidak dipakai apa adanya — dijepit, bukan dibiarkan
    (fail-safe ke nilai aman, tanpa membuat login gagal).
    """
    try:
        menit = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))
    except ValueError:
        menit = 30
    return max(UMUR_MIN_MENIT, min(UMUR_MAKS_MENIT, menit))


def _issue_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "loc": str(user.location_id) if user.location_id else None,
        # `typ` menandai token yang diterbitkan untuk SESI MANUSIA lewat login.
        # Endpoint admin menolak token tanpa penanda ini (audit 2026-10-29,
        # AUD-006): token layanan agen adalah JWT milik akun `bgn_monitor`,
        # sehingga tanpa pembeda ia bisa mengelola pengguna.
        "typ": "user",
        "iat": now,
        "exp": now + _expire_minutes() * 60,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_algorithm())


def issue_token_for_user(user: User) -> str:
    """Token Bearer untuk SATU user (dipakai jalur review in-process).

    Review lokal (`AGENT_REVIEW_MODE=local`) berjalan di dalam backend dan harus
    membaca API dengan identitas pemanggil — bukan token layanan berumur panjang
    yang bisa kedaluwarsa di tengah demo, dan bukan identitas lain. Umur token
    tetap mengikuti `JWT_EXPIRE_MINUTES` yang sudah dijepit `_expire_minutes()`.
    """
    return _issue_token(user)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependensi auth: validasi Bearer token + user DB-backed."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="butuh Bearer token")
    try:
        claims = pyjwt.decode(
            credentials.credentials,
            _secret(),
            algorithms=[_algorithm()],
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="token tidak valid") from exc
    raw_sub = claims.get("sub")
    try:
        user_id = UUID(str(raw_sub))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail="token tidak valid") from exc
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="token tidak valid")
    # Jejak jenis token untuk guard `require_sesi_manusia` (AUD-006). Disimpan
    # sebagai atribut transien, bukan kolom DB: nilainya milik request ini saja.
    setattr(user, "_token_typ", claims.get("typ"))
    return user


def require_roles(*allowed: str):
    """Guard RBAC: user harus punya salah satu role yang diizinkan."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="role tidak diizinkan")
        return user

    return _guard


async def require_sesi_manusia(
    user: User = Depends(get_current_user),
) -> User:
    """Guard untuk endpoint tulis administratif (audit 2026-10-29, AUD-006).

    RBAC saja tidak cukup di sini: token layanan agen adalah JWT milik akun
    berperan `bgn_monitor`, jadi dari sisi RBAC ia identik dengan operator
    manusia. Endpoint admin karena itu menuntut klaim `typ="user"` yang HANYA
    diterbitkan jalur login. Token tanpa klaim itu ditolak (fail-closed); sesi
    manusia cukup login ulang.
    """
    if getattr(user, "_token_typ", None) != "user":
        raise HTTPException(
            status_code=403,
            detail="endpoint ini hanya untuk sesi pengguna, bukan token layanan",
        )
    return user


# CATATAN audit 2026-10-11: di sini dulu ada `require_target_location` yang
# mengembalikan `user` apa adanya — dependency tanpa penjagaan apa pun yang
# namanya menjanjikan penegakan O-SEC-2. Tidak satu pun endpoint memakainya,
# jadi ia dihapus supaya tidak ada yang mengira cakupan lokasi sudah dijaga.
# Penegakan yang NYATA ada di dua tempat:
#   - `app/api/decisions.py::_assert_target_location_allowed` (dipakai POST
#     /decisions dan aksi yang menyasar decision),
#   - handler yang mengekstrak target dari payload lalu membandingkannya dengan
#     `user.location_id`.
# /events/* BELUM menegakkannya — lihat catatan audit di app/api/events.py.


# Role yang boleh melakukan mutasi/komputasi endpoint (bgn_monitor read-only
# per PRD §77). Dipakai guard endpoint legacy Sprint 1/2 (residual debt).
MUTATING_ROLES = ("sppg_head", "sppg_nutritionist")


def _kunci_laju(request: Request, email: str) -> str:
    """Kunci pembatas: IP + email. NAT kantor tidak saling memblokir."""
    ip = request.client.host if request.client else "tanpa-ip"
    return f"login:{ip}:{email}"


@router.get("/auth/demo-login")
async def demo_login_accounts(request: Request):
    """Akun demo untuk layar login — TANPA token, tapi TIGA kunci harus aktif.

    Halaman login bersifat publik dan belum punya sesi, jadi `GET
    /auth/demo-accounts` (ber-token `bgn_monitor`) tidak bisa dipakainya. Pintu
    ini dibuat khusus untuk itu, dan hanya terbuka bila `DEMO_MODE` aktif **dan**
    `DEMO_LOGIN_AUTOFILL` aktif (lihat `demo_login_autofill_aktif()`) **dan**
    pemanggilnya lokal (lihat `boleh_autofill_dari()`). Default ketiganya mati,
    sehingga instalasi nyata menjawab `{enabled:false, accounts:[]}` dan kata
    sandi tidak pernah keluar dari server.

    Konsekuensi yang harus disadari: selama kunci-kunci itu aktif, proses lokal
    mana pun yang bisa menjangkau backend demo dapat membaca sandi akun demo.
    Karena itu `DEMO_MODE` wajib `false` di luar sesi demo (Rules.md §1.4).
    """
    from app.seed.demo_credentials import (
        DemoCredentialError,
        akun_demo_untuk_browser,
        demo_login_autofill_aktif,
    )

    if not demo_login_autofill_aktif() or not boleh_autofill_dari(request):
        return {"enabled": False, "accounts": []}
    try:
        akun = akun_demo_untuk_browser()
    except DemoCredentialError:
        return {"enabled": False, "accounts": []}
    return {"enabled": True, "accounts": akun}


@router.get("/auth/demo-accounts")
async def demo_accounts(
    _admin: User = Depends(require_roles("bgn_monitor")),
):
    """Akun demo siap-pakai untuk layar login — HANYA saat `DEMO_MODE` aktif.

    Kenapa di balik auth (26 Okt 2026): endpoint ini mengembalikan KREDENSIAL
    (email + kata sandi yang berlaku). Sebelumnya siapa pun yang bisa menjangkau
    backend dapat membacanya tanpa token. Skema tidak punya peran `admin`
    (Schema.md §1: tiga peran final), jadi penjaganya mengikuti pola yang sudah
    dipakai `/admin/*`: `require_roles("bgn_monitor")` — satu-satunya peran
    nasional, lihat `app/core/admin_rules.py`. Tanpa token → 401, token non-admin
    → 403. Di mode non-demo jawabannya tetap `{enabled:false, accounts:[]}`.

    Konsumen: layar login publik TIDAK memanggil endpoint ini (ia memakai daftar
    tanpa sandi di `frontend/lib/demo-accounts.ts`); pemanggilnya adalah skrip
    demo/operator yang sudah punya sesi admin.
    """
    from app.seed.demo_credentials import DemoCredentialError, akun_demo_untuk_browser

    try:
        akun = akun_demo_untuk_browser()
    except DemoCredentialError:
        return {"enabled": False, "accounts": []}
    return {"enabled": True, "accounts": akun}


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower().strip()
    kunci = _kunci_laju(request, email)
    tunggu = rate_limit.sisa_tunggu(kunci)
    if tunggu > 0:
        # SEC-03: tanpa pembatas, satu skrip bisa menebak kata sandi tanpa jeda.
        raise HTTPException(
            status_code=429,
            detail="terlalu banyak percobaan login, coba lagi nanti",
            headers={"Retry-After": str(int(tunggu) + 1)},
        )
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None:
        # Timing konsisten untuk email tak dikenal.
        bcrypt.checkpw(payload.password.encode(), _DUMMY_HASH.encode())
        rate_limit.catat_gagal(kunci)
        raise HTTPException(status_code=401, detail="email atau password salah")
    if not bcrypt.checkpw(payload.password.encode(), user.password_hash.encode()):
        rate_limit.catat_gagal(kunci)
        raise HTTPException(status_code=401, detail="email atau password salah")
    rate_limit.lupakan(kunci)
    return {
        "access_token": _issue_token(user),
        "token_type": "bearer",
        "role": user.role,
        "user_id": str(user.id),
        "expires_in": _expire_minutes() * 60,
    }


@router.get("/auth/me")
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    loc_name = None
    if user.location_id:
        loc = (
            await db.execute(
                select(Location).where(Location.id == user.location_id)
            )
        ).scalar_one_or_none()
        loc_name = loc.name if loc else None
    return {
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "location_id": str(user.location_id) if user.location_id else None,
        "location_name": loc_name,
    }
