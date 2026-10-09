"""Event 3 — Safety Disruption (Sprint 4, plan §S4-02 + prompt Owner §18–22).

Alur deterministik:
  temperature_log persisted
    → evaluate_safety (core Sprint 1, ambang 30 menit terkunci)
    → batch FAIL dipersist DULU (commit #1 — boundary plan §11:
      status FAIL tidak boleh hilang walau optimisasi gagal)
    → re-optimasi (build_recommendations reuse; kandidat FAIL otomatis
      skor 0 & ter-exclude oleh core)
    → alternatif eligible? ya → Decision safety_disruption + evidence
      temperature + trace DETECT/OPTIMIZE (commit #2)
      tidak → Event3NoAlternativeError (409 di API), tanpa decision write.

Lineage (ruling O-EVENT-2): previous_decision_id dicatat pada evidence
`temperature` dan response — supersedes_id TIDAK dipalsukan; old decision
tidak dimutasi. Execute revalidation (safety terkini dari batch sumber)
dilakukan di lapis API actions.

LLM tidak pernah menghitung safety — seluruh nilai dari modul deterministik.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.safety import evaluate_safety
from app.models import (
    Batch,
    Decision,
    DecisionEvidence,
)
from app.services.recommendation_service import build_recommendations
from app.services.trace_persistence import persist_trace_steps

_DEFAULT_TTL_MINUTES = 30
_DEFAULT_FACTS = staticmethod(None)  # placeholder agar ruff tidy tetap tenang


class Event3ConflictError(Exception):
    """operation_key sudah dipakai untuk batch berbeda (→ 409)."""


class Event3NoAlternativeError(Exception):
    """Tidak ada alternatif eligible pasca-exclude (→ 409 di API)."""


async def _evaluate_batch_safety(batch: Batch) -> dict:
    """Evaluasi deterministik temperature_log via core Sprint 1."""
    return evaluate_safety(
        batch.temperature_log or [],
        safe_min_c=0.0,
        safe_max_c=8.0,
        max_excursion_minutes=30.0,
    )


async def _find_replay(
    db: AsyncSession, operation_key: str
) -> tuple[Decision, dict] | None:
    """Cari event sebelumnya dengan operation_key sama (trace DETECT)."""
    row = (
        await db.execute(
            text(
                "SELECT t.decision_id FROM agent_traces t "
                "JOIN decisions d ON d.id = t.decision_id "
                "WHERE t.step_name = 'DETECT' "
                "AND t.tool_called = 'evaluate_safety' "
                "AND t.input_summary->>'operation_key' = :k "
                "ORDER BY t.step_at DESC LIMIT 1"
            ),
            {"k": operation_key},
        )
    ).fetchone()
    if row is None:
        return None
    decision = (
        await db.execute(select(Decision).where(Decision.id == row[0]))
    ).scalar_one_or_none()
    if decision is None:
        return None
    ev = (
        await db.execute(
            select(DecisionEvidence).where(
                DecisionEvidence.decision_id == decision.id,
                DecisionEvidence.evidence_type == "temperature",
            )
        )
    ).scalars()
    ev_row = ev.first()
    payload = (ev_row.payload if ev_row else {}) or {}
    outcome = {
        "status": payload.get("outcome_status", "revised"),
        "decision_id": str(decision.id),
        "event_type": "safety_disruption",
        "batch_id": payload.get("batch_id"),
        "safety_status": payload.get("safety_status"),
        "evaluation": {
            "safety_status": payload.get("safety_status"),
            "excursion_minutes": payload.get("excursion_minutes"),
        },
        "excursion_minutes": payload.get("excursion_minutes"),
        "excluded_batch_ids": payload.get("excluded_batch_ids") or [],
        "previous_decision_id": payload.get("previous_decision_id"),
        "recommended_candidate": payload.get("recommended_candidate"),
        "message": "Replay: event safety disruption sudah tercatat",
    }
    return decision, outcome


async def run_safety_disruption_event(
    batch_id: uuid.UUID,
    target_location_id: uuid.UUID,
    operation_key: uuid.UUID,
    previous_decision_id: uuid.UUID | None,
    actor_id: str | None,
    db: AsyncSession,
    fetch_facts=None,
) -> dict:
    """Pipeline Event 3; session DI-COMMIT di sini (dua boundary).

    Commit #1: evaluasi + persist batch.safety_status (FAIL tahan bencana).
    Commit #2: decision + evidence + trace bila ada alternatif eligible.
    """
    op_key = str(operation_key)

    # ---- Kunci serialisasi lintas request (pola Event 2, footnote §11).
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": op_key}
    )

    # ---- Replay: key sama → batch sama; batch beda → 409.
    replay = await _find_replay(db, op_key)
    if replay is not None:
        _decision, outcome = replay
        if outcome.get("batch_id") != str(batch_id):
            raise Event3ConflictError(
                "operation_key sudah dipakai untuk batch berbeda"
            )
        await db.rollback()
        return outcome

    # ---- Load batch + lokasi komoditas (untuk evidence & revalidation).
    batch = (
        await db.execute(select(Batch).where(Batch.id == batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise LookupError("batch tidak ditemukan")

    # Commit #1 — evaluasi deterministik + persist status FAIL/otherwise.
    raw_log = batch.temperature_log or []
    temp_result = evaluate_safety(
        raw_log,
        safe_min_c=0.0,
        safe_max_c=8.0,
        max_excursion_minutes=30.0,
    )
    batch.safety_status = temp_result["safety_status"]
    await db.commit()

    # Kondisi berhenti dini: batch ternyata aman → bukan event 3.
    if temp_result["safety_status"] != "fail":
        no_event = {
            "status": "no_disruption",
            "decision_id": None,
            "event_type": "safety_disruption",
            "batch_id": str(batch.id),
            "safety_status": temp_result["safety_status"],
            "evaluation": {
                "safety_status": temp_result["safety_status"],
                "excursion_minutes": float(temp_result["excursion_minutes"]),
            },
            "excursion_minutes": float(temp_result["excursion_minutes"]),
            "excluded_batch_ids": [],
            "previous_decision_id": (
                str(previous_decision_id) if previous_decision_id else None
            ),
            "message": "Tidak ada gangguan keamanan pangan (batch aman)",
        }
        await db.rollback()
        return no_event

    # ---- Re-optimasi deterministik (reuse pipeline Event 1).
    if fetch_facts is None:
        from app.core.config import settings
        from app.db import create_engine as _mk_engine
        from app.db import create_session_maker as _mk_session
        from app.services import recommendation_service as _rs

        _engine = _mk_engine(settings.database_url)
        _maker = _mk_session(_engine)

        async def _default_fetch():
            async with _maker() as _session:
                return await _rs.fetch_operational_facts(_session, None)

        fetch_facts = _default_fetch
    result = await build_recommendations(fetch_facts)
    recommendations = result.get("recommendations", [])

    eligible = [r for r in recommendations if r.get("eligible")]
    if not eligible:
        # FAIL sudah terpersist (commit #1); tanpa decision write.
        raise Event3NoAlternativeError(
            "Tidak ada alternatif eligible setelah batch fail di-exclude"
        )

    top = eligible[0]
    exc_min = float(temp_result["excursion_minutes"])
    message = (
        f"Batch excluded: temperature excursion {exc_min:.0f} menit "
        f"melebihi ambang 30 menit. Safety status: FAIL. "
        f"Eligibility: 0. Alternatif aman: "
        f"{top['candidate']['source_location']} → "
        f"{top['candidate']['destination_location']}."
    )

    # ---- Commit #2: Decision + evidence + trace.
    decision = Decision(
        decision_type="safety_disruption",
        status="proposed",
        proposed_by=actor_id or "event3_pipeline",
        target_location_id=target_location_id,
        source_location_id=batch.location_id,
        commodity_id=batch.commodity_id,
        quantity_kg=Decimal(str(batch.quantity_kg)),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=_DEFAULT_TTL_MINUTES),
        cost_breakdown={
            "candidate_score": str(top.get("score")),
            "safe_delivered_cost": str(top.get("safe_delivered_cost")),
            "cost_breakdown": top.get("cost_breakdown", {}),
        },
    )
    db.add(decision)
    await db.flush()

    prev_id = str(previous_decision_id) if previous_decision_id else None
    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="temperature",
            payload={
                "batch_id": str(batch.id),
                "safety_status": temp_result["safety_status"],
                "excursion_minutes": exc_min,
                "rule": temp_result.get("rule"),
                "excluded_batch_ids": [str(batch.id)],
                "previous_decision_id": prev_id,
                "outcome_status": "revised",
                "recommended_candidate": top["candidate"],
                "synthetic": False,
            },
            is_consistent=None,
        )
    )
    persist_trace_steps(
        db,
        decision_id=str(decision.id),
        steps=[
            {
                "step_name": "DETECT",
                "tool_called": "evaluate_safety",
                "input_summary": {
                    "operation_key": op_key,
                    "batch_id": str(batch.id),
                    "previous_decision_id": prev_id,
                },
                "output_summary": {
                    "safety_status": temp_result["safety_status"],
                    "excursion_minutes": exc_min,
                    "rule": temp_result.get("rule"),
                },
            },
            {
                "step_name": "OPTIMIZE",
                "tool_called": "build_recommendations",
                "input_summary": {
                    "excluded_batch_ids": [str(batch.id)],
                },
                "output_summary": {
                    "recommended_candidate": {
                        "source_location": top["candidate"][
                            "source_location"
                        ],
                        "destination_location": top["candidate"][
                            "destination_location"
                        ],
                        "commodity": top["candidate"]["commodity"],
                        "score": str(top.get("score")),
                    },
                    "eligible_count": len(eligible),
                },
            },
        ],
    )
    await db.commit()

    cand = top["candidate"]
    return {
        "status": "revised",
        "decision_id": str(decision.id),
        "event_type": "safety_disruption",
        "batch_id": str(batch.id),
        "safety_status": temp_result["safety_status"],
        "evaluation": {
            "safety_status": temp_result["safety_status"],
            "excursion_minutes": exc_min,
            "reasons": temp_result.get("reasons", []),
        },
        "excursion_minutes": exc_min,
        "excluded_batch_ids": [str(batch.id)],
        "previous_decision_id": prev_id,
        "recommended_candidate": {
            "source_location": cand["source_location"],
            "destination_location": cand["destination_location"],
            "commodity": cand["commodity"],
            "quantity_kg": str(cand["quantity_kg"]),
            "score": str(top.get("score")),
            "safe_delivered_cost": str(top.get("safe_delivered_cost")),
        },
        "message": message,
        "verifier": "pending",
    }
