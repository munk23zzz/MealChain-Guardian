"""Rejection loop (permintaan Roy 2026-10-07): alasan wajib + iterasi.

- decisions.rejection_reason: alasan penolakan manusia (wajib saat reject)
- decisions.iteration: v1, v2, v3... dalam satu keluarga re-propose
- decisions.supersedes_id: keputusan sebelumnya yang digantikan iterasi ini
- decisions.demo_case: penanda kasus demo (seed idempotent)

Revision ID: 008_rejection_loop
Revises: 007_supervise_step
Create Date: 2026-10-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "008_rejection_loop"
down_revision: Union[str, None] = "007_supervise_step"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "decisions",
        sa.Column(
            "iteration",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "decisions",
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "decisions",
        sa.Column("demo_case", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decisions_supersedes_id",
        "decisions",
        "decisions",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_decisions_supersedes_id", "decisions", ["supersedes_id"]
    )
    op.create_index("idx_decisions_demo_case", "decisions", ["demo_case"])


def downgrade() -> None:
    op.drop_index("idx_decisions_demo_case", table_name="decisions")
    op.drop_index("idx_decisions_supersedes_id", table_name="decisions")
    op.drop_constraint("fk_decisions_supersedes_id", "decisions", type_="foreignkey")
    op.drop_column("decisions", "demo_case")
    op.drop_column("decisions", "supersedes_id")
    op.drop_column("decisions", "iteration")
    op.drop_column("decisions", "rejection_reason")
