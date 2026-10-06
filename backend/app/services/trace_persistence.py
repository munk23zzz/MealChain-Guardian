"""Trace persistence (S3-10) — satu row per langkah aktual, tersanitasi."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentTrace
from app.services.agent_memory import sanitize_memory_payload

_VALID_STEPS = frozenset(
    {"DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE",
     "ACT", "LEARN"}
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
                # timestamp monoton per indeks agar urutan timeline
                # dapat di-replay (satu transaksi = now() DB identik)
                step_at=base_ts + timedelta(microseconds=index),
            )
        )
    for row in sanitized:
        session.add(row)
    return len(sanitized)
