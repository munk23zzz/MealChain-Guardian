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
    {"DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "ANALYZE", "DECIDE",
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
        parent_run_id = step.get("parent_run_id")
        if parent_run_id is not None:
            parent_run_id = str(parent_run_id)
            try:
                uuid.UUID(parent_run_id)
            except (ValueError, AttributeError, TypeError) as exc:
                raise ValueError(
                    f"parent_run_id trace tidak valid: {step.get('parent_run_id')!r}"
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
                parent_run_id=parent_run_id,
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
    """Persist satu putaran review: 7 worker + 1 verifier + 1 SUPERVISE, idempoten.

    Kontrak P5 (+ AUD-9A-03):

    - tepat 9 baris (tujuh worker, verifier, SUPERVISE), atau 8 baris dari
      runtime lama tanpa verifier;
    - setiap baris wajib membawa `run_id` UUID;
    - SATU run induk per putaran: run dari baris SUPERVISE (fallback: run yang
      paling banyak muncul). Baris lain boleh memakai run induk itu;
    - verifier adalah RUN ANAK: baris VERIFY boleh membawa `run_id` sendiri dan
      wajib menunjuk run induk lewat `parent_run_id` = run review. Baris lain
      tidak boleh punya `parent_run_id` lain;
    - bila run induk itu sudah tersimpan untuk decision ini, tidak menulis ulang
      (Event 1 boleh dipanggil ulang tanpa menggandakan trace).
    """
    if len(trace_rows) not in (8, 9):
        raise ValueError(
            "review wajib 9 baris trace (7 worker + verifier + SUPERVISE), "
            f"atau 8 baris dari runtime lama tanpa verifier; diterima {len(trace_rows)}"
        )
    run_ids = [str(row.get("run_id") or "").strip() for row in trace_rows]
    if any(not nilai for nilai in run_ids):
        raise ValueError("setiap baris review wajib membawa run_id")
    for nilai in run_ids:
        try:
            uuid.UUID(nilai)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"run_id review tidak valid: {nilai!r}") from exc

    # Run induk = run baris SUPERVISE; fallback ke run terbanyak bila runtime
    # lama tidak mengirim baris SUPERVISE dengan run_id.
    supervise = next(
        (
            str(row.get("run_id"))
            for row in trace_rows
            if row.get("step_name") == "SUPERVISE" and row.get("run_id")
        ),
        None,
    )
    root_run_id = supervise or max(set(run_ids), key=run_ids.count)
    root_uuid = uuid.UUID(root_run_id)

    for row in trace_rows:
        parent = row.get("parent_run_id")
        if parent is None:
            # Langkah dari run induk: run_id wajib sama dengan run induk.
            if str(row.get("run_id")) != root_run_id:
                raise ValueError(
                    "baris tanpa parent_run_id wajib memakai satu run_id (run "
                    f"induk {root_run_id}); diterima {row.get('run_id')!r} pada "
                    f"{row.get('step_name')!r}"
                )
            continue
        if str(parent) != root_run_id:
            raise ValueError(
                "parent_run_id harus menunjuk run induk review "
                f"({root_run_id}); diterima {parent!r} pada {row.get('step_name')!r}"
            )
        if str(row.get("run_id")) == root_run_id:
            # Run anak harus punya identitas sendiri supaya jejaknya bisa
            # dibedakan dari langkah run induk.
            raise ValueError(
                "baris ber-parent_run_id wajib membawa run_id sendiri "
                f"(step {row.get('step_name')!r})"
            )

    existing = await session.scalar(
        select(func.count())
        .select_from(AgentTrace)
        .where(
            AgentTrace.decision_id == decision_id,
            AgentTrace.run_id == root_uuid,
        )
    )
    if existing:
        return 0
    return persist_trace_steps(
        session,
        decision_id=decision_id,
        steps=trace_rows,
    )
