"""price_signals.source — source unik per supplier (revisi Roy 2026-10-03).

Revisi Roy: quote Supplier A/B/C dipersist dengan source unik
('supplier_A'/'supplier_B'/'supplier_C') agar bersih dan mudah ditelusuri
saat mitigasi error. Check constraint dari migration 002 dilebarkan:
- tetap wajib 'pihps_reference' untuk harga referensi;
- quote supplier wajib memakai pola 'supplier_<ID>' (LIKE 'supplier\\_%');

Revision ID: 003_price_source_supplier
Revises: 002_operational_data
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003_price_source_supplier"
down_revision: Union[str, None] = "002_operational_data"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

_OLD_CHECK = "price_signals_source_check"
_NEW_CHECK = "price_signals_source_supplier_check"


def upgrade() -> None:
    op.drop_constraint(_OLD_CHECK, "price_signals", type_="check")
    op.create_check_constraint(
        _NEW_CHECK,
        "price_signals",
        "source = 'pihps_reference' OR source LIKE 'supplier\\_%'",
    )
    # Bersihkan row legacy dari ruling lama ('supplier_quote' × 3)
    op.execute("DELETE FROM price_signals WHERE source = 'supplier_quote'")


def downgrade() -> None:
    # Kembalikan kontrak lama; row dengan source supplier_<ID> dihapus dulu
    op.execute("DELETE FROM price_signals WHERE source LIKE 'supplier\\_%'")
    op.drop_constraint(_NEW_CHECK, "price_signals", type_="check")
    op.create_check_constraint(
        _OLD_CHECK,
        "price_signals",
        "source IN ('pihps_reference','supplier_quote')",
    )
