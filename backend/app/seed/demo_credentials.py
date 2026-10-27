"""Kredensial akun demo — satu pintu, dengan guard (temuan D-01).

Sebelum 25 Oktober 2026, password akun demo tertulis sebagai literal di
`app/seed/seed_data.py` dan jalur seed yang sama dipakai pada stack produksi
(`docker-compose.prod.yml` mendokumentasikan `python -m app.seed.seed_data`).
Artinya siapa pun yang bisa membaca repository — termasuk mirror publik —
mendapat kredensial yang berlaku pada instalasi mana pun.

Kontrak sekarang:

1. Password demo HANYA dipakai bila `DEMO_MODE` benar-benar aktif
   (`true`/`1`/`yes`/`on`). Nilai lain — termasuk `false`, `0`, string kosong —
   dianggap mati.
2. Operator dapat menyuplai password sendiri lewat `DEMO_PASSWORD_<ROLE>`
   (mis. `DEMO_PASSWORD_SPPG_HEAD`); nilai itu menang atas password demo.
3. Tanpa keduanya, seed MENOLAK berjalan (`DemoCredentialError`) alih-alih
   memasang kredensial yang bisa ditebak.

Rotasi kredensial historis adalah tindakan pemilik kredensial, bukan efek
samping perubahan kode ini (lihat checklist di `REPAIR_PLAN.md`).
"""

from __future__ import annotations

import os
from typing import Mapping

#: Password juri yang didokumentasikan untuk demonstrasi. Hanya dipakai saat
#: `DEMO_MODE` aktif; bukan kredensial produksi.
DEMO_PASSWORDS_JURI: dict[str, str] = {
    "sppg_head": "Demo#SPPG2026",
    "sppg_nutritionist": "Demo#Nut2026",
    "bgn_monitor": "Demo#BGN2026",
}

_NILAI_AKTIF = {"1", "true", "yes", "on"}

#: Akun yang ditawarkan tombol demo di layar login. Satu sumber untuk frontend: label,
#: email, peran, dan pengelompokan ("utama" vs "kota") supaya tidak ada daftar ganda di
#: `frontend/app/page.tsx`. Sandi TIDAK ada di sini — diambil lewat `resolve_demo_password`
#: hanya ketika `DEMO_MODE` aktif.
AKUN_DEMO_BROWSER: tuple[dict[str, str], ...] = (
    {"label": "SPPG Head", "email": "sppg.head@demo.local", "role": "sppg_head", "grup": "utama"},
    {
        "label": "Nutritionist",
        "email": "sppg.nutritionist@demo.local",
        "role": "sppg_nutritionist",
        "grup": "utama",
    },
    {
        "label": "BGN Monitor",
        "email": "bgn.monitor@demo.local",
        "role": "bgn_monitor",
        "grup": "utama",
    },
    {
        "label": "Kepala Bandung",
        "email": "sppg.head.bandung@demo.local",
        "role": "sppg_head",
        "grup": "kota",
    },
    {
        "label": "Gizi Bandung",
        "email": "sppg.nutritionist.bandung@demo.local",
        "role": "sppg_nutritionist",
        "grup": "kota",
    },
    {
        "label": "Kepala Surabaya",
        "email": "sppg.head.surabaya@demo.local",
        "role": "sppg_head",
        "grup": "kota",
    },
    {
        "label": "Gizi Surabaya",
        "email": "sppg.nutritionist.surabaya@demo.local",
        "role": "sppg_nutritionist",
        "grup": "kota",
    },
)


def akun_demo_untuk_browser(env: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    """Daftar akun demo LENGKAP dengan sandi — hanya saat `DEMO_MODE` aktif.

    Dipakai `GET /auth/demo-accounts` supaya satu klik peran langsung siap masuk.
    Memanggil fungsi ini di mode non-demo akan melempar `DemoCredentialError`,
    bukan diam-diam mengirim kredensial.
    """
    if not demo_mode_aktif(env):
        raise DemoCredentialError(
            "akun demo bertanya-pundi hanya tersedia saat DEMO_MODE aktif"
        )
    hasil: list[dict[str, str]] = []
    for akun in AKUN_DEMO_BROWSER:
        hasil.append({**akun, "password": resolve_demo_password(akun["role"], env)})
    return hasil


class DemoCredentialError(RuntimeError):
    """Seed menolak memasang kredensial demo tanpa otorisasi konfigurasi."""


class AkunDemo(dict):
    """Akun demo yang menyelesaikan `password` lewat guard, bukan literal.

    Banyak pemanggil lama (`tests/*`, `scripts/verifikasi_*.py`,
    `app/seed/reference.py`) membaca `akun["password"]`. Menghapus kunci itu
    memutus 20+ pemanggil (KeyError) seperti terbukti pada suite penuh
    25 Oktober 2026. Kelas ini membuat pembacaan tersebut tetap bekerja
    sekaligus tetap melewati `resolve_demo_password` — sehingga `DEMO_MODE`
    tetap menjadi satu-satunya pintu, dan password tidak pernah tersimpan
    sebagai nilai di dalam dict (`**akun`, `items()`, `json.dumps` aman).
    """

    def __getitem__(self, kunci: str):  # type: ignore[override]
        if kunci == "password":
            return resolve_demo_password(super().__getitem__("role"))
        return super().__getitem__(kunci)

    def get(self, kunci: str, default=None):  # type: ignore[override]
        if kunci == "password":
            try:
                return resolve_demo_password(super().__getitem__("role"))
            except DemoCredentialError:
                return default
        return super().get(kunci, default)


def demo_mode_aktif(env: Mapping[str, str] | None = None) -> bool:
    sumber: Mapping[str, str] = os.environ if env is None else env
    return (sumber.get("DEMO_MODE") or "").strip().lower() in _NILAI_AKTIF


def demo_login_autofill_aktif(env: Mapping[str, str] | None = None) -> bool:
    """Kunci kedua untuk `GET /auth/demo-login` (layar login, tanpa token).

    Kenapa perlu dua kunci: endpoint itu tidak ber-token — satu-satunya pemakainya
    adalah halaman login yang belum punya sesi. Supaya instalasi nyata tidak pernah
    membuka kredensial, autofill harus dinyalakan eksplisit lewat
    `DEMO_LOGIN_AUTOFILL=true` DAN `DEMO_MODE=true`. Default keduanya mati.
    """
    sumber: Mapping[str, str] = os.environ if env is None else env
    if not demo_mode_aktif(sumber):
        return False
    return (sumber.get("DEMO_LOGIN_AUTOFILL") or "").strip().lower() in _NILAI_AKTIF


def _kunci_env(role: str) -> str:
    return f"DEMO_PASSWORD_{role.upper()}"


def resolve_demo_password(role: str, env: Mapping[str, str] | None = None) -> str:
    """Password untuk `role` atau `DemoCredentialError` bila tidak diizinkan."""
    sumber: Mapping[str, str] = os.environ if env is None else env
    if role not in DEMO_PASSWORDS_JURI:
        raise DemoCredentialError(
            f"role demo tidak dikenal: {role!r} (dikenal: {sorted(DEMO_PASSWORDS_JURI)})"
        )

    eksplisit = (sumber.get(_kunci_env(role)) or "").strip()
    if eksplisit:
        return eksplisit

    if demo_mode_aktif(sumber):
        return DEMO_PASSWORDS_JURI[role]

    raise DemoCredentialError(
        "menolak memasang password demo: set DEMO_MODE=true untuk demonstrasi, "
        f"atau suplai {_kunci_env(role)} lewat environment."
    )
