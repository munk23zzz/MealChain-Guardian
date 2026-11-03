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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MenuPlan(Base):
    __tablename__ = "menu_plans"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint("delivered_portions >= 0", name="delivery_portions_check"),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_delivery_events_origin_vocab"
        ),
        Index("ix_delivery_events_origin_delivered_at", "origin", "delivered_at"),
        # Index operasional yang lahir dari migrasi 009/013/029 — dideklarasikan
        # di sini supaya `alembic check` tidak mengusulkan DROP (audit DB-01).
        Index("idx_delivery_events_menu_plan", "menu_plan_id"),
        Index(
            "uq_delivery_events_source_ref",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    menu_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("menu_plans.id", ondelete="CASCADE"), nullable=False
    )
    delivered_portions: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="delivered")
    # Kunci idempotensi penulis KPI (migrasi 029): `receipt:<uuid>` untuk baris
    # yang lahir dari approve penerimaan. NULL untuk baris seeder lama.
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: `origin`/`generated_at` (migrasi 017) — penanda asal, pola sama dengan
    #: tabel deret waktu lain. Default 'seed' berarti baris lama otomatis benar
    #: dan baris baru yang lupa mengisi dianggap kanonik (salahnya ke arah
    #: "data tetap ada", bukan "data demo menghapus data kanonik").
    origin: Mapped[str] = mapped_column(String, nullable=False, server_default="seed")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DisposalEvent(Base):
    __tablename__ = "disposal_events"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        # Indeks FK (migrasi 033): DB sudah punya indeks ini; tanpa
        # deklarasi di sini `alembic check` akan mengusulkan drop.
        Index("ix_disposal_events_commodity_id", "commodity_id"),
        CheckConstraint("quantity_kg >= 0", name="disposal_qty_check"),
        CheckConstraint(
            "origin IN ('seed','demo')", name="check_disposal_events_origin_vocab"
        ),
        Index("ix_disposal_events_origin_disposed_at", "origin", "disposed_at"),
        Index("idx_disposal_events_loc_time", "location_id", "disposed_at"),
        Index(
            "uq_disposal_events_source_ref",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    commodity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commodities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: Mitra yang menerima limbah (bank sampah / komposter / pakan). NULL =
    #: dibuang tanpa mitra; itu keadaan BERBEDA dari 0 kg, jadi API memisahkan
    #: `diverted` dari `unassigned_kg` alih-alih menyamakannya.
    partner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Kunci idempotensi penulis KPI (migrasi 029): `disposal:<kunci>`.
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Lihat catatan di `DeliveryEvent.origin` (migrasi 017).
    origin: Mapped[str] = mapped_column(String, nullable=False, server_default="seed")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
