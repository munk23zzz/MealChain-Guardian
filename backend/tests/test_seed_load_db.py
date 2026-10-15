"""Test load seed ke PostgreSQL + idempotensi (Task 10).

Menjalankan load dua kali dengan reference time sama:
- jumlah row tidak bertambah pada load kedua
- payload kanonik identik
- angka terkunci Cianjur/Jakarta/Bogor + supplier quotes terverifikasi
"""

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.seed.seed_data import build_seed_rows, canonical_hash, load_seed

DB_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

# Ruling REF seed canonical (Roy 2026-10-09): dataset demo ter-anchor ke
# REF 2026-10-08 12:00 UTC — konsisten dengan final gate sprint 3 (551 passed).
# load_seed dengan REF lain menduplikasi baris (id stabil bergantung REF).
REF = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


@pytest.mark.asyncio
async def test_load_twice_is_idempotent(sync_engine):
    await load_seed(REF)
    snap1 = _snapshot(sync_engine)
    await load_seed(REF)
    snap2 = _snapshot(sync_engine)

    assert canonical_hash(snap1) == canonical_hash(snap2)
    # Load kedua tidak menambah row time-series apa pun
    assert snap2["counts"] == snap1["counts"]


def test_locked_values_cianjur_jakarta_bogor(sync_engine):
    with sync_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT s.quantity_kg FROM supply_records s "
                "JOIN locations l ON l.id = s.location_id "
                "JOIN commodities c ON c.id = s.commodity_id "
                "WHERE l.name='Cianjur' AND c.name='telur' "
                "ORDER BY s.recorded_at DESC LIMIT 1"
            )
        ).scalar_one()
        assert float(row) == 1400.0

        row = conn.execute(
            text(
                "SELECT s.quantity_kg FROM supply_records s "
                "JOIN locations l ON l.id = s.location_id "
                "JOIN commodities c ON c.id = s.commodity_id "
                "WHERE l.name='Jakarta' AND c.name='telur' "
                "ORDER BY s.recorded_at DESC LIMIT 1"
            )
        ).scalar_one()
        assert float(row) == 300.0

        row = conn.execute(
            text(
                "SELECT s.quantity_kg FROM supply_records s "
                "JOIN locations l ON l.id = s.location_id "
                "JOIN commodities c ON c.id = s.commodity_id "
                "WHERE l.name='Bogor' AND c.name='telur' "
                "ORDER BY s.recorded_at DESC LIMIT 1"
            )
        ).scalar_one()
        assert float(row) == 800.0


def test_supplier_quotes_persisted_as_price_signals(sync_engine):
    """Revisi kedua Roy: quote = source 'supplier_quote' + supplier_id FK terisi.

    Fase 4 (2026-10-15): dibatasi `origin='seed'`. Semenjak ada deret waktu
    demo, satu pemasok punya banyak kutipan (mingguan) di tabel yang sama;
    tanpa saringan ini dict di bawah menimpa nilai kanonik dengan nilai demo.
    """
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT s.name, ps.price_per_kg FROM price_signals ps "
                "JOIN suppliers s ON s.id = ps.supplier_id "
                "WHERE ps.source = 'supplier_quote' AND ps.origin = 'seed'"
            )
        ).fetchall()
        prices = {r[0]: float(r[1]) for r in rows}
        assert prices["Supplier A Cianjur"] == 26200.0
        assert prices["Supplier B Cianjur"] == 27000.0
        assert prices["Supplier C Cianjur"] == 32000.0
        assert prices["Supplier D Cianjur"] == 25400.0


def test_seed_batches_bands_and_safety_fail(sync_engine):
    # Seleksi deterministik via UUID5 natural key (bukan window created_at
    # yang flaky saat hari bergeser)
    expected_ids = {str(b["id"]) for b in build_seed_rows(REF)["batches"]}
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT b.freshness_score, b.safety_status FROM batches b "
                "WHERE b.id = ANY(:ids)"
            ),
            {"ids": list(expected_ids)},
        ).fetchall()
        scores = [float(r[0]) for r in rows if r[0] is not None]
        safety = {r[1] for r in rows}
        assert any(s >= 0.85 for s in scores)
        assert any(0.60 <= s < 0.85 for s in scores)
        assert any(s < 0.60 for s in scores)
        assert "fail" in safety


def test_mock_sap_stock_and_confirmed_po(sync_engine):
    with sync_engine.connect() as conn:
        cianjur = conn.execute(
            text(
                "SELECT quantity FROM sap_mock_material_stock "
                "WHERE plant='CIANJ' AND material_number='1000'"
            )
        ).scalar_one()
        assert float(cianjur) == 1400.0

        po = conn.execute(
            text(
                "SELECT status FROM sap_mock_purchase_orders "
                "WHERE po_number='4500000001'"
            )
        ).scalar_one()
        assert po == "confirmed"


def _snapshot(engine) -> dict:
    with engine.connect() as conn:
        counts = {}
        for table in (
            "locations",
            "commodities",
            "suppliers",
            "supply_records",
            "demand_records",
            "price_signals",
            "batches",
            "sap_mock_material_stock",
            "sap_mock_purchase_orders",
        ):
            counts[table] = conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
        supply = conn.execute(
            text(
                "SELECT l.name, c.name, s.quantity_kg, s.source "
                "FROM supply_records s "
                "JOIN locations l ON l.id=s.location_id "
                "JOIN commodities c ON c.id=s.commodity_id "
                "ORDER BY l.name, c.name"
            )
        ).fetchall()
        prices = conn.execute(
            text(
                "SELECT l.name, c.name, ps.source, ps.price_per_kg "
                "FROM price_signals ps "
                "JOIN locations l ON l.id=ps.location_id "
                "JOIN commodities c ON c.id=ps.commodity_id "
                "ORDER BY ps.source"
            )
        ).fetchall()
    return {
        "counts": counts,
        "supply": [[str(v) for v in r] for r in supply],
        "prices": [[str(v) for v in r] for r in prices],
    }
