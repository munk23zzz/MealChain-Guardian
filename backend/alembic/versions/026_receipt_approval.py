"""Persetujuan penerimaan barang → stok masuk (20 Okt 2026).

Sebelum migrasi ini, `batch_receipts` hanya mencatat pemeriksaan petugas: tidak
ada langkah persetujuan dan tidak ada efek ke pasokan. Akibatnya demo "barang
sampai → approve → angka Overview berubah" tidak mungkin: Overview membaca
`supply_records`, sedangkan penerimaan tidak pernah menulis ke sana.

Migrasi ini menambah keadaan keputusan pada catatan penerimaan:

    menunggu  → dicatat petugas, BELUM masuk stok
    disetujui → disetujui kepala SPPG, satu baris `supply_records` ditulis
    ditolak   → tidak masuk stok, alasan wajib (review_note)

`supply_record_id` menyimpan baris stok yang lahir dari persetujuan itu —
itulah yang membuat approve idempoten (klik dua kali tidak menambah stok dua
kali) dan bisa ditelusuri balik.

Invarian "satu batch hanya boleh punya SATU penerimaan disetujui" ditegakkan
di tingkat DB lewat unique index parsial; tanpa itu dua permintaan bersamaan
bisa sama-sama lolos dan stok bertambah dua kali.

Aditif dan berdefault, jadi baris lama otomatis berstatus 'menunggu'.

Revision ID: 026_receipt_approval
Revises: 025_demo_session_columns
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "026_receipt_approval"
down_revision = "025_demo_session_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batch_receipts",
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="menunggu",
        ),
    )
    op.add_column(
        "batch_receipts",
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "batch_receipts",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "batch_receipts",
        sa.Column("review_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "batch_receipts",
        sa.Column(
            "supply_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("supply_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "batch_receipts_status_check",
        "batch_receipts",
        "status IN ('menunggu','disetujui','ditolak')",
    )
    # Satu batch = paling banyak satu penerimaan disetujui (stok tidak dobel).
    op.create_index(
        "uq_batch_receipts_satu_disetujui",
        "batch_receipts",
        ["batch_id"],
        unique=True,
        postgresql_where=sa.text("status = 'disetujui'"),
    )


def downgrade() -> None:
    op.drop_index("uq_batch_receipts_satu_disetujui", table_name="batch_receipts")
    op.drop_constraint(
        "batch_receipts_status_check", "batch_receipts", type_="check"
    )
    op.drop_column("batch_receipts", "supply_record_id")
    op.drop_column("batch_receipts", "review_note")
    op.drop_column("batch_receipts", "reviewed_at")
    op.drop_column("batch_receipts", "reviewed_by")
    op.drop_column("batch_receipts", "status")
