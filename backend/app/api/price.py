"""Router price (Task 12) — referensi terbaru + deviation via core."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.api.supply import _resolve_commodity, _resolve_location
from app.core.price import price_deviation
from app.models import PriceSignal, User

router = APIRouter()


@router.get("/price/{location}/{commodity}")
async def get_price(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    loc = await _resolve_location(db, location)
    com = await _resolve_commodity(db, commodity)
    record = (
        await db.execute(
            select(PriceSignal)
            .where(
                PriceSignal.location_id == loc.id,
                PriceSignal.commodity_id == com.id,
                PriceSignal.source == "pihps_reference",
            )
            .order_by(PriceSignal.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="price reference tidak ditemukan")
    return {
        "location": loc.name,
        "commodity": com.name,
        "price_per_kg": float(record.price_per_kg),
        "recorded_at": record.recorded_at.isoformat(),
        "source": record.source,
    }


class DeviationRequest(BaseModel):
    location: str
    commodity: str
    supplier_price: Decimal


@router.post("/price/deviation")
async def post_price_deviation(
    payload: DeviationRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    loc = await _resolve_location(db, payload.location)
    com = await _resolve_commodity(db, payload.commodity)
    record = (
        await db.execute(
            select(PriceSignal)
            .where(
                PriceSignal.location_id == loc.id,
                PriceSignal.commodity_id == com.id,
                PriceSignal.source == "pihps_reference",
            )
            .order_by(PriceSignal.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="price reference tidak ditemukan")

    result = price_deviation(payload.supplier_price, record.price_per_kg)
    return {
        "deviation_pct": str(result["deviation_pct"]),
        "reference_price": float(record.price_per_kg),
        "classification": str(result["status"]),
        "flagged": bool(result["flagged"]),
    }
