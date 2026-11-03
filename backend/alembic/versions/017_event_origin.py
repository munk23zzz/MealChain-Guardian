"""Penanda asal (`origin`/`generated_at`) untuk kiriman & limbah (migrasi 017).

Latar: deret AKTUAL (supply/harga) sudah berjalan sampai 5 Nov, tetapi
`delivery_events` (1–7 Okt) dan `disposal_events` (4–7 Okt) tidak punya penanda
asal — akibatnya dua panel tetap mati di jendela pendek:

- "Meal Continuity Rate" = 0.00% (rencana ada, kiriman tidak ada);
- "Avoidable Food Loss" = "tidak ada disposal event pada periode ini".

Untuk memperluas keduanya dengan pola generator yang sama seperti supply/harga,
kedua tabel butuh `origin` + `generated_at` supaya baris demo bisa dibedakan dan
dihapus SELEKTIF (klausa yang sama: `origin='demo'`).

Keputusan (mengikuti migrasi 013): `origin` NOT NULL DEFAULT 'seed' sehingga
seluruh baris kanonik yang sudah ada langsung benar tanpa backfill, dan baris
baru yang lupa mengisi kolom ini terbaca kanonik — salahnya ke arah data tetap
ada, bukan data demo menghapus data kanonik.

Revision ID: 017_event_origin
Revises: 016_batch_receipts
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "017_event_origin"
down_revision: Union[str, None] = "016_batch_receipts"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

# tabel, kolom tanggal untuk index (origin, <kolom>)
TABLES: list[tuple[str, str]] = [
    ("delivery_events", "delivered_at"),
    ("disposal_events", "disposed_at"),
]


def upgrade() -> None:
    for table, date_col in TABLES:
        op.add_column(
            table,
            sa.Column(
                "origin",
                sa.String(),
                nullable=False,
                server_default=sa.text("'seed'"),
            ),
        )
        op.add_column(
            table, sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_check_constraint(
            f"check_{table}_origin_vocab",
            table,
            "origin IN ('seed','demo')",
        )
        op.create_index(f"ix_{table}_origin_{date_col}", table, ["origin", date_col])


def downgrade() -> None:
    # Baris demo tidak bisa diwakili tanpa `origin` — kalau dibiarkan, setelah
    # turun versi mereka terbaca kanonik dan menggeser angka KPI. Buang dulu
    # (bisa dibangun ulang dalam hitungan detik lewat POST /demo/timeseries).
    for table, _date_col in TABLES:
        op.execute(f"DELETE FROM {table} WHERE origin = 'demo'")

    for table, date_col in reversed(TABLES):
        op.drop_index(f"ix_{table}_origin_{date_col}", table_name=table)
        op.drop_constraint(f"check_{table}_origin_vocab", table, type_="check")
        op.drop_column(table, "generated_at")
        op.drop_column(table, "origin")
