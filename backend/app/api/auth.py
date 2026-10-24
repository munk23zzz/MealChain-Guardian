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
        "iat": now,
        "exp": now + _expire_minutes() * 60,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_algorithm())


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
    return user


def require_roles(*allowed: str):
    """Guard RBAC: user harus punya salah satu role yang diizinkan."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="role tidak diizinkan")
        return user

    return _guard


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
