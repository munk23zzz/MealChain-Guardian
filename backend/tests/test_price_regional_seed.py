"""Test harga regional realistis + source supplier_A/B/C (revisi Roy 2026-10-03).

Keputusan Roy:
1. Quote Supplier A/B/C dipersist dengan source unik per supplier
   ('supplier_A'/'supplier_B'/'supplier_C') — menimpa ruling 'supplier_quote × 3'.
2. Harga mockup harus realistis (tidak terlalu murah/mahal); kesenjangan antar
   wilayah diperbolehkan — justru root cause yang dipecahkan proyek ini.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.seed.seed_data import build_seed_rows

DB_URL = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain".replace(
    "+asyncpg", "+psycopg"
)

REF = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

TEN_LOCATIONS = {
    "Jakarta",
    "Bogor",
    "Cianjur",
    "Bandung",
    "Semarang",
    "Yogyakarta",
    "Surabaya",
    "Malang",
    "Palembang",
    "Medan",
}

# Realistis Indonesia 2026 (kg, IDR):
# - telur: min 24.000 (tak mungkin di bawah HET pakan), max 34.000 (wilayah ekstrem)
# - ayam broiler: min 32.000, max 46.000
# - wortel: min 14.000, max 30.000
PRICE_BOUNDS = {
    "telur": (24000, 34000),
    "ayam": (32000, 46000),
    "wortel": (14000, 30000),
}

# Kesamplesan wilayah: rasio harga termahal/termurah per komoditas >= 1.05
# (kesenjangan antar wilayah harus terasa — root cause proyek)
MIN_REGIONAL_SPREAD = 1.05


def test_regional_prices_present_for_all_pairs():
    rows = build_seed_rows(REF)["price_signals"]
    refs = {r["location"] for r in rows if r["source"] == "pihps_reference"}
    assert refs == TEN_LOCATIONS
    for loc in TEN_LOCATIONS:
        for com in PRICE_BOUNDS:
            matching = [
                r
                for r in rows
                if r["location"] == loc
                and r["commodity"] == com
                and r["source"] == "pihps_reference"
            ]
            assert len(matching) == 1, (
                f"{loc}/{com} harus punya tepat 1 referensi"
            )


def test_regional_prices_within_realistic_bounds():
    rows = build_seed_rows(REF)["price_signals"]
    for r in rows:
        if r["source"] != "pihps_reference":
            continue
        lo, hi = PRICE_BOUNDS[r["commodity"]]
        price = float(r["price_per_kg"])
        assert lo <= price <= hi, (
            f"{r['location']}/{r['commodity']} = {price} "
            f"di luar batas realistis {PRICE_BOUNDS[r['commodity']]}"
        )


def test_regional_price_gap_exists_per_commodity():
    """Kesenjangan antar wilayah harus ada (root cause proyek) — rasio >= 1.05."""
    rows = build_seed_rows(REF)["price_signals"]
    for com in PRICE_BOUNDS:
        prices = [
            float(r["price_per_kg"])
            for r in rows
            if r["commodity"] == com and r["source"] == "pihps_reference"
        ]
        ratio = max(prices) / min(prices)
        assert ratio >= MIN_REGIONAL_SPREAD, (
            f"{com}: rasio max/min {ratio:.3f} < {MIN_REGIONAL_SPREAD}"
        )


def test_locked_quotes_have_unique_supplier_sources():
    """Quote A/B/C dipersist dengan source unik 'supplier_A/B/C' (Cianjur/telur)."""
    rows = build_seed_rows(REF)["price_signals"]
    by_source = {
        r["source"]: float(r["price_per_kg"])
        for r in rows
        if r["source"].startswith("supplier_")
    }
    assert by_source == {"supplier_A": 26200.0, "supplier_B": 27000.0, "supplier_C": 32000.0}


def test_cianjur_reference_still_locked():
    rows = build_seed_rows(REF)["price_signals"]
    ref_cianjur = [
        r
        for r in rows
        if r["location"] == "Cianjur"
        and r["commodity"] == "telur"
        and r["source"] == "pihps_reference"
    ]
    assert len(ref_cianjur) == 1
    assert float(ref_cianjur[0]["price_per_kg"]) == 26500.0


def test_db_constraint_accepts_supplier_sources():
    """Setelah migration 003, DB harus menerima source supplier_A/B/C.
    Skip otomatis bila constraint 003 belum ter-aplikasi."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            has_003 = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_constraint "
                    "WHERE conname='price_signals_source_supplier_check')"
                )
            ).scalar()
        if not has_003:
            pytest.skip("migration 003 belum ter-aplikasi")
        inserted = []
        try:
            with engine.begin() as conn:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name='Cianjur'")
                ).scalar_one()
                com_id = conn.execute(
                    text("SELECT id FROM commodities WHERE name='telur'")
                ).scalar_one()
                for src in ("supplier_A", "supplier_B", "supplier_C"):
                    result = conn.execute(
                        text(
                            "INSERT INTO price_signals (id, location_id, commodity_id, "
                            "price_per_kg, recorded_at, source) "
                            "VALUES (gen_random_uuid(), :l, :c, 26200, now(), :s) "
                            "RETURNING id"
                        ),
                        {"l": str(loc_id), "c": str(com_id), "s": src},
                    )
                    inserted.append(str(result.scalar_one()))
        finally:
            # Self-cleaning: row uji tidak boleh tertinggal di DB bersama
            with engine.begin() as conn:
                for pid in inserted:
                    conn.execute(
                        text("DELETE FROM price_signals WHERE id = :i"), {"i": pid}
                    )
    finally:
        engine.dispose()


def test_no_orphan_price_rows_after_load():
    """Invariant idempotensi: DB tidak boleh punya row price_signals di luar
    set id hasil build_seed_rows (deteksi drift skema natural key)."""
    rows = build_seed_rows(REF)
    expected = {str(r["id"]) for r in rows["price_signals"]}
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            db_ids = {str(r[0]) for r in conn.execute(text("SELECT id FROM price_signals"))}
    finally:
        engine.dispose()
    orphans = db_ids - expected
    assert not orphans, f"row orphan di price_signals: {len(orphans)}"
