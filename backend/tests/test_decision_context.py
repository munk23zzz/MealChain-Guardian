"""Task 12: kontrak context Supervisor (assembler murni, allowlist).

Fixture memakai bentuk emisi service nyata (Task 9): status freshness/
safety/logistics hidup di dalam `candidate`, supplier_id di
`candidate.price`, price_anomaly + evidence di level rekomendasi.
"""

import json

import pytest

from app.core.decision_context import (
    build_supervisor_context,
    canonical_context_json,
)

OUT = {
    "generated_at": "2026-10-01T12:00:00+00:00",
    "facts": {
        "supply": {"Cianjur:telur": "1400", "Jakarta:telur": "300"},
        "demand": {"Cianjur:telur": "500", "Jakarta:telur": "1000"},
    },
    "recommendations": [
        {
            "rank": 1,
            "candidate_id": "Cianjur->Jakarta:telur",
            "score": "0.6312",
            "safe_delivered_cost": "16206000.00",
            "cost_breakdown": {"purchase": "15720000.00"},
            "price_anomaly": {"status": "normal", "deviation_pct": "-1.13", "flagged": False},
            "evidence": {
                "batch_ids": ["b-1"],
                "price_sources": ["pihps_reference", "supplier_quote"],
            },
            "candidate": {
                "source_location": "Cianjur",
                "destination_location": "Jakarta",
                "commodity": "telur",
                "quantity_kg": "600",
                "freshness_status": "pass",
                "safety_status": "pass",
                "logistics_feasible": True,
                "logistics_distance_km": "120",
                "logistics_time_min": 150.0,
                "price": {
                    "reference_price": "26500",
                    "supplier_quote": "26200",
                    "supplier_id": "11111111-1111-1111-1111-111111111111",
                },
            },
        }
    ],
    # kunci asing yang HARUS dibuang:
    "api_key": "AKIASECRET",
    "password": "hunter2",
}


def test_context_serializes_deterministically():
    a = canonical_context_json(OUT)
    b = canonical_context_json(OUT)
    assert a == b
    assert json.loads(a)["candidates"][0]["candidate_id"]


def test_context_required_keys():
    ctx = build_supervisor_context(OUT)
    assert ctx["generated_at"] == OUT["generated_at"]
    assert ctx["facts"]["supply"]["Cianjur:telur"] == "1400"
    c = ctx["candidates"][0]
    for key in (
        "candidate_id",
        "score",
        "safe_delivered_cost",
        "freshness_status",
        "safety_status",
        "price_anomaly",
        "logistics",
        "supplier_id",
        "evidence",
    ):
        assert key in c, key
    assert c["supplier_id"] == "11111111-1111-1111-1111-111111111111"
    assert c["freshness_status"] == "pass"
    assert c["safety_status"] == "pass"
    assert c["logistics"]["distance_km"] == "120"


def test_context_drops_unknown_keys():
    raw = canonical_context_json(OUT)
    assert "AKIASECRET" not in raw
    assert "hunter2" not in raw


def test_context_missing_required_key_rejected():
    broken = {k: v for k, v in OUT.items() if k != "facts"}
    with pytest.raises(ValueError):
        build_supervisor_context(broken)
    no_cands = {k: v for k, v in OUT.items() if k != "recommendations"}
    with pytest.raises(ValueError):
        build_supervisor_context(no_cands)


def test_context_candidate_missing_status_rejected():
    broken = json.loads(json.dumps(OUT))
    del broken["recommendations"][0]["candidate"]["freshness_status"]
    with pytest.raises(ValueError):
        build_supervisor_context(broken)


def test_context_integration_with_real_service_emission():
    """Builder menerima emisi service Task 9 apa adanya."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.services import recommendation_service as rs

    supply = {("Cianjur", "telur"): Decimal("1400"),
              ("Jakarta", "telur"): Decimal("300")}
    demand = {("Cianjur", "telur"): Decimal("500"),
              ("Jakarta", "telur"): Decimal("1000")}
    refs = {("Cianjur", "telur"): Decimal("26500"),
            ("Jakarta", "telur"): Decimal("30500")}
    quotes = {("Cianjur", "telur"): (
        Decimal("26200"), "11111111-1111-1111-1111-111111111111")}
    batches = [{
        "batch_id": "b-1",
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.90"),
        "freshness_status": "pass",
        "safety_status": "pass",
    }]
    reliability = {
        "11111111-1111-1111-1111-111111111111": Decimal("0.80")
    }
    logi = {("Cianjur", "Jakarta"): {
        "distance_km": 120, "estimated_time_min": 150.0, "feasible": True}}
    as_of = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    import asyncio

    out = asyncio.run(rs.build_recommendations(
        lambda: (supply, demand, refs, quotes, batches, reliability),
        as_of=as_of,
        logistics_by_pair=logi,
    ))
    ctx = build_supervisor_context(out)
    c = ctx["candidates"][0]
    assert c["candidate_id"].startswith("Cianjur->Jakarta")
    assert c["supplier_id"] == "11111111-1111-1111-1111-111111111111"
    assert c["freshness_status"] == "pass"
    assert c["safety_status"] == "pass"
    assert c["price_anomaly"]["status"] in {"normal", "elevated", "anomalous"}
    assert c["evidence"]["batch_ids"] == ["b-1"]
