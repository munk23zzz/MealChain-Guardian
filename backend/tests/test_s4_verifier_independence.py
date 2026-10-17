"""S4-00 O-SEC-3: verifier independen — verdict TIDAK pernah dari client.

Kontrak baru /actions/verify (plan §10, resolusi Owner):
- request HANYA decision_id (extra="forbid") — browser tidak bisa mengirim verdict.
- server menyusun ctx kanonik dari DB lalu memanggil run_verifier
  (chain env; test menyuntik provider via dependency override).
- tanpa provider → UNAVAILABLE (konservatif), bukan echo client.
- verify ditolak 409 bila status decision di luar
  proposed/verifier_flagged/pending_approval (integritas approval, §22).
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.test_action_boundary_e2e import _event1_decision_id
from tests.test_actions import _cleanup, _login, _mk_user

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_verifier():
    """Suntik chain provider server-side (bukan verdict dari request)."""

    def _install(verdict: str, reason: str = "uji"):
        def _chain():
            return [
                (
                    "test_provider",
                    lambda prompt: json.dumps({"verdict": verdict, "reason": reason}),
                    "test",
                )
            ]

        app.dependency_overrides[get_verifier_chain] = _chain

    yield _install
    app.dependency_overrides.pop(get_verifier_chain, None)


def _verifier_row(decision_id: str):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(
                text(
                    "SELECT verified_by, verifier_note, status FROM decisions "
                    "WHERE id = :d"
                ),
                {"d": decision_id},
            ).one_or_none()
    finally:
        engine.dispose()


def test_verify_menolak_verdict_dari_client(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id, "verdict": "CONSISTENT"},
            headers=_login(client, head),
        )
        assert resp.status_code == 422, resp.text
        verified_by, note, _status = _verifier_row(decision_id)
        assert note == "unavailable"  # server-derived, bukan echo client
        assert verified_by == "verifier_agent"
    finally:
        _cleanup(decision_id, [head["email"]])


def test_verify_menurunkan_unavailable_tanpa_provider(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "UNAVAILABLE"
        assert body["approval_requirement"]["min_approvals"] == 2
        _v, note, _s = _verifier_row(decision_id)
        assert note == "unavailable"
    finally:
        _cleanup(decision_id, [head["email"]])


def test_verify_memakai_chain_server_side(client, fake_verifier):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        fake_verifier("CONSISTENT", reason="uji chain server-side")
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["verdict"] == "CONSISTENT"
        assert body["provider"] == "test_provider"
        assert body["approval_requirement"]["min_approvals"] == 1
        _v, note, _s = _verifier_row(decision_id)
        assert note == "consistent"
    finally:
        _cleanup(decision_id, [head["email"]])


def test_verify_flagged_turunkan_status_verifier_flagged(client, fake_verifier):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        fake_verifier("FLAGGED")
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["approval_requirement"]["min_approvals"] == 2
        _v, note, status = _verifier_row(decision_id)
        assert note == "flagged"
        assert status == "verifier_flagged"
    finally:
        _cleanup(decision_id, [head["email"]])


def test_verify_ditolak_409_setelah_approved(client, fake_verifier):
    head = _mk_user("sppg_head", "Jakarta")
    # Ruling 2026-10-14 §3: uji ini soal integritas jejak audit (verify setelah
    # ada approval → 409), bukan soal cakupan. Ahli gizi wajib satu SPPG dengan
    # target agar sampai ke penjaga 409, bukan berhenti di 403 cakupan.
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _event1_decision_id()
    try:
        fake_verifier("CONSISTENT")
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
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, nutritionist),
        )
        assert resp.status_code == 409, resp.text
        _v, note, _s = _verifier_row(decision_id)
        assert note == "consistent"  # tidak berubah oleh verify late
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])
