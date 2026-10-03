"""Router demand + forecast (Task 11).

CATATAN URUTAN: router forecast terdaftar SEBELUM router demand generik
(`/demand/{location}` dapat menangkap "forecast" sebagai path param).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.supply import _resolve_commodity, _resolve_location
from app.core.forecasting_fallback import statistical_forecast
from app.models import DemandRecord

router = APIRouter()
forecast_router = APIRouter()


class DemandResponse(BaseModel):
    quantity_kg: float
    needed_by: str


class ForecastResponse(BaseModel):
    forecast_qty_kg: float
    method: str
    confidence: float


@forecast_router.get("/demand/forecast/{location}/{commodity}")
async def get_demand_forecast(
    location: str,
    commodity: str,
    horizon_days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> ForecastResponse:
    loc = await _resolve_location(db, location)
    com = await _resolve_commodity(db, commodity)
    rows = (
        (
            await db.execute(
                select(DemandRecord)
                .where(
                    DemandRecord.location_id == loc.id,
                    DemandRecord.commodity_id == com.id,
                )
                .order_by(DemandRecord.recorded_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="demand history tidak ditemukan")
    daily_kg = [float(r.quantity_kg) for r in reversed(rows)]
    result = statistical_forecast(daily_kg, horizon_days=horizon_days)
    return ForecastResponse(
        forecast_qty_kg=float(result["forecast_qty_kg"]),
        method=str(result["method"]),
        confidence=float(result["confidence"]),
    )


@router.get("/demand/{location}/{commodity}")
async def get_demand(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
) -> DemandResponse:
    loc = await _resolve_location(db, location)
    com = await _resolve_commodity(db, commodity)
    record = (
        await db.execute(
            select(DemandRecord)
            .where(
                DemandRecord.location_id == loc.id,
                DemandRecord.commodity_id == com.id,
            )
            .order_by(DemandRecord.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="demand tidak ditemukan")
    return DemandResponse(
        quantity_kg=float(record.quantity_kg),
        needed_by=record.needed_by.isoformat(),
    )
