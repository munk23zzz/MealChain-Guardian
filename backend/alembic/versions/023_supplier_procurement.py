"""Pengadaan pemasok: `decisions.supplier_id` + tipe `supplier_procurement`
(19 Okt 2026).

Demo Control menilai PEMASOK → SPPG: pemasok yang sudah memasok SPPG itu
(terdaftar di lokasi SPPG, stok batch dan penawaran harganya di lokasi yang
sama) dinilai jarak angkutnya dari koordinat pemasok ke SPPG. Sebelum ini
identitas pemasok hanya tersimpan sebagai snapshot JSON di
`decision_evidence.payload`, jadi "pemasok mana yang dipilih" tidak bisa
dibaca langsung dari baris keputusan dan tidak punya FK.

Dua perubahan, keduanya aditif:

1. Kolom `supplier_id` (FK `suppliers.id`, `NULL` sah). Baris lama tetap
   `NULL` — pemindahan antar SPPG memang mengikat supplier lewat evidence
   batch, bukan lewat kolom ini.
2. Nilai `decision_type` baru `supplier_procurement` supaya pengadaan tidak
   diberi label "regional_balance" yang artinya pemindahan antar SPPG.

Revision ID: 023_supplier_procurement
Revises: 022_disposal_partner
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "023_supplier_procurement"
down_revision = "022_disposal_partner"
branch_labels = None
depends_on = None

_LAMA = (
    "decision_type IN ('regional_balance','price_anomaly',"
    "'safety_disruption','supplier_exclusion',"
    "'supplier_exclusion_restoration')"
)
_BARU = (
    "decision_type IN ('regional_balance','price_anomaly',"
    "'safety_disruption','supplier_exclusion',"
    "'supplier_exclusion_restoration','supplier_procurement')"
)


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.drop_constraint(
        "decisions_decision_type_check", "decisions", type_="check"
    )
    op.create_check_constraint(
        "decisions_decision_type_check", "decisions", _BARU
    )


def downgrade() -> None:
    op.drop_constraint(
        "decisions_decision_type_check", "decisions", type_="check"
    )
    op.create_check_constraint(
        "decisions_decision_type_check", "decisions", _LAMA
    )
    op.drop_column("decisions", "supplier_id")
