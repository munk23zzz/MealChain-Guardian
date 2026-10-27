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
import os
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
from app.models import Commodity, Decision, DemandRecord, DemoSession, Location
from app.services import recommendation_service as rs
from app.services.agent_memory import catat_learn
from app.services.supervisor_client import run_supervisor
from app.services.trace_persistence import persist_trace_steps

DEFAULT_TTL_MINUTES = 30


def _memory_write_aktif() -> bool:
    """LEARN menulis AgentCore Memory hanya bila diminta eksplisit.

    Default MATI: demo tidak boleh bergantung pada izin AWS yang mungkin belum
    ada. Nyalakan dengan `AGENT_MEMORY_WRITE=1` setelah izin CreateEvent siap.
    """
    return os.environ.get("AGENT_MEMORY_WRITE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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


async def _jam_evaluasi(session, demo_session_id) -> datetime | None:
    """Jam evaluasi Event 1: sesi yang MEMINTA, atau sesi yang sedang aktif.

    Dataset demo adalah dataset replay berjangkar kanon (2026-10-08 12:00).
    Menilainya dengan jam dinding membuat bukti suhu yang sah terbaca basi dan
    seluruh kandidat tertahan gate Fase 6 — di dalam aplikasi itu tidak terjadi
    karena selalu ada sesi aktif, tetapi Event 1 yang dipanggil tanpa sesi harus
    memakai jangkar yang sama dengan sesi aktif, bukan jam dinding.
    Tanpa sesi sama sekali: `None` = jam dinding (perilaku lama, jujur).
    """
    try:
        if demo_session_id is not None:
            baris = (
                await session.execute(
                    select(DemoSession).where(DemoSession.id == demo_session_id)
                )
            ).scalar_one_or_none()
            anchor = getattr(baris, "evaluation_anchor", None)
            if anchor is not None:
                return anchor
        aktif = (
            await session.execute(
                select(DemoSession)
                .where(DemoSession.status == "active")
                .order_by(DemoSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        anchor = getattr(aktif, "evaluation_anchor", None)
        if anchor is not None:
            return anchor
        # Tanpa sesi aktif: JAM DINDING (`None`), persis perilaku sebelum
        # fungsi ini ada. Jangkar kanon TIDAK boleh dipakai sebagai cadangan:
        # deret batch demo disemai relatif "sekarang" (panen -5..-34 jam),
        # sehingga evaluasi pada 2026-10-08 12:00 tidak melihat satu batch pun
        # (`Batch.harvested_at <= as_of` kosong) dan Event 1 mati dengan
        # "tidak ada kandidat eligible" — terukur pada 9 tes
        # `tests/test_event1_supervisor_flow.py` (27 Okt 2026).
        return None
    except Exception:  # noqa: BLE001 - jam evaluasi tidak boleh menggagalkan alur
        return None


async def _run_event1(
    *,
    commodity: str,
    target_location: str,
    verifier_bedrock,
    safety_status_override: str | None,
    ttl_minutes: int,
    demo_session_id: uuid.UUID | None = None,
) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    traces: list[_TraceStep] = []
    memori: dict | None = None

    async with maker() as session:
        # Jam evaluasi mengikuti SESI bila ada: dataset replay berjangkar
        # kanon (2026-10-08 12:00), jadi menilai dengan jam dinding membuat
        # bukti suhu yang sah terbaca "basi" dan seluruh kandidat tertahan.
        # Tanpa sesi, perilaku lama (jam dinding) dipertahankan.
        as_of = await _jam_evaluasi(session, demo_session_id)

        # OPTIMIZE input = pipeline rekomendasi deterministik (tool sama
        # dengan POST /balance/recommend).
        async def _fetch():
            return await rs.fetch_operational_facts(session, as_of)

        out = await rs.build_recommendations(_fetch, as_of=as_of)
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
            # Verdict verifier yang baru saja berjalan TERTULIS saat
            # pembuatan (semantik identik /actions/verify) — tanpa ini
            # decision hasil Event 1 dianggap belum terverifikasi selamanya.
            verified_by="verifier_agent",
            verifier_note=verifier_result.verdict.lower(),
            source_location_id=await _loc_id(
                chosen["candidate"]["source_location"]
            ),
            target_location_id=await _loc_id(target_location),
            commodity_id=await _com_id(commodity),
            quantity_kg=Decimal(chosen["candidate"]["quantity_kg"]),
            safe_delivered_cost=Decimal(chosen["safe_delivered_cost"]),
            cost_breakdown=chosen.get("cost_breakdown"),
            expires_at=expires_at,
            # Identitas pemasok ikut tersimpan. Tanpa ini keputusan hasil
            # Event 1 lahir tanpa supplier_id dan kartu Identitas menulis
            # "tanpa identitas pemasok" untuk transfer yang jelas berasal dari
            # satu pemasok (temuan audit 19 Okt 2026).
            supplier_id=(
                uuid.UUID(chosen["candidate"]["supplier_id"])
                if chosen["candidate"].get("supplier_id")
                else None
            ),
            # Fase 2 MG: kepemilikan baris eksplisit. Tanpa ini keputusan hasil
            # analisis hanya "milik sesi yang kebetulan aktif" — dan begitu sesi
            # lain dibuka, baris ini tidak bisa lagi dibedakan pemiliknya.
            demo_session_id=demo_session_id,
        )
        session.add(decision)
        await session.flush()

        from app.services.supplier_eligibility import persist_binding
        await persist_binding(session, decision, chosen["candidate"])

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
                history,
                horizon_days=FORECAST_HORIZON_DAYS,
                # S4-10: provider NYATA bila env SAP AI Core lengkap; None
                # (env kosong/tes terisolasi) → chain/statistik seperti sebelumnya.
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

        # SUPERVISE (narasi akhir, bukan safety-critical — tidak mengubah
        # verdict/rekomendasi/angka apa pun; model mati → jujur dijelaskan,
        # decision tetap lahir)
        supervise_out = run_supervisor(
            {
                "commodity": commodity,
                "target_location": target_location,
                "surplus": detect["surplus"],
                "shortage": detect["shortage"],
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

        # ------------------------------------------------------------------
        # LEARN (Fase 11 MG): simpan pelajaran yang sudah disanitasi ke AgentCore
        # Memory — HANYA bila `AGENT_MEMORY_WRITE=1`. Dijalankan SESUDAH commit
        # supaya panggilan jaringan tidak menahan transaksi DB, dan kegagalannya
        # hanya menjadi status di jejak: verdict, rekomendasi, dan angka tidak
        # boleh berubah karena Memory (gerbang butir 6).
        # ------------------------------------------------------------------
        if _memory_write_aktif():
            memori = await asyncio.to_thread(
                catat_learn,
                f"{demo_session_id or 'sesi-lokal'}:{decision.id}",
                "learn",
                {
                    "decision_id": str(decision.id),
                    "commodity": commodity,
                    "target_location": target_location,
                    "verifier_verdict": verifier_result.verdict,
                    "chosen_candidate_id": chosen["candidate_id"],
                    "safe_delivered_cost": chosen["safe_delivered_cost"],
                    "surplus": detect.get("surplus"),
                    "shortage": detect.get("shortage"),
                },
            )
            persist_trace_steps(
                session,
                decision_id=str(decision.id),
                steps=[
                    {
                        "step_name": "LEARN",
                        "tool_called": "agentcore.memory.write",
                        "input_summary": {"key": "learn", "decision_id": str(decision.id)},
                        "output_summary": memori,
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
        "supervisor": supervisor_payload,
        "recommendations": recommendations,
        "decision_snapshot": {
            "decision_id": str(decision.id),
            "status": decision.status,
            "approved": False,
            "expires_at": expires_at.isoformat(),
            "recommendation": chosen,
        },
        "kpi": kpi,
        # Fase 11: status tulis Memory (None = fitur mati, bukan "gagal").
        "memory": memori,
        "trace_steps": [t.step_name for t in traces],
    }


def run_event1(
    commodity: str,
    target_location: str,
    *,
    verifier_bedrock=None,
    safety_status_override: str | None = None,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    demo_session_id: uuid.UUID | None = None,
) -> dict:
    """Jalankan Event 1 penuh; sync wrapper di atas sesi async.

    `demo_session_id` (Fase 2 MG) = sesi PEMILIK keputusan yang lahir di sini.
    Diteruskan apa adanya: pemanggil yang menentukan sesi, bukan penjaga
    `before_flush` yang menebaknya dari sesi aktif.
    """
    return asyncio.run(
        _run_event1(
            commodity=commodity,
            target_location=target_location,
            verifier_bedrock=verifier_bedrock,
            safety_status_override=safety_status_override,
            ttl_minutes=ttl_minutes,
            demo_session_id=demo_session_id,
        )
    )
