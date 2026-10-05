"""Task 5 Sprint 2: Candidate Score engine deterministik.

Kontrak terkunci (plan Task 5):
score = Demand Fit × Supply Availability × Freshness × Safety Eligibility
        × Supplier Reliability × Logistics Feasibility

- Semua faktor [0,1]; di luar → ValueError.
- safety_status 'fail' → score 0 dan eligible False (tidak bisa
  dihidupkan oleh faktor mana pun).
- pending/needs_verification TIDAK mengecualikan (konsisten
  constraints.is_batch_eligible Sprint 1) — hanya fail yang hard-exclude.
- freshness_status needs_verification dipertahankan → review_required.
- Produk Decimal eksak, tanpa pembulatan — deterministik.
- LLM tidak pernah memanggil modul ini; ini kode deterministik murni.
"""

from decimal import Decimal

import pytest

from app.core.scoring import (
    CandidateScoreFactors,
    CandidateScoreResult,
    calculate_candidate_score,
)


def _factors(**overrides):
    base = {
        "demand_fit": Decimal("1"),
        "supply_availability": Decimal("1"),
        "freshness_score": Decimal("1"),
        "safety_status": "pass",
        "supplier_reliability": Decimal("1"),
        "logistics_feasible": True,
    }
    base.update(overrides)
    return CandidateScoreFactors(**base)


def test_all_ones_gives_one():
    r = calculate_candidate_score(_factors())
    assert r.score == Decimal("1")
    assert r.eligible is True
    assert r.review_required is False


def test_partial_factors_multiply_exactly():
    r = calculate_candidate_score(
        _factors(
            demand_fit=Decimal("0.5"),
            supply_availability=Decimal("0.8"),
            freshness_score=Decimal("0.9"),
            supplier_reliability=Decimal("0.75"),
        )
    )
    assert r.score == Decimal("0.5") * Decimal("0.8") * Decimal("0.9") * Decimal("0.75")


def test_zero_factor_gives_zero():
    r = calculate_candidate_score(_factors(demand_fit=Decimal("0")))
    assert r.score == Decimal("0")
    assert r.eligible is True  # bukan safety fail — hanya skor nol


def test_safety_fail_zero_and_never_resurrected():
    r = calculate_candidate_score(_factors(safety_status="fail"))
    assert r.score == Decimal("0")
    assert r.eligible is False
    assert r.review_required is False


def test_safety_pending_does_not_hard_exclude():
    r = calculate_candidate_score(_factors(safety_status="pending"))
    assert r.eligible is True
    assert r.score == Decimal("1")


def test_needs_verification_preserved_as_review():
    r = calculate_candidate_score(
        _factors(safety_status="needs_verification")
    )
    assert r.eligible is True
    assert r.review_required is True


def test_infeasible_logistics_zero_factor():
    r = calculate_candidate_score(_factors(logistics_feasible=False))
    assert r.score == Decimal("0")


def test_factor_out_of_range_rejected():
    with pytest.raises(ValueError):
        _factors(demand_fit=Decimal("1.01"))
    with pytest.raises(ValueError):
        _factors(freshness_score=Decimal("-0.001"))


def test_unknown_safety_status_rejected():
    with pytest.raises(ValueError):
        _factors(safety_status="dead")


def test_deterministic_repeat():
    f = _factors(
        demand_fit=Decimal("0.7"),
        freshness_score=Decimal("0.83"),
        supplier_reliability=Decimal("0.8"),
    )
    a = calculate_candidate_score(f)
    b = calculate_candidate_score(f)
    assert a == b
    assert isinstance(a, CandidateScoreResult)


def test_result_not_eligible_excluded_upstream_contract():
    """eligible=False adalah kontrak exclude untuk ranking (Task 7)."""
    r = calculate_candidate_score(_factors(safety_status="fail"))
    assert r.eligible is False
