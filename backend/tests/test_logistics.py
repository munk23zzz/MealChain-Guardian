"""Test logistics matrix dan feasibility (Task 5, plan Sprint 1 domain core)."""

import pytest

from app.core.logistics import DISTANCE_KM, LOCATIONS, estimate_logistics


def test_locations_exactly_ten_seed_locations():
    assert LOCATIONS == (
        "Jakarta", "Bogor", "Cianjur", "Bandung", "Semarang",
        "Yogyakarta", "Surabaya", "Malang", "Palembang", "Medan",
    )


def test_matrix_has_exactly_45_unique_pairs():
    assert len(DISTANCE_KM) == 45
    keys = [frozenset(k) for k in DISTANCE_KM]
    assert len(set(keys)) == len(keys)


def test_cianjur_jakarta_locked_value():
    assert DISTANCE_KM[frozenset({"Cianjur", "Jakarta"})] == 120


def test_matrix_pairs_cover_all_location_combinations():
    expected = {
        frozenset({a, b})
        for i, a in enumerate(LOCATIONS)
        for b in LOCATIONS[i + 1:]
    }
    assert set(DISTANCE_KM) == expected


def test_cianjur_jakarta_estimate_uses_locked_distance_and_time():
    result = estimate_logistics("Cianjur", "Jakarta", quantity_kg=500.0)

    assert result["distance_km"] == 120
    assert result["estimated_time_min"] == pytest.approx(150.0)
    assert result["feasible"] is True


def test_time_formula_distance_speed_plus_handling():
    result = estimate_logistics("Jakarta", "Bogor", quantity_kg=100.0)

    assert result["distance_km"] == 50
    assert result["estimated_time_min"] == pytest.approx(50.0 / 60.0 * 60.0 + 30.0)


def test_same_location_zero_distance():
    result = estimate_logistics("Jakarta", "Jakarta", quantity_kg=100.0)

    assert result["distance_km"] == 0
    assert result["estimated_time_min"] == pytest.approx(30.0)


def test_exact_window_boundary_is_feasible():
    result = estimate_logistics(
        "Cianjur", "Jakarta", quantity_kg=500.0, delivery_window_min=150.0
    )

    assert result["feasible"] is True


def test_window_below_estimate_infeasible():
    result = estimate_logistics(
        "Cianjur", "Jakarta", quantity_kg=500.0, delivery_window_min=149.0
    )

    assert result["feasible"] is False


def test_no_window_always_feasible():
    result = estimate_logistics("Medan", "Jakarta", quantity_kg=10.0)

    assert result["feasible"] is True


def test_unknown_location_rejected():
    with pytest.raises(ValueError):
        estimate_logistics("Cianjur", "Solo", quantity_kg=100.0)


def test_quantity_not_positive_rejected():
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            estimate_logistics("Cianjur", "Jakarta", quantity_kg=bad)


def test_speed_not_positive_rejected():
    with pytest.raises(ValueError):
        estimate_logistics("Cianjur", "Jakarta", quantity_kg=100.0, speed_kmh=0)


def test_negative_window_rejected():
    with pytest.raises(ValueError):
        estimate_logistics(
            "Cianjur", "Jakarta", quantity_kg=100.0, delivery_window_min=-1.0
        )
