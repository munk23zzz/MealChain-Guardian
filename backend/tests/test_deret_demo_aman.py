"""Jaring keamanan deret demo kanonik (2026-10-16, malam).

Kejadian nyata yang memunculkan berkas ini: `tests/test_demo_timeseries_api.py`
dan `tests/test_timeseries_db.py` memanggil `purge_demo_rows()`, yang menghapus
SELURUH baris `origin='demo'` — termasuk deret kanonik 1 Sep–5 Nov (supply 2190 ·
price 2274 · menu 590). Ketika salah satu tes itu gagal di tengah (dulu: teardown
memakai token HTTP yang sudah tidak sah → 401), pemulihannya tak jalan dan DB
tertinggal ter-purge. Akibatnya puluhan tes lain gagal berantai (gejala `assert
2190 == 0`, `401 token tidak valid` di berkas yang tak bersangkutan) DAN data
presentasi juri lenyap.

Kontrak yang dikunci di sini:

1. `pastikan_deret_demo()` mengembalikan deret kanonik ke bentuk SEMULA (dibanding
   snapshot, bukan angka yang ditulis ulang di tes) — termasuk saat seluruh baris
   demo sudah terhapus.
2. Idempoten: saat deret sudah lengkap, ia TIDAK menambah baris apa pun.
3. Hanya menyentuh `origin='demo'`: baris kanonik `origin='seed'` tidak berubah.
"""

import asyncio

from sqlalchemy import create_engine, text

from app.seed.timeseries import (
    demo_data_status,
    pastikan_deret_demo,
    purge_demo_rows,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
TABEL = ("supply_records", "price_signals", "menu_plans")


def _jumlah(origin: str) -> dict[str, int]:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return {
                t: int(
                    conn.execute(
                        text(f"SELECT count(*) FROM {t} WHERE origin = :o"), {"o": origin}
                    ).scalar()
                    or 0
                )
                for t in TABEL
            }
    finally:
        engine.dispose()


def _status() -> dict[str, int]:
    status = asyncio.run(demo_data_status())
    return {t: status["tables"][t]["demo"] for t in TABEL}


def test_pulihkan_deret_kanonik_yang_terhapus():
    """Purge habis → `pastikan_deret_demo` memulihkan PERSIS seperti semula."""
    sebelum = _status()
    assert sebelum["supply_records"] > 0, "prasyarat: deret kanonik harus ada"
    seed_sebelum = _jumlah("seed")

    asyncio.run(purge_demo_rows())
    assert _status()["supply_records"] == 0, "panggung harus bersih dulu"

    hasil = asyncio.run(pastikan_deret_demo())

    assert hasil["dipulihkan"] is True
    assert _status() == sebelum, "deret kanonik tidak kembali ke bentuk semula"
    assert _jumlah("seed") == seed_sebelum, "baris seed tidak boleh tersentuh"


def test_idempoten_saat_deret_sudah_lengkap():
    """Sudah lengkap → tidak menambah satu baris pun (bukan generate ulang)."""
    asyncio.run(pastikan_deret_demo())
    sebelum = _status()

    hasil = asyncio.run(pastikan_deret_demo())

    assert hasil["dipulihkan"] is False
    assert hasil["kurang"] == {}
    assert _status() == sebelum


def test_melaporkan_kekurangan_sebagai_data_bukan_tebakan():
    """Ringkasan menyebut angka sebelum/sesudah/harapan — bisa diperiksa manusia."""
    asyncio.run(purge_demo_rows())
    hasil = asyncio.run(pastikan_deret_demo())

    for kunci in ("sebelum", "sesudah", "harapan", "kurang", "dipulihkan"):
        assert kunci in hasil, f"ringkasan harus memuat '{kunci}'"
    assert hasil["sebelum"]["supply_records"] == 0
    assert hasil["sesudah"]["supply_records"] == hasil["harapan"]["supply_records"]
    assert set(hasil["sebelum"]) == set(TABEL)
