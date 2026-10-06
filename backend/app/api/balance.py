"""Router balance (Task 10 Sprint 2) — tipis: validasi + delegasi service."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models import (
    Commodity,
    DemandRecord,
    Location,
    SupplyRecord,
)
from app.services import recommendation_service as rs

router = APIRouter()


async def _resolve_location(db, value: str) -> Location:
    loc = (
        await db.execute(
            select(Location).where(
                (Location.name == value)
                | (Location.id.cast(String) == value)
            )
        )
    ).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="location tidak ditemukan")
    return loc


async def _resolve_commodity(db, value: str) -> Commodity:
    com = (
        await db.execute(
            select(Commodity).where(
                (Commodity.name == value)
                | (Commodity.id.cast(String) == value)
            )
        )
    ).scalar_one_or_none()
    if com is None:
        raise HTTPException(status_code=404, detail="commodity tidak ditemukan")
    return com


@router.get("/balance/{location}/{commodity}")
async def get_balance(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
):
    loc = await _resolve_location(db, location)
    com = await _resolve_commodity(db, commodity)
    from app.core.gaps import calculate_supply_gap

    row_supply = (
        await db.execute(
            select(SupplyRecord)
            .where(
                SupplyRecord.location_id == loc.id,
                SupplyRecord.commodity_id == com.id,
            )
            .order_by(SupplyRecord.recorded_at.desc(), SupplyRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    row_demand = (
        await db.execute(
            select(DemandRecord)
            .where(
                DemandRecord.location_id == loc.id,
                DemandRecord.commodity_id == com.id,
            )
            .order_by(DemandRecord.recorded_at.desc(), DemandRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row_supply is None and row_demand is None:
        raise HTTPException(
            status_code=404,
            detail="data supply/demand tidak ditemukan untuk pasangan ini",
        )
    supply = (
        Decimal(str(row_supply.quantity_kg))
        if row_supply is not None
        else Decimal("0")
    )
    demand = (
        Decimal(str(row_demand.quantity_kg))
        if row_demand is not None
        else Decimal("0")
    )
    gap = calculate_supply_gap(supply, demand)
    return {
        "location": loc.name,
        "commodity": com.name,
        "supply_kg": float(gap.supply_kg),
        "demand_kg": float(gap.demand_kg),
        "surplus_kg": float(gap.surplus_kg),
        "shortage_kg": float(gap.shortage_kg),
        "status": gap.status,
    }


class _AsyncFetcher:
    """Adapter async session → fetch_facts() awaitable untuk pipeline."""

    def __init__(self, db):
        self._db = db

    async def __call__(self):
        return await rs.fetch_operational_facts(self._db, None)


@router.post("/balance/recommend")
async def post_recommend(db: AsyncSession = Depends(get_db)):
    fetcher = _AsyncFetcher(db)
    try:
        out = await rs.build_recommendations(fetcher)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return out


@router.post("/balance/analyze")
async def post_analyze(db: AsyncSession = Depends(get_db)):
    """Pipeline penuh + ringkasan hitung (S3-02, carry-over Sprint 2).

    Tipis: rekomendasi dari service yang sama dengan /balance/recommend;
    summary murni agregasi hitung, tanpa logika baru.
    """
    fetcher = _AsyncFetcher(db)
    try:
        out = await rs.build_recommendations(fetcher)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    recs = out["recommendations"]
    out["summary"] = {
        "candidates_total": len(recs),
        "eligible": sum(1 for r in recs if r.get("eligible")),
        "review_required": sum(1 for r in recs if r.get("review_required")),
        "flagged_price": sum(
            1 for r in recs if (r.get("price_anomaly") or {}).get("flagged")
        ),
    }
    return out
