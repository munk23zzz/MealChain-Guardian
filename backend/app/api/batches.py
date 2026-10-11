"""Endpoint batch read-only (P4 chaos panel — keputusan Roy 2026-10-09).

GET /batches — daftar batch (id, kode, lokasi, komoditas, safety status,
temperature ringkas) untuk dipilih di panel chaos Event 3. Read-only,
semua role terautentikasi. TIDAK mengekspos kolom sensitif tambahan.
"""


from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models import Batch, Commodity, Location
from app.models.users import User

router = APIRouter(prefix="", tags=["batches"])


@router.get("/batches")
async def list_batches(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Daftar batch untuk panel chaos Event 3.

    CATATAN audit 2026-10-11: daftar ini sengaja lintas lokasi (batch source
    chaos bisa berada di lokasi mana pun) — kalau O-SEC-2 dikunci untuk
    /events/*, daftar ini juga wajib di-scope, dan panel akan kosong untuk
    SPPG Head di Jakarta (seed tidak punya batch Jakarta).
    """
    query = (
        select(
            Batch.id,
            Batch.quantity_kg,
            Batch.safety_status,
            Batch.freshness_score,
            Batch.usable_until,
            Batch.location_id,
            Location.name.label("location"),
            Commodity.name.label("commodity"),
        )
        .join(Location, Location.id == Batch.location_id)
        .join(Commodity, Commodity.id == Batch.commodity_id)
        .order_by(Batch.created_at.desc())
        .limit(50)
    )
    rows = (await db.execute(query)).all()
    return {
        "batches": [
            {
                "id": str(r.id),
                "location": r.location,
                "location_id": str(r.location_id),
                "commodity": r.commodity,
                "quantity_kg": float(r.quantity_kg),
                "safety_status": r.safety_status,
                "freshness_score": (
                    float(r.freshness_score) if r.freshness_score is not None else None
                ),
                "usable_until": r.usable_until.isoformat() if r.usable_until else None,
            }
            for r in rows
        ]
    }
