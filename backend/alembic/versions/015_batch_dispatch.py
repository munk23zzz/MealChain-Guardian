"""Jam berangkat kiriman (`batches.dispatched_at`) — dasar estimasi tiba.

Revision ID: 015_batch_dispatch
Revises: 014_road_routes

Latar (permintaan pemilik 2026-10-16): saat lapisan "jalur kiriman" dinyalakan,
peta harus menyebut **waktu estimasi sampai**, dan jalur itu memang perjalanan
barang dari pemasok ke tujuan — jadi angkanya harus sinkron dengan DB.

Masalahnya sebelum migrasi ini: DB tidak punya jam keberangkatan sama sekali.
Yang ada hanya waktu tempuh jalur (cache `road_routes.duration_s` dari OSRM) dan
batas layak pakai (`usable_until`). Tanpa jam berangkat, "estimasi tiba" apa pun
adalah angka karangan. Karena itu jam berangkatnya dibuat nyata di sini.

Empat keputusan yang sengaja diambil:

1. **NULL berarti "belum berangkat", bukan nol.** Barang yang masih di pemasok
   tidak punya jam berangkat; UI harus bisa mengatakannya apa adanya, dan
   estimasi tiba baru dihitung setelah jam ini terisi.
2. **CHECK `dispatched_at >= harvested_at`.** Kiriman tidak mungkin berangkat
   sebelum barangnya dipanen; ini menjaga aritmetika waktu agar tidak
   membalikkan cerita perjalanan (sekaligus mendeteksi salah isi seed).
3. **Kolom nullable + tanpa nilai default.** Baris lama (termasuk batch yang
   sudah kedaluwarsa) tetap jujur: jam berangkatnya memang tidak pernah dicatat,
   jadi tidak diisi nilai yang dibuat-buat.
4. **Bukan kolom turunan.** Estimasi tiba TIDAK disimpan; ia dihitung saat baca
   (`app/core/journey.py`) dari jam berangkat + waktu tempuh OSRM, supaya tidak
   ada dua sumber kebenaran yang bisa saling bertentangan.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "015_batch_dispatch"
down_revision: Union[str, None] = "014_road_routes"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "batches_dispatch_after_harvest",
        "batches",
        "dispatched_at IS NULL OR dispatched_at >= harvested_at",
    )


def downgrade() -> None:
    # Jam berangkat turunan dari berkas seed + waktu referensi seeder, jadi bisa
    # dipulihkan dengan `alembic upgrade head` lalu seeding ulang.
    op.drop_constraint("batches_dispatch_after_harvest", "batches", type_="check")
    op.drop_column("batches", "dispatched_at")
