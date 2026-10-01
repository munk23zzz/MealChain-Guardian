"""Freshness engine (Task 2) — ambang final Roy 2026-10-01."""

from datetime import datetime, timedelta

from app.core.temperature import summarize_temperature_log

PASS_THRESHOLD = 0.85
VERIFY_THRESHOLD = 0.60
TEMP_PENALTY_WEIGHT = 0.30


def compute_freshness_score(
    harvested_at: datetime,
    as_of: datetime,
    shelf_life_days: float,
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
) -> float:
    if harvested_at > as_of:
        raise ValueError("harvested_at tidak boleh di masa depan")
    if shelf_life_days <= 0:
        raise ValueError("shelf_life_days harus positif")

    age_fraction = (as_of - harvested_at).total_seconds() / (shelf_life_days * 86400.0)
    base = max(0.0, 1.0 - age_fraction)

    summary = summarize_temperature_log(temperature_log, safe_min_c, safe_max_c)
    if summary.observed_minutes > 0 and summary.complete:
        outside_fraction = summary.outside_minutes / summary.observed_minutes
    else:
        outside_fraction = 0.0

    return max(0.0, min(1.0, base - TEMP_PENALTY_WEIGHT * outside_fraction))


def classify_freshness(
    score: float,
    pass_threshold: float = PASS_THRESHOLD,
    verify_threshold: float = VERIFY_THRESHOLD,
) -> str:
    if score != score or score < 0.0 or score > 1.0:
        raise ValueError("score harus di [0.0, 1.0] dan bukan NaN")
    if verify_threshold >= pass_threshold:
        raise ValueError("verify_threshold harus di bawah pass_threshold")
    if score >= pass_threshold:
        return "pass"
    if score >= verify_threshold:
        return "needs_verification"
    return "fail"


def compute_usable_until(
    harvested_at: datetime,
    shelf_life_days: float,
    score: float,
) -> datetime:
    if shelf_life_days <= 0:
        raise ValueError("shelf_life_days harus positif")
    if score != score or score < 0.0 or score > 1.0:
        raise ValueError("score harus di [0.0, 1.0] dan bukan NaN")
    return harvested_at + timedelta(days=shelf_life_days * score)
