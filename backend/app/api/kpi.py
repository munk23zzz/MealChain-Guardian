"""S4-03: GET /kpi — agregasi KPI read-only (plan §11 baris KPI).

Kontrak:
- Required start/end RFC3339; optional location_id UUID.
- Omit scope = own location untuk SPPG, global untuk bgn_monitor.
- Max range 366 hari; invalid range/naive time 422; foreign scope 403.
- 200 envelope: period, scope, computed_at, data_source, metrics (tepat
  tujuh entri dari kpi_service). Read murni; tanpa mutation/provider.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import get_db
from app.models import User
from app.services.kpi_service import compute_kpis

router = APIRouter(prefix="", tags=["kpi"])

MAX_RANGE_DAYS = 366


@router.get("/kpi")
async def get_kpi(
    start: datetime = Query(...),
    end: datetime = Query(...),
    location_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """KPI tujuh metrik, state available/no_data/unavailable + reason.

    SPPG hanya scope lokasinya (403 foreign); bgn_monitor global atau
    lokasi mana pun (read-only). Naive timestamp ditolak 422 (kontrak
    RFC3339 dengan offset eksplisit).
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="start/end wajib RFC3339 dengan offset zona waktu",
        )
    if start >= end:
        raise HTTPException(status_code=422, detail="start harus < end")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"rentang maksimum {MAX_RANGE_DAYS} hari",
        )

    scope = str(user.location_id) if user.location_id else None
    if user.role == "bgn_monitor":
        scope = str(location_id) if location_id else None  # global bila omit
    else:
        if location_id is not None and str(location_id) != scope:
            raise HTTPException(
                status_code=403, detail="scope lokasi di luar otoritas Anda"
            )
        if scope is None:
            raise HTTPException(
                status_code=403,
                detail="user belum terikat lokasi — tidak bisa membaca KPI",
            )
        location_id = user.location_id

    metrics = await compute_kpis(db, start, end, location_id)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "scope": {
            "location_id": str(location_id) if location_id else None,
            "role": user.role,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "live_aggregate",
        "metrics": metrics,
    }
