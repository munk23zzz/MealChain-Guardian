"""Test Verifier safety guard (S3-06, TDD).

Guard keras: verifier TIDAK BISA mengangkat safety FAIL. Segala
keputusan safety-critical tetap dari deterministic core. Output model
yang mengklaim "safe"/"PASS" saat core bilang FAIL TIDAK dihargai.
"""


from app.ai_providers.verifier_client import enforce_verifier_guard


def test_cannot_resurrect_safety_fail():
    verdict = enforce_verifier_guard(
        model_verdict="CONSISTENT",
        safety_status="FAIL",
        model_says_safe=True,
    )
    # safety FAIL hard constraint — verifier tidak mengubahnya
    assert verdict == "FLAGGED"


def test_guard_flags_when_model_claims_safe_but_core_fail():
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT",
            safety_status="FAIL",
            model_says_safe=False,
        )
        == "FLAGGED"
    )


def test_guard_passes_through_when_safety_ok():
    assert (
        enforce_verifier_guard(
            model_verdict="CONSISTENT", safety_status="PASS", model_says_safe=False
        )
        == "CONSISTENT"
    )


def test_guard_unavailable_if_model_verdict_invalid():
    assert (
        enforce_verifier_guard(
            model_verdict="APA AJA", safety_status="PASS", model_says_safe=False
        )
        == "UNAVAILABLE"
    )
