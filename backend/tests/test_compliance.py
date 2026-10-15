"""Compliance dossier API: auth scope and persisted evidence contract."""

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.test_actions import _drop_user, _login, _mk_user

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _db():
    return create_engine(DB_URL)


def _decision_with_evidence(client, owner):
    response = client.post(
        "/decisions",
        headers=_login(client, owner),
        json={
            "recommendation": {
                "candidate": {
                    "source_location": "Cianjur",
                    "destination_location": "Jakarta",
                    "commodity": "telur",
                    "quantity_kg": "12",
                },
                "safe_delivered_cost": "1000",
            },
        },
    )
    assert response.status_code == 201, response.text
    decision_id = response.json()["decision_id"]
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO decision_evidence "
                    "(id, decision_id, evidence_type, payload, is_consistent, recorded_at) "
                    "VALUES (:id, :decision, 'temperature', CAST(:payload AS jsonb), "
                    ":consistent, :recorded)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "decision": decision_id,
                    "payload": (
                        '{"reading": 4, "unit": "C", "provenance": "MOCK", '
                        '"status": "PASS"}'
                    ),
                    "consistent": False,
                    "recorded": datetime.now(timezone.utc),
                },
            )
    finally:
        engine.dispose()
    return decision_id


def _cleanup(decision_id, emails):
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM decisions WHERE id = :id"), {"id": decision_id})
    finally:
        engine.dispose()
    for email in emails:
        _drop_user(email)


def test_compliance_returns_actual_persisted_evidence_and_integrity_metadata():
    owner = _mk_user("sppg_head", "Jakarta")
    with TestClient(app) as client:
        decision_id = _decision_with_evidence(client, owner)
        try:
            response = client.get(
                f"/decisions/{decision_id}/compliance", headers=_login(client, owner)
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["decision_id"] == decision_id
            assert body["evidence"][0]["payload"]["provenance"] == "MOCK"
            assert body["evidence"][0]["is_consistent"] is False
            assert body["signature"]["state"] in {"signed", "unsigned"}
            assert body["content_address"].startswith("mc1-")
        finally:
            _cleanup(decision_id, [owner["email"]])


def test_compliance_uses_exact_decision_read_scope_for_other_user_and_monitor():
    owner = _mk_user("sppg_head", "Jakarta")
    other = _mk_user("sppg_nutritionist", "Bogor")
    monitor = _mk_user("bgn_monitor")
    with TestClient(app) as client:
        decision_id = _decision_with_evidence(client, owner)
        try:
            # Ruling 2026-10-14: verifier lintas SPPG TIDAK lagi boleh membaca
            # (pengecualian 2026-10-08 dicabut); bgn_monitor tetap global.
            assert client.get(
                f"/decisions/{decision_id}/compliance", headers=_login(client, other)
            ).status_code == 403
            assert client.get(
                f"/decisions/{decision_id}/compliance", headers=_login(client, monitor)
            ).status_code == 200
        finally:
            _cleanup(decision_id, [owner["email"], other["email"], monitor["email"]])


def test_compliance_requires_auth_and_returns_404_for_unknown_decision():
    with TestClient(app) as client:
        decision_id = uuid.uuid4()
        assert client.get(f"/decisions/{decision_id}/compliance").status_code == 401
        user = _mk_user("sppg_head", "Jakarta")
        try:
            response = client.get(
                f"/decisions/{decision_id}/compliance", headers=_login(client, user)
            )
            assert response.status_code == 404
        finally:
            _drop_user(user["email"])
