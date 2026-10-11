"""Verifier REST client (S3-06).

REST model call TERPISAH — bukan agent Strands kedua. Urutan provider
(SAP AI Core primary → SAP AI Core fallback → Claude/Bedrock final)
dijalankan lewat shared chain S3-05 (`with_fallback_chain`).

Kontrak:
- verdict terstruktur CONSISTENT | FLAGGED | UNAVAILABLE
- output tak terbaca / provider tidak ada → UNAVAILABLE (konservatif)
- safety guard keras via `enforce_verifier_guard`: safety FAIL dari core
  tidak dapat dihidupkan kembali oleh output model
- attempts hanya merekam provider yang benar-benar dicoba
- prompt TIDAK memuat secret/credential
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources
from typing import Callable

VALID_VERDICTS = ("CONSISTENT", "FLAGGED", "UNAVAILABLE")


@dataclass
class VerifierResult:
    """Hasil audit verifier + jejak provider eksplisit."""

    verdict: str  # CONSISTENT | FLAGGED | UNAVAILABLE
    reason: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    attempts: list = field(default_factory=list)


def load_verifier_system_prompt() -> str:
    """Muat system prompt verifier dari paket (container-robust)."""
    return (
        resources.files("app.ai_providers")
        .joinpath("prompts/verifier_system_prompt.md")
        .read_text(encoding="utf-8")
    )


def _build_user_prompt(ctx: dict) -> str:
    """Prompt audit berisi SEMUA dimensi, tanpa secret."""
    return json.dumps(
        {
            "task": "audit konsistensi keputusan distribusi",
            "decision_id": ctx.get("decision_id"),
            "commodity": ctx.get("commodity"),
            "dimensions": {
                "safety_status": ctx.get("safety_status"),
                "freshness_score": ctx.get("freshness_score"),
                "candidates": ctx.get("candidates"),
                "evidence": ctx.get("evidence"),
                "logistics": ctx.get("logistics"),
                "cost": ctx.get("cost"),
            },
            "rationale": ctx.get("rationale"),
        },
        ensure_ascii=False,
    )


def _extract_verdict(raw: str) -> tuple[str, str | None] | None:
    """Ekstrak verdict dari output model; toleran noise di sekitar JSON."""
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in VALID_VERDICTS:
        return None
    reason = data.get("reason")
    return verdict, str(reason) if reason is not None else None


def enforce_verifier_guard(
    *,
    model_verdict: str,
    safety_status: str,
    model_says_safe: bool,
) -> str:
    """Guard keras: safety FAIL dari core tidak bisa dihidupkan kembali.

    - verdict model tidak valid → UNAVAILABLE (konservatif)
    - safety FAIL + model klaim CONSISTENT → FLAGGED (bukan CONSISTENT)
    """
    verdict = (model_verdict or "").strip().upper()
    if verdict not in VALID_VERDICTS:
        return "UNAVAILABLE"
    if (safety_status or "").strip().upper() == "FAIL" and verdict == "CONSISTENT":
        return "FLAGGED"
    return verdict


def run_verifier(
    ctx: dict,
    *,
    sap_primary: Callable[[str], str] | None = None,
    sap_fallback: Callable[[str], str] | None = None,
    bedrock: Callable[[str], str] | None = None,
    timeout_seconds: float | None = 30.0,
    default_chain: list | None = None,
) -> VerifierResult:
    """Jalankan audit verifier lewat chain fallback S3-05.

    `default_chain` dari `build_default_callers("verifier")` bila pemanggil
    tidak menyuntik provider eksplisit (sap_primary/sap_fallback/bedrock) —
    kontrak label baru `primary:bedrock` dst. Tanpa env → UNAVAILABLE.
    """
    system_prompt = load_verifier_system_prompt()
    prompt = f"{system_prompt}\n\n### CONTEXT\n{_build_user_prompt(ctx)}"

    chain: list[Callable[[str], str]] = []
    labels: list[str] = []
    if sap_primary is not None:
        chain.append(sap_primary)
        labels.append("primary")
    if sap_fallback is not None:
        chain.append(sap_fallback)
        labels.append("fallback_1")
    if bedrock is not None:
        chain.append(bedrock)
        labels.append("fallback_2")

    if not chain and default_chain is not None:
        for slot_label, fn, _kind in default_chain:
            chain.append(fn)
            labels.append(slot_label)

    if not chain:
        env_chain = _default_env_chain()
        labels = [label for label, _fn, _kind in env_chain]
        chain = [fn for _label, fn, _kind in env_chain]

    if not chain:
        return VerifierResult(verdict="UNAVAILABLE", attempts=[])

    # O-AI (S4-00): seluruh chain diteruskan — slot 4+ tidak lagi terpotong;
    # exhaustion (semua provider gagal) → UNAVAILABLE, bukan exception naik.
    from app.ai_providers.resilience import with_fallback_chain as _wfc

    result = _wfc(
        primary=chain[0],
        prompt=prompt,
        fallbacks=[fn for fn in chain[1:]],
        timeout_seconds=timeout_seconds,
    )

    # Nama pemenang dari chain bersifat posisional (primary/fallback_N);
    # translasi ke label jujur memakai list `labels` (urutan penyusunan).
    slot_to_index = {"primary": 0, **{f"fallback_{i}": i for i in range(1, 25)}}
    winner_index = slot_to_index.get(result.provider, 0)
    winner_label = (
        labels[winner_index] if winner_index < len(labels) else result.provider
    )
    provider_label = {
        "primary": "sap_ai_core_primary",
        "fallback_1": "sap_ai_core_fallback",
        "fallback_2": "bedrock_final",
    }.get(winner_label, winner_label)

    extracted = _extract_verdict(result.text)
    if extracted is None:
        # output tak terbaca → UNAVAILABLE konservatif; jejak tetap eksplisit
        return VerifierResult(
            verdict="UNAVAILABLE",
            reason=None,
            provider=None,
            fallback_used=result.fallback_used,
            attempts=result.attempts,
        )

    verdict, reason = extracted
    safety_status = str(ctx.get("safety_status") or "")
    guarded = enforce_verifier_guard(
        model_verdict=verdict,
        safety_status=safety_status,
        model_says_safe=verdict == "CONSISTENT",
    )
    return VerifierResult(
        verdict=guarded,
        reason=reason,
        provider=provider_label,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
    )


def _default_env_chain() -> list[tuple[str, Callable, str]]:
    """Chain default verifier dari env (lazy import hindari siklus modul)."""
    from app.ai_providers.ai_provider_chain import build_default_callers

    return build_default_callers("verifier")


def _default_sap_ai_core_callers() -> tuple[Callable | None, Callable | None]:
    """Factory caller SAP AI Core dari env (kosong → None, jujur).

    Dipisah agar test bisa menyuntik callable tanpa env.
    """
    from app.ai_providers.sap_ai_core_caller import build_llm_caller

    try:
        # S4-10: general model SAP AI Core (`/invoke`), bukan stub lagi.
        return build_llm_caller(), None
    except RuntimeError:
        return None, None
