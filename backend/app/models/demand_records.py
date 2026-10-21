"""Model DemandRecord — kebutuhan per lokasi/komoditas (Schema.md §2)."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DemandRecord(Base):
    __tablename__ = "demand_records"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint(
            "quantity_kg >= 0", name="demand_records_quantity_nonneg_check"
        ),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_demand_records_origin_vocab"
        ),
        # Satu observasi kebutuhan per lokasi×komoditas per waktu (migrasi 013).
        UniqueConstraint(
            "location_id",
            "commodity_id",
            "recorded_at",
            name="uq_demand_records_loc_com_time",
        ),
        Index("ix_demand_records_origin_recorded_at", "origin", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=False
    )
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    needed_by: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
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
