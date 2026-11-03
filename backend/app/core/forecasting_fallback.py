"""Forecast statistik fallback (Task 7) — transparan, selalu berlabel fallback."""

import math

_DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)


def _validate_weights(weights) -> tuple[float, ...]:
    if len(weights) == 0 or len(weights) > 3:
        raise ValueError("weights harus 1-3 bobot terbaru-dulu")
    for w in weights:
        if not math.isfinite(w) or w <= 0:
            raise ValueError("weights harus finite dan > 0")
    if sum(weights) <= 0:
        raise ValueError("total weights harus positif")
    return tuple(float(w) for w in weights)


def statistical_forecast(
    daily_kg: list[float],
    horizon_days: int = 7,
    weights: tuple[float, ...] = _DEFAULT_WEIGHTS,
) -> dict[str, float | str]:
    if not daily_kg:
        raise ValueError("histori demand tidak boleh kosong")
    if not isinstance(horizon_days, int) or horizon_days <= 0:
        raise ValueError("horizon_days harus integer positif")

    cleaned: list[float] = []
    for value in daily_kg:
        if not math.isfinite(value) or value < 0:
            raise ValueError("nilai histori harus finite dan >= 0")
        cleaned.append(float(value))

    weights = _validate_weights(weights)

    recent = list(reversed(cleaned[-len(weights):]))
    total_weight = sum(weights[: len(recent)])
    daily_rate = sum(w * v for w, v in zip(weights, recent)) / total_weight

    max_history = 3.0
    confidence = min(1.0, len(recent) / max_history)

    return {
        "forecast_qty_kg": daily_rate * horizon_days,
        "method": "statistical_fallback",
        "confidence": confidence,
    }
