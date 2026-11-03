"""Konsistensi bukti — unit test murni (TDD, 16 Okt 2026).

Latar gap terukur: `decision_evidence.is_consistent` selalu NULL karena kedua
penulis bukti (`event2_service.py`, `event3_service.py`) dan dua penulis lain
(`supplier_eligibility.py`, `supplier_exclusion_service.py`) menulisnya apa
adanya sebagai `None`. Akibatnya metrik **Evidence Completeness** menuntut
"≥2 tipe bukti `is_consistent IS TRUE`" yang tidak mungkin terpenuhi — kartu
KPI itu 0,00% permanen sambil berlabel "tersedia".

Definisi yang dikunci di sini (dan wajib dipakai pemanggilnya):
- `True`  = payload bukti COCOK dengan fakta DB yang ia kutip, setelah
  diturunkan ulang (harga & klasifikasi dihitung ulang dari baris
  `price_signals`; status suhu dihitung ulang dari log mentah batch).
- `False` = payload TIDAK cocok dengan sumbernya. Itu temuan integritas
  (bukti diubah/dipalsukan), bukan kegagalan penulisan.
- `None`  = tidak bisa dinilai karena fakta yang dibutuhkan tidak ada.
  NULL tidak boleh diisi `True` supaya metrik terlihat penuh.

Modul ini murni: tanpa DB, tanpa jaringan, tanpa LLM.
"""

from decimal import Decimal

from app.core.evidence_consistency import (
    administrative_consistency,
    binding_consistency,
    market_price_consistency,
    temperature_consistency,
)

# --------------------------------------------------------------------------
# human_inspection — binding alokasi batch/supplier (supplier_eligibility.py)
# --------------------------------------------------------------------------

BATCH_A = "11111111-1111-1111-1111-111111111111"
BATCH_B = "22222222-2222-2222-2222-222222222222"
SUP = "33333333-3333-3333-3333-333333333333"
LOC = "44444444-4444-4444-4444-444444444444"
COM = "55555555-5555-5555-5555-555555555555"


def _binding_payload() -> dict:
    return {
        "allocation_binding": True,
        "supplier_id": SUP,
        "batch_ids": sorted([BATCH_A, BATCH_B]),
    }


def _binding_facts(**over) -> dict:
    facts = {
        "batch_ids": [BATCH_A, BATCH_B],
        "batch_suppliers": [SUP, SUP],
        "batch_locations": [LOC, LOC],
        "batch_commodities": [COM, COM],
        "supplier_id": SUP,
        "source_location_id": LOC,
        "commodity_id": COM,
    }
    facts.update(over)
    return facts


def test_binding_cocok_dengan_baris_batch():
    assert binding_consistency(_binding_payload(), **_binding_facts()) is True


def test_binding_batch_milik_supplier_lain_tidak_konsisten():
    """Payload mengklaim supplier SUP, DB bilang batch itu milik supplier lain."""
    other = "66666666-6666-6666-6666-666666666666"
    assert (
        binding_consistency(_binding_payload(), **_binding_facts(batch_suppliers=[SUP, other]))
        is False
    )


def test_binding_daftar_batch_tidak_sama_tidak_konsisten():
    assert (
        binding_consistency(_binding_payload(), **_binding_facts(batch_ids=[BATCH_A])) is False
    )


def test_binding_lokasi_komoditas_beda_tidak_konsisten():
    assert (
        binding_consistency(_binding_payload(), **_binding_facts(commodity_id=LOC)) is False
    )


def test_binding_tanpa_fakta_lengkap_tidak_dinilai():
    """Fakta kurang (mis. keputusan lama tanpa lokasi sumber) → NULL, bukan True."""
    assert (
        binding_consistency(
            _binding_payload(), **_binding_facts(source_location_id=None)
        )
        is None
    )
    assert binding_consistency(_binding_payload(), **_binding_facts(batch_ids=[])) is None


def test_binding_bukan_evidence_binding_tidak_dinilai():
    payload = {"allocation_binding": False, "supplier_id": SUP, "batch_ids": []}
    assert binding_consistency(payload, **_binding_facts()) is None


# --------------------------------------------------------------------------
# human_inspection — aksi administratif (supplier_exclusion_service.py)
# --------------------------------------------------------------------------


