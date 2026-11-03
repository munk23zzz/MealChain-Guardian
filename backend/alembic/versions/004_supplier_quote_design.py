"""price_signals: kolom supplier_id + kontrak source dua nilai (revisi kedua Roy).

Desain final Roy 2026-10-03:
- source kembali generik dua nilai: 'pihps_reference' | 'supplier_quote'
- identitas supplier = kolom TERPISAH supplier_id (FK → suppliers.id, nullable)
  sehingga tidak terbatas pada inisial A/B/C — supplier apa pun bisa ditambah
- konsistensi dijaga constraint:
  * referensi  -> source='pihps_reference' DAN supplier_id IS NULL
  * quote      -> source='supplier_quote' DAN supplier_id IS NOT NULL

Revision ID: 004_supplier_quote_design
Revises: 002_operational_data
Create Date: 2026-10-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_supplier_quote_design"
down_revision: Union[str, None] = "002_operational_data"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    # 1. Hapus constraint lama dari migration 002
    op.drop_constraint("price_signals_source_check", "price_signals", type_="check")
    # 2. Kolom supplier_id (FK ke suppliers, nullable — referensi pasar tanpa supplier)
    op.add_column(
        "price_signals",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_price_signals_supplier", "price_signals", ["supplier_id"]
    )
    # 3. Kontrak source dua nilai + konsistensi source <-> supplier_id
    op.create_check_constraint(
        "price_signals_source_quote_check",
        "price_signals",
        "source IN ('pihps_reference','supplier_quote')",
    )
    op.create_check_constraint(
        "price_signals_supplier_consistency_check",
        "price_signals",
        "(source = 'pihps_reference' AND supplier_id IS NULL) OR "
        "(source = 'supplier_quote' AND supplier_id IS NOT NULL)",
    )
    # 4. Bersihkan row legacy desain interim 'supplier_<ID>' — dipindah ke desain baru
    op.execute(
        "DELETE FROM price_signals WHERE source NOT IN "
        "('pihps_reference','supplier_quote')"
    )


def downgrade() -> None:
    op.drop_constraint(
        "price_signals_supplier_consistency_check", "price_signals", type_="check"
    )
    op.drop_constraint("price_signals_source_quote_check", "price_signals", type_="check")
    op.drop_index("idx_price_signals_supplier", table_name="price_signals")
    op.drop_column("price_signals", "supplier_id")
    op.create_check_constraint(
        "price_signals_source_check",
        "price_signals",
        "source IN ('pihps_reference','supplier_quote')",
    )
