from decimal import Decimal

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates


def test_supplier_identity_not_inferred_from_quote_or_location_and_local_exclusion():
    batches = [
        dict(
            batch_id="a",
            supplier_id="one",
            location="Bogor",
            commodity="telur",
            quantity_kg=100,
            freshness_score=1,
            freshness_status="pass",
            safety_status="pass",
            excluded_destinations=["Jakarta"],
        ),
        dict(
            batch_id="b",
            supplier_id="two",
            location="Bogor",
            commodity="telur",
            quantity_kg=100,
            freshness_score=1,
            freshness_status="pass",
            safety_status="pass",
            excluded_destinations=[],
        ),
    ]
    kwargs = dict(
        source_records={("Bogor", "telur"): 200},
        destination_records={("Jakarta", "telur"): 100, ("Bandung", "telur"): 100},
        batches=batches,
        logistics_by_pair={
            ("Bogor", d): dict(feasible=True, distance_km=50, estimated_time_min=60)
            for d in ["Jakarta", "Bandung"]
        },
        prices={
            ("Bogor", d, "telur"): PriceInfo(Decimal("100"), Decimal("110"), "one")
            for d in ["Jakarta", "Bandung"]
        },
    )
    results = generate_candidates(**kwargs)
    assert {(r.supplier_id, r.destination_location) for r in results} == {
        ("one", "Bandung"),
        ("two", "Jakarta"),
        ("two", "Bandung"),
    }
    assert all(r.batch_ids == (("a",) if r.supplier_id == "one" else ("b",)) for r in results)
    assert all(r.price.supplier_quote is None for r in results if r.supplier_id == "two")
    batches[1]["safety_status"] = "fail"
    assert {(r.supplier_id, r.destination_location) for r in generate_candidates(**kwargs)} == {
        ("one", "Bandung")
    }
    batches[0]["supplier_id"] = None
    assert generate_candidates(**kwargs) == []
