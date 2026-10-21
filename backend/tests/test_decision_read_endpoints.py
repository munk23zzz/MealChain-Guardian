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
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
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
    """Buat decision target Jakarta via API — kontrak baru S4-00: butuh
    JWT sppg_head; target lokasi = lokasi user pembuat (Jakarta)."""
    from tests.test_actions import _login, _mk_user

    with TestClient(app) as c:
        user = _mk_user("sppg_head", "Jakarta")
        resp = c.post(
            "/decisions",
            json={"recommendation": RECOMMENDATION},
            headers=_login(c, user),
        )
        assert resp.status_code == 201, resp.text
        decision_id = resp.json()["decision_id"]
    _drop_user_quiet(user["email"])
    return decision_id


def _drop_user_quiet(email: str) -> None:
    from tests.test_actions import _drop_user

    try:
        _drop_user(email)
    except Exception:
        pass


def _authed_headers(client) -> dict:
    """Login sppg_head (role pembaca feed) — untuk test baca terautentikasi."""
    from tests.test_actions import _login, _mk_user

    user = _mk_user("sppg_head", "Jakarta")
    return _login(client, user)


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
        resp = client.get("/decisions", headers=_authed_headers(client))
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
        resp = client.get(
            f"/decisions/{decision_id}/traces", headers=_authed_headers(client)
        )
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
            # P5: field worker selalu ada di kontrak, NULL untuk trace lama.
            for field in (
                "duration_ms",
                "run_id",
                "agent_name",
                "confidence",
                "citations",
            ):
                assert field in s
            assert s["run_id"] is None
            assert s["agent_name"] is None

        # P5: serializer mengirim metadata worker yang tersimpan.
        run_id = str(uuid.uuid4())
        engine = create_engine(DB_URL)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE agent_traces SET run_id = :r, agent_name = 'supply', "
                    "duration_ms = 1234, confidence = 0.9, "
                    "citations = CAST(:c AS jsonb) "
                    "WHERE decision_id = :d AND step_name = 'DETECT'"
                ),
                {
                    "r": run_id,
                    "c": '[{"source": "/balance/Jakarta/telur", "claim": "supply_kg"}]',
                    "d": decision_id,
                },
            )
        engine.dispose()
        lagi = client.get(
            f"/decisions/{decision_id}/traces", headers=_authed_headers(client)
        ).json()["steps"]
        detect = next(s for s in lagi if s["step_name"] == "DETECT")
        assert detect["run_id"] == run_id
        assert detect["agent_name"] == "supply"
        assert detect["duration_ms"] == 1234
        assert detect["confidence"] == 0.9
        assert detect["citations"][0]["claim"] == "supply_kg"
    finally:
        _cleanup(decision_id)


def test_get_decision_traces_404_unknown(client):
    """Unknown id → 404 (auth dicek lebih dulu oleh dependency; keduanya valid,
    urutan FastAPI menempatkan auth sebelum handler)."""
    resp = client.get(
        f"/decisions/{uuid.uuid4()}/traces", headers=_authed_headers(client)
    )
    assert resp.status_code == 404


def test_decision_read_endpoints_require_auth(client):
    """S3-15: endpoint baca S3-12 diproteksi — unauth = 401."""
    resp = client.get("/decisions")
    assert resp.status_code == 401
    resp = client.get(f"/decisions/{uuid.uuid4()}/traces")
    assert resp.status_code == 401


def _mk_auth_headers(client) -> dict:
    from tests.test_actions import _login, _mk_user

    user = _mk_user("sppg_head", "Jakarta")
    return _login(client, user), user
