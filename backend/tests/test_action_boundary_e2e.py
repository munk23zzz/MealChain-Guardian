"""Test approval + action boundary E2E (S3-11, TDD).

Full lifecycle API-pure dari decision Event 1:
propose → verify (verifier_note benar-benar tertulis) → approval
requirement sesuai verdict → human approve → execute → PO Mock SAP.
Rejected/expired diblokir; bgn_monitor tidak bisa approve/execute.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.test_actions import _cleanup, _login, _mk_user

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


def _force_server_verdict(verdict: str, reason: str = "uji"):
    """Override chain verifier server-side (kontrak O-SEC-3: verdict berasal
    dari run_verifier server, bukan dari request body)."""
    import json as _json

    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: _json.dumps({"verdict": verdict, "reason": reason}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain

    def _restore():
        app.dependency_overrides.pop(get_verifier_chain, None)

    return _restore


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
    """Verify endpoint HARUS menulis verdict ke verifier_note (gap nyata).

    Kontrak O-SEC-3: verdict diturunkan server (chain override FLAGGED),
    request body tidak membawa verdict.
    """
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    restore = _force_server_verdict("FLAGGED")
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
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
        restore()
        _cleanup(decision_id, [head["email"]])


def test_actions_verify_rejects_unknown_verdict(client):
    """Verdict tak dikenal tidak bisa masuk lewat jalur mana pun: request
    body ditolak 422 (extra="forbid"); provider yang mengembalikan output
    tak terbaca diturunkan UNAVAILABLE oleh run_verifier (konservatif)."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    restore = _force_server_verdict("SEPUASNYA")
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        # 1) body membawa verdict → ditolak 422 oleh extra="forbid"
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "SEPUASNYA"},
            headers=_login(client, head),
        )
        assert resp.status_code == 422
        # 2) provider mengembalikan verdict tak valid → UNAVAILABLE server-side
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verdict"] == "UNAVAILABLE"
        # verifier_note tidak berubah oleh verify yang ditolak/UPA — decision
        # lahir dengan verdict verifier pipeline ('unavailable' tanpa provider)
        assert _verifier_note(decision_id) == "unavailable"
    finally:
        restore()
        _cleanup(decision_id, [head["email"]])


def test_e2e_event1_to_mock_sap_dua_approval_untuk_transfer(client):
    """Transfer operasional: dua approval (Head lalu Nutritionist) wajib → PO mock."""
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _event1_decision_id()
    restore = _force_server_verdict("CONSISTENT")
    try:
        # propose
        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending_approval"
        # verify CONSISTENT — server-side chain override (kontrak O-SEC-3)
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["approval_requirement"]["min_approvals"] == 2
        # approve Head saja → belum cukup
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409, "approval Nutritionist belum ada"
        # approval kedua: Nutritionist
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, nutritionist),
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
        restore()
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_e2e_unavailable_requires_both_approvers(client):
    """UNAVAILABLE: dua approval (head DAN nutritionist) wajib."""
    head = _mk_user("sppg_head", "Jakarta")
    # Ruling 2026-10-14 §3: approver kedua wajib satu SPPG dengan target
    # (dulu "Bogor" — lolos hanya karena jalur tulis belum ber-cakupan).
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _event1_decision_id()
    restore = _force_server_verdict("UNAVAILABLE")
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
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
        restore()
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_e2e_rejected_decision_blocked(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    restore = _force_server_verdict("CONSISTENT")
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
            headers=_login(client, head),
        )
        client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
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
        restore()
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
            ("verify", {"decision_id": decision_id}),
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
