"""Skor, putusan, dan berat diterima pada ceklis penerimaan (Dok 05 §3–§5).

Revision ID: 044_receipt_scoring
Revises: 043_least_privilege_app

Latar. Sampai 043, `batch_receipts.checked` hanya menyimpan lima-dua belas
boolean: "diperiksa atau tidak". Dokumen 05 menuntut lebih: tujuh butir
berbobot, nilai 0–100, putusan berjenjang, dan nilai rupiah yang dihitung dari
BERAT YANG DITERIMA — bukan berat batch. Tanpa kolom di bawah ini, skor hanya
hidup di memori layar dan hilang saat halaman dimuat ulang; pengawas tidak bisa
membuktikan mengapa sebuah kiriman diterima.

Keputusan yang diambil:

1. **Kolom terpisah, bukan menumpang `checked`.** `checked` tetap snapshot
   pilihan apa adanya (jawaban per butir), sementara `points` menyimpan hasil
   hitung server. Menyimpan skor di dalam `checked` membuat satu kolom memikul
   dua arti, dan angka lama tidak bisa diaudit ulang.
2. **`checklist_version` ikut disimpan** (§4 paragraf terakhir). Kalau bobot
   berubah kelak, baris lama tetap terbaca dengan rumus yang berlaku saat itu.
3. **NULL = "belum dinilai", bukan 0.** Baris lama (sebelum migrasi ini) tidak
   punya skor; menulis 0 akan tampak seperti kiriman gagal total.
4. **`accepted_kg` NULL berarti "belum ditimbang"**, dan pembaca wajib jatuh ke
   `batches.quantity_kg` — perilaku lama tetap jalan untuk baris lama.
5. **`verdict` disimpan, bukan dihitung ulang saat dibaca.** Putusan yang sudah
   tercatat tidak boleh berubah hanya karena ambang di kode diubah besok.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "044_receipt_scoring"
down_revision: Union[str, None] = "043_least_privilege_app"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "batch_receipts",
        sa.Column("answers", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "batch_receipts",
        sa.Column("points", postgresql.JSONB, nullable=True),
    )
    op.add_column("batch_receipts", sa.Column("score", sa.Integer, nullable=True))
    op.add_column("batch_receipts", sa.Column("verdict", sa.Text, nullable=True))
    op.add_column("batch_receipts", sa.Column("advice", sa.Text, nullable=True))
    op.add_column(
        "batch_receipts",
        sa.Column("ordered_kg", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "batch_receipts",
        sa.Column("accepted_kg", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "batch_receipts", sa.Column("checklist_version", sa.Text, nullable=True)
    )
    # Saringan "yang perlu diputuskan" membaca verdict; baris lama NULL tetap
    # ikut (dianggap belum dinilai) karena indeks parsial hanya untuk tiga nilai.
    op.create_index(
        "ix_batch_receipts_verdict",
        "batch_receipts",
        ["verdict"],
        postgresql_where=sa.text("verdict IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_batch_receipts_verdict", table_name="batch_receipts")
    for kolom in (
        "checklist_version",
        "accepted_kg",
        "ordered_kg",
        "advice",
        "verdict",
        "score",
        "points",
        "answers",
    ):
        op.drop_column("batch_receipts", kolom)
