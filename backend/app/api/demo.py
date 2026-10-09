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

Demo-day guard (Roy 2026-10-07): SEMUA kasus berstatus
pending_approval/verifier_flagged dijaga TTL >= 60 menit pasca-seed
(di-guard test) — tidak ada kasus mati sebelum sempat didemokan.

Semua angka konsisten dengan seed sintetis (telur, SDC Rp16,2 jt,
freshness 0,90). Tidak ada auto-approve — loop manusia tetap wajib.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_roles
from app.api.dependencies import get_db
from app.models import AgentTrace, Commodity, Decision, Location, User

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


@router.post("/demo/seed", status_code=200)
async def seed_demo(
    payload: SeedRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles("sppg_head", "sppg_nutritionist")),
):
    existing = (
        await db.execute(
            select(Decision).where(Decision.demo_case.in_(DEMO_CASES))
        )
    ).scalars().all()
    if existing and not payload.force:
        return {
            "seeded": False,
            "already": len(existing),
            "message": "Kasus demo sudah ada — pakai force=true untuk reset.",
        }
    if payload.force and existing:
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
