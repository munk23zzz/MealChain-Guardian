"""Sesi demo: tabel `demo_sessions` + stempel `batches.demo_session_id`
(20 Okt 2026).

Permintaan pemilik: tampilan default KOSONG; tombol "Siapkan data demo"
memanggil data dan mengaktifkannya satu jam (bisa diperpanjang), ada hitungan
mundur, dan sesudah sesi habis data kembali kosong — perubahan selama sesi
hilang, data berikutnya mulai dari template lagi.

Migrasi ini menyiapkan fondasinya, bukan seluruh fiturnya:

1. `demo_sessions` — satu baris per jendela demo. `anchor_now` = waktu server
   saat tombol ditekan (jam TIDAK dibekukan; hanya dicatat).
2. `batches.demo_session_id` — kolom pertama yang memakai aturan sesi. Model
   lain (decisions, receipts, evidence, traces) menyusul di migrasi/iterasi
   berikutnya; `app/services/demo_session.py` menemukan model bersesi secara
   otomatis lewat keberadaan kolom ini, jadi tidak ada daftar manual yang bisa
   lupa diperbarui.

Keduanya aditif dan nullable: dengan `DEMO_SESSION_ENFORCE=false` (bawaan)
perilaku aplikasi dan 1.200+ tes backend tidak berubah sama sekali.

Revision ID: 024_demo_sessions
Revises: 023_supplier_procurement
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "024_demo_sessions"
down_revision = "023_supplier_procurement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_now", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("template_version", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('active','expired','ended')",
            name="demo_sessions_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="demo_sessions_created_by_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_demo_sessions_status_expires",
        "demo_sessions",
        ["status", "expires_at"],
    )
    op.add_column(
        "batches",
        sa.Column(
            "demo_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_batches_demo_session_id", "batches", ["demo_session_id"])
    op.create_foreign_key(
        "batches_demo_session_id_fkey",
        "batches",
        "demo_sessions",
        ["demo_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("batches_demo_session_id_fkey", "batches", type_="foreignkey")
    op.drop_index("ix_batches_demo_session_id", table_name="batches")
    op.drop_column("batches", "demo_session_id")
    op.drop_index("ix_demo_sessions_status_expires", table_name="demo_sessions")
    op.drop_table("demo_sessions")
