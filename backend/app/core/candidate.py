"""Model kandidat balancing deterministik (Task 1 Sprint 2).

Immutable dataclass + validasi kontrak domain di __post_init__:
- source != destination; quantity_kg > 0 ketat.
- Faktor skor dalam [0,1]; biaya non-negatif.
- Status eksplisit: safety pending|pass|fail|needs_verification,
  freshness pass|needs_verification|fail.
- Dua lapis harga (disiplin Roy 2026-10-05): reference_price = benchmark
  pasar per kota (pihps); supplier_quote = sinyal harga beli supplier dan
  WAJIB diikuti supplier_id — identitas supplier di kolom terpisah, tidak
  pernah dienkode ke string source.
- Candidate Score dihitung Task 5, tidak ada di model ini.
Semua perhitungan deterministik; LLM tidak pernah menyentuh modul ini.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

__all__ = [
    "BalancingCandidate",
    "CandidateValidationError",
    "PriceInfo",
]

_FRACTION_FACTORS = (
    "demand_fit",
    "supply_availability",
    "freshness_score",
    "supplier_reliability",
)
_SAFETY_STATUSES = frozenset({"pending", "pass", "fail", "needs_verification"})
_FRESHNESS_STATUSES = frozenset({"pass", "needs_verification", "fail"})


class CandidateValidationError(ValueError):
    """Input kandidat melanggar kontrak domain deterministik."""


def _to_decimal(value, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CandidateValidationError(f"{name} bukan angka valid: {value!r}") from exc


def _require_fraction(d: Decimal, name: str) -> None:
    if d < 0 or d > 1:
        raise CandidateValidationError(f"{name} wajib dalam [0,1], dapat {d}")


def _require_nonnegative(d: Decimal, name: str) -> None:
    if d < 0:
        raise CandidateValidationError(f"{name} tidak boleh negatif: {d}")


@dataclass(frozen=True)
class PriceInfo:
    """Dua lapis harga: referensi pasar (benchmark) + quote supplier (beli)."""

    reference_price: Decimal
    supplier_quote: Optional[Decimal] = None
    supplier_id: Optional[str] = None

    def __post_init__(self) -> None:
        ref = _to_decimal(self.reference_price, "reference_price")
        object.__setattr__(self, "reference_price", ref)
        if ref <= 0:
            raise CandidateValidationError("reference_price wajib > 0")
        if self.supplier_quote is not None:
            quote = _to_decimal(self.supplier_quote, "supplier_quote")
            object.__setattr__(self, "supplier_quote", quote)
            if quote <= 0:
                raise CandidateValidationError("supplier_quote wajib > 0")
            if not self.supplier_id:
                raise CandidateValidationError(
                    "supplier_quote wajib punya supplier_id — identitas "
                    "supplier ada di kolom terpisah, bukan di source"
                )
        if self.supplier_id is not None and not isinstance(self.supplier_id, str):
            object.__setattr__(self, "supplier_id", str(self.supplier_id))


@dataclass(frozen=True)
class BalancingCandidate:
    """Satu kandidat balancing antar wilayah; tanpa skor, tanpa perilaku LLM."""

    source_location: str
    destination_location: str
    commodity: str
    quantity_kg: Decimal
    demand_fit: Decimal
    supply_availability: Decimal
    freshness_score: Decimal
    freshness_status: str
    safety_status: str
    supplier_reliability: Decimal
    logistics_feasible: bool
    logistics_distance_km: Decimal
    logistics_time_min: int
    price: PriceInfo
    transport_cost: Decimal = Decimal("0")
    handling_cost: Decimal = Decimal("0")
    supplier_id: Optional[str] = None
    batch_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("source_location", "destination_location", "commodity"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CandidateValidationError(f"{name} wajib string non-kosong")
            object.__setattr__(self, name, value.strip())
        if self.source_location == self.destination_location:
            raise CandidateValidationError(
                "source_location dan destination_location tidak boleh sama"
            )
        quantity = _to_decimal(self.quantity_kg, "quantity_kg")
        object.__setattr__(self, "quantity_kg", quantity)
        if quantity <= 0:
            raise CandidateValidationError(
                f"quantity_kg wajib > 0 (positif ketat), dapat {quantity}"
            )
        for name in _FRACTION_FACTORS:
            d = _to_decimal(getattr(self, name), name)
            _require_fraction(d, name)
            object.__setattr__(self, name, d)
        if self.freshness_status not in _FRESHNESS_STATUSES:
            raise CandidateValidationError(
                "freshness_status wajib salah dari "
                f"{sorted(_FRESHNESS_STATUSES)}, dapat {self.freshness_status!r}"
            )
        if self.safety_status not in _SAFETY_STATUSES:
            raise CandidateValidationError(
                "safety_status wajib salah dari "
                f"{sorted(_SAFETY_STATUSES)}, dapat {self.safety_status!r}"
            )
        if not isinstance(self.logistics_feasible, bool):
            raise CandidateValidationError("logistics_feasible wajib boolean")
        distance = _to_decimal(self.logistics_distance_km, "logistics_distance_km")
        _require_nonnegative(distance, "logistics_distance_km")
        object.__setattr__(self, "logistics_distance_km", distance)
        if isinstance(self.logistics_time_min, bool) or not isinstance(
            self.logistics_time_min, int
        ):
            raise CandidateValidationError("logistics_time_min wajib integer menit")
        if self.logistics_time_min < 0:
            raise CandidateValidationError("logistics_time_min tidak boleh negatif")
        if not isinstance(self.price, PriceInfo):
            raise CandidateValidationError("price wajib PriceInfo")
        transport = _to_decimal(self.transport_cost, "transport_cost")
        _require_nonnegative(transport, "transport_cost")
        object.__setattr__(self, "transport_cost", transport)
        handling = _to_decimal(self.handling_cost, "handling_cost")
        _require_nonnegative(handling, "handling_cost")
        object.__setattr__(self, "handling_cost", handling)
        if self.supplier_id is not None:
            object.__setattr__(self, "supplier_id", str(self.supplier_id))
        if not isinstance(self.batch_ids, tuple):
            object.__setattr__(self, "batch_ids", tuple(self.batch_ids))

    def to_dict(self) -> dict:
        """Serialisasi deterministik: semua Decimal jadi string eksak."""

        def _dec(value):
            return None if value is None else str(value)

        return {
            "source_location": self.source_location,
            "destination_location": self.destination_location,
            "commodity": self.commodity,
            "quantity_kg": str(self.quantity_kg),
            "demand_fit": str(self.demand_fit),
            "supply_availability": str(self.supply_availability),
            "freshness_score": str(self.freshness_score),
            "freshness_status": self.freshness_status,
            "safety_status": self.safety_status,
            "supplier_reliability": str(self.supplier_reliability),
            "logistics_feasible": self.logistics_feasible,
            "logistics_distance_km": str(self.logistics_distance_km),
            "logistics_time_min": self.logistics_time_min,
            "price": {
                "reference_price": str(self.price.reference_price),
                "supplier_quote": _dec(self.price.supplier_quote),
                "supplier_id": self.price.supplier_id,
            },
            "transport_cost": str(self.transport_cost),
            "handling_cost": str(self.handling_cost),
            "supplier_id": self.supplier_id,
            "batch_ids": list(self.batch_ids),
        }
