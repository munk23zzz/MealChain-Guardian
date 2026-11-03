"""Jendela simpan gudang SPPG — satu tempat yang menentukan `hari_simpan`.

Latar (konsep Performance & Audit, 29 Okt 2026). Susut gudang dihitung dari
LAMA BARANG DISIMPAN, bukan dari kesegaran saat terima. Kesegaran mengukur mutu
pada satu titik serah terima; ia tidak tahu berapa hari barang duduk di gudang.
Memakai `(1 − freshness)` sebagai pengali susut membuat dua hal berbeda terbaca
sebagai satu: kiriman yang mutunya rendah dianggap tersimpan lama, dan kiriman
yang tersimpan lama tidak terlihat bedanya dari yang baru tiba.

Aturan modul ini sengaja kecil dan eksplisit supaya bisa diperiksa:

1. `hari_simpan` = lama barang berada di gudang SPPG, dibatasi `[0, umur]`.
2. Bila tanggal kebutuhan menu diketahui (`needed_by`) DAN waktu tiba diketahui,
   `hari_simpan` = selang tiba → dibutuhkan (basis `rencana_menu`). Ini rencana,
   bukan tebakan: tanggalnya datang dari rencana menu.
3. Bila tanggal kebutuhan tidak diketahui, dipakai asumsi siklus harian SPPG —
   satu hari — dengan basis `asumsi_siklus_harian`. Angkanya TIDAK nol supaya
   pembaca tidak menyimpulkan "tidak ada susut", dan basisnya ikut dilaporkan
   supaya panel audit bisa menjelaskan asalnya.
4. Basis tidak pernah tersembunyi: setiap hasil membawa `storage_basis`.

Yang dilarang modul ini: memakai kesegaran untuk apa pun. Tidak ada parameter
freshness di sini, dan itu disengaja.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import Decimal

__all__ = [
    "BASIS_ASUMSI",
    "BASIS_RENCANA",
    "DEFAULT_STORAGE_DAYS",
    "storage_days_for",
]

#: Asumsi siklus harian SPPG (belum divalidasi domain owner). Dipakai HANYA bila
#: tanggal kebutuhan barang tidak diketahui; nilainya dilaporkan lewat
#: `storage_basis` supaya tidak terbaca sebagai rencana.
DEFAULT_STORAGE_DAYS = Decimal("1")

BASIS_RENCANA = "rencana_menu"
BASIS_ASUMSI = "asumsi_siklus_harian"


def _ke_utc(nilai: datetime) -> datetime:
    """Waktu dari DB bisa naif; samakan zona, jangan menebak offset."""
    if nilai.tzinfo is None:
        return nilai
    return nilai.astimezone(UTC).replace(tzinfo=None)


def storage_days_for(
    *,
    needed_by: datetime | None,
    arrival_at: datetime | None,
    shelf_life_days: Decimal | float | int | None = None,
) -> tuple[Decimal, str]:
    """`(hari_simpan, basis)` untuk satu kiriman.

    Angka dikembalikan sebagai `Decimal` dengan dua desimal; pembulatan ke ATAS
    (bukan ke bawah) karena susut yang dibebankan tidak boleh lebih kecil dari
    lama simpan sebenarnya — mis. 0,4 hari tersimpan tetap satu hari simpan.

    `shelf_life_days` hanya dipakai sebagai batas atas. Batas itu bukan rumus
    baru: barang tidak mungkin tersimpan lebih lama dari umur simpannya.
    """
    batas = (
        Decimal(str(shelf_life_days))
        if shelf_life_days is not None
        else None
    )
    if needed_by is not None and arrival_at is not None:
        selang_detik = (_ke_utc(needed_by) - _ke_utc(arrival_at)).total_seconds()
        hari = Decimal(max(0.0, selang_detik) / 86400.0)
        basis = BASIS_RENCANA
    else:
        hari = DEFAULT_STORAGE_DAYS
        basis = BASIS_ASUMSI
    if hari > 0:
        # ceil ke 2 desimal: 0,333 hari → 0,34 hari, supaya tidak ada susut yang
        # hilang karena pembulatan ke bawah.
        hari = Decimal(math.ceil(float(hari) * 100) / 100)
    if batas is not None and hari > batas:
        hari = batas
    return hari.quantize(Decimal("0.01")), basis
