"""Sinkronisasi rute JALAN (OSRM) ke tabel cache `road_routes`.

Kapan jalan: **saat seeding/sync**, bukan saat peta dibuka (keputusan
pemilik 2026-10-16). Karena itu modul ini yang menyentuh jaringan, sedangkan
`app/core/road_route.py` tetap murni dan bisa diuji tanpa kabel.

Dua hal yang dihemat di sini:
- Hanya batch **masih layak** (`usable_until >= now`) yang diambil rutenya —
  kiriman kedaluwarsa tidak pernah digambar, jadi meminta rutenya cuma
  membebani server OSRM demo tanpa hasil.
- Kunci yang sudah ada di cache dilewati, dan pemasok→tujuan yang sama hanya
  dipanggil sekali walau ada beberapa batch (`plan_route_sync`).

Kalau OSRM tidak terjangkau, sinkronisasi TIDAK menggagalkan seeding: ia
melaporkan jumlah gagal + alasannya, dan peta akan mengatakan "belum
disinkronkan" untuk rute itu. Yang tidak boleh terjadi adalah garis karangan.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.road_route import (
    ALASAN_LAYANAN_TIDAK_TERJANGKAU,
    ALASAN_RESPONS_TIDAK_DIKENAL,
    PROFIL_DEFAULT,
    RoadRouteError,
    osrm_url,
    parse_osrm_route,
    plan_route_sync,
    route_key,
)
from app.models.batches import Batch
from app.models.locations import Location
from app.models.road_routes import RoadRoute
from app.models.suppliers import Supplier

OSRM_BASE_URL_DEFAULT = "https://router.project-osrm.org"

# Server demo OSRM diminta baik-baik: ada UA yang bisa dihubungi kalau ada masalah.
_USER_AGENT = "MealChainGuardian/1.0 (sinkronisasi rute demo; kontak: tim proyek)"


def http_fetcher(url: str, timeout: float = 20.0) -> Any:
    """Ambil JSON dari OSRM (dipakai sebagai `fetcher` default)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL dari config, bukan input user)
        return json.loads(resp.read().decode("utf-8"))


def sync_requests(
    rows: list[dict], profil: str = PROFIL_DEFAULT
) -> list[dict]:
    """Baris (pemasok → tujuan) menjadi permintaan rute unik. Murni.

    Baris tanpa koordinat salah satu ujungnya DILEWATI: rute tidak bisa
    digambar, dan mengarang titik pengganti = menyesatkan peta.
    """
    out: list[dict] = []
    for row in rows:
        lat_a, lon_a = row.get("origin_lat"), row.get("origin_lon")
        lat_b, lon_b = row.get("destination_lat"), row.get("destination_lon")
        if None in (lat_a, lon_a, lat_b, lon_b):
            continue
        out.append(
            {
                "key": route_key(lat_a, lon_a, lat_b, lon_b, profil),
                "profil": profil,
                "origin_lat": float(lat_a),
                "origin_lon": float(lon_a),
                "destination_lat": float(lat_b),
                "destination_lon": float(lon_b),
                "batch_id": str(row.get("batch_id")) if row.get("batch_id") else None,
                "nama": row.get("supplier_name"),
            }
        )
    return out


async def batch_route_rows(
    db: AsyncSession, now: datetime, semua_batch: bool = False
) -> list[dict]:
    """Baris batch + koordinat kedua ujungnya (pemasok → lokasi tujuan)."""
    stmt = (
        select(
            Batch.id.label("batch_id"),
            Batch.usable_until,
            Supplier.name.label("supplier_name"),
            Supplier.latitude.label("origin_lat"),
            Supplier.longitude.label("origin_lon"),
            Location.name.label("destination_name"),
            Location.latitude.label("destination_lat"),
            Location.longitude.label("destination_lon"),
        )
        .join(Supplier, Supplier.id == Batch.supplier_id)
        .outerjoin(Location, Location.id == Batch.location_id)
    )
    if not semua_batch:
        stmt = stmt.where(Batch.usable_until >= now)
    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.all()]


async def sync_road_routes(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
    fetcher: Optional[Callable[[str], Any]] = None,
    base_url: str = OSRM_BASE_URL_DEFAULT,
    timeout: float = 20.0,
    profil: str = PROFIL_DEFAULT,
    semua_batch: bool = False,
    rows: Optional[list[dict]] = None,
) -> dict:
    """Isi `road_routes` untuk kiriman aktif. Laporan apa adanya, idempoten.

    `rows` bisa disuntikkan (dipakai tes supaya tidak menyentuh kunci cache
    asli); kalau None, barisnya dibaca dari DB.
    """
    now = now or datetime.now(UTC)
    fetch = fetcher or (lambda url: http_fetcher(url, timeout))

    if rows is None:
        rows = await batch_route_rows(db, now, semua_batch=semua_batch)

    requests = sync_requests(rows, profil)
    keys = {r["key"] for r in requests}
    cached: set[str] = set()
    if keys:
        cached = set(
            (await db.execute(select(RoadRoute.route_key).where(RoadRoute.route_key.in_(keys))))
            .scalars()
            .all()
        )

    rencana = plan_route_sync(requests, cached)
    diambil = 0
    alasan_gagal: dict[str, int] = {}
    rincian_gagal: list[dict] = []

    for req in rencana["perlu_diambil"]:
        url = osrm_url(
            base_url,
            req["origin_lat"],
            req["origin_lon"],
            req["destination_lat"],
            req["destination_lon"],
            req["profil"],
        )
        try:
            payload = await asyncio.to_thread(fetch, url)
            urai = parse_osrm_route(payload)
        except RoadRouteError as err:
            alasan_gagal[err.reason] = alasan_gagal.get(err.reason, 0) + 1
            rincian_gagal.append(
                {"key": req["key"], "nama": req["nama"], "alasan": err.reason, "detail": err.detail}
            )
            continue
        except Exception as err:  # jaringan mati, timeout, DNS, HTTP error
            alasan = (
                ALASAN_LAYANAN_TIDAK_TERJANGKAU
                if isinstance(err, (urllib.error.URLError, TimeoutError, OSError))
                else ALASAN_RESPONS_TIDAK_DIKENAL
            )
            alasan_gagal[alasan] = alasan_gagal.get(alasan, 0) + 1
            rincian_gagal.append(
                {
                    "key": req["key"],
                    "nama": req["nama"],
                    "alasan": alasan,
                    "detail": f"{type(err).__name__}: {err}",
                }
            )
            continue

        db.add(
            RoadRoute(
                route_key=req["key"],
                profile=req["profil"],
                origin_lat=req["origin_lat"],
                origin_lon=req["origin_lon"],
                destination_lat=req["destination_lat"],
                destination_lon=req["destination_lon"],
                distance_m=urai["distance_m"],
                duration_s=urai["duration_s"],
                geometry=urai["geometry"],
                source=urai["source"],
                fetched_at=now,
            )
        )
        diambil += 1

    await db.commit()

    return {
        "diperiksa": len(requests),
        "sudah_ada": rencana["sudah_ada"],
        "duplikat": rencana["duplikat"],
        "diambil": diambil,
        "gagal": sum(alasan_gagal.values()),
        "alasan_gagal": alasan_gagal,
        "rincian_gagal": rincian_gagal,
        "sumber_rute": base_url,
        "hanya_kiriman_aktif": not semua_batch,
    }
