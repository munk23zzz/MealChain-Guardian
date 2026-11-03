"""Router balance (Task 10 Sprint 2) — tipis: validasi + delegasi service."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.core.config import settings
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


def _batas_waktu(as_of: datetime | None) -> datetime:
    """Batas atas waktu baris: default SEKARANG (UTC).

    Deret demo diperluas sampai 5 Nov (ACTUAL_REF), jadi tanpa batas ini
    dashboard berlabel "Hari Ini" bisa menampilkan pasokan 4 Nov sementara
    permintaan masih 8 Okt — dua tanggal berbeda yang terbaca sebagai kondisi
    hari ini. `as_of` eksplisit dipakai untuk menelusuri snapshot lain.
    """
    if as_of is None:
        return datetime.now(timezone.utc)
    return as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=timezone.utc)


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


def _asal_nilai(row) -> str:
    """Asal sebuah angka: `terukur` (baris ada) atau `tidak_ada_baris`.

    Angka `0` TETAP dikirim supaya aturan tampilan tidak berubah (`0 kg` tetap
    `0 kg`), tetapi konsumen harus bisa memisahkan "nol terukur" dari "tidak ada
    catatan" — tanpa penanda ini, lokasi tanpa baris permintaan (nyata: Bandung
    & Cianjur untuk telur) tampak punya surplus ratusan kilo (PLAN-023).
    """
    return "terukur" if row is not None else "tidak_ada_baris"


def _data_state(s_row, d_row) -> str:
    """Ringkasan per lokasi: `terukur` | `sebagian` | `tidak_ada_baris`."""
    if s_row is not None and d_row is not None:
        return "terukur"
    if s_row is None and d_row is None:
        return "tidak_ada_baris"
    return "sebagian"


def _waktu_kebutuhan(row) -> str | None:
    """`needed_by` baris permintaan — kapan komoditas itu dibutuhkan."""
    if row is None:
        return None
    nilai = getattr(row, "needed_by", None)
    return nilai.isoformat() if nilai is not None else None


def _waktu(row) -> str | None:
    """Stempel waktu baris yang benar-benar dipakai (= asal nilai); None = tak ada."""
    if row is None or row.recorded_at is None:
        return None
    return row.recorded_at.isoformat()


@router.get("/balance/{location}/{commodity}")
async def get_balance(
    location: str,
    commodity: str,
    as_of: datetime | None = Query(
        None, description="Batas atas waktu baris (default: sekarang)"
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    loc = await _resolve_location(db, location)
    assert_in_scope(user, loc.id, what="lokasi")
    com = await _resolve_commodity(db, commodity)
    from app.core.gaps import calculate_supply_gap

    batas = _batas_waktu(as_of)

    row_supply = (
        await db.execute(
            select(SupplyRecord)
            .where(
                SupplyRecord.location_id == loc.id,
                SupplyRecord.commodity_id == com.id,
                SupplyRecord.recorded_at <= batas,
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
                DemandRecord.recorded_at <= batas,
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
        # Asal nilai per sisi (PLAN-023): angka 0 tidak lagi ambigu.
        "supply_state": _asal_nilai(row_supply),
        "demand_state": _asal_nilai(row_demand),
        "data_state": _data_state(row_supply, row_demand),
        "supply_recorded_at": _waktu(row_supply),
        "demand_recorded_at": _waktu(row_demand),
        # Kapan kebutuhan itu DIPERLUKAN (datanya bisa untuk beberapa hari ke
        # depan). Tanpa ini UI menulis "Kebutuhan 1.080 kg" seolah hari ini.
        "demand_needed_by": _waktu_kebutuhan(row_demand),
        # Batas waktu yang dipakai (default: sekarang) — UI menyebut tanggalnya.
        "as_of": batas.isoformat(),
    }


class _AsyncFetcher:
    """Adapter async session → fetch_facts() awaitable untuk pipeline.

    `as_of` dibawa dari pemanggil: saat ada sesi demo AKTIF, jam evaluasinya
    adalah jangkar sesi (dataset replay berjangkar kanon). Tanpa itu, bukti suhu
    yang sah terbaca basi terhadap jam dinding sehingga gerbang Fase 6 menahan
    seluruh kandidat.
    """

    def __init__(self, db, as_of=None):
        self._db = db
        self._as_of = as_of

    async def __call__(self):
        return await rs.fetch_operational_facts(self._db, self._as_of)


async def _jam_sesi_aktif(db) -> datetime | None:
    """Jangkar sesi demo yang sedang aktif, atau `None` (jam dinding)."""
    from app.models import DemoSession

    try:
        baris = (
            await db.execute(
                select(DemoSession)
                .where(DemoSession.status == "active")
                .order_by(DemoSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    except Exception:  # noqa: BLE001 - jam evaluasi tidak boleh menggagalkan analisis
        return None
    anchor = getattr(baris, "evaluation_anchor", None)
    if anchor is not None:
        return anchor
    # Tanpa sesi aktif di mode demo: dataset replay berjangkar kanon.
    if bool(settings.demo_mode):
        from app.services.decision_time import REPLAY_ANCHOR

        return REPLAY_ANCHOR
    return None


@router.post("/balance/recommend")
async def post_recommend(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
):
    as_of = await _jam_sesi_aktif(db)
    fetcher = _AsyncFetcher(db, as_of)
    try:
        out = await rs.build_recommendations(fetcher, as_of=as_of)
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
    #: Fase 10 MG: sesi demo yang sedang dipilih operator. Analisis ini
    #: read-only (tidak menulis baris), tetapi balasannya harus menyebut sesi
    #: mana yang dimaksud supaya UI/Joule tidak memakai "sesi terbaru".
    demo_session: uuid.UUID | None = None


@router.get("/balance/map")
async def get_balance_map(
    commodity: str,
    as_of: datetime | None = Query(
        None, description="Batas atas waktu baris (default: sekarang)"
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """S4-06 polish (arah Roy 2026-10-08): kondisi semua lokasi utk map.

    Read-only (JWT, semua role boleh baca). Satu komoditas → snapshot
    supply/demand TERBARU tiap lokasi YANG SUDAH TERJADI (`recorded_at <=
    as_of`, default sekarang), aturan sama dengan GET /balance/{loc}/{com},
    gap via `calculate_supply_gap` — formula yang sama dengan panel, tanpa
    rumus kedua. Lokasi tanpa data → zeros (map tetap lengkap).
    Koordinat dari DB.
    """
    com = await _resolve_commodity(db, commodity)
    batas = _batas_waktu(as_of)
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
                    .where(
                        model.commodity_id == com.id,
                        model.recorded_at <= batas,
                    )
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
                # Asal nilai per sisi (PLAN-023): lokasi tanpa baris permintaan
                # tidak lagi tampak "surplus" tanpa bisa dibedakan.
                "supply_state": _asal_nilai(s_row),
                "demand_state": _asal_nilai(d_row),
                "data_state": _data_state(s_row, d_row),
                "supply_recorded_at": _waktu(s_row),
                "demand_recorded_at": _waktu(d_row),
                "demand_needed_by": _waktu_kebutuhan(d_row),
            }
        )
    return {"commodity": com.name, "as_of": batas.isoformat(), "locations": items}


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
    #: Fase 10 MG: sesi yang diminta operator divalidasi; sesi asing 404 —
    #: lebih baik menolak daripada mengembalikan analisis yang diberi label
    #: sesi lain.
    pemilik = None
    if payload is not None and payload.demo_session is not None:
        from app.services import demo_ownership

        try:
            pemilik = await demo_ownership.sesi_pemilik(
                db, demo_session=payload.demo_session
            )
        except demo_ownership.SesiTidakDitemukanError:
            raise HTTPException(
                status_code=404,
                detail=f"sesi demo {payload.demo_session} tidak ditemukan",
            ) from None
    as_of = await _jam_sesi_aktif(db)
    fetcher = _AsyncFetcher(db, as_of)
    try:
        out = await rs.build_recommendations(fetcher, as_of=as_of, commodity=commodity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    recs = out["recommendations"]
    out["summary"] = {
        "candidates_total": len(recs),
        "eligible": sum(1 for r in recs if r.get("eligible")),
        "review_required": sum(1 for r in recs if r.get("review_required")),
        # Fase 6: kandidat yang TERTAHAN gerbang hierarki (bukti/keamanan/
        # tenggat). Dihitung di sini supaya UI bisa menyebutnya tanpa merakit
        # ulang evaluasi batch di klien.
        "held_total": len(out.get("held") or []),
        "flagged_price": sum(
            1 for r in recs if (r.get("price_anomaly") or {}).get("flagged")
        ),
    }
    if commodity:
        out["filtered_by"] = {"commodity": commodity}
    #: Fase 10 MG: sesi yang dipakai analisis ini, atau `null` bila operator
    #: tidak menyebut sesi (jalur lama). Joule/UI membaca field ini, bukan
    #: menebak dari sesi terbaru.
    from app.services.demo_ownership import blok_sesi

    out["demo_session"] = blok_sesi(pemilik)
    return out
