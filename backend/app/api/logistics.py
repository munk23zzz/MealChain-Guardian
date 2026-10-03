"""Router logistics (Task 12) — estimasi deterministik via core."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logistics import LOCATIONS, estimate_logistics

router = APIRouter()


class LogisticsRequest(BaseModel):
    source: str
    target: str
    quantity_kg: float = Field(gt=0)
    delivery_window_min: float | None = Field(default=None, ge=0)


@router.post("/logistics/estimate")
async def post_logistics_estimate(payload: LogisticsRequest) -> dict:
    if payload.source not in LOCATIONS or payload.target not in LOCATIONS:
        raise HTTPException(status_code=404, detail="lokasi tidak dikenal")
    try:
        result = estimate_logistics(
            source=payload.source,
            target=payload.target,
            quantity_kg=payload.quantity_kg,
            delivery_window_min=payload.delivery_window_min,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "distance_km": int(result["distance_km"]),
        "estimated_time_min": float(result["estimated_time_min"]),
        "feasible": bool(result["feasible"]),
    }
