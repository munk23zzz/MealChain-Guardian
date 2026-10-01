"""Safety engine (Task 3) — hard constraint tanpa jalur override."""

from app.core.temperature import summarize_temperature_log

FAIL_EXCURSION_DEFAULT_MINUTES = 30.0


def evaluate_safety(
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
    max_excursion_minutes: float = FAIL_EXCURSION_DEFAULT_MINUTES,
) -> dict[str, object]:
    if safe_min_c > safe_max_c:
        raise ValueError("safe_min_c tidak boleh lebih besar dari safe_max_c")
    if max_excursion_minutes <= 0:
        raise ValueError("max_excursion_minutes harus positif")

    summary = summarize_temperature_log(temperature_log, safe_min_c, safe_max_c)
    reasons = list(summary.issues)

    if not summary.complete:
        return {
            "safety_status": "needs_verification",
            "reasons": reasons or ["log suhu tidak lengkap"],
            "excursion_minutes": summary.outside_minutes,
        }

    if summary.outside_minutes >= max_excursion_minutes:
        reasons.append(
            f"excursion {summary.outside_minutes:.3f} menit "
            f">= ambang fail {max_excursion_minutes} menit"
        )
        return {
            "safety_status": "fail",
            "reasons": reasons,
            "excursion_minutes": summary.outside_minutes,
        }

    if summary.outside_minutes > 0:
        reasons.append(
            f"excursion {summary.outside_minutes:.3f} menit > 0 "
            f"dan < ambang fail {max_excursion_minutes} menit"
        )
        return {
            "safety_status": "needs_verification",
            "reasons": reasons,
            "excursion_minutes": summary.outside_minutes,
        }

    return {
        "safety_status": "pass",
        "reasons": [],
        "excursion_minutes": 0.0,
    }
