"""Klien review 7 worker dari backend ke AgentCore Runtime.

Backend tidak mengimpor `agent/` (image backend tidak memuat folder itu).
Klien ini hanya mengirim task JSON ke caller AgentCore; tanpa ARN, hasilnya
`unavailable` dan tidak ada temuan yang dikarang.

Kontrak payload runtime:
    {"task": "review_decision", "decision_id": "<uuid>"}
Runtime mengembalikan JSON `AgentRun` di dalam `response`. Caller boleh
di-inject untuk tes; default memakai `build_runtime_caller(ARN)`.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable

TASK = "review_decision"
ENV_RUNTIME_ARN = "AGENTCORE_RUNTIME_ARN"
DEFAULT_TIMEOUT_SECONDS = 45.0
ALLOWED_STATUS = frozenset({"completed", "partial", "failed", "timeout", "unavailable"})


@dataclass(frozen=True)
class AgentReviewResult:
    """Hasil satu pemanggilan review; `payload` hanya diisi bila valid."""

    status: str
    run_id: str | None = None
    payload: dict[str, Any] | None = None
    error: str | None = None

    @property
    def completed(self) -> bool:
        return self.status in {"completed", "partial"}


def _default_caller() -> Callable[[str], str] | None:
    """Caller AgentCore bila ARN terisi; ARN kosong bukan alasan mengarang."""
    arn = (os.environ.get(ENV_RUNTIME_ARN) or "").strip()
    if not arn:
        return None
    try:
        from app.ai_providers.agentcore_caller import build_runtime_caller

        return build_runtime_caller(arn)
    except Exception:
        # ARN tidak valid / SDK tidak ada: laporkan unavailable oleh pemanggil,
        # jangan menebak runtime lain.
        return None


def _extract_json(raw: str) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    candidate = text[start : end + 1] if start != -1 and end > start else text
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    nested = data.get("review")
    if isinstance(nested, dict):
        return nested
    return data


def _parse_review(raw: str) -> AgentReviewResult:
    data = _extract_json(raw)
    if data is None:
        return AgentReviewResult(
            status="failed", error="respons runtime bukan JSON review yang sah"
        )

    status = data.get("status")
    if status not in ALLOWED_STATUS:
        status = "failed"
    if status == "unavailable":
        error = data.get("error") if isinstance(data.get("error"), str) else None
        return AgentReviewResult(status="unavailable", error=error)

    findings = data.get("findings")
    run_id = data.get("run_id")
    if not isinstance(findings, list) or len(findings) != 7:
        return AgentReviewResult(
            status="failed", error="respons runtime tidak memuat tepat 7 finding"
        )
    if not isinstance(run_id, str) or not run_id.strip():
        return AgentReviewResult(status="failed", error="respons runtime tanpa run_id")
    return AgentReviewResult(status=status, run_id=run_id.strip(), payload=data)


def review_decision(
    decision_id: str,
    *,
    caller: Callable[[str], str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AgentReviewResult:
    """Kirim task review ke runtime dengan batas waktu yang tidak menahan UI."""
    if not isinstance(decision_id, str) or not decision_id.strip():
        return AgentReviewResult(status="failed", error="decision_id wajib diisi")

    selected = caller if caller is not None else _default_caller()
    if selected is None:
        return AgentReviewResult(
            status="unavailable",
            error="runtime AgentCore belum dikonfigurasi (AGENTCORE_RUNTIME_ARN kosong)",
        )

    prompt = json.dumps(
        {"task": TASK, "decision_id": decision_id.strip()}, ensure_ascii=False
    )
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-review")
    future = executor.submit(selected, prompt)
    try:
        raw = future.result(timeout=max(0.1, float(timeout_seconds)))
    except FutureTimeout:
        future.cancel()
        return AgentReviewResult(
            status="timeout",
            error=f"review melewati batas {timeout_seconds:g} detik",
        )
    except Exception as exc:
        return AgentReviewResult(
            status="failed", error=f"{type(exc).__name__}: {exc}"
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not isinstance(raw, str):
        return AgentReviewResult(
            status="failed", error="respons runtime bukan teks"
        )
    return _parse_review(raw)


__all__ = [
    "AgentReviewResult",
    "DEFAULT_TIMEOUT_SECONDS",
    "ENV_RUNTIME_ARN",
    "TASK",
    "review_decision",
]
