"""Candidate Score engine deterministik (Task 5 Sprint 2).

Kontrak terkunci (plan):
score = Demand Fit × Supply Availability × Freshness × Safety Eligibility
        × Supplier Reliability × Logistics Feasibility

- Semua faktor [0,1]; di luar → ValueError.
- safety_status 'fail' → score 0, eligible False, TIDAK dapat dihidupkan
  oleh faktor mana pun (Safety FAIL = hard exclusion terkunci).
- pending/needs_verification TIDAK hard-exclude (konsisten
  constraints.is_batch_eligible Sprint 1: hanya fail yang mengecualikan).
- review_required=True hanya bila safety needs_verification — sinyal
  review, bukan pengecualian.
- Produk Decimal eksak tanpa pembulatan; murni deterministik; tanpa LLM.
"""

from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "CandidateScoreFactors",
    "CandidateScoreResult",
    "calculate_candidate_score",
]

_SAFETY_STATUSES = frozenset(
    {"pending", "pass", "fail", "needs_verification"}
)

_FACTOR_NAMES = (
    "demand_fit",
    "supply_availability",
    "freshness_score",
    "supplier_reliability",
)


@dataclass(frozen=True)
class CandidateScoreFactors:
    demand_fit: Decimal
    supply_availability: Decimal
    freshness_score: Decimal
    safety_status: str
    supplier_reliability: Decimal
    logistics_feasible: bool

    def __post_init__(self) -> None:
        for name in _FACTOR_NAMES:
            d = Decimal(str(getattr(self, name)))
            if d < 0 or d > 1:
                raise ValueError(f"{name} wajib dalam [0,1], dapat {d}")
            object.__setattr__(self, name, d)
        if self.safety_status not in _SAFETY_STATUSES:
            raise ValueError(
                f"safety_status tidak dikenal: {self.safety_status!r}"
            )


@dataclass(frozen=True)
class CandidateScoreResult:
    score: Decimal
    eligible: bool
    review_required: bool


def calculate_candidate_score(
    factors: CandidateScoreFactors,
) -> CandidateScoreResult:
    """Hitung skor produk eksak; safety fail → skor 0 tanpa kecuali."""
    if factors.safety_status == "fail":
        return CandidateScoreResult(
            score=Decimal("0"), eligible=False, review_required=False
        )
    # Safety Eligibility = 1 untuk non-fail (pending/needs_verification
    # tetap masuk peringkat dengan penanda review, bukan pengecualian).
    safety_eligibility = Decimal("1")
    logistics = Decimal("1") if factors.logistics_feasible else Decimal("0")
    score = (
        factors.demand_fit
        * factors.supply_availability
        * factors.freshness_score
        * safety_eligibility
        * factors.supplier_reliability
        * logistics
    )
    return CandidateScoreResult(
        score=score,
        eligible=True,
        review_required=factors.safety_status == "needs_verification",
    )
