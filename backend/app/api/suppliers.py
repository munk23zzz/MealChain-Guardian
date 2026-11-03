"""Daftar pemasok untuk peta & halaman Pemasok (Fase 2, Fase 7b).

Sebelum ini backend TIDAK punya endpoint daftar pemasok, sehingga halaman
"Pemasok" frontend terpaksa menyusun daftarnya dari pemasok yang kebetulan
muncul pada keputusan terakhir (`frontend/lib/suppliers-board.ts` menuliskan
keterbatasan itu di komentar). Endpoint ini menghapus keterbatasan tersebut.

Cakupan (Ruling 2026-10-14 §4): pemasok adalah data sisi SUMBER, sama seperti
`GET /batches` - boleh dibaca semua peran yang sudah login, lintas lokasi.
Yang dikunci per lokasi adalah KEPUTUSAN/eksklusi yang menyebut pemasok itu,
bukan profil pemasoknya. Tiap baris tetap membawa `excluded_scope_locations`
supaya UI bisa menyatakan "dikecualikan di <lokasi>" tanpa berpura-pura bahwa
eksklusi bersifat nasional (eksklusi memang lokal-cakupan).

Jarak & "terjangkau" (Fase 7b, keputusan pemilik 2026-10-15):

- `distance_km` = jarak pemasok dari SATU titik rujukan. Titik itu: lokasi user
  bila user terikat lokasi (peran SPPG) - jadi UI bisa menulis "jarak dari SPPG
  Anda"; untuk `bgn_monitor` (tanpa lokasi) rujukannya hub pada filter
  `location=`; bila tidak ada keduanya, `distance_km` = null dan
  `distance_reference` = null. Lokasi user SELALU menang atas filter `location=`.
- `max_distance_km` = penyaring RELEVANSI, bukan scope: semua peran tetap boleh
  membaca lintas lokasi. Karena itu penyaring ini hanya bekerja bila ADA titik
  rujukan; tanpa rujukan jawabannya 422 - bukan diam-diam mengembalikan seluruh
  tabel seolah penyaringnya berlaku.
- Baris tanpa koordinat TIDAK dianggap "dalam jangkauan": saat penyaring aktif ia
  dikeluarkan dan dihitung terpisah di `reach.excluded_unknown_distance` (jujur:
  tidak bisa dibuktikan dekat, jadi tidak diklaim dekat).

Penyaringan dilakukan di Python setelah baris dibaca, karena jarak dihitung dari
koordinat per baris; ukuran tabel pemasok kecil (35 baris) dan itu disengaja -
`total` karena itu berarti "jumlah SETELAH penyaringan", bukan jumlah tabel.
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.geo import haversine_km
from app.core.supplier_shipping import shipping_for, shipping_summary
from app.models import Batch, Commodity, Location, Supplier, SupplierExclusion

router = APIRouter()

# Ambang tampilan yang dipakai frontend untuk peran SPPG (lib/supplier-pins.ts).
# Endpoint TIDAK memasang default ini sendiri: penyaring harus diminta eksplisit
# supaya "dipanggil tanpa parameter" tidak pernah berarti "disaring diam-diam".
DEFAULT_REACH_KM = 150.0


def _num(value) -> Optional[float]:
    return None if value is None else float(value)


async def _reference_point(db, user, location_name: Optional[str]) -> Optional[dict]:
    """Titik rujukan jarak: lokasi user (SPPG) -> hub filter `location` -> None."""
    location_id = getattr(user, "location_id", None)
    if location_id is not None:
        row = (
            await db.execute(select(Location).where(Location.id == location_id))
        ).scalar_one_or_none()
        if row is not None and row.latitude is not None and row.longitude is not None:
            return {
                "location": row.name,
                "latitude": _num(row.latitude),
                "longitude": _num(row.longitude),
            }
    if location_name:
        row = (
            await db.execute(
                select(Location).where(
                    func.lower(Location.name) == location_name.strip().lower()
                )
            )
        ).scalar_one_or_none()
        if row is not None and row.latitude is not None and row.longitude is not None:
            return {
                "location": row.name,
                "latitude": _num(row.latitude),
                "longitude": _num(row.longitude),
            }
    return None


def _distance_km(reference: Optional[dict], supplier: Supplier) -> Optional[float]:
    """Jarak pemasok dari titik rujukan (satu desimal), atau None bila tak bisa dihitung."""
    if reference is None:
        return None
    if supplier.latitude is None or supplier.longitude is None:
        return None
    return round(
        haversine_km(
            float(supplier.latitude),
            float(supplier.longitude),
            float(reference["latitude"]),
            float(reference["longitude"]),
        ),
        1,
    )


def _shipping_payload(summary: Optional[dict]) -> Optional[dict]:
    """Bentuk JSON ringkasan kiriman aktif (tanggal ISO, kg float)."""
    if summary is None:
        return None
    return {
        "count": summary["count"],
        "total_kg": summary["total_kg"],
        "until": summary["until"].isoformat(),
        "commodities": summary["commodities"],
        "safety_fail_count": summary["safety_fail_count"],
    }


async def _active_shipping(db, now: datetime) -> dict[str, dict]:
    """Ringkasan kiriman aktif SEMUA pemasok (satu query, bukan per baris).

    Sumbernya batch kiriman: `usable_until >= now` = masih layak, yaitu definisi
    "sedang mengirim" yang dikunci pemilik 2026-10-16 (`app/core/supplier_shipping.py`).
    Endpoint ini tidak menghitung apa pun di sisi frontend: peta/daftar hanya
    menampilkan angka yang datang dari sini.
    """
    rows = (
        await db.execute(
            select(
                Batch.supplier_id,
                Commodity.name.label("commodity"),
                Batch.quantity_kg,
                Batch.usable_until,
                Batch.safety_status,
            ).outerjoin(Commodity, Commodity.id == Batch.commodity_id)
        )
    ).all()
    return shipping_summary(
        [
            {
                "supplier_id": row.supplier_id,
                "commodity": row.commodity,
                "quantity_kg": row.quantity_kg,
                "usable_until": row.usable_until,
                "safety_status": row.safety_status,
            }
            for row in rows
        ],
        now,
    )


@router.get("/suppliers")
async def list_suppliers(
    commodity: Optional[str] = Query(None, description="nama komoditas, mis. telur"),
    location: Optional[str] = Query(None, description="nama hub pemasok, mis. Cianjur"),
    q: Optional[str] = Query(None, description="cari nama/alamat/kontak (case-insensitive)"),
    max_distance_km: Optional[float] = Query(
        None,
        ge=0,
        le=2000,
        description=(
            "penyaring RELEVANSI: hanya pemasok dalam radius ini dari titik rujukan "
            "(lokasi user, atau hub pada `location=`). Butuh rujukan -> 422 tanpa itu."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Daftar pemasok + profil peta (koordinat, kapasitas, sertifikasi, jarak)."""
    stmt = (
        select(
            Supplier,
            Location.name.label("location_name"),
            Commodity.name.label("commodity_name"),
        )
        .join(Location, Location.id == Supplier.location_id)
        .outerjoin(Commodity, Commodity.id == Supplier.commodity_id)
    )
    if commodity:
        stmt = stmt.where(func.lower(Commodity.name) == commodity.strip().lower())
    if location:
        stmt = stmt.where(func.lower(Location.name) == location.strip().lower())
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Supplier.name).like(needle),
                func.lower(func.coalesce(Supplier.address, "")).like(needle),
                func.lower(func.coalesce(Supplier.contact_name, "")).like(needle),
            )
        )

    reference = await _reference_point(db, user, location)
    if max_distance_km is not None and reference is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "penyaring jarak butuh titik rujukan: akun yang terikat lokasi "
                "atau filter `location=`"
            ),
        )

    candidates = (await db.execute(stmt.order_by(Supplier.name))).all()

    out_of_reach = 0
    unknown_distance = 0
    kept: list[tuple] = []
    for supplier, location_name, commodity_name in candidates:
        distance = _distance_km(reference, supplier)
        if max_distance_km is not None:
            if distance is None:
                unknown_distance += 1
                continue
            if distance > max_distance_km:
                out_of_reach += 1
                continue
        kept.append((supplier, location_name, commodity_name, distance))

    total = len(kept)
    page = kept[offset : offset + limit]

    # Eksklusi aktif per pemasok -> daftar NAMA lokasi cakupan (eksklusi lokal,
    # jadi UI tidak boleh menyebutnya nasional).
    excl_rows = (
        await db.execute(
            select(SupplierExclusion.supplier_id, Location.name)
            .join(Location, Location.id == SupplierExclusion.scope_location_id)
            .where(SupplierExclusion.status == "active")
        )
    ).all()
    excluded: dict[uuid.UUID, list[str]] = {}
    for supplier_id, scope_name in excl_rows:
        excluded.setdefault(supplier_id, []).append(scope_name)

    items = []
    shipping_map = await _active_shipping(db, datetime.now(UTC))
    for supplier, location_name, commodity_name, distance in page:
        scopes = sorted(excluded.get(supplier.id, []))
        items.append(
            {
                "id": str(supplier.id),
                "name": supplier.name,
                "location_id": str(supplier.location_id),
                "location": location_name,
                "latitude": _num(supplier.latitude),
                "longitude": _num(supplier.longitude),
                "commodity_id": str(supplier.commodity_id) if supplier.commodity_id else None,
                "commodity": commodity_name,
                "reliability_score": _num(supplier.reliability_score),
                "capacity_kg_per_week": _num(supplier.capacity_kg_per_week),
                "certification_status": supplier.certification_status,
                "address": supplier.address,
                "contact_name": supplier.contact_name,
                "distance_km": distance,
                # "Sedang mengirim" = punya batch kiriman yang masih layak hari ini
                # (keputusan pemilik 2026-10-16). null = tidak sedang mengirim.
                "shipping": _shipping_payload(shipping_for(shipping_map, supplier.id)),
                # 22 Okt 2026: dulu dibandingkan dengan lokasi PEMASOK sendiri,
                # sehingga penanda tidak pernah menyala walau eksklusi aktif
                # (scope berisi nama hub, bukan nama lokasi pemasok). Arti yang
                # benar: ada eksklusi aktif pada pemasok ini di hub mana pun.
                # Rincian hub-nya tetap ada di `excluded_scope_locations`.
                "excluded_at_hub": bool(scopes),
                "excluded_scope_locations": scopes,
            }
        )
    return {
        "count": len(items),
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "distance_reference": reference,
        "reach": {
            "max_distance_km": None if max_distance_km is None else float(max_distance_km),
            "excluded_out_of_reach": out_of_reach,
            "excluded_unknown_distance": unknown_distance,
        },
        "items": items,
    }
