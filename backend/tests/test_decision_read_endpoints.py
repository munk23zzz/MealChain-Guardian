"""Test read endpoints decision list + trace timeline (S3-12, TDD).

Frontend Agent Flow butuh sumber data aktual:
- GET /decisions: daftar decision (terbaru dulu) untuk feed.
- GET /decisions/{id}/traces: timeline AgentTrace terurut untuk
  activity log. Tanpa endpoint ini UI harus mengarang data — dilarang.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

RECOMMENDATION = {
    "candidate": {
        "source_location": "Cianjur",
        "destination_location": "Jakarta",
        "commodity": "telur",
        "quantity_kg": "600",
    },
    "safe_delivered_cost": "16206000",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _mk_decision() -> str:
    with TestClient(app) as c:
        resp = c.post("/decisions", json={"recommendation": RECOMMENDATION})
        assert resp.status_code == 201, resp.text
        return resp.json()["decision_id"]


def _cleanup(decision_id: str) -> None:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM agent_traces WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


def test_get_decisions_lists_actual_rows_newest_first(client):
    first = _mk_decision()
    second = _mk_decision()
    try:
        resp = client.get("/decisions")
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        ids = [d["decision_id"] for d in items]
        assert first in ids and second in ids
        # terbaru dulu
        assert ids.index(second) < ids.index(first)
        row = items[ids.index(first)]
        for field in (
            "status", "decision_type", "quantity_kg",
            "safe_delivered_cost", "expires_at", "valid",
        ):
            assert field in row
        assert row["status"] == "proposed"
        assert row["valid"] is True
    finally:
        _cleanup(first)
        _cleanup(second)


def test_get_decision_traces_returns_ordered_actual_steps(client):
    """Trace timeline: urutan langkah asli dari DB (bukan teks karangan)."""
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    decision_id = outcome["decision_id"]
    try:
        resp = client.get(f"/decisions/{decision_id}/traces")
        assert resp.status_code == 200, resp.text
        steps = resp.json()["steps"]
        names = [s["step_name"] for s in steps]
        assert names == [
            "DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE"
        ]
        verify = next(s for s in steps if s["step_name"] == "VERIFY")
        assert verify["output_summary"]["verdict"] == "UNAVAILABLE"
        optimize = next(s for s in steps if s["step_name"] == "OPTIMIZE")
        assert optimize["tool_called"] == "balance.recommend"
        for s in steps:
            assert s["step_at"]
    finally:
        _cleanup(decision_id)


def test_get_decision_traces_404_unknown(client):
    resp = client.get(f"/decisions/{uuid.uuid4()}/traces")
    assert resp.status_code == 404
