"""Generasi ledger: blok lama diarsipkan saat data demo direset (N3, 24 Okt 2026).

Latar (audit ulang 24 Okt 2026, temuan N3): `ledger_blocks` append-only, sedangkan
reset data demo menghapus keputusan/batch. Setiap reset meninggalkan blok yang
menunjuk entitas yang sudah tidak ada — terukur 1437 dari 1541 blok (93%) yatim.
Rantai hash-nya tetap utuh, tetapi angka "keterkaitan" jadi tidak bermakna dan
terus memburuk setiap reset.

Keputusan desain: JANGAN menghapus atau menulis ulang blok (itu memutus sifat
append-only dan menghapus jejak audit). Beri setiap blok penanda generasi:
- `ledger_meta.generation` = generasi aktif (satu baris, id = 1);
- `ledger_blocks.generation` = generasi saat blok ditulis;
- cakupan (`linked_ratio`) dihitung pada generasi AKTIF saja;
- blok generasi lama dilaporkan terpisah sebagai `archived_blocks` dan tetap
  diverifikasi hash-nya oleh `verify_chain`.

Revision ID: 031_ledger_generation
Revises: 030_approval_four_eyes_unique
"""

from __future__ import annotations

from alembic import op

revision = "031_ledger_generation"
down_revision = "030_approval_four_eyes_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS ledger_meta ("
        "id SMALLINT PRIMARY KEY, "
        "generation INTEGER NOT NULL DEFAULT 1, "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    op.execute(
        "INSERT INTO ledger_meta (id, generation) VALUES (1, 1) "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "ALTER TABLE ledger_blocks "
        "ADD COLUMN IF NOT EXISTS generation INTEGER NOT NULL DEFAULT 1"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ledger_blocks_generation "
        "ON ledger_blocks (generation, height)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ledger_blocks_generation")
    op.execute("ALTER TABLE ledger_blocks DROP COLUMN IF EXISTS generation")
    op.execute("DROP TABLE IF EXISTS ledger_meta")
