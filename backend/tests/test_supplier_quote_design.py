"""Desain quote supplier gaya Roy (revisi kedua 2026-10-03).

- source kembali ke dua nilai generik: 'pihps_reference' | 'supplier_quote'
- identitas supplier ada di field/kolom TERPISAH (supplier -> supplier_id FK)
- tidak terbatas sampai C — seed mendemokan Supplier D untuk membuktikan skalabilitas
"""

from datetime import UTC, datetime

from app.seed.seed_data import build_seed_rows

REF = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def test_seed_defines_four_suppliers_including_d():
    """Supplier bukan patokan sampai C — seed punya 4 supplier (A/B/C/D)."""
    suppliers = build_seed_rows(REF)["suppliers"]
    names = {s["name"] for s in suppliers}
    assert {
        "Supplier A Cianjur",
        "Supplier B Cianjur",
        "Supplier C Cianjur",
        "Supplier D Cianjur",
    } <= names


def test_quotes_use_generic_source_with_supplier_name():
    """Quote = source 'supplier_quote' + field 'supplier' (bukan source supplier_X)."""
    rows = build_seed_rows(REF)["price_signals"]
    quotes = [r for r in rows if r["source"] == "supplier_quote"]
    assert len(quotes) >= 4, "minimal 4 quote (A/B/C/D)"

    sources = {r["source"] for r in rows}
    assert sources == {"pihps_reference", "supplier_quote"}, (
        f"source harus dua nilai generik, ada: {sources}"
    )

    by_supplier = {
        r["supplier"]: float(r["price_per_kg"])
        for r in quotes
        if r["commodity"] == "telur"
    }
    assert by_supplier["Supplier A Cianjur"] == 26200.0
    assert by_supplier["Supplier B Cianjur"] == 27000.0
    assert by_supplier["Supplier C Cianjur"] == 32000.0
    assert by_supplier["Supplier D Cianjur"] == 25400.0


def test_quotes_carry_no_supplier_initials_in_source():
    """source harus persis dua nilai kontrak — otomatis melarang pola inisial
    (supplier_A/dll) karena nilai itu berada di luar set yang diizinkan."""
    rows = build_seed_rows(REF)["price_signals"]
    allowed = {"pihps_reference", "supplier_quote"}
    for r in rows:
        assert r["source"] in allowed, (
            f"source '{r['source']}' di luar kontrak {allowed} — "
            "identitas supplier seharusnya ada di kolom supplier_id"
        )
