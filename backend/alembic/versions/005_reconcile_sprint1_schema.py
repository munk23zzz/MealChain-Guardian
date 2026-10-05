"""Rekonsiliasi kontrak Sprint 1 (Task 0 Sprint 2).

Keputusan Roy 2026-10-05 (disetujui):
- price_signals.seed_key hanya ada di database live (drift dari periode
  sebelum pemulihan repo) — tidak ada di migration mana pun, ORM, seed
  loader, API, atau docs. Bukan kontrak aplikasi: dihapus di sini.
- Idempotensi seed TIDAK bergantung kolom ini; loader memakai UUID5
  natural key (location, commodity, source, ref_time) + reconciliation.
- Migration idempoten: DROP COLUMN IF EXISTS — no-op pada database baru
  yang memang tidak pernah memiliki kolom ini.
- Downgrade sengaja tidak mengembalikan kolom: mengembalikannya justru
  memunculkan kembali drift yang bukan kontrak. Jejak keputusan tetap di
  docs/verification/sprint-2.md.

Revision ID: 005_reconcile_sprint1_schema
Revises: 004_supplier_quote_design
Create Date: 2026-10-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005_reconcile_sprint1_schema"
down_revision: Union[str, None] = "004_supplier_quote_design"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    # Kolom drift-only: ada di database live, tidak ada di kontrak repo.
    # IF EXISTS membuat migration aman pada database baru (no-op).
    op.execute("ALTER TABLE price_signals DROP COLUMN IF EXISTS seed_key")


def downgrade() -> None:
    # Sengaja no-op: seed_key bukan kontrak aplikasi dan tidak dikembalikan.
    pass
