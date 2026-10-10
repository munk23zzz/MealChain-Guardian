"""Service rekomendasi deterministik (Task 9 Sprint 2).

Pipeline terkunci (plan): fetch facts → gaps → candidates → hard
elimination → Candidate Score → SDC → rank. Tanpa LLM/agent/SAP.

Ruling Task 9 (ledger progress.md):
1. fetch_facts() callable tanpa argumen, mengembalikan 6-tuple
   (supply, demand, refs, quotes, batches, reliability); pemilihan
   latest-record ada di fetcher produksi (recorded_at DESC, id DESC).
2. transport 300 Rp/km/ton x distance_km x ton; handling flat 150.000.
3. supplier_reliability dari DB (Task 4); fallback 0.80 bila quote
   tanpa supplier dikenal.
4. purchase_cost = supplier_quote bila ada, else pihps reference.
"""

import inspect
from dataclasses import replace
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.core.candidate import PriceInfo
from app.core.candidate_generation import generate_candidates
from app.core.config import settings
from app.core.freshness import classify_freshness, compute_freshness_score
from app.core.logistics import estimate_logistics
from app.core.price import price_deviation
from app.core.ranking import ScoredCandidate, rank_candidates
from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)
from app.core.scoring import CandidateScoreFactors, calculate_candidate_score
from app.models import (
    Batch,
    Commodity,
    DemandRecord,
    Location,
    PriceSignal,
    Supplier,
    SupplierExclusion,
    SupplyRecord,
)

__all__ = ["build_recommendations", "fetch_operational_facts"]

