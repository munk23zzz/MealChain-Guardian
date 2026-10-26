"""Indeks untuk 22 kolom FK yang belum punya indeks pendukung.

Latar (audit lineage 25 Okt 2026, temuan F-07): Postgres tidak membuat indeks untuk
kolom FK. Audit katalog menemukan **22** kolom FK yang tidak menjadi kolom pertama
indeks mana pun. Yang paling mahal adalah yang dipakai filter/join sehari-hari:

    batches.location_id, batches.commodity_id, batches.supplier_id,
    decisions.target_location_id / source_location_id / commodity_id / supplier_id,
    supply_records.commodity_id, demand_records.commodity_id,
    price_signals.commodity_id, disposal_events.commodity_id,
    approvals.approved_by, supplier_exclusions.*, sap_mock_purchase_orders.supplier_id

Tanpa indeks, `DELETE` pada induk (lokasi/komoditas/pemasok) memicu sequential scan
pada tabel anak — dan itu jalur yang dipakai pembersihan data demo.

Catatan: daftar ini diverifikasi dari katalog, bukan dari model. Tes
`tests/test_fk_index_coverage.py` membaca pg_constraint/pg_index dan gagal bila ada
kolom FK baru yang lahir tanpa indeks, jadi migrasi berikutnya tidak bisa lupa.

Revision ID: 033_indeks_fk_hilang
Revises: 032_satu_sesi_aktif
"""

from __future__ import annotations

from alembic import op

revision = "033_indeks_fk_hilang"
down_revision = "032_satu_sesi_aktif"
branch_labels = None
depends_on = None

# (tabel, kolom) — urutan mengikuti audit §13.3 agar mudah dicocokkan.
INDEKS_FK: tuple[tuple[str, str], ...] = (
    ("approvals", "approved_by"),
    ("batch_receipts", "recorded_by"),
    ("batch_receipts", "reviewed_by"),
    ("batch_receipts", "supply_record_id"),
    ("batches", "commodity_id"),
    ("batches", "location_id"),
    ("batches", "quarantine_actor_id"),
    ("batches", "supplier_id"),
    ("decisions", "commodity_id"),
    ("decisions", "source_location_id"),
    ("decisions", "supplier_id"),
    ("decisions", "target_location_id"),
    ("demand_records", "commodity_id"),
    ("demo_sessions", "created_by"),
    ("disposal_events", "commodity_id"),
    ("price_signals", "commodity_id"),
    ("sap_mock_purchase_orders", "supplier_id"),
    ("supplier_exclusions", "proposed_by"),
    ("supplier_exclusions", "restoration_decision_id"),
    ("supplier_exclusions", "scope_location_id"),
    ("supplier_exclusions", "source_decision_id"),
    ("supply_records", "commodity_id"),
)


def _nama(tabel: str, kolom: str) -> str:
    return f"ix_{tabel}_{kolom}"


def upgrade() -> None:
    for tabel, kolom in INDEKS_FK:
        op.create_index(_nama(tabel, kolom), tabel, [kolom])


def downgrade() -> None:
    for tabel, kolom in reversed(INDEKS_FK):
        op.drop_index(_nama(tabel, kolom), table_name=tabel)
