"""Event 1 orchestrator (S3-04) — DETECT→VERIFY→TRACE→PREDICT→OPTIMIZE→DECIDE.

Semua angka safety-critical bersumber dari tools deterministik backend:
- DETECT/OPTIMIZE dari rekomendasi `recommendation_service` (satu sumber
  dengan /balance/recommend — Supervisor tidak menghitung ulang apa pun);
- VERIFY memakai `run_verifier` (S3-06) — provider kosong → UNAVAILABLE;
- PREDICT memakai `run_forecast` (S3-07) dengan fallback statistik core;
- DECIDE menyimpan Decision berstatus `proposed` + AgentTrace bernama
  ASLI per langkah. Tidak ada approval otomatis, tidak ada eksekusi.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.ai_providers.forecast_client import run_forecast
from app.ai_providers.verifier_client import run_verifier
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Commodity, Decision, DemandRecord, Location
from app.services import recommendation_service as rs
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
    """ProviderAttempt → dict JSON-aman (tanpa error mentah berlebih)."""
    return [
        {
            "name": getattr(a, "name", None),
            "outcome": getattr(a, "outcome", None),
            "category": getattr(a, "category", None),
        }
        for a in (attempts or [])
    ]


def _detect_payload(recommendations: list[dict], commodity: str,
                    target_location: str, chosen: dict) -> dict:
    """Hasil DETECT: baris kandidat engine + sisi surplus/shortage.

    Quantity surplus/shortage = quantity movement yang direkomendasikan
    engine deterministik — bukan angka baru hasil hitung orchestrator.
    """
    rows = [
        {
            "source_location": r["candidate"]["source_location"],
            "destination_location": r["candidate"]["destination_location"],
            "quantity_kg": r["candidate"]["quantity_kg"],
            "eligible": r["eligible"],
            "rank": r.get("rank"),
        }
        for r in recommendations
        if r["candidate"]["commodity"] == commodity
    ]
    return {
        "commodity": commodity,
        "target_location": target_location,
        "candidates": rows,
        "surplus": {
            "location": chosen["candidate"]["source_location"],
            "quantity_kg": chosen["candidate"]["quantity_kg"],
        },
        "shortage": {
            "location": target_location,
            "quantity_kg": chosen["candidate"]["quantity_kg"],
        },
    }


async def _run_event1(
    *,
    commodity: str,
    target_location: str,
    verifier_bedrock,
    safety_status_override: str | None,
    ttl_minutes: int,
) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    traces: list[_TraceStep] = []

    async with maker() as session:
        # OPTIMIZE input = pipeline rekomendasi deterministik (tool sama
        # dengan POST /balance/recommend).
        async def _fetch():
            return await rs.fetch_operational_facts(session, None)

        out = await rs.build_recommendations(_fetch)
        recommendations: list[dict] = out["recommendations"]

        pool = [
            r
            for r in recommendations
            if r["candidate"]["commodity"] == commodity
            and r["candidate"]["destination_location"] == target_location
        ]
        eligible_pool = [r for r in pool if r["eligible"]]
        if not eligible_pool:
            raise ValueError(
                "tidak ada kandidat eligible untuk Event 1 "
                f"({commodity} -> {target_location}); decision tidak dibuat"
            )
        chosen = min(eligible_pool, key=lambda r: r["rank"])

        # DETECT ------------------------------------------------------------
        detect = _detect_payload(recommendations, commodity, target_location,
                                 chosen)
        traces.append(
            _TraceStep(
                "DETECT",
                "supply.get+demand.get",
                {"commodity": commodity, "target_location": target_location},
                detect,
            )
        )

        # VERIFY ------------------------------------------------------------
        ctx = {
            "decision_id": None,
            "commodity": commodity,
            "safety_status": safety_status_override
            or chosen["candidate"]["safety_status"],
            "freshness_score": chosen["candidate"]["freshness_score"],
            "candidates": [r["candidate"] for r in eligible_pool],
            "evidence": chosen.get("evidence"),
            "logistics": {
                "distance_km": chosen["candidate"]["logistics_distance_km"],
                "time_min": chosen["candidate"]["logistics_time_min"],
                "feasible": chosen["candidate"]["logistics_feasible"],
            },
            "cost": {
                "safe_delivered_cost": chosen["safe_delivered_cost"],
                "breakdown": chosen.get("cost_breakdown"),
            },
            "rationale": (
                "Event 1 regional imbalance: surplus "
                f"{chosen['candidate']['source_location']} -> shortage "
                f"{target_location}"
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
                    "safety_status": ctx["safety_status"],
                    "freshness_score": ctx["freshness_score"],
                },
                verifier_payload,
            )
        )

        # DECIDE: id diperlukan FK trace → buat decision dulu (flush).
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)

        async def _loc_id(name: str | None):
            if not name:
                return None
            row = (
                await session.execute(
                    select(Location).where(Location.name == name)
                )
            ).scalar_one_or_none()
            return row.id if row else None

        async def _com_id(name: str):
            row = (
                await session.execute(
                    select(Commodity).where(Commodity.name == name)
                )
            ).scalar_one_or_none()
            return row.id if row else None

        decision = Decision(
            id=uuid.uuid4(),
            decision_type="regional_balance",
            status="proposed",
            proposed_by="supervisor_agent",
            source_location_id=await _loc_id(
                chosen["candidate"]["source_location"]
            ),
            target_location_id=await _loc_id(target_location),
            commodity_id=await _com_id(commodity),
            quantity_kg=Decimal(chosen["candidate"]["quantity_kg"]),
            safe_delivered_cost=Decimal(chosen["safe_delivered_cost"]),
            cost_breakdown=chosen.get("cost_breakdown"),
            expires_at=expires_at,
        )
        session.add(decision)
        await session.flush()

        # TRACE (rekaman langkah; step itu sendiri sudah berjalan di atas)
        traces.append(
            _TraceStep(
                "TRACE",
                None,
                {"decision_id": str(decision.id)},
                {"steps_recorded": 6},
            )
        )

        # PREDICT: histori demand NYATA per (target, commodity) dari DB.
        demand_rows = (
            await session.execute(
                select(DemandRecord)
                .where(
                    DemandRecord.location_id == decision.target_location_id,
                    DemandRecord.commodity_id == decision.commodity_id,
                )
                .order_by(
                    DemandRecord.recorded_at.asc(), DemandRecord.id.asc()
                )
            )
        ).scalars().all()
        history = [float(r.quantity_kg) for r in demand_rows]
        if history:
            forecast = run_forecast(
                history, horizon_days=FORECAST_HORIZON_DAYS
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

        # OPTIMIZE (rekaman hasil pemilihan kandidat deterministik)
        traces.append(
            _TraceStep(
                "OPTIMIZE",
                "balance.recommend",
                {"commodity": commodity, "target_location": target_location},
                {
                    "chosen_candidate_id": chosen["candidate_id"],
                    "rank": chosen["rank"],
                    "score": chosen["score"],
                    "safe_delivered_cost": chosen["safe_delivered_cost"],
                },
            )
        )

        # DECIDE (rekaman persist; tanpa approval, tanpa eksekusi)
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

    kpi = {
        "candidates_total": len(recommendations),
        "eligible": sum(1 for r in recommendations if r.get("eligible")),
        "review_required": sum(
            1 for r in recommendations if r.get("review_required")
        ),
        "flagged_price": sum(
            1
            for r in recommendations
            if (r.get("price_anomaly") or {}).get("flagged")
        ),
    }

    return {
        "decision_id": str(decision.id),
        "detect": detect,
        "verifier": verifier_payload,
        "forecast": predict_out,
        "recommendations": recommendations,
        "decision_snapshot": {
            "decision_id": str(decision.id),
            "status": decision.status,
            "approved": False,
            "expires_at": expires_at.isoformat(),
            "recommendation": chosen,
        },
        "kpi": kpi,
        "trace_steps": [t.step_name for t in traces],
    }


def run_event1(
    commodity: str,
    target_location: str,
    *,
    verifier_bedrock=None,
    safety_status_override: str | None = None,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> dict:
    """Jalankan Event 1 penuh; sync wrapper di atas sesi async."""
    return asyncio.run(
        _run_event1(
            commodity=commodity,
            target_location=target_location,
            verifier_bedrock=verifier_bedrock,
            safety_status_override=safety_status_override,
            ttl_minutes=ttl_minutes,
        )
    )
