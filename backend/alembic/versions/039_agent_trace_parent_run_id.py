"""Run induk pada jejak agen — verifier sebagai run anak (migrasi 039).

Latar (AUD-9A-03). Agent verifier berjalan SESUDAH narasi supervisor dan
mengaudit putaran review itu. Ia bukan langkah dari run review, melainkan run
sendiri yang memakai run review sebagai masukan — sama seperti auditor yang
menandatangani laporan orang lain.

Supaya jejaknya dapat direkonstruksi dari DB (provider/model yang menjawab,
verdict, dan sitasi), baris VERIFY memerlukan dua identitas:

- ``run_id``        — identitas run verifier itu sendiri;
- ``parent_run_id`` — run review yang diaudit (induk).

Kolom nullable, tanpa backfill: baris lama (dan baris analitik pada run yang
sama) tetap valid dengan ``parent_run_id`` NULL. Index dipakai untuk menelusuri
"run ini mengaudit run mana".

Catatan nomor: berkas ini memakai nomor 039 sesuai rencana perbaikan audit 9A;
revisi 034-038 tidak dipakai sehingga tidak ada berkas yang bertabrakan.

Revision ID: 039_agent_trace_parent_run_id
Revises: 033_indeks_fk_hilang

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "039_agent_trace_parent_run_id"
down_revision: Union[str, None] = "033_indeks_fk_hilang"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "agent_traces",
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_agent_traces_parent_run_id",
        "agent_traces",
        ["parent_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_traces_parent_run_id", table_name="agent_traces")
    op.drop_column("agent_traces", "parent_run_id")
