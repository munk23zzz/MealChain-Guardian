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

from app.ai_providers.resilience import provider_slot_index, with_fallback_chain

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
    # O-AI (S4-00): seluruh chain diteruskan; exhaustion (semua provider
    # gagal) → status `unavailable` rapi, bukan ProviderUnavailableError naik.
    from app.ai_providers.resilience import (
        ProviderUnavailableError,
    )

    try:
        result = with_fallback_chain(
            primary=chain[0][1],
            prompt=prompt,
            fallbacks=[fn for _label, fn, _kind in chain[1:]],
            timeout_seconds=timeout_seconds,
        )
    except ProviderUnavailableError as exc:
        return SupervisorResult(status="unavailable", attempts=exc.attempts)
    summary = _extract_summary(result.text)
    if not summary:
        return SupervisorResult(
            status="error",
            provider=None,
            fallback_used=result.fallback_used,
            attempts=result.attempts,
        )
    # nama pemenang chain posisional → translasi label jujur slot:kind.
    # Pakai helper terpusat dari resilience.py: peta 3 entri lokal dulu memetakan
    # pemenang `fallback_3` ke indeks 0 sehingga dilaporkan sebagai "primary"
    # (label karangan) begitu rantai punya lebih dari tiga slot.
    winner_index = provider_slot_index(result.provider)
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
