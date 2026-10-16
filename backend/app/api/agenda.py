"""GET /agenda — agenda harian tab "Hari Ini" (permintaan pemilik 2026-10-16).

Kontrak:
- `start`/`end` = tanggal ISO (YYYY-MM-DD), inklusif, diartikan sebagai HARI WIB.
- Rentang maksimum 62 hari (satu bulan kalender + margin); `end` sebelum `start`
  atau tanggal tak sah → 422.
- 200: envelope `period`, `scope`, `computed_at`, `days` (SATU entri per hari —
  kalender butuh deret tanpa lubang). Setiap bagian menulis `available: false`
  bila tak ada catatan, bukan nol yang tampak terukur.
- Cakupan: rencana/kiriman/limbah/pasokan/harga/keputusan ikut scope user
  (`app/core/scope.py`); batch lintas lokasi seperti GET /batches.
- Read murni: tanpa mutation, idempoten (kecuali `computed_at`).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import get_db
from app.models import User
from app.services.agenda_service import MAX_DAYS, compute_agenda

router = APIRouter(prefix="", tags=["agenda"])


@router.get("/agenda")
async def get_agenda(
    start: date = Query(..., description="tanggal awal (YYYY-MM-DD), hari WIB"),
    end: date = Query(..., description="tanggal akhir (YYYY-MM-DD), inklusif"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Agenda harian: rencana menu, kiriman, limbah, pasokan, harga, batch
    kedaluwarsa, dan keputusan per hari."""
    if end < start:
        raise HTTPException(status_code=422, detail="start harus <= end")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(
            status_code=422, detail=f"rentang maksimum {MAX_DAYS} hari"
        )
    return await compute_agenda(db, user, start, end)
