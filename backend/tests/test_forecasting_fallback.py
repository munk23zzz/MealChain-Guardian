"""Test forecast statistik fallback (Task 7, plan Sprint 1 domain core)."""

import pytest

from app.core.forecasting_fallback import statistical_forecast


def test_flat_history_projects_flat_total():
    result = statistical_forecast([100.0, 100.0, 100.0], horizon_days=7)

    assert result["forecast_qty_kg"] == pytest.approx(700.0)


def test_weighted_recent_history():
    result = statistical_forecast([100.0, 200.0, 300.0], horizon_days=7)

    expected_daily = 300 * 0.5 + 200 * 0.3 + 100 * 0.2
    assert result["forecast_qty_kg"] == pytest.approx(expected_daily * 7)


def test_single_observation_normalizes_weights():
    result = statistical_forecast([250.0], horizon_days=7)

    assert result["forecast_qty_kg"] == pytest.approx(250.0 * 7)


def test_two_observations_normalize_weights():
    result = statistical_forecast([100.0, 200.0], horizon_days=7)

    expected_daily = 200 * (0.5 / 0.8) + 100 * (0.3 / 0.8)
    assert result["forecast_qty_kg"] == pytest.approx(expected_daily * 7)


def test_more_than_three_uses_only_latest_three():
    result = statistical_forecast([999.0, 1.0, 100.0, 200.0, 300.0], horizon_days=7)

    expected_daily = 300 * 0.5 + 200 * 0.3 + 100 * 0.2
    assert result["forecast_qty_kg"] == pytest.approx(expected_daily * 7)


def test_confidence_increases_with_history_length():
    conf1 = statistical_forecast([100.0])["confidence"]
    conf2 = statistical_forecast([100.0, 200.0])["confidence"]
    conf3 = statistical_forecast([100.0, 200.0, 300.0])["confidence"]

    assert 0.0 <= conf1 < conf2 < conf3 <= 1.0


def test_method_label_always_statistical_fallback():
    result = statistical_forecast([100.0, 100.0])

    assert result["method"] == "statistical_fallback"


def test_empty_history_rejected():
    with pytest.raises(ValueError):
        statistical_forecast([])


def test_negative_value_rejected():
    with pytest.raises(ValueError):
        statistical_forecast([100.0, -5.0])


def test_non_finite_value_rejected():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            statistical_forecast([100.0, bad])


def test_invalid_horizon_rejected():
    for bad in (0, -3):
        with pytest.raises(ValueError):
            statistical_forecast([100.0], horizon_days=bad)


def test_invalid_weights_rejected():
    with pytest.raises(ValueError):
        statistical_forecast([100.0, 200.0], weights=(0.5, 0.0))

    with pytest.raises(ValueError):
        statistical_forecast([100.0, 200.0], weights=(0.5, float("nan")))

    with pytest.raises(ValueError):
        statistical_forecast([100.0, 200.0], weights=())
