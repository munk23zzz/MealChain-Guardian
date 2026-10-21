"""Stempel sesi demo untuk tabel operasional (lanjutan 024, 20 Okt 2026).

024 hanya memberi `batches.demo_session_id` sebagai potongan vertikal. Migrasi
ini melengkapi tabel yang dipakai layar demo, supaya "default kosong" berlaku
di seluruh halaman — bukan cuma Keamanan Pangan:

    decisions, batch_receipts, demand_records, supply_records, price_signals,
    menu_plans, delivery_events, disposal_events, road_routes,
    supplier_exclusions, sap_mock_material_stock, sap_mock_purchase_orders

Yang TIDAK diberi stempel (sengaja): `users`, `locations`, `commodities`,
`suppliers`. Itu data referensi — login dan peta harus tetap jalan tanpa sesi.
Konsekuensinya dinyatakan terbuka: pemasok/lokasi baru hasil seed tetap
terlihat setelah sesi habis; hanya baris operasional yang kembali kosong.

Anak dari decisions (decision_evidence, approvals, agent_traces) tidak diberi
kolom: FK-nya `ON DELETE CASCADE`, jadi ikut terhapus saat decisions sesi
dihapus, dan tidak pernah dibaca tanpa lewat keputusan induknya.

Aditif dan nullable — dengan DEMO_SESSION_ENFORCE=false (bawaan) perilaku dan
seluruh tes lama tidak berubah.

Revision ID: 025_demo_session_columns
Revises: 024_demo_sessions
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "025_demo_session_columns"
down_revision = "024_demo_sessions"
branch_labels = None
depends_on = None

#: (tabel, nama constraint FK) — urutan tidak penting, semuanya merujuk demo_sessions.
TABEL = [
    "decisions",
    "batch_receipts",
    "demand_records",
    "supply_records",
    "price_signals",
    "menu_plans",
    "delivery_events",
    "disposal_events",
    "road_routes",
    "supplier_exclusions",
    "sap_mock_material_stock",
    "sap_mock_purchase_orders",
]


def upgrade() -> None:
    for tabel in TABEL:
        op.add_column(
            tabel,
            sa.Column(
                "demo_session_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{tabel}_demo_session_id", tabel, ["demo_session_id"])
        op.create_foreign_key(
            f"{tabel}_demo_session_id_fkey",
            tabel,
            "demo_sessions",
            ["demo_session_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for tabel in reversed(TABEL):
        op.drop_constraint(f"{tabel}_demo_session_id_fkey", tabel, type_="foreignkey")
        op.drop_index(f"ix_{tabel}_demo_session_id", table_name=tabel)
        op.drop_column(tabel, "demo_session_id")
