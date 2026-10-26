"""Validasi angka rekomendasi sebelum dipakai (temuan F-09 / A-02).

`POST /decisions` menerima snapshot rekomendasi dari klien lalu menyimpan
`quantity_kg` dan `safe_delivered_cost` apa adanya; angka itu kemudian dipakai
apa adanya untuk menerbitkan purchase order. Artinya klien bisa mengarang
kuantitas/harga — termasuk nilai negatif atau bukan angka (yang dulu berakhir
sebagai HTTP 500 `InvalidOperation`).

Modul ini murni: mengubah teks/angka menjadi `Decimal` yang tervalidasi, atau
melempar `InvalidRecommendationNumbers` dengan kode alasan yang stabil.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

#: Batas kewajaran untuk satu keputusan pengadaan (bukan batas ilmiah):
#: 1.000 ton per keputusan dan Rp 1 triliun per keputusan sudah jauh di atas
#: operasi nyata mana pun, sehingga nilai di atasnya pasti salah input.
MAKS_KUANTITAS_KG = Decimal("1000000")
MAKS_BIAYA = Decimal("1000000000000")
#: Batas harga satuan turunan (Rp/kg). TIDAK ada batas bawah selain "positif":
#: nilai murah tetap sah (mis. 12 kg senilai 1.000 → ~83/kg pada data uji), dan
#: menolaknya akan memblokir keputusan nyata. Yang dijaga hanya absurditas.
MAKS_HARGA_SATUAN = Decimal("5000000")
#: Toleransi ketidakcocokan antara `safe_delivered_cost` dan total rinciannya.
TOLERANSI_RINCIAN = Decimal("0.01")

KODE_BUKAN_ANGKA = "bukan_angka"
KODE_TIDAK_POSITIF = "tidak_positif"
KODE_MELEBIHI_BATAS = "melebihi_batas"
KODE_HARGA_SATUAN_TIDAK_WAJAR = "harga_satuan_tidak_wajar"
KODE_RINCIAN_TIDAK_COCOK = "rincian_tidak_cocok"


class InvalidRecommendationNumbers(ValueError):  # noqa: N818 - nama dipakai lintas modul
    """Angka rekomendasi tidak sah; `kode` stabil untuk pemetaan HTTP."""

    def __init__(self, kode: str, pesan: str) -> None:
        super().__init__(pesan)
        self.kode = kode


def _desimal(nilai: Any, *, nama: str) -> Decimal | None:
    if nilai is None or nilai == "":
        return None
    if isinstance(nilai, bool):  # bool adalah int di Python — bukan angka bisnis
        raise InvalidRecommendationNumbers(KODE_BUKAN_ANGKA, f"{nama} bukan angka")
    try:
        hasil = Decimal(str(nilai).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidRecommendationNumbers(KODE_BUKAN_ANGKA, f"{nama} bukan angka") from exc
    if not hasil.is_finite():
        raise InvalidRecommendationNumbers(KODE_BUKAN_ANGKA, f"{nama} bukan angka berhingga")
    return hasil


def _total_rincian(cost_breakdown: Any) -> Decimal | None:
    if not isinstance(cost_breakdown, dict):
        return None
    nilai = cost_breakdown.get("total")
    if nilai is None:
        return None
    return _desimal(nilai, nama="cost_breakdown.total")


def validasi_angka_rekomendasi(
    quantity_kg: Any,
    safe_delivered_cost: Any,
    cost_breakdown: Any = None,
) -> tuple[Decimal | None, Decimal | None]:
    """Kembalikan `(qty, biaya)` tervalidasi, atau lempar penolakan beralasan."""
    qty = _desimal(quantity_kg, nama="quantity_kg")
    biaya = _desimal(safe_delivered_cost, nama="safe_delivered_cost")

    if qty is not None:
        if qty <= 0:
            raise InvalidRecommendationNumbers(
                KODE_TIDAK_POSITIF, "quantity_kg harus lebih besar dari 0"
            )
        if qty > MAKS_KUANTITAS_KG:
            raise InvalidRecommendationNumbers(
                KODE_MELEBIHI_BATAS, "quantity_kg melebihi batas kewajaran"
            )

    if biaya is not None:
        if biaya <= 0:
            raise InvalidRecommendationNumbers(
                KODE_TIDAK_POSITIF, "safe_delivered_cost harus lebih besar dari 0"
            )
        if biaya > MAKS_BIAYA:
            raise InvalidRecommendationNumbers(
                KODE_MELEBIHI_BATAS, "safe_delivered_cost melebihi batas kewajaran"
            )

    if qty is not None and biaya is not None:
        harga_satuan = biaya / qty
        if harga_satuan <= 0 or harga_satuan > MAKS_HARGA_SATUAN:
            raise InvalidRecommendationNumbers(
                KODE_HARGA_SATUAN_TIDAK_WAJAR,
                "harga satuan turunan (cost / quantity) tidak wajar",
            )
        total = _total_rincian(cost_breakdown)
        if total is not None:
            selisih = abs(total - biaya)
            if selisih > (biaya * TOLERANSI_RINCIAN):
                raise InvalidRecommendationNumbers(
                    KODE_RINCIAN_TIDAK_COCOK,
                    "total cost_breakdown tidak cocok dengan safe_delivered_cost",
                )

    return qty, biaya
