"""Supervisor client — narasi akhir agent pengawas (permintaan Roy).

Posisi dalam pipeline: langkah TERAKHIR, SETELAH verifier/forecast/
optimasi. Narasi TIDAK safety-critical: tidak pernah mengubah verdict
verifier, rekomendasi engine, cost, atau angka apa pun — hanya
meringkas untuk manusia yang akan approve.

Kontrak (selaras verifier/forecast):
- chain = build_default_callers("supervisor") dari env; tanpa chain →
  status `unavailable`, tanpa panggilan (jujur)
- label provider jujur slot:kind (`primary:bedrock`, `fallback_1:inferhub`)
- output tak terbaca → status `error`, decision tetap lahir
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.ai_providers.resilience import with_fallback_chain

NARRATION_KEYS = ("ringkasan",)


@dataclass
class SupervisorResult:
    """Hasil narasi supervisor + jejak provider eksplisit."""

    status: str  # narrated | unavailable | error
    summary: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    attempts: list = field(default_factory=list)


def _build_prompt(outcome_ctx: dict) -> str:
    """Prompt narasi — ringkasan operasional, tanpa secret."""
    return json.dumps(
        {
            "task": "ringkas keputusan distribusi untuk reviewer manusia",
            "commodity": outcome_ctx.get("commodity"),
            "target_location": outcome_ctx.get("target_location"),
            "surplus": outcome_ctx.get("surplus"),
            "shortage": outcome_ctx.get("shortage"),
            "verifier_verdict": outcome_ctx.get("verifier_verdict"),
            "forecast": outcome_ctx.get("forecast"),
            "chosen": outcome_ctx.get("chosen"),
        },
        ensure_ascii=False,
    )


def _extract_summary(raw: str) -> str | None:
    """Ringkasan dari output model; toleran noise di sekitar JSON."""
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return raw.strip()[:400] or None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return raw.strip()[:400] or None
    for key in NARRATION_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # JSON valid tanpa key ringkasan → pakai teks utuh (terpotong wajar)
    return raw.strip()[:400] or None


def run_supervisor(
    outcome_ctx: dict,
    *,
    chain: list | None = None,
    timeout_seconds: float | None = 30.0,
) -> SupervisorResult:
    """Narasi akhir lewat chain fallback S3-05 (default dari env)."""
    if chain is None:
        from app.ai_providers.ai_provider_chain import build_default_callers

        chain = build_default_callers("supervisor")
    if not chain:
        return SupervisorResult(status="unavailable", attempts=[])

    prompt = _build_prompt(outcome_ctx)
    result = with_fallback_chain(
        primary=chain[0][1],
        prompt=prompt,
        fallback_1=chain[1][1] if len(chain) > 1 else None,
        fallback_2=chain[2][1] if len(chain) > 2 else None,
        timeout_seconds=timeout_seconds,
    )
    summary = _extract_summary(result.text)
    if not summary:
        return SupervisorResult(
            status="error",
            provider=None,
            fallback_used=result.fallback_used,
            attempts=result.attempts,
        )
    # nama pemenang chain posisional → translasi label jujur slot:kind
    slot_to_index = {"primary": 0, "fallback_1": 1, "fallback_2": 2}
    winner_index = slot_to_index.get(result.provider, 0)
    winner_label = (
        chain[winner_index][0] if winner_index < len(chain) else result.provider
    )
    return SupervisorResult(
        status="narrated",
        summary=summary,
        provider=winner_label,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
    )
