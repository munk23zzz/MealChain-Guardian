"""Guard verifier tidak bisa menaikkan kondisi kesegaran (regresi AUD-9A-03).

Temuan audit 9 agen: untuk `freshness_score = 0,82` — yang menurut
`backend/app/core/freshness.py` adalah `needs_verification` — verifier LLM
mengembalikan CONSISTENT dengan alasan "freshness 0,82 mendukung distribusi".
Guard lama hanya memeriksa `safety_status == "FAIL"`, sehingga verdict model
(yang berbagi model & system prompt dengan penulis narasi) menutupi fakta core.

Perbaikan: guard memakai gerbang CERTIFIED yang sama (PASS >= 0,85,
needs_verification >= 0,60). Uji di bawah mengunci perilaku itu — termasuk
jalur `run_verifier` penuh, supaya `ctx["freshness_score"]` benar-benar
tersambung ke guard (bukan hanya di unit fungsi).
"""

import json

import pytest

from app.ai_providers.verifier_client import (
    enforce_verifier_guard,
    freshness_gate_score,
    run_verifier,
)

CONSISTENT_JSON = json.dumps({"verdict": "CONSISTENT", "reason": "freshness mendukung distribusi"})


# ---------------------------------------------------------------- unit guard


@pytest.mark.parametrize("skor", [0.82, 0.60, 0.84, 0.5, 0.0, 0.35])
def test_consistent_downgraded_when_freshness_below_pass_threshold(skor: float) -> None:
    assert freshness_gate_score(skor) in {"needs_verification", "fail"}

    verdict = enforce_verifier_guard(
        model_verdict="CONSISTENT",
        safety_status="PASS",
        model_says_safe=True,
        freshness_score=skor,
    )

    assert verdict == "FLAGGED"


@pytest.mark.parametrize("skor", [0.85, 0.9, 0.95, 1.0])
def test_consistent_kept_when_freshness_certified_pass(skor: float) -> None:
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT",
            safety_status="PASS",
            model_says_safe=True,
            freshness_score=skor,
        )
        == "CONSISTENT"
    )


def test_freshness_absent_is_not_a_claim() -> None:
    """Tanpa skor (dimensi tidak dikirim) guard tidak mengarang penilaian."""
    assert freshness_gate_score(None) is None
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT",
            safety_status="PASS",
            model_says_safe=True,
            freshness_score=None,
        )
        == "CONSISTENT"
    )


@pytest.mark.parametrize("nilai", [float("nan"), "bukan angka", True, 1.7, -0.2])
def test_skor_tak_terbaca_tidak_boleh_menaikkan_consistent(nilai: object) -> None:
    assert freshness_gate_score(nilai) == "invalid"
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT",
            safety_status="PASS",
            model_says_safe=True,
            freshness_score=nilai,
        )
        == "FLAGGED"
    )


def test_safety_fail_tetap_menang_atas_freshness_pass() -> None:
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT",
            safety_status="FAIL",
            model_says_safe=True,
            freshness_score=0.99,
        )
        == "FLAGGED"
    )


def test_flagged_dari_model_tidak_diubah_guard() -> None:
    assert (
        enforce_verifier_guard(
            model_verdict="FLAGGED",
            safety_status="PASS",
            model_says_safe=False,
            freshness_score=0.99,
        )
        == "FLAGGED"
    )


# ------------------------------------------------- jalur run_verifier penuh


def _ctx(freshness_score: object) -> dict:
    return {
        "decision_id": "d-1",
        "commodity": "telur",
        "safety_status": "PASS",
        "freshness_score": freshness_score,
        "candidates": [],
        "evidence": {},
        "logistics": {},
        "cost": {},
        "rationale": "uji guard",
    }


def test_run_verifier_meneruskan_skor_ke_guard() -> None:
    """0,82 (kasus runtime audit) → FLAGGED, bukan CONSISTENT."""
    result = run_verifier(_ctx(0.82), sap_primary=lambda prompt: CONSISTENT_JSON)

    assert result.verdict == "FLAGGED"
    assert result.provider == "sap_ai_core_primary"


def test_run_verifier_consistent_untuk_skor_pass() -> None:
    result = run_verifier(_ctx(0.965), sap_primary=lambda prompt: CONSISTENT_JSON)

    assert result.verdict == "CONSISTENT"
