"""Test price deviation (Task 4, plan Sprint 1 domain core)."""

from decimal import Decimal

import pytest

from app.core.price import price_deviation


def test_exact_reference_gives_zero_deviation():
    result = price_deviation(26500, 26500)

    assert result["deviation_pct"] == Decimal("0")
    assert result["status"] == "normal"
    assert result["flagged"] is False


def test_supplier_a_26200_normal():
    result = price_deviation(26200, 26500)

    expected = Decimal("-1.132075471698113207547169811")
    assert result["deviation_pct"] == pytest.approx(expected, abs=Decimal("0.0001"))
    assert result["status"] == "normal"
    assert result["flagged"] is False


def test_supplier_b_27000_normal():
    result = price_deviation(27000, 26500)

    assert result["status"] == "normal"
    assert result["flagged"] is False


def test_supplier_c_32000_anomalous_flagged():
    result = price_deviation(32000, 26500)

    assert result["status"] == "anomalous"
    assert result["flagged"] is True


def test_exact_five_percent_elevated():
    result = price_deviation(27825, 26500)

    assert result["status"] == "elevated"
    assert result["flagged"] is False


def test_exact_fifteen_percent_anomalous_flagged():
    result = price_deviation(30475, 26500)

    assert result["status"] == "anomalous"
    assert result["flagged"] is True


def test_below_five_percent_normal():
    result = price_deviation(27000, 26500)

    assert result["status"] == "normal"


def test_between_five_and_fifteen_elevated():
    result = price_deviation(29000, 26500)

    assert result["status"] == "elevated"


def test_negative_deviation_within_five_percent_normal():
    result = price_deviation(26000, 26500)

    assert result["status"] == "normal"
    assert result["flagged"] is False


def test_negative_deviation_between_five_and_fifteen_elevated():
    result = price_deviation(24000, 26500)

    assert result["status"] == "elevated"


def test_negative_deviation_at_fifteen_anomalous():
    result = price_deviation(22525, 26500)

    assert result["status"] == "anomalous"
    assert result["flagged"] is True


def test_zero_reference_rejected():
    with pytest.raises(ValueError):
        price_deviation(26500, 0)


def test_non_finite_reference_rejected():
    with pytest.raises(ValueError):
        price_deviation(26500, Decimal("NaN"))


def test_non_numeric_input_rejected():
    with pytest.raises(ValueError):
        price_deviation("murah", 26500)
