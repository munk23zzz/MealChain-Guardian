"""Biaya angkut PER TRIP — bukan per ton-km (revisi 2026-10-29b).

Alasan (kritik pemilik, 29 Okt 2026): model lama `300 × km × kg/1000` menagih
150 kg Cianjur–Jakarta Rp 5.400, padahal satu truk box sekali jalan ke Jakarta
berbiaya ratusan ribu rupiah terlepas isinya 150 kg atau 1 ton. Akibatnya
pengiriman kecil terlihat hampir gratis dan pengiriman besar menanggung
ongkos yang tidak pernah dikeluarkan satu pun truk.

Kontrak:

- `biaya = jumlah_trip × (TARIF_TETAP + TARIF_PER_KM × jarak)`
- `jumlah_trip = ceil(berat ÷ KAPASITAS_TRUK_KG)`, minimum 1 trip. Muatan
  600 kg memakai satu truk 1 ton yang berangkat tidak penuh — itu kenyataannya,
  bukan kesalahan hitung.
- Jarak yang dikirim pemanggil adalah jarak TOTAL satu perjalanan. Rute
  pemasok → SPPG asal → SPPG tujuan dikerjakan truk yang sama, jadi tarif tetap
  hanya ditagih SEKALI per trip. Menjumlahkan dua perhitungan per kaki akan
  menagih dua kali biaya berangkat untuk satu pengiriman.
- `jarak = 0` tetap kena tarif tetap (bongkar-muat tidak gratis), dan rincian
  perhitungan ikut dikembalikan supaya panel bukti bisa menjelaskannya.

Angka tarif adalah ASUMSI yang dilabeli `tarif_per_trip_asumsi` sampai ada
angka resmi perusahaan logistik; ia tidak boleh disajikan sebagai tarif nyata.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from math import ceil

__all__ = [
    "BASIS_TARIF",
    "KAPASITAS_TRUK_KG",
    "TARIF_PER_KM",
    "TARIF_TETAP",
    "biaya_angkut_trip",
]

#: Truk box 1 ton — kendaraan yang dipakai SPPG untuk antar-lokasi di Jawa.
KAPASITAS_TRUK_KG = Decimal("1000")
#: Biaya berangkat: bahan bakar saat menunggu, sopir, bongkar-muat.
TARIF_TETAP = Decimal("250000")
#: Biaya jalan per km (BBM + tol + penyusutan).
TARIF_PER_KM = Decimal("4000")

BASIS_TARIF = "tarif_per_trip_asumsi"

_DUA_DESIMAL = Decimal("0.01")


def _desimal(nilai: object, nama: str) -> Decimal:
    if isinstance(nilai, bool):
        raise ValueError(f"{nama} bukan angka valid: {nilai!r}")
    if isinstance(nilai, Decimal):
        hasil = nilai
    else:
        try:
            hasil = Decimal(str(nilai).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{nama} bukan angka valid: {nilai!r}") from exc
    if not hasil.is_finite():
        raise ValueError(f"{nama} bukan angka valid: {nilai!r}")
    return hasil


def biaya_angkut_trip(
    distance_km: object, quantity_kg: object
) -> tuple[Decimal, dict[str, object]]:
    """Biaya satu pengiriman per trip + rincian dasarnya.

    `quantity_kg` wajib > 0: pengiriman tanpa muatan bukan pengiriman, dan
    menagih tarif berangkat untuk muatan nol akan mengarang biaya. Jarak boleh
    0 (barang sudah di lokasi) dan tetap kena tarif tetap.
    """
    jarak = _desimal(distance_km, "distance_km")
    if jarak < 0:
        raise ValueError(f"distance_km tidak boleh negatif: {jarak}")
    berat = _desimal(quantity_kg, "quantity_kg")
    if berat <= 0:
        raise ValueError(f"quantity_kg harus positif: {berat}")

    trip = max(1, ceil(berat / KAPASITAS_TRUK_KG))
    biaya = (TARIF_TETAP + TARIF_PER_KM * jarak) * trip
    biaya = biaya.quantize(_DUA_DESIMAL, rounding=ROUND_HALF_UP)

    return biaya, {
        "basis": BASIS_TARIF,
        "trips": trip,
        "capacity_kg": KAPASITAS_TRUK_KG,
        "fixed_idr": TARIF_TETAP,
        "rate_per_km": TARIF_PER_KM,
        "distance_km": jarak,
        "quantity_kg": berat,
    }
