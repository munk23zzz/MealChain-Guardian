"""Metadata worker pada jejak agen (migrasi 018).

Latar: P4 menghasilkan delapan baris trace (tujuh worker + satu SUPERVISE),
tetapi `agent_traces` hanya menyimpan step_name/tool/input/output/duration.
Akibatnya Agent Log tidak bisa mengelompokkan satu putaran review, menampilkan
nama agen, confidence, atau sitasi — dan `duration_ms` yang sudah ada di model
bahkan tidak pernah dikirim serializer.

Migrasi ini MENAMBAH kolom nullable, tanpa backfill:
- run_id      — UUID putaran review (satu run = 8 baris);
- agent_name  — supply/demand/.../evidence/supervisor;
- confidence  — hanya bila worker benar-benar mengirim angka;
- citations   — daftar Citation JSON apa adanya (disanitasi saat persist).

Baris trace lama tetap valid dengan nilai NULL; UI menulis "—" dan tidak
mengarang run_id. Index run_id dipakai untuk memilih putaran terbaru.

Revision ID: 018_agent_trace_worker_fields
Revises: 017_event_origin
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_agent_trace_worker_fields"
down_revision: Union[str, None] = "017_event_origin"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "agent_traces",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_traces", sa.Column("agent_name", sa.Text(), nullable=True)
    )
    op.add_column(
        "agent_traces", sa.Column("confidence", sa.Float(), nullable=True)
    )
    op.add_column(
        "agent_traces",
        sa.Column("citations", postgresql.JSONB(none_as_null=True), nullable=True),
    )
    op.create_index(
        "ix_agent_traces_run_id", "agent_traces", ["run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_agent_traces_run_id", table_name="agent_traces")
    op.drop_column("agent_traces", "citations")
    op.drop_column("agent_traces", "confidence")
    op.drop_column("agent_traces", "agent_name")
    op.drop_column("agent_traces", "run_id")
