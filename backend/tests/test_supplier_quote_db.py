"""Test DB-level desain quote supplier (revisi kedua Roy).

Butuh migration 004 (kolom supplier_id + constraint baru) — skip otomatis
bila migration belum ter-aplikasi.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.seed.seed_data import build_seed_rows

DB_URL = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain".replace(
    "+asyncpg", "+psycopg"
)

REF = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def _has_004(engine) -> bool:
    with engine.connect() as conn:
        col = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name='price_signals' AND column_name='supplier_id')"
            )
        ).scalar()
        cons = conn.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid='price_signals'::regclass AND conname="
                "'price_signals_source_quote_check'"
            )
        ).scalar()
    return bool(col) and bool(cons)


def test_quotes_persisted_with_supplier_id_fk():
    """Quote tersimpan dengan supplier_id FK terisi; referensi tanpa supplier."""
    engine = create_engine(DB_URL)
    try:
        if not _has_004(engine):
            pytest.skip("migration 004 belum ter-aplikasi")
        expected = build_seed_rows(REF)
        sup_by_name = {s["name"]: str(s["id"]) for s in expected["suppliers"]}
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT ps.source, ps.supplier_id, s.name "
                    "FROM price_signals ps "
                    "LEFT JOIN suppliers s ON s.id = ps.supplier_id"
                )
            ).fetchall()
        for source, supplier_id, supplier_name in rows:
            if source == "pihps_reference":
                assert supplier_id is None, "referensi tidak boleh terikat supplier"
            else:
                assert supplier_id is not None
                assert supplier_name in sup_by_name
    finally:
        engine.dispose()


def test_db_rejects_source_without_supplier_identity():
    """source='supplier_quote' tanpa supplier_id DITOLAK constraint."""
    engine = create_engine(DB_URL)
    try:
        if not _has_004(engine):
            pytest.skip("migration 004 belum ter-aplikasi")
        with engine.begin() as conn:
            loc_id = conn.execute(
                text("SELECT id FROM locations WHERE name='Cianjur'")
            ).scalar_one()
            com_id = conn.execute(
                text("SELECT id FROM commodities WHERE name='telur'")
            ).scalar_one()
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        "INSERT INTO price_signals (id, location_id, commodity_id, "
                        "price_per_kg, recorded_at, source) "
                        "VALUES (gen_random_uuid(), :l, :c, 12000, now(), "
                        "'supplier_quote')"
                    ),
                    {"l": str(loc_id), "c": str(com_id)},
                )
    finally:
        engine.dispose()
