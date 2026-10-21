"""Router safety (Task 12) — status API uppercase, DB lowercase, tanpa override."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, require_roles
from app.api.dependencies import get_db
from app.core.commodity_limits import safe_temp_for
from app.core.safety import evaluate_safety
from app.models import Batch, Commodity, User

router = APIRouter()


class SafetyRequest(BaseModel):
    batch_id: str


@router.post("/safety/evaluate")
async def evaluate_safety_endpoint(
    payload: SafetyRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    # Nama komoditas ikut dibaca: batas suhu aman berbeda per komoditas
    # (beras 15–30 °C, protein/sayur 0–8 °C) dan harus sama dengan freshness.
    baris = (
        await db.execute(
            select(Batch, Commodity.name)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .where(Batch.id == payload.batch_id)
        )
    ).one_or_none()
    if baris is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")
    batch, commodity_name = baris

    safe_min_c, safe_max_c = safe_temp_for(commodity_name)
    result = evaluate_safety(
        temperature_log=batch.temperature_log or [],
        safe_min_c=safe_min_c,
        safe_max_c=safe_max_c,
    )

    # DB lowercase (kontrak Schema.md), API uppercase (kontrak Skill.md §5)
    batch.safety_status = str(result["safety_status"]).lower()
    await db.commit()

    return {
        "safety_status": str(result["safety_status"]).upper(),
        "reasons": list(result["reasons"]),
        "excursion_minutes": float(result["excursion_minutes"]),
    }
