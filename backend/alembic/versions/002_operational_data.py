"""Tabel operasional Sprint 1 — Schema.md §2/§4/§5

Revision ID: 002_operational_data
Revises: 001_master_data
Create Date: 2026-10-01

Kontrak:
- Persis docs/Schema.md §2 (supply_records, demand_records, price_signals, batches)
  dan §4 (sap_mock_material_stock, sap_mock_purchase_orders).
- Tabel `decisions` adalah kontrak Sprint 2 — TIDAK dibuat di sini, sehingga
  sap_mock_purchase_orders.decision_id = UUID nullable TANPA FK.
- Check constraint sesuai Schema: quantity >= 0, price > 0, freshness 0..1,
  safety enum 4 nilai.
- Indeks §5 untuk tabel Sprint 1 + indeks query "terbaru per pasangan"
  (location_id, commodity_id, recorded_at DESC) untuk supply dan demand.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_operational_data"
down_revision: Union[str, None] = "001_master_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _uuid_pk():
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
_created_at = lambda: sa.Column(  # noqa: E731
    "created_at", sa.DateTime(timezone=True), nullable=False,
    server_default=sa.func.now(),
)
_location_fk = lambda: sa.Column(  # noqa: E731
    "location_id", postgresql.UUID(as_uuid=True),
    sa.ForeignKey("locations.id"), nullable=False,
)
_commodity_fk = lambda: sa.Column(  # noqa: E731
    "commodity_id", postgresql.UUID(as_uuid=True),
    sa.ForeignKey("commodities.id"), nullable=False,
)


def upgrade() -> None:
    op.create_table(
        "supply_records",
        _uuid_pk(),
        _location_fk(),
        _commodity_fk(),
        sa.Column("quantity_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        _created_at(),
        sa.CheckConstraint("quantity_kg >= 0", name="supply_records_quantity_nonneg_check"),
        sa.CheckConstraint(
            "source IN ('mock_sap','manual','sensor')",
            name="supply_records_source_check",
        ),
    )

    op.create_table(
        "demand_records",
        _uuid_pk(),
        _location_fk(),
        _commodity_fk(),
        sa.Column("quantity_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("needed_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.CheckConstraint("quantity_kg >= 0", name="demand_records_quantity_nonneg_check"),
    )

    op.create_table(
        "price_signals",
        _uuid_pk(),
        _location_fk(),
        _commodity_fk(),
        sa.Column("price_per_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        _created_at(),
        sa.CheckConstraint("price_per_kg > 0", name="price_signals_price_positive_check"),
        sa.CheckConstraint(
            "source IN ('pihps_reference','supplier_quote')",
            name="price_signals_source_check",
        ),
    )

    op.create_table(
        "batches",
        _uuid_pk(),
        sa.Column(
            "commodity_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commodities.id"), nullable=False,
        ),
        sa.Column(
            "location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"), nullable=False,
        ),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"), nullable=False,
        ),
        sa.Column("quantity_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("harvested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "temperature_log", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("certification_status", sa.String(), nullable=False, server_default="none"),
        sa.Column("freshness_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("safety_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("usable_until", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "freshness_score IS NULL OR (freshness_score >= 0 AND freshness_score <= 1)",
            name="batches_freshness_range_check",
        ),
        sa.CheckConstraint(
            "safety_status IN ('pending','pass','fail','needs_verification')",
            name="batches_safety_status_check",
        ),
        sa.CheckConstraint(
            "certification_status IN ('none','hygiene','haccp')",
            name="batches_certification_check",
        ),
    )

    op.create_table(
        "sap_mock_material_stock",
        _uuid_pk(),
        sa.Column("material_number", sa.String(), nullable=False),
        sa.Column("plant", sa.String(), nullable=False),
        sa.Column("storage_location", sa.String(), nullable=True),
        sa.Column("batch", sa.String(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        _created_at(),
    )

    op.create_table(
        "sap_mock_purchase_orders",
        _uuid_pk(),
        sa.Column("po_number", sa.String(), nullable=False, unique=True),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"), nullable=False,
        ),
        sa.Column("material_number", sa.Text(), nullable=False),
        sa.Column("ordered_quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        _created_at(),
        sa.CheckConstraint(
            "status IN ('draft','submitted','confirmed')",
            name="sap_mock_po_status_check",
        ),
        sa.CheckConstraint("price > 0", name="sap_mock_po_price_positive_check"),
    )

    # Indeks §5 (tabel Sprint 1) + indeks query terbaru-per-pasangan
    op.create_index("idx_supply_location_commodity", "supply_records", ["location_id", "commodity_id"])
    op.create_index("idx_demand_location_commodity", "demand_records", ["location_id", "commodity_id"])
    op.create_index("idx_batches_safety_status", "batches", ["safety_status"])
    op.create_index(
        "idx_supply_latest",
        "supply_records",
        ["location_id", "commodity_id", sa.text("recorded_at DESC")],
    )
    op.create_index(
        "idx_demand_latest",
        "demand_records",
        ["location_id", "commodity_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_demand_latest", table_name="demand_records")
    op.drop_index("idx_supply_latest", table_name="supply_records")
    op.drop_index("idx_batches_safety_status", table_name="batches")
    op.drop_index("idx_demand_location_commodity", table_name="demand_records")
    op.drop_index("idx_supply_location_commodity", table_name="supply_records")
    op.drop_table("sap_mock_purchase_orders")
    op.drop_table("sap_mock_material_stock")
    op.drop_table("batches")
    op.drop_table("price_signals")
    op.drop_table("demand_records")
    op.drop_table("supply_records")
