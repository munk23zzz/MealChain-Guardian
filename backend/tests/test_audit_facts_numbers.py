"""Fakta SDC vs rincian untuk audit verifier — murni, tanpa DB.

Yang dikunci:

1. `ringkasan_rincian` memakai aturan modul `recommendation_numbers` (toleransi
   dan sumber total yang sama), bukan hitungan baru di agent.
2. Bentuk data kanonik (komponen biaya, tanpa kunci `total`) tetap dapat
   dinilai; komponennya sama dengan daftar yang dipakai seeder & gate invarian.
3. Keadaan yang tidak dapat dinilai menghasilkan `cocok=None` (belum terbukti),
   bukan `True`.
"""

from app.core.recommendation_numbers import (
    KODE_RINCIAN_TIDAK_COCOK,
    KOMPONEN_BIAYA,
    ringkasan_rincian,
)
from app.seed.demo_template import KOMPONEN_BIAYA as KOMPONEN_SEEDER

BREAKDOWN_KANONIK = {
    "purchase": "15269400.00",
    "transport": "24244.38",
    "handling": "150000.00",
    "expected_loss": "305388.00",
    "freshness_risk": "0.00",
    "safety_penalty": "0.00",
    "supplier_leg_km": "14.691",  # turunan: TIDAK ikut dijumlah
}
SDC_KANONIK = "15749032.38"


def test_komponen_kanonik_menjumlah_ke_sdc() -> None:
    hasil = ringkasan_rincian(SDC_KANONIK, BREAKDOWN_KANONIK)

    assert hasil["cocok"] is True
    assert hasil["sumber_total"] == "komponen"
    assert hasil["breakdown_total"] == 15749032.38
    assert hasil["selisih"] == 0.0


def test_komponen_selisih_ditandai_tidak_cocok() -> None:
    breakdown = dict(BREAKDOWN_KANONIK, purchase="15000000.00")

    hasil = ringkasan_rincian(SDC_KANONIK, breakdown)

    assert hasil["cocok"] is False
    assert hasil["alasan"] == KODE_RINCIAN_TIDAK_COCOK
    assert hasil["selisih"] > 0


def test_kunci_total_dipakai_bila_ada() -> None:
    hasil = ringkasan_rincian("1000.00", {"total": "1000.00", "purchase": "1.00"})

    assert hasil["cocok"] is True
    assert hasil["sumber_total"] == "total"
    assert hasil["breakdown_total"] == 1000.0


def test_tanpa_rincian_tidak_dapat_dinilai() -> None:
    hasil = ringkasan_rincian("1000.00", None)

    assert hasil["cocok"] is None
    assert hasil["alasan"] == "rincian_total_tidak_tersedia"


def test_komponen_bukan_angka_tidak_dapat_dinilai() -> None:
    hasil = ringkasan_rincian("1000.00", {"purchase": "bukan-angka"})

    assert hasil["cocok"] is None
    assert hasil["alasan"] == "bukan_angka"


def test_daftar_komponen_sama_dengan_seeder() -> None:
    """Cegah daftar komponen menyimpang dari yang dipakai menyemai data."""
    assert KOMPONEN_BIAYA == KOMPONEN_SEEDER
