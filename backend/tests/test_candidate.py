"""Task 1 Sprint 2: model kandidat balancing deterministik.

Kontrak (plan Task 1):
- Immutable, deterministik (equality + serialisasi stabil).
- source == destination ditolak; quantity wajib > 0.
- Faktor [0,1]: demand_fit, supply_availability, freshness_score,
  supplier_reliability.
- safety_status eksplisit: pending|pass|fail|needs_verification.
- freshness_status: pass|needs_verification|fail.
- Dua lapis harga: reference (pihps benchmark) + quote supplier;
  identitas supplier di supplier_id, BUKAN dienkode di source string.
- Candidate Score TIDAK ada di model (dihitung Task 5).
"""

import json
from decimal import Decimal

import pytest

from app.core.candidate import (
    BalancingCandidate,
    CandidateValidationError,
    PriceInfo,
)


def _price(**overrides):
    base = {
        "reference_price": Decimal("26500"),
        "supplier_quote": Decimal("26200"),
        "supplier_id": "11111111-1111-1111-1111-111111111111",
    }
    base.update(overrides)
    return PriceInfo(**base)


def _candidate(**overrides):
    base = {
        "source_location": "Cianjur",
        "destination_location": "Jakarta",
        "commodity": "telur",
        "quantity_kg": Decimal("500"),
        "demand_fit": Decimal("1"),
        "supply_availability": Decimal("1"),
        "freshness_score": Decimal("0.9"),
        "freshness_status": "pass",
        "safety_status": "pass",
        "supplier_reliability": Decimal("0.8"),
        "logistics_feasible": True,
        "logistics_distance_km": Decimal("120"),
        "logistics_time_min": 150,
        "price": _price(),
    }
    base.update(overrides)
    return BalancingCandidate(**base)


def test_valid_candidate_holds_all_fields():
    c = _candidate()
    assert c.source_location == "Cianjur"
    assert c.destination_location == "Jakarta"
    assert c.commodity == "telur"
    assert c.quantity_kg == Decimal("500")
    assert c.safety_status == "pass"
    assert c.freshness_status == "pass"


def test_same_source_and_destination_rejected():
    with pytest.raises(CandidateValidationError, match="sama"):
        _candidate(destination_location="Cianjur")


def test_quantity_must_be_strictly_positive():
    with pytest.raises(CandidateValidationError, match="quantity"):
        _candidate(quantity_kg=Decimal("0"))
    with pytest.raises(CandidateValidationError, match="quantity"):
        _candidate(quantity_kg=Decimal("-5"))


def test_factor_out_of_range_rejected():
    with pytest.raises(CandidateValidationError):
        _candidate(demand_fit=Decimal("1.5"))
    with pytest.raises(CandidateValidationError):
        _candidate(freshness_score=Decimal("-0.1"))
    with pytest.raises(CandidateValidationError):
        _candidate(supplier_reliability=Decimal("2"))


def test_safety_status_must_be_explicit_valid_value():
    for status in ("pending", "pass", "fail", "needs_verification"):
        assert _candidate(safety_status=status).safety_status == status
    with pytest.raises(CandidateValidationError, match="safety_status"):
        _candidate(safety_status="dead")


def test_freshness_status_limited_to_three_bands():
    for status in ("pass", "needs_verification", "fail"):
        assert _candidate(freshness_status=status).freshness_status == status
    with pytest.raises(CandidateValidationError, match="freshness_status"):
        _candidate(freshness_status="PASS")


def test_price_quote_requires_supplier_id():
    """Disiplin dua lapis: quote tanpa identitas supplier ditolak."""
    with pytest.raises(CandidateValidationError, match="supplier_id"):
        _price(supplier_quote=Decimal("26200"), supplier_id=None)


def test_price_reference_must_be_positive():
    with pytest.raises(CandidateValidationError):
        _price(reference_price=Decimal("0"))
    with pytest.raises(CandidateValidationError):
        _price(supplier_quote=Decimal("-1"))


def test_price_reference_only_is_allowed():
    """Referensi pasar boleh berdiri sendiri tanpa quote (pihps benchmark)."""
    p = _price(supplier_quote=None, supplier_id=None)
    assert p.supplier_quote is None
    assert p.supplier_id is None


def test_candidate_is_immutable():
    c = _candidate()
    with pytest.raises(Exception):
        c.quantity_kg = Decimal("999")


def test_equality_and_serialization_deterministic():
    a = _candidate()
    b = _candidate()
    assert a == b
    assert a.to_dict() == b.to_dict()
    assert json.dumps(a.to_dict()) == json.dumps(b.to_dict())
    d = a.to_dict()
    assert d["quantity_kg"] == "500"
    assert d["freshness_score"] == "0.9"
    assert d["logistics_feasible"] is True


def test_numeric_coercion_from_int_and_str():
    c = _candidate(quantity_kg=500, demand_fit="0.75")
    assert c.quantity_kg == Decimal("500")
    assert c.demand_fit == Decimal("0.75")


def test_delivered_cost_inputs_default_zero_and_reject_negative():
    c = _candidate()
    assert c.transport_cost == Decimal("0")
    assert c.handling_cost == Decimal("0")
    with pytest.raises(CandidateValidationError):
        _candidate(transport_cost=Decimal("-1"))
    with pytest.raises(CandidateValidationError):
        _candidate(handling_cost=Decimal("-0.01"))
