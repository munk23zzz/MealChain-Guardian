"""Safe Delivered Cost engine deterministik (Task 6 Sprint 2).

Kontrak terkunci (plan Task 6):
total = Purchase + Transport + Handling + Expected Loss
        + Freshness Risk Penalty + Safety Risk Penalty

Ruling (ledger 2026-10-05, dicatat sebelum eksekusi):
- expected_loss = purchase × 0.2 × (1 − freshness) — laju loss atas biaya
  beli (koherensi dimensi rupiah).
- freshness_risk = purchase × 0.50 bila freshness < 0.60, else 0.
- safety_risk = purchase × 0.10 bila safety needs_verification, else 0
  (pending/pass = 0; FAIL ditolak SEBELUM perhitungan — ValueError —
  tidak pernah dihitung, tidak pernah diranking).
- Rounding HALF_UP 2dp per komponen; total = jumlah komponen terbulatkan,
  sehingga breakdown selalu menjumlah persis ke total (audit-proof).
- Semua nilai uang diterima apa adanya (str/int/Decimal), tervalidasi
  non-negatif; purchase wajib > 0; freshness ∈ [0,1]; murni deterministik.
"""

from dataclasses import dataclass
from decimal import (
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)

__all__ = [
    "SafeDeliveredCostInputs",
    "SafeDeliveredCostResult",
    "calculate_safe_delivered_cost",
]

_EXPECTED_LOSS_RATE = Decimal("0.2")
_FRESHNESS_RISK_FACTOR = Decimal("0.50")
_FRESHNESS_RISK_THRESHOLD = Decimal("0.60")
_SAFETY_RISK_RATE = Decimal("0.10")
_TWO_DP = Decimal("0.01")

_VALID_SAFETY = frozenset(
    {"pending", "pass", "fail", "needs_verification"}
)


def _to_decimal(value, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} bukan angka valid: {value!r}") from exc


def _require_nonnegative(value, name: str) -> Decimal:
    d = _to_decimal(value, name)
    if d < 0:
        raise ValueError(f"{name} tidak boleh negatif: {d}")
    return d


@dataclass(frozen=True)
class SafeDeliveredCostInputs:
    purchase_cost: Decimal
    transport_cost: Decimal
    handling_cost: Decimal
    freshness_score: Decimal
    safety_status: str

    def __post_init__(self) -> None:
        purchase = _require_nonnegative(self.purchase_cost, "purchase_cost")
        if purchase <= 0:
            raise ValueError("purchase_cost wajib > 0")
        object.__setattr__(self, "purchase_cost", purchase)
        object.__setattr__(
            self,
            "transport_cost",
            _require_nonnegative(self.transport_cost, "transport_cost"),
        )
        object.__setattr__(
            self,
            "handling_cost",
            _require_nonnegative(self.handling_cost, "handling_cost"),
        )
        freshness = _to_decimal(self.freshness_score, "freshness_score")
        if freshness < 0 or freshness > 1:
            raise ValueError(
                f"freshness_score wajib dalam [0,1], dapat {freshness}"
            )
        object.__setattr__(self, "freshness_score", freshness)
        if self.safety_status not in _VALID_SAFETY:
            raise ValueError(
                f"safety_status tidak dikenal: {self.safety_status!r}"
            )


@dataclass(frozen=True)
class SafeDeliveredCostResult:
    purchase_cost: Decimal
    transport_cost: Decimal
    handling_cost: Decimal
    expected_loss: Decimal
    freshness_risk_penalty: Decimal
    safety_risk_penalty: Decimal
    total: Decimal


def calculate_safe_delivered_cost(
    inputs: SafeDeliveredCostInputs,
) -> SafeDeliveredCostResult:
    """SDC lengkap; safety fail ditolak sebelum ada angka dihitung."""
    if inputs.safety_status == "fail":
        raise ValueError(
            "batch dengan safety_status=fail tidak boleh dihitung biaya "
            "eligible-nya — hard exclusion terkunci"
        )
    # Rounding HALF_UP 2dp PER KOMPONEN (kontrak modul), lalu total = jumlah
    # komponen terbulatkan sehingga breakdown selalu menjumlah persis ke total.
    # Sebelumnya hanya expected_loss yang di-quantize: freshness/safety penalty
    # keluar tiga desimal (mis. 12.345,67 × 0,50 = 6.172,835) dan angka itu ikut
    # dipakai membandingkan biaya serta (nanti) dikirim sebagai NetPriceAmount.
    purchase = inputs.purchase_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    transport = inputs.transport_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    handling = inputs.handling_cost.quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    expected_loss = (
        purchase * _EXPECTED_LOSS_RATE * (Decimal("1") - inputs.freshness_score)
    ).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    freshness_risk = (
        (purchase * _FRESHNESS_RISK_FACTOR).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
        if inputs.freshness_score < _FRESHNESS_RISK_THRESHOLD
        else Decimal("0.00")
    )
    safety_risk = (
        (purchase * _SAFETY_RISK_RATE).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
        if inputs.safety_status == "needs_verification"
        else Decimal("0.00")
    )
    total = (
        purchase
        + transport
        + handling
        + expected_loss
        + freshness_risk
        + safety_risk
    )
    return SafeDeliveredCostResult(
        purchase_cost=purchase,
        transport_cost=transport,
        handling_cost=handling,
        expected_loss=expected_loss,
        freshness_risk_penalty=freshness_risk,
        safety_risk_penalty=safety_risk,
        total=total,
    )
