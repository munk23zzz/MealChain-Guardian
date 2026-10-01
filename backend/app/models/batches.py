"""Model Batch — unit inti freshness/safety check (Schema.md §2)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
