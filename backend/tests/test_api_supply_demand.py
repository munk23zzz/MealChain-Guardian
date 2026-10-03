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

LATEST = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _db():
    return create_engine(DB_URL)


def test_supply_happy_path_with_mock_header(client):
    resp = client.get("/supply/Cianjur/telur")
    assert resp.status_code == 200
    body = resp.json()
    assert body["quantity_kg"] == 1400.0
    assert body["source"] == "mock_sap"
    assert "recorded_at" in body
    assert resp.headers.get("X-Data-Source") == "MOCK"


def test_supply_latest_record_not_sum(client):
    """Terbaru = recorded_at maksimum, bukan penjumlahan snapshot lintas waktu."""
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO supply_records (id, location_id, commodity_id, "
                    "quantity_kg, recorded_at, source) "
                    "SELECT gen_random_uuid(), l.id, c.id, 777, "
                    "'2026-10-05T00:00:00+00'::timestamptz, 'manual' "
                    "FROM locations l, commodities c "
                    "WHERE l.name='Cianjur' AND c.name='telur'"
                )
            )
        resp = client.get("/supply/Cianjur/telur")
        assert resp.status_code == 200
        assert resp.json()["quantity_kg"] == 777.0
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM supply_records WHERE source='manual' "
                    "AND quantity_kg=777"
                )
            )
        engine.dispose()


def test_supply_same_timestamp_source_precedence(client):
    """Mock > manual > sensor pada timestamp sama — SATU record, bukan SUM."""
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO supply_records (id, location_id, commodity_id, "
                    "quantity_kg, recorded_at, source) "
                    "SELECT gen_random_uuid(), l.id, c.id, x.q, x.ts, x.src "
                    "FROM locations l, commodities c, "
                    "(VALUES (999, '2026-10-01T12:00:00+00'::timestamptz, 'manual'), "
                    "        (888, '2026-10-01T12:00:00+00'::timestamptz, 'sensor')) "
                    "AS x(q, ts, src) "
                    "WHERE l.name='Cianjur' AND c.name='telur'"
                )
            )
        resp = client.get("/supply/Cianjur/telur")
        assert resp.status_code == 200
        assert resp.json()["quantity_kg"] == 1400.0
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM supply_records WHERE source IN ('manual','sensor')"
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
            loc_id = conn.execute(
                text("SELECT id FROM locations WHERE name='Cianjur'")
            ).scalar_one()
            com_id = conn.execute(
                text("SELECT id FROM commodities WHERE name='telur'")
            ).scalar_one()
        resp = client.get(f"/supply/{loc_id}/{com_id}")
        assert resp.status_code == 200
        assert resp.json()["quantity_kg"] == 1400.0
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
