"""Revisi ketiga Roy: supplier lokal di SEMUA kota (bukan hanya Cianjur).

- pihps_reference TETAP sebagai acuan pasar per kota (benchmark /price/deviation)
- tiap kota punya >=1 supplier lokal (nama memuat wilayah) dengan quote format
  {source: 'supplier_quote', supplier: '<nama wilayah>', price_per_kg}
"""

from datetime import UTC, datetime

from app.seed.seed_data import build_seed_rows

REF = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

TEN_CITIES = {
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


def test_every_city_has_local_supplier_quote():
    rows = build_seed_rows(REF)["price_signals"]
    quote_cities = {
        r["location"] for r in rows if r["source"] == "supplier_quote"
    }
    assert quote_cities == TEN_CITIES, (
        f"kota tanpa supplier quote: {TEN_CITIES - quote_cities}"
    )


def test_local_suppliers_named_after_their_city():
    """Supplier lokal memakai nama wilayah (mis. 'Supplier Semarang-1')."""
    rows = build_seed_rows(REF)["price_signals"]
    for r in rows:
        if r["source"] != "supplier_quote":
            continue
        city = r["location"]
        assert city in r["supplier"], (
            f"nama supplier '{r['supplier']}' tidak memuat wilayah '{city}'"
        )


def test_quotes_reference_still_thirty_city_prices():
    rows = build_seed_rows(REF)["price_signals"]
    refs = [r for r in rows if r["source"] == "pihps_reference"]
    assert len(refs) == 30, "acuan pasar 10 kota x 3 komoditas tetap utuh"


def test_cianjur_locked_quotes_still_exact():
    rows = build_seed_rows(REF)["price_signals"]
    cianjur_quotes = {
        r["supplier"]: float(r["price_per_kg"])
        for r in rows
        if r["location"] == "Cianjur" and r["source"] == "supplier_quote"
    }
    assert cianjur_quotes == {
        "Supplier A Cianjur": 26200.0,
        "Supplier B Cianjur": 27000.0,
        "Supplier C Cianjur": 32000.0,
        "Supplier D Cianjur": 25400.0,
    }


def test_new_local_quotes_within_realistic_bounds():
    bounds = {"telur": (24000, 34000), "ayam": (32000, 46000), "wortel": (14000, 30000)}
    rows = build_seed_rows(REF)["price_signals"]
    for r in rows:
        if r["source"] != "supplier_quote":
            continue
        lo, hi = bounds[r["commodity"]]
        price = float(r["price_per_kg"])
        assert lo <= price <= hi, (
            f"quote {r['supplier']} = {price} di luar batas realistis {bounds[r['commodity']]}"
        )
