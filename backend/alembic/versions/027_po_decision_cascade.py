"""PO ikut terhapus bersama keputusannya (21 Okt 2026).

`decision_id` di `sap_mock_purchase_orders` dipasang dengan `ON DELETE SET NULL`
dan kolomnya tidak punya `ForeignKey` di model, jadi tidak ada lapisan yang
menjaga: begitu sebuah keputusan dibuang (tes demo, pembersihan sesi), PO-nya
tertinggal sebagai baris yatim.

Akibat terukur pada audit 21 Okt 2026: setelah satu suite backend, **16 dari 16**
PO punya `decision_id IS NULL`; `test_filter_decision_id` gagal `StopIteration`,
`test_nama_komoditas_dari_keputusan_bukan_tebakan_kode` jatuh ke tebakan kode,
dan dua tes cakupan PO ikut merah. Relink deterministik
(`po.id == uuid5(decision_id, "po")`) tidak bisa memulihkan apa pun karena
keputusan induknya sudah tidak ada.

PO lahir dari keputusan yang dieksekusi; tanpa keputusan ia tidak punya arti.
Maka aturan yang benar adalah CASCADE, bukan SET NULL.

Revision ID: 027_po_decision_cascade
Revises: 026_receipt_approval
"""

from __future__ import annotations

from alembic import op

revision = "027_po_decision_cascade"
down_revision = "026_receipt_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "sap_po_decision_fk", "sap_mock_purchase_orders", type_="foreignkey"
    )
    op.create_foreign_key(
        "sap_po_decision_fk",
        "sap_mock_purchase_orders",
        "decisions",
        ["decision_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "sap_po_decision_fk", "sap_mock_purchase_orders", type_="foreignkey"
    )
    op.create_foreign_key(
        "sap_po_decision_fk",
        "sap_mock_purchase_orders",
        "decisions",
        ["decision_id"],
        ["id"],
        ondelete="SET NULL",
    )
