"""Endpoint batch read-only (P4 chaos panel — keputusan Roy 2026-10-09).

GET /batches — daftar batch (id, kode, lokasi, komoditas, safety status,
temperature ringkas) untuk dipilih di panel chaos Event 3. Read-only,
semua role terautentikasi. TIDAK mengekspos kolom sensitif tambahan.

Sejak 2026-10-20 endpoint ini menerima `limit`/`offset` (default 50, plafon 500) dan
mengembalikan `total` = jumlah seluruh baris tabel. Sebelumnya batas 50 tertanam di kode,
sehingga konsumen yang butuh inventaris lengkap (jembatan Joule, laporan nasional) diam-diam
hanya melihat 50 batch terbaru sementara database berisi 158 — data "hilang" tanpa galat.

Sejak 2026-10-20 juga mengembalikan `receipt_status` (status catatan penerimaan terakhir per
batch, null bila belum pernah dicatat) — dipakai layar Penerimaan agar hanya menawarkan batch
yang masih perlu diperiksa/dicatat.
"""


import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models import Batch, BatchReceipt, Commodity, Location
from app.models.users import User

router = APIRouter(prefix="", tags=["batches"])

#: Batas baris sekali baca. Plafon 500 = lebih dari seluruh batch demo, tetap satu query.
BATAS_DEFAULT = 50
BATAS_MAKS = 500


@router.get("/batches")
async def list_batches(
    limit: int = Query(
        BATAS_DEFAULT,
        ge=1,
        le=BATAS_MAKS,
        description="jumlah baris yang dikembalikan (plafon 500)",
    ),
    offset: int = Query(0, ge=0, description="baris yang dilewati, untuk paginasi"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Daftar batch untuk panel chaos Event 3.

    CATATAN audit 2026-10-11: daftar ini sengaja lintas lokasi (batch source
    chaos bisa berada di lokasi mana pun) — kalau O-SEC-2 dikunci untuk
    /events/*, daftar ini juga wajib di-scope, dan panel akan kosong untuk
    SPPG Head di Jakarta (seed tidak punya batch Jakarta).

    `total` dikirim supaya konsumen tahu berapa baris sebenarnya: batas `limit` tidak boleh
    lagi tampak seperti "hanya ini yang ada di database".
    """
    # Status catatan penerimaan TERAKHIR per batch. Dipakai layar Penerimaan
    # untuk hanya menawarkan batch yang masih perlu diperiksa/dicatat —
    # batch yang sudah `menunggu` atau `disetujui` tidak ditawarkan lagi.
    receipt_terakhir = (
        select(BatchReceipt.status)
        .where(BatchReceipt.batch_id == Batch.id)
        .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
        .limit(1)
        .correlate(Batch)
        .scalar_subquery()
        .label("receipt_status")
    )
    query = (
        select(
            Batch.id,
            receipt_terakhir,
            Batch.quantity_kg,
            Batch.safety_status,
            Batch.freshness_score,
            Batch.usable_until,
            Batch.quarantine_status,
            Batch.location_id,
            Location.name.label("location"),
            Commodity.name.label("commodity"),
        )
        .join(Location, Location.id == Batch.location_id)
        .join(Commodity, Commodity.id == Batch.commodity_id)
        # Kunci kedua `Batch.id`: banyak batch berbagi `created_at` yang sama, dan paginasi
        # `offset` menjadi tidak stabil kalau urutannya seri (baris bisa muncul dua kali /
        # hilang di antara halaman).
        .order_by(Batch.created_at.desc(), Batch.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(query)).all()
    total = int((await db.execute(select(func.count()).select_from(Batch))).scalar_one())
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "batches": [_baris(r) for r in rows],
    }


def _baris(r: object) -> dict:
    """Satu bentuk baris untuk daftar DAN detail — dua tempat, satu kontrak.

    Kalau detail menambah kolom sendiri, UI/Joule akan melihat dua bentuk berbeda
    untuk entitas yang sama; itu jenis kebingungan yang mahal saat demo.
    """
    return {
        "id": str(r.id),
        "location": r.location,
        "location_id": str(r.location_id),
        "commodity": r.commodity,
        "quantity_kg": float(r.quantity_kg),
        "safety_status": r.safety_status,
        "freshness_score": (float(r.freshness_score) if r.freshness_score is not None else None),
        "usable_until": r.usable_until.isoformat() if r.usable_until else None,
        # Karantina: batch ditahan tidak boleh dihitung sebagai stok layak pakai
        # walau kilogram fisiknya masih tercatat.
        "receipt_status": r.receipt_status,
        "quarantine_status": r.quarantine_status,
    }


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Satu batch (audit 21 Okt 2026, P6).

    Sebelumnya tidak ada rute ini: semua peran menerima 404, sehingga tautan dalam
    dan pertanyaan "batch ini apa?" hanya bisa dijawab dengan menarik seluruh daftar.
    Visibilitas mengikuti daftar (lintas lokasi, sengaja: panel chaos membaca batch
    dari lokasi mana pun), jadi endpoint ini tidak menambah aturan cakupan baru.
    """
    receipt_terakhir = (
        select(BatchReceipt.status)
        .where(BatchReceipt.batch_id == Batch.id)
        .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
        .limit(1)
        .correlate(Batch)
        .scalar_subquery()
        .label("receipt_status")
    )
    row = (
        await db.execute(
            select(
                Batch.id,
                receipt_terakhir,
                Batch.quantity_kg,
                Batch.safety_status,
                Batch.freshness_score,
                Batch.usable_until,
                Batch.quarantine_status,
                Batch.location_id,
                Location.name.label("location"),
                Commodity.name.label("commodity"),
            )
            .join(Location, Location.id == Batch.location_id)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .where(Batch.id == batch_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")
    return {"batch": _baris(row)}
