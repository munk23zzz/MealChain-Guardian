"""Rekonsiliasi `cost_breakdown` dengan `safe_delivered_cost` (D-01/BL-01/NUM-01).

Latar (audit integritas database 26 Okt 2026, temuan D-01): kartu kedua tiap
kasus dibuat dengan kuantitas & SDC 70% dari aslinya, tetapi `cost_breakdown`
disalin APA ADANYA. Hasil terukur: 4 keputusan `pending_approval` /
`verifier_flagged` menampilkan rincian yang bila dijumlahkan berbeda
Rp 4.724.709,71 dan Rp 6.624.258,72 dari angka yang harus disetujui manusia.

Kontrak yang dikunci di sini:

1. setiap komponen biaya diskalakan dengan rasio yang sama, lalu sisa
   pembulatan diserap komponen terbesar sehingga
   ``sum(komponen) == safe_delivered_cost`` persis (bukan "hampir");
2. turunan internal (`logistics`, `transport_linehaul`, `transport_supplier_leg`)
   ikut diskalakan supaya tidak bertentangan dengan `transport`;
3. breakdown NARATIF (tanpa komponen biaya) tidak disentuh — bukan rincian
   biaya, jadi tidak ada yang bisa direkonsiliasi;
4. masukan tak terduga (bukan dict, nilai bukan angka) dikembalikan apa adanya,
   bukan ditebak.
"""

from __future__ import annotations

from decimal import Decimal

from app.seed.demo_template import KOMPONEN_BIAYA, skalakan_breakdown

#: Breakdown nyata dari DB demo (keputusan `e7150da4…`, telur 600 kg).
BREAKDOWN: dict[str, str] = {
    "basis": "dihitung: kutipan pemasok Rp27200.00/kg, linehaul 0 km, pemasok 1.88 km",
    "handling": "150000.00",
    "purchase": "16320000.00",
    "logistics": "338.40",
    "transport": "338.40",
    "expected_loss": "1011840.00",
    "freshness_risk": "0.00",
    "safety_penalty": "0.00",
    "supplier_leg_km": "1.88",
    "transport_linehaul": "0.00",
    "supplier_leg_reference": "supplier_coordinates",
    "transport_supplier_leg": "338.40",
}
SDC = Decimal("17482178.40")


def _jumlah(breakdown: dict) -> Decimal:
    return sum(
        (Decimal(str(breakdown[k])) for k in KOMPONEN_BIAYA if k in breakdown),
        Decimal("0"),
    )


def test_jumlah_komponen_sama_dengan_sdc_setelah_diskalakan():
    """Invarian utama D-01: Σ komponen == SDC (toleransi ≤ Rp0,01)."""
    target = (SDC * Decimal("0.7")).quantize(Decimal("0.01"))
    hasil = skalakan_breakdown(BREAKDOWN, Decimal("0.7"), target)

    assert hasil is not None
    selisih = abs(_jumlah(hasil) - target)
    assert selisih <= Decimal("0.01"), f"selisih {selisih}"


def test_setiap_komponen_turun_tujuh_puluh_persen():
    target = (SDC * Decimal("0.7")).quantize(Decimal("0.01"))
    hasil = skalakan_breakdown(BREAKDOWN, Decimal("0.7"), target)

    assert hasil["purchase"] == "11424000.00"
    assert hasil["handling"] == "105000.00"
    assert hasil["expected_loss"] == str(
        (Decimal("1011840.00") * Decimal("0.7")).quantize(Decimal("0.01"))
    )


def test_sisa_pembulatan_diserap_komponen_terbesar():
    """Tiga komponen yang pembulatannya "menguntungkan" tidak boleh lolos.

    0,7 × 0,05 = 0,035 → 0,04 (naik 0,005 per komponen). Tanpa penyerapan
    sisa, Σ komponen akan 0,01–0,02 lebih besar dari SDC.
    """
    breakdown = {"purchase": "0.05", "transport": "0.05", "handling": "0.05"}
    target = Decimal("0.09")

    hasil = skalakan_breakdown(breakdown, Decimal("0.7"), target)

    assert _jumlah(hasil) == target


def test_turunan_internal_ikut_diskalakan_dan_tetap_konsisten():
    target = (SDC * Decimal("0.7")).quantize(Decimal("0.01"))
    hasil = skalakan_breakdown(BREAKDOWN, Decimal("0.7"), target)

    # transport = linehaul + supplier_leg, dan logistics = transport.
    assert Decimal(hasil["transport"]) == Decimal("236.88")
    assert Decimal(hasil["logistics"]) == Decimal(hasil["transport"])
    assert Decimal(hasil["transport_linehaul"]) + Decimal(
        hasil["transport_supplier_leg"]
    ) == Decimal(hasil["transport"])


def test_kunci_bukan_biaya_tidak_disentuh():
    """`supplier_leg_km` adalah jarak, bukan uang: tidak boleh ×0,7."""
    target = (SDC * Decimal("0.7")).quantize(Decimal("0.01"))
    hasil = skalakan_breakdown(BREAKDOWN, Decimal("0.7"), target)

    assert hasil["supplier_leg_km"] == "1.88"
    assert hasil["basis"] == BREAKDOWN["basis"]
    assert hasil["supplier_leg_reference"] == "supplier_coordinates"


def test_breakdown_naratif_tidak_disentuh():
    naratif = {"catatan": "sudah disetujui, eksekusi belum dijalankan"}
    assert skalakan_breakdown(naratif, Decimal("0.7"), Decimal("1000")) == naratif

    kuotasi = {"quoted_price_per_kg": "13680", "deviation_pct": "14.0"}
    assert skalakan_breakdown(kuotasi, Decimal("0.7"), Decimal("1000")) == kuotasi


def test_masukan_tak_terduga_dikembalikan_apa_adanya():
    assert skalakan_breakdown(None, Decimal("0.7"), Decimal("1")) is None
    assert skalakan_breakdown({}, Decimal("0.7"), Decimal("1")) == {}

    rusak = {"purchase": "bukan-angka", "transport": "1.00"}
    assert skalakan_breakdown(rusak, Decimal("0.7"), Decimal("1")) == rusak
