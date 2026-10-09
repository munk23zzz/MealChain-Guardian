"""Router /events (Sprint 4) — Event 2 price anomaly (plan §11).

Tipis: validasi + delegasi `event2_service`. Deterministik — angka hanya
dari `app.core.price` + DB. Mutating → sppg_head/sppg_nutritionist saja;
bgn_monitor read-only (O-SEC). Tanpa PO (O-PO).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, require_roles
from app.api.dependencies import get_db
from app.models import User
from app.services import event2_service as svc
from app.services.event2_service import Event2ConflictError, Event2NotFoundError

router = APIRouter()


class PriceAnomalyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote_id: uuid.UUID
    target_location_id: uuid.UUID
    operation_key: uuid.UUID


@router.post("/events/price-anomaly", status_code=201)
async def trigger_price_anomaly(
    payload: PriceAnomalyRequest,
    user: User = Depends(require_roles(*MUTATING_ROLES)),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """Event 2 — price anomaly (review-only; TANPA auto-PO).

    201: anomali terdeteksi → decision price_anomaly + evidence + trace.
    200: tidak ada anomali → decision_id null, tanpa write.
    409: operation_key sama dipakai untuk payload berbeda.
    """
    try:
        outcome = await svc.run_price_anomaly_event(
            quote_id=payload.quote_id,
            target_location_id=payload.target_location_id,
            operation_key=payload.operation_key,
            actor_id=str(user.id),
            db=db,
        )
    except Event2NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Event2ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if outcome.get("status") == "no_anomaly":
        # Kontrak §11: no-anomaly → 200 + decision_id null.
        if response is not None:
            response.status_code = 200
        return outcome
    return outcome


# ---------------------------------------------------------------------------
# Event 3 — safety disruption (plan §S4-02, prompt Owner §18–22)
# ---------------------------------------------------------------------------

from app.services import event3_service as svc3  # noqa: E402
from app.services.event3_service import (  # noqa: E402
    Event3ConflictError,
    Event3NoAlternativeError,
)


class SafetyDisruptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: uuid.UUID
    target_location_id: uuid.UUID
    operation_key: uuid.UUID
    previous_decision_id: uuid.UUID | None = None


@router.post("/events/safety-disruption", status_code=201)
async def trigger_safety_disruption(
    payload: SafetyDisruptionRequest,
    user: User = Depends(require_roles(*MUTATING_ROLES)),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """Event 3 — safety disruption (deterministik; TANPA override client).

    201: batch FAIL → exclude → alternatif eligible → decision
         safety_disruption + evidence temperature + trace DETECT/OPTIMIZE.
    200: batch aman (no_disruption) → decision_id null, tanpa decision.
    409: operation_key dipakai batch lain / tidak ada alternatif eligible.
    404: batch tidak ditemukan.
    Safety dihitung server-side dari temperature_log persisted (core
    Sprint 1, ambang 30 menit terkunci) — bukan dari payload browser.
    """
    try:
        outcome = await svc3.run_safety_disruption_event(
            batch_id=payload.batch_id,
            target_location_id=payload.target_location_id,
            operation_key=payload.operation_key,
            previous_decision_id=payload.previous_decision_id,
            actor_id=str(user.id),
            db=db,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Event3ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Event3NoAlternativeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if outcome.get("status") == "no_disruption":
        # Batch aman → 200 + decision_id null (idem Event 2 no-anomaly).
        if response is not None:
            response.status_code = 200
    return outcome
