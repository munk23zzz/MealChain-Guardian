"""Penanda data demo pada PO + index kolom pencarian Joule (22 Okt 2026).

Latar (audit Fase 2 pekerjaan `db-modes-demo-coverage`):

1. **PO tidak punya penanda demo.** Semua tabel deret waktu sudah membawa
   `origin` (`'seed'`/`'demo'`) sejak migrasi 017, tetapi
   `sap_mock_purchase_orders` hanya punya `demo_session_id`. Baris PO hasil
   impor kanonik (`decision_id IS NULL`, 12 baris) karena itu tidak bisa
   dibedakan dari PO nyata saat pembersihan mode demo: `origin` di sini yang
   membuat `reset-demo` aman dan tepat sasaran.

2. **Empat kolom yang dipakai setiap jawaban Joule tidak punya index.**
   `/decisions/{id}/approval-summary`, `/decisions/{id}/traces`,
   `/decisions/{id}/compliance`, `/sap/purchase-orders?decision_id=...`, dan
   gerbang penerimaan (`/receipts/menunggu`) semuanya memfilter kolom yang
   belum ber-index, sehingga Postgres memindai seluruh tabel. Index di bawah
   hanya menambah struktur; tidak ada data yang diubah.

Revision ID: 028_demo_marker_indexes
Revises: 027_po_decision_cascade
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "028_demo_marker_indexes"
down_revision = "027_po_decision_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Penanda demo pada PO. Default 'seed' supaya 12 baris lama sah tanpa
    #    backfill khusus (mereka memang data kerja), dan PO baru tanpa origin
    #    tetap berperilaku seperti sebelumnya.
    op.add_column(
        "sap_mock_purchase_orders",
        sa.Column(
            "origin",
            sa.String(length=16),
            nullable=False,
            server_default="seed",
        ),
    )
    op.create_check_constraint(
        "sap_mock_po_origin_check",
        "sap_mock_purchase_orders",
        "origin IN ('seed','demo')",
    )

    # 2. Index untuk query yang dipakai UI dan jembatan Joule.
    op.create_index(
        "ix_sap_mock_purchase_orders_decision_id",
        "sap_mock_purchase_orders",
        ["decision_id"],
    )
    op.create_index("ix_agent_traces_decision_id", "agent_traces", ["decision_id"])
    op.create_index("ix_approvals_decision_id", "approvals", ["decision_id"])
    op.create_index(
        "ix_decision_evidence_decision_id", "decision_evidence", ["decision_id"]
    )
    op.create_index(
        "ix_batch_receipts_status_recorded",
        "batch_receipts",
        ["status", "recorded_at"],
    )

    # 3. Dua FK eksklusi pemasok menahan penghapusan keputusan (NO ACTION).
    #    Terukur 22 Okt 2026: GET /batches dan GET /balance/map balas 500
    #    (`ForeignKeyViolationError ... supplier_exclusions_restoration_decision_id_fkey`)
    #    karena jalur pemeliharaan data demo menghapus keputusan yang masih
    #    dirujuk eksklusi. Aturannya mengikuti sifat kolomnya (lihat di bawah).
    # `source_decision_id` NOT NULL -> CASCADE (eksklusi lahir dari keputusan,
    # sama seperti PO pada migrasi 027). `restoration_decision_id` opsional ->
    # SET NULL (pencabutan tetap tercatat walau keputusan pemulihnya hilang).
    op.drop_constraint(
        "supplier_exclusions_source_decision_id_fkey",
        "supplier_exclusions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "supplier_exclusions_source_decision_id_fkey",
        "supplier_exclusions",
        "decisions",
        ["source_decision_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "supplier_exclusions_restoration_decision_id_fkey",
        "supplier_exclusions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "supplier_exclusions_restoration_decision_id_fkey",
        "supplier_exclusions",
        "decisions",
        ["restoration_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    for kolom in ("source_decision_id", "restoration_decision_id"):
        op.drop_constraint(
            f"supplier_exclusions_{kolom}_fkey",
            "supplier_exclusions",
            type_="foreignkey",
        )
        op.create_foreign_key(
            f"supplier_exclusions_{kolom}_fkey",
            "supplier_exclusions",
            "decisions",
            [kolom],
            ["id"],
        )
    op.drop_index("ix_batch_receipts_status_recorded", table_name="batch_receipts")
    op.drop_index(
        "ix_decision_evidence_decision_id", table_name="decision_evidence"
    )
    op.drop_index("ix_approvals_decision_id", table_name="approvals")
    op.drop_index("ix_agent_traces_decision_id", table_name="agent_traces")
    op.drop_index(
        "ix_sap_mock_purchase_orders_decision_id",
        table_name="sap_mock_purchase_orders",
    )
    op.drop_constraint(
        "sap_mock_po_origin_check", "sap_mock_purchase_orders", type_="check"
    )
    op.drop_column("sap_mock_purchase_orders", "origin")
