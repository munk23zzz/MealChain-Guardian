"""Task 3 Sprint 2: generator kandidat cross-regional deterministik.

Kontrak (plan Task 3):
- quantity = min(source_surplus, destination_shortage,
  available_eligible_quantity)
- Exclude: source shortage (surplus 0), destination surplus/balanced
  (shortage 0), commodity mismatch, safety fail, freshness fail,
  logistics infeasible.
- needs_verification TETAP masuk sebagai kandidat review-required,
  tidak pernah clean pass.
- Batas kapasitas & delivery window dijaga persis (inklusif).
- Records: Mapping[(location, commodity), Decimal] — agregasi latest
  record adalah urusan caller (ruling Task 2).
- Ruling interface: plan tidak menyebut sumber PriceInfo padahal model
  kandidat mewajibkannya — generator menerima mapping `prices` eksplisit
  dari caller (Task 9 yang baca DB), tanpa kalkulasi harga di generator.
"""

from decimal import Decimal

import pytest

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates

REF = Decimal("26500")


def _price(quote=Decimal("26200"), supplier_id="11111111-1111-1111-1111-111111111111"):
    return PriceInfo(
        reference_price=REF, supplier_quote=quote, supplier_id=supplier_id
    )


def _batch(**overrides):
    base = {
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.92"),
        "freshness_status": "pass",
        "safety_status": "pass",
    }
    base.update(overrides)
    return base


def _logistics(feasible=True, distance=120, time_min=150.0):
    return {
        "distance_km": distance,
        "estimated_time_min": time_min,
        "feasible": feasible,
    }


