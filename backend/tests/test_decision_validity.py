"""Task 11: validitas decision deterministik.

- is_decision_valid(now, expires_at): wajib timezone-aware keduanya;
  mixed/naive ditolak (ValueError). Exact expiry = expired.
- now < expires_at → valid; now >= expires_at → expired.
- Expired tetap tersimpan (audit), tidak boleh dipakai ulang.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.decision_validity import is_decision_valid

UTC = timezone.utc


def test_valid_before_expiry():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    exp = now + timedelta(minutes=30)
    assert is_decision_valid(now, exp) is True


def test_exact_expiry_is_expired():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    assert is_decision_valid(now, now) is False


def test_after_expiry_is_expired():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    exp = now - timedelta(seconds=1)
    assert is_decision_valid(now, exp) is False


def test_timezone_conversion_respected():
    now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    # 20:00 UTC+7 = 13:00 UTC → 1 jam di masa depan → valid
    exp = datetime(2026, 10, 1, 20, 0, tzinfo=timezone(timedelta(hours=7)))
    assert is_decision_valid(now, exp) is True
    # 19:00 UTC+7 = 12:00 UTC → exact expiry → expired
    exp_exact = datetime(
        2026, 10, 1, 19, 0, tzinfo=timezone(timedelta(hours=7))
    )
    assert is_decision_valid(now, exp_exact) is False


def test_naive_input_rejected():
    now = datetime(2026, 10, 1, 12, 0)
    exp = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)
    with pytest.raises(ValueError):
        is_decision_valid(now, exp)
    with pytest.raises(ValueError):
        is_decision_valid(now.replace(tzinfo=UTC), exp.replace(tzinfo=None))


def test_non_datetime_rejected():
    with pytest.raises(ValueError):
        is_decision_valid("2026-10-01", datetime.now(UTC))
