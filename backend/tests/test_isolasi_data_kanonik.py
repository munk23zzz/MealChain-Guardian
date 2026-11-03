"""Penjaga isolasi data uji: baris KANONIK tidak boleh diubah oleh tes.

Kejadian nyata 21 Okt 2026: `test_admin_api.py::test_daftar_lokasi_dan_ubah_nama`
mengganti nama lokasi kanonik "Bandung" menjadi "Bandung (uji)" dan tidak pernah
memulihkannya. Karena id lokasi adalah `uuid5("location", nama)`, baris hasil
rename menyimpan id milik "Bandung" dengan nama lain; seed berikutnya mencoba
menyisipkan Bandung dengan id itu lalu gagal `duplicate key locations_pkey` —
"Siapkan data demo" mati dan template tidak bisa dibangun lagi.

Dua invarian di bawah mengunci hal itu:
1. tidak ada lokasi bernama berakhiran "(uji)" (sisa tes yang bocor);
2. id setiap lokasi sama dengan `stable_uuid("location", namanya)` — rename apa
   pun pada baris kanonik akan melanggar ini sebelum merusak seed.
"""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.seed.seed_data import stable_uuid
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DSN = os.environ.get(
    "TEST_DATABASE_URL",
    DSN_ASYNC,
)


def _lokasi() -> list[tuple[str, str]]:
    import asyncio

    async def ambil():
        engine = create_async_engine(DSN)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(text("SELECT id::text, name FROM locations ORDER BY name"))
                ).all()
            return [(r[0], r[1]) for r in rows]
        finally:
            await engine.dispose()

    return asyncio.run(ambil())


def test_tidak_ada_lokasi_sisa_tes():
    bocor = [nama for _, nama in _lokasi() if nama.strip().lower().endswith("(uji)")]
    assert bocor == [], (
        "lokasi sisa tes ditemukan: "
        f"{bocor}. Pulihkan namanya (lihat test_admin_api::test_daftar_lokasi_dan_ubah_nama) "
        "sebelum menyemai ulang, kalau tidak seed akan gagal duplicate key."
    )


def test_id_lokasi_konsisten_dengan_namanya():
    salah = [
        (nama, lid)
        for lid, nama in _lokasi()
        if lid != str(stable_uuid("location", nama))
    ]
    assert salah == [], (
        "id lokasi tidak cocok dengan uuid5(nama) — baris ini hasil rename/ubah manual "
        f"pada data kanonik: {salah}"
    )
