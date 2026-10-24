"""Model tabel ledger hash-chain (audit DB-01, 2026-10-24).

Tabel `ledger_blocks` dibuat migrasi 018 dan ditulis oleh ledger service lewat
SQL, tetapi tidak pernah punya model SQLAlchemy. Akibatnya `alembic check`
menganggapnya tabel yatim dan `--autogenerate` mengusulkan **DROP** riwayat
audit (353 blok). Model di bawah menyalin DDL apa adanya: kolom, tipe, unique
`height`, check panjang hash 64, dan index `height`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LedgerBlock(Base):
    """Satu blok rantai audit (§18): hash payload + hash blok sebelumnya."""

    __tablename__ = "ledger_blocks"
    __table_args__ = (
        UniqueConstraint("height", name="ledger_blocks_height_key"),
        CheckConstraint(
            "length(payload_hash) = 64 AND length(prev_hash) = 64",
            name="ledger_hash_len_check",
        ),
        Index("idx_ledger_blocks_height", "height"),
        Index("idx_ledger_blocks_generation", "generation", "height"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    height: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prev_hash: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    # Generasi data demo: naik setiap reset demo, supaya blok lama bisa
    # diarsipkan tanpa memutus rantai (lihat migrasi 031 + audit N3).
    generation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LedgerMeta(Base):
    """Penanda generasi ledger (satu baris, `id = 1`).

    Naik setiap data demo direset; lihat migrasi 031 dan `ledger_service`.
    """

    __tablename__ = "ledger_meta"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    generation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