TRANSPORT_RATE = Decimal("300")  # Rp per km per ton
HANDLING_FLAT = Decimal("150000")
DEFAULT_RELIABILITY = Decimal("0.80")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def _latest_rows(db, model):
    rows = (
        (await db.execute(select(model).order_by(model.recorded_at.desc(), model.id.desc())))
        .scalars()
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault((row.location_id, row.commodity_id), row)
    return latest


def _shelf_life_map():
    return {
        "telur": settings.shelf_life_days_telur,
        "ayam": settings.shelf_life_days_ayam,
        "wortel": settings.shelf_life_days_wortel,
    }


async def fetch_operational_facts(db, as_of):
    """Baca DB dan kembalikan 6-tuple facts untuk build_recommendations."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    locs = {loc.id: loc.name for loc in (await db.execute(select(Location))).scalars()}
    coms = {c.id: c.name for c in (await db.execute(select(Commodity))).scalars()}
    shelf = _shelf_life_map()

    supply = {}
    for (loc_id, com_id), row in (await _latest_rows(db, SupplyRecord)).items():
        supply[(locs[loc_id], coms[com_id])] = Decimal(str(row.quantity_kg))

    demand = {}
    for (loc_id, com_id), row in (await _latest_rows(db, DemandRecord)).items():
        demand[(locs[loc_id], coms[com_id])] = Decimal(str(row.quantity_kg))

    refs, quotes = {}, {}
    # Harga: latest per (location, commodity, SOURCE) — pihps dan quote
    # hidup berdampingan untuk pasangan yang sama (disiplin dua lapis).
    price_rows = (
        (
            await db.execute(
                select(PriceSignal).order_by(PriceSignal.recorded_at.desc(), PriceSignal.id.desc())
            )
        )
        .scalars()
        .all()
    )
    price_latest: dict = {}
    for row in price_rows:
        price_latest.setdefault((row.location_id, row.commodity_id, row.source), row)
    for (loc_id, com_id, _source), row in price_latest.items():
        key = (locs[loc_id], coms[com_id])
        if row.source == "pihps_reference":
            refs[key] = Decimal(str(row.price_per_kg))
        else:
            quotes[key] = (Decimal(str(row.price_per_kg)), row.supplier_id)

    active_exclusions = (
        (await db.execute(select(SupplierExclusion).where(SupplierExclusion.status == "active")))
        .scalars()
        .all()
    )
    batches = []
    # A later read can see harvests newer than the captured evaluation time.
    # Exclude them at the query boundary, including for explicit historical as_of;
    # never advance the clock or award freshness to a future harvest.
    batch_query = select(Batch).where(Batch.harvested_at <= as_of)
    for b in (await db.execute(batch_query)).scalars():
        name = coms[b.commodity_id]
        score = compute_freshness_score(
            b.harvested_at,
            as_of,
            shelf[name],
            b.temperature_log or [],
            settings.safe_temp_min_c,
            settings.safe_temp_max_c,
        )
        batches.append(
            {
                "batch_id": str(b.id),
                "supplier_id": str(b.supplier_id) if b.supplier_id else None,
                "excluded_destinations": [
                    locs[e.scope_location_id]
                    for e in active_exclusions
                    if e.supplier_id == b.supplier_id
                ],
                "location": locs[b.location_id],
                "commodity": name,
                "quantity_kg": Decimal(str(b.quantity_kg)),
                "freshness_score": _score(Decimal(str(score))),
                "freshness_status": classify_freshness(float(score)),
                "safety_status": b.safety_status,
            }
        )

    reliability = {
        str(s.id): Decimal(str(s.reliability_score))
        for s in (await db.execute(select(Supplier))).scalars()
    }
    return supply, demand, refs, quotes, batches, reliability


def _build_prices_map(refs, quotes):
    """PriceInfo per (source, dest, commodity); quote milik source."""
    prices = {}
    for (s_loc, com), ref in refs.items():
        quote, sid = quotes.get((s_loc, com), (None, None))
        for (d_loc, com2), _ref in refs.items():
            if com2 != com or d_loc == s_loc:
                continue
            prices[(s_loc, d_loc, com)] = PriceInfo(
                reference_price=ref,
                supplier_quote=quote,
                supplier_id=str(sid) if sid else None,
            )
    return prices


def _filter_commodity(
    supply: dict,
    demand: dict,
    refs: dict,
    quotes: dict,
    batches: list,
    commodity: str | None,
) -> tuple:
    """Ruling Owner 2026-10-08 (S4-05 p10): filter facts ke 1 komoditas.

    Dipakai /balance/analyze agar proposal mengikuti komoditas panel
    (bukan selalu rank-1 global). None = tanpa filter (perilaku lama —
    dipakai /balance/recommend dan orchestrator Event 1/3).
    """
    if not commodity:
        return supply, demand, refs, quotes, batches
    return (
        {k: v for k, v in supply.items() if k[1] == commodity},
        {k: v for k, v in demand.items() if k[1] == commodity},
        {k: v for k, v in refs.items() if k[1] == commodity},
        {k: v for k, v in quotes.items() if k[1] == commodity},
        [b for b in batches if b.get("commodity") == commodity],
    )


async def build_recommendations(
    fetch_facts, as_of=None, logistics_by_pair=None, commodity: str | None = None
):
    """Pipeline deterministik penuh; hasil terurut rank 1..N.

    fetch_facts boleh sync (kembalikan 6-tuple) atau async (kembalikan
    coroutine 6-tuple) — pipeline tetap identik.
    `commodity` (opsional, ruling S4-05): filter facts ke 1 komoditas;
    None = global (perilaku lama).
    """
    facts = fetch_facts()
    if inspect.isawaitable(facts):
        facts = await facts
    supply, demand, refs, quotes, batches, reliability = facts
    supply, demand, refs, quotes, batches = _filter_commodity(
        supply, demand, refs, quotes, batches, commodity
    )
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    prices_map = _build_prices_map(refs, quotes)
    if logistics_by_pair is None:
        logistics_by_pair = {}
        for s_loc, d_loc, _com in prices_map:
            logistics_by_pair.setdefault(
                (s_loc, d_loc),
                estimate_logistics(s_loc, d_loc, 1.0),
            )

    candidates = generate_candidates(
        source_records=supply,
        destination_records=demand,
        batches=batches,
        logistics_by_pair=logistics_by_pair,
        prices=prices_map,
    )

    scored = []
    breakdowns: dict = {}
    for cand in candidates:
        sid = cand.supplier_id or cand.price.supplier_id
        rel = reliability.get(sid, DEFAULT_RELIABILITY) if sid else DEFAULT_RELIABILITY
        if rel != cand.supplier_reliability:
            cand = replace(cand, supplier_reliability=rel)
        result = calculate_candidate_score(
            CandidateScoreFactors(
                demand_fit=cand.demand_fit,
                supply_availability=cand.supply_availability,
                freshness_score=cand.freshness_score,
                safety_status=cand.safety_status,
                supplier_reliability=rel,
                logistics_feasible=cand.logistics_feasible,
            )
        )
        unit = cand.price.supplier_quote or cand.price.reference_price
        sdc = calculate_safe_delivered_cost(
            SafeDeliveredCostInputs(
                purchase_cost=_money(cand.quantity_kg * unit),
                transport_cost=_money(
                    TRANSPORT_RATE * cand.logistics_distance_km * cand.quantity_kg / 1000
                ),
                handling_cost=HANDLING_FLAT,
                freshness_score=cand.freshness_score,
                safety_status=cand.safety_status,
            )
        )
        breakdown = {
            "purchase": str(sdc.purchase_cost),
            "transport": str(sdc.transport_cost),
            "handling": str(sdc.handling_cost),
            "expected_loss": str(sdc.expected_loss),
            "freshness_risk": str(sdc.freshness_risk_penalty),
            "safety_penalty": str(sdc.safety_risk_penalty),
        }
        scored.append(
            ScoredCandidate(
                candidate=cand,
                candidate_id=(
                    f"{cand.source_location}->{cand.destination_location}:"
                    f"{cand.commodity}" + (f":{cand.supplier_id}" if cand.supplier_id else "")
                ),
                score=_score(result.score),
                eligible=result.eligible,
                review_required=result.review_required,
                safe_delivered_cost=sdc.total,
            )
        )
        breakdowns[
            f"{cand.source_location}->{cand.destination_location}:"
            f"{cand.commodity}" + (f":{cand.supplier_id}" if cand.supplier_id else "")
        ] = breakdown

    ranked = rank_candidates(scored)
    recommendations = []
    for rc in ranked:
        cand = rc.candidate
        payload = rc.to_dict()
        payload["rank"] = rc.rank
        payload["cost_breakdown"] = breakdowns[rc.candidate_id]
        # Anomali harga: reuse engine price_deviation Sprint 1 (5%/15%).
        if cand.price.supplier_quote is not None:
            dev = price_deviation(cand.price.supplier_quote, cand.price.reference_price)
            payload["price_anomaly"] = {
                "status": dev["status"],
                "deviation_pct": str(
                    dev["deviation_pct"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ),
                "flagged": dev["flagged"],
            }
        else:
            payload["price_anomaly"] = {
                "status": "no_supplier_quote",
                "deviation_pct": None,
                "flagged": False,
            }
        # Evidence: batch sumber yang eligible + sumber harga terpakai.
        payload["evidence"] = {
            "batch_ids": list(cand.batch_ids)
            if cand.batch_ids
            else sorted(
                {
                    str(b["batch_id"])
                    for b in batches
                    if b.get("location") == cand.source_location
                    and b.get("commodity") == cand.commodity
                    and b.get("batch_id")
                }
            ),
            "price_sources": (
                ["pihps_reference", "supplier_quote"]
                if cand.price.supplier_quote is not None
                else ["pihps_reference"]
            ),
        }
        recommendations.append(payload)

    return {
        "generated_at": as_of.isoformat(),
        "facts": {
            "supply": {f"{k[0]}:{k[1]}": str(v) for k, v in supply.items()},
            "demand": {f"{k[0]}:{k[1]}": str(v) for k, v in demand.items()},
        },
        "recommendations": recommendations,
    }
