"""Task 6 Sprint 2: Safe Delivered Cost deterministik.

Kontrak terkunci (plan Task 6):
total = Purchase + Transport + Handling + Expected Loss
        + Freshness Risk Penalty + Safety Risk Penalty
- Expected loss = purchase × 0.2 × (1 − freshness)  [ruling: laju loss
  atas biaya beli — koheren dimensi rupiah; plan menulis lajunya saja]
- Freshness risk: freshness < 0.60 → penalty = purchase × 0.50
- Safety risk: needs_verification → penalty = purchase × 0.10
- Safety FAIL ditolak SEBELUM perhitungan (ValueError) — tidak pernah
  dihitung, tidak pernah diranking.
- Input uang negatif ditolak; freshness di luar [0,1] ditolak.
- Rounding HALF_UP 2dp per komponen; total = jumlah komponen terbulatkan
  (breakdown selalu menjumlah persis ke total — audit trail).
- Contoh 0.75 di Skill.md §8 = aritmetika saja, bukan klaim PASS
  (0.60–<0.85 adalah needs_verification; eligibility diputuskan scoring).
"""

from decimal import Decimal

import pytest

from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    SafeDeliveredCostResult,
    calculate_safe_delivered_cost,
)


def _inputs(**overrides):
    base = {
        "purchase_cost": Decimal("12500000"),  # 25.000 × 500 kg (Skill §8)
        "transport_cost": Decimal("1000000"),
        "handling_cost": Decimal("250000"),
        "freshness_score": Decimal("1.00"),
        "safety_status": "pass",
    }
    base.update(overrides)
    return SafeDeliveredCostInputs(**base)


def test_clean_batch_sums_all_components():
    r = calculate_safe_delivered_cost(_inputs())
    assert isinstance(r, SafeDeliveredCostResult)
    assert r.expected_loss == Decimal("0")
    assert r.freshness_risk_penalty == Decimal("0")
    assert r.safety_risk_penalty == Decimal("0")
    assert r.total == Decimal("13750000")


def test_expected_loss_formula_locked():
    r = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.75")))
    # 12.500.000 × 0.2 × 0.25 = 625.000 — aritmetika saja, bukan klaim PASS
    assert r.expected_loss == Decimal("625000.00")
    assert r.freshness_risk_penalty == Decimal("0")
    assert r.total == Decimal("14375000.00")


def test_freshness_risk_penalty_below_060():
    r = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.59")))
    assert r.freshness_risk_penalty == Decimal("6250000.00")  # purchase × 0.5
    exp = Decimal("12500000") * Decimal("0.2") * Decimal("0.41")
    assert r.expected_loss == exp.quantize(Decimal("0.01"))


def test_locked_600kg_freshness_050_numeric_breakdown():
    """Contoh Sprint 2 harus menghitung setiap komponen secara eksplisit."""
    purchase = Decimal("600") * Decimal("26200")
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost=purchase,
            transport_cost=Decimal("21600"),
            handling_cost=Decimal("150000"),
            freshness_score=Decimal("0.50"),
        )
    )
    assert r.purchase_cost == Decimal("15720000.00")
    assert r.transport_cost == Decimal("21600.00")
    assert r.handling_cost == Decimal("150000.00")
    assert r.expected_loss == Decimal("1572000.00")
    assert r.freshness_risk_penalty == Decimal("7860000.00")
    assert r.safety_risk_penalty == Decimal("0.00")
    assert r.total == Decimal("25323600.00")
    assert r.total == sum(
        (
            r.purchase_cost,
            r.transport_cost,
            r.handling_cost,
            r.expected_loss,
            r.freshness_risk_penalty,
            r.safety_risk_penalty,
        ),
        Decimal("0"),
    )


def test_freshness_boundary_060_no_penalty():
    r = calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("0.60")))
    assert r.freshness_risk_penalty == Decimal("0")


def test_safety_needs_verification_penalty_10pct():
    r = calculate_safe_delivered_cost(
        _inputs(safety_status="needs_verification")
    )
    assert r.safety_risk_penalty == Decimal("1250000.00")  # purchase × 0.1


