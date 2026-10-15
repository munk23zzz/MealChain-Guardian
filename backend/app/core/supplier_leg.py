"""Jarak pemasok → SPPG sumber (Fase 7d) — murni, deterministik.

Latar: sampai 2026-10-15 biaya angkut kandidat HANYA memakai matriks
SPPG↔SPPG (`app/core/logistics.py`). Keputusan pemilik 2026-10-15 (plan
`.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md` §7.4 keputusan #4 +
§7.4b) meminta jarak PEMASOK ikut dihitung dalam biaya SDC.

Aturan yang dikunci modul ini:
- Rantai angkut satu batch = **pemasok → SPPG sumber** (kaki pertama) +
  **SPPG sumber → SPPG tujuan** (linehaul, tetap dari `logistics.py`).
- Kaki pertama = jarak antara titik `suppliers.latitude/longitude` dan
  koordinat `locations` SPPG tempat batch berada.
- Rumusnya haversine dari `app/core/geo.py` — satu implementasi, supaya
  angka jarak di biaya tidak pernah berbeda dari angka di halaman Pemasok.
- Koordinat tidak lengkap (NULL/separuh) → hasil `None`; pemanggil WAJIB
  menandainya "tidak diketahui". Nilai 0 km tidak pernah dikarang, karena
  nol berarti "pemasok menempel di dinding SPPG" — klaim yang tidak punya
  dasar di data.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.core.geo import haversine_km

__all__ = [
    "LEG_REFERENCE_COORDINATES",
    "LEG_REFERENCE_MISSING",
    "LEG_REFERENCE_NO_SUPPLIER",
    "supplier_leg_km",
    "supplier_leg_map",
]

# Label jujur yang ikut dikirim ke payload/DB — pembaca angka biaya harus
# bisa membedakan "kaki pertama terhitung" dari "kaki pertama tidak diketahui".
LEG_REFERENCE_COORDINATES = "supplier_coordinates"
LEG_REFERENCE_MISSING = "supplier_coordinates_missing"
LEG_REFERENCE_NO_SUPPLIER = "no_supplier"

_KM_DP = Decimal("0.001")


def _pair(coords) -> Optional[tuple[float, float]]:
    """Normalisasi koordinat; None kalau tidak lengkap/bukan pasangan angka."""
    if not coords:
        return None
    try:
        lat, lon = coords
    except (TypeError, ValueError):
        return None
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def supplier_leg_km(supplier_coords, location_coords) -> Optional[Decimal]:
    """Jarak pemasok→SPPG (km, 3 desimal) atau `None` bila koordinat kurang.

    Pembulatan 3 desimal: presisi yang sama dengan kolom koordinat (6 desimal
    ≈ 0,1 m); lebih halus dari itu hanya menambah angka palsu.
    """
    supplier = _pair(supplier_coords)
    location = _pair(location_coords)
    if supplier is None or location is None:
        return None
    km = haversine_km(supplier[0], supplier[1], location[0], location[1])
    return Decimal(str(km)).quantize(_KM_DP, rounding=ROUND_HALF_UP)


def supplier_leg_map(
    supplier_coords_by_id, location_coords_by_name
) -> dict[tuple[str, str], Decimal]:
    """Peta {(supplier_id, nama lokasi) -> km} untuk pasangan yang lengkap.

    Hanya pasangan dengan DUA koordinat lengkap yang masuk; pasangan lain
    sengaja absen supaya pemanggil menandainya "tidak diketahui" alih-alih
    membaca nol sebagai data.
    """
    out: dict[tuple[str, str], Decimal] = {}
    for supplier_id, supplier_coords in (supplier_coords_by_id or {}).items():
        for location_name, location_coords in (location_coords_by_name or {}).items():
            km = supplier_leg_km(supplier_coords, location_coords)
            if km is None:
                continue
            out[(str(supplier_id), str(location_name))] = km
    return out
