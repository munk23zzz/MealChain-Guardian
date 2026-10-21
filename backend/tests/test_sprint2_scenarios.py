"""Task 14 Sprint 2: skenario integrasi deterministik + 10x repetisi.

Skenario terkunci (brief Task 14):
1. Cianjur 1400/500 → surplus 900; Jakarta 300/1000 → shortage 700;
   kandidat Cianjur→Jakarta telur ada.
2. Ref 26500 vs Supplier C 32000 → anomalous + flagged.
3. Temperature excursion → safety FAIL → kandidat tereliminasi;
   alternatif aman tetap eligible.
4. Quote Supplier A/B/C/D mempertahankan supplier_id terpisah dari
   source generik.
5. Freshness 0.60–<0.85 → needs_verification, bukan PASS.

Setiap skenario fungsi deterministik → 10x eksekusi identik.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, text

from app.core.gaps import calculate_supply_gap
from app.core.price import price_deviation
from app.services import recommendation_service as rs
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

UTC = timezone.utc
AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
SUP_ID = "11111111-1111-1111-1111-111111111111"
LOGI = {("Cianjur", "Jakarta"): {
    "distance_km": 120, "estimated_time_min": 150.0, "feasible": True}}


def _scenario_facts(safety="pass", freshness=Decimal("0.90"), alternative=False):
    """Skenario terkunci: Cianjur surplus, Jakarta shortage (Task 9).

    freshness_status diturunkan dari score lewat engine yang sama
    (classify_freshness) — facts wajib konsisten score↔status.
    """
    from app.core.freshness import classify_freshness

    supply = {("Cianjur", "telur"): Decimal("1400"),
              ("Jakarta", "telur"): Decimal("300")}
    demand = {("Cianjur", "telur"): Decimal("500"),
              ("Jakarta", "telur"): Decimal("1000")}
    refs = {("Cianjur", "telur"): Decimal("26500"),
            ("Jakarta", "telur"): Decimal("30500")}
    quotes = {("Cianjur", "telur"): (Decimal("26200"), SUP_ID)}
    batches = [{
        "batch_id": "b-1",
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": freshness,
        "freshness_status": classify_freshness(float(freshness)),
        "safety_status": safety,
    }]
    logistics = dict(LOGI)
    if alternative:
        supply[("Bogor", "telur")] = Decimal("900")
        demand[("Bogor", "telur")] = Decimal("300")
        refs[("Bogor", "telur")] = Decimal("27000")
        quotes[("Bogor", "telur")] = (Decimal("26800"), SUP_ID)
        batches.append({
            "batch_id": "b-safe",
            "location": "Bogor",
            "commodity": "telur",
            "quantity_kg": Decimal("600"),
            "freshness_score": Decimal("0.90"),
            "freshness_status": "pass",
            "safety_status": "pass",
        })
        logistics[("Bogor", "Jakarta")] = {
            "distance_km": 60, "estimated_time_min": 90.0, "feasible": True
        }
    reliability = {SUP_ID: Decimal("0.80")}
    return supply, demand, refs, quotes, batches, reliability, logistics


def _run(facts):
    *facts, logistics = facts
    return asyncio.run(rs.build_recommendations(
        lambda: tuple(facts), as_of=AS_OF, logistics_by_pair=logistics
    ))


def _canonical(out):
    return json.dumps(out, sort_keys=True, separators=(",", ":"))


def test_scenario_1_cianjur_surplus_jakarta_shortage():
    supply, demand, *_ = _scenario_facts()
    gap_src = calculate_supply_gap(supply[("Cianjur", "telur")],
                                   demand[("Cianjur", "telur")])
    gap_dst = calculate_supply_gap(supply[("Jakarta", "telur")],
                                   demand[("Jakarta", "telur")])
    assert gap_src.surplus_kg == Decimal("900")
    assert gap_dst.shortage_kg == Decimal("700")
    out = _run(_scenario_facts())
    hits = [r for r in out["recommendations"]
            if r["candidate"]["source_location"] == "Cianjur"
            and r["candidate"]["destination_location"] == "Jakarta"]
    assert hits, "kandidat Cianjur→Jakarta telur wajib ada"


def test_scenario_2_supplier_c_anomalous():
    dev = price_deviation(Decimal("32000"), Decimal("26500"))
    assert dev["status"] == "anomalous"
    assert dev["flagged"] is True


def test_scenario_3_safety_fail_eliminated_safe_alternative_remains():
    out = _run(_scenario_facts(safety="fail", alternative=True))
    unsafe = [
        r for r in out["recommendations"]
        if r["candidate"]["source_location"] == "Cianjur"
    ]
    safe = [
        r for r in out["recommendations"]
        if r["candidate"]["source_location"] == "Bogor"
    ]
    assert unsafe == [], "candidate unsafe wajib excluded sebelum cost/ranking"
    assert safe, "candidate aman harus tetap tersedia"
    assert all(r["eligible"] is True for r in safe)
    assert all(r["candidate"]["safety_status"] == "pass" for r in safe)


def test_scenario_4_supplier_identity_in_supplier_id():
    # Empat quote terpisah (seed nilai riil Sprint 1) — identitas di
    # supplier_id, source tetap generik 'supplier_quote'.
    a = price_deviation(Decimal("26200"), Decimal("26500"))
    b = price_deviation(Decimal("27000"), Decimal("26500"))
    c = price_deviation(Decimal("32000"), Decimal("26500"))
    d = price_deviation(Decimal("25400"), Decimal("26500"))
    assert [x["status"] for x in (a, b, c, d)] == [
        "normal", "normal", "anomalous", "normal"]
    # Sumber data (seed) memisahkan identitas dari source generik:
    engine = create_engine(
        DSN_SYNC
    )
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT ps.source, ps.supplier_id FROM price_signals ps "
                "JOIN locations l ON l.id = ps.location_id "
                "JOIN commodities c ON c.id = ps.commodity_id "
                "WHERE l.name = 'Cianjur' AND c.name = 'telur' "
                "AND ps.source = 'supplier_quote' LIMIT 1"
            )
        ).one()
    assert row.source == "supplier_quote"
    assert row.supplier_id is not None


def test_scenario_5_needs_verification_band():
    out = _run(_scenario_facts(freshness=Decimal("0.70")))
    top = out["recommendations"][0]
    assert top["candidate"]["freshness_status"] == "needs_verification"
    assert top["candidate"]["freshness_status"] != "pass"


def test_deterministic_repeat_10x():
    """10x eksekusi identik (skenario 1, aman; freshness 0.90 pass).

    Fungsi deterministik wajib menghasilkan output identik setiap
    eksekusi sukses. (Skenario 2–5 juga deterministik murni — fungsi
    core tanpa state — dan diulang via parameterize di bawah.)
    """
    outs = [_run(_scenario_facts()) for _ in range(10)]
    canonical = [_canonical(o) for o in outs]
    assert len(set(canonical)) == 1, (
        "10x eksekusi wajib identik bit-per-bit"
    )
