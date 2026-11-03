"""Supplier exclusion history and administrative decision types.

Revision ID: 011_supplier_exclusions
Revises: 010_ledger_blocks
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "011_supplier_exclusions"
down_revision: Union[str, None] = "010_ledger_blocks"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.drop_constraint("decisions_decision_type_check", "decisions", type_="check")
    op.create_check_constraint(
        "decisions_decision_type_check",
        "decisions",
        "decision_type IN ('regional_balance','price_anomaly','safety_disruption',"
        "'supplier_exclusion','supplier_exclusion_restoration')",
    )
    op.create_table(
        "supplier_exclusions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column(
            "scope_location_id", UUID(as_uuid=True), sa.ForeignKey("locations.id"), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_refs", JSONB(), nullable=False),
        sa.Column(
            "source_decision_id", UUID(as_uuid=True), sa.ForeignKey("decisions.id"), nullable=False
        ),
        sa.Column(
            "restoration_decision_id",
            UUID(as_uuid=True),
            sa.ForeignKey("decisions.id"),
            nullable=True,
        ),
        sa.Column("proposed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('proposed','active','rejected','revoked')",
            name="supplier_exclusions_status_check",
        ),
    )
    op.create_index(
        "uq_supplier_exclusions_active_scope",
        "supplier_exclusions",
        ["supplier_id", "scope_location_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_supplier_exclusions_scope",
        "supplier_exclusions",
        ["supplier_id", "scope_location_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_supplier_exclusions_scope", table_name="supplier_exclusions")
    op.drop_index("uq_supplier_exclusions_active_scope", table_name="supplier_exclusions")
    op.drop_table("supplier_exclusions")
    op.drop_constraint("decisions_decision_type_check", "decisions", type_="check")
    op.create_check_constraint(
        "decisions_decision_type_check",
        "decisions",
        "decision_type IN ('regional_balance','price_anomaly','safety_disruption')",
    )
