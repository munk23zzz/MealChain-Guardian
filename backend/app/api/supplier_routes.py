"""Rute JALAN kiriman (pemasok → tujuan) untuk garis di peta (Fase 10).

Keputusan pemilik 2026-10-16: garis di peta mengikuti **jalan** (OSRM), bukan
garis lurus, dan tambahan kiriman demo ke SPPG Jakarta supaya jalurnya terlihat
di peta SPPG Jakarta.

Endpoint ini **tidak menghubungi jaringan**: geometrinya dibaca dari cache
`road_routes` yang sudah diisi saat sinkronisasi
(`app/seed/road_routes.py`). Kalau rute belum ada di cache, jawabannya tetap
kiriman itu tapi dengan `road = null` + `road_missing_reason` — peta lalu
menuliskan "belum disinkronkan", bukan menggambar garis yang tidak pernah
dihitung.

Cakupan (Ruling 2026-10-14, logika sama seperti endpoint armada lain): kiriman
adalah data sisi **tujuan**, jadi peran yang terikat lokasi (kepala SPPG) hanya
melihat kiriman yang menuju SPPG-nya; `bgn_monitor`/peran tanpa lokasi melihat
seluruh kiriman aktif. Filter `location=` TIDAK bisa menembus cakupan itu —
cakupan server selalu menang, sama seperti di `GET /suppliers`.
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.road_route import SUMBER_OSRM, build_route_payloads, route_key
from app.models import Batch, Commodity, Location, RoadRoute, Supplier

router = APIRouter()


async def _read_cache(db: AsyncSession, keys: set[str]) -> dict[str, dict]:
    """Baca cache rute untuk kunci yang dibutuhkan (satu query, bukan per baris)."""
    if not keys:
        return {}
    rows = (
        (await db.execute(select(RoadRoute).where(RoadRoute.route_key.in_(keys))))
        .scalars()
        .all()
    )
    return {
        row.route_key: {
            "distance_m": row.distance_m,
            "duration_s": row.duration_s,
            "geometry": row.geometry,
            "source": row.source,
            "fetched_at": row.fetched_at,
        }
        for row in rows
    }


def _keys_for(shipments: list[dict]) -> set[str]:
    """Kunci cache untuk kiriman yang kedua ujungnya punya koordinat."""
    keys: set[str] = set()
    for s in shipments:
        origin, dest = s.get("origin") or {}, s.get("destination") or {}
        if None in (
            origin.get("latitude"),
            origin.get("longitude"),
            dest.get("latitude"),
            dest.get("longitude"),
        ):
            continue
        keys.add(
            route_key(
                float(origin["latitude"]),
                float(origin["longitude"]),
                float(dest["latitude"]),
                float(dest["longitude"]),
            )
        )
    return keys


async def _location_name(db: AsyncSession, location_id: Optional[uuid.UUID]) -> Optional[str]:
    if location_id is None:
        return None
    return (
        await db.execute(select(Location.name).where(Location.id == location_id))
    ).scalar_one_or_none()


@router.get("/supplier-routes")
async def list_supplier_routes(
    commodity: Optional[str] = Query(None, description="nama komoditas, mis. telur"),
    location: Optional[str] = Query(
        None,
        description=(
            "nama lokasi TUJUAN (kiriman adalah data sisi tujuan). Diabaikan bila "
            "peran user terikat lokasi — cakupan user selalu menang."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    reference_time: Optional[datetime] = Query(
        None,
        description=(
            "ISO 8601. Kiriman dianggap aktif bila `usable_until >= ` waktu ini. "
            "Default: sekarang. Dipakai untuk meniru keadaan demo pada tanggal lain."
        ),
    ),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kiriman aktif + geometri rute jalan (bila sudah ada di cache)."""
    now = reference_time or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    stmt = (
        select(
            Batch.quantity_kg,
            Batch.usable_until,
            Batch.safety_status,
            Supplier.id.label("supplier_id"),
            Supplier.name.label("supplier_name"),
            Supplier.latitude.label("origin_lat"),
            Supplier.longitude.label("origin_lon"),
            Location.id.label("location_id"),
            Location.name.label("destination_name"),
            Location.latitude.label("dest_lat"),
            Location.longitude.label("dest_lon"),
            Commodity.name.label("commodity"),
        )
        .join(Supplier, Supplier.id == Batch.supplier_id)
        .outerjoin(Location, Location.id == Batch.location_id)
        .outerjoin(Commodity, Commodity.id == Batch.commodity_id)
        .where(Batch.usable_until >= now)
    )

    user_location_id = getattr(user, "location_id", None)
    if user_location_id is not None:
        stmt = stmt.where(Batch.location_id == user_location_id)
        scope = "lokasi user"
    else:
        scope = "nasional"
        if location:
            stmt = stmt.where(func.lower(Location.name) == location.strip().lower())

    if commodity:
        stmt = stmt.where(func.lower(Commodity.name) == commodity.strip().lower())

    rows = (await db.execute(stmt.order_by(Batch.usable_until.desc()).limit(limit))).all()

    shipments = [
        {
            "batch_id": None,
            "supplier_id": row.supplier_id,
            "supplier_name": row.supplier_name,
            "origin": {
                "latitude": float(row.origin_lat) if row.origin_lat is not None else None,
                "longitude": float(row.origin_lon) if row.origin_lon is not None else None,
                "name": row.supplier_name,
            },
            "destination_id": row.location_id,
            "destination_name": row.destination_name or "Tanpa lokasi",
            "destination": {
                "latitude": float(row.dest_lat) if row.dest_lat is not None else None,
                "longitude": float(row.dest_lon) if row.dest_lon is not None else None,
                "name": row.destination_name,
            },
            "commodity": row.commodity,
            "quantity_kg": float(row.quantity_kg) if row.quantity_kg is not None else None,
            "usable_until": row.usable_until,
            "safety_status": row.safety_status,
        }
        for row in rows
    ]

    cache = await _read_cache(db, _keys_for(shipments))
    hasil = build_route_payloads(shipments, cache)
    routes = hasil["routes"]

    return {
        "routes": routes,
        "summary": {
            "routes": len(routes),
            "with_road": sum(1 for r in routes if r["road"] is not None),
            "without_road": sum(1 for r in routes if r["road"] is None),
            "dilewati_tanpa_koordinat": hasil["dilewati_tanpa_koordinat"],
            "active_only": True,
            "scope": scope,
            "reference_location": await _location_name(db, user_location_id),
            "reference_time": now.isoformat(),
            "road_source": SUMBER_OSRM,
        },
    }
