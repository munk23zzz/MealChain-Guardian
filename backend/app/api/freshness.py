"""Router freshness (Task 12) — tipis: validasi, ambil batch, panggil core, persist."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, require_roles
from app.api.dependencies import get_db
from app.core.config import settings
from app.core.freshness import classify_freshness, compute_freshness_score, compute_usable_until
from app.models import Batch, Commodity, User

router = APIRouter()

_SHELF_LIFE_BY_COMMODITY = {
    "telur": settings.shelf_life_days_telur,
    "ayam": settings.shelf_life_days_ayam,
    "wortel": settings.shelf_life_days_wortel,
}


class FreshnessRequest(BaseModel):
    batch_id: str
    as_of: datetime | None = None


@router.post("/freshness/evaluate")
async def evaluate_freshness(
    payload: FreshnessRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    batch = (
        await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")

    # as_of hanya boleh di-override dalam DEMO_MODE (plan Task 12)
    if payload.as_of is not None and not settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="as_of hanya boleh di-override dalam DEMO_MODE",
        )
    as_of = payload.as_of or datetime.now(batch.harvested_at.tzinfo)

    commodity_name = str(
        (
            await db.execute(
                select(Commodity.name).where(Commodity.id == batch.commodity_id)
            )
        ).scalar_one()
    )
    shelf_life_days = _SHELF_LIFE_BY_COMMODITY[commodity_name]
    score = compute_freshness_score(
        harvested_at=batch.harvested_at,
        as_of=as_of,
        shelf_life_days=shelf_life_days,
        temperature_log=batch.temperature_log or [],
        safe_min_c=0.0,
        safe_max_c=8.0,
    )
    status = classify_freshness(score)
    usable_until = compute_usable_until(
        harvested_at=batch.harvested_at,
        shelf_life_days=shelf_life_days,
        score=score,
    )

    batch.freshness_score = round(score, 2)
    batch.usable_until = usable_until
    await db.commit()

    return {
        "freshness_score": float(batch.freshness_score),
        "status": status,
        "usable_until": usable_until.isoformat(),
    }
