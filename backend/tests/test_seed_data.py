"""Test seed transformer deterministik (Task 10, plan Sprint 1)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.seed.seed_data import build_seed_rows

SEED_JSON = Path("/data/seed/sprint1_seed.json")

EXPECTED_LOCATIONS = (
    "Jakarta",
    "Bogor",
    "Cianjur",
    "Bandung",
    "Semarang",
    "Yogyakarta",
    "Surabaya",
    "Makassar",
    "Palembang",
    "Medan",
)
EXPECTED_COMMODITIES = ("telur", "ayam", "wortel")

REF_TIME = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def _load_json() -> dict:
    return json.loads(SEED_JSON.read_text(encoding="utf-8"))


def test_seed_json_has_exactly_ten_locked_locations() -> None:
    names = [loc["name"] for loc in _load_json()["locations"]]
    assert names == list(EXPECTED_LOCATIONS)


def test_seed_json_has_exactly_three_commodities_with_shelf_life() -> None:
    data = _load_json()
    commodities = {c["name"]: c["shelf_life_days"] for c in data["commodities"]}
    assert set(commodities) == set(EXPECTED_COMMODITIES)
    assert commodities == {"telur": 28, "ayam": 5, "wortel": 21}


def test_build_seed_rows_supply_counts_and_locked_values() -> None:
    rows = build_seed_rows(REF_TIME)

    supply = rows["supply"]
    cianjur_telur = [
        r
        for r in supply
        if r["location"] == "Cianjur" and r["commodity"] == "telur"
    ]
    assert len(cianjur_telur) == 1
    assert float(cianjur_telur[0]["quantity_kg"]) == 1400.0

    jakarta_telur = [
        r for r in supply if r["location"] == "Jakarta" and r["commodity"] == "telur"
    ]
    assert len(jakarta_telur) == 1
    assert float(jakarta_telur[0]["quantity_kg"]) == 300.0

    bogor_telur = [
        r for r in supply if r["location"] == "Bogor" and r["commodity"] == "telur"
    ]
    assert len(bogor_telur) == 1
    assert float(bogor_telur[0]["quantity_kg"]) == 800.0

    telur_rows = [r for r in supply if r["commodity"] == "telur"]
    assert len(telur_rows) == 10


def test_build_seed_rows_demand_min_seven_observations_for_forecast_pair() -> None:
    rows = build_seed_rows(REF_TIME)
    demand = rows["demand"]
    jakarta_telur = [r for r in demand if r["location"] == "Jakarta" and r["commodity"] == "telur"]
    assert len(jakarta_telur) >= 7


def test_build_seed_rows_price_signals_suppliers() -> None:
    """Revisi kedua Roy: quote = source 'supplier_quote' + field 'supplier'."""
    rows = build_seed_rows(REF_TIME)
    quotes = {
        r["supplier"]: float(r["price_per_kg"])
        for r in rows["price_signals"]
        if r["source"] == "supplier_quote"
    }
    assert quotes["Supplier A Cianjur"] == 26200.0
    assert quotes["Supplier B Cianjur"] == 27000.0
    assert quotes["Supplier C Cianjur"] == 32000.0
    assert quotes["Supplier D Cianjur"] == 25400.0
    refs_cianjur = [
        r
        for r in rows["price_signals"]
        if r["location"] == "Cianjur" and r["source"] == "pihps_reference"
    ]
    assert any(float(r["price_per_kg"]) == 26500.0 for r in refs_cianjur)


def test_build_seed_rows_batches_cover_three_bands_plus_safety_fail() -> None:
    rows = build_seed_rows(REF_TIME)
    batches = rows["batches"]
    scores = [float(b["freshness_score"]) for b in batches]
    statuses = {b["safety_status"] for b in batches}

    assert any(s >= 0.85 for s in scores)
    assert any(0.60 <= s < 0.85 for s in scores)
    assert any(s < 0.60 for s in scores)
    assert "fail" in statuses


def test_build_seed_rows_deterministic_same_reference_time() -> None:
    rows1 = build_seed_rows(REF_TIME)
    rows2 = build_seed_rows(REF_TIME)
    assert json.dumps(rows1, sort_keys=True, default=str) == json.dumps(
        rows2, sort_keys=True, default=str
    )


def test_build_seed_rows_rejects_naive_reference_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_seed_rows(datetime(2026, 10, 1, 12, 0, 0))
