"""Model decision persistence (Task 8 Sprint 2) — mirror Schema.md §3."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Decision(Base):
    """Keputusan deterministik + expires_at (kontrak Roy 2026-10-05)."""

    __tablename__ = "decisions"
    # Sesi demo (025): NULL = data kerja biasa; terisi = milik sesi berjalan.
    demo_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("demo_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('regional_balance','price_anomaly',"
            "'safety_disruption','supplier_exclusion',"
            "'supplier_exclusion_restoration','supplier_procurement')",
            name="decisions_decision_type_check",
        ),
        CheckConstraint(
            "status IN ('proposed','verifier_flagged','pending_approval',"
            "'approved','rejected','executed','review_only')",
            name="decisions_status_check",
        ),
        CheckConstraint(
            "quantity_kg IS NULL OR quantity_kg > 0",
            name="decisions_quantity_positive_check",
        ),
        Index("idx_decisions_status", "status"),
        Index("idx_decisions_origin_created_at", "origin", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    decision_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="regional_balance"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="proposed"
    )
    proposed_by: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="supervisor_agent"
    )
    verified_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verifier_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Rejection loop (permintaan Roy 2026-10-07): alasan wajib saat reject,
    # iterasi v1→v2→v3 terhubung supersedes_id (bahan learning agent).
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iteration: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    demo_case: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    target_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    # Pengadaan pemasok (Demo Control 2026-10-19): identitas pemasok yang
    # DINILAI, bukan ditebak dari lokasi atau quote. NULL untuk pemindahan
    # antar SPPG yang supplier-nya terikat lewat decision_evidence.
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    commodity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commodities.id"), nullable=True
    )
    quantity_kg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    safe_delivered_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    cost_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    origin: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="seed"
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DecisionEvidence(Base):
    """Bukti audit trail; ikut terhapus saat decision dihapus (CASCADE)."""

    __tablename__ = "decision_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('sap_purchase_order','sap_goods_receipt',"
            "'gps','temperature','human_inspection','market_price')",
            name="decision_evidence_type_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_consistent: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Approval(Base):
    """Catatan approval manusia (human-in-the-loop, tidak otomatis)."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    approved_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentTrace(Base):
    """Cermin langkah agent untuk observability (tanpa rahasia)."""

    __tablename__ = "agent_traces"
    __table_args__ = (
        CheckConstraint(
            "step_name IN ('DETECT','VERIFY','TRACE','PREDICT','OPTIMIZE',"
            "'DECIDE','SUPERVISE','ACT','LEARN')",
            name="agent_traces_step_name_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_called: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # P5: metadata review 7 agen. NULL untuk baris lama (trace S3 tidak punya
    # run_id/agent), sehingga migrasi aman tanpa backfill dan UI tetap jujur.
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    agent_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    citations: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    step_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
