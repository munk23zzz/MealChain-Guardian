"""Cakupan lokasi per peran — Ruling 2026-10-14.

Rujukan: `docs/ruling-2026-10-14-scope-lokasi.md` (+ `docs/Architecture.md` §7).
Aturan yang ditegakkan modul ini, satu tempat, supaya tidak lahir dua gaya scope:

- `sppg_head` / `sppg_nutritionist` → hanya lokasi TUJUAN miliknya sendiri
  (`user.location_id`). Lokasi SUMBER (asal pasokan/batch) tetap lintas daerah.
- `bgn_monitor` → seluruh lokasi, read-only (pengawasan nasional).
- User peran SPPG tanpa `location_id` → 403 (bukan "lihat semua"); constraint DB
  menjamin ini tidak terjadi, tetapi jalur kode tetap ditutup supaya kegagalan
  data tidak berubah jadi kebocoran.

Pola ini menyalin yang sudah berlaku di `app/api/kpi.py` (GET /kpi) — pola itu
yang benar sejak awal, jadi tidak ada aturan baru yang dikarang di sini.

Catatan: modul ini hanya untuk data ber-**target** (SPPG penerima). Data sisi
sumber (`batches` untuk panel chaos, `supply`/`price` hub, batch FAIL di lokasi
lain) tetap lintas lokasi dan TIDAK boleh memakai helper ini.
"""

import uuid
from typing import Protocol

from fastapi import HTTPException


class ScopedUser(Protocol):
    """Bentuk minimum yang dibutuhkan helper ini (User asli memenuhinya).

    Protocol dipakai supaya aturan scope bisa diuji tanpa membangun objek ORM,
    dan supaya tidak ada modul yang perlu mengimpor model hanya untuk tipe.
    """

    role: str
    location_id: uuid.UUID | None

SPPG_ROLES = ("sppg_head", "sppg_nutritionist")

_403_DETAIL = "cakupan lokasi di luar SPPG Anda"


def is_national_scope(user: ScopedUser) -> bool:
    """True bila peran ini memang lintas lokasi (bgn_monitor / read-only)."""
    return user.role == "bgn_monitor"


def scope_location_id(user: ScopedUser) -> uuid.UUID | None:
    """Lokasi yang menjadi cakupan user; None = tanpa batas (nasional).

    Melempar 403 bila peran SPPG tidak terikat lokasi — gagal-tertutup.
    """
    if is_national_scope(user):
        return None
    if user.location_id is None:
        raise HTTPException(
            status_code=403,
            detail="user belum terikat lokasi — cakupan data tidak bisa ditentukan",
        )
    return user.location_id


def in_scope(user: ScopedUser, location_id: uuid.UUID | None) -> bool:
    """True bila baris ber-target `location_id` boleh dibaca user ini."""
    if is_national_scope(user):
        return True
    if location_id is None or user.location_id is None:
        return False
    return location_id == user.location_id


def assert_in_scope(
    user: ScopedUser, location_id: uuid.UUID | None, what: str = "lokasi"
) -> None:
    """403 bila target di luar cakupan (tanpa efek untuk bgn_monitor)."""
    if is_national_scope(user):
        return
    if not in_scope(user, location_id):
        raise HTTPException(status_code=403, detail=f"{what} di {_403_DETAIL}")


def apply_location_scope(statement, column, user: ScopedUser):
    """Tambahkan `WHERE column == user.location_id` untuk peran SPPG.

    `bgn_monitor` mengembalikan statement apa adanya (tanpa filter). Dipakai
    untuk daftar/agregat: feed keputusan, peta saldo, daftar batch/lokasi.
    """
    scope = scope_location_id(user)
    if scope is None:
        return statement
    return statement.where(column == scope)
