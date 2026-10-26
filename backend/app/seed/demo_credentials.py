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
