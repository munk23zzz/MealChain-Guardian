"""Biaya angkut PER TRIP (revisi 2026-10-29b).

Kontrak pemilik: "Biaya truk adalah per trip, bukan per ton. Satu truk box
sekali jalan ke Jakarta biaya ratusan ribu, terlepas isinya 150 kg atau 1 ton."

Model: biaya = jumlah_trip × (tarif_tetap + tarif_per_km × jarak), dengan
jumlah_trip = ceil(berat ÷ kapasitas truk), minimum 1 trip.

Rute berbilang kaki (pemasok → SPPG asal → SPPG tujuan) dikerjakan SATU truk
dalam satu perjalanan, jadi pemanggil mengirim jarak TOTAL: tarif tetap tidak
boleh ditagih dua kali untuk satu pengiriman.
"""

from decimal import Decimal

import pytest

from app.core.trip_cost import (
    BASIS_TARIF,
    KAPASITAS_TRUK_KG,
    TARIF_PER_KM,
    TARIF_TETAP,
    biaya_angkut_trip,
)


def test_muatan_di_bawah_kapasitas_satu_trip():
    """Cianjur–Jakarta 120 km, 600 kg: 250.000 + 4.000 × 120 = 730.000."""
    biaya, rincian = biaya_angkut_trip(
        distance_km=Decimal("120"), quantity_kg=Decimal("600")
    )
    assert biaya == Decimal("730000.00")
    assert rincian["trips"] == 1
    assert rincian["basis"] == BASIS_TARIF


def test_ongkos_tidak_lagi_sebanding_berat():
    """Inti kritik: 150 kg dan 1.000 kg ke tujuan yang sama = ongkos sama."""
    ringan, _ = biaya_angkut_trip(120, 150)
    penuh, _ = biaya_angkut_trip(120, 1000)
    assert ringan == penuh == Decimal("730000.00")


def test_muatan_lebih_dari_kapasitas_jadi_dua_trip():
    biaya, rincian = biaya_angkut_trip(120, 1500)
    assert rincian["trips"] == 2
    assert biaya == Decimal("1460000.00")


def test_tepat_kapasitas_tetap_satu_trip():
    _, rincian = biaya_angkut_trip(100, KAPASITAS_TRUK_KG)
    assert rincian["trips"] == 1


def test_jarak_nol_tetap_kena_tarif_tetap():
    """Bongkar-muat tetap berbiaya walau jarak 0 km — bukan gratis."""
    biaya, rincian = biaya_angkut_trip(0, 500)
    assert biaya == TARIF_TETAP
    assert rincian["distance_km"] == Decimal("0")


def test_rincian_membawa_dasar_perhitungan():
    _, rincian = biaya_angkut_trip(120, 600)
    assert rincian["capacity_kg"] == KAPASITAS_TRUK_KG
    assert rincian["fixed_idr"] == TARIF_TETAP
    assert rincian["rate_per_km"] == TARIF_PER_KM
    assert rincian["distance_km"] == Decimal("120")
    assert rincian["quantity_kg"] == Decimal("600")


def test_biaya_selalu_dua_desimal():
    biaya, _ = biaya_angkut_trip(Decimal("12.345"), Decimal("333"))
    assert -biaya.as_tuple().exponent == 2


def test_input_tidak_valid_ditolak():
    with pytest.raises(ValueError, match="distance_km"):
        biaya_angkut_trip(-1, 100)
    with pytest.raises(ValueError, match="quantity_kg"):
        biaya_angkut_trip(10, 0)
    with pytest.raises(ValueError, match="distance_km"):
        biaya_angkut_trip("bukan-angka", 100)


def test_deterministik():
    a = biaya_angkut_trip(120, 600)
    b = biaya_angkut_trip(120, 600)
    assert a == b
