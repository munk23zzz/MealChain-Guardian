"""Permintaan demo: deret yang sepadan dengan pasokan (audit 18 Okt 2026).

MASALAH yang dipaku di sini. Deret demo memperluas pasokan/harga/menu sampai
5 Nov, tetapi `demand_records` hanya punya baris KANONIK 8 Okt. Akibatnya label
peta selalu berbunyi "pasokan per 18 Okt · permintaan per 8 Okt" — dua tanggal
berjauhan yang membuat dashboard "Hari Ini" terasa aneh, padahal kedua angka
sama-sama benar.

ATURAN yang ditegakkan:
- permintaan dicatat SATU kali per hari pada 00:00 UTC (rencana menu), bukan
  mengikuti kadens telemetri pasokan 12 jam — supaya kadensnya tidak tercampur;
- nilainya bergerak di sekitar baseline KANONIK pasangan itu (bukan angka baru):
  variasi lebih kecil dari pasokan (permintaan institusional mengikuti rencana
  menu), tetap memakai pola akhir-pekan yang sudah ada;
- `needed_by` = `recorded_at` + 3 hari, sama dengan jarak baris kanonik;
- HANYA pasangan yang memang punya permintaan kanonik (Bandung & Cianjur tetap
  "belum ada catatan" — itu fakta, bukan kekurangan data yang perlu ditutupi);
- baris demo tidak boleh menimpa baris kanonik (kunci unik lokasi×komoditas×waktu).
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import DemandRecord
from app.seed.timeseries import (
    DEFAULT_END,
    DEFAULT_START,
    DEMAND_LEAD_DAYS,
    DEMAND_NOISE_SPREAD,
    PURGE_MODELS,
    WEEKEND_FACTOR,
    _upsert_demand,
    plan_all,
    plan_demand_rows,
)
from tests.dsn import DSN_ASYNC, DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC


def _pairs(n: int = 2, baseline: str = "1080") -> list[tuple[str, uuid.UUID, uuid.UUID, Decimal]]:
    return [
        (
            f"pair-{i}",
            uuid.uuid4(),
            uuid.uuid4(),
            Decimal(baseline),
        )
        for i in range(n)
    ]


def _stamps() -> list[datetime]:
    """Stempel campuran: 8 Okt (sebelum mulai), 15–17 Okt 00:00, plus 12:00.

    Stempel 12:00 WAJIB ada di daftar: kalau generator ikut menulis di situ,
    kadens permintaan bercampur dengan telemetri pasokan dan tes ini gagal.
    """
    return [
        datetime(2026, 10, 8, 0, 0, tzinfo=UTC),  # sebelum DEMAND_DEMO_START
        datetime(2026, 10, 15, 0, 0, tzinfo=UTC),  # Kamis
        datetime(2026, 10, 15, 12, 0, tzinfo=UTC),  # kadens pasokan -> dilewati
        datetime(2026, 10, 16, 0, 0, tzinfo=UTC),
        datetime(2026, 10, 17, 0, 0, tzinfo=UTC),  # Sabtu
        datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    ]


def test_satu_observasi_per_hari_setelah_kanonik():
    rows = plan_demand_rows(_pairs(2), _stamps())
    # 2 pasangan × 3 hari (15, 16, 17 Okt) — 8 Okt & semua jam 12:00 dilewati.
    assert len(rows) == 2 * 3
    assert {row["recorded_at"].hour for row in rows} == {0}
    assert min(row["recorded_at"] for row in rows) >= datetime(2026, 10, 9, tzinfo=UTC)
    assert all(row["origin"] == "demo" for row in rows)


def test_needed_by_tiga_hari_setelah_dicatat():
    rows = plan_demand_rows(_pairs(1), _stamps())
    for row in rows:
        assert row["needed_by"] == row["recorded_at"] + timedelta(days=DEMAND_LEAD_DAYS)


def test_nilai_dekat_baseline_dan_akhir_pekan_lebih_rendah():
    baseline = Decimal("1080")
    rows = plan_demand_rows(_pairs(1, "1080"), _stamps())
    weekday = [r["quantity_kg"] for r in rows if r["recorded_at"].weekday() < 5]
    weekend = [r["quantity_kg"] for r in rows if r["recorded_at"].weekday() >= 5]
    assert weekday and weekend
    for value in weekday:
        assert abs(value - baseline) <= baseline * DEMAND_NOISE_SPREAD
    for value in weekend:
        # Akhir pekan lebih sedikit, tetapi tidak hilang.
        assert value <= baseline * WEEKEND_FACTOR * (1 + DEMAND_NOISE_SPREAD)
        assert value >= baseline * WEEKEND_FACTOR * (1 - DEMAND_NOISE_SPREAD)
    assert sum(weekend) / len(weekend) < sum(weekday) / len(weekday)


def test_rencana_deterministik():
    pairs, stamps = _pairs(2), _stamps()
    assert plan_demand_rows(pairs, stamps) == plan_demand_rows(pairs, stamps)


def test_plan_all_menyertakan_permintaan():
    plan = plan_all(
        supply_pairs=[],
        reference_pairs=[],
        quotes=[],
        menu_bases=[],
        demand_pairs=_pairs(1),
        start=DEFAULT_START,
        end=DEFAULT_END,
    )
    assert "demand" in plan
    # 9 Okt .. 4 Nov = 27 hari (satu observasi per hari), bukan 130 stempel 12 jam.
    assert len(plan["demand"]) == 27
    assert plan["event_plan"]["demand"] == len(plan["demand"])


def test_purge_mencakup_permintaan_demo():
    """Tanpa `DemandRecord` di PURGE_MODELS, permintaan demo tak bisa di-rollback."""
    assert DemandRecord in PURGE_MODELS


def test_upsert_tidak_menimpa_baris_kanonik_dan_idempoten():
    """Baris demo boleh ditulis ulang; baris kanonik 8 Okt tidak boleh berubah."""
    loc_id, com_id = uuid.uuid4(), uuid.uuid4()
    canonical = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    kunci = uuid.uuid4().hex[:8]

    async def _jalankan() -> None:
        engine = create_async_engine(
            DSN_ASYNC
        )
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as session:
                # Lokasi & komoditas uji (FK wajib ada).
                await session.execute(
                    text(
                        "INSERT INTO locations (id, name, region, latitude, longitude)"
                        " VALUES (:id, :n, 'Test Region', -6.2, 106.8)"
                    ),
                    {"id": loc_id, "n": f"TEST-{kunci}"},
                )
                await session.execute(
                    text("INSERT INTO commodities (id, name, unit)" " VALUES (:id, :n, 'kg')"),
                    {"id": com_id, "n": f"uji-{kunci}"},
                )
                await session.execute(
                    text(
                        "INSERT INTO demand_records (location_id, commodity_id,"
                        " quantity_kg, needed_by, recorded_at, origin)"
                        " VALUES (:l, :c, 500, :nb, :at, 'seed')"
                    ),
                    {
                        "l": loc_id,
                        "c": com_id,
                        "nb": canonical + timedelta(days=3),
                        "at": canonical,
                    },
                )
                rows = [
                    {
                        "location_id": loc_id,
                        "commodity_id": com_id,
                        "quantity_kg": Decimal("510.00"),
                        "needed_by": canonical + timedelta(days=DEMAND_LEAD_DAYS),
                        "recorded_at": canonical,
                        "origin": "demo",
                    },
                    {
                        "location_id": loc_id,
                        "commodity_id": com_id,
                        "quantity_kg": Decimal("512.00"),
                        "needed_by": canonical + timedelta(days=DEMAND_LEAD_DAYS, hours=12),
                        "recorded_at": canonical + timedelta(hours=12),
                        "origin": "demo",
                    },
                ]
                await _upsert_demand(session, rows, datetime.now(UTC))
                await session.commit()
                # Kali kedua: idempoten (tidak menambah baris baru).
                await _upsert_demand(session, rows, datetime.now(UTC))
                await session.commit()

                kanonik = (
                    await session.execute(
                        text(
                            "SELECT quantity_kg FROM demand_records"
                            " WHERE location_id=:l AND commodity_id=:c"
                            " AND recorded_at=:at AND origin='seed'"
                        ),
                        {"l": loc_id, "c": com_id, "at": canonical},
                    )
                ).scalar_one()
                assert float(kanonik) == 500.0
                jumlah = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM demand_records"
                            " WHERE location_id=:l AND commodity_id=:c"
                        ),
                        {"l": loc_id, "c": com_id},
                    )
                ).scalar_one()
                assert int(jumlah) == 2, "kunci unik lokasi×komoditas×waktu harus dipakai"
        finally:
            await engine.dispose()

    try:
        asyncio.run(_jalankan())
    finally:
        engine = create_engine(DB_URL)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM demand_records WHERE location_id=:l"),
                    {"l": loc_id},
                )
                conn.execute(text("DELETE FROM locations WHERE id=:l"), {"l": loc_id})
                conn.execute(text("DELETE FROM commodities WHERE id=:c"), {"c": com_id})
        finally:
            engine.dispose()
