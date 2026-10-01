"""Master data tables — 3 role final (Schema.md §1)

Revision ID: 001_master_data
Revises:
Create Date: 2026-09-30

Kontrak:
- PK UUID dengan server default gen_random_uuid()
- created_at TIMESTAMPTZ DEFAULT now()
- users.role hanya 3 nilai: sppg_head | sppg_nutritionist | bgn_monitor
- sppg_head/sppg_nutritionist WAJIB punya location_id; bgn_monitor WAJIB NULL
- suppliers.reliability_score CHECK 0..1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_master_data"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "locations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("region", sa.String(), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("role_hint", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "commodities",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("unit", sa.String(), nullable=False, server_default="kg"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "suppliers",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"), nullable=False,
        ),
        sa.Column("reliability_score", sa.Numeric(3, 2), nullable=False, server_default="0.80"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="check_reliability",
        ),
    )

    op.create_table(
        "users",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column(
            "location_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("locations.id"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('sppg_head','sppg_nutritionist','bgn_monitor')",
            name="check_user_role",
        ),
        sa.CheckConstraint(
            "(role IN ('sppg_head','sppg_nutritionist') AND location_id IS NOT NULL) "
            "OR (role = 'bgn_monitor' AND location_id IS NULL)",
            name="check_user_role_location_scope",
        ),
    )

    op.create_index("idx_suppliers_location", "suppliers", ["location_id"])
    op.create_index("idx_users_location", "users", ["location_id"])


def downgrade() -> None:
    op.drop_index("idx_users_location", table_name="users")
    op.drop_index("idx_suppliers_location", table_name="suppliers")
    op.drop_table("users")
    op.drop_table("suppliers")
    op.drop_table("commodities")
    op.drop_table("locations")
