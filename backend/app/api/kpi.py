"""S4-03 + periode server: GET /kpi — agregasi KPI read-only (plan §11 baris KPI).

Kontrak:
- Pilih SALAH SATU: `periode=today|7d|1bulan` (dihitung SERVER, hari kalender
  Asia/Jakarta) ATAU `start`+`end` RFC3339 eksplisit.
- Optional location_id UUID.
- Omit scope = own location untuk SPPG, global untuk bgn_monitor.
- Max range 366 hari; invalid range/naive time 422; foreign scope 403.
- 200 envelope: period (key/label/timezone/start/end), scope, computed_at,
  data_source, metrics (tepat tujuh entri dari kpi_service). Read murni.

Periode dihitung di sini, bukan di klien: satu tombol "hari ini" harus berarti
satu rentang yang sama untuk semua kartu. Client hanya mengirim kunci periode.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.kpi_period import LABEL_PERIODE, PERIODE_KPI, ZONA_KPI, resolve_periode
from app.db import get_db
from app.models import User
from app.services.kpi_service import compute_kpis

router = APIRouter(prefix="", tags=["kpi"])

MAX_RANGE_DAYS = 366


@router.get("/kpi")
async def get_kpi(
    periode: str | None = Query(
        None,
        description=(
            "Kunci periode yang dihitung server (Asia/Jakarta): "
            + " | ".join(PERIODE_KPI)
            + ". Tidak boleh dikirim bersama start/end."
        ),
    ),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    location_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """KPI tujuh metrik, state available/no_data/unavailable + reason.

    SPPG hanya scope lokasinya (403 foreign); bgn_monitor global atau
    lokasi mana pun (read-only). Naive timestamp ditolak 422 (kontrak
    RFC3339 dengan offset eksplisit).
    """
    kunci: str | None = None
    label: str | None = None

    if periode is not None:
        if start is not None or end is not None:
            raise HTTPException(
                status_code=422,
                detail="kirim periode ATAU start+end, bukan keduanya",
            )
        if periode not in PERIODE_KPI:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"periode tidak dikenal: {periode!r}; pilihan: "
                    + ", ".join(PERIODE_KPI)
                ),
            )
        start, end = resolve_periode(periode, datetime.now(timezone.utc))
        kunci, label = periode, LABEL_PERIODE[periode]
    else:
        if start is None or end is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "wajib mengirim periode=("
                    + "|".join(PERIODE_KPI)
                    + "), atau start dan end sekaligus"
                ),
            )
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
        "period": {
            "key": kunci,
            "label": label,
            "timezone": str(ZONA_KPI),
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "scope": {
            "location_id": str(location_id) if location_id else None,
            "role": user.role,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "live_aggregate",
        "metrics": metrics,
    }
