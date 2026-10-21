"""Model sesi demo (migrasi 024, 20 Okt 2026).

Satu baris = satu jendela demo. `status` hanya tiga nilai: `active` (data
terlihat), `expired` (lewat waktu; data sesi sudah dibersihkan), `ended`
(ditutup manual). `anchor_now` menyimpan waktu server saat tombol "Siapkan data
demo" ditekan — jam TIDAK dibekukan, hanya dicatat supaya label "hari ini"
konsisten dengan saat sesi dimulai.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DemoSession(Base):
    __tablename__ = "demo_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','expired','ended')",
            name="demo_sessions_status_check",
        ),
        Index("ix_demo_sessions_status_expires", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anchor_now: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    template_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
