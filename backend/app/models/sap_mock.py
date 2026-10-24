"""Model Mock SAP — meniru struktur OData asli (Schema.md §4)."""

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SapMockMaterialStock(Base):
    __tablename__ = "sap_mock_material_stock"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    material_number: Mapped[str] = mapped_column(String, nullable=False)
    plant: Mapped[str] = mapped_column(String, nullable=False)
    storage_location: Mapped[str | None] = mapped_column(String, nullable=True)
    batch: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SapMockPurchaseOrder(Base):
    __tablename__ = "sap_mock_purchase_orders"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','confirmed')",
            name="sap_mock_po_status_check",
        ),
        CheckConstraint(
            "price > 0", name="sap_mock_po_price_positive_check"
        ),
        # 028: penanda data demo, sejajar dengan tabel deret waktu (017).
        CheckConstraint(
            "origin IN ('seed','demo')", name="sap_mock_po_origin_check"
        ),
        Index("ix_sap_mock_purchase_orders_decision_id", "decision_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    po_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False
    )
    material_number: Mapped[str] = mapped_column(Text, nullable=False)
    ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")
    # 028: penanda data demo ('seed' = data kerja, 'demo' = dibersihkan reset-demo).
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="seed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
