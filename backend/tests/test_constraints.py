"""Test constraint primitives (Task 6, plan Sprint 1 domain core)."""

import pytest

from app.core.constraints import (
    check_capacity,
    check_delivery_window,
    is_batch_eligible,
)


def test_capacity_exact_match_is_sufficient():
    result = check_capacity(available_kg=500.0, required_kg=500.0)

    assert result["sufficient"] is True
    assert result["headroom_kg"] == pytest.approx(0.0)


def test_capacity_insufficient_is_flagged():
    result = check_capacity(available_kg=400.0, required_kg=500.0)

    assert result["sufficient"] is False
    assert result["headroom_kg"] == pytest.approx(-100.0)


def test_capacity_surplus_headroom_positive():
    result = check_capacity(available_kg=900.0, required_kg=500.0)

    assert result["sufficient"] is True
    assert result["headroom_kg"] == pytest.approx(400.0)


def test_capacity_rejects_negative_or_nonfinite():
    bad_cases = [
        (-1.0, 100.0),
        (100.0, -1.0),
        (float("nan"), 100.0),
        (float("inf"), 100.0),
        (100.0, float("nan")),
        (100.0, 0.0),
    ]

    for available, required in bad_cases:
        with pytest.raises(ValueError):
            check_capacity(available_kg=available, required_kg=required)


def test_delivery_window_exact_estimate_is_feasible():
    assert check_delivery_window(estimated_time_min=150.0, delivery_window_min=150.0) is True


def test_delivery_window_over_estimate_infeasible():
    assert check_delivery_window(estimated_time_min=151.0, delivery_window_min=150.0) is False


def test_delivery_window_under_estimate_feasible():
    assert check_delivery_window(estimated_time_min=120.0, delivery_window_min=150.0) is True


def test_delivery_window_rejects_invalid_inputs():
    bad_cases = [
        (-1.0, 150.0),
        (float("nan"), 150.0),
        (float("inf"), 150.0),
        (120.0, -5.0),
    ]

    for estimated, window in bad_cases:
        with pytest.raises(ValueError):
            check_delivery_window(estimated_time_min=estimated, delivery_window_min=window)


def test_freshness_fail_makes_batch_ineligible():
    assert is_batch_eligible(freshness_status="fail", safety_status="pass") is False


def test_safety_fail_makes_batch_ineligible():
    assert is_batch_eligible(freshness_status="pass", safety_status="fail") is False


def test_both_fail_makes_batch_ineligible():
    assert is_batch_eligible(freshness_status="fail", safety_status="fail") is False


def test_pass_pass_eligible():
    assert is_batch_eligible(freshness_status="pass", safety_status="pass") is True


def test_needs_verification_is_forwardable_to_review():
    assert is_batch_eligible(freshness_status="needs_verification", safety_status="pass") is True
    assert is_batch_eligible(freshness_status="pass", safety_status="needs_verification") is True


def test_unknown_status_rejected():
    with pytest.raises(ValueError):
        is_batch_eligible(freshness_status="ok", safety_status="pass")

    with pytest.raises(ValueError):
        is_batch_eligible(freshness_status="pass", safety_status="PASS")
