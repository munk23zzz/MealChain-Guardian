"""Test Verifier REST client (S3-06, TDD).

Verifier adalah REST model call terpisah — BUKAN agent Strands kedua.
Urutan provider WAJIB: SAP AI Core primary → SAP AI Core fallback →
Claude/Bedrock final fallback, semua lewat shared chain S3-05.

Kontrak:
- verdict terstruktur: CONSISTENT | FLAGGED | UNAVAILABLE
- output model tak terbaca → UNAVAILABLE (konservatif)
- tanpa provider terkonfigurasi → UNAVAILABLE tanpa memanggil apa pun
- daftar fallback hanya merekam provider yang BENAR-BENAR dicoba/sukses
- audit mencakup: safety, freshness, eligibility, evidence, logistics,
  cost, rationale (prompt memuat semuanya)
- tidak ada secret di prompt/result

Plan: .hermes/plans/2026-10-06-sprint3-agent-layer.md §S3-06.
"""

import json

from app.ai_providers.verifier_client import (
    run_verifier,
)
from app.core.approval_matrix import approval_requirement


def _ctx(**overrides):
    base = {
        "decision_id": "d-123",
        "commodity": "telur",
        "safety_status": "PASS",
        "freshness_score": 0.9,
        "candidates": [{"supplier": "Bogor", "eligible": True}],
        "evidence": {"safety": "ok", "freshness": "ok"},
        "logistics": {"feasible": True},
        "cost": {"sdc_total": "16206000.00"},
        "rationale": "surplus Cianjur ke shortage Jakarta",
    }
    base.update(overrides)
    return base


def _sap_ok(prompt):
    return json.dumps({"verdict": "CONSISTENT", "reason": "semua dimensi cocok"})


def test_consistent_from_primary_provider():
    calls = []

    def sap_primary(prompt):
        calls.append("sap_primary")
        assert "safety" in prompt and "cost" in prompt  # audit dimensi lengkap
        return json.dumps({"verdict": "CONSISTENT", "reason": "ok"})

    result = run_verifier(_ctx(), sap_primary=sap_primary)

    assert result.verdict == "CONSISTENT"
    assert result.provider == "sap_ai_core_primary"
    assert result.fallback_used is False
    assert [(a.name, a.outcome) for a in result.attempts] == [
        ("primary", "succeeded")
    ]
    assert calls == ["sap_primary"]


def test_falls_back_to_sap_fallback_then_bedrock():
    def sap_primary(prompt):
        raise RuntimeError("SAP AI Core down")

    def sap_fallback(prompt):
        return json.dumps({"verdict": "FLAGGED", "reason": "freshness rendah"})

    result = run_verifier(
        _ctx(),
        sap_primary=sap_primary,
        sap_fallback=sap_fallback,
    )

    assert result.verdict == "FLAGGED"
    assert result.provider == "sap_ai_core_fallback"
    assert result.fallback_used is True
    # bedrock_final TIDAK dicoba — hanya provider yang benar-benar diattempt
    assert [a.name for a in result.attempts] == ["primary", "fallback_1"]


def test_reaches_bedrock_final_fallback():
    def sap_primary(prompt):
        raise RuntimeError("down-1")

    def sap_fallback(prompt):
        raise RuntimeError("down-2")

    def bedrock(prompt):
        return json.dumps({"verdict": "CONSISTENT", "reason": "bedrock ok"})

    result = run_verifier(
        _ctx(), sap_primary=sap_primary, sap_fallback=sap_fallback, bedrock=bedrock
    )

    assert result.verdict == "CONSISTENT"
    assert result.provider == "bedrock_final"
    assert [a.name for a in result.attempts] == [
        "primary",
        "fallback_1",
        "fallback_2",
    ]


def test_unparseable_output_maps_to_unavailable():
    def sap_primary(prompt):
        return "blabla bukan json sama sekali"

    result = run_verifier(_ctx(), sap_primary=sap_primary)

    assert result.verdict == "UNAVAILABLE"
    assert result.provider is None
    assert result.fallback_used is False


def test_no_provider_configured_returns_unavailable_without_calls():
    result = run_verifier(_ctx())  # tanpa provider sama sekali

    assert result.verdict == "UNAVAILABLE"
    assert result.provider is None
    assert result.attempts == []


def test_unavailable_maps_to_two_approvals():
    # UNAVAILABLE (verifier tidak bisa memverifikasi) → dual approval
    # required_roles = grup AND: tiap grup wajib ≥1 approver
    req = approval_requirement("unavailable")
    assert req["min_approvals"] == 2
    groups = req["required_roles"]
    assert len(groups) == 2
    assert {role for group in groups for role in group} == {
        "sppg_head",
        "sppg_nutritionist",
    }


def test_verdict_token_tolerant_whitespace_case():
    def sap_primary(prompt):
        return 'noise prefix {"verdict": "  consistent ", "reason": "x"} noise'

    result = run_verifier(_ctx(), sap_primary=sap_primary)
    assert result.verdict == "CONSISTENT"


def test_system_prompt_file_exists_and_guarded():
    from app.ai_providers.verifier_client import load_verifier_system_prompt

    text = load_verifier_system_prompt()
    # guard eksplisit di prompt: tidak override safety, tidak hitung angka
    assert "FAIL" in text
    assert "CONSISTENT" in text and "FLAGGED" in text and "UNAVAILABLE" in text
