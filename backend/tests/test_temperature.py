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


def test_out_of_range_last_sample_counts_its_interval():
    """Audit 2026-10-29, AUD-007: sampel terakhir tidak boleh diabaikan.

    Sebelum perbaikan, interval [5, 20] diatribusikan hanya ke sampel sebelumnya
    (5 °C), sehingga log yang memanas di ujung perjalanan menghasilkan
    `outside_minutes == 0` dan lolos gerbang sebagai "tanpa excursion".
    """
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 5.0},
        {"timestamp": "2026-10-01T01:00:00+00:00", "temperature_c": 5.0},
        {"timestamp": "2026-10-01T02:00:00+00:00", "temperature_c": 20.0},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.observed_minutes == 120.0
    assert summary.outside_minutes == 60.0, "interval 01:00–02:00 berakhir di 20 °C"
    assert summary.complete is True


def test_fully_out_of_range_log_counts_every_interval():
    """Semua interval di luar rentang (kedua ujung) — tidak boleh dobel hitung."""
    log = [
        {"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 20.0},
        {"timestamp": "2026-10-01T01:00:00+00:00", "temperature_c": 20.0},
        {"timestamp": "2026-10-01T02:00:00+00:00", "temperature_c": 5.0},
    ]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.observed_minutes == 120.0
    assert summary.outside_minutes == 120.0


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
    # Pesan sengaja berbahasa Indonesia (dibaca di kartu "Bukti suhu"); tes lama
    # masih mengejar kata Inggris "malformed" sehingga merah walau perilakunya
    # benar. Perilaku yang dikunci tetap: entri rusak -> complete False.
    assert any("rusak" in issue for issue in summary.issues), summary.issues


def test_fewer_than_two_samples_flags_incomplete():
    log = [{"timestamp": "2026-10-01T00:00:00+00:00", "temperature_c": 4.0}]

    summary = summarize_temperature_log(log, safe_min_c=0.0, safe_max_c=8.0)

    assert summary.complete is False
    assert summary.observed_minutes == 0.0
    assert any("sampel" in issue for issue in summary.issues), summary.issues


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
