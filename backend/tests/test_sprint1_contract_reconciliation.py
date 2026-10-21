"""Rekonsiliasi kontrak Sprint 1 (Task 0 Sprint 2).

RED awal: kolom drift price_signals.seed_key hanya ada di database live —
tidak ada di migration mana pun, ORM, seed loader, API, atau docs.
Keputusan Roy 2026-10-05 (disetujui): bukan kontrak aplikasi, dihapus lewat
migration 005_reconcile_sprint1_schema; idempotensi seed tetap UUID5
natural key di loader.

Dua test lainnya adalah pengaman regresi: migration rekonsiliasi TIDAK
boleh mengubah jumlah baris maupun kontrak source/supplier.
"""

import json
from pathlib import Path

from sqlalchemy import create_engine, text

from app.seed.suppliers_demo import load_demo_rows
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC
SEED_JSON = Path("/data/seed/sprint1_seed.json")


def _harga_seed() -> list[dict]:
    """Baris `prices` dari berkas seed — sumber angka, bukan konstanta tes."""
    with open(SEED_JSON, encoding="utf-8") as f:
        return json.load(f)["prices"]


def test_price_signals_has_no_seed_key_column():
    """Kolom drift seed_key tidak boleh ada di database."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='price_signals' "
                    "AND column_name='seed_key'"
                )
            ).scalar()
        assert not exists, (
            "price_signals.seed_key adalah drift database, "
            "bukan kontrak aplikasi — wajib dihapus migration 005"
        )
    finally:
        engine.dispose()


def test_reconciliation_preserves_row_counts():
    """Migration rekonsiliasi tidak boleh menghapus baris bisnis."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            # Fase 4 (2026-10-15): tabel yang sama juga memuat deret waktu DEMO
            # (`origin='demo'`, lihat app/seed/timeseries.py). Kontrak
            # rekonsiliasi ini soal baris KANONIK hasil seed, jadi dihitung
            # dengan `origin='seed'` — bukan lagi count(*) seluruh tabel.
            prices = conn.execute(
                text("SELECT count(*) FROM price_signals WHERE origin='seed'")
            ).scalar()
            suppliers = conn.execute(
                text("SELECT count(*) FROM suppliers")
            ).scalar()
            refs = conn.execute(
                text(
                    "SELECT count(*) FROM price_signals "
                    "WHERE source='pihps_reference' AND origin='seed'"
                )
            ).scalar()
            quotes = conn.execute(
                text(
                    "SELECT count(*) FROM price_signals "
                    "WHERE source='supplier_quote' AND origin='seed'"
                )
            ).scalar()
        # Angka TURUNAN dari berkas seed, bukan konstanta: dataset 19 Okt 2026
        # memuat 40 pasangan lokasi×komoditas (10 referensi + kutipan lokal per
        # kota). Dulu 40 referensi + 17 kutipan = 57.
        harga = _harga_seed()
        assert refs == sum(1 for r in harga if r["source"] == "pihps_reference")
        assert quotes == sum(1 for r in harga if r["source"] == "supplier_quote")
        assert prices == refs + quotes
        # Berkas demo kini MASTER: jumlah baris = jumlah baris berkas (tidak ada
        # lagi 17 kanonik legacy + overlay).
        assert suppliers == len(load_demo_rows())
    finally:
        engine.dispose()


def test_source_supplier_contract_intact():
    """Referensi tanpa supplier; quote wajib terikat supplier_id; 10 kota."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            bad = conn.execute(
                text(
                    "SELECT count(*) FROM price_signals ps "
                    "WHERE (ps.source='pihps_reference' "
                    "AND ps.supplier_id IS NOT NULL) "
                    "OR (ps.source='supplier_quote' "
                    "AND ps.supplier_id IS NULL)"
                )
            ).scalar()
            quote_cities = conn.execute(
                text(
                    "SELECT count(DISTINCT l.name) FROM price_signals ps "
                    "JOIN locations l ON l.id=ps.location_id "
                    "WHERE ps.source='supplier_quote'"
                )
            ).scalar()
        assert bad == 0
        assert quote_cities == 10
    finally:
        engine.dispose()
