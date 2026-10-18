"""Jaring keamanan deret demo kanonik (2026-10-16, malam).

Kejadian nyata yang memunculkan berkas ini: `tests/test_demo_timeseries_api.py`
dan `tests/test_timeseries_db.py` memanggil `purge_demo_rows()`, yang menghapus
SELURUH baris `origin='demo'` — termasuk deret kanonik 1 Sep–5 Nov. Sejak
2026-10-17 rentang itu penuh sampai 5 Nov: 130 cap waktu × 30 pasangan =
**3.900 baris supply** (3.870 demo + 30 kanonik 8 Okt 12:00) dan **4.040 baris
harga** sebagai rencana. Ketika salah satu tes itu gagal di tengah (dulu: teardown
memakai token HTTP yang sudah tidak sah → 401), pemulihannya tak jalan dan DB
tertinggal ter-purge. Akibatnya puluhan tes lain gagal berantai DAN data
presentasi juri lenyap.

Kontrak yang dikunci di sini:

1. `pastikan_deret_demo()` mengembalikan deret kanonik ke bentuk SEMULA (dibanding
   snapshot, bukan angka yang ditulis ulang di tes) — termasuk saat seluruh baris
   demo sudah terhapus.
2. Idempoten: saat deret sudah lengkap, ia TIDAK menambah baris apa pun.
3. Hanya menyentuh `origin='demo'`: baris kanonik `origin='seed'` tidak berubah.
4. Kelengkapan diukur agnostik-origin (baris di dalam rentang dari SEMUA origin),
   karena stamp 8 Okt 12:00 memang dipegang baris kanonik.
"""

import asyncio

from sqlalchemy import create_engine, text

from app.seed.timeseries import (
    demo_data_status,
    pastikan_deret_demo,
    purge_demo_rows,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
TABEL = (
    "supply_records",
    "price_signals",
    "menu_plans",
    "delivery_events",
    "disposal_events",
)


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
    tables = status["tables"]
    # `demo_data_status` melaporkan tiga tabel deret; kiriman/limbah dibaca
    # langsung supaya berkas ini tetap bisa membandingkan kelima tabel.
    demo = _jumlah("demo")
    return {t: int(tables[t]["demo"]) if t in tables else demo[t] for t in TABEL}


def _kanonik() -> dict[str, int]:
    """Jangkar kanonik menurut JENDELANYA, bukan seluruh origin='seed'.

    Tes lain sah menambah baris ber-origin 'seed' (mis. harga lewat POST), jadi
    membandingkan seluruh origin akan gagal karena pekerjaan tes lain. Yang
    dijaga di sini: supply/harga pada stamp 8 Okt 12:00, rencana 1–7 Okt,
    kiriman & limbah 1–7 Okt.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            baris = conn.execute(
                text(
                    "SELECT 'supply', count(*) FROM supply_records WHERE origin='seed' "
                    "AND recorded_at = TIMESTAMP '2026-10-08 12:00:00+00' "
                    "UNION ALL SELECT 'price', count(*) FROM price_signals "
                    "WHERE origin='seed' AND recorded_at = TIMESTAMP '2026-10-08 12:00:00+00' "
                    "UNION ALL SELECT 'menu', count(*) FROM menu_plans "
                    "WHERE origin='seed' AND plan_date "
                    "BETWEEN DATE '2026-10-01' AND DATE '2026-10-07' "
                    "UNION ALL SELECT 'kiriman', count(*) FROM delivery_events de "
                    "JOIN menu_plans mp ON mp.id = de.menu_plan_id WHERE de.origin='seed' "
                    "AND mp.plan_date BETWEEN DATE '2026-10-01' AND DATE '2026-10-07' "
                    "UNION ALL SELECT 'limbah', count(*) FROM disposal_events "
                    "WHERE origin='seed' AND disposed_at >= TIMESTAMP '2026-10-04 00:00:00+00' "
                    "AND disposed_at < TIMESTAMP '2026-10-08 00:00:00+00'"
                )
            ).all()
            return {kunci: int(nilai) for kunci, nilai in baris}
    finally:
        engine.dispose()


def test_pulihkan_deret_kanonik_yang_terhapus():
    """Purge habis → `pastikan_deret_demo` memulihkan PERSIS seperti semula."""
    sebelum = _status()
    assert sebelum["supply_records"] > 0, "prasyarat: deret kanonik harus ada"
    kanonik_sebelum = _kanonik()

    asyncio.run(purge_demo_rows())
    assert _status()["supply_records"] == 0, "panggung harus bersih dulu"

    hasil = asyncio.run(pastikan_deret_demo())

    assert hasil["dipulihkan"] is True
    assert _status() == sebelum, "deret kanonik tidak kembali ke bentuk semula"
    assert _kanonik() == kanonik_sebelum, "jangkar kanonik tidak boleh tersentuh"


def test_idempoten_saat_deret_sudah_lengkap():
    """Sudah lengkap → tidak menambah satu baris pun (bukan generate ulang)."""
    asyncio.run(pastikan_deret_demo())
    sebelum = _status()

    hasil = asyncio.run(pastikan_deret_demo())

    assert hasil["dipulihkan"] is False
    assert hasil["kurang"] == {}
    # 3.900 = 3.870 baris demo + 30 baris kanonik pada stamp 8 Okt 12:00 — bukti
    # bahwa kelengkapan diukur agnostik-origin (kalau hanya baris demo, 3.870).
    # Dipakai `>=`, bukan `==`: fitur "Segarkan ke hari ini" dan seeder lain sah
    # menambah baris di dalam rentang. Yang dijaga di sini "tidak kurang dari
    # rencana", bukan angka yang kebetulan pas.
    assert hasil["sesudah"]["supply_records"] >= 3900
    assert _status() == sebelum


def test_melaporkan_kekurangan_sebagai_data_bukan_tebakan():
    """Ringkasan menyebut angka sebelum/sesudah/harapan — bisa diperiksa manusia."""
    asyncio.run(purge_demo_rows())
    hasil = asyncio.run(pastikan_deret_demo())

    for kunci in ("sebelum", "sesudah", "harapan", "kurang", "dipulihkan"):
        assert kunci in hasil, f"ringkasan harus memuat '{kunci}'"
    # `sebelum`/`sesudah` dihitung dari SEMUA origin di dalam rentang, jadi setelah
    # purge pun masih ada baris kanonik (30 baris supply 8 Okt 12:00, 44 harga).
    assert hasil["sebelum"]["supply_records"] < hasil["harapan"]["supply_records"]
    assert hasil["sesudah"]["supply_records"] >= hasil["harapan"]["supply_records"]
    # Permintaan ikut dilaporkan: setelah purge, baris demo permintaan habis
    # (baris kanonik 8 Okt berada di luar rentang) dan dipulihkan oleh `pastikan`.
    assert hasil["sebelum"]["demand_records"] < hasil["harapan"]["demand_records"]
    assert hasil["sesudah"]["demand_records"] >= hasil["harapan"]["demand_records"]
    assert set(hasil["sebelum"]) == {
        "supply_records",
        "demand_records",
        "price_signals",
        "menu_plans",
        "deliveries",
        "disposals",
    }
