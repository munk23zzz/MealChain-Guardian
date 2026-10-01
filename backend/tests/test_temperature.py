"""Test parser interval suhu (Task 1, plan Sprint 1 domain core)."""

from app.core.temperature import summarize_temperature_log


def test_two_in_range_samples_ten_minutes_apart():
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.5},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.observed_minutes == 10.0
    assert summary.outside_minutes == 0.0
    assert summary.complete is True
    assert summary.issues == ()


def test_out_of_range_first_sample_counts_its_interval():
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 12.0},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.0},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.observed_minutes == 10.0
    assert summary.outside_minutes == 10.0
    assert summary.complete is True


def test_unsorted_input_sorted_before_summarizing():
    log = [
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 12.0},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.observed_minutes == 10.0
    assert summary.outside_minutes == 10.0
    assert summary.complete is True


def test_duplicate_timestamp_flags_incomplete():
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.5},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.0},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.complete is False
    assert any("duplikat" in issue for issue in summary.issues)
    assert summary.observed_minutes >= 0.0


def test_malformed_entry_flags_incomplete():
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
        {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": "panas"},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.complete is False
    assert any("malformed" in issue for issue in summary.issues)


def test_fewer_than_two_samples_flags_incomplete():
    log = [{"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0}]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.complete is False
    assert summary.observed_minutes == 0.0
    assert any("sample" in issue for issue in summary.issues)


def test_inverted_safe_range_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        summarize_temperature_log(
            [
                {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0},
                {"timestamp": "2026-10-01T00:10:00+00:00", "temperature_c": 4.0},
            ],
            safe_min_c=10.0,
            safe_max_c=2.0,
        )
