"""Supply/demand gap engine deterministik (Task 2 Sprint 2).

Kontrak plan Task 2:
- surplus = max(supply - demand, 0)
- shortage = max(demand - supply, 0)
- calculate_supply_gap mengembalikan keduanya + status.
- Quantity negatif DITOLAK. Zero diperbolehkan.
- Engine MURNI: seleksi "latest record" adalah tanggung jawab
  caller/service (kontrak latest-record Sprint 1); engine tidak pernah
  menjumlahkan/menggabungkan riwayat.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

__all__ = [
    "SupplyDemandGap",
    "calculate_shortage",
    "calculate_supply_gap",
    "calculate_surplus",
]


def _to_decimal(value, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} bukan angka valid: {value!r}") from exc


def _require_nonnegative(d: Decimal, name: str) -> None:
    if d < 0:
        raise ValueError(f"{name} tidak boleh negatif, dapat {d}")


def calculate_surplus(supply_kg, demand_kg) -> Decimal:
    """Kelebihan pasokan: max(supply - demand, 0)."""
    supply = _to_decimal(supply_kg, "supply_kg")
    demand = _to_decimal(demand_kg, "demand_kg")
    _require_nonnegative(supply, "supply_kg")
    _require_nonnegative(demand, "demand_kg")
    gap = supply - demand
    return gap if gap > 0 else Decimal("0")


def calculate_shortage(supply_kg, demand_kg) -> Decimal:
    """Kekurangan pasokan: max(demand - supply, 0)."""
    supply = _to_decimal(supply_kg, "supply_kg")
    demand = _to_decimal(demand_kg, "demand_kg")
    _require_nonnegative(supply, "supply_kg")
    _require_nonnegative(demand, "demand_kg")
    gap = demand - supply
    return gap if gap > 0 else Decimal("0")


@dataclass(frozen=True)
class SupplyDemandGap:
    supply_kg: Decimal
    demand_kg: Decimal
    surplus_kg: Decimal
    shortage_kg: Decimal
    status: str  # 'surplus' | 'shortage' | 'balanced'


def calculate_supply_gap(supply_kg, demand_kg) -> SupplyDemandGap:
    """Gap lengkap satu pasang supply/demand + status."""
    supply = _to_decimal(supply_kg, "supply_kg")
    demand = _to_decimal(demand_kg, "demand_kg")
    _require_nonnegative(supply, "supply_kg")
    _require_nonnegative(demand, "demand_kg")
    surplus = calculate_surplus(supply, demand)
    shortage = calculate_shortage(supply, demand)
    if surplus > 0:
        status = "surplus"
    elif shortage > 0:
        status = "shortage"
    else:
        status = "balanced"
    return SupplyDemandGap(
        supply_kg=supply,
        demand_kg=demand,
        surplus_kg=surplus,
        shortage_kg=shortage,
        status=status,
    )
