"""Demo seeder (permintaan Roy 2026-10-07): 4 kasus siap-demo.

POST /demo/seed — idempotent (skip bila kasus sudah ada; force=true
menghapus ulang HANYA baris ber-demo_case). Kasus:
  1. rejection-loop-kuota : v1 ditolak (kuota) → v2 ditolak (harga) →
     v3 pending_approval FRESH → approve/execute live saat demo.
  2. shortage-darurat     : shortage Jakarta 780 kg, drama safety
     window ada di trace (safety_window 30 mnt) — TTL kartu panjang
     supaya tidak EXPIRED di tengah demo.
  3. supplier-janggal     : harga supplier 40% di bawah referensi →
     verifier FLAGGED (anti-fraud).
  4. gangguan-logistik    : v1 ditolak (rute Bogor banjir) → v2
     pending_approval dengan sumber alternatif Cianjur.

Catatan (Ruling 2026-10-14): Event 3 tetap bisa dipicu kepala SPPG dengan batch
di lokasi SUMBER mana pun — yang dikunci cakupan adalah LOKASI TUJUAN keputusan
(SPPG pemakai), dan itu ditentukan pemanggil (target_location_id), bukan lokasi
batch. Panel chaos sengaja TIDAK mengirim lokasi batch sebagai target.

Demo-day guard (Roy 2026-10-07): SEMUA kasus berstatus
pending_approval/verifier_flagged dijaga TTL >= 60 menit pasca-seed
(di-guard test) — tidak ada kasus mati sebelum sempat didemokan.

Semua angka konsisten dengan seed sintetis (telur, SDC Rp16,2 jt,
freshness 0,90). Tidak ada auto-approve — loop manusia tetap wajib.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_roles
from app.api.dependencies import get_db
from app.models import AgentTrace, Commodity, Decision, Location, User
from app.seed.timeseries import (
    DEFAULT_END,
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_START,
    demo_data_status,
    generate_timeseries,
    preview_timeseries,
    purge_demo_rows,
    validate_range,
)

router = APIRouter()

DEMO_CASES = (
    "rejection-loop-kuota",
    "shortage-darurat",
    "supplier-janggal",
    "gangguan-logistik",
)


class SeedRequest(BaseModel):
    force: bool = False


def _loc_map(locations) -> dict:
    return {loc.name: loc.id for loc in locations}


async def _commodity_id(db: AsyncSession, name: str):
    row = (
        await db.execute(select(Commodity).where(Commodity.name == name))
    ).scalar_one_or_none()
    return row.id if row else None


async def _add_trace(
    db: AsyncSession,
    decision_id,
    step_name: str,
    minutes_ago: int,
    tool: str,
    input_summary: dict,
    output_summary: dict,
):
    db.add(
        AgentTrace(
            decision_id=decision_id,
            step_name=step_name,
            tool_called=tool,
            input_summary=input_summary,
            output_summary=output_summary,
            step_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        )
    )


def _decision(
    case: str,
    iteration: int,
    status: str,
    src,
    tgt,
    commodity_id,
    qty: str,
    sdc: str,
    ttl_minutes: int,
    supersedes=None,
    rejection_reason=None,
    verifier_note=None,
    verified_by=None,
) -> Decision:
    return Decision(
        decision_type=(
            "safety_disruption"
            if case in {"shortage-darurat", "gangguan-logistik"}
            else "regional_balance"
            if case == "rejection-loop-kuota"
            else "price_anomaly"
        ),
        status=status,
        proposed_by="supervisor_agent",
        verified_by=verified_by,
        verifier_note=verifier_note,
        rejection_reason=rejection_reason,
        iteration=iteration,
        supersedes_id=supersedes,
        demo_case=case,
        origin="demo",
        generated_at=datetime.now(timezone.utc),
        source_location_id=src,
        target_location_id=tgt,
        commodity_id=commodity_id,
        quantity_kg=qty,
        safe_delivered_cost=sdc,
        cost_breakdown={
            "purchase": "15720000",
            "logistics": "486000",
            "note": "seed demo — angka konsisten docs",
        },
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )


async def _seed_demo_cases(db: AsyncSession, force: bool) -> dict:
    """Badan `POST /demo/seed` — dipakai juga oleh `/demo/refresh`.

    Dipisah sebagai fungsi supaya "Segarkan ke hari ini" bisa menjalankan
    seeder relatif lalu MEMUAT ULANG kasus skrip (TTL baru) tanpa menduplikasi
    logika kasus di dua tempat.
    """
    existing = (
        await db.execute(
            select(Decision).where(Decision.demo_case.in_(DEMO_CASES))
        )
    ).scalars().all()
    if existing and not force:
        return {
            "seeded": False,
            "already": len(existing),
            "message": "Kasus demo sudah ada — pakai force=true untuk reset.",
        }
    if force and existing:
        # Hanya baris demo (demo_case NOT NULL) yang dihapus.
        await db.execute(
            delete(Decision).where(Decision.demo_case.in_(DEMO_CASES))
        )
        await db.flush()

    locations = (await db.execute(select(Location))).scalars().all()
    loc = _loc_map(locations)
    missing = {"Bogor", "Jakarta", "Cianjur"} - set(loc)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"lokasi seed tidak lengkap: {sorted(missing)}",
        )
    telur = await _commodity_id(db, "telur")
    if telur is None:
        raise HTTPException(status_code=422, detail="komoditas telur tidak ada")

    created: list[str] = []

    # ---- Kasus 1: rejection-loop-kuota (v1 ditolak → v2 ditolak → v3 fresh)
    v1 = _decision(
        "rejection-loop-kuota", 1, "rejected",
        loc["Cianjur"], loc["Jakarta"], telur, "600", "16206000.00",
        ttl_minutes=-60,  # kedaluwarsa (sudah lewat, keputusan mati)
        rejection_reason="Kuota SPPG Jakarta penuh minggu ini — coba skema bertahap.",
    )
    db.add(v1)
    await db.flush()
    created.append(v1.id)
    await _add_trace(db, v1.id, "DETECT", 95, "demand.snapshot",
        {"location": "Jakarta", "window": "7d"},
        {"shortage_kg": 600, "signal": "permintaan naik"})
    await _add_trace(db, v1.id, "DECIDE", 92, "supply_balance.propose",
        {"source": "Cianjur", "target": "Jakarta", "qty": 600},
        {"sdc": 16206000, "scenario": "regional_balance"})
    await _add_trace(db, v1.id, "LEARN", 60, "rejection_loop.repropose",
        {"parent_iteration": 1},
        {"parent_rejection_reason": "Kuota SPPG Jakarta penuh minggu ini — coba skema bertahap.",
         "learning_note": "Iterasi berikut: skema bertahap 300 kg + 300 kg."})

    v2 = _decision(
        "rejection-loop-kuota", 2, "rejected",
        loc["Cianjur"], loc["Jakarta"], telur, "600", "16206000.00",
        ttl_minutes=-30,
        supersedes=v1.id,
        rejection_reason="Harga per kg naik 12% dari referensi — negosiasi ulang dulu.",
    )
    db.add(v2)
    await db.flush()
    created.append(v2.id)
    await _add_trace(db, v2.id, "LEARN", 30, "rejection_loop.repropose",
        {"parent_iteration": 2},
        {"parent_rejection_reason": "Harga per kg naik 12% dari referensi — negosiasi ulang dulu.",
         "learning_note": "Iterasi berikut: skema bertahap 2×300 kg dengan harga terkunci."})

    v3 = _decision(
        "rejection-loop-kuota", 3, "pending_approval",
        loc["Cianjur"], loc["Jakarta"], telur, "600", "16206000.00",
        ttl_minutes=480,  # demo-day guard: jangan EXPIRED saat demo (Roy)
        supersedes=v2.id,
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(v3)
    await db.flush()
    created.append(v3.id)
    await _add_trace(db, v3.id, "PREDICT", 25, "forecast.daily",
        {"model": "chain-11-slot", "horizon_days": 7},
        {"method": "provider_forecast", "note": "skema bertahap 2×300 kg"})
    await _add_trace(db, v3.id, "DECIDE", 24, "supply_balance.propose",
        {"source": "Cianjur", "target": "Jakarta", "qty": 600, "scheme": "2x300"},
        {"sdc": 16206000, "learning_applied": ["kuota", "harga"]})

    # ---- Kasus 2: shortage-darurat (TTL pendek — drama safety window)
    s1 = _decision(
        "shortage-darurat", 1, "pending_approval",
        loc["Bogor"], loc["Jakarta"], telur, "780", "14787096.28",
        ttl_minutes=120,  # drama tetap di trace (safety window 30 mnt);
        # TTL kartu panjang supaya kasus tidak mati saat demo (Roy)
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(s1)
    await db.flush()
    created.append(s1.id)
    await _add_trace(db, s1.id, "DETECT", 20, "demand.snapshot",
        {"location": "Jakarta", "shortage": 780},
        {"severity": "CRITICAL", "safety_window_minutes": 30})
    await _add_trace(db, s1.id, "PREDICT", 19, "forecast.daily",
        {"horizon_days": 1},
        {"method": "provider_forecast", "coverage": 0.94})
    await _add_trace(db, s1.id, "DECIDE", 18, "supply_balance.propose",
        {"source": "Bogor", "target": "Jakarta", "qty": 780},
        {"sdc": 14787096.28, "urgency": "safety_window"})

    # ---- Kasus 3: supplier-janggal (verifier FLAGGED — anti-fraud)
    j1 = _decision(
        "supplier-janggal", 1, "verifier_flagged",
        loc["Cianjur"], loc["Jakarta"], telur, "600", "9200000.00",
        ttl_minutes=480,  # demo-day guard (Roy)
        verified_by="verifier_agent",
        verifier_note="flagged",
    )
    db.add(j1)
    await db.flush()
    created.append(j1.id)
    await _add_trace(db, j1.id, "DETECT", 40, "price.signal",
        {"commodity": "telur", "source": "Cianjur"},
        {"anomaly": "harga 40% di bawah referensi pihps"})
    await _add_trace(db, j1.id, "VERIFY", 38, "evidence.crosscheck",
        {"ref_source": "pihps_reference", "supplier_quote_ratio": 0.60},
        {"verdict": "FLAGGED",
         "reason": "Harga supplier janggal — 40% di bawah referensi; minta dokumen pendukung."})

    # ---- Kasus 4: gangguan-logistik (v1 ditolak → v2 rute alternatif)
    g1 = _decision(
        "gangguan-logistik", 1, "rejected",
        loc["Bogor"], loc["Jakarta"], telur, "600", "16206000.00",
        ttl_minutes=-45,
        rejection_reason="Rute Bogor–Jakarta terganggu banjir — cari sumber alternatif.",
    )
    db.add(g1)
    await db.flush()
    created.append(g1.id)
    await _add_trace(db, g1.id, "DETECT", 70, "logistics.status",
        {"route": "Bogor→Jakarta"},
        {"disruption": "banjir", "eta_delay_hours": 6})
    await _add_trace(db, g1.id, "LEARN", 45, "rejection_loop.repropose",
        {"parent_iteration": 1},
        {"parent_rejection_reason": "Rute Bogor–Jakarta terganggu banjir — cari sumber alternatif.",
         "learning_note": "Iterasi berikut: sumber alternatif Cianjur."})

    g2 = _decision(
        "gangguan-logistik", 2, "pending_approval",
        loc["Cianjur"], loc["Jakarta"], telur, "600", "16206000.00",
        ttl_minutes=300,  # demo-day guard (Roy)
        supersedes=g1.id,
        verified_by="verifier_agent",
        verifier_note="consistent",
    )
    db.add(g2)
    await db.flush()
    created.append(g2.id)
    await _add_trace(db, g2.id, "OPTIMIZE", 40, "logistics.reroute",
        {"candidates": ["Cianjur", "Sukabumi"]},
        {"selected_source": "Cianjur", "eta_ok": True})
    await _add_trace(db, g2.id, "DECIDE", 39, "supply_balance.propose",
        {"source": "Cianjur", "target": "Jakarta", "qty": 600},
        {"sdc": 16206000, "reroute_from": "Bogor"})

    await db.commit()
    return {
        "seeded": True,
        "cases": len(DEMO_CASES),
        "decisions": len(created),
        "message": "4 kasus demo siap — v3 kuota & v2 logistik siap approve.",
    }


@router.post("/demo/seed", status_code=200)
async def seed_demo(
    payload: SeedRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Muat 4 kasus skrip. Idempotent; `force=true` menghapus ulang HANYA baris kasus."""
    return await _seed_demo_cases(db, payload.force)


