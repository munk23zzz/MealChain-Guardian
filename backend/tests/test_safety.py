"""Test safety engine (Task 3, plan Sprint 1 domain core)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.safety import evaluate_safety


def _clean_log():
    return [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.5},
    ]


def _excursion_log(minutes_out):
    t0 = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=minutes_out)
    return [
        {"timestamp": t0.isoformat(), "temperature_c": 4.0},
        {"timestamp": t1.isoformat(), "temperature_c": 20.0},
        {"timestamp": t2.isoformat(), "temperature_c": 4.0},
    ]


def test_clean_complete_log_passes():
    result = evaluate_safety(_clean_log(), 0.0, 8.0)

    assert result["safety_status"] == "pass"
    assert result["excursion_minutes"] == 0.0
    assert result["reasons"] == []


def test_excursion_just_under_thirty_minutes_needs_verification():
    result = evaluate_safety(_excursion_log(29.999), 0.0, 8.0)

    assert result["safety_status"] == "needs_verification"
    assert result["excursion_minutes"] == pytest.approx(29.999)


def test_exactly_thirty_minutes_fails():
    result = evaluate_safety(_excursion_log(30.0), 0.0, 8.0)

    assert result["safety_status"] == "fail"


def test_over_thirty_minutes_fails():
    result = evaluate_safety(_excursion_log(90.0), 0.0, 8.0)

    assert result["safety_status"] == "fail"


def test_malformed_log_needs_verification():
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": "panas"},
    ]

    result = evaluate_safety(log, 0.0, 8.0)

    assert result["safety_status"] == "needs_verification"
    assert result["reasons"]


def test_empty_log_needs_verification():
    result = evaluate_safety([], 0.0, 8.0)

    assert result["safety_status"] == "needs_verification"


def test_single_sample_needs_verification():
    log = [{"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0}]
    result = evaluate_safety(log, 0.0, 8.0)

    assert result["safety_status"] == "needs_verification"


def test_inverted_range_raises_value_error():
    with pytest.raises(ValueError):
        evaluate_safety(_clean_log(), 10.0, 2.0)


def test_non_positive_threshold_raises_value_error():
    with pytest.raises(ValueError):
        evaluate_safety(_clean_log(), 0.0, 8.0, max_excursion_minutes=0)


def test_deterministic_repeated_call():
    a = evaluate_safety(_excursion_log(45.0), 0.0, 8.0)
    b = evaluate_safety(list(reversed(_excursion_log(45.0))), 0.0, 8.0)

    assert a == b


def test_status_always_within_contract():
    cases = [
        _clean_log(),
        _excursion_log(29.999),
        _excursion_log(30.0),
        _excursion_log(45.0),
        [],
        [{"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": "x"}],
    ]

    for log in cases:
        status = evaluate_safety(log, 0.0, 8.0)["safety_status"]
        assert status in {"pass", "needs_verification", "fail"}
