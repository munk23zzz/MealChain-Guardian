"""Task 9 Sprint 2: service rekomendasi deterministik (test).

Kontrak: fetch_facts() tanpa argumen → 6-tuple facts;
build_recommendations(fetch_facts, as_of=..., logistics_by_pair=...).
Emisi: transport 300 Rp/km/ton; handling flat 150.000.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from app.services import recommendation_service as rs

UTC = timezone.utc
AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

SUPPLY = {
    ("Cianjur", "telur"): Decimal("1400"),
    ("Jakarta", "telur"): Decimal("300"),
}
DEMAND = {
    ("Cianjur", "telur"): Decimal("500"),
    ("Jakarta", "telur"): Decimal("1000"),
}
REFS = {("Cianjur", "telur"): Decimal("26500"),
        ("Jakarta", "telur"): Decimal("30500")}
QUOTES = {("Cianjur", "telur"): (
    Decimal("26200"), "11111111-1111-1111-1111-111111111111")}
RELIABILITY = {"11111111-1111-1111-1111-111111111111": Decimal("0.80")}
BATCHES = [{
    "batch_id": "b-1",
    "location": "Cianjur",
    "commodity": "telur",
    "quantity_kg": Decimal("600"),
    "freshness_score": Decimal("0.90"),
    "freshness_status": "pass",
    "usable_until": datetime(2099, 1, 1, tzinfo=timezone.utc),
    "safety_status": "pass",
}]
LOGI = {("Cianjur", "Jakarta"): {
    "distance_km": 120, "estimated_time_min": 150.0, "feasible": True}}


def _facts():
    return SUPPLY, DEMAND, REFS, QUOTES, BATCHES, RELIABILITY


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_cianjur_to_jakarta_telur_ranked():
    out = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    hits = [r for r in out["recommendations"]
            if r["candidate"]["source_location"] == "Cianjur"
            and r["candidate"]["destination_location"] == "Jakarta"]
    assert hits, "kandidat Cianjur→Jakarta wajib ada"
    top = hits[0]
    assert Decimal(top["candidate"]["quantity_kg"]) == Decimal("600")
    assert top["rank"] == 1


def test_sdc_arithmetic_locked():
    out = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    top = out["recommendations"][0]
    sdc = Decimal(top["safe_delivered_cost"])
    purchase = Decimal("600") * Decimal("26200")
    transport = Decimal("300") * Decimal("120") * Decimal("0.6")
    expected = purchase + transport + Decimal("150000") \
        + Decimal("0.2") * Decimal("0.10") * purchase
    assert sdc == expected


def test_deterministic_repeat():
    a = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    b = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_price_anomaly_emitted_reusing_engine():
    out = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    top = out["recommendations"][0]
    # Cianjur quote 26200 vs pihps 26500 → -1.13% → normal (reuse engine
    # price_deviation Sprint 1, tanpa formula baru).
    assert top["price_anomaly"]["status"] == "normal"
    assert Decimal(top["price_anomaly"]["deviation_pct"]) == Decimal("-1.13")


def test_no_quote_anomaly_marked():
    facts = (
        SUPPLY,
        DEMAND,
        REFS,
        {("Cianjur", "telur"): (None, None)},
        BATCHES,
        RELIABILITY,
    )
    out = _run(rs.build_recommendations(
        lambda: facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    top = out["recommendations"][0]
    assert top["price_anomaly"]["status"] == "no_supplier_quote"
    assert top["price_anomaly"]["deviation_pct"] is None


def test_evidence_emitted():
    out = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    top = out["recommendations"][0]
    assert top["evidence"]["batch_ids"] == ["b-1"]
    assert top["evidence"]["price_sources"] == [
        "pihps_reference",
        "supplier_quote",
    ]


def test_safety_fail_never_ranked():
    batches = [dict(BATCHES[0], safety_status="fail")]
    facts = (SUPPLY, DEMAND, REFS, QUOTES, batches, RELIABILITY)
    out = _run(rs.build_recommendations(
        lambda: facts, as_of=AS_OF, logistics_by_pair=LOGI
    ))
    assert out["recommendations"] == []


def test_infeasible_logistics_excluded():
    logi = {("Cianjur", "Jakarta"): {"distance_km": 120,
                                     "estimated_time_min": 999.0,
                                     "feasible": False}}
    out = _run(rs.build_recommendations(
        _facts, as_of=AS_OF, logistics_by_pair=logi
    ))
    assert out["recommendations"] == []
