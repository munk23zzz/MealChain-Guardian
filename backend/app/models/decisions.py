"""Model decision persistence (Task 8 Sprint 2) — mirror Schema.md §3."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('regional_balance','price_anomaly',"
            "'safety_disruption')",
            name="decisions_decision_type_check",
        ),
        CheckConstraint(
            "status IN ('proposed','verifier_flagged','pending_approval',"
            "'approved','rejected','executed')",
            name="decisions_status_check",
        ),
        CheckConstraint(
            "quantity_kg IS NULL OR quantity_kg > 0",
            name="decisions_quantity_positive_check",
        ),
        Index("idx_decisions_status", "status"),
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
    source_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    target_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
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
            "'DECIDE','ACT','LEARN')",
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
    step_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
