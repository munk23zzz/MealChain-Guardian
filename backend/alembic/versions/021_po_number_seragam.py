"""Seragamkan nomor PO yang lahir dari keputusan (audit M8, 18 Okt 2026).

Sebelum ini seed aktivitas demo menulis `DEMO-PO-<KOTA>-<KOMODITAS>`, padahal
barisnya punya `decision_id` — sama seperti PO dari `POST /actions/execute`
yang memakai `MC-<12 hex id>`. Panel melaporkan keduanya `origin=execution`,
jadi bentuk nomor yang berbeda membuat pembaca mengira asalnya berbeda.

Migrasi ini menormalkan baris historis ke `MC-<12 hex id keputusan>`. Baris
impor SAP tanpa `decision_id` (mis. `4500000001`) TIDAK disentuh: itu objek
lain dan panel menandainya `origin=demo`.

Catatan: nomor lama tidak bisa direkonstruksi otomatis (kota/komoditas tidak
disimpan di baris PO), jadi downgrade hanya mengembalikan CHECK/indeks — bukan
nomor lama.

Revision ID: 021_po_number_seragam
Revises: 020_review_only_status
"""

from alembic import op

revision = "021_po_number_seragam"
down_revision = "020_review_only_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE sap_mock_purchase_orders "
        "SET po_number = 'MC-' || upper(substr(replace(decision_id::text, '-', ''), 1, 12)) "
        "WHERE po_number LIKE 'DEMO-PO-%' AND decision_id IS NOT NULL"
    )


def downgrade() -> None:
    # Sengaja tidak mengubah kembali: nama lama memuat kota/komoditas yang
    # tidak tersimpan di baris PO. Yang bisa dipulihkan hanyalah keadaan
    # skema, dan skema tidak berubah di migrasi ini.
    pass
