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
from app.core.scope import assert_in_scope
from app.models import PriceSignal, Supplier, User

router = APIRouter()


@router.get("/price/quotes/{location}/{commodity}")
async def list_quotes(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Daftar supplier_quote + reference terkini (S4-01 UI Event 2).

    Read-only (semua role ter-autentikasi). Reference diambil pada
    lokasi/komoditas yang SAMA dengan quote — anti pencampuran lintas
    lokasi/period.
    """
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    quotes = (
        (
            await db.execute(
                select(PriceSignal)
                .where(
                    PriceSignal.location_id == loc.id,
                    PriceSignal.commodity_id == com.id,
                    PriceSignal.source == "supplier_quote",
                )
                .order_by(PriceSignal.recorded_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    ref = (
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
    supplier_names: dict = {}
    if quotes:
        sup_ids = [q.supplier_id for q in quotes if q.supplier_id is not None]
        if sup_ids:
            sup_rows = (
                await db.execute(
                    select(Supplier.id, Supplier.name).where(
                        Supplier.id.in_(sup_ids)
                    )
                )
            ).all()
            supplier_names = {sid: name for sid, name in sup_rows}
    out = {
        "location": loc.name,
        "location_id": str(loc.id),
        "commodity": com.name,
        "quotes": [
            {
                "id": str(q.id),
                "supplier_id": str(q.supplier_id) if q.supplier_id else None,
                "supplier_name": (
                    supplier_names.get(q.supplier_id)
                    if q.supplier_id is not None
                    else None
                ),
                "price_per_kg": float(q.price_per_kg),
                "recorded_at": q.recorded_at.isoformat(),
            }
            for q in quotes
        ],
        "reference": (
            {
                "id": str(ref.id),
                "price_per_kg": float(ref.price_per_kg),
                "recorded_at": ref.recorded_at.isoformat(),
            }
            if ref is not None
            else None
        ),
    }
    return out


@router.get("/price/{location}/{commodity}")
async def get_price(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
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