def test_administratif_cocok():
    payload = {
        "supplier_id": SUP,
        "scope_location_id": LOC,
        "reason": "sertifikat haccp dicabut",
        "administrative_action": "supplier_exclusion",
    }
    assert (
        administrative_consistency(
            payload, supplier_id=SUP, scope_location_id=LOC, supplier_exists=True
        )
        is True
    )


def test_administratif_pemasok_tidak_ada_tidak_konsisten():
    payload = {
        "supplier_id": SUP,
        "scope_location_id": LOC,
        "reason": "alasan",
        "administrative_action": "supplier_exclusion",
    }
    assert (
        administrative_consistency(
            payload, supplier_id=SUP, scope_location_id=LOC, supplier_exists=False
        )
        is False
    )


def test_administratif_alasan_kosong_tidak_konsisten():
    payload = {
        "supplier_id": SUP,
        "scope_location_id": LOC,
        "reason": "   ",
        "administrative_action": "supplier_restoration",
    }
    assert (
        administrative_consistency(
            payload, supplier_id=SUP, scope_location_id=LOC, supplier_exists=True
        )
        is False
    )


def test_administratif_scope_beda_tidak_konsisten():
    payload = {
        "supplier_id": SUP,
        "scope_location_id": LOC,
        "reason": "alasan",
        "administrative_action": "supplier_exclusion",
    }
    assert (
        administrative_consistency(
            payload, supplier_id=SUP, scope_location_id=COM, supplier_exists=True
        )
        is False
    )


# --------------------------------------------------------------------------
# market_price (event2_service.py)
# --------------------------------------------------------------------------


def _price_payload(**over) -> dict:
    payload = {
        "quoted_price_per_kg": "40250.00",
        "reference_price_per_kg": "35000.00",
        "deviation_pct": "15.00",
        "classification": "deviation",
    }
    payload.update(over)
    return payload


def test_market_price_cocok_dengan_baris_harga():
    assert (
        market_price_consistency(
            _price_payload(),
            quote_price=Decimal("40250.00"),
            reference_price=Decimal("35000.00"),
            deviation_pct=Decimal("15"),
            classification="deviation",
        )
        is True
    )


def test_market_price_kutipan_diubah_tidak_konsisten():
    """Payload ditulis 40.250 padahal baris DB 39.000 → temuan, bukan True."""
    assert (
        market_price_consistency(
            _price_payload(),
            quote_price=Decimal("39000"),
            reference_price=Decimal("35000.00"),
            deviation_pct=Decimal("15"),
            classification="deviation",
        )
        is False
    )


def test_market_price_klasifikasi_beda_tidak_konsisten():
    assert (
        market_price_consistency(
            _price_payload(classification="anjlok"),
            quote_price=Decimal("40250.00"),
            reference_price=Decimal("35000.00"),
            deviation_pct=Decimal("15"),
            classification="deviation",
        )
        is False
    )


def test_market_price_tanpa_harga_acuan_tidak_dinilai():
    assert (
        market_price_consistency(
            _price_payload(),
            quote_price=Decimal("40250.00"),
            reference_price=None,
            deviation_pct=Decimal("15"),
            classification="deviation",
        )
        is None
    )


# --------------------------------------------------------------------------
# temperature (event3_service.py)
# --------------------------------------------------------------------------


def test_temperature_cocok_dengan_hasil_hitung_ulang():
    payload = {"safety_status": "fail", "excursion_minutes": 60}
    assert (
        temperature_consistency(
            payload, safety_status="fail", excursion_minutes=Decimal("60.0")
        )
        is True
    )


def test_temperature_status_beda_tidak_konsisten():
    """Bukti bilang fail, hitung ulang dari log mentah bilang pass."""
    payload = {"safety_status": "fail", "excursion_minutes": 60}
    assert (
        temperature_consistency(
            payload, safety_status="pass", excursion_minutes=Decimal("60.0")
        )
        is False
    )


def test_temperature_menit_penyimpangan_beda_tidak_konsisten():
    payload = {"safety_status": "fail", "excursion_minutes": 90}
    assert (
        temperature_consistency(
            payload, safety_status="fail", excursion_minutes=Decimal("60.0")
        )
        is False
    )


def test_temperature_tanpa_hitung_ulang_tidak_dinilai():
    payload = {"safety_status": "fail", "excursion_minutes": 60}
    assert temperature_consistency(payload, safety_status=None, excursion_minutes=None) is None
