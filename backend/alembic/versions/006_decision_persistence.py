"""Decision persistence schema (Task 8 Sprint 2).

Kontrak docs/Schema.md §3 + keputusan Roy 2026-10-05:
- decisions: kolom lengkap + expires_at TIMESTAMPTZ NOT NULL (approved).
  Validitas: now < expires_at valid; now >= expires_at expired; keputusan
  expired tetap disimpan (audit), tidak dihapus, tidak dihidupkan ulang.
- decision_evidence: FK decision_id → decisions.id, ondelete CASCADE.
- sap_mock_purchase_orders.decision_id: FK dipasang (dijanjikan sejak
  Sprint 1), ondelete SET NULL — PO tidak boleh ikut terhapus.
- Index idx_decisions_status per Schema.md.
- approvals & agent_traces DIBUAT DI SINI juga: Schema.md mendefinisikannya
  sebagai bagian blok keputusan (§3) dan Task 10+ memakai decision_id
  link-nya; menunda justru memecah kontrak skema tunggal.

Revision ID: 006_decision_persistence
Revises: 005_reconcile_sprint1_schema
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_decision_persistence"
down_revision: Union[str, None] = "005_reconcile_sprint1_schema"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "decision_type", sa.Text(), nullable=False,
            server_default="regional_balance",
        ),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="proposed",
        ),
        sa.Column(
            "proposed_by", sa.Text(), nullable=False,
            server_default="supervisor_agent",
        ),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("verifier_note", sa.Text(), nullable=True),
        sa.Column(
            "source_location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"), nullable=True,
        ),
        sa.Column(
            "target_location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"), nullable=True,
        ),
        sa.Column(
            "commodity_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commodities.id"), nullable=True,
        ),
        sa.Column("quantity_kg", sa.Numeric(10, 2), nullable=True),
        sa.Column("safe_delivered_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision_type IN "
            "('regional_balance','price_anomaly','safety_disruption')",
            name="decisions_decision_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','verifier_flagged','pending_approval',"
            "'approved','rejected','executed')",
            name="decisions_status_check",
        ),
        sa.CheckConstraint(
            "quantity_kg IS NULL OR quantity_kg > 0",
            name="decisions_quantity_positive_check",
        ),
    )
    op.create_index(
        "idx_decisions_status", "decisions", ["status"], unique=False
    )

    op.create_table(
        "decision_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "decision_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_consistent", sa.Boolean(), nullable=True),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "evidence_type IN ('sap_purchase_order','sap_goods_receipt',"
            "'gps','temperature','human_inspection','market_price')",
            name="decision_evidence_type_check",
        ),
    )

    op.create_table(
        "approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "decision_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "approved_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "approved_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "agent_traces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "decision_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("tool_called", sa.Text(), nullable=True),
        sa.Column(
            "input_summary", postgresql.JSONB(), nullable=True,
        ),
        sa.Column(
            "output_summary", postgresql.JSONB(), nullable=True,
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "step_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "step_name IN ('DETECT','VERIFY','TRACE','PREDICT','OPTIMIZE',"
            "'DECIDE','ACT','LEARN')",
            name="agent_traces_step_name_check",
        ),
    )

    # FK dijanjikan sejak Sprint 1 (002 tanpa FK): pasang sekarang.
    op.create_foreign_key(
        "sap_po_decision_fk",
        "sap_mock_purchase_orders",
        "decisions",
        ["decision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "sap_po_decision_fk", "sap_mock_purchase_orders", type_="foreignkey"
    )
    op.drop_table("agent_traces")
    op.drop_table("approvals")
    op.drop_table("decision_evidence")
    op.drop_index("idx_decisions_status", table_name="decisions")
    op.drop_table("decisions")
