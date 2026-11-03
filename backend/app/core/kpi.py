"""KPI core (S4-03) — helper murni tanpa I/O.

Deterministik penuh: quantize HALF_UP 2 desimal, resolve root lineage
(dedupe deteksi berulang), trend dari previous_value. Tidak ada LLM,
tidak ada nilai default palsu — missing tetap None.
"""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def quantize2(value: Decimal) -> Decimal:
    """Bulatkan HALF_UP ke 2 desimal (kontrak O-NUM: HALF_UP)."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def resolve_root(parent_map: dict, decision_id) -> str:
    """Resolve akar lineage (supersedes_id chain) untuk dedupe case.

    parent_map memetakan decision_id -> parent_id (hanya yang punya parent).
    """
    current = decision_id
    seen = set()
    while current in parent_map and current not in seen:
        seen.add(current)
        current = parent_map[current]
    return str(current)


def trend_of(current: Decimal | None, previous: Decimal | None) -> str | None:
    """Tren sederhana; None bila salah satu nilai tidak comparable."""
    if current is None or previous is None:
        return None
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"
