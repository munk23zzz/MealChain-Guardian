"""Router balance (Task 10 Sprint 2) — tipis: validasi + delegasi service."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.core.scope import apply_location_scope, assert_in_scope
from app.models import (
    Commodity,
    DemandRecord,
    Location,
    SupplyRecord,
    User,
)
from app.services import recommendation_service as rs

router = APIRouter()


async def _resolve_location(db, value: str) -> Location:
    loc = (
        await db.execute(
            select(Location).where(
                (Location.name == value)
                | (Location.id.cast(String) == value)
            )
        )
    ).scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=404, detail="location tidak ditemukan")
    return loc


async def _resolve_commodity(db, value: str) -> Commodity:
    com = (
        await db.execute(
            select(Commodity).where(
                (Commodity.name == value)
                | (Commodity.id.cast(String) == value)
            )
        )
    ).scalar_one_or_none()
    if com is None:
        raise HTTPException(status_code=404, detail="commodity tidak ditemukan")
    return com


@router.get("/balance/{location}/{commodity}")
async def get_balance(
    location: str,
    commodity: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    from app.core.gaps import calculate_supply_gap

    row_supply = (
        await db.execute(
            select(SupplyRecord)
            .where(
                SupplyRecord.location_id == loc.id,
                SupplyRecord.commodity_id == com.id,
            )
            .order_by(SupplyRecord.recorded_at.desc(), SupplyRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    row_demand = (
        await db.execute(
            select(DemandRecord)
            .where(
                DemandRecord.location_id == loc.id,
                DemandRecord.commodity_id == com.id,
            )
            .order_by(DemandRecord.recorded_at.desc(), DemandRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row_supply is None and row_demand is None:
        raise HTTPException(
            status_code=404,
            detail="data supply/demand tidak ditemukan untuk pasangan ini",
        )
    supply = (
        Decimal(str(row_supply.quantity_kg))
        if row_supply is not None
        else Decimal("0")
    )
    demand = (
        Decimal(str(row_demand.quantity_kg))
        if row_demand is not None
        else Decimal("0")
    )
    gap = calculate_supply_gap(supply, demand)
    return {
        "location": loc.name,
        "commodity": com.name,
        "supply_kg": float(gap.supply_kg),
        "demand_kg": float(gap.demand_kg),
        "surplus_kg": float(gap.surplus_kg),
        "shortage_kg": float(gap.shortage_kg),
        "status": gap.status,
    }


class _AsyncFetcher:
    """Adapter async session → fetch_facts() awaitable untuk pipeline."""

    def __init__(self, db):
        self._db = db

    async def __call__(self):
        return await rs.fetch_operational_facts(self._db, None)


@router.post("/balance/recommend")
async def post_recommend(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    fetcher = _AsyncFetcher(db)
    try:
        out = await rs.build_recommendations(fetcher)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return out


class AnalyzeRequest(BaseModel):
    """Body opsional /balance/analyze (ruling S4-05 p10).

    `commodity` = filter pipeline ke 1 komoditas (mengikuti panel).
    Tidak dikirim = perilaku lama (global). `location` TIDAK memfilter
    supply/demand — rantai pasok lintas wilayah by design (Sprint 2/3).
    """

    model_config = ConfigDict(extra="forbid")

    commodity: str | None = None


@router.get("/balance/map")
async def get_balance_map(
    commodity: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """S4-06 polish (arah Roy 2026-10-08): kondisi semua lokasi utk map.

    Read-only (JWT, semua role boleh baca). Satu komoditas → snapshot
    supply/demand TERBARU tiap lokasi (record terakhir per lokasi,
    aturan sama dengan GET /balance/{loc}/{com}), gap via
    `calculate_supply_gap` — formula yang sama dengan panel, tanpa
    rumus kedua. Lokasi tanpa data → zeros (map tetap lengkap).
    Koordinat dari DB.
    """
    com = await _resolve_commodity(db, commodity)
    # Ruling 2026-10-14: peran SPPG hanya menerima lokasinya sendiri;
    # bgn_monitor tetap menerima seluruh lokasi (pengawasan nasional).
    locs = (
        (
            await db.execute(
                apply_location_scope(
                    select(Location).order_by(Location.name.asc()), Location.id, user
                )
            )
        )
        .scalars()
        .all()
    )

    async def _latest_by_location(model, ids: list):
        if not ids:
            return {}
        rows = (
            (
                await db.execute(
                    select(model)
                    .where(model.commodity_id == com.id)
                    .order_by(
                        model.location_id.asc(),
                        model.recorded_at.desc(),
                        model.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        out: dict = {}
        for r in rows:
            if r.location_id not in out:
                out[r.location_id] = r
        return out

    from app.core.gaps import calculate_supply_gap

    sup_by_loc = await _latest_by_location(
        SupplyRecord, [loc.id for loc in locs]
    )
    dem_by_loc = await _latest_by_location(
        DemandRecord, [loc.id for loc in locs]
    )

    items = []
    for loc in locs:
        s_row, d_row = sup_by_loc.get(loc.id), dem_by_loc.get(loc.id)
        supply = (
            Decimal(str(s_row.quantity_kg))
            if s_row is not None
            else Decimal("0")
        )
        demand = (
            Decimal(str(d_row.quantity_kg))
            if d_row is not None
            else Decimal("0")
        )
        gap = calculate_supply_gap(supply, demand)
        items.append(
            {
                "location": loc.name,
                "region": loc.region,
                "latitude": float(loc.latitude) if loc.latitude is not None else None,
                "longitude": float(loc.longitude) if loc.longitude is not None else None,
                "supply_kg": float(gap.supply_kg),
                "demand_kg": float(gap.demand_kg),
                "surplus_kg": float(gap.surplus_kg),
                "shortage_kg": float(gap.shortage_kg),
                "status": gap.status,
            }
        )
    return {"commodity": com.name, "locations": items}


@router.post("/balance/analyze")
async def post_analyze(
    payload: AnalyzeRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    """Pipeline penuh + ringkasan hitung (S3-02, carry-over Sprint 2).

    Tipis: rekomendasi dari service yang sama dengan /balance/recommend;
    summary murni agregasi hitung, tanpa logika baru.
    Ruling S4-05: `commodity` (opsional) memfilter pipeline ke komoditas
    panel; tanpa body → global (perilaku lama, kompatibilitas).
    """
    commodity = (payload.commodity if payload else None) or None
    fetcher = _AsyncFetcher(db)
    try:
        out = await rs.build_recommendations(fetcher, commodity=commodity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    recs = out["recommendations"]
    out["summary"] = {
        "candidates_total": len(recs),
        "eligible": sum(1 for r in recs if r.get("eligible")),
        "review_required": sum(1 for r in recs if r.get("review_required")),
        "flagged_price": sum(
            1 for r in recs if (r.get("price_anomaly") or {}).get("flagged")
        ),
    }
    if commodity:
        out["filtered_by"] = {"commodity": commodity}
    return out