def _inputs(**kw):
    """Locked demo: Cianjur 1400/500, Jakarta 300/1000 (telur)."""
    source_records = kw.get(
        "source_records",
        {
            ("Cianjur", "telur"): Decimal("1400"),
            ("Jakarta", "telur"): Decimal("300"),
        },
    )
    destination_records = kw.get(
        "destination_records",
        {
            ("Cianjur", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("1000"),
        },
    )
    batches = kw.get("batches", [_batch()])
    logistics = kw.get(
        "logistics_by_pair", {("Cianjur", "Jakarta"): _logistics()}
    )
    prices = kw.get("prices", {("Cianjur", "Jakarta", "telur"): _price()})
    return source_records, destination_records, batches, logistics, prices


def test_cianjur_to_jakarta_telur_locked_scenario():
    s, d, b, lg, p = _inputs()
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1
    c = out[0]
    assert c.source_location == "Cianjur"
    assert c.destination_location == "Jakarta"
    assert c.commodity == "telur"
    # min(surplus 900, shortage 700, available 600)
    assert c.quantity_kg == Decimal("600")
    assert c.logistics_distance_km == Decimal("120")
    assert c.logistics_time_min == 150
    assert c.logistics_feasible is True
    assert c.price == _price()


def test_quantity_capped_by_batch_availability():
    s, d, b, lg, p = _inputs(batches=[_batch(quantity_kg=Decimal("450"))])
    out = generate_candidates(s, d, b, lg, prices=p)
    assert out[0].quantity_kg == Decimal("450")


def test_quantity_capped_by_surplus_not_shortage():
    s, d, b, lg, p = _inputs(
        source_records={("Cianjur", "telur"): Decimal("1000"),
                        ("Jakarta", "telur"): Decimal("300")},
    )
    # surplus Cianjur = 1000-500 = 500 < shortage 700; batch 600
    out = generate_candidates(s, d, b, lg, prices=p)
    assert out[0].quantity_kg == Decimal("500")


def test_batch_kuantitas_nol_tidak_meledakkan_pipeline():
    """Batch quantity_kg=0 tidak boleh menjadi 0/0 (decimal.InvalidOperation).

    Regresi audit 2026-10-11: _aggregate_batches membagi weighted_freshness /
    total_qty, jadi satu batch berkuantitas nol membuat generate_candidates
    melempar InvalidOperation (ArithmeticError, bukan ValueError) dan mematikan
    pipeline rekomendasi/Event 1/Event 3. Batch berkuantitas nol memang tidak
    bisa dikirim → hasilnya tanpa kandidat.
    """
    s, d, b, lg, p = _inputs(batches=[_batch(quantity_kg=Decimal("0"))])
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_batch_kuantitas_nol_diabaikan_yang_positif_tetap_dihitung():
    """Batch nol dilewati; agregat dihitung dari batch yang benar-benar dikirim."""
    s, d, b, lg, p = _inputs(
        batches=[
            _batch(quantity_kg=Decimal("0")),
            _batch(quantity_kg=Decimal("300")),
        ]
    )
    out = generate_candidates(s, d, b, lg, prices=p)
    assert len(out) == 1
    assert out[0].quantity_kg == Decimal("300")
    assert out[0].freshness_score == Decimal("0.92")


def test_source_shortage_excluded():
    s, d, b, lg, p = _inputs(
        source_records={("Cianjur", "telur"): Decimal("400"),
                        ("Jakarta", "telur"): Decimal("300")},
    )
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_destination_surplus_excluded():
    s, d, b, lg, p = _inputs(
        destination_records={("Cianjur", "telur"): Decimal("500"),
                             ("Jakarta", "telur"): Decimal("200")},
    )
    # Jakarta supply 300 > demand 200 → tidak ada shortage
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_commodity_filter_excludes_mismatch():
    s, d, b, lg, p = _inputs(
        batches=[
            _batch(commodity="wortel", quantity_kg=Decimal("900")),
            _batch(commodity="telur"),
        ]
    )
    out = generate_candidates(s, d, b, lg, prices=p, commodity="telur")
    assert len(out) == 1
    assert out[0].commodity == "telur"


def test_safety_fail_batch_excluded():
    s, d, b, lg, p = _inputs(
        batches=[_batch(safety_status="fail")]
    )
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_freshness_fail_batch_excluded():
    s, d, b, lg, p = _inputs(
        batches=[_batch(freshness_status="fail")]
    )
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_needs_verification_allowed_and_marked():
    s, d, b, lg, p = _inputs(
        batches=[_batch(freshness_status="needs_verification")]
    )
    out = generate_candidates(s, d, b, lg, prices=p)
    assert len(out) == 1
    assert out[0].freshness_status == "needs_verification"
    assert out[0].safety_status == "pass"


def test_mixed_batches_weighted_freshness_and_conservative_status():
    s, d, b, lg, p = _inputs(
        batches=[
            _batch(quantity_kg=Decimal("300"), freshness_score=Decimal("0.95"),
                   freshness_status="pass"),
            _batch(quantity_kg=Decimal("300"), freshness_score=Decimal("0.70"),
                   freshness_status="needs_verification"),
        ]
    )
    out = generate_candidates(s, d, b, lg, prices=p)
    assert len(out) == 1
    c = out[0]
    assert c.quantity_kg == Decimal("600")
    assert c.freshness_status == "needs_verification"
    # weighted: (300*0.95 + 300*0.70) / 600 = 0.825
    assert c.freshness_score == Decimal("0.825")


def test_infeasible_logistics_excluded():
    s, d, b, lg, p = _inputs(
        logistics_by_pair={("Cianjur", "Jakarta"): _logistics(feasible=False)}
    )
    assert generate_candidates(s, d, b, lg, prices=p) == []


def test_exact_capacity_boundary_feasible():
    """Batas persis: waktu estimasi == window → feasible, kandidat ada."""
    s, d, b, lg, p = _inputs(
        logistics_by_pair={
            ("Cianjur", "Jakarta"): _logistics(time_min=150.0)
        }
    )
    out = generate_candidates(s, d, b, lg, prices=p)
    assert len(out) == 1
    assert out[0].logistics_feasible is True


def test_missing_logistics_pair_raises():
    s, d, b, lg, p = _inputs(logistics_by_pair={})
    with pytest.raises(ValueError, match="logistik"):
        generate_candidates(s, d, b, lg, prices=p)


def test_missing_price_raises():
    s, d, b, lg, p = _inputs(prices={})
    with pytest.raises(ValueError, match="harga"):
        generate_candidates(s, d, b, lg, prices=p)


def test_output_deterministic_ordering():
    s, d, b, lg, p = _inputs(
        destination_records={
            ("Cianjur", "telur"): Decimal("500"),
            ("Jakarta", "telur"): Decimal("1000"),
            ("Bogor", "telur"): Decimal("700"),
        },
        logistics_by_pair={
            ("Cianjur", "Jakarta"): _logistics(),
            ("Cianjur", "Bogor"): _logistics(distance=70, time_min=100.0),
        },
        prices={
            ("Cianjur", "Jakarta", "telur"): _price(),
            ("Cianjur", "Bogor", "telur"): _price(),
        },
    )
    out1 = generate_candidates(s, d, b, lg, prices=p)
    out2 = generate_candidates(s, d, b, lg, prices=p)
    keys1 = [(c.source_location, c.destination_location, c.commodity) for c in out1]
    keys2 = [(c.source_location, c.destination_location, c.commodity) for c in out2]
    assert keys1 == keys2 == sorted(keys1)
    assert [c.to_dict() for c in out1] == [c.to_dict() for c in out2]
