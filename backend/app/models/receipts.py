"""Model BatchReceipt — catatan penerimaan barang (migrasi 016)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BatchReceipt(Base):
    """Satu kali penerimaan barang dicatat oleh petugas.

    Bukan kolom di `batches` karena satu batch bisa diterima beberapa kali dan
    tiap catatan punya pencatat & waktunya sendiri (lihat migrasi 016).
    """

    __tablename__ = "batch_receipts"
    __table_args__ = (
        Index("ix_batch_receipts_batch_recorded", "batch_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: Snapshot titik periksa yang benar-benar dicentang saat mencatat ({id: bool}).
    checked: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    #: Isian "Lainnya" — keadaan yang tidak ada di daftar periksa. NULL = tidak ada.
    other_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
