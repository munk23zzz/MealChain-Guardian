"""Foundation reliability supplier deterministik (Task 4 Sprint 2).

Kontrak plan Task 4:
- Nilai valid 0..1 inklusif; di luar rentang ditolak (ValueError).
- Default 0.80 HANYA dipakai ketika kontrak eksplisit menyuplai nilai
  yang hilang (Schema.md §1: reliability_score DEFAULT 0.80, CHECK 0..1).
- Tidak ada prediksi, tidak ada ML, tidak ada smoothing — angka apa
  adanya dari facts.
- `normalize_supplier_reliability(None)` sengaja ditolak: keputusan
  default adalah kontrak pemanggil (get_supplier_reliability), bukan
  perilaku diam di normalizer.
"""

from decimal import Decimal, InvalidOperation

__all__ = [
    "DEFAULT_SUPPLIER_RELIABILITY",
    "get_supplier_reliability",
    "normalize_supplier_reliability",
]

# Kontrak Schema.md §1: NUMERIC(3,2) NOT NULL DEFAULT 0.80 CHECK 0..1
DEFAULT_SUPPLIER_RELIABILITY = "0.80"


def normalize_supplier_reliability(value) -> Decimal:
    """Terima 0..1 ( inklusif) dari int/float/str/Decimal; tolak lainnya."""
    if value is None:
        raise ValueError(
            "reliability None tidak dinormalisasi — gunakan kontrak "
            "eksplisit (DEFAULT 0.80) di level pemanggil"
        )
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"reliability wajib angka, dapat {value!r}") from exc
    if d < 0 or d > 1:
        raise ValueError(f"reliability wajib dalam rentang [0,1]: {d}")
    return d


def get_supplier_reliability(supplier) -> Decimal:
    """Ambil reliability_score dari facts supplier (mapping).

    Missing/None → default kontrak 0.80 (schema DEFAULT); nilai ada →
    divalidasi rentang [0,1] tanpa dimodifikasi.
    """
    if not hasattr(supplier, "get"):
        raise ValueError("supplier facts wajib mapping (punya .get)")
    value = supplier.get("reliability_score")
    if value is None:
        return Decimal(DEFAULT_SUPPLIER_RELIABILITY)
    return normalize_supplier_reliability(value)
