"""Test API supply/demand/forecast (Task 11, plan Sprint 1).

Menjalankan FastAPI app nyata terhadap PostgreSQL ter-seed.
Semua data sisipan test dibersihkan di finally.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

# Ruling REF seed canonical (Roy 2026-10-09): REF 2026-10-08 12:00 UTC.
LATEST = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def client(monitor_headers):
    """Klien baca nasional (bgn_monitor).

    Ruling 2026-10-14: kepala SPPG Jakarta hanya boleh membaca lokasinya
    sendiri, sedangkan berkas ini menguji semantik nilai supply/demand di
    Cianjur/Bogor (jangkar angka Sprint 1). Peran yang sah membaca lintas
    lokasi adalah bgn_monitor — berkas ini tidak menguji mutasi apa pun.
    """
    with TestClient(app) as c:
        c.headers.update(monitor_headers)
        yield c


def _db():
    return create_engine(DB_URL)


def _ids_for(conn, location: str, commodity: str):
    loc_id = conn.execute(
        text("SELECT id FROM locations WHERE name = :n"), {"n": location}
    ).scalar_one()
    com_id = conn.execute(
        text("SELECT id FROM commodities WHERE name = :n"), {"n": commodity}
    ).scalar_one()
    return loc_id, com_id


def _latest_supply_row(conn, loc_id, com_id):
    """Baris TERBARU di DB untuk pasangan ini, memakai urutan yang sama dengan
    endpoint `/supply`: recorded_at DESC lalu presedensi source (mock_sap >
    manual > sensor). Dipakai sebagai acuan angka supaya tes tidak memaku
    snapshot kanonik 8 Okt — ujung deret AKTUAL demo kini 4 Nov 12:00."""
    return conn.execute(
        text(
            "SELECT quantity_kg, source FROM supply_records "
            "WHERE location_id = :loc AND commodity_id = :com "
            "ORDER BY recorded_at DESC, "
            "CASE source WHEN 'mock_sap' THEN 0 WHEN 'manual' THEN 1 "
            "WHEN 'sensor' THEN 2 ELSE 99 END "
            "LIMIT 1"
        ),
        {"loc": loc_id, "com": com_id},
    ).one()


def test_supply_happy_path_with_mock_header(client):
    engine = _db()
    try:
        with engine.connect() as conn:
            loc_id, com_id = _ids_for(conn, "Cianjur", "telur")
            expected_qty, expected_source = _latest_supply_row(conn, loc_id, com_id)
    finally:
        engine.dispose()

    resp = client.get("/supply/Cianjur/telur")
    assert resp.status_code == 200
    body = resp.json()
    # Fase 4: deret AKTUAL demo (s/d 4 Nov 12:00) yang kini terbaru, jadi angka
    # dibandingkan dengan baris terbaru DB — bukan snapshot kanonik 1400. Baris
    # demo tetap bersumber 'mock_sap', jadi asersi source & header di bawah tetap sah.
    assert body["quantity_kg"] == float(expected_qty)
    assert body["source"] == expected_source == "mock_sap"
    assert "recorded_at" in body
    assert resp.headers.get("X-Data-Source") == "MOCK"


def test_supply_latest_record_not_sum(client):
    """Terbaru = recorded_at maksimum, bukan penjumlahan snapshot lintas waktu."""
    engine = _db()
    try:
        # Fase 4: cap waktu uji harus LEBIH BARU dari ujung deret AKTUAL demo
        # (4 Nov 12:00) agar baris uji ini benar-benar 'terbaru' bagi endpoint.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO supply_records (id, location_id, commodity_id, "
                    "quantity_kg, recorded_at, source) "
                    "SELECT gen_random_uuid(), l.id, c.id, 777, "
                    "'2026-11-20T00:00:00+00'::timestamptz, 'manual' "
                    "FROM locations l, commodities c "
                    "WHERE l.name='Cianjur' AND c.name='telur'"
                )
            )
        resp = client.get("/supply/Cianjur/telur")
        assert resp.status_code == 200
        assert resp.json()["quantity_kg"] == 777.0
    finally:
        with engine.begin() as conn:
            # Hapus HANYA baris uji ini (cap waktu + source khas tes), jangan sentuh seed/demo.
            conn.execute(
                text(
                    "DELETE FROM supply_records WHERE source='manual' "
                    "AND recorded_at='2026-11-20T00:00:00+00'::timestamptz"
                )
            )
        engine.dispose()


def test_supply_same_timestamp_source_precedence(client):
    """Mock > manual > sensor pada timestamp sama — SATU record, bukan SUM.

    Fase 4: baris uji disisipkan pada cap waktu SAMA yang lebih baru dari ujung
    deret AKTUAL demo (4 Nov 12:00) — di sini 20 Nov 12:00 — sehingga ketiga
    baris itulah yang jadi 'terbaru' dan presedensi source yang diuji benar-benar
    menentukan pemenangnya.
    """
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO supply_records (id, location_id, commodity_id, "
                    "quantity_kg, recorded_at, source) "
                    "SELECT gen_random_uuid(), l.id, c.id, x.q, x.ts, x.src "
                    "FROM locations l, commodities c, "
                    "(VALUES (1500, '2026-11-20T12:00:00+00'::timestamptz, 'mock_sap'), "
                    "        (999, '2026-11-20T12:00:00+00'::timestamptz, 'manual'), "
                    "        (888, '2026-11-20T12:00:00+00'::timestamptz, 'sensor')) "
                    "AS x(q, ts, src) "
                    "WHERE l.name='Cianjur' AND c.name='telur'"
                )
            )
        resp = client.get("/supply/Cianjur/telur")
        assert resp.status_code == 200
        body = resp.json()
        assert body["quantity_kg"] == 1500.0  # mock_sap menang
        assert body["source"] == "mock_sap"
    finally:
        with engine.begin() as conn:
            # Hapus HANYA baris uji (cap waktu unik milik tes ini), jangan sentuh seed/demo.
            conn.execute(
                text(
                    "DELETE FROM supply_records "
                    "WHERE recorded_at='2026-11-20T12:00:00+00'::timestamptz"
                )
            )
        engine.dispose()


def test_supply_unknown_location_404(client):
    assert client.get("/supply/Atlantis/telur").status_code == 404
    assert client.get("/supply/Cianjur/nasi-goreng").status_code == 404


def test_supply_by_uuid(client):
    engine = _db()
    try:
        with engine.connect() as conn:
            loc_id, com_id = _ids_for(conn, "Cianjur", "telur")
            # Fase 4: angka acuan = baris terbaru DB (deret AKTUAL demo s/d
            # 4 Nov 12:00), bukan snapshot kanonik 1400.
            expected_qty, _ = _latest_supply_row(conn, loc_id, com_id)
        resp = client.get(f"/supply/{loc_id}/{com_id}")
        assert resp.status_code == 200
        assert resp.json()["quantity_kg"] == float(expected_qty)
    finally:
        engine.dispose()


def test_demand_happy_path(client):
    resp = client.get("/demand/Jakarta/telur")
    assert resp.status_code == 200
    body = resp.json()
    assert body["quantity_kg"] == 1080.0
    assert "needed_by" in body


def test_demand_unknown_404(client):
    assert client.get("/demand/Atlantis/telur").status_code == 404


def test_forecast_happy_path(client):
    resp = client.get("/demand/forecast/Jakarta/telur")
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "statistical_fallback"
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["forecast_qty_kg"] > 0


def test_forecast_horizon_respected(client):
    resp = client.get("/demand/forecast/Jakarta/telur", params={"horizon_days": 2})
    assert resp.status_code == 200
    # 3 observasi terbaru Jakarta/telur (terlama→terbaru): 1100, 1000, 1080
    daily_avg = 1100 * 0.2 + 1000 * 0.3 + 1080 * 0.5
    assert resp.json()["forecast_qty_kg"] == pytest.approx(daily_avg * 2, rel=1e-6)


def test_forecast_invalid_horizon_422(client):
    resp = client.get("/demand/forecast/Jakarta/telur", params={"horizon_days": 0})
    assert resp.status_code == 422
    resp = client.get("/demand/forecast/Jakarta/telur", params={"horizon_days": "abc"})
    assert resp.status_code == 422


def test_forecast_unknown_404(client):
    assert client.get("/demand/forecast/Atlantis/telur").status_code == 404


def test_engine_reused_across_requests(client):
    """Kontrak lifespan: satu engine dipakai ulang antar request (tidak bocor)."""
    engine_first = app.state.engine
    client.get("/supply/Cianjur/telur")
    client.get("/supply/Bogor/telur")
    assert app.state.engine is engine_first


def test_engine_fresh_per_lifespan():
    """Lifespan baru = engine baru; engine lama sudah di-dispose saat shutdown."""
    import asyncio

    with TestClient(app) as c1:
        e1 = app.state.engine
        c1.get("/supply/Cianjur/telur")
    # Beri event loop kesempatan menyelesaikan disposal
    asyncio.new_event_loop().close()
    with TestClient(app) as c2:
        e2 = app.state.engine
        c2.get("/supply/Cianjur/telur")
    assert e1 is not e2
    # Engine lama dan baru memakai pool berbeda (dispose + recreate pada lifespan baru)
    assert e1.pool is not e2.pool
