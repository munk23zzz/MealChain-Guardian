"""Task 2 Sprint 2: supply/demand gap engine deterministik.

Kontrak (plan Task 2):
- calculate_surplus: max(supply - demand, 0)
- calculate_shortage: max(demand - supply, 0)
- calculate_supply_gap: keduanya + status, quantities >= 0.
- Negative DITOLAK (ValueError). Engine murni: pemilihan "latest record"
  adalah tanggung jawab caller/service (kontrak latest-record Sprint 1),
  engine tidak pernah menjumlahkan riwayat.
"""

from decimal import Decimal

import pytest

from app.core.gaps import (
    calculate_shortage,
    calculate_supply_gap,
    calculate_surplus,
)


def test_surplus_cianjur_locked_numbers():
    assert calculate_surplus(Decimal("1400"), Decimal("500")) == Decimal("900")


def test_shortage_jakarta_locked_numbers():
    assert calculate_shortage(Decimal("300"), Decimal("1000")) == Decimal("700")


def test_surplus_zero_when_deficit():
    assert calculate_surplus(Decimal("300"), Decimal("1000")) == Decimal("0")


def test_shortage_zero_when_surplus():
    assert calculate_shortage(Decimal("1400"), Decimal("500")) == Decimal("0")


def test_equal_supply_demand_both_zero():
    assert calculate_surplus(Decimal("800"), Decimal("800")) == Decimal("0")
    assert calculate_shortage(Decimal("800"), Decimal("800")) == Decimal("0")


def test_zero_inputs_allowed():
    assert calculate_surplus(Decimal("0"), Decimal("0")) == Decimal("0")
    assert calculate_shortage(Decimal("0"), Decimal("500")) == Decimal("500")


def test_negative_inputs_rejected():
    with pytest.raises(ValueError, match="negatif"):
        calculate_surplus(Decimal("-1"), Decimal("500"))
    with pytest.raises(ValueError, match="negatif"):
        calculate_shortage(Decimal("500"), Decimal("-0.01"))
    with pytest.raises(ValueError, match="negatif"):
        calculate_supply_gap(Decimal("-5"), Decimal("5"))


def test_supply_gap_balanced_and_status():
    gap = calculate_supply_gap(Decimal("900"), Decimal("900"))
    assert gap.surplus_kg == Decimal("0")
    assert gap.shortage_kg == Decimal("0")
    assert gap.status == "balanced"


def test_supply_gap_surplus_and_shortage_status():
    g1 = calculate_supply_gap(Decimal("1400"), Decimal("500"))
    assert g1.surplus_kg == Decimal("900")
    assert g1.shortage_kg == Decimal("0")
    assert g1.status == "surplus"
    g2 = calculate_supply_gap(Decimal("300"), Decimal("1000"))
    assert g2.surplus_kg == Decimal("0")
    assert g2.shortage_kg == Decimal("700")
    assert g2.status == "shortage"


def test_gap_is_deterministic_and_coerces_numeric():
    a = calculate_supply_gap(1400, 500)  # int coercion
    b = calculate_supply_gap("1400", "500")  # str coercion
    assert a == b
    assert a.surplus_kg == Decimal("900")


def test_engine_does_not_sum_history():
    """Engine murni: dua snapshot diberikan caller → engine hanya melihat
    nilai yang dikirim (latest-record selection di caller)."""
    latest_supply, latest_demand = Decimal("1400"), Decimal("500")
    older_supply, older_demand = Decimal("1200"), Decimal("450")
    assert calculate_surplus(latest_supply, latest_demand) == Decimal("900")
    assert calculate_surplus(older_supply, older_demand) == Decimal("750")
