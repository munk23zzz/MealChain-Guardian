"""Task 10 Sprint 2: API decision intelligence (4 endpoint).

- GET  /balance/{location}/{commodity}
- POST /balance/recommend
- POST /decisions
- GET  /decisions/{decision_id}

Routers tipis; formulas tetap di core/service. Expiry contract:
now < expires_at → valid, else expired (Task 11 tumpang tindih di sini
untuk GET validity).
"""

import uuid as uuidlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


@pytest.fixture()
def client(auth_headers):
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


def _db():
    return create_engine(DB_URL)


def _cleanup(decision_id):
    with _db().begin() as conn:
        conn.execute(
            text("DELETE FROM decisions WHERE id = :id"),
            {"id": decision_id},
        )


def test_balance_endpoint_returns_gap_facts(client):
    resp = client.get("/balance/Jakarta/telur")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supply_kg"] == 300.0
    assert body["demand_kg"] == 1080.0  # latest record (bukan rerata)
    assert body["shortage_kg"] == 780.0
    assert body["status"] == "shortage"


def test_balance_endpoint_surplus_city_without_demand(client):
    """Cianjur tanpa demand rows → demand 0, surplus murni."""
    resp = client.get("/balance/Cianjur/telur")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["supply_kg"] == 1400.0
    assert body["demand_kg"] == 0.0
    assert body["surplus_kg"] == 1400.0


def test_balance_endpoint_unknown_location_404(client):
    resp = client.get("/balance/Narnia/telur")
    assert resp.status_code == 404


def test_recommend_endpoint_ranks_candidates(client):
    resp = client.post("/balance/recommend", json={})
    assert resp.status_code == 200, resp.text
    items = resp.json()["recommendations"]
    assert items, "seed wajib menghasilkan kandidat"
    ranks = [r["rank"] for r in items]
    assert ranks == sorted(ranks)
    telur = [r for r in items
             if r["candidate"]["source_location"] == "Cianjur"
             and r["candidate"]["destination_location"] == "Jakarta"]
    assert telur, "Cianjur→Jakarta telur wajib ada"


def test_decisions_persist_and_get_validity(client):
    rec = client.post("/balance/recommend", json={}).json()
    top = rec["recommendations"][0]

    payload = {
        "recommendation": top,
        "ttl_minutes": 30,
    }
    resp = client.post("/decisions", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    decision_id = body["decision_id"]
    assert body["status"] == "proposed"  # CHECK enum Schema.md, initial
    assert body["valid"] is True

    got = client.get(f"/decisions/{decision_id}").json()
    assert got["decision_id"] == decision_id
    assert got["valid"] is True
    assert got["expires_at"] > got["created_at"]

    _cleanup(decision_id)


def test_decision_persistence_without_expires_at_impossible(client):
    """Kontrak: expires_at NOT NULL — POST tanpa ttl tetap sukses (default),
    kolom di DB tidak boleh nullable. Verifikasi via information_schema."""
    with _db().connect() as conn:
        nullable = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='decisions' AND column_name='expires_at'"
            )
        ).scalar()
    assert nullable == "NO"


def test_decision_get_unknown_id_404(client):
    resp = client.get(f"/decisions/{uuidlib.uuid4()}")
    assert resp.status_code == 404


def test_recommend_deterministic(client):
    """Determinisme API = urutan ranking & identitas kandidat stabil
    antar panggilan. (Bit-identik penuh diuji di level service dengan
    as_of tetap — endpoint live menghitung freshness pada now().)"""
    a = client.post("/balance/recommend", json={}).json()
    b = client.post("/balance/recommend", json={}).json()
    ids_a = [r["candidate_id"] for r in a["recommendations"]]
    ids_b = [r["candidate_id"] for r in b["recommendations"]]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))  # tanpa duplikat
