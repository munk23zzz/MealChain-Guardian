"""Model Batch — unit inti freshness/safety check (Schema.md §2)."""

import uuid
from datetime import datetime
from decimal import Decimal

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint(
            "freshness_score IS NULL OR (freshness_score >= 0 AND freshness_score <= 1)",
            name="batches_freshness_range_check",
        ),
        CheckConstraint(
            "safety_status IN ('pending','pass','fail','needs_verification')",
            name="batches_safety_status_check",
        ),
        CheckConstraint(
            "certification_status IN ('none','hygiene','haccp')",
            name="batches_certification_check",
        ),
        CheckConstraint("origin IN ('seed','demo')", name="check_batches_origin_vocab"),
        CheckConstraint(
            "dispatched_at IS NULL OR dispatched_at >= harvested_at",
            name="batches_dispatch_after_harvest",
        ),
        Index("ix_batches_origin_harvested_at", "origin", "harvested_at"),
        Index("idx_batches_safety_status", "safety_status"),
        Index("ix_batches_quarantine_status", "quarantine_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False
    )
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Sesi demo (024): baris hanya terlihat selama sesinya. NULL = data kerja
    # biasa (tidak tersaring) — dipakai saat demo_session_enforce mati.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    harvested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    temperature_log: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    certification_status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="none"
    )
    freshness_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    safety_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )
    usable_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Jam barang meninggalkan pemasok. NULL = belum berangkat (bukan jam nol);
    #: estimasi tiba dihitung dari sini + waktu tempuh OSRM (app/core/journey.py).
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    origin: Mapped[str] = mapped_column(
        String, nullable=False, server_default="seed"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Karantina (migrasi 019): batch ditahan dari kandidat alokasi sampai
    # manusia melepas atau menyatakannya gagal. Lihat core/quarantine.py.
    quarantine_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="none"
    )
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    quarantined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quarantine_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quarantine_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
