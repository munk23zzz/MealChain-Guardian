"""Perluasan deret demo ke KIRIMAN & LIMBAH (2026-10-17).

Kenapa ada: setelah deret AKTUAL (supply/harga) berjalan sampai 4 Nov, dua panel
masih mati di jendela pendek karena `delivery_events` (1–7 Okt) dan
`disposal_events` (4–7 Okt) tidak ikut diperluas:

- "Avoidable Food Loss" → "tidak ada disposal event pada periode ini";
- "Meal Continuity Rate" → 0.00% (rencana ada, kiriman tidak ada), yang terbaca
  "tidak ada makanan terkirim" padahal sebabnya tabel kiriman berhenti 7 Okt.

Kontrak yang dikunci di sini:

1. Generator menulis baris demo (`origin='demo'`) untuk SETIAP hari rencana
   8 Okt–5 Nov pada 10 lokasi — satu kiriman per rencana, dua catatan limbah
   per hari.
2. Baris KANONIK (1–7 Okt) tidak tersentuh: jumlah dan porsinya tetap.
3. Purge membuang HANYA baris demo pada kedua tabel.
4. Efeknya di permukaan: KPI jendela 7 hari berisi Meal Continuity (>0) dan
   Avoidable Food Loss (sample_count > 0), dan agenda hari setelah 7 Okt
   menampilkan kiriman + limbah.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.seed.timeseries import (
    DEFAULT_END,
    DEFAULT_START,
    generate_timeseries,
    purge_demo_rows,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

#: hari rencana pertama yang BELUM punya kiriman/limbah kanonik (kanonik 1–7 Okt)
HARI_PERTAMA_DEMO = date(2026, 10, 8)
#: ujung rencana menu (DEFAULT_END = 5 Nov, jam 00:00)
HARI_TERAKHIR_DEMO = date(2026, 11, 5)


def _q(sql: str, **param):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return conn.execute(text(sql), param).all()
    finally:
        engine.dispose()


def _jumlah_kiriman(origin: str) -> int:
    return int(_q("SELECT count(*) FROM delivery_events WHERE origin = :o", o=origin)[0][0])


def _jumlah_limbah(origin: str) -> int:
    return int(_q("SELECT count(*) FROM disposal_events WHERE origin = :o", o=origin)[0][0])


def _hari_rencana() -> list[str]:
    return [
        r[0].isoformat()
        for r in _q(
            "SELECT DISTINCT plan_date FROM menu_plans "
            "WHERE plan_date >= :a AND plan_date <= :b ORDER BY plan_date",
            a=HARI_PERTAMA_DEMO,
            b=HARI_TERAKHIR_DEMO,
        )
    ]


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module", autouse=True)
def deret_terbangun():
    """Bangun deret demo sekali untuk seluruh berkas, lalu pulihkan di akhir."""
    asyncio.run(purge_demo_rows())
    asyncio.run(generate_timeseries(DEFAULT_START, DEFAULT_END, interval_hours=12))
    yield
    asyncio.run(purge_demo_rows())
    asyncio.run(generate_timeseries(DEFAULT_START, DEFAULT_END, interval_hours=12))


def test_kiriman_demo_menutup_seluruh_hari_rencana():
    """Satu kiriman per rencana, 8 Okt–5 Nov, 10 lokasi tiap hari."""
    hari = _hari_rencana()
    assert hari[0] == HARI_PERTAMA_DEMO.isoformat()
    assert hari[-1] == HARI_TERAKHIR_DEMO.isoformat()

    baris = _q(
        "SELECT count(*), count(DISTINCT mp.plan_date), count(DISTINCT mp.location_id) "
        "FROM delivery_events de JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "WHERE mp.plan_date >= :a AND mp.plan_date <= :b",
        a=HARI_PERTAMA_DEMO,
        b=HARI_TERAKHIR_DEMO,
    )
    # Dihitung dari SEMUA origin: seeder lain bisa saja menulis baris kanonik pada
    # hari yang sama. Yang dijaga generator ini adalah "tiap hari rencana punya
    # tepat satu kiriman per lokasi", bukan "semua barisnya milik demo".
    jumlah, hari_tertutup, lokasi = (int(x) for x in baris[0])
    assert hari_tertutup == len(hari), "setiap hari rencana harus punya kiriman"
    assert lokasi == 10, "seluruh lokasi demo ikut"
    assert jumlah == len(hari) * 10, f"harusnya {len(hari) * 10} kiriman, dapat {jumlah}"

    # Tidak ada kiriman demo di luar rentang rencana.
    liar = _q(
        "SELECT count(*) FROM delivery_events de JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "WHERE de.origin = 'demo' AND (mp.plan_date < :a OR mp.plan_date > :b)",
        a=HARI_PERTAMA_DEMO,
        b=HARI_TERAKHIR_DEMO,
    )
    assert int(liar[0][0]) == 0


def test_kiriman_tidak_nol_dan_tidak_melebihi_rencana():
    """Porsi terkirim = 80–100% rencana (bukan nol, bukan lebih dari rencana)."""
    rusak = _q(
        "SELECT count(*) FROM delivery_events de JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "WHERE de.origin = 'demo' AND (de.delivered_portions <= 0 "
        "OR de.delivered_portions > mp.planned_portions)"
    )
    assert int(rusak[0][0]) == 0
    # Ada variasi wajar, bukan semua 100% (kalau semua sama, deretnya bohong).
    beragam = _q(
        "SELECT count(DISTINCT de.delivered_portions * 100 / mp.planned_portions) "
        "FROM delivery_events de JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "WHERE de.origin = 'demo'"
    )
    assert int(beragam[0][0]) >= 2


def _kanonik_kiriman() -> int:
    """Kiriman kanonik di jendela kanonik 1–7 Okt (di luar itu bukan milik seed)."""
    baris = _q(
        "SELECT count(*) FROM delivery_events de "
        "JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "WHERE de.origin = 'seed' AND mp.plan_date >= DATE '2026-10-01' "
        "AND mp.plan_date <= DATE '2026-10-07'"
    )
    return int(baris[0][0])


def _kanonik_limbah() -> int:
    """Limbah kanonik 4–7 Okt (rentang asli `disposal_events` seed)."""
    baris = _q(
        "SELECT count(*) FROM disposal_events WHERE origin = 'seed' "
        "AND disposed_at >= TIMESTAMP '2026-10-04 00:00:00+00' "
        "AND disposed_at < TIMESTAMP '2026-10-08 00:00:00+00'"
    )
    return int(baris[0][0])


def test_kiriman_dan_limbah_kanonik_tetap_utuh():
    """Baris kanonik 1–7 Okt tidak boleh berubah (70 kiriman, 20 limbah)."""
    assert _kanonik_kiriman() == 70
    assert _kanonik_limbah() == 20
    # Jangkar agenda: 2 Okt di Jakarta (rencana 1200 porsi) tetap 1200 terkirim.
    baris = _q(
        "SELECT sum(de.delivered_portions) FROM delivery_events de "
        "JOIN menu_plans mp ON mp.id = de.menu_plan_id "
        "JOIN locations l ON l.id = mp.location_id "
        "WHERE de.origin = 'seed' AND mp.plan_date = DATE '2026-10-02' "
        "AND l.name = 'Jakarta'"
    )
    assert int(baris[0][0]) == 1200


def test_limbah_demo_terisi_dengan_alasan_yang_dikenal():
    """Dua catatan limbah per hari rencana, alasan dari domain kanonik."""
    hari = _hari_rencana()
    assert _jumlah_limbah("demo") == len(hari) * 2
    alasan = {
        r[0]
        for r in _q("SELECT DISTINCT reason FROM disposal_events WHERE origin = 'demo'")
    }
    assert alasan <= {"spoilage_cold_chain", "expired_transport"}, alasan
    nol = _q(
        "SELECT count(*) FROM disposal_events WHERE origin = 'demo' AND quantity_kg <= 0"
    )
    assert int(nol[0][0]) == 0


def test_purge_hanya_membuang_baris_demo():
    """Purge membersihkan kedua tabel, tanpa menyentuh baris kanonik."""
    asyncio.run(purge_demo_rows())
    assert _jumlah_kiriman("demo") == 0
    assert _jumlah_limbah("demo") == 0
    assert _kanonik_kiriman() == 70
    assert _kanonik_limbah() == 20
    # Dipulihkan lagi supaya tes berikutnya (KPI/agenda) tetap punya data.
    asyncio.run(generate_timeseries(DEFAULT_START, DEFAULT_END, interval_hours=12))


def test_kpi_jendela_7_hari_kini_terisi(client, monitor_headers):
    """Dua kartu yang dulu kosong harus available dengan sampel nyata."""
    akhir = datetime.now(UTC) + timedelta(hours=24)
    mulai = akhir - timedelta(days=7)
    r = client.get(
        "/kpi",
        params={"start": mulai.isoformat(), "end": akhir.isoformat()},
        headers=monitor_headers,
    )
    assert r.status_code == 200, r.text
    kartu = {m["name"]: m for m in r.json()["metrics"]}

    continuity = kartu["Meal Continuity Rate"]
    assert continuity["state"] == "available", continuity
    assert float(continuity["value"]) > 0, "ada rencana + kiriman → continuity > 0"

    limbah = kartu["Avoidable Food Loss"]
    assert limbah["state"] == "available", limbah
    assert int(limbah["sample_count"]) > 0
    assert float(limbah["value"]) > 0


def test_agenda_hari_setelah_kanonik_punya_kiriman_dan_limbah(client, monitor_headers):
    """12 Okt: kiriman + limbah tampil; 6 Nov (di luar rencana) tetap kosong."""
    r = client.get(
        "/agenda",
        params={"start": "2026-10-12", "end": "2026-10-12"},
        headers=monitor_headers,
    )
    assert r.status_code == 200, r.text
    hari = r.json()["days"][0]
    assert hari["delivery"]["available"] is True, hari["delivery"]
    assert hari["delivery"]["rows"] > 0
    assert hari["disposal"]["available"] is True, hari["disposal"]
    assert hari["disposal"]["rows"] > 0

    luar = client.get(
        "/agenda",
        params={"start": "2026-11-06", "end": "2026-11-06"},
        headers=monitor_headers,
    )
    assert luar.status_code == 200, luar.text
    hari_luar = luar.json()["days"][0]
    assert hari_luar["delivery"]["available"] is False
    assert hari_luar["disposal"]["available"] is False
