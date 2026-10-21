"""Fakta operasional harus dibatasi waktu evaluasi (`as_of`).

MASALAH. `fetch_operational_facts(db, as_of)` sudah memakai `as_of` untuk
menyaring batch (`harvested_at <= as_of`) dan kebutuhan menu, tetapi pasokan,
permintaan, dan harga diambil lewat `_latest_rows()` TANPA batas waktu. Karena
deret demo berjalan sampai 4 Nov, alokasi rekomendasi bisa memakai baris yang
belum terjadi — sementara peta (`/balance/map`) memakai "sekarang". Dua sisi
dashboard lalu berbicara tentang hari yang berbeda tanpa memberi tahu siapa pun.

KONTRAK yang dipaku:
- baris dengan `recorded_at > as_of` tidak boleh masuk facts;
- `as_of=None` berarti sekarang (bukan "selamanya");
- snapshot historis (`as_of` = 8 Okt) harus memberi angka kanonik, bukan angka
  demo 18 Okt/4 Nov.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import recommendation_service as rs
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_ASYNC


def _facts(as_of):
    async def _jalankan():
        engine = create_async_engine(DB_URL)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as session:
                return await rs.fetch_operational_facts(session, as_of)
        finally:
            await engine.dispose()

    return asyncio.run(_jalankan())


def _baris_terbaru(table: str, kolom: str, batas, lokasi: str, komoditas: str):
    """Nilai baris terbaru `<= batas`; `batas=None` berarti tanpa batas."""

    async def _jalankan():
        engine = create_async_engine(DB_URL)
        try:
            async with engine.connect() as conn:
                sql = (
                    f"SELECT d.{kolom} FROM {table} d "
                    "JOIN locations l ON l.id = d.location_id "
                    "JOIN commodities c ON c.id = d.commodity_id "
                    "WHERE l.name = :lok AND c.name = :kom"
                )
                params = {"lok": lokasi, "kom": komoditas}
                if batas is not None:
                    sql += " AND d.recorded_at <= :batas"
                    params["batas"] = batas
                sql += " ORDER BY d.recorded_at DESC LIMIT 1"
                return (await conn.execute(text(sql), params)).scalar_one()
        finally:
            await engine.dispose()

    return Decimal(str(asyncio.run(_jalankan())))


def test_permintaan_dan_pasokan_tidak_memakai_baris_masa_depan():
    sekarang = datetime.now(UTC)
    fakta = _facts(None)
    supply, demand = fakta[0], fakta[1]

    pasokan_batas = _baris_terbaru("supply_records", "quantity_kg", sekarang, "Jakarta", "telur")
    minta_batas = _baris_terbaru("demand_records", "quantity_kg", sekarang, "Jakarta", "telur")
    assert supply[("Jakarta", "telur")] == pasokan_batas
    assert demand[("Jakarta", "telur")] == minta_batas

    # Bukti bahwa batas itu BUKAN formalitas: tanpa batas, angkanya berbeda
    # (deret demo memasok baris sampai 4 Nov).
    pasokan_bebas = _baris_terbaru("supply_records", "quantity_kg", None, "Jakarta", "telur")
    assert pasokan_bebas != pasokan_batas


def test_snapshot_historis_memberi_angka_kanonik():
    as_of = datetime(2026, 10, 8, 12, tzinfo=UTC)
    supply, demand = _facts(as_of)[:2]
    assert supply[("Jakarta", "telur")] == _baris_terbaru(
        "supply_records", "quantity_kg", as_of, "Jakarta", "telur"
    )
    assert demand[("Jakarta", "telur")] == _baris_terbaru(
        "demand_records", "quantity_kg", as_of, "Jakarta", "telur"
    )


def test_harga_yang_dipakai_juga_dibatasi_waktu_evaluasi():
    as_of = datetime.now(UTC) - timedelta(days=3)
    refs, quotes = _facts(as_of)[2], _facts(as_of)[3]

    async def _harga(batas):
        engine = create_async_engine(DB_URL)
        try:
            async with engine.connect() as conn:
                return (
                    await conn.execute(
                        text(
                            "SELECT p.price_per_kg FROM price_signals p "
                            "JOIN locations l ON l.id = p.location_id "
                            "JOIN commodities c ON c.id = p.commodity_id "
                            "WHERE l.name = 'Jakarta' AND c.name = 'telur'"
                            " AND p.source = 'pihps_reference'"
                            " AND p.recorded_at <= :batas"
                            " ORDER BY p.recorded_at DESC LIMIT 1"
                        ),
                        {"batas": batas},
                    )
                ).scalar_one()
        finally:
            await engine.dispose()

    terbatas = Decimal(str(asyncio.run(_harga(as_of))))
    assert refs[("Jakarta", "telur")] == terbatas
    assert quotes or refs  # minimal satu sisi harga terbaca
