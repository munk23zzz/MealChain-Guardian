"""Penanda asal data (`origin`) + `generated_at` + kunci upsert deret waktu.

Revision ID: 013_origin_generated_at
Revises: 012_supplier_profile

Latar (Fase 4 rencana `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`):
data demo deret waktu harus bisa dibedakan dari data kanonik dan dibersihkan
SELEKTIF. Sebelum ini tidak ada satu pun penanda asal, jadi "bersihkan data
demo" hanya bisa berarti "hapus database".

Tiga keputusan yang sengaja diambil:

1. **`origin` NOT NULL dengan DEFAULT 'seed'**, jadi seluruh baris yang sudah
   ada (kanonik) langsung benar tanpa UPDATE backfill — dan baris baru yang
   lupa mengisi kolom ini otomatis dianggap kanonik, bukan demo: salahnya
   ke arah "data tetap ada", bukan "data demo menghapus data kanonik".
2. **`generated_at` nullable.** Baris kanonik ditulis tangan, tidak pernah
   dihasilkan generator; NULL-nya jujur. Baris demo WAJIB mengisinya (dipaku
   uji data, bukan constraint, supaya penyimpangannya terbaca sebagai laporan
   tes, bukan sebagai migrasi gagal).
3. **Kunci upsert deret waktu.** Generator harus idempoten ("dua kali jalan
   tidak menggandakan"). Tanpa kunci unik, upsert tak mungkin: harus
   men-SELECT dulu, dan itu balapan. Kuncinya per tabel mengikuti arti
   datanya:
   - `supply_records`  : (location_id, commodity_id, recorded_at, source) —
     sumber berbeda pada waktu sama MEMANG boleh ada (ada tes kontrak
     "mock > manual > sensor").
   - `price_signals`   : dua index parsial, karena aturannya berbeda —
     referensi PIHPS per lokasi×komoditas, kutipan pemasok per pemasok.
     Index parsial dipilih supaya `supplier_id NULL` (referensi) tidak
     dianggap sama satu sama lain.
   - `demand_records`  : (location_id, commodity_id, recorded_at) — satu
     observasi kebutuhan per lokasi×komoditas per waktu.

Rentang pemakaian data demo dibatasi di LAPISAN GENERATOR, bukan di sini:
baris aktual demo tidak pernah dibuat pada/di atas REF kanonik (8 Okt 12:00
UTC) karena 12 berkas tes jangkar mengunci nilai snapshot terbaru.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "013_origin_generated_at"
down_revision: Union[str, None] = "012_supplier_profile"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

# tabel, kolom tanggal untuk index (origin, <kolom>)
TABLES: list[tuple[str, str]] = [
    ("supply_records", "recorded_at"),
    ("demand_records", "recorded_at"),
    ("price_signals", "recorded_at"),
    ("menu_plans", "plan_date"),
    ("batches", "harvested_at"),
    ("decisions", "created_at"),
]


def upgrade() -> None:
    for table, date_col in TABLES:
        op.add_column(
            table,
            sa.Column(
                "origin",
                sa.String(),
                nullable=False,
                server_default=sa.text("'seed'"),
            ),
        )
        op.add_column(
            table, sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.create_check_constraint(
            f"check_{table}_origin_vocab",
            table,
            "origin IN ('seed','demo')",
        )
        op.create_index(f"ix_{table}_origin_{date_col}", table, ["origin", date_col])

    op.create_unique_constraint(
        "uq_supply_records_loc_com_time_source",
        "supply_records",
        ["location_id", "commodity_id", "recorded_at", "source"],
    )
    op.create_unique_constraint(
        "uq_demand_records_loc_com_time",
        "demand_records",
        ["location_id", "commodity_id", "recorded_at"],
    )
    op.create_index(
        "uq_price_signals_reference",
        "price_signals",
        ["location_id", "commodity_id", "recorded_at"],
        unique=True,
        postgresql_where=sa.text("source = 'pihps_reference'"),
    )
    op.create_index(
        "uq_price_signals_quote",
        "price_signals",
        ["location_id", "commodity_id", "supplier_id", "recorded_at"],
        unique=True,
        postgresql_where=sa.text("source = 'supplier_quote'"),
    )


def downgrade() -> None:
    # Baris demo TIDAK BISA diwakili tanpa kolom `origin` — kalau dibiarkan,
    # setelah turun versi mereka akan terbaca sebagai baris kanonik dan
    # menggeser jangkar angka. Jadi mereka dibuang lebih dulu: baris turunan
    # (dibuat generator, `generated_at` terisi) dan bisa dibangun ulang dalam
    # hitungan detik lewat `POST /demo/timeseries`.
    for table, _date_col in TABLES:
        op.execute(f"DELETE FROM {table} WHERE origin = 'demo'")

    op.drop_index("uq_price_signals_quote", table_name="price_signals")
    op.drop_index("uq_price_signals_reference", table_name="price_signals")
    op.drop_constraint(
        "uq_demand_records_loc_com_time", "demand_records", type_="unique"
    )
    op.drop_constraint(
        "uq_supply_records_loc_com_time_source", "supply_records", type_="unique"
    )
    for table, date_col in reversed(TABLES):
        op.drop_index(f"ix_{table}_origin_{date_col}", table_name=table)
        op.drop_constraint(
            f"check_{table}_origin_vocab", table, type_="check"
        )
        op.drop_column(table, "generated_at")
        op.drop_column(table, "origin")
