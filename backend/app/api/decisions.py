"""Router decisions (Task 10 Sprint 2): persist + validity endpoint.

- POST /decisions: simpan recommendation terpilih + expires_at (wajib).
  TIDAK mengeksekusi PO, TIDAK approve otomatis (Rules.md).
- GET /decisions/{id}: status + validitas terhitung (now < expires_at).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models import Commodity, Decision, Location, User

router = APIRouter()

DEFAULT_TTL_MINUTES = 30


class DecisionCreate(BaseModel):
    recommendation: dict
    ttl_minutes: int = Field(
        default=DEFAULT_TTL_MINUTES, ge=1, le=1440
    )
    decision_type: str = "regional_balance"


def _validity(expires_at: datetime) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "valid": now < expires_at,
        "seconds_remaining": max(
            0, int((expires_at - now).total_seconds())
        ),
    }


def _extract(recommendation: dict):
    """Ambil field terstruktur dari snapshot rekomendasi."""
    cand = recommendation.get("candidate", {})
    qty = cand.get("quantity_kg")
    sdc = recommendation.get("safe_delivered_cost")
    return {
        "source_location": cand.get("source_location"),
        "target_location": cand.get("destination_location"),
        "commodity": cand.get("commodity"),
        "quantity_kg": Decimal(str(qty)) if qty is not None else None,
        "safe_delivered_cost": (
            Decimal(str(sdc)) if sdc is not None else None
        ),
        "cost_breakdown": recommendation.get("cost_breakdown"),
    }


@router.post("/decisions", status_code=201)
async def create_decision(
    payload: DecisionCreate,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=payload.ttl_minutes)
    fields = _extract(payload.recommendation)

    async def _loc_id(name):
        if not name:
            return None
        row = (
            await db.execute(
                select(Location).where(Location.name == name)
            )
        ).scalar_one_or_none()
        return row.id if row else None

    async def _com_id(name):
        if not name:
            return None
        row = (
            await db.execute(
                select(Commodity).where(Commodity.name == name)
            )
        ).scalar_one_or_none()
        return row.id if row else None

    decision = Decision(
        id=uuid4(),
        decision_type=payload.decision_type,
        status="proposed",
        proposed_by="supervisor_agent",
        source_location_id=await _loc_id(fields["source_location"]),
        target_location_id=await _loc_id(fields["target_location"]),
        commodity_id=await _com_id(fields["commodity"]),
        quantity_kg=fields["quantity_kg"],
        safe_delivered_cost=fields["safe_delivered_cost"],
        cost_breakdown=fields["cost_breakdown"],
        expires_at=expires_at,
    )
    db.add(decision)
    await db.commit()
    return {
        "decision_id": str(decision.id),
        "status": "proposed",
        "valid": True,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "ttl_minutes": payload.ttl_minutes,
    }


@router.get("/decisions")
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Feed keputusan (S3-12): baris aktual, terbaru dulu, tanpa karangan."""
    rows = (
        await db.execute(
            select(Decision).order_by(
                Decision.created_at.desc(), Decision.id.desc()
            )
        )
    ).scalars().all()
    items = []
    for row in rows:
        validity = _validity(row.expires_at)
        items.append(
            {
                "decision_id": str(row.id),
                "decision_type": row.decision_type,
                "status": row.status,
                "proposed_by": row.proposed_by,
                "quantity_kg": (
                    float(row.quantity_kg)
                    if row.quantity_kg is not None
                    else None
                ),
                "safe_delivered_cost": (
                    float(row.safe_delivered_cost)
                    if row.safe_delivered_cost is not None
                    else None
                ),
                "expires_at": row.expires_at.isoformat(),
                "created_at": row.created_at.isoformat(),
                "valid": validity["valid"],
                "seconds_remaining": validity["seconds_remaining"],
                "rejection_reason": row.rejection_reason,
                "iteration": row.iteration or 1,
                "supersedes_id": (
                    str(row.supersedes_id) if row.supersedes_id else None
                ),
                "demo_case": row.demo_case,
            }
        )
    return {"items": items}


@router.get("/decisions/{decision_id}/chain")
async def get_decision_chain(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Timeline keluarga iterasi (rejection loop): v1 → v2 → v3...

    Jalur supersedes_id ditelusuri dua arah dari keputusan mana pun
    dalam keluarga; urutan akhir by iteration lalu created_at.
    """
    anchor = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if anchor is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")

    async def _parent_of(row: Decision):
        if not row.supersedes_id:
            return None
        return (
            await db.execute(
                select(Decision).where(Decision.id == row.supersedes_id)
            )
        ).scalar_one_or_none()

    async def _children_of(row: Decision):
        return (
            await db.execute(
                select(Decision)
                .where(Decision.supersedes_id == row.id)
                .order_by(Decision.iteration.asc(), Decision.created_at.asc())
            )
        ).scalars().all()

    # Naik ke root, lalu turun seluruh cabang utama.
    root = anchor
    while True:
        p = await _parent_of(root)
        if p is None:
            break
        root = p
    family: list[Decision] = []
    current = root
    while current is not None:
        family.append(current)
        kids = await _children_of(current)
        current = kids[0] if kids else None
    chain = [
        {
            "decision_id": str(r.id),
            "iteration": r.iteration or 1,
            "status": r.status,
            "rejection_reason": r.rejection_reason,
            "quantity_kg": (
                float(r.quantity_kg) if r.quantity_kg is not None else None
            ),
            "safe_delivered_cost": (
                float(r.safe_delivered_cost)
                if r.safe_delivered_cost is not None
                else None
            ),
            "created_at": r.created_at.isoformat(),
            "demo_case": r.demo_case,
        }
        for r in family
    ]
    return {"anchor_id": str(anchor.id), "chain": chain}


@router.get("/decisions/{decision_id}/traces")
async def get_decision_traces(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Timeline AgentTrace aktual (S3-12): urutan langkah asli dari DB."""
    decision = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    from app.models import AgentTrace

    rows = (
        await db.execute(
            select(AgentTrace)
            .where(AgentTrace.decision_id == decision_id)
            .order_by(AgentTrace.step_at.asc(), AgentTrace.id.asc())
        )
    ).scalars().all()
    steps = [
        {
            "step_name": row.step_name,
            "tool_called": row.tool_called,
            "input_summary": row.input_summary,
            "output_summary": row.output_summary,
            "step_at": row.step_at.isoformat(),
        }
        for row in rows
    ]
    return {"decision_id": str(decision_id), "steps": steps}


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    validity = _validity(row.expires_at)
    return {
        "decision_id": str(row.id),
        "decision_type": row.decision_type,
        "status": row.status,
        "proposed_by": row.proposed_by,
        "source_location_id": str(row.source_location_id) if row.source_location_id else None,
        "target_location_id": str(row.target_location_id) if row.target_location_id else None,
        "commodity_id": str(row.commodity_id) if row.commodity_id else None,
        "quantity_kg": float(row.quantity_kg) if row.quantity_kg is not None else None,
        "safe_delivered_cost": (
            float(row.safe_delivered_cost)
            if row.safe_delivered_cost is not None
            else None
        ),
        "cost_breakdown": row.cost_breakdown,
        "expires_at": row.expires_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "valid": validity["valid"],
        "seconds_remaining": validity["seconds_remaining"],
        "rejection_reason": row.rejection_reason,
        "iteration": row.iteration or 1,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "demo_case": row.demo_case,
    }
