"""Router decisions (Task 10 Sprint 2): persist + validity endpoint.

- POST /decisions: simpan recommendation terpilih + expires_at (wajib).
  TIDAK mengeksekusi PO, TIDAK approve otomatis (Rules.md).
- GET /decisions/{id}: status + validitas terhitung (now < expires_at).
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models import Commodity, Decision, Location

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
    from decimal import Decimal as D

    qty = cand.get("quantity_kg")
    sdc = recommendation.get("safe_delivered_cost")
    return {
        "source_location": cand.get("source_location"),
        "target_location": cand.get("destination_location"),
        "commodity": cand.get("commodity"),
        "quantity_kg": D(str(qty)) if qty is not None else None,
        "safe_delivered_cost": D(str(sdc)) if sdc is not None else None,
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
    now = datetime.now(timezone.utc)
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
        "safe_delivered_cost": float(row.safe_delivered_cost) if row.safe_delivered_cost is not None else None,
        "cost_breakdown": row.cost_breakdown,
        "expires_at": row.expires_at.isoformat(),
        "created_at": row.created_at.isoformat(),
        "valid": validity["valid"],
        "seconds_remaining": validity["seconds_remaining"],
    }
