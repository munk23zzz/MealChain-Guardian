"""Batas argumen asyncpg pada regenerasi deret waktu.

Postgres/asyncpg menolak satu statement dengan lebih dari 32767 argumen bind.
Sebelum `_potong()` ada, `_upsert_supply` mengirim SEMUA baris dalam satu
INSERT: 7 argumen per baris, jadi ~4700 baris sudah cukup untuk mematikan
seluruh regenerasi dengan

    InterfaceError: the number of query arguments cannot exceed 32767

Regenerasi besar (banyak hari x lokasi x komoditas) memang mencapai angka itu,
jadi tes ini mengunci dua hal: pemotongan baris benar, dan 5000 baris benar-
benar bisa dieksekusi dalam satu panggilan `_upsert_supply`.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.seed.timeseries import _potong, _upsert_supply

# 32767 argumen / 7 kolom per baris supply_records -> ~4681 baris adalah plafon.
AMAN_ARGUMEN = 32767
KOLOM_SUPPLY = 7


def test_potong_menutup_semua_baris_tanpa_duplikat():
    rows = [{"i": i} for i in range(2500)]
    bagian = list(_potong(rows))

    assert [len(b) for b in bagian] == [1000, 1000, 500]
    assert [row["i"] for b in bagian for row in b] == list(range(2500))


def test_potong_tidak_pernah_melewati_batas_argumen_asyncpg():
    # 5000 baris x 7 kolom = 35000 argumen: tanpa pemotongan ini pasti gagal.
    rows = [{"i": i} for i in range(5000)]
    assert 5000 * KOLOM_SUPPLY > AMAN_ARGUMEN

    for bagian in _potong(rows):
        assert len(bagian) * KOLOM_SUPPLY <= AMAN_ARGUMEN


def test_potong_kosong_tidak_menghasilkan_apa_pun():
    assert list(_potong([])) == []


def test_upsert_supply_5000_baris_tidak_melewati_batas_argumen():
    """Regresi langsung: satu panggilan, 5000 baris, harus sukses.

    Semua tulisan di-rollback, jadi tes ini tidak meninggalkan residu di DB demo.
    """

    async def _jalan():
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                pasangan = (
                    await session.execute(
                        text(
                            "SELECT s.location_id, s.commodity_id FROM supply_records s "
                            "WHERE s.origin = 'seed' LIMIT 1"
                        )
                    )
                ).first()
                assert pasangan is not None, "butuh minimal satu baris seed sebagai jangkar FK"

                lokasi, komoditas = pasangan
                dasar = datetime(2026, 1, 1, tzinfo=UTC)
                rows = [
                    {
                        "location_id": lokasi,
                        "commodity_id": komoditas,
                        "quantity_kg": Decimal("10.00"),
                        "recorded_at": dasar + timedelta(minutes=i),
                        "source": "mock_sap",
                        "origin": "demo",
                    }
                    for i in range(5000)
                ]

                await _upsert_supply(session, rows, datetime.now(UTC))
                await session.rollback()
        finally:
            await engine.dispose()

    asyncio.run(_jalan())
