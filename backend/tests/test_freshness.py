"""Test freshness engine (Task 2, plan Sprint 1 domain core)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.freshness import compute_freshness_score


def _clean_log():
    return [
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T10:00:00+00:00", "temperature_c": 4.5},
    ]


def test_fresh_clean_chain_scores_ninety_percent():
    as_of = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    harvested_at = as_of - timedelta(days=2.8)

    score = compute_freshness_score(
        harvested_at=harvested_at,
        as_of=as_of,
        shelf_life_days=28.0,
        temperature_log=_clean_log(),
        safe_min_c=0.0,
        safe_max_c=8.0,
    )

    assert score == pytest.approx(0.90)


def test_excursion_penalty_halves_score_to_seventy_five_percent():
    as_of = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    harvested_at = as_of - timedelta(days=2.8)
    log = [
        {"timestamp": "2026-10-01T09:50:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T10:00:00+00:00", "temperature_c": 20.0},
        {"timestamp": "2026-10-01T10:10:00+00:00", "temperature_c": 4.5},
    ]

    score = compute_freshness_score(
        harvested_at=harvested_at,
        as_of=as_of,
        shelf_life_days=28.0,
        temperature_log=log,
        safe_min_c=0.0,
        safe_max_c=8.0,
    )

    assert score == pytest.approx(0.75)


def test_expired_batch_scores_zero():
    as_of = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
    harvested_at = as_of - timedelta(days=35)

    score = compute_freshness_score(
        harvested_at=harvested_at,
        as_of=as_of,
        shelf_life_days=28.0,
        temperature_log=_clean_log(),
        safe_min_c=0.0,
        safe_max_c=8.0,
    )

    assert score == 0.0


def test_future_harvest_raises_value_error():
    as_of = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        compute_freshness_score(
            harvested_at=as_of + timedelta(hours=1),
            as_of=as_of,
            shelf_life_days=28.0,
            temperature_log=_clean_log(),
            safe_min_c=0.0,
            safe_max_c=8.0,
        )


def test_invalid_shelf_life_raises_value_error():
    as_of = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

    for bad in (0, -5):
        with pytest.raises(ValueError):
            compute_freshness_score(
                harvested_at=as_of - timedelta(days=1),
                as_of=as_of,
                shelf_life_days=bad,
                temperature_log=_clean_log(),
                safe_min_c=0.0,
                safe_max_c=8.0,
            )


def test_classify_boundaries_final_thresholds():
    from app.core.freshness import classify_freshness

    assert classify_freshness(0.85) == "pass"
    assert classify_freshness(0.849999) == "needs_verification"
    assert classify_freshness(0.60) == "needs_verification"
    assert classify_freshness(0.599999) == "fail"


def test_classify_invalid_score_raises_value_error():
    from app.core.freshness import classify_freshness

    for bad in (-0.01, 1.01, float("nan")):
        with pytest.raises(ValueError):
            classify_freshness(bad)


def test_usable_until_exact_datetime():
    from app.core.freshness import compute_usable_until

    harvested_at = datetime(2026, 10, 1, 0, 0, 0, tzinfo=UTC)

    result = compute_usable_until(
        harvested_at=harvested_at,
        shelf_life_days=28.0,
        score=0.90,
    )

    assert result == datetime(2026, 10, 26, 4, 48, 0, tzinfo=UTC)
    assert result.tzinfo is not None
