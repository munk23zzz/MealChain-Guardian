"""Model Supplier — pemasok dengan reliability_score (Schema.md §1).

Profil pemasok (Ruling 2026-10-14 / Fase 2 rencana scope-pemasok-peta): kolom
koordinat + fokus komoditas + kapasitas + sertifikasi + alamat, supaya pemasok
bisa ditampilkan di peta sebagai titik (permintaan pemilik proyek).

Kolom profil SEMUA nullable dengan sengaja: pemasok kanonik dari
`data/seed/sprint1_seed.json` bisa ada tanpa profil lengkap, dan kolom yang
diisi nilai tebakan lebih buruk daripada NULL yang jujur. Yang di-backfill saat
migrasi hanya KOORDINAT (diturunkan dari titik hub SPPG-nya) karena peta tidak
bisa menampilkan pemasok tanpa posisi.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="check_reliability",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="check_supplier_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="check_supplier_longitude_range",
        ),
        # Titik peta butuh DUA koordinat; setengah koordinat = data rusak.
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="check_supplier_coordinates_pair",
        ),
        CheckConstraint(
            "capacity_kg_per_week IS NULL OR capacity_kg_per_week >= 0",
            name="check_supplier_capacity_nonneg",
        ),
        CheckConstraint(
            "certification_status IS NULL OR "
            "certification_status IN ('none','hygiene','haccp')",
            name="check_supplier_certification_vocab",
        ),
        Index("ix_suppliers_location_id", "location_id"),
        Index("ix_suppliers_commodity_id", "commodity_id"),
        Index("idx_suppliers_location", "location_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    reliability_score: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, server_default="0.80"
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # --- Profil untuk peta pemasok (semua nullable; lihat docstring modul) ---
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    commodity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=True
    )
    capacity_kg_per_week: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    certification_status: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
