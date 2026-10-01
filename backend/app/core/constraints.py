"""Constraint primitives (Task 6) — capacity, delivery window, eligibility."""

import math

_FRESHNESS_STATUSES = {"pass", "needs_verification", "fail"}
_SAFETY_STATUSES = {"pass", "needs_verification", "fail"}


def _require_non_negative_finite(value: float, label: str) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} harus finite dan >= 0")
    return value


def check_capacity(available_kg: float, required_kg: float) -> dict[str, float | bool]:
    _require_non_negative_finite(available_kg, "available_kg")
    _require_non_negative_finite(required_kg, "required_kg")
    if required_kg == 0:
        raise ValueError("required_kg harus > 0")

    headroom_kg = available_kg - required_kg
    return {
        "sufficient": headroom_kg >= 0.0,
        "headroom_kg": headroom_kg,
    }


def check_delivery_window(estimated_time_min: float, delivery_window_min: float) -> bool:
    _require_non_negative_finite(estimated_time_min, "estimated_time_min")
    _require_non_negative_finite(delivery_window_min, "delivery_window_min")

    return estimated_time_min <= delivery_window_min


def is_batch_eligible(freshness_status: str, safety_status: str) -> bool:
    if freshness_status not in _FRESHNESS_STATUSES:
        raise ValueError(f"freshness_status tidak dikenal: {freshness_status!r}")
    if safety_status not in _SAFETY_STATUSES:
        raise ValueError(f"safety_status tidak dikenal: {safety_status!r}")

    if freshness_status == "fail" or safety_status == "fail":
        return False
    return True
