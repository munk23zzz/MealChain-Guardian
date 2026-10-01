"""Integrasi schema operasional Sprint 1 — dijalankan TERHADAP PostgreSQL nyata
di dalam container backend (butuh docker compose + alembic).

Kontrak docs/Schema.md §2/§4/§5 (Sprint 1). Tabel keputusan Sprint 2 tidak
dibuat di sini; `sap_mock_purchase_orders.decision_id` sengaja tanpa FK
(tabel `decisions` baru ada di Sprint 2).
"""

import os

import pytest
from sqlalchemy import create_engine, text

DB_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

EXPECTED_TABLES = {
    "supply_records",
    "demand_records",
    "price_signals",
    "batches",
    "sap_mock_material_stock",
    "sap_mock_purchase_orders",
}

EXPECTED_COLUMNS = {
    "supply_records": {
        "id", "location_id", "commodity_id", "quantity_kg",
        "recorded_at", "source", "created_at",
    },
    "demand_records": {
        "id", "location_id", "commodity_id", "quantity_kg",
        "needed_by", "recorded_at", "created_at",
    },
    "price_signals": {
        "id", "location_id", "commodity_id", "price_per_kg",
        "recorded_at", "source", "created_at",
    },
    "batches": {
        "id", "commodity_id", "location_id", "supplier_id", "quantity_kg",
        "harvested_at", "temperature_log", "certification_status",
        "freshness_score", "safety_status", "usable_until", "created_at",
    },
    "sap_mock_material_stock": {
        "id", "material_number", "plant", "storage_location", "batch",
        "quantity", "unit", "created_at",
    },
    "sap_mock_purchase_orders": {
        "id", "po_number", "supplier_id", "material_number",
        "ordered_quantity", "price", "decision_id", "status", "created_at",
    },
}

EXPECTED_CHECKS = {
    # Fragment harus cocok render kanonik Postgres (pg_get_constraintdef, lowercase)
    "supply_records": "quantity_kg >= (0)::numeric",
    "demand_records": "quantity_kg >= (0)::numeric",
    "price_signals": "price_per_kg > (0)::numeric",
    "batches": "(freshness_score >= (0)::numeric) and (freshness_score <= (1)::numeric)",
}

EXPECTED_INDEXES = {
    ("supply_records", "idx_supply_location_commodity"),
    ("demand_records", "idx_demand_location_commodity"),
    ("batches", "idx_batches_safety_status"),
}


@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


def test_operational_tables_exist(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ).scalars().all()
    tables = set(rows)
    missing = EXPECTED_TABLES - tables
    assert not missing, f"tabel operasional belum ada: {sorted(missing)}"


def test_operational_columns_match_contract(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            )
        ).all()
    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(table_name, set()).add(column_name)

    for table, expected_columns in EXPECTED_COLUMNS.items():
        for column in expected_columns:
            assert column in actual.get(table, set()), (
                f"kolom {table}.{column} tidak ada"
            )


def test_check_constraints_present(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conrelid::regclass::text AS table_name, pg_get_constraintdef(oid) "
                "FROM pg_constraint WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
            )
        ).all()
    checks: dict[str, str] = {}
    for table, definition in rows:
        checks[table] = f"{checks.get(table, '')};{definition.lower()}"

    for table, fragment in EXPECTED_CHECKS.items():
        assert fragment in checks.get(table, ""), (
            f"check constraint {table}: {fragment} tidak ditemukan"
        )


def test_decisions_table_still_absent(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'decisions'"
            )
        ).scalars().all()
    assert rows == [], "decisions adalah kontrak Sprint 2 — jangan dibuat sekarang"


def test_po_decision_id_has_no_foreign_key(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.constraint_column_usage ccu "
                "ON tc.constraint_name = ccu.constraint_name "
                "WHERE tc.constraint_type = 'FOREIGN KEY' "
                "AND tc.table_name = 'sap_mock_purchase_orders' "
                "AND ccu.column_name = 'decision_id'"
            )
        ).scalars().all()
    assert rows == [], "decision_id belum boleh punya FK sebelum tabel decisions ada"


def test_required_indexes_present(sync_engine):
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename, indexname FROM pg_indexes "
                "WHERE schemaname = 'public'"
            )
        ).all()
    indexes = set(rows)
    for table, index in EXPECTED_INDEXES:
        assert (table, index) in indexes, f"indeks {index} di {table} tidak ada"
