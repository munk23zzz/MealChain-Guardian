"""Kontrak "Segarkan ke hari ini" terhadap rute jalan — murni, tanpa DB/HTTP.

Kenapa dipisah dari tes API: perilaku yang dijanjikan tombol demo cuma dua hal
dan keduanya bisa diuji langsung pada helper-nya:

1. refresh MENCOBA menyinkronkan rute (pasangan pemasok→tujuan baru hanya punya
   geometri kalau disinkronkan — tanpa ini kiriman tampil "belum disinkronkan"),
2. kegagalan jaringan TIDAK menggagalkan refresh; alasannya dilaporkan.

Tes lewat HTTP ikut bergantung pada token/DB bersama sehingga mudah goyah saat
lingkungan demo sedang dipakai; kontrak ini tidak.
"""

import asyncio
from datetime import UTC, datetime

import app.seed.seed_data as seed_data
from app.api.demo import _sync_routes_aman

NOW = datetime(2026, 10, 17, 4, 0, tzinfo=UTC)


def test_refresh_menyinkronkan_rute_kiriman(monkeypatch) -> None:
    dipanggil: dict = {}

    async def palsu(reference_time):
        dipanggil["ref"] = reference_time
        return {"diambil": 2, "sudah_ada": 3, "gagal": 0, "alasan_gagal": {}}

    monkeypatch.setattr(seed_data, "sync_routes_after_seed", palsu)

    laporan, galat = asyncio.run(_sync_routes_aman(NOW))

    assert laporan["diambil"] == 2, "laporan sinkronisasi harus diteruskan ke respons"
    assert galat is None
    assert dipanggil["ref"] is NOW, "waktu referensi refresh yang dipakai, bukan waktu lain"


def test_refresh_tetap_berhasil_bila_osrm_tidak_terjangkau(monkeypatch) -> None:
    async def meledak(reference_time):
        raise RuntimeError("OSRM tidak terjangkau")

    monkeypatch.setattr(seed_data, "sync_routes_after_seed", meledak)

    laporan, galat = asyncio.run(_sync_routes_aman(NOW))

    assert laporan == {}, "tidak ada laporan palsu saat sinkronisasi gagal"
    assert galat is not None and "OSRM tidak terjangkau" in galat
