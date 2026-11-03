"""P6 (pakai keputusan Roy 2026-10-09): tabel facts KPI Meal Continuity
& Avoidable Food Loss — sebelumnya `unavailable` karena schema tak punya
facts-nya (ruling O-KPI: jujur, tanpa proxy). Sekarang facts-nya dibuat:

- menu_plans: rencana porsi per lokasi per tanggal (denominator continuity)
- delivery_events: porsi tersampaikan per menu plan (numerator continuity)
- disposal_events: pembuangan eksplisit (qty/reason) — basis food loss

Revision ID: 009_kpi_facts_tables
Revises: 008_rejection_loop
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "009_kpi_facts_tables"
down_revision: Union[str, None] = "008_rejection_loop"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "menu_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("location_id", UUID(as_uuid=True),
                  sa.ForeignKey("locations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("planned_portions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("location_id", "plan_date",
                            name="uq_menu_plans_loc_date"),
    )
    op.create_table(
        "delivery_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("menu_plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("menu_plans.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("delivered_portions", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False,
            server_default=sa.text("'delivered'"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_delivery_events_menu_plan", "delivery_events",
                    ["menu_plan_id"])
    op.create_table(
        "disposal_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("location_id", UUID(as_uuid=True),
                  sa.ForeignKey("locations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("commodity_id", UUID(as_uuid=True),
                  sa.ForeignKey("commodities.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("quantity_kg", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("disposed_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_disposal_events_loc_time", "disposal_events",
                    ["location_id", "disposed_at"])


def downgrade() -> None:
    op.drop_index("idx_disposal_events_loc_time", table_name="disposal_events")
    op.drop_table("disposal_events")
    op.drop_index("idx_delivery_events_menu_plan", table_name="delivery_events")
    op.drop_table("delivery_events")
    op.drop_table("menu_plans")
