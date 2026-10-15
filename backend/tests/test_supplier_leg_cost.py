"""Fase 7d — jarak pemasok→SPPG masuk biaya SDC.

Keputusan pemilik 2026-10-15 (plan `2026-10-14_scope-pemasok-peta-rentang.md`
§7.4 keputusan #4 + §7.4b): jarak PEMASOK ikut dihitung dalam biaya SDC,
bukan hanya matriks SPPG↔SPPG `logistics.py`.

Aturan yang diuji di sini (murni, tanpa DB):
- kaki pertama angkut = pemasok → SPPG tempat batch berada, dari koordinat;
- koordinat tidak lengkap → TIDAK ditebak (0 km yang jujur + label);
- linehaul SPPG↔SPPG dan kelayakan delivery window TIDAK berubah;
- 6-tuple facts lama tetap sah (kompatibilitas kontrak Task 9).
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core import geo
from app.core.supplier_leg import (
    LEG_REFERENCE_COORDINATES,
    LEG_REFERENCE_MISSING,
    LEG_REFERENCE_NO_SUPPLIER,
    supplier_leg_km,
    supplier_leg_map,
)
from app.services import recommendation_service as rs

UTC = timezone.utc
AS_OF = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

SID = "11111111-1111-1111-1111-111111111111"

# Cianjur (-6.8420, 107.1426) — sama dengan titik hub di DB.
CIANJUR = (-6.8420, 107.1426)
BOGOR = (-6.5950, 106.8166)

SUPPLY = {
    ("Cianjur", "telur"): Decimal("1400"),
    ("Jakarta", "telur"): Decimal("300"),
}
DEMAND = {
    ("Cianjur", "telur"): Decimal("500"),
    ("Jakarta", "telur"): Decimal("1000"),
}
REFS = {
    ("Cianjur", "telur"): Decimal("26500"),
    ("Jakarta", "telur"): Decimal("30500"),
}
QUOTES = {("Cianjur", "telur"): (Decimal("26200"), SID)}
RELIABILITY = {SID: Decimal("0.80")}
BATCHES = [
    {
        "batch_id": "b-1",
        "supplier_id": SID,
        "location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": Decimal("600"),
        "freshness_score": Decimal("0.90"),
        "freshness_status": "pass",
        "safety_status": "pass",
    }
]
LOGI = {
    ("Cianjur", "Jakarta"): {
        "distance_km": 120,
        "estimated_time_min": 150.0,
        "feasible": True,
    }
}

# Kaki pertama kanonik untuk uji: pemasok 64 km dari SPPG sumber.
LEG_KM = Decimal("64.000")
LEGS = {(SID, "Cianjur"): LEG_KM}


def _facts(legs=LEGS, batches=BATCHES):
    """7-tuple: 6-tuple Task 9 + peta jarak pemasok (elemen ke-7)."""
    return (SUPPLY, DEMAND, REFS, QUOTES, batches, RELIABILITY, legs)


def _facts_legacy(batches=BATCHES):
    """6-tuple lama — tanpa peta jarak pemasok sama sekali."""
    return (SUPPLY, DEMAND, REFS, QUOTES, batches, RELIABILITY)


def _run(facts):
    return asyncio.run(
        rs.build_recommendations(lambda: facts, as_of=AS_OF, logistics_by_pair=LOGI)
    )


def _top(facts):
    return _run(facts)["recommendations"][0]


# --------------------------------------------------------------------------
# 1. Modul murni
# --------------------------------------------------------------------------


def test_leg_km_uses_shared_haversine():
    km = supplier_leg_km((-6.854, 107.1306), CIANJUR)
    expected = geo.haversine_km(-6.854, 107.1306, *CIANJUR)
    assert km is not None
    assert km == Decimal(str(round(expected, 3))).quantize(Decimal("0.001"))
    # simetris: arah tidak mengubah jarak
    assert supplier_leg_km(CIANJUR, (-6.854, 107.1306)) == km


@pytest.mark.parametrize(
    "supplier_coords,location_coords",
    [
        (None, CIANJUR),
        (CIANJUR, None),
        (None, None),
        ((-6.854, None), CIANJUR),
        (CIANJUR, (None, 107.1426)),
    ],
    ids=["tanpa-koordinat-pemasok", "tanpa-koordinat-lokasi", "dua-duanya",
         "separuh-lat", "separuh-lon"],
)
def test_leg_km_none_when_coordinates_incomplete(supplier_coords, location_coords):
    assert supplier_leg_km(supplier_coords, location_coords) is None


def test_leg_map_only_complete_pairs():
    legs = supplier_leg_map(
        {"s-1": (-6.854, 107.1306), "s-2": (None, None)},
        {"Cianjur": CIANJUR, "Bogor": None},
    )
    assert set(legs) == {("s-1", "Cianjur")}
    assert legs[("s-1", "Cianjur")] > 0


# --------------------------------------------------------------------------
# 2. Biaya SDC: transport = kaki pemasok + linehaul
# --------------------------------------------------------------------------


def test_transport_includes_supplier_leg():
    top = _top(_facts())
    bd = top["cost_breakdown"]
    leg = Decimal("300") * LEG_KM * Decimal("0.6")  # 11.520,00
    linehaul = Decimal("300") * Decimal("120") * Decimal("0.6")  # 21.600,00
    assert Decimal(bd["transport_supplier_leg"]) == leg
    assert Decimal(bd["transport_linehaul"]) == linehaul
    assert Decimal(bd["transport"]) == leg + linehaul
    # breakdown tetap menjumlah persis ke total SDC
    components = (
        "purchase", "transport", "handling", "expected_loss",
        "freshness_risk", "safety_penalty",
    )
    assert sum(Decimal(bd[k]) for k in components) == Decimal(
        top["safe_delivered_cost"]
    )


def test_supplier_leg_reported_with_source():
    payload = _top(_facts())["supplier_leg"]
    assert payload["reference"] == LEG_REFERENCE_COORDINATES
    assert Decimal(payload["km"]) == LEG_KM
    assert Decimal(payload["cost"]) == Decimal("11520.00")
    assert payload["source_location"] == "Cianjur"


def test_linehaul_and_feasibility_untouched():
    """Linehaul tetap jarak SPPG↔SPPG; kelayakan delivery window tidak berubah."""
    cand = _top(_facts())["candidate"]
    assert Decimal(cand["logistics_distance_km"]) == Decimal("120")
    assert cand["logistics_feasible"] is True


# --------------------------------------------------------------------------
# 3. Kejujuran: koordinat tidak lengkap tidak ditebak
# --------------------------------------------------------------------------


def test_legacy_six_tuple_keeps_locked_arithmetic():
    """Kontrak Task 9 (6-tuple) tetap sah: biaya angkut lama + label jujur."""
    top = _top(_facts_legacy())
    bd = top["cost_breakdown"]
    assert Decimal(bd["transport"]) == Decimal("300") * Decimal("120") * Decimal("0.6")
    assert Decimal(bd["transport_supplier_leg"]) == Decimal("0")
    # Identitas pemasok ADA (dari quote) tetapi tidak ada peta jarak → label
    # "koordinat tidak diketahui", bukan 0 km yang menyamar sebagai data.
    assert top["supplier_leg"]["reference"] == LEG_REFERENCE_MISSING
    assert top["supplier_leg"]["km"] is None
    assert Decimal(top["supplier_leg"]["cost"]) == Decimal("0")


def test_missing_supplier_coordinates_not_guessed():
    """Pemasok dikenal tetapi tanpa koordinat → 0 km + label, bukan tebakan."""
    top = _top(_facts(legs={}))
    assert top["supplier_leg"]["reference"] == LEG_REFERENCE_MISSING
    assert top["supplier_leg"]["km"] is None
    assert Decimal(top["cost_breakdown"]["transport_supplier_leg"]) == Decimal("0")


def test_candidate_without_supplier_marked():
    """Tanpa identitas pemasok sama sekali (tanpa quote) → `no_supplier`."""
    batches = [dict(BATCHES[0])]
    batches[0].pop("supplier_id")
    facts = (
        SUPPLY,
        DEMAND,
        REFS,
        {("Cianjur", "telur"): (None, None)},
        batches,
        RELIABILITY,
        {},
    )
    top = _top(facts)
    assert top["supplier_leg"]["supplier_id"] is None
    assert top["supplier_leg"]["reference"] == LEG_REFERENCE_NO_SUPPLIER
    assert top["supplier_leg"]["km"] is None


def test_identity_from_quote_still_resolves_leg():
    """Batch tanpa supplier_id tetap dapat kaki pertama bila quote membawa id."""
    batches = [dict(BATCHES[0])]
    batches[0].pop("supplier_id")
    top = _top(_facts(batches=batches))
    assert top["supplier_leg"]["supplier_id"] == SID
    assert top["supplier_leg"]["reference"] == LEG_REFERENCE_COORDINATES
    assert Decimal(top["supplier_leg"]["km"]) == LEG_KM


# --------------------------------------------------------------------------
# 4. Determinisme
# --------------------------------------------------------------------------


def test_deterministic_with_leg():
    a = json.dumps(_run(_facts()), sort_keys=True)
    b = json.dumps(_run(_facts()), sort_keys=True)
    assert a == b
