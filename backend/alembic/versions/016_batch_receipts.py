"""Catatan penerimaan barang (`batch_receipts`) — rumah jujur untuk isian manual.

Revision ID: 016_batch_receipts
Revises: 015_batch_dispatch

Latar (permintaan pemilik 2026-10-16): kartu "Penerimaan barang" punya daftar
periksa tetap, tetapi petugas sering menghadapi keadaan yang tidak ada di daftar
itu — pemilik meminta **opsi "Lainnya"** yang bisa diisi sendiri. Catatan bebas
baru berguna kalau tidak hilang saat halaman dimuat ulang dan bisa dibaca
pengawas, jadi ia butuh tempat di database — bukan sekadar state layar.

Lima keputusan yang sengaja diambil:

1. **Tabel sendiri, bukan kolom baru di `batches`.** Satu batch bisa diterima
   lebih dari sekali (kiriman ulang, koreksi hitungan) dan setiap catatan punya
   pencatat serta waktunya sendiri; satu kolom di `batches` akan menimpa riwayat.
2. **`checked` = snapshot JSONB apa adanya.** Id titik periksa hidup di lapisan
   UI (`RECEIVING_CHECKS` di frontend); backend menyimpan laporan apa adanya,
   sehingga baris lama tetap menggambarkan apa yang benar-benar dicentang saat
   itu walau daftar periksa berubah di kemudian hari.
3. **`other_note` NULL berarti "tidak ada catatan".** Catatan kosong atau hanya
   spasi tidak disimpan sebagai string kosong, supaya UI bisa mengatakannya
   apa adanya tanpa menebak.
4. **`recorded_by` NOT NULL dan `recorded_at` diisi server.** Catatan penerimaan
   tanpa pencatat bukan bukti; waktunya diambil dari server (jam perangkat klien
   berbeda-beda dan tidak boleh jadi sumber kebenaran).
5. **`ON DELETE CASCADE` dari `batches`.** Catatan ini milik batch-nya: saat
   data demo dibersihkan (Demo Control), catatannya ikut terhapus — tidak ada
   baris yatim yang menunjuk batch yang sudah tidak ada.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "016_batch_receipts"
down_revision: Union[str, None] = "015_batch_dispatch"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "batch_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "checked",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("other_note", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_batch_receipts_batch_recorded",
        "batch_receipts",
        ["batch_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    # Catatan penerimaan adalah hasil kerja manusia (tidak bisa diturunkan dari
    # seed), jadi menurunkan migrasi ini MEMBUANG data itu — sengaja dibiarkan
    # ekplisit di sini supaya tidak dilakukan tanpa sadar.
    op.drop_index("ix_batch_receipts_batch_recorded", table_name="batch_receipts")
    op.drop_table("batch_receipts")
