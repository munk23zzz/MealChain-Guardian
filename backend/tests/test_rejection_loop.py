"""Test rejection loop (TDD, permintaan Roy 2026-10-07).

Siklus demo: rekomendasi ditolak DENGAN ALASAN → agent re-propose
(iterasi baru, terhubung ke keputusan lama) → timeline v1→v2→v3.
Alasan penolakan wajib — tanpa alasan agent tidak bisa belajar.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

PW = "TestPass#2026"


def _db():
    return create_engine(DB_URL)


def _mk_user(role: str, location_name: str = "Jakarta") -> dict:
    engine = _db()
    user_id = str(uuid.uuid4())
    email = f"{role}-{uuid.uuid4().hex[:8]}@test.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"),
                    {"n": location_name},
                ).scalar_one_or_none()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (:id, :n, :e, :h, :r, :l)"
                ),
                {"id": user_id, "n": f"T {role}", "e": email, "h": digest, "r": role, "l": loc_id},
            )
        return {"id": user_id, "email": email, "password": PW, "role": role}
    finally:
        engine.dispose()


def _drop_user(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


RECOMMENDATION = {
    "candidate": {
        "source_location": "Cianjur",
        "destination_location": "Jakarta",
        "commodity": "telur",
        "quantity_kg": "600",
    },
    "safe_delivered_cost": "16206000",
    "cost_breakdown": {"purchase": "15720000"},
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _mk_decision(client) -> str:
    resp = client.post("/decisions", json={"recommendation": RECOMMENDATION})
    assert resp.status_code == 201, resp.text
    return resp.json()["decision_id"]


def _cleanup(decision_ids: list[str], emails: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            for did in decision_ids:
                conn.execute(
                    text("DELETE FROM decisions WHERE id = :d"), {"d": did}
                )
            for e in emails:
                conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": e})
    finally:
        engine.dispose()


def _login(client, user: dict) -> dict:
    resp = client.post(
        "/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _to_pending(client, decision_id: str, user: dict) -> None:
    resp = client.post(
        "/actions/propose",
        json={"decision_id": decision_id, "material_number": "MAT-TELUR"},
        headers=_login(client, user),
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------- d2: alasan wajib
def test_reject_without_reason_ditolak_422(client):
    user = _mk_user("sppg_head")
    did = _mk_decision(client)
    try:
        _to_pending(client, did, user)
        resp = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": False},
            headers=_login(client, user),
        )
        assert resp.status_code == 422
        assert "alasan" in resp.json()["detail"].lower()
    finally:
        _cleanup([did], [user["email"]])


def test_reject_dengan_alasan_tersimpan(client):
    user = _mk_user("sppg_head")
    did = _mk_decision(client)
    try:
        _to_pending(client, did, user)
        resp = client.post(
            "/actions/approve",
            json={
                "decision_id": did,
                "approved": False,
                "comment": "Kuota SPPG Jakarta penuh minggu ini",
            },
            headers=_login(client, user),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_status"] == "rejected"
        detail = client.get(f"/decisions/{did}").json()
        assert detail["rejection_reason"] == "Kuota SPPG Jakarta penuh minggu ini"
    finally:
        _cleanup([did], [user["email"]])


# ---------------------------------------------------------------- d3: re-propose
def test_repropose_rejected_membuat_iterasi_baru(client):
    user = _mk_user("sppg_head")
    v1 = _mk_decision(client)
    try:
        _to_pending(client, v1, user)
        client.post(
            "/actions/approve",
            json={
                "decision_id": v1,
                "approved": False,
                "comment": "Kuota SPPG Jakarta penuh minggu ini",
            },
            headers=_login(client, user),
        )
        resp = client.post(
            "/actions/repropose",
            json={"decision_id": v1},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["decision_id"] != v1
        assert body["status"] == "proposed"
        assert body["iteration"] == 2
        assert body["supersedes_id"] == v1
        assert body["parent_rejection_reason"] == "Kuota SPPG Jakarta penuh minggu ini"
    finally:
        _cleanup([v1], [user["email"]])


def test_repropose_non_rejected_ditolak_409(client):
    did = _mk_decision(client)
    try:
        resp = client.post("/actions/repropose", json={"decision_id": did})
        assert resp.status_code == 409
    finally:
        _cleanup([did], [])


def test_chain_endpoint_urut_iterasi(client):
    user = _mk_user("sppg_head")
    v1 = _mk_decision(client)
    try:
        _to_pending(client, v1, user)
        client.post(
            "/actions/approve",
            json={
                "decision_id": v1,
                "approved": False,
                "comment": "Harga supplier tidak masuk akal",
            },
            headers=_login(client, user),
        )
        v2 = client.post("/actions/repropose", json={"decision_id": v1}).json()[
            "decision_id"
        ]
        chain = client.get(
            f"/decisions/{v2}/chain", headers=_login(client, user)
        ).json()["chain"]
        assert [c["iteration"] for c in chain] == [1, 2]
        assert chain[0]["status"] == "rejected"
        assert chain[0]["rejection_reason"] == "Harga supplier tidak masuk akal"
        assert chain[1]["decision_id"] == v2
        assert chain[1]["status"] == "proposed"
    finally:
        _cleanup([v1, v2], [user["email"]])


def test_repropose_menulis_trace_learn(client):
    user = _mk_user("sppg_head")
    v1 = _mk_decision(client)
    try:
        _to_pending(client, v1, user)
        client.post(
            "/actions/approve",
            json={
                "decision_id": v1,
                "approved": False,
                "comment": "Kesegaran batch tidak memenuhi 0,85",
            },
            headers=_login(client, user),
        )
        v2 = client.post("/actions/repropose", json={"decision_id": v1}).json()[
            "decision_id"
        ]
        traces = client.get(
            f"/decisions/{v2}/traces", headers=_login(client, user)
        ).json()["steps"]
        learn = [s for s in traces if s["step_name"] == "LEARN"]
        assert learn, "iterasi baru wajib punya langkah LEARN (bahan memory agent)"
        out = learn[0]["output_summary"] or {}
        assert out.get("parent_rejection_reason") == (
            "Kesegaran batch tidak memenuhi 0,85"
        )
    finally:
        _cleanup([v1, v2], [user["email"]])


def test_list_decisions_memuat_iterasi_dan_alasan(client):
    user = _mk_user("sppg_head")
    did = _mk_decision(client)
    try:
        items = client.get(
            "/decisions", headers=_login(client, user)
        ).json()["items"]
        row = [i for i in items if i["decision_id"] == did][0]
        assert row["iteration"] == 1
        assert row["rejection_reason"] is None
        assert row["supersedes_id"] is None
    finally:
        _cleanup([did], [])
