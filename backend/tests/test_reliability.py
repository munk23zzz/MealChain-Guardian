"""Task 4 Sprint 2: foundation reliability supplier deterministik.

Kontrak (plan Task 4):
- normalize_supplier_reliability(value): terima 0..1 inklusif, Decimal.
  Di luar rentang → ValueError. None TIDAK dinormalisasi di sini (kontrak
  eksplisit yang memutuskan default).
- get_supplier_reliability(supplier): ambil reliability_score dari facts;
  default 0.80 HANYA bila facts secara eksplisit menyediakan flag missing
  (kontrak schema: DEFAULT 0.80, CHECK 0..1). Tidak ada prediksi/ML.
"""

from decimal import Decimal

import pytest

from app.core.reliability import (
    DEFAULT_SUPPLIER_RELIABILITY,
    get_supplier_reliability,
    normalize_supplier_reliability,
)


def test_accepts_zero_and_one_inclusive():
    assert normalize_supplier_reliability(Decimal("0")) == Decimal("0")
    assert normalize_supplier_reliability(Decimal("1")) == Decimal("1")


def test_accepts_normal_decimal_float_int_str():
    assert normalize_supplier_reliability(Decimal("0.85")) == Decimal("0.85")
    assert normalize_supplier_reliability(0.9) == Decimal("0.9")
    assert normalize_supplier_reliability(1) == Decimal("1")
    assert normalize_supplier_reliability("0.75") == Decimal("0.75")


def test_rejects_negative_and_above_one():
    with pytest.raises(ValueError, match="0"):
        normalize_supplier_reliability(Decimal("-0.01"))
    with pytest.raises(ValueError, match="1"):
        normalize_supplier_reliability(Decimal("1.01"))


def test_rejects_non_numeric():
    with pytest.raises(ValueError, match="angka"):
        normalize_supplier_reliability("banyak")


def test_get_from_facts():
    assert get_supplier_reliability({"reliability_score": "0.90"}) == Decimal(
        "0.90"
    )


def test_get_default_only_when_contract_supplies_missing():
    # facts yang memang tidak punya nilai (nullable tak ada di schema, tapi
    # kontrak default 0.80 berlaku untuk missing eksplisit dari DB default)
    assert get_supplier_reliability({}) == Decimal(DEFAULT_SUPPLIER_RELIABILITY)
    # None eksplisit juga default (nilai DB NULL tak mungkin karena NOT NULL,
    # tapi kontrak fungsi menutupnya deterministik)
    assert get_supplier_reliability({"reliability_score": None}) == Decimal(
        DEFAULT_SUPPLIER_RELIABILITY
    )


def test_get_validates_out_of_range_from_facts():
    with pytest.raises(ValueError):
        get_supplier_reliability({"reliability_score": "1.5"})


def test_default_constant_matches_schema():
    assert DEFAULT_SUPPLIER_RELIABILITY == "0.80"