def test_safety_pending_no_penalty_not_fail():
    r = calculate_safe_delivered_cost(_inputs(safety_status="pending"))
    assert r.safety_risk_penalty == Decimal("0")


def test_safety_fail_rejected_before_calculation():
    with pytest.raises(ValueError, match="fail"):
        calculate_safe_delivered_cost(_inputs(safety_status="fail"))


def test_negative_costs_rejected():
    with pytest.raises(ValueError, match="transport"):
        calculate_safe_delivered_cost(_inputs(transport_cost=Decimal("-1")))
    with pytest.raises(ValueError, match="handling"):
        calculate_safe_delivered_cost(_inputs(handling_cost=Decimal("-0.01")))
    with pytest.raises(ValueError, match="purchase"):
        calculate_safe_delivered_cost(_inputs(purchase_cost=Decimal("0")))


def test_freshness_out_of_range_rejected():
    with pytest.raises(ValueError, match="0"):
        calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("1.2")))
    with pytest.raises(ValueError, match="0"):
        calculate_safe_delivered_cost(_inputs(freshness_score=Decimal("-0.1")))


def test_zero_transport_and_handling_allowed():
    r = calculate_safe_delivered_cost(
        _inputs(transport_cost=Decimal("0"), handling_cost=Decimal("0"))
    )
    assert r.total == Decimal("12500000.00")


def test_breakdown_sums_exactly_to_total():
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost="12345678.555",
            transport_cost="987654.321",
            handling_cost="0.004",
            freshness_score="0.83",
            safety_status="needs_verification",
        )
    )
    assert (
        r.purchase_cost
        + r.transport_cost
        + r.handling_cost
        + r.expected_loss
        + r.freshness_risk_penalty
        + r.safety_risk_penalty
        == r.total
    )


def test_deterministic_repeat():
    i = _inputs(freshness_score="0.83", safety_status="needs_verification")
    a = calculate_safe_delivered_cost(i)
    b = calculate_safe_delivered_cost(i)
    assert a == b


def test_setiap_komponen_dibulatkan_2dp():
    """Kontrak modul: "Rounding HALF_UP 2dp per komponen; total = jumlah
    komponen terbulatkan".

    Uji audit 2026-10-11: hanya expected_loss yang di-quantize; freshness_risk
    dan safety_risk keluar mentah (mis. 12345.67 × 0.50 = 6172.835) sehingga
    breakdown tidak lagi 2dp — padahal angka ini dipakai membandingkan/meranking
    biaya dan (nanti) dikirim sebagai NetPriceAmount ke SAP.
    """
    r = calculate_safe_delivered_cost(
        _inputs(
            purchase_cost=Decimal("12345.67"),
            transport_cost=Decimal("150.005"),
            handling_cost=Decimal("50.004"),
            freshness_score=Decimal("0.55"),  # < 0.60 → freshness risk aktif
            safety_status="needs_verification",  # → safety risk aktif
        )
    )
    komponen = {
        "purchase_cost": r.purchase_cost,
        "transport_cost": r.transport_cost,
        "handling_cost": r.handling_cost,
        "expected_loss": r.expected_loss,
        "freshness_risk_penalty": r.freshness_risk_penalty,
        "safety_risk_penalty": r.safety_risk_penalty,
        "total": r.total,
    }
    for nama, nilai in komponen.items():
        eksponen = nilai.as_tuple().exponent
        assert isinstance(eksponen, int) and -eksponen <= 2, f"{nama} tidak 2dp: {nilai}"

    # nilai terbulatkan HALF_UP, bukan dipotong
    assert r.freshness_risk_penalty == Decimal("6172.84")  # 6172.835
    assert r.safety_risk_penalty == Decimal("1234.57")  # 1234.567
    assert r.transport_cost == Decimal("150.01")  # 150.005
    assert r.handling_cost == Decimal("50.00")  # 50.004

    # breakdown tetap menjumlah persis ke total
    assert (
        r.purchase_cost
        + r.transport_cost
        + r.handling_cost
        + r.expected_loss
        + r.freshness_risk_penalty
        + r.safety_risk_penalty
        == r.total
    )