# --------------------------------------------------------------------------
# Data & rentang waktu (Fase 4): generator deret waktu demo.
#
# Peran: sama dengan /demo/seed (kepala SPPG) — panel Demo Control memang
# dipakai operator demo, bukan pemantau BGN.
# --------------------------------------------------------------------------


class TimeseriesRequest(BaseModel):
    start: datetime = DEFAULT_START
    end: datetime = DEFAULT_END
    interval_hours: int = DEFAULT_INTERVAL_HOURS
    force: bool = False


def _validate_or_422(start: datetime, end: datetime) -> None:
    try:
        validate_range(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/demo/preview")
async def preview_timeseries_data(
    start: datetime = Query(default=DEFAULT_START),
    end: datetime = Query(default=DEFAULT_END),
    interval_hours: int = Query(default=DEFAULT_INTERVAL_HOURS, ge=1, le=168),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Pratinjau: berapa baris yang AKAN ditambah. Tidak menulis apa pun."""
    _validate_or_422(start, end)
    return await preview_timeseries(start, end, interval_hours=interval_hours)


@router.post("/demo/timeseries", status_code=200)
async def generate_timeseries_data(
    payload: TimeseriesRequest,
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Buat/perbarui baris demo `origin='demo'`. Idempoten.

    `force=true` menghapus dulu baris demo (bukan baris kanonik) supaya rentang
    bisa diganti bersih — pola yang sama dengan `POST /demo/seed`.
    """
    _validate_or_422(payload.start, payload.end)
    summary: dict = {"purged": None}
    if payload.force:
        summary["purged"] = await purge_demo_rows()
    summary.update(
        await generate_timeseries(
            payload.start, payload.end, interval_hours=payload.interval_hours
        )
    )
    return summary


@router.post("/demo/timeseries/purge", status_code=200)
async def purge_timeseries_data(
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Hapus HANYA baris deret waktu `origin='demo'`; snapshot kanonik tidak disentuh."""
    return await purge_demo_rows()


@router.get("/demo/data-status")
async def get_data_status(
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Keadaan data demo SEKARANG (baca DB, bukan ingatan klien).

    Panel Demo Control memakainya untuk baris status; kalau operator membuka
    tab baru atau kontainer di-restart, UI tetap jujur.
    """
    return await demo_data_status()


#: Peringatan yang WAJIB tampil bersama tombol "Segarkan ke hari ini".
#: Bukan basa-basi: menjalankan seeder relatif `now` memang menggeser tanggal
#: snapshot kanonik, dan itu punya konsekuensi yang harus diketahui operator.
REFRESH_WARNING = (
    "Seeder relatif menjalankan ulang snapshot kanonik pada tanggal HARI INI "
    "dan memuat ulang 4 kasus skrip dengan batas waktu baru. Nilai jangkar "
    "(4.900 kg, 3 surplus : 7 shortage, Cianjur 1.400 kg) tidak berubah karena "
    "angkanya berasal dari berkas seed yang sama — yang bergeser adalah "
    "TANGGALNYA. Akibatnya tes backend yang memaku 8 Okt 12:00 tidak lagi "
    "cocok sampai snapshot dikembalikan (lihat prosedur rollback di rencana "
    "Fase 6). Baris deret waktu demo lama tetap ada sampai Anda menekan "
    "\"Bersihkan data demo\" atau membangun ulang rentangnya."
)


@router.post("/demo/refresh", status_code=200)
async def refresh_to_today(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
) -> dict:
    """Tombol hari demo: seeder relatif `now` + muat ulang 4 kasus skrip.

    Akun demo TIDAK disentuh (password tidak direset) dan baris deret waktu
    demo TIDAK dihapus — keduanya punya tombol sendiri di panel.
    """
    from app.seed.seed_data import load_seed

    now = datetime.now(timezone.utc)
    rows = await load_seed(now)
    cases = await _seed_demo_cases(db, force=True)
    return {
        "reference_time": now.isoformat(),
        "rows": rows,
        "cases": cases,
        "warning": REFRESH_WARNING,
        "message": "Snapshot kanonik disegarkan ke hari ini; 4 kasus skrip dimuat ulang.",
    }
