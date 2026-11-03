"""Cache rute JALAN (OSRM) untuk garis pemasok → tujuan di peta.

Revision ID: 014_road_routes
Revises: 013_origin_generated_at

Latar (keputusan pemilik 2026-10-16, dua tanya-jawab): garis di peta harus
mengikuti **jalan**, bukan garis lurus, dan rutenya diambil **saat seeding/sync**
lalu disimpan — bukan saat peta dibuka.

Empat keputusan yang sengaja diambil di sini:

1. **Rute disimpan, bukan diambil ulang saat peta dibuka.** Demo tidak boleh
   bergantung pada internet, hasil harus identik setiap kali diperlihatkan, dan
   server OSRM demo publik tidak boleh dibanjiri peramban pengunjung.
2. **Kunci = KOORDINAT ternormalisasi, bukan (supplier_id, location_id).**
   Dua batch dari pemasok dan tujuan yang sama cuma butuh satu rute, dan rute
   yang sama bisa dipakai ulang kalau koordinatnya sama. `UNIQUE` pada kunci
   membuat sinkronisasi idempoten ("dua kali jalan tidak menggandakan").
3. **`source` NOT NULL + CHECK vocabs.** Baris ini data pihak ketiga (routing
   OpenStreetMap); UI harus bisa menyebut asalnya, dan kosakata yang terbatas
   mencegah nilai bebas masuk diam-diam di kemudian hari.
4. **`geometry` JSONB apa adanya dari OSRM** (`[lon, lat]`), tanpa disederhanakan
   ulang di sini — kita tidak mengubah data orang lain, penyederhanaan sudah
   diminta ke OSRM sendiri lewat `overview=simplified` (~36 titik/rute, 1,5 KB).

Tidak ada kolom relasi ke `suppliers`/`locations`: rute ini murni geometri
jalan antar dua titik. Kalau pemasok pindah koordinat, kuncinya berubah dan
rute baru diambil — data lama tidak berbohong soal apa yang pernah dihitung.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "014_road_routes"
down_revision: Union[str, None] = "013_origin_generated_at"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "road_routes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("route_key", sa.String(length=120), nullable=False),
        sa.Column(
            "profile",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'driving'"),
        ),
        sa.Column("origin_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("origin_lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("destination_lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("destination_lon", sa.Numeric(9, 6), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("geometry", JSONB(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("route_key", name="uq_road_routes_key"),
        sa.CheckConstraint("distance_m >= 0", name="road_routes_distance_check"),
        sa.CheckConstraint("duration_s >= 0", name="road_routes_duration_check"),
        sa.CheckConstraint("source IN ('osrm')", name="check_road_routes_source_vocab"),
    )


def downgrade() -> None:
    # Cache turunan: seluruh isinya bisa diambil ulang dari OSRM dalam hitungan
    # detik (`scripts/sync_road_routes.py`), jadi tidak ada yang perlu diselamatkan.
    op.drop_table("road_routes")
