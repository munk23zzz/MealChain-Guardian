"""Profil pemasok: koordinat + fokus komoditas + kapasitas + sertifikasi.

Revision ID: 012_supplier_profile
Revises: 011_supplier_exclusions

Latar (permintaan pemilik proyek 2026-10-14, Fase 2 rencana
`.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`): pemasok harus bisa
ditampilkan di peta, jadi butuh koordinat — sebelumnya `suppliers` hanya punya
nama/lokasi/skor.

Tiga keputusan yang sengaja diambil di sini:

1. **Semua kolom profil nullable.** 14 pemasok kanonik (`sprint1_seed.json`)
   memang tidak punya kapasitas/sertifikasi/alamat. Mengisinya dengan angka
   tebakan sama dengan mengarang data; lebih baik NULL yang jujur dan UI
   menampilkan "—".
2. **Backfill KOORDINAT untuk pemasok lama**, diturunkan dari titik hub
   SPPG-nya dengan geseran deterministik kecil supaya pemasok satu kota tidak
   saling menumpuk di satu pin. Ini derivasi dari data yang SUDAH ada (lokasi
   hub), bukan angka baru.
3. **CHECK koordinat berpasangan** (`(lat IS NULL) = (lon IS NULL)`): setengah
   koordinat tidak bisa dipetakan dan selalu menandakan data rusak.

Backfill dijalankan SEBELUM constraint rentang dibuat supaya kegagalan pada
data lama terlihat sebagai kegagalan migrasi, bukan tertelan constraint.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "012_supplier_profile"
down_revision: Union[str, None] = "011_supplier_exclusions"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "suppliers", sa.Column("latitude", sa.Numeric(9, 6), nullable=True)
    )
    op.add_column(
        "suppliers", sa.Column("longitude", sa.Numeric(9, 6), nullable=True)
    )
    op.add_column(
        "suppliers",
        sa.Column(
            "commodity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commodities.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "suppliers",
        sa.Column("capacity_kg_per_week", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "suppliers", sa.Column("certification_status", sa.String(), nullable=True)
    )
    op.add_column("suppliers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("suppliers", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column(
        "suppliers", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Backfill koordinat pemasok lama dari hub-nya (9 posisi berbeda per hub).
    op.execute(
        """
        WITH ranked AS (
            SELECT s.id,
                   l.latitude  AS base_lat,
                   l.longitude AS base_lon,
                   row_number() OVER (PARTITION BY s.location_id ORDER BY s.name) - 1 AS rn
            FROM suppliers s
            JOIN locations l ON l.id = s.location_id
            WHERE s.latitude IS NULL AND l.latitude IS NOT NULL
        )
        UPDATE suppliers s
        SET latitude  = r.base_lat  + (0.012 * ((r.rn % 3) - 1)),
            longitude = r.base_lon + (0.012 * (((r.rn / 3) % 3) - 1)),
            updated_at = now()
        FROM ranked r
        WHERE s.id = r.id
        """
    )

    op.create_check_constraint(
        "check_supplier_latitude_range",
        "suppliers",
        "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
    )
    op.create_check_constraint(
        "check_supplier_longitude_range",
        "suppliers",
        "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
    )
    op.create_check_constraint(
        "check_supplier_coordinates_pair",
        "suppliers",
        "(latitude IS NULL) = (longitude IS NULL)",
    )
    op.create_check_constraint(
        "check_supplier_capacity_nonneg",
        "suppliers",
        "capacity_kg_per_week IS NULL OR capacity_kg_per_week >= 0",
    )
    op.create_check_constraint(
        "check_supplier_certification_vocab",
        "suppliers",
        "certification_status IS NULL OR certification_status IN "
        "('none','hygiene','haccp')",
    )
    op.create_index("ix_suppliers_location_id", "suppliers", ["location_id"])
    op.create_index("ix_suppliers_commodity_id", "suppliers", ["commodity_id"])


def downgrade() -> None:
    op.drop_index("ix_suppliers_commodity_id", table_name="suppliers")
    op.drop_index("ix_suppliers_location_id", table_name="suppliers")
    op.drop_constraint("check_supplier_certification_vocab", "suppliers", type_="check")
    op.drop_constraint("check_supplier_capacity_nonneg", "suppliers", type_="check")
    op.drop_constraint("check_supplier_coordinates_pair", "suppliers", type_="check")
    op.drop_constraint("check_supplier_longitude_range", "suppliers", type_="check")
    op.drop_constraint("check_supplier_latitude_range", "suppliers", type_="check")
    op.drop_column("suppliers", "updated_at")
    op.drop_column("suppliers", "contact_name")
    op.drop_column("suppliers", "address")
    op.drop_column("suppliers", "certification_status")
    op.drop_column("suppliers", "capacity_kg_per_week")
    op.drop_column("suppliers", "commodity_id")
    op.drop_column("suppliers", "longitude")
    op.drop_column("suppliers", "latitude")
