"""Orchestrator pengadaan pemasok untuk Demo Control (19 Okt 2026).

Alur tujuh langkah yang sama dengan `event1_orchestrator`, tetapi objek yang
dinilai adalah PEMASOK yang sudah memasok SPPG target (bukan surplus SPPG
lain):

DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → SUPERVISE

Semua angka berasal dari `supplier_procurement.evaluate_suppliers`
(pemasok, stok batch di SPPG itu, penawaran harga, jarak pemasok→SPPG) dan
`run_forecast` untuk histori demand. Tidak ada approval otomatis dan tidak ada
eksekusi: keputusan lahir `proposed`.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.ai_providers.forecast_client import (
    run_forecast,
    sap_rpt_caller_from_env,
)
from app.ai_providers.verifier_client import run_verifier
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Commodity, Decision, DemandRecord, Location
from app.services.supervisor_client import run_supervisor
from app.services.supplier_procurement import (
    evaluate_suppliers,
    persist_supplier_binding,
)
from app.services.trace_persistence import persist_trace_steps

DEFAULT_TTL_MINUTES = 30
FORECAST_HORIZON_DAYS = 7


@dataclass
class _TraceStep:
    step_name: str
    tool_called: str | None
    input_summary: dict | None
    output_summary: dict | None


def _attempt_dicts(attempts) -> list[dict]:
    return [
        {
            "name": getattr(a, "name", None),
            "outcome": getattr(a, "outcome", None),
            "category": getattr(a, "category", None),
        }
        for a in (attempts or [])
    ]


def _ringkas_tolak(kandidat: list[dict]) -> list[dict]:
    """Alasan pemasok tidak layak — dibawa ke pesan 409 supaya bisa dibuktikan."""
    return [
        {
            "supplier": k["supplier"],
            "excluded": k["excluded"],
            "reasons": k["reasons"],
        }
        for k in kandidat
        if not k["eligible"]
    ]


def _kalimat_tolak(ditolak: list[dict], batas_alasan: int = 2) -> str:
    """Alasan dalam kalimat yang bisa dibaca manusia (bukan repr list Python).

    Tetap menyebut sebab per pemasok: tanpa itu, pesan 409 hanya bilang
    "tidak ada" dan tidak bisa dibuktikan dari data.
    """
    bagian = []
    for baris in ditolak:
        alasan = "; ".join(baris["reasons"][:batas_alasan]) or "tidak tercatat"
        bagian.append(f"{baris['supplier']}: {alasan}")
    return "; ".join(bagian) if bagian else "tidak ada pemasok terdaftar"


async def _run_supplier_procurement(
    *,
    commodity: str,
    target_location: str,
    verifier_bedrock,
    ttl_minutes: int,
    demo_session_id: uuid.UUID | None = None,
) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    traces: list[_TraceStep] = []

    async with maker() as session:
        target = (
            await session.execute(
                select(Location).where(Location.name == target_location)
            )
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(f"lokasi SPPG {target_location!r} tidak ada di database")

        komoditas = (
            await session.execute(
                select(Commodity).where(Commodity.name == commodity)
            )
        ).scalar_one_or_none()
        if komoditas is None:
            raise ValueError(f"komoditas {commodity!r} tidak ada di database")

        penilaian = await evaluate_suppliers(
            session, target=target, commodity=commodity
        )
        kandidat = penilaian["candidates"]
        chosen = penilaian["chosen"]
        if chosen is None:
            ditolak = _ringkas_tolak(kandidat)
            raise ValueError(
                "tidak ada pemasok yang memasok "
                f"{target_location} untuk {commodity} yang bisa dikirim sekarang "
                f"({len(kandidat)} pemasok dinilai, 0 layak). "
                f"Alasan: {_kalimat_tolak(ditolak)}"
            )

        # DETECT -----------------------------------------------------------
        detect = {
            "commodity": commodity,
            "target_location": target_location,
            "supply_kg": penilaian["supply_kg"],
            "demand_kg": penilaian["demand_kg"],
            "gap_kg": penilaian["gap_kg"],
            "suppliers_total": penilaian["suppliers_total"],
            "suppliers_eligible": len(penilaian["ranked"]),
            "suppliers_rejected": _ringkas_tolak(kandidat),
        }
        traces.append(
            _TraceStep(
                "DETECT",
                "supply.get+demand.get+supplier.get",
                {"commodity": commodity, "target_location": target_location},
                detect,
            )
        )

        # VERIFY -----------------------------------------------------------
        ctx = {
            "decision_id": None,
            "commodity": commodity,
            "safety_status": chosen["safety_status"],
            "freshness_score": chosen["freshness_score"],
            "candidates": kandidat,
            "evidence": {
                "batch_ids": chosen["batch_ids"],
                "price_sources": ["pihps_reference", "supplier_quote"],
            },
            "logistics": {
                "distance_km": chosen["leg_km"],
                "time_min": None,
                "feasible": chosen["leg_km"] is not None,
            },
            "cost": {
                "safe_delivered_cost": chosen["safe_delivered_cost"],
                "breakdown": chosen["cost_breakdown"],
            },
            "rationale": (
                f"Pengadaan dari pemasok {chosen['supplier']} yang memasok "
                f"{target_location}: kekurangan {penilaian['gap_kg']} kg, "
                f"dipasok {chosen['quantity_kg']} kg"
            ),
        }
        verifier_result = run_verifier(ctx, bedrock=verifier_bedrock)
        verifier_payload = {
            "verdict": verifier_result.verdict,
            "reason": verifier_result.reason,
            "provider": verifier_result.provider,
            "fallback_used": verifier_result.fallback_used,
            "attempts": _attempt_dicts(verifier_result.attempts),
        }
        traces.append(
            _TraceStep(
                "VERIFY",
                "verifier.rest",
                {
                    "commodity": commodity,
                    "supplier": chosen["supplier"],
                    "safety_status": ctx["safety_status"],
                    "freshness_score": ctx["freshness_score"],
                },
                verifier_payload,
            )
        )

        # DECIDE: baris keputusan (id dipakai FK trace) ---------------------
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)
        # Status awal DITURUNKAN dari verdict verifier yang baru dihitung di
        # langkah VERIFY — bukan dari model, dan bukan `proposed` buta.
        #
        # Kenapa (regresi 28 Okt 2026): keputusan lahir `proposed` sementara
        # `verified_by`/`verifier_note` sudah terisi. Akibatnya `/actions/approve`
        # menolak ("status proposed tidak dapat di-approve") DAN `/actions/execute`
        # menolak ("status proposed tidak dapat dieksekusi") — satu-satunya jalan
        # keluar adalah memanggil `/actions/propose` lebih dulu, yang tidak
        # ditawarkan UI. Pemilik melihat "agent jalan tapi keputusannya tidak bisa
        # di-approve/execute".
        #
        # Aturannya sama dengan `/actions/verify` + `/actions/propose`:
        #   CONSISTENT → `pending_approval` (terverifikasi, siap disetujui)
        #   FLAGGED    → `verifier_flagged` (tetap boleh disetujui, dengan catatan)
        #   UNAVAILABLE→ tetap `proposed` (belum dinilai; verify masih boleh diulang)
        verdict = (verifier_result.verdict or "").upper()
        status_awal = {
            "CONSISTENT": "pending_approval",
            "FLAGGED": "verifier_flagged",
        }.get(verdict, "proposed")
        decision = Decision(
            id=uuid.uuid4(),
            decision_type="supplier_procurement",
            status=status_awal,
            proposed_by="supervisor_agent",
            verified_by="verifier_agent",
            verifier_note=verifier_result.verdict.lower(),
            # Baris ini lahir dari DEMO, bukan data kanonik: `origin='demo'`
            # adalah syarat yang membuat penjaga sesi (`boleh_distempel`,
            # `tandai_sesi`, `kosongkan_bertanda`) mau menghapusnya saat jendela
            # demo berakhir. Dengan default DB `'seed'`, keputusan hasil agent
            # hidup selamanya dan "data hilang saat demo habis" tidak terjadi.
            origin="demo",
            # Pengadaan tidak memindahkan stok SPPG lain: sisi asal = NULL.
            source_location_id=None,
            target_location_id=target.id,
            commodity_id=komoditas.id,
            supplier_id=uuid.UUID(chosen["supplier_id"]),
            quantity_kg=Decimal(str(chosen["quantity_kg"])),
            safe_delivered_cost=Decimal(str(chosen["safe_delivered_cost"])),
            cost_breakdown=chosen["cost_breakdown"],
            expires_at=expires_at,
            # Fase 2 MG: pemilik baris disebut pemanggil, bukan ditebak dari
            # "sesi aktif" oleh penjaga `before_flush`.
            demo_session_id=demo_session_id,
        )
        session.add(decision)
        await session.flush()

        await persist_supplier_binding(
            session,
            decision,
            supplier_id=chosen["supplier_id"],
            batch_ids=chosen["batch_ids"],
        )

        traces.append(
            _TraceStep(
                "TRACE",
                None,
                {"decision_id": str(decision.id)},
                {"steps_recorded": 6},
            )
        )

        # PREDICT: histori demand NYATA per (target, commodity) -------------
        history_rows = (
            (
                await session.execute(
                    select(DemandRecord)
                    .where(
                        DemandRecord.location_id == target.id,
                        DemandRecord.commodity_id == komoditas.id,
                    )
                    .order_by(DemandRecord.recorded_at.asc(), DemandRecord.id.asc())
                )
            )
            .scalars()
            .all()
        )
        history = [float(r.quantity_kg) for r in history_rows]
        if history:
            forecast = run_forecast(
                history,
                horizon_days=FORECAST_HORIZON_DAYS,
                sap_rpt=sap_rpt_caller_from_env(),
            )
            predict_out = {
                "forecast_qty_kg": forecast.forecast_qty_kg,
                "method": forecast.method,
                "provider": forecast.provider,
                "fallback_used": forecast.fallback_used,
                "attempts": _attempt_dicts(forecast.attempts),
            }
        else:
            predict_out = {
                "forecast_qty_kg": None,
                "method": "statistical_fallback",
                "provider": None,
                "fallback_used": True,
                "attempts": [],
                "note": "histori demand kosong; tanpa panggilan model",
            }
        traces.append(
            _TraceStep(
                "PREDICT",
                "forecast.provider",
                {
                    "history_points": len(history),
                    "horizon_days": FORECAST_HORIZON_DAYS,
                },
                predict_out,
            )
        )

        # OPTIMIZE (rekaman pemeringkatan pemasok deterministik) -----------
        traces.append(
            _TraceStep(
                "OPTIMIZE",
                "supplier.evaluate",
                {"commodity": commodity, "target_location": target_location},
                {
                    "chosen_supplier": chosen["supplier"],
                    "chosen_supplier_id": chosen["supplier_id"],
                    "rank": chosen["rank"],
                    "score": chosen["score"],
                    "safe_delivered_cost": chosen["safe_delivered_cost"],
                    "leg_km": chosen["leg_km"],
                    "available_kg": chosen["available_kg"],
                    "quote_price_per_kg": chosen["quote_price_per_kg"],
                    "reliability": chosen["reliability"],
                    "capacity_kg_per_week": chosen["capacity_kg_per_week"],
                    "candidates_total": len(kandidat),
                    "ranked": [
                        {
                            "rank": r["rank"],
                            "supplier": r["supplier"],
                            "score": r["score"],
                            "safe_delivered_cost": r["safe_delivered_cost"],
                        }
                        for r in penilaian["ranked"]
                    ],
                },
            )
        )

        # DECIDE (rekaman persist) -----------------------------------------
        traces.append(
            _TraceStep(
                "DECIDE",
                "POST /decisions",
                {"status": decision.status, "ttl_minutes": ttl_minutes},
                {
                    "decision_id": str(decision.id),
                    "expires_at": expires_at.isoformat(),
                    "approved": False,
                },
            )
        )

        # SUPERVISE --------------------------------------------------------
        supervise_out = run_supervisor(
            {
                "commodity": commodity,
                "target_location": target_location,
                "supplier": chosen["supplier"],
                "supplier_leg_km": chosen["leg_km"],
                "supplier_quote_per_kg": chosen["quote_price_per_kg"],
                "supplier_available_kg": chosen["available_kg"],
                "gap_kg": penilaian["gap_kg"],
                "verifier_verdict": verifier_result.verdict,
                "forecast": predict_out,
                "chosen": chosen,
            }
        )
        supervisor_payload = {
            "status": supervise_out.status,
            "summary": supervise_out.summary,
            "provider": supervise_out.provider,
            "fallback_used": supervise_out.fallback_used,
            "attempts": _attempt_dicts(supervise_out.attempts),
        }
        if supervise_out.status == "narrated":
            traces.append(
                _TraceStep(
                    "SUPERVISE",
                    "supervisor.narration",
                    {"decision_id": str(decision.id)},
                    supervisor_payload,
                )
            )

        for step in traces:
            persist_trace_steps(
                session,
                decision_id=str(decision.id),
                steps=[
                    {
                        "step_name": step.step_name,
                        "tool_called": step.tool_called,
                        "input_summary": step.input_summary,
                        "output_summary": step.output_summary,
                    }
                ],
            )

        await session.commit()

    return {
        "decision_id": str(decision.id),
        "mode": "supplier_procurement",
        "detect": detect,
        "verifier": verifier_payload,
        "forecast": predict_out,
        "supervisor": supervisor_payload,
        "suppliers": penilaian,
        "decision_snapshot": {
            "decision_id": str(decision.id),
            "status": decision.status,
            "approved": False,
            "expires_at": expires_at.isoformat(),
            "supplier": chosen["supplier"],
            "recommendation": chosen,
        },
        "trace_steps": [t.step_name for t in traces],
    }


def run_supplier_procurement(
    commodity: str,
    target_location: str,
    *,
    verifier_bedrock=None,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    demo_session_id: uuid.UUID | None = None,
) -> dict:
    """Jalankan pengadaan pemasok penuh; sync wrapper di atas sesi async.

    `demo_session_id` (Fase 2 MG) = sesi PEMILIK keputusan yang lahir di sini.
    """
    return asyncio.run(
        _run_supplier_procurement(
            commodity=commodity,
            target_location=target_location,
            verifier_bedrock=verifier_bedrock,
            ttl_minutes=ttl_minutes,
            demo_session_id=demo_session_id,
        )
    )
