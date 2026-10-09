"""P1 (paket 1-6, keputusan Roy 2026-10-09): ledger_blocks — Merkle
append-only. Setiap aksi mutasi keputusan (approve/reject/execute)
menambah block: payload_hash = sha256(prev_hash + canonical payload),
prev_hash block pertama = 64 karakter '0' (genesis). Rantai diverifikasi
GET /ledger/verify; manipulasi payload/payload_hash memutus rantai.

Revision ID: 010_ledger_blocks
Revises: 009_kpi_facts_tables
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "010_ledger_blocks"
down_revision: Union[str, None] = "009_kpi_facts_tables"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "ledger_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("height", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "length(payload_hash) = 64 AND length(prev_hash) = 64",
            name="ledger_hash_len_check",
        ),
    )
    op.create_index("idx_ledger_blocks_height", "ledger_blocks", ["height"])


def downgrade() -> None:
    op.drop_table("ledger_blocks")
