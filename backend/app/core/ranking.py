"""Ranking kandidat deterministik (Task 7 Sprint 2).

Kontrak plan Task 7:
- Primary: Candidate Score DESC; secondary: Safe Delivered Cost ASC.
- Tie eksplisit ascending lexical: source_location, destination_location,
  commodity, supplier_id, candidate_id.
- Kandidat eligible=False (safety fail) DIKECUALIKAN sebelum sorting —
  tidak pernah diranking, tidak pernah mendapat rank.
- review_required dipertahankan; rank 1..N berurutan; input sama →
  output identik (Decimal eksak, tanpa floating point).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.candidate import BalancingCandidate

__all__ = ["RankedCandidate", "ScoredCandidate", "rank_candidates"]


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: BalancingCandidate
    candidate_id: str
    score: Decimal
    eligible: bool
    review_required: bool
    safe_delivered_cost: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, BalancingCandidate):
            raise ValueError("candidate wajib BalancingCandidate")
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise ValueError("candidate_id wajib string non-kosong")
        for name in ("score", "safe_delivered_cost"):
            object.__setattr__(
                self, name, Decimal(str(getattr(self, name)))
            )
        if not isinstance(self.eligible, bool) or not isinstance(
            self.review_required, bool
        ):
            raise ValueError("eligible/review_required wajib boolean")

    def sort_key(self):
        return (
            -self.score,
            self.safe_delivered_cost,
            self.candidate.source_location,
            self.candidate.destination_location,
            self.candidate.commodity,
            self.candidate.price.supplier_id or "",
            self.candidate_id,
        )

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "score": str(self.score),
            "eligible": self.eligible,
            "review_required": self.review_required,
            "safe_delivered_cost": str(self.safe_delivered_cost),
            "candidate": self.candidate.to_dict(),
        }


@dataclass(frozen=True)
class RankedCandidate(ScoredCandidate):
    rank: int = 0

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload["rank"] = self.rank
        return payload


def rank_candidates(candidates) -> list:
    """Kecualikan ineligible, urutkan deterministik, beri rank 1..N."""
    eligible = [c for c in candidates if c.eligible]
    ordered = sorted(eligible, key=ScoredCandidate.sort_key)
    return [
        RankedCandidate(
            candidate=c.candidate,
            candidate_id=c.candidate_id,
            score=c.score,
            eligible=c.eligible,
            review_required=c.review_required,
            safe_delivered_cost=c.safe_delivered_cost,
            rank=index + 1,
        )
        for index, c in enumerate(ordered)
    ]
