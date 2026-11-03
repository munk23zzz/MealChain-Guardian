"""Router demand + forecast (Task 11).

CATATAN URUTAN: router forecast terdaftar SEBELUM router demand generik
(`/demand/{location}` dapat menangkap "forecast" sebagai path param).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.balance import _batas_waktu
from app.api.dependencies import get_db
from app.api.supply import _resolve_commodity, _resolve_location
from app.core.scope import assert_in_scope
from app.models import DemandRecord, User
from app.services.forecast_service import forecast_kebutuhan

router = APIRouter()
forecast_router = APIRouter()


class DemandResponse(BaseModel):
    quantity_kg: float
    needed_by: str


class ForecastResponse(BaseModel):
    forecast_qty_kg: float | None = None
    method: str
    confidence: float | None = None
    #: Sumber angka, eksplisit untuk juri: "SAP-RPT-1.6" atau "statistical_fallback".
    source: str = "statistical_fallback"
    #: True bila provider utama gagal/tak terbaca dan rantai turun ke statistik.
    fallback_used: bool = True
    #: Alasan bila cadangan dipakai (riwayat tipis, breaker, batas panggilan, …).
    reason: str | None = None
    sample_count: int = 0
    cache_hit: bool = False


@forecast_router.get("/demand/forecast/{location}/{commodity}")
async def get_demand_forecast(
    location: str,
    commodity: str,
    horizon_days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ForecastResponse:
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    # Perkiraan hanya boleh dibentuk dari catatan yang SUDAH TERJADI: baris
    # bertanggal masa depan bukan riwayat, dan batasnya sama dengan /balance
    # supaya angkanya sejalan. Jendela riwayat + ambang minimum + cache ada di
    # `services/forecast_service` — satu-satunya tempat yang memanggil model.
    hasil = await forecast_kebutuhan(
        db,
        location_id=loc.id,
        commodity_id=com.id,
        horizon_days=horizon_days,
        batas=_batas_waktu(None),
    )
    if hasil.qty_kg is None:
        raise HTTPException(
            status_code=404, detail=hasil.reason or "demand history tidak ditemukan"
        )
    return ForecastResponse(**hasil.as_dict(), reason=hasil.reason)


@router.get("/demand/{location}/{commodity}")
async def get_demand(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DemandResponse:
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    # Batas waktu SAMA dengan /balance: kondisi "kini" tidak boleh berasal dari
    # baris masa depan. Lihat catatan di /balance/{loc}/{com}.
    batas = _batas_waktu(None)
    record = (
        await db.execute(
            select(DemandRecord)
            .where(
                DemandRecord.location_id == loc.id,
                DemandRecord.commodity_id == com.id,
                DemandRecord.recorded_at <= batas,
            )
            .order_by(DemandRecord.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="demand tidak ditemukan")
    return DemandResponse(
        quantity_kg=float(record.quantity_kg),
        needed_by=record.needed_by.isoformat(),
    )
