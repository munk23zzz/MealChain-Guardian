"""Model BatchReceipt — catatan penerimaan barang (migrasi 016, keputusan 026)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BatchReceipt(Base):
    """Satu kali penerimaan barang dicatat oleh petugas.

    Bukan kolom di `batches` karena satu batch bisa diterima beberapa kali dan
    tiap catatan punya pencatat & waktunya sendiri (lihat migrasi 016).
    """

    __tablename__ = "batch_receipts"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        Index("ix_batch_receipts_batch_recorded", "batch_id", "recorded_at"),
        # Invarian 026: satu batch paling banyak satu penerimaan disetujui.
        Index(
            "uq_batch_receipts_satu_disetujui",
            "batch_id",
            unique=True,
            postgresql_where=sql_text("status = 'disetujui'"),
        ),
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

    # ---- Keputusan penerimaan (migrasi 026) --------------------------------
    #: 'menunggu' (belum masuk stok) → 'disetujui' / 'ditolak'.
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="menunggu"
    )
    #: Kepala SPPG yang memutuskan. NULL selama masih 'menunggu'.
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Alasan penolakan (wajib saat 'ditolak'); NULL untuk keadaan lain.
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Baris stok yang lahir dari persetujuan — dasar idempotensi approve.
    supply_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supply_records.id", ondelete="SET NULL"),
        nullable=True,
    )
