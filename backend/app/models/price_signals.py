"""Model PriceSignal — sinyal harga referensi/supplier (Schema.md §2)."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PriceSignal(Base):
    __tablename__ = "price_signals"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint(
            "price_per_kg > 0", name="price_signals_price_positive_check"
        ),
        CheckConstraint(
            "source IN ('pihps_reference','supplier_quote')",
            name="price_signals_source_quote_check",
        ),
        CheckConstraint(
            "(source = 'pihps_reference' AND supplier_id IS NULL) OR "
            "(source = 'supplier_quote' AND supplier_id IS NOT NULL)",
            name="price_signals_supplier_consistency_check",
        ),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_price_signals_origin_vocab"
        ),
        # Kunci upsert deret waktu (migrasi 013): dua index PARSIAL karena
        # aturannya berbeda — referensi PIHPS per lokasi×komoditas, kutipan
        # pemasok per pemasok.
        Index(
            "uq_price_signals_reference",
            "location_id",
            "commodity_id",
            "recorded_at",
            unique=True,
            postgresql_where=text("source = 'pihps_reference'"),
        ),
        Index(
            "uq_price_signals_quote",
            "location_id",
            "commodity_id",
            "supplier_id",
            "recorded_at",
            unique=True,
            postgresql_where=text("source = 'supplier_quote'"),
        ),
        Index("ix_price_signals_origin_recorded_at", "origin", "recorded_at"),
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
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(
        String, nullable=False, server_default="seed"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
