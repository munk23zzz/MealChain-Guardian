"""Kunci idempotensi penulis KPI (23 Okt 2026).

Latar: tiga sumber KPI hanya diisi seeder — `delivery_events` (Meal Continuity),
`price_signals` kutipan pemasok (Price Deviation), dan `disposal_events`
(Avoidable Food Loss). Akibatnya kartu KPI tidak bergerak saat penerimaan
disetujui atau PO terbit; angkanya hanya berubah bila seed dijalankan ulang.

`app/services/settlement.py` menulis ketiga tabel itu dari aksi nyata. Supaya
approve/eksekusi yang diulang (klik ganda, retry HTTP, job yang jalan dua kali)
tidak menggandakan angka KPI, tiap baris membawa `source_ref` unik:

- `receipt:<receipt_id>`  → satu penerimaan = satu baris delivery_events
- `po:<po_number>`        → satu PO = satu kutipan harga
- `disposal:<kunci>`      → satu aksi limbah = satu kejadian

Index di bawah PARSIAL (`source_ref IS NOT NULL`) karena baris seeder lama
tidak punya kunci — NULL berulang harus tetap diizinkan.

Revision ID: 029_kpi_writeback_ref
Revises: 028_demo_marker_indexes
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "029_kpi_writeback_ref"
down_revision = "028_demo_marker_indexes"
branch_labels = None
depends_on = None

TABEL = ("delivery_events", "disposal_events", "price_signals")


def upgrade() -> None:
    for tabel in TABEL:
        op.add_column(tabel, sa.Column("source_ref", sa.Text(), nullable=True))
        op.create_index(
            f"uq_{tabel}_source_ref",
            tabel,
            ["source_ref"],
            unique=True,
            postgresql_where=sa.text("source_ref IS NOT NULL"),
        )


def downgrade() -> None:
    for tabel in TABEL:
        op.drop_index(f"uq_{tabel}_source_ref", table_name=tabel)
        op.drop_column(tabel, "source_ref")
