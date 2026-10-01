"""Utility time-series suhu (Task 1) — kontrak shared freshness & safety."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TemperatureSummary:
    observed_minutes: float
    outside_minutes: float
    complete: bool
    issues: tuple[str, ...]


def _parse_entry(entry: dict) -> tuple[datetime, float] | None:
    try:
        ts = datetime.fromisoformat(entry["timestamp"])
        temp = float(entry["temperature_c"])
    except (KeyError, TypeError, ValueError):
        return None
    return ts, temp


def summarize_temperature_log(
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
) -> TemperatureSummary:
    if safe_min_c > safe_max_c:
        raise ValueError("safe_min_c tidak boleh lebih besar dari safe_max_c")

    issues: list[str] = []
    parsed: list[tuple[datetime, float]] = []
    for index, entry in enumerate(temperature_log):
        result = _parse_entry(entry)
        if result is None:
            issues.append(f"malformed entry pada index {index}")
            continue
        parsed.append(result)

    timestamps = [ts for ts, _ in parsed]
    if len(timestamps) != len(set(timestamps)):
        issues.append("timestamp duplikat")

    if len(parsed) < 2:
        issues.append(f"sample kurang dari 2 ({len(parsed)})")
        return TemperatureSummary(
            observed_minutes=0.0,
            outside_minutes=0.0,
            complete=False,
            issues=tuple(issues),
        )

    ordered = sorted(parsed)
    observed_minutes = 0.0
    outside_minutes = 0.0
    for (ts_prev, temp_prev), (ts_curr, _temp_curr) in zip(ordered, ordered[1:]):
        duration = (ts_curr - ts_prev).total_seconds() / 60.0
        observed_minutes += duration
        if temp_prev < safe_min_c or temp_prev > safe_max_c:
            outside_minutes += duration
    return TemperatureSummary(
        observed_minutes=observed_minutes,
        outside_minutes=outside_minutes,
        complete=len(issues) == 0,
        issues=tuple(issues),
    )
