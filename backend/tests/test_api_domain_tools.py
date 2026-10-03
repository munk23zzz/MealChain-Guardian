"""Test API freshness/safety/price/logistics (Task 12, plan Sprint 1)."""

import uuid as uuidlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain".replace(
    "+asyncpg", "+psycopg"
)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _db():
    return create_engine(DB_URL)


def _batch_id_by_quantity(quantity: float) -> str:
    with _db().connect() as conn:
        return str(
            conn.execute(
                text(
                    "SELECT b.id FROM batches b WHERE b.quantity_kg = :q "
                    "ORDER BY b.created_at LIMIT 1"
                ),
                {"q": quantity},
            ).scalar_one()
        )


def test_freshness_evaluate_pass_band_persists(client):
    batch_id = _batch_id_by_quantity(500)
    resp = client.post("/freshness/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert 0.85 <= body["freshness_score"] <= 1.0
    assert body["status"] == "pass"
    assert "usable_until" in body
    # Persistence (Schema.md batches hanya punya freshness_score + usable_until;
    # status diturunkan ulang deterministik dari score — ruling 2026-10-03)
    with _db().connect() as conn:
        stored = conn.execute(
            text(
                "SELECT freshness_score, usable_until FROM batches WHERE id = :id"
            ),
            {"id": batch_id},
        ).fetchone()
    assert float(stored[0]) == pytest.approx(body["freshness_score"], abs=1e-9)
    assert stored[1].isoformat() == body["usable_until"]


def test_freshness_evaluate_fail_band(client):
    # Semarang ayam freshness 0.15 → fail
    with _db().connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    "SELECT b.id FROM batches b "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "WHERE c.name = 'ayam' LIMIT 1"
                )
            ).scalar_one()
        )
    resp = client.post("/freshness/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    assert resp.json()["status"] == "fail"


def test_freshness_as_of_rejected_when_not_demo(client):
    batch_id = _batch_id_by_quantity(500)
    resp = client.post(
        "/freshness/evaluate",
        json={"batch_id": batch_id, "as_of": "2026-10-01T12:00:00+00:00"},
    )
    assert resp.status_code == 403


def test_freshness_missing_batch_404(client):
    random_id = str(uuidlib.uuid4())
    resp = client.post("/freshness/evaluate", json={"batch_id": random_id})
    assert resp.status_code == 404


def test_safety_evaluate_fail_persists_uppercase(client):
    with _db().connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    "SELECT b.id FROM batches b "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "JOIN locations l ON l.id = b.location_id "
                    "WHERE l.name = 'Surabaya' LIMIT 1"
                )
            ).scalar_one()
        )
    resp = client.post("/safety/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_status"] == "FAIL"
    assert body["excursion_minutes"] >= 30
    assert isinstance(body["reasons"], list)
    # DB lowercase
    with _db().connect() as conn:
        stored = conn.execute(
            text("SELECT safety_status FROM batches WHERE id = :id"),
            {"id": batch_id},
        ).scalar_one()
    assert stored == "fail"


def test_safety_evaluate_pass_clean_batch(client):
    with _db().connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    "SELECT b.id FROM batches b "
                    "JOIN locations l ON l.id = b.location_id "
                    "WHERE l.name = 'Bogor' LIMIT 1"
                )
            ).scalar_one()
        )
    resp = client.post("/safety/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_status"] == "PASS"
    assert body["excursion_minutes"] == 0.0


def test_safety_missing_batch_404(client):
    resp = client.post("/safety/evaluate", json={"batch_id": str(uuidlib.uuid4())})
    assert resp.status_code == 404


def test_price_latest_reference(client):
    resp = client.get("/price/Cianjur/telur")
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_per_kg"] == 26500.0
    assert body["source"] == "pihps_reference"


def test_price_unknown_404(client):
    assert client.get("/price/Atlantis/telur").status_code == 404


def test_price_deviation_supplier_c_flagged(client):
    resp = client.post(
        "/price/deviation",
        json={"location": "Cianjur", "commodity": "telur", "supplier_price": 32000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_price"] == 26500.0
    assert body["classification"] == "anomalous"
    assert body["flagged"] is True


def test_price_deviation_normal(client):
    resp = client.post(
        "/price/deviation",
        json={"location": "Cianjur", "commodity": "telur", "supplier_price": 26200},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "normal"
    assert body["flagged"] is False


def test_logistics_estimate_cianjur_jakarta(client):
    resp = client.post(
        "/logistics/estimate",
        json={
            "source": "Cianjur",
            "target": "Jakarta",
            "quantity_kg": 500,
            "delivery_window_min": 150,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["distance_km"] == 120
    assert body["estimated_time_min"] == 150
    assert body["feasible"] is True


def test_logistics_boundary_over_window_infeasible(client):
    resp = client.post(
        "/logistics/estimate",
        json={
            "source": "Cianjur",
            "target": "Jakarta",
            "quantity_kg": 500,
            "delivery_window_min": 149,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["feasible"] is False


def test_logistics_unknown_location_422_or_404(client):
    resp = client.post(
        "/logistics/estimate",
        json={"source": "Atlantis", "target": "Jakarta", "quantity_kg": 100},
    )
    assert resp.status_code in (404, 422)


def test_malformed_payload_422(client):
    assert client.post("/freshness/evaluate", json={}).status_code == 422
    assert client.post("/safety/evaluate", json={}).status_code == 422
    assert client.post("/logistics/estimate", json={"source": "Cianjur"}).status_code == 422
    assert client.post("/price/deviation", json={"location": "Cianjur"}).status_code == 422


def test_router_no_domain_duplication():
    """Router tidak memuat rumus domain — semua lewat core."""
    import inspect

    import app.api.freshness as fmod
    import app.api.logistics as lmod
    import app.api.price as pmod
    import app.api.safety as smod

    for mod in (fmod, smod, pmod, lmod):
        src = inspect.getsource(mod)
        assert "0.85" not in src.replace("#", ""), f"{mod.__name__} hardcode threshold"
        assert "* 60" not in src, f"{mod.__name__} duplikasi rumus waktu"
