"""Router supply (Task 11) — tipis: validasi, ambil data, panggil terbaru."""

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import String, case, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.scope import assert_in_scope
from app.models import Commodity, Location, SupplyRecord, User

router = APIRouter()

_SOURCE_PRECEDENCE = {"mock_sap": 0, "manual": 1, "sensor": 2}


def _source_order_expr():
    """Precedence source sebagai ekspresi SQL (mock > manual > sensor > lainnya)."""
    return case(_SOURCE_PRECEDENCE, value=SupplyRecord.source, else_=99)


async def _resolve_location(db: AsyncSession, value: str) -> Location:
    loc = (
        await db.execute(
            select(Location).where(
                (Location.name == value) | (cast(Location.id, String) == value)
            )
        )
    ).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="location tidak ditemukan")
    return loc


async def _resolve_commodity(db: AsyncSession, value: str) -> Commodity:
    com = (
        await db.execute(
            select(Commodity).where(
                (Commodity.name == value) | (cast(Commodity.id, String) == value)
            )
        )
    ).scalar_one_or_none()
    if com is None:
        raise HTTPException(status_code=404, detail="commodity tidak ditemukan")
    return com


@router.get("/supply/{location}/{commodity}")
async def get_supply(
    location: str,
    commodity: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    x_data_source: str | None = Header(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    record = (
        await db.execute(
            select(SupplyRecord)
            .where(
                SupplyRecord.location_id == loc.id,
                SupplyRecord.commodity_id == com.id,
            )
            .order_by(
                SupplyRecord.recorded_at.desc(),
                _source_order_expr(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="supply tidak ditemukan")
    response.headers["X-Data-Source"] = "MOCK" if record.source == "mock_sap" else "LIVE"
    return {
        "quantity_kg": float(record.quantity_kg),
        "recorded_at": record.recorded_at.isoformat(),
        "source": record.source,
    }
