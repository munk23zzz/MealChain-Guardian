"""Mitra pengolahan limbah pada `disposal_events` (18 Okt 2026).

Panel Surplus & Limbah menampilkan baris "Komposter / bank pangan" dengan nilai
"—" karena skema tidak menyimpan ke mana limbah dialihkan. Tanpa kolom itu,
pertanyaan "limbah ini dibuang atau dikomposkan?" tidak bisa dijawab dari data,
dan menjawabnya di UI berarti mengarang.

Kolom `partner_name` = mitra yang menerima limbah (bank sampah, komposter,
pengolahan pakan). `NULL` berarti limbah DIBUANG tanpa mitra — dan itu memang
keadaan yang berbeda dari 0 kg, jadi dibedakan di API (`diverted` vs
`unassigned_kg`), bukan dianggap sama.

Revision ID: 022_disposal_partner
Revises: 021_po_number_seragam
"""

import sqlalchemy as sa

from alembic import op

revision = "022_disposal_partner"
down_revision = "021_po_number_seragam"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disposal_events",
        sa.Column("partner_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("disposal_events", "partner_name")
