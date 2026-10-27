"""Model `commodity_policies` — profil komoditas berversi (Fase 3 MG).

Kenapa tabel, bukan peta Python: rencana Fase 3 meminta aturan yang sama bisa
dibaca core, API, seed, dan Joule **tanpa mengulang mapping Python**. Sebelum
ini aturan komoditas hidup di tiga tempat yang bisa berbeda:

- `settings.shelf_life_days_*` (dipakai `api/freshness.py`);
- `core/commodity_limits.SAFE_TEMP_BY_COMMODITY` (dipakai safety & freshness);
- tabel `commodities` (hanya `name`/`unit`).

Satu baris aktif per komoditas. `policy_version` + `policy_basis` + `policy_kind`
membuat angka demo tidak menyamar sebagai standar regulasi.

Batasan ditegakkan DI DB juga (bukan hanya di Python), karena nilai cacat yang
lolos ke tabel akan dipakai evaluasi batch dan tidak ada satu pun galat yang
muncul — persis kelas bug yang Fase 3 tutup:

- `safe_temp_min_c <= safe_temp_max_c`
- `shelf_life_days > 0`
- `min_temperature_samples >= 0`
- komoditas rantai dingin wajib punya rentang + batas usia sampel
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CommodityPolicyRow(Base):
    """Satu profil aktif per komoditas.

    Nama kelas sengaja `CommodityPolicyRow`: `CommodityPolicy` sudah dipakai
    dataclass domain di `core/commodity_policy.py`. Dua kelas dengan nama sama
    di dua modul adalah sumber kebingungan yang mahal saat demo ("profil mana
    yang dipakai?").
    """

    __tablename__ = "commodity_policies"
    __table_args__ = (
        # Rentang hanya boleh terbalik bila salah satunya kosong (ambient).
        CheckConstraint(
            "safe_temp_min_c IS NULL OR safe_temp_max_c IS NULL "
            "OR safe_temp_min_c <= safe_temp_max_c",
            name="commodity_policies_temp_range_check",
        ),
        CheckConstraint(
            "shelf_life_days > 0", name="commodity_policies_shelf_life_check"
        ),
        CheckConstraint(
            "min_temperature_samples >= 0",
            name="commodity_policies_min_samples_check",
        ),
        CheckConstraint(
            "max_observation_age_minutes IS NULL OR max_observation_age_minutes > 0",
            name="commodity_policies_max_age_check",
        ),
        CheckConstraint(
            "max_excursion_minutes > 0",
            name="commodity_policies_max_excursion_check",
        ),
        CheckConstraint(
            "policy_kind IN ('simulated_policy','calibrated_model','unavailable')",
            name="commodity_policies_kind_check",
        ),
        # Rantai dingin wajib punya rentang + batas usia sampel + minimal 2 sampel.
        CheckConstraint(
            "cold_chain_required = false OR ("
            "safe_temp_min_c IS NOT NULL AND safe_temp_max_c IS NOT NULL "
            "AND max_observation_age_minutes IS NOT NULL "
            "AND min_temperature_samples >= 2)",
            name="commodity_policies_cold_chain_complete_check",
        ),
        # Satu baris aktif per komoditas: versi lama tetap tersimpan untuk audit.
        CheckConstraint(
            "policy_version <> ''", name="commodity_policies_version_check"
        ),
        # Indeks dideklarasikan INLINE (rencana Fase 3 §Berkas): tanpa deklarasi
        # di sini `alembic check` mengusulkan `remove_index` untuk indeks yang
        # dibuat migrasi — drift yang terbukti muncul saat migrasi 041 diuji.
        Index("ix_commodity_policies_commodity_id", "commodity_id"),
        Index(
            "uq_commodity_policies_aktif",
            "commodity_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commodities.id", ondelete="CASCADE"),
        nullable=False,
    )
    cold_chain_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    safe_temp_min_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    safe_temp_max_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    shelf_life_days: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    min_temperature_samples: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    max_observation_age_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    max_excursion_minutes: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default="30"
    )
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    policy_basis: Mapped[str] = mapped_column(Text, nullable=False)
    policy_kind: Mapped[str] = mapped_column(
        String, nullable=False, server_default="simulated_policy"
    )
    #: True = baris yang dipakai evaluasi. Versi lain disimpan non-aktif
    #: supaya "profil apa yang dipakai saat keputusan ini dibuat" bisa dijawab.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
