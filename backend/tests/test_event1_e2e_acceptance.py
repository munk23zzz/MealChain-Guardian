"""S3-13: Event 1 E2E acceptance — jalur UI → supervisor → tools → decision
→ approval → Mock SAP, semuanya aktual di environment yang tersedia.

Hop eksternal tidak tersedia di env lokal → dilaporkan jujur:
- verifier tanpa provider → UNAVAILABLE, approval dual AND (S3-01);
- safety FAIL core tidak bisa diangkat (guard S3-06);
- PO mock selalu data_source=MOCK;
- trace tersimpan = langkah AKTUAL, tanpa LEARN sintetis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL
from tests.test_action_boundary_e2e import _force_server_verdict
from tests.test_actions import _cleanup, _login, _mk_user
from tests.test_event1_supervisor_flow import _trace_rows

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _event1_decision_id(**overrides) -> tuple[str, dict]:
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(
        commodity="telur", target_location="Jakarta", **overrides
    )
    return outcome["decision_id"], outcome


def _po_rows(decision_id: str) -> list[dict]:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT po_number, status FROM "
                    "sap_mock_purchase_orders WHERE decision_id = :d"
                ),
                {"d": decision_id},
            ).mappings().all()
            return [dict(r) for r in rows]
    finally:
        engine.dispose()


def test_event1_e2e_propose_approve_execute_mock_sap(client):
    """Full hop aktual: supervisor→decision→propose→dual approve→execute→PO mock."""
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id, outcome = _event1_decision_id()
    try:
        # supervisor hop: decision nyata + verifier jujur (tanpa provider)
        assert outcome["decision_snapshot"]["status"] == "proposed"
        assert outcome["verifier"]["verdict"] == "UNAVAILABLE"
        # trace tersimpan = langkah aktual
        steps = _trace_rows(decision_id)
        assert [s["step_name"] for s in steps] == [
            "DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE",
        ]
        assert all("LEARN" not in s["step_name"] for s in steps)

        head_h = _login(client, head)
        resp = client.post(
            "/actions/propose",
            json={
                "decision_id": decision_id,
                "material_number": "MAT-TELUR",
                "supplier_id": None,
            },
            headers=head_h,
        )
        assert resp.status_code == 201, resp.text
        # UNAVAILABLE dari supervisor hop → approval TERKUNCI (audit M1: approve
        # menuntut verdict hasil audit). Verdict dicatat lewat jalur server
        # /actions/verify dengan provider uji, bukan dengan memalsukan kolom DB.
        restore = _force_server_verdict("CONSISTENT", "uji e2e")
        try:
            resp = client.post(
                "/actions/verify",
                json={"decision_id": decision_id},
                headers=head_h,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["recorded"] is True, resp.text
        finally:
            restore()
        # dual AND tetap berlaku (konservatif, S3-01)
        assert resp.json()["approval_requirement"]["min_approvals"] == 2

        for user in (head, nut):
            r = client.post(
                "/actions/approve",
                json={"decision_id": decision_id, "approved": True},
                headers=_login(client, user),
            )
            assert r.status_code == 200, r.text

        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=head_h,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data_source"] == "MOCK"
        assert body["po_number"].startswith("MC-")
        # PO tertulis di DB (bukan cuma response); label MOCK = kontrak API.
        # Gerbang 1 (dokumen 02-approval-action.md §6): PO masih DRAFT — review
        # Kepala SPPG adalah gerbang kedua, diuji di test_po_review_flow.py.
        pos = _po_rows(decision_id)
        assert len(pos) == 1
        assert pos[0]["status"] == "draft"
        review = client.post(
            f"/actions/purchase-orders/{body['po_number']}/approve",
            headers=head_h,
        )
        assert review.status_code == 200, review.text
        assert _po_rows(decision_id)[0]["status"] == "submitted"
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])


def test_event1_e2e_safety_fail_guard_via_api(client):
    """Safety FAIL core + model stub bandel → verdict FLAGGED (guard S3-06)."""

    def stubborn_model(prompt):
        return '{"verdict": "CONSISTENT"}'

    decision_id, outcome = _event1_decision_id(
        verifier_bedrock=stubborn_model,
        safety_status_override="fail",
    )
    try:
        assert outcome["verifier"]["verdict"] == "FLAGGED"
        assert outcome["decision_snapshot"]["status"] == "proposed"
        assert outcome["decision_snapshot"]["recommendation"] is not None
        # tidak ada PO untuk decision yang di-flag
        assert _po_rows(decision_id) == []
    finally:
        _cleanup(decision_id, [])


def test_event1_e2e_approval_boundary_blocked_paths(client):
    """bgn_monitor 403; expired → execute diblokir 409."""
    head = _mk_user("sppg_head", "Jakarta")
    # bgn_monitor tidak boleh punya location (check_user_role_location_scope)
    mon = _mk_user("bgn_monitor", None)
    decision_id, _ = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={
                "decision_id": decision_id,
                "material_number": "MAT-TELUR",
                "supplier_id": None,
            },
            headers=_login(client, head),
        )
        # bgn_monitor tidak bisa approve (403)
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, mon),
        )
        assert resp.status_code == 403
        # bgn_monitor tidak bisa execute (403)
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, mon),
        )
        assert resp.status_code == 403
        # expired → execute diblokir (409)
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
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
    finally:
        _cleanup(decision_id, [head["email"], mon["email"]])


def test_event1_e2e_verifier_unavailable_dual_approval(client):
    """dual AND tetap wajib: 1 approval tidak cukup (409).

    Sejak audit M1, verify UNAVAILABLE tidak membuka approval sama sekali, jadi
    verdict dicatat lebih dulu lewat /actions/verify dengan provider uji — yang
    diuji di sini adalah kuorum dua peran, bukan jalur verifikasi.
    """
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id, _ = _event1_decision_id()
    try:
        client.post(
            "/actions/propose",
            json={
                "decision_id": decision_id,
                "material_number": "MAT-TELUR",
                "supplier_id": None,
            },
            headers=_login(client, head),
        )
        restore = _force_server_verdict("CONSISTENT", "uji kuorum")
        try:
            resp = client.post(
                "/actions/verify",
                json={"decision_id": decision_id},
                headers=_login(client, head),
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["recorded"] is True, resp.text
        finally:
            restore()
        # HANYA head approve → execute HARUS ditolak (dual AND)
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
        # KEDUA role approve → execute sukses + PO mock
        for user in (head, nut):
            client.post(
                "/actions/approve",
                json={"decision_id": decision_id, "approved": True},
                headers=_login(client, user),
            )
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200
        assert resp.json()["data_source"] == "MOCK"
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])
