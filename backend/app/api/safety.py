"""Router safety (Task 12) — status API uppercase, DB lowercase, tanpa override."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.safety import evaluate_safety
from app.models import Batch

router = APIRouter()


class SafetyRequest(BaseModel):
    batch_id: str


@router.post("/safety/evaluate")
async def evaluate_safety_endpoint(
    payload: SafetyRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    batch = (
        await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")

    result = evaluate_safety(
        temperature_log=batch.temperature_log or [],
        safe_min_c=settings.safe_temp_min_c,
        safe_max_c=settings.safe_temp_max_c,
    )

    # DB lowercase (kontrak Schema.md), API uppercase (kontrak Skill.md §5)
    batch.safety_status = str(result["safety_status"]).lower()
    await db.commit()

    return {
        "safety_status": str(result["safety_status"]).upper(),
        "reasons": list(result["reasons"]),
        "excursion_minutes": float(result["excursion_minutes"]),
    }
