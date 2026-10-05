"""Task 8 Sprint 2: schema persistence decision + expires_at.

Butuh migration 006 — skip otomatis bila belum ter-aplikasi.

Kontrak (docs/Schema.md §3 + keputusan Roy 2026-10-05):
- decisions.expires_at TIMESTAMPTZ NOT NULL (approved).
- decision_type & status CHECK sesuai Schema.md.
- decision_evidence.decision_id FK → decisions.id NOT NULL, CASCADE.
- sap_mock_purchase_orders.decision_id FK → decisions.id (dijanjikan
  Sprint 1), ondelete SET NULL.
- Index idx_decisions_status per Schema.md.
Setiap expected-rejection dijalankan dalam transaksinya sendiri agar
transaksi utama tidak ter-aborsi (pola self-cleaning Sprint 1).
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _has_006(engine) -> bool:
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name='decisions')"
            )
        ).scalar()
    return bool(exists)


def _cleanup_decisions(engine, decision_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"), {"id": decision_id}
        )


def test_decisions_table_with_expires_at_not_null():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        with engine.connect() as conn:
            nullable = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name='decisions' "
                    "AND column_name='expires_at'"
                )
            ).scalar()
            dtype = conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name='decisions' "
                    "AND column_name='expires_at'"
                )
            ).scalar()
        assert nullable == "NO"
        assert dtype == "timestamp with time zone"
    finally:
        engine.dispose()


def test_insert_without_expires_at_rejected():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type) "
                        "VALUES ('regional_balance')"
                    )
                )
    finally:
        engine.dispose()


def test_status_and_type_constraints_enforced():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        # decision_type di luar kontrak ditolak
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type, expires_at) "
                        "VALUES ('jaran', now() + interval '30 minutes')"
                    )
                )
        # status di luar kontrak ditolak
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type, status, "
                        "expires_at) VALUES ('regional_balance', 'jaran', "
                        "now() + interval '30 minutes')"
                    )
                )
        # kombinasi valid diterima lalu dibersihkan
        with engine.begin() as conn:
            decision_id = str(
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type, expires_at) "
                        "VALUES ('regional_balance', "
                        "now() + interval '30 minutes') RETURNING id"
                    )
                ).scalar_one()
            )
        _cleanup_decisions(engine, decision_id)
    finally:
        engine.dispose()


def test_decision_evidence_fk_enforced():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        # FK ditolak untuk decision yang tidak ada
        with pytest.raises(Exception):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO decision_evidence "
                        "(decision_id, evidence_type, payload, recorded_at) "
                        "VALUES (:d, 'temperature', '{}', now())"
                    ),
                    {"d": str(uuid4())},
                )
        # FK valid: insert + cascade delete evidence
        with engine.begin() as conn:
            decision_id = str(
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type, expires_at) "
                        "VALUES ('regional_balance', "
                        "now() + interval '30 minutes') RETURNING id"
                    )
                ).scalar_one()
            )
            conn.execute(
                text(
                    "INSERT INTO decision_evidence "
                    "(decision_id, evidence_type, payload, recorded_at) "
                    "VALUES (:d, 'temperature', '{}', now())"
                ),
                {"d": decision_id},
            )
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM decisions WHERE id = :id"),
                {"id": decision_id},
            )
            left = conn.execute(
                text(
                    "SELECT count(*) FROM decision_evidence "
                    "WHERE decision_id = :d"
                ),
                {"d": decision_id},
            ).scalar()
        assert left == 0  # CASCADE menjaga evidence tidak yatim
    finally:
        engine.dispose()


def test_sap_purchase_order_fk_to_decisions():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        # decision fiktif ditolak FK
        with pytest.raises(Exception):
            with engine.begin() as conn:
                supplier_id = conn.execute(
                    text("SELECT id FROM suppliers LIMIT 1")
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO sap_mock_purchase_orders "
                        "(po_number, supplier_id, material_number, "
                        "ordered_quantity, price, decision_id, status) "
                        "VALUES ('PO-T8-A', :s, 'MAT-1', 100, 25000, "
                        ":d, 'draft')"
                    ),
                    {"s": str(supplier_id), "d": str(uuid4())},
                )
        # decision valid: PO terhubung; hapus PO lalu decision
        with engine.begin() as conn:
            decision_id = str(
                conn.execute(
                    text(
                        "INSERT INTO decisions (decision_type, expires_at) "
                        "VALUES ('regional_balance', "
                        "now() + interval '30 minutes') RETURNING id"
                    )
                ).scalar_one()
            )
            supplier_id = conn.execute(
                text("SELECT id FROM suppliers LIMIT 1")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO sap_mock_purchase_orders "
                    "(po_number, supplier_id, material_number, "
                    "ordered_quantity, price, decision_id, status) "
                    "VALUES ('PO-T8-B', :s, 'MAT-1', 100, 25000, "
                    ":d, 'draft')"
                ),
                {"s": str(supplier_id), "d": decision_id},
            )
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM sap_mock_purchase_orders "
                    "WHERE po_number = 'PO-T8-B'"
                )
            )
        _cleanup_decisions(engine, decision_id)
    finally:
        engine.dispose()


def test_status_index_exists():
    engine = create_engine(DB_URL)
    try:
        if not _has_006(engine):
            pytest.skip("migration 006 belum ter-aplikasi")
        with engine.connect() as conn:
            index = conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE tablename='decisions' "
                    "AND indexname='idx_decisions_status'"
                )
            ).scalar()
        assert index == 1
    finally:
        engine.dispose()
