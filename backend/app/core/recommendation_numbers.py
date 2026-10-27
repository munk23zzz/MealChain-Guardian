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


#: Komponen biaya yang WAJIB menjumlah ke `safe_delivered_cost` — cermin
#: `app.seed.demo_template.KOMPONEN_BIAYA` dan urutan penjumlahan di
#: `app.core.safe_delivered_cost.calculate_safe_delivered_cost`.
#: Dipakai audit verifier saat `cost_breakdown` tidak memuat kunci `total`
#: (bentuk yang dipakai data kanonik: komponen, bukan total).
KOMPONEN_BIAYA: tuple[str, ...] = (
    "purchase",
    "transport",
    "handling",
    "expected_loss",
    "freshness_risk",
    "safety_penalty",
)


def _total_komponen(cost_breakdown: Any) -> Decimal | None:
    """Jumlah komponen biaya; `None` bila tidak ada satu pun komponen."""
    if not isinstance(cost_breakdown, dict):
        return None
    nilai = [cost_breakdown.get(nama) for nama in KOMPONEN_BIAYA]
    if all(item is None or item == "" for item in nilai):
        return None
    total = Decimal("0")
    for nama, item in zip(KOMPONEN_BIAYA, nilai):
        if item is None or item == "":
            continue
        bagian = _desimal(item, nama=f"cost_breakdown.{nama}")
        if bagian is None:
            continue
        total += bagian
    return total


def ringkasan_rincian(
    safe_delivered_cost: Any,
    cost_breakdown: Any,
) -> dict[str, Any]:
    """Fakta konsistensi SDC vs total rincian — TANPA melempar.

    Verifier agent membutuhkan jawaban "cocok/tidak" sebagai FAKTA yang sudah
    dihitung kode. Aturannya sengaja memakai fungsi & toleransi modul ini
    (`_total_rincian`/`_total_komponen` + `TOLERANSI_RINCIAN`) supaya tidak
    lahir kalkulator kedua: bila aturan pembuatan keputusan berubah, audit ikut
    berubah.

    Sumber total: kunci `cost_breakdown.total` bila ada (bentuk snapshot
    rekomendasi), kalau tidak jumlah `KOMPONEN_BIAYA` (bentuk data kanonik).

    `cocok=None` berarti tidak dapat dinilai (SDC atau total tidak ada /
    tidak terbaca) — pemanggil wajib memperlakukannya sebagai belum terbukti,
    bukan sebagai lulus.
    """
    try:
        biaya = _desimal(safe_delivered_cost, nama="safe_delivered_cost")
        total = _total_rincian(cost_breakdown)
        sumber_total = "total"
        if total is None:
            total = _total_komponen(cost_breakdown)
            sumber_total = "komponen" if total is not None else None
    except InvalidRecommendationNumbers as exc:
        return {
            "safe_delivered_cost": None,
            "breakdown_total": None,
            "selisih": None,
            "toleransi": float(TOLERANSI_RINCIAN),
            "cocok": None,
            "sumber_total": None,
            "alasan": exc.kode,
        }
    if biaya is None or total is None:
        return {
            "safe_delivered_cost": float(biaya) if biaya is not None else None,
            "breakdown_total": float(total) if total is not None else None,
            "selisih": None,
            "toleransi": float(TOLERANSI_RINCIAN),
            "cocok": None,
            "sumber_total": sumber_total,
            "alasan": "rincian_total_tidak_tersedia" if total is None else "sdc_tidak_tersedia",
        }
    selisih = abs(total - biaya)
    cocok = selisih <= (biaya * TOLERANSI_RINCIAN)
    return {
        "safe_delivered_cost": float(biaya),
        "breakdown_total": float(total),
        "selisih": float(selisih),
        "toleransi": float(TOLERANSI_RINCIAN),
        "cocok": cocok,
        "sumber_total": sumber_total,
        "alasan": None if cocok else KODE_RINCIAN_TIDAK_COCOK,
    }

