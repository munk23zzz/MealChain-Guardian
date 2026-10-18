"""Trace persistence (S3-10) — satu row per langkah aktual, tersanitasi."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentTrace
from app.services.agent_memory import sanitize_memory_payload

_VALID_STEPS = frozenset(
    {"DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE",
     "SUPERVISE", "ACT", "LEARN"}
)


def persist_trace_steps(
    session: AsyncSession,
    *,
    decision_id: str,
    steps: list[dict[str, Any]],
) -> int:
    """Tulis langkah trace aktual; kembalikan jumlah row.

    - payload input/output disanitasi dari secret sebelum masuk DB;
    - step_name di luar whitelist → ValueError eksplisit (tidak didrop
      diam-diam); seluruh batch tidak tertulis.
    """
    sanitized: list[AgentTrace] = []
    base_ts = datetime.now(timezone.utc)
    for index, step in enumerate(steps):
        step_name = (step.get("step_name") or "").strip()
        if step_name not in _VALID_STEPS:
            raise ValueError(
                f"step_name trace tidak valid: {step.get('step_name')!r}"
            )
        run_id = step.get("run_id")
        if run_id is not None:
            run_id = str(run_id)
            try:
                uuid.UUID(run_id)
            except (ValueError, AttributeError, TypeError) as exc:
                raise ValueError(
                    f"run_id trace tidak valid: {step.get('run_id')!r}"
                ) from exc
        sanitized.append(
            AgentTrace(
                decision_id=decision_id,
                step_name=step_name,
                tool_called=step.get("tool_called"),
                input_summary=sanitize_memory_payload(
                    step.get("input_summary")
                ),
                output_summary=sanitize_memory_payload(
                    step.get("output_summary")
                ),
                duration_ms=step.get("duration_ms"),
                run_id=run_id,
                agent_name=step.get("agent_name"),
                confidence=step.get("confidence"),
                citations=sanitize_memory_payload(step.get("citations")),
                # timestamp monoton per indeks agar urutan timeline
                # dapat di-replay (satu transaksi = now() DB identik)
                step_at=base_ts + timedelta(microseconds=index),
            )
        )
    for row in sanitized:
        session.add(row)
    return len(sanitized)


async def persist_agent_review(
    session: AsyncSession,
    *,
    decision_id: str,
    trace_rows: list[dict[str, Any]],
) -> int:
    """Persist satu putaran review: 7 worker + 1 SUPERVISE, idempoten.

    Kontrak P5:
    - tepat 8 baris, semua membawa `run_id` yang sama;
    - run_id harus UUID;
    - bila `run_id` itu sudah tersimpan untuk decision ini, tidak menulis ulang
      (Event 1 boleh dipanggil ulang tanpa menggandakan trace).
    """
    if len(trace_rows) != 8:
        raise ValueError(
            f"review wajib 8 baris trace (7 worker + SUPERVISE), diterima {len(trace_rows)}"
        )
    run_ids = {str(row.get("run_id") or "").strip() for row in trace_rows}
    run_ids.discard("")
    if len(run_ids) != 1:
        raise ValueError("review wajib membawa tepat satu run_id")
    run_id = next(iter(run_ids))
    try:
        run_uuid = uuid.UUID(run_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"run_id review tidak valid: {run_id!r}") from exc

    existing = await session.scalar(
        select(func.count())
        .select_from(AgentTrace)
        .where(
            AgentTrace.decision_id == decision_id,
            AgentTrace.run_id == run_uuid,
        )
    )
    if existing:
        return 0
    return persist_trace_steps(
        session,
        decision_id=decision_id,
        steps=trace_rows,
    )
