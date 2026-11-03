"""Price deviation (Task 4) — ambang disetujui Roy: elevated 5%, anomalous 15%."""

from decimal import Decimal, InvalidOperation

ELEVATED_PCT_DEFAULT = Decimal("5")
ANOMALOUS_PCT_DEFAULT = Decimal("15")


def _to_price(value, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} harus angka harga yang valid")
    if isinstance(value, Decimal):
        price = value
    elif isinstance(value, (int, str)):
        try:
            price = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} harus angka harga yang valid") from exc
    else:
        raise ValueError(f"{label} harus angka harga yang valid")
    if not price.is_finite() or price <= 0:
        raise ValueError(f"{label} harus angka harga yang valid (> 0, finite)")
    return price


def price_deviation(
    supplier_price,
    reference_price,
    elevated_pct=ELEVATED_PCT_DEFAULT,
    anomalous_pct=ANOMALOUS_PCT_DEFAULT,
) -> dict[str, object]:
    supplier = _to_price(supplier_price, "supplier_price")
    reference = _to_price(reference_price, "reference_price")

    deviation_pct = (supplier - reference) / reference * Decimal("100")
    magnitude = abs(deviation_pct)

    if magnitude >= anomalous_pct:
        status = "anomalous"
        flagged = True
    elif magnitude >= elevated_pct:
        status = "elevated"
        flagged = False
    else:
        status = "normal"
        flagged = False

    return {
        "deviation_pct": deviation_pct,
        "status": status,
        "flagged": flagged,
    }
