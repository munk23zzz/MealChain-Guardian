"""Test approval + action boundary E2E (S3-11, TDD).

Full lifecycle API-pure dari decision Event 1:
propose → verify (verifier_note benar-benar tertulis) → approval
requirement sesuai verdict → human approve → execute → PO Mock SAP.
Rejected/expired diblokir; bgn_monitor tidak bisa approve/execute.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.test_actions import _cleanup, _login, _mk_user

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _event1_decision_id() -> str:
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    return outcome["decision_id"]


def _set_expiry_past(decision_id: str) -> None:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE decisions SET expires_at = "
                    "now() - interval '1 minute' WHERE id = :d"
                ),
                {"d": decision_id},
            )
    finally:
        engine.dispose()


def _verifier_note(decision_id: str) -> str | None:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT verifier_note FROM decisions WHERE id = :d"
                ),
                {"d": decision_id},
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def test_actions_verify_writes_verifier_note_and_flagged_status(client):
    """Verify endpoint HARUS menulis verdict ke verifier_note (gap nyata)."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "FLAGGED"},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "FLAGGED"
        assert body["approval_requirement"]["min_approvals"] == 2
        assert body["approval_requirement"]["required_roles"] == [
            ["sppg_head"],
            ["sppg_nutritionist"],
        ]
        # verdict TERTULIS di DB — bukan sekadar echo response
        assert _verifier_note(decision_id) == "flagged"
        # status decision ikut turun ke verifier_flagged
        engine = create_engine(DB_URL)
        with engine.begin() as conn:
            status = conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"),
                {"d": decision_id},
            ).scalar_one()
        engine.dispose()
        assert status == "verifier_flagged"
    finally:
        _cleanup(decision_id, [head["email"]])


def test_actions_verify_rejects_unknown_verdict(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "SEPUASNYA"},
            headers=_login(client, head),
        )
        assert resp.status_code == 422
        # verifier_note tetap kosong
        assert _verifier_note(decision_id) is None
    finally:
        _cleanup(decision_id, [head["email"]])


def test_e2e_event1_to_mock_sap_single_approval_consistent(client):
    """CONSISTENT: 1 approval (head ATAU nutritionist) cukup → PO mock."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        # propose
        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending_approval"
        # verify CONSISTENT (sumber: run_verifier di pipeline nyata)
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "CONSISTENT"},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["approval_requirement"]["min_approvals"] == 1
        # approve HANYA head → requirement CONSISTENT terpenuhi
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        # execute → PO mock
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data_source"] == "MOCK"
        assert body["po_number"].startswith("MC-")
        engine = create_engine(DB_URL)
        with engine.begin() as conn:
            po = conn.execute(
                text(
                    "SELECT COUNT(*) FROM sap_mock_purchase_orders "
                    "WHERE decision_id = :d"
                ),
                {"d": decision_id},
            ).scalar_one()
        engine.dispose()
        assert po == 1
    finally:
        _cleanup(decision_id, [head["email"]])


def test_e2e_unavailable_requires_both_approvers(client):
    """UNAVAILABLE: dua approval (head DAN nutritionist) wajib."""
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Bogor")
    decision_id = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "UNAVAILABLE"},
            headers=_login(client, head),
        )
        # hanya head → execute ditolak
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        # nutritionist melengkapi → execute lolos
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, nutritionist),
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_e2e_rejected_decision_blocked(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "CONSISTENT"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": False,
                  "comment": "tidak setuju"},
            headers=_login(client, head),
        )
        assert resp.status_code == 200
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        assert "ditolak" in resp.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])


def test_e2e_expired_decision_blocked(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        _set_expiry_past(decision_id)
        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        assert "expired" in resp.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])


def test_e2e_bgn_monitor_cannot_touch_lifecycle(client):
    monitor = _mk_user("bgn_monitor")
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        for endpoint, payload in (
            ("propose", {"decision_id": decision_id,
                         "material_number": "MAT-TELUR"}),
            ("verify", {"decision_id": decision_id,
                        "verdict": "CONSISTENT"}),
            ("approve", {"decision_id": decision_id, "approved": True}),
            ("execute", {"decision_id": decision_id}),
        ):
            resp = client.post(
                f"/actions/{endpoint}", json=payload,
                headers=_login(client, monitor),
            )
            assert resp.status_code == 403, f"{endpoint}: {resp.text}"
    finally:
        _cleanup(decision_id, [monitor["email"], head["email"]])
