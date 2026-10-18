"""Status karantina batch (migrasi 019).

Latar: proposal menyebut kewenangan agent terbatas pada "merekomendasikan
karantina". Sebelum migrasi ini tidak ada status karantina sama sekali —
`safety_status='needs_verification'` masih boleh masuk kandidat alokasi, jadi
batch yang belum terbukti aman tetap bisa dipakai menyusun menu.

Kolom baru pada `batches` (semua nullable/default supaya baris lama sah):
- quarantine_status     none|quarantined|released|failed, default 'none'
- quarantine_reason     alasan manusia (wajib diisi lewat API, bukan di DB)
- quarantined_at        kapan ditahan
- quarantine_updated_at kapan status terakhir berubah
- quarantine_actor_id   siapa yang memutuskan (users.id, ON DELETE SET NULL)

Batch `quarantined` dikeluarkan dari kandidat alokasi (lihat
`core/candidate_generation.py`), sehingga stok fisik tetap tercatat sementara
stok layak pakai berkurang — physical inventory != usable inventory.

Revision ID: 019_batch_quarantine
Revises: 018_agent_trace_worker_fields
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "019_batch_quarantine"
down_revision: Union[str, None] = "018_agent_trace_worker_fields"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "quarantine_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
    )
    op.add_column("batches", sa.Column("quarantine_reason", sa.Text(), nullable=True))
    op.add_column(
        "batches",
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "batches",
        sa.Column("quarantine_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "batches",
        sa.Column(
            "quarantine_actor_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "batches_quarantine_status_check",
        "batches",
        "quarantine_status IN ('none','quarantined','released','failed')",
    )
    op.create_index(
        "ix_batches_quarantine_status", "batches", ["quarantine_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_batches_quarantine_status", table_name="batches")
    op.drop_constraint(
        "batches_quarantine_status_check", "batches", type_="check"
    )
    op.drop_column("batches", "quarantine_actor_id")
    op.drop_column("batches", "quarantine_updated_at")
    op.drop_column("batches", "quarantined_at")
    op.drop_column("batches", "quarantine_reason")
    op.drop_column("batches", "quarantine_status")
