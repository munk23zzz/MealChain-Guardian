"""Task 7 Sprint 2: ranking kandidat deterministik.

Kontrak (plan Task 7):
- Primary: Candidate Score DESC. Secondary: Safe Delivered Cost ASC.
- Tie eksplisit: source, destination, commodity, supplier_id, candidate_id
  ascending lexical.
- Kandidat safety-fail (eligible=False) DIKECUALIKAN sebelum sorting —
  tidak pernah muncul, tidak pernah mendapat rank.
- review_required dipertahankan pada output.
- rank = 1..N pada hasil terurut; input yang sama → output identik.
"""

from decimal import Decimal

from app.core.candidate import BalancingCandidate, PriceInfo
from app.core.ranking import ScoredCandidate, rank_candidates

_SUP = "11111111-1111-1111-1111-111111111111"


def _candidate(source="Cianjur", dest="Jakarta", commodity="telur",
               supplier_id=_SUP, cid="c1", quantity=Decimal("500")):
    return BalancingCandidate(
        source_location=source,
        destination_location=dest,
        commodity=commodity,
        quantity_kg=quantity,
        demand_fit=Decimal("1"),
        supply_availability=Decimal("1"),
        freshness_score=Decimal("0.9"),
        freshness_status="pass",
        safety_status="pass",
        supplier_reliability=Decimal("0.8"),
        logistics_feasible=True,
        logistics_distance_km=Decimal("120"),
        logistics_time_min=150,
        price=PriceInfo(
            reference_price=Decimal("26500"),
            supplier_quote=Decimal("26200"),
            supplier_id=supplier_id,
        ),
    )


def _scored(score, sdc, cid="c1", **kw):
    candidate = kw.pop("candidate", None) or _candidate(cid=cid, **kw)
    return ScoredCandidate(
        candidate=candidate,
        candidate_id=cid,
        score=Decimal(str(score)),
        eligible=True,
        review_required=False,
        safe_delivered_cost=Decimal(str(sdc)),
    )


def test_rank_by_score_desc():
    low = _scored(0.1, 15_000_000, cid="low")
    high = _scored(0.9, 14_000_000, cid="high")
    ranked = rank_candidates([low, high])
    assert [r.candidate_id for r in ranked] == ["high", "low"]
    assert ranked[0].rank == 1


def test_sdc_ascending_breaks_score_tie():
    a = _scored(0.5, 15_000_000, cid="a")
    b = _scored(0.5, 13_999_999.99, cid="b")
    ranked = rank_candidates([a, b])
    assert [r.candidate_id for r in ranked] == ["b", "a"]


def test_full_tie_lexical_deterministic():
    a = _scored(0.5, 14_000_000, cid="same", source="Bogor",
                dest="Jakarta", commodity="telur", supplier_id=_SUP)
    b = _scored(0.5, 14_000_000, cid="same", source="Cianjur",
                dest="Jakarta", commodity="telur", supplier_id=_SUP)
    ranked = rank_candidates([b, a])
    assert [r.candidate.source_location for r in ranked] == ["Bogor", "Cianjur"]


def test_candidate_id_final_tiebreak():
    a = _scored(0.5, 14_000_000, cid="zz", source="Cianjur", dest="Jakarta")
    b = _scored(0.5, 14_000_000, cid="aa", source="Cianjur", dest="Jakarta")
    ranked = rank_candidates([a, b])
    assert [r.candidate_id for r in ranked] == ["aa", "zz"]


def test_safety_fail_excluded_before_sorting():
    fail = ScoredCandidate(
        candidate=_candidate(cid="dead"),
        candidate_id="dead",
        score=Decimal("0"),
        eligible=False,
        review_required=False,
        safe_delivered_cost=Decimal("0"),
    )
    good = _scored(0.4, 15_000_000, cid="good")
    ranked = rank_candidates([fail, good])
    assert [r.candidate_id for r in ranked] == ["good"]


def test_review_required_preserved():
    review = ScoredCandidate(
        candidate=_candidate(cid="rv"),
        candidate_id="rv",
        score=Decimal("0.5"),
        eligible=True,
        review_required=True,
        safe_delivered_cost=Decimal("14_000_000"),
    )
    ranked = rank_candidates([review])
    assert ranked[0].review_required is True


def test_ranks_are_one_based_sequential():
    items = [
        _scored(0.3, 16_000_000, cid="x"),
        _scored(0.7, 13_000_000, cid="y"),
        _scored(0.5, 14_000_000, cid="z"),
    ]
    ranked = rank_candidates(items)
    assert [r.rank for r in ranked] == [1, 2, 3]
    assert [r.candidate_id for r in ranked] == ["y", "z", "x"]


def test_repeat_deterministic():
    items = [
        _scored(0.3, 16_000_000, cid="x"),
        _scored(0.7, 13_000_000, cid="y"),
        _scored(0.5, 14_000_000, cid="z"),
    ]
    a = [r.to_dict() for r in rank_candidates(items)]
    b = [r.to_dict() for r in rank_candidates(items)]
    assert a == b


def test_empty_input():
    assert rank_candidates([]) == []
