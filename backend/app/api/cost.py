"""Router cost (S3-02) — SDC standalone endpoint (carry-over Sprint 2).

Tipis: validasi + delegasi penuh ke core.safe_delivered_cost (Opsi A
terkunci). FAIL ditolak sebelum perhitungan (422), tanpa eksepsi bocor.
"""

from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)

router = APIRouter()


class SafeDeliveredRequest(BaseModel):
    purchase_cost: Decimal
    transport_cost: Decimal = Decimal("0")
    handling_cost: Decimal = Decimal("0")
    freshness_score: Decimal = Field(ge=0, le=1)
    safety_status: str


@router.post("/cost/safe-delivered")
async def post_safe_delivered(payload: SafeDeliveredRequest) -> dict:
    try:
        result = calculate_safe_delivered_cost(
            SafeDeliveredCostInputs(
                purchase_cost=payload.purchase_cost,
                transport_cost=payload.transport_cost,
                handling_cost=payload.handling_cost,
                freshness_score=payload.freshness_score,
                safety_status=payload.safety_status,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "purchase_cost": str(result.purchase_cost),
        "transport_cost": str(result.transport_cost),
        "handling_cost": str(result.handling_cost),
        "expected_loss": str(result.expected_loss),
        "freshness_risk_penalty": str(result.freshness_risk_penalty),
        "safety_risk_penalty": str(result.safety_risk_penalty),
        "total": str(result.total),
    }
