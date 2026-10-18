"""Model facts KPI P6 (keputusan Roy 2026-10-09) — migration 009.

menu_plans      : rencana porsi per lokasi per tanggal (denominator continuity)
delivery_events : porsi tersampaikan per menu plan (numerator continuity)
disposal_events : pembuangan eksplisit qty/reason (basis food loss)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MenuPlan(Base):
    __tablename__ = "menu_plans"
    __table_args__ = (
        UniqueConstraint("location_id", "plan_date", name="uq_menu_plans_loc_date"),
        CheckConstraint("planned_portions >= 0", name="menu_plans_portions_check"),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_menu_plans_origin_vocab"
        ),
        Index("ix_menu_plans_origin_plan_date", "origin", "plan_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_portions: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(
        String, nullable=False, server_default="seed"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"
    __table_args__ = (
        CheckConstraint("delivered_portions >= 0", name="delivery_portions_check"),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_delivery_events_origin_vocab"
        ),
        Index("ix_delivery_events_origin_delivered_at", "origin", "delivered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    menu_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_plans.id", ondelete="CASCADE"), nullable=False
    )
    delivered_portions: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="delivered")
    #: `origin`/`generated_at` (migrasi 017) — penanda asal, pola sama dengan
    #: tabel deret waktu lain. Default 'seed' berarti baris lama otomatis benar
    #: dan baris baru yang lupa mengisi dianggap kanonik (salahnya ke arah
    #: "data tetap ada", bukan "data demo menghapus data kanonik").
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="seed")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DisposalEvent(Base):
    __tablename__ = "disposal_events"
    __table_args__ = (
        CheckConstraint("quantity_kg >= 0", name="disposal_qty_check"),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_disposal_events_origin_vocab"
        ),
        Index("ix_disposal_events_origin_disposed_at", "origin", "disposed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=False
    )
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: Mitra yang menerima limbah (bank sampah / komposter / pakan). NULL =
    #: dibuang tanpa mitra; itu keadaan BERBEDA dari 0 kg, jadi API memisahkan
    #: `diverted` dari `unassigned_kg` alih-alih menyamakannya.
    partner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Lihat catatan di `DeliveryEvent.origin` (migrasi 017).
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default="seed")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
