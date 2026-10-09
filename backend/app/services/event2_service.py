"""Event 2 service — price anomaly (S4-01, plan §11).

Deterministik: semua angka dari `app.core.price.price_deviation` (5%/15%)
dan PriceSignal di DB. Tidak ada angka dari browser/LLM. Persist Decision
(`price_anomaly`) + DecisionEvidence + AgentTrace. TIDAK membuat PO
(review-only, ruling O-PO).

Idempoten tanpa tabel baru (footnote §11): kunci paralel via
`pg_advisory_xact_lock`, replay dideteksi dari trace DETECT yang menyimpan
`operation_key` pada `input_summary`. Payload beda dengan key sama → 409.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.price import price_deviation
from app.models import (
    Commodity,
    Decision,
    DecisionEvidence,
    Location,
    PriceSignal,
    Supplier,
)
from app.services.trace_persistence import persist_trace_steps


class Event2ConflictError(Exception):
    """operation_key sudah dipakai dengan payload berbeda (→ 409)."""


class Event2NotFoundError(Exception):
    """quote/reference/location tidak ditemukan (→ 404)."""


_DEFAULT_TTL_MINUTES = 30


def _deviation_message(dev_pct: Decimal, status: str) -> str:
    arah = "di atas" if dev_pct > 0 else "di bawah"
    return (
        f"Procurement price deviation detected — review required "
        f"(kutipan {arah} referensi {abs(dev_pct):.2f}%, status: {status})"
    )


async def _load_pair(
    db: AsyncSession, quote_id: uuid.UUID, target_location_id: uuid.UUID
) -> tuple[PriceSignal, PriceSignal, Location, Commodity, Supplier | None]:
    """Resolve pasangan quote/reference + entitas terkait dari DB saja."""
    quote = (
        await db.execute(
            select(PriceSignal).where(
                PriceSignal.id == quote_id,
                PriceSignal.source == "supplier_quote",
            )
        )
    ).scalar_one_or_none()
    if quote is None:
        raise Event2NotFoundError("supplier quote tidak ditemukan")
    target = (
        await db.execute(select(Location).where(Location.id == target_location_id))
    ).scalar_one_or_none()
    if target is None:
        raise Event2NotFoundError("target location tidak ditemukan")
    commodity = (
        await db.execute(select(Commodity).where(Commodity.id == quote.commodity_id))
    ).scalar_one_or_none()
    if commodity is None:
        raise Event2NotFoundError("commodity tidak ditemukan")
    # Reference: pihps_reference TERBARU untuk lokasi+komoditas yang sama
    # dengan quote (mencegah pencampuran harga lintas lokasi — risk §S4-01).
    ref = (
        (
            await db.execute(
                select(PriceSignal)
                .where(
                    PriceSignal.location_id == quote.location_id,
                    PriceSignal.commodity_id == quote.commodity_id,
                    PriceSignal.source == "pihps_reference",
                )
                .order_by(PriceSignal.recorded_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if ref is None:
        raise Event2NotFoundError(
            "reference price (pihps_reference) tidak tersedia untuk "
            "lokasi/komoditas quote"
        )
    supplier = None
    if quote.supplier_id is not None:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.id == quote.supplier_id))
        ).scalar_one_or_none()
    return quote, ref, target, commodity, supplier


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
                "AND t.tool_called = 'price_deviation' "
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
                DecisionEvidence.evidence_type == "market_price",
            )
        )
    ).scalars()
    ev_row = ev.first()
    payload = (ev_row.payload if ev_row else {}) or {}
    outcome = {
        "status": "anomaly",
        "decision_id": str(decision.id),
        "event_type": "price_anomaly",
        "deviation_pct": payload.get("deviation_pct"),
        "classification": payload.get("classification"),
        "quote_id": payload.get("source_record_id"),
        "reference_id": payload.get("reference_record_id"),
        "supplier_id": payload.get("supplier_id"),
        "message": _deviation_message(
            Decimal(payload["deviation_pct"]), payload.get("classification", "anomalous")
        )
        if payload.get("deviation_pct")
        else "Procurement price deviation detected — review required",
        "verifier": "pending",
    }
    return decision, outcome


async def run_price_anomaly_event(
    quote_id: uuid.UUID,
    target_location_id: uuid.UUID,
    operation_key: uuid.UUID,
    actor_id: str | None,
    db: AsyncSession,
) -> dict:
    """Analisis pasangan quote/reference; persist bila anomali; replay aman.

    Session DI-COMMIT di sini (satu transaksi: lock → lookup → persist).
    """
    op_key = str(operation_key)

    # Kunci serialisasi lintas worker/request (footnote §11: DB transaction
    # lock keyed operation, lalu recheck persisted operation key).
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": op_key}
    )

    # Replay: key sama → resource sama; payload beda → 409.
    replay = await _find_replay(db, op_key)
    if replay is not None:
        _decision, outcome = replay
        if outcome.get("quote_id") != str(quote_id):
            raise Event2ConflictError(
                "operation_key sudah dipakai untuk quote berbeda"
            )
        # outcome sudah plain-dict (tak ada akses ORM setelah rollback).
        await db.rollback()
        return outcome

    quote, ref, target, commodity, supplier = await _load_pair(
        db, quote_id, target_location_id
    )
    dev = price_deviation(quote.price_per_kg, ref.price_per_kg)
    dev_pct: Decimal = dev["deviation_pct"].quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    status = dev["status"]

    if status == "normal":
        # No-anomaly: tanpa write apa pun (200, decision_id null).
        # Nilai dibaca SEBELUM rollback (atribut ORM expired setelahnya).
        no_anomaly = {
            "status": "no_anomaly",
            "decision_id": None,
            "event_type": "price_anomaly",
            "deviation_pct": str(dev_pct),
            "classification": status,
            "quote_id": str(quote.id),
            "reference_id": str(ref.id),
            "message": _deviation_message(dev_pct, status),
        }
        await db.rollback()
        return no_anomaly

    message = _deviation_message(dev_pct, status)
    decision = Decision(
        decision_type="price_anomaly",
        status="proposed",
        proposed_by=actor_id or "event2_pipeline",
        target_location_id=target.id,
        source_location_id=quote.location_id,
        commodity_id=commodity.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=_DEFAULT_TTL_MINUTES),
        cost_breakdown={
            "reference_price_per_kg": str(ref.price_per_kg),
            "quoted_price_per_kg": str(quote.price_per_kg),
            "deviation_pct": str(dev_pct),
            "classification": status,
        },
    )
    db.add(decision)
    await db.flush()

    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="market_price",
            payload={
                "source_record_id": str(quote.id),
                "source_kind": "supplier_quote",
                "reference_record_id": str(ref.id),
                "reference_kind": "pihps_reference",
                "supplier_id": (
                    str(quote.supplier_id) if quote.supplier_id else None
                ),
                "supplier_name": supplier.name if supplier else None,
                "quoted_price_per_kg": str(quote.price_per_kg),
                "reference_price_per_kg": str(ref.price_per_kg),
                "deviation_pct": str(dev_pct),
                "classification": status,
                "recorded_at": (
                    quote.recorded_at.isoformat() if quote.recorded_at else None
                ),
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
                "tool_called": "price_deviation",
                "input_summary": {
                    "operation_key": op_key,
                    "quote_id": str(quote.id),
                    "reference_id": str(ref.id),
                },
                "output_summary": {
                    "deviation_pct": str(dev_pct),
                    "status": status,
                    "flagged": dev["flagged"],
                },
            }
        ],
    )
    await db.commit()

    return {
        "status": "anomaly",
        "decision_id": str(decision.id),
        "event_type": "price_anomaly",
        "deviation_pct": str(dev_pct),
        "classification": status,
        "quote_id": str(quote.id),
        "reference_id": str(ref.id),
        "supplier_id": str(quote.supplier_id) if quote.supplier_id else None,
        "message": message,
        "verifier": "pending",
    }
