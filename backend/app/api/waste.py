"""GET /waste/summary — limbah & pengalihannya (Surplus & Limbah).

Latar: panel menampilkan "Komposter / bank pangan: —" karena tidak ada sumber
data. Modul ini menjawabnya dari tabel `disposal_events` (kolom `partner_name`,
migrasi 022), bukan dari angka karangan di klien.

Kontrak:
- `days` = jendela ke belakang dalam hari (default 30, 1..365). Jendela END =
  sekarang; itu yang dipakai panel ("sebulan terakhir"), dan ditulis di respons
  supaya pembaca tahu angkanya tentang periode apa.
- Cakupan: `sppg_*` hanya lokasi sendiri; `bgn_monitor` seluruh lokasi
  (`app/core/scope.py`).
- Tiga angka dipisah dengan sengaja:
  * `recorded_kg`   — semua limbah yang tercatat;
  * `diverted_kg`   — yang punya MITRA (dialihkan, bukan dibuang);
  * `unassigned_kg` — tercatat tetapi tanpa mitra.
  `recorded = diverted + unassigned` selalu benar; kalau tidak, itu bug.
- `available: false` + alasan bila tidak ada baris — bukan 0 kg yang tampak
  terukur.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.core.scope import scope_location_id
from app.db import get_db
from app.models import DisposalEvent, Location, User
from app.services import settlement

router = APIRouter(prefix="", tags=["waste"])

MAX_DAYS = 365


@router.get("/waste/summary")
async def waste_summary(
    days: int = Query(30, ge=1, le=MAX_DAYS),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Ringkasan limbah + mitra pengolahan dalam `days` hari terakhir."""
    akhir = datetime.now(UTC)
    mulai = akhir - timedelta(days=days)
    scope_id = scope_location_id(user)

    stmt = (
        select(
            DisposalEvent.partner_name,
            DisposalEvent.quantity_kg,
            Location.name.label("location_name"),
        )
        .join(Location, Location.id == DisposalEvent.location_id)
        .where(
            DisposalEvent.disposed_at >= mulai,
            DisposalEvent.disposed_at <= akhir,
        )
    )
    if scope_id is not None:
        stmt = stmt.where(DisposalEvent.location_id == scope_id)

    baris = (await db.execute(stmt)).all()

    total = 0.0
    dialihkan = 0.0
    mitra: dict[str, dict] = {}
    lokasi: set[str] = set()
    for partner_name, quantity, location_name in baris:
        kg = float(quantity)
        total += kg
        lokasi.add(location_name)
        if partner_name:
            dialihkan += kg
            catatan = mitra.setdefault(partner_name, {"name": partner_name, "kg": 0.0, "events": 0})
            catatan["kg"] += kg
            catatan["events"] += 1

    dasar = {
        "period": {"start": mulai.isoformat(), "end": akhir.isoformat(), "days": days},
        "scope": {
            "role": user.role,
            "location_id": str(scope_id) if scope_id else None,
            "locations": sorted(lokasi),
        },
        "computed_at": akhir.isoformat(),
    }

    if not baris:
        kosong = {"available": False, "reason": "tidak ada limbah tercatat pada periode ini"}
        return {
            **dasar,
            "recorded": {**kosong, "kg": None, "events": 0},
            "diverted": {**kosong, "kg": None, "events": 0},
            "unassigned": {**kosong, "kg": None, "events": 0},
            "partners": [],
        }

    return {
        **dasar,
        "recorded": {"available": True, "kg": round(total, 2), "events": len(baris)},
        "diverted": {
            "available": True,
            "kg": round(dialihkan, 2),
            "events": sum(1 for b in baris if b.partner_name),
        },
        "unassigned": {
            "available": True,
            "kg": round(total - dialihkan, 2),
            "events": sum(1 for b in baris if not b.partner_name),
        },
        "partners": sorted(
            ({**v, "kg": round(v["kg"], 2)} for v in mitra.values()),
            key=lambda x: (-x["kg"], x["name"]),
        ),
    }


class LimbahBaru(BaseModel):
    """Satu kejadian limbah yang dicatat operator.

    `kunci` opsional membuat penulisan idempoten (mis. id keputusan); tanpa
    kunci, setiap permintaan dianggap kejadian baru — karena dua pencatatan
    bisa memang dua kejadian.
    """

    location_id: str | None = None
    commodity_id: str
    quantity_kg: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    partner_name: str | None = None
    kunci: str | None = None


@router.post("/waste/disposals", status_code=201)
async def catat_limbah(
    payload: LimbahBaru,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    """Catat limbah → `disposal_events`. Inilah satu-satunya jalan agar
    Avoidable Food Loss bergerak tanpa menjalankan seeder.

    Cakupan: akun SPPG hanya boleh mencatat untuk lokasinya sendiri; BGN Monitor
    wajib menyebut `location_id`. Alasan yang tidak terbaca ditolak 422 — angka
    limbah tanpa alasan tidak bisa ditindaklanjuti.
    """
    import uuid as _uuid
    from decimal import Decimal as _Decimal

    scope_id = scope_location_id(user)
    if scope_id is not None:
        lokasi = scope_id
        if payload.location_id is not None and str(payload.location_id) != str(scope_id):
            raise HTTPException(
                status_code=403, detail="akun ini hanya boleh mencatat limbah lokasinya sendiri"
            )
    elif payload.location_id:
        try:
            lokasi = _uuid.UUID(str(payload.location_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="location_id bukan UUID") from exc
    else:
        raise HTTPException(
            status_code=422, detail="location_id wajib diisi untuk akun lintas lokasi"
        )

    try:
        komoditas = _uuid.UUID(str(payload.commodity_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="commodity_id bukan UUID") from exc

    sekarang = datetime.now(UTC)
    hasil = await settlement.catat_pembuangan(
        db,
        location_id=lokasi,
        commodity_id=komoditas,
        quantity_kg=_Decimal(str(payload.quantity_kg)),
        reason=payload.reason,
        partner_name=payload.partner_name,
        sekarang=sekarang,
        kunci=payload.kunci,
    )
    await db.commit()
    return {"dicatat_oleh": user.email, **hasil}
