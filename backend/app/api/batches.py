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


from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.commodity_policy import CommodityPolicy
from app.core.policy_store import baca_semua_profil
from app.models import Batch, BatchReceipt, Commodity, DemoSession, Location
from app.models.users import User
from app.services.batch_eligibility_service import (
    evaluasi_batch,
    payload_eligibility,
)
from app.services.batch_evidence import blok_bukti_batch, blok_bukti_profil_hilang

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
            # Fase 3 MG butir 5: daftar ikut membawa BUKTI SUHU yang dipakai,
            # dari parser yang sama dengan detail. Tanpa kolom ini pembaca
            # daftar hanya melihat verdict, lalu menyimpulkan kelengkapan bukti
            # sendiri — dua tempat, dua cerita.
            Batch.temperature_log,
            Batch.origin,
            # Fase 7 MG: kerangka waktu bukti. Baris milik sesi demo dievaluasi
            # pada jangkar sesinya; baris operasional/kanonik tetap jam dinding.
            Batch.demo_session_id,
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
    # Profil dibaca SEKALI untuk seluruh halaman (bukan satu query per baris):
    # 500 baris × satu SELECT profil adalah latensi yang tidak dibayar UI.
    profil = await baca_semua_profil(db)
    waktu = await _waktu_evaluasi(db, rows)
    return {
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "batches": [
            {**_baris(r), "evidence": _bukti(r, profil, waktu(r))} for r in rows
        ],
    }


async def _waktu_evaluasi(db: AsyncSession, rows):
    """Pengambil waktu evaluasi per baris: jangkar sesi untuk baris ber-sesi.

    Dua sumbu waktu (rencana Fase 2, dipakai Fase 7): data milik sesi demo
    dievaluasi pada `evaluation_anchor` sesi itu — itulah arti "dataset replay 8
    Oktober": log 8 Oktober segar pada 8 Oktober, bukan basi hari ini. Data tanpa
    sesi (kanonik/operasional) tetap dinilai pada jam dinding, karena "masih
    berlaku hari ini" memang pertanyaannya.

    Jangkar diambil SATU query untuk seluruh halaman (bukan per baris): halaman
    500 batch tidak boleh menambah 500 SELECT.
    """
    sesi_ids = {
        getattr(r, "demo_session_id", None)
        for r in rows
        if getattr(r, "demo_session_id", None) is not None
    }
    jangkar: dict[uuid.UUID, datetime] = {}
    if sesi_ids:
        hasil = await db.execute(
            select(DemoSession.id, DemoSession.evaluation_anchor).where(
                DemoSession.id.in_(sesi_ids)
            )
        )
        jangkar = {baris[0]: baris[1] for baris in hasil.all()}
    sekarang = datetime.now(UTC)

    def ambil(r) -> datetime:
        sesi_id = getattr(r, "demo_session_id", None)
        nilai = jangkar.get(sesi_id) if sesi_id is not None else None
        return nilai or sekarang

    return ambil


def _bukti(
    r: object,
    profil: dict[str, tuple[CommodityPolicy, str]],
    sekarang: datetime,
) -> dict:
    """Blok bukti suhu untuk satu baris — satu jalur untuk daftar DAN detail.

    Komoditas tanpa profil tidak dinilai dengan rentang karangan; blok itu
    menyatakan `insufficient` beserta alasannya (lihat `batch_evidence`).
    """
    kunci = (getattr(r, "commodity", None) or "").strip().lower()
    if kunci not in profil:
        return blok_bukti_profil_hilang(
            komoditas=getattr(r, "commodity", None),
            origin=getattr(r, "origin", None),
            evaluation_time=sekarang,
            safety_status=getattr(r, "safety_status", None),
        )
    policy, asal = profil[kunci]
    return blok_bukti_batch(
        temperature_log=getattr(r, "temperature_log", None),
        policy=policy,
        policy_source=asal,
        origin=getattr(r, "origin", None),
        # Waktu EVALUASI: sekarang, karena yang ditanyakan pembaca daftar adalah
        # "apakah bukti batch ini masih berlaku hari ini", bukan "apakah log ini
        # segar saat diunggah". Log lima hari lalu harus terbaca `stale` di sini.
        evaluation_time=sekarang,
        safety_status=getattr(r, "safety_status", None),
    )


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

    Sejak Fase 4 MG respons memuat `eligibility` {status, blocking_reasons,
    next_step}: kesimpulan kelayakan yang sama dengan penerimaan/eksekusi,
    dihitung saat dibaca sehingga tidak pernah berupa snapshot usang.
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
                # Masukan evaluator kelayakan (Fase 4): suhu & kode batch. Tidak
                # ikut dikirim ke klien — hanya dipakai menghitung `eligibility`.
                Batch.temperature_log,
                # Fase 3 butir 5: asal log (seed/demo) dibaca blok bukti supaya
                # labelnya "log simulasi", bukan klaim sensor.
                Batch.origin,
                # Fase 7 MG: sama dengan daftar — baris milik sesi dievaluasi
                # pada jangkar sesinya, bukan jam dinding.
                Batch.demo_session_id,
            )
            .join(Location, Location.id == Batch.location_id)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .where(Batch.id == batch_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")
    # Fase 4 MG poin 5: `eligibility` DIHITUNG SERVER dari evaluator tunggal —
    # UI tidak boleh menyimpulkan sendiri apakah batch boleh diterima. `batch`
    # sengaja tetap berbentuk sama dengan elemen daftar (kontrak
    # `test_batch_detail`), jadi field baru hidup di tingkat atas respons.
    profil = await baca_semua_profil(db)
    waktu = await _waktu_evaluasi(db, [row])
    return {
        "batch": _baris(row),
        "eligibility": payload_eligibility(evaluasi_batch(row)),
        # Fase 3 MG butir 5: bukti suhu yang DIPAKAI, dari parser yang sama
        # dengan daftar — bukan kesimpulan klien.
        "evidence": _bukti(row, profil, waktu(row)),
    }
