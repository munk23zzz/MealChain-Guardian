"""Profil komoditas berversi + bukti suhu (Fase 3 MG, migrasi 041).

Latar: sebelum ini tidak ada satu pun tempat yang menyatakan **apakah** sebuah
komoditas wajib rantai dingin, berapa sampel minimum, dan berapa usia maksimum
sampel agar masih dianggap observasi. Yang ada hanya peta rentang suhu di
`core/commodity_limits.py` (beras 15-30 °C, sisanya 0-8 °C) dan `settings`
masa layak, dan keduanya dipakai dengan cara berbeda oleh freshness dan safety.

Yang dibuat:

- tabel ``commodity_policies`` — satu baris AKTIF per komoditas, dengan
  ``policy_version``/``policy_basis``/``policy_kind`` supaya angka demo tidak
  menyamar sebagai standar regulasi;
- isi awal untuk 4 komoditas yang ada di DB (telur, ayam, wortel, beras),
  diturunkan dari nilai yang SUDAH dipakai kode hari ini (settings masa layak +
  peta rentang) sehingga tidak ada perilaku yang berubah diam-diam;
- batasan keras di DB untuk nilai cacat: ``min > max``, ``shelf_life_days <= 0``,
  ``min_temperature_samples < 0``, dan rantai dingin tanpa rentang/usia sampel.

Nomor: rencana menyebut 035, tetapi 039 dan **040** sudah dipakai pekerjaan
lain (040 = mode sesi demo, masih belum ter-commit di pohon kerja). Migrasi ini
memakai **041** supaya tidak bertabrakan; rantai `down_revision` menunjuk 040.

Revision ID: 041_commodity_policies
Revises: 040_session_modes_and_ownership

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "041_commodity_policies"
down_revision: Union[str, None] = "040_session_modes_and_ownership"
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None

#: Versi profil awal. Naikkan bila angka/dasarnya berubah.
VERSI_AWAL = "sim-2026-10-27.v1"

#: Dasar kebijakan: nilai yang SUDAH dipakai kode + asumsi demo. Kalimat ini
#: ikut tersimpan di DB supaya pembaca (API, UI, Joule) bisa menyebutnya.
BASIS_AWAL = (
    "Asumsi demo (belum divalidasi domain owner): masa layak dari settings/seed "
    "kanon, rentang suhu dari praktik rantai dingin SPPG. Ditandai "
    "simulated_policy agar tidak terbaca sebagai regulasi."
)

#: Profil awal. `None` = komoditas ambient (tidak diukur terhadap rentang).
#: Nilai masa layak mengikuti `settings.shelf_life_days_*` hari ini:
#: telur 28, ayam 5, wortel 21, beras 180.
PROFIL_AWAL: tuple[dict, ...] = (
    {
        "commodity": "telur",
        "cold_chain_required": True,
        "safe_temp_min_c": 0.0,
        "safe_temp_max_c": 8.0,
        "shelf_life_days": 28.0,
        "min_temperature_samples": 2,
        "max_observation_age_minutes": 360,
        "max_excursion_minutes": 30.0,
    },
    {
        "commodity": "ayam",
        "cold_chain_required": True,
        "safe_temp_min_c": 0.0,
        "safe_temp_max_c": 8.0,
        "shelf_life_days": 5.0,
        "min_temperature_samples": 2,
        "max_observation_age_minutes": 360,
        "max_excursion_minutes": 30.0,
    },
    {
        "commodity": "wortel",
        "cold_chain_required": True,
        "safe_temp_min_c": 0.0,
        "safe_temp_max_c": 8.0,
        "shelf_life_days": 21.0,
        "min_temperature_samples": 2,
        "max_observation_age_minutes": 360,
        "max_excursion_minutes": 30.0,
    },
    {
        "commodity": "beras",
        "cold_chain_required": False,
        "safe_temp_min_c": None,
        "safe_temp_max_c": None,
        "shelf_life_days": 180.0,
        "min_temperature_samples": 0,
        "max_observation_age_minutes": None,
        "max_excursion_minutes": 30.0,
    },
)


def upgrade() -> None:
    op.create_table(
        "commodity_policies",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("commodity_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cold_chain_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("safe_temp_min_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("safe_temp_max_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("shelf_life_days", sa.Numeric(8, 2), nullable=False),
        sa.Column(
            "min_temperature_samples", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("max_observation_age_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "max_excursion_minutes", sa.Numeric(8, 2), server_default="30", nullable=False
        ),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("policy_basis", sa.Text(), nullable=False),
        sa.Column(
            "policy_kind",
            sa.String(),
            server_default="simulated_policy",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # ── batasan: nilai cacat tidak boleh masuk tabel ────────────────────
        sa.CheckConstraint(
            "safe_temp_min_c IS NULL OR safe_temp_max_c IS NULL "
            "OR safe_temp_min_c <= safe_temp_max_c",
            name="commodity_policies_temp_range_check",
        ),
        sa.CheckConstraint(
            "shelf_life_days > 0", name="commodity_policies_shelf_life_check"
        ),
        sa.CheckConstraint(
            "min_temperature_samples >= 0", name="commodity_policies_min_samples_check"
        ),
        sa.CheckConstraint(
            "max_observation_age_minutes IS NULL OR max_observation_age_minutes > 0",
            name="commodity_policies_max_age_check",
        ),
        sa.CheckConstraint(
            "max_excursion_minutes > 0", name="commodity_policies_max_excursion_check"
        ),
        sa.CheckConstraint(
            "policy_kind IN ('simulated_policy','calibrated_model','unavailable')",
            name="commodity_policies_kind_check",
        ),
        sa.CheckConstraint(
            "cold_chain_required = false OR ("
            "safe_temp_min_c IS NOT NULL AND safe_temp_max_c IS NOT NULL "
            "AND max_observation_age_minutes IS NOT NULL "
            "AND min_temperature_samples >= 2)",
            name="commodity_policies_cold_chain_complete_check",
        ),
        sa.CheckConstraint(
            "policy_version <> ''", name="commodity_policies_version_check"
        ),
    )
    op.create_index(
        "ix_commodity_policies_commodity_id", "commodity_policies", ["commodity_id"]
    )
    # Satu baris AKTIF per komoditas — versi lama boleh menumpuk (audit).
    op.create_index(
        "uq_commodity_policies_aktif",
        "commodity_policies",
        ["commodity_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # ── isi awal dari komoditas yang sudah ada ──────────────────────────────
    # Hanya untuk komoditas yang memang ada di tabel `commodities`: menjumlah
    # atau mengarang baris untuk komoditas yang tidak ada akan membuat tabel ini
    # bercerita tentang entitas yang tidak dikenal sisa sistem.
    for profil in PROFIL_AWAL:
        op.execute(
            sa.text(
                """
                INSERT INTO commodity_policies (
                    commodity_id, cold_chain_required,
                    safe_temp_min_c, safe_temp_max_c,
                    shelf_life_days, min_temperature_samples,
                    max_observation_age_minutes, max_excursion_minutes,
                    policy_version, policy_basis, policy_kind, is_active
                )
                SELECT c.id, :cold, :tmin, :tmax, :shelf, :minsamples,
                       :maxage, :maxexc, :versi, :basis, 'simulated_policy', true
                FROM commodities c
                WHERE c.name = :nama
                  AND NOT EXISTS (
                      SELECT 1 FROM commodity_policies p
                      WHERE p.commodity_id = c.id AND p.is_active
                  )
                """
            ).bindparams(
                nama=profil["commodity"],
                cold=profil["cold_chain_required"],
                tmin=profil["safe_temp_min_c"],
                tmax=profil["safe_temp_max_c"],
                shelf=profil["shelf_life_days"],
                minsamples=profil["min_temperature_samples"],
                maxage=profil["max_observation_age_minutes"],
                maxexc=profil["max_excursion_minutes"],
                versi=VERSI_AWAL,
                basis=BASIS_AWAL,
            )
        )


def downgrade() -> None:
    op.drop_index("uq_commodity_policies_aktif", table_name="commodity_policies")
    op.drop_index("ix_commodity_policies_commodity_id", table_name="commodity_policies")
    op.drop_table("commodity_policies")
