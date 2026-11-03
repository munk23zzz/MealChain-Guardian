"""Kebijakan peran final (PLAN.md §13.1/§13.3) — tes penegakan.

Yang diuji:
1. Nutritionist TIDAK boleh propose, repropose, execute (403).
2. Nutritionist TETAP boleh verify dan approve (approval kedua).
3. Keputusan operasional wajib 2 approval dari dua role; tipe administrasi
   (supplier_exclusion*) tetap mengikuti verdict verifier.
4. Monitor (tata kelola) TIDAK boleh mengubah perannya sendiri, tetapi tetap
   boleh mengubah peran/penugasan pengguna lain.
5. Proposal supplier exclusion milik Head saja.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import _requirement_for
from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")

PW = "TestPass#2026"

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


def _db():
    return create_engine(DB_URL)


def _mk_user(role: str, location_name: str | None = None) -> dict:
    engine = _db()
    user_id = str(uuid.uuid4())
    # Domain SENGAJA bukan test.local: fixture sesi lain menyapu akun
    # `%@test.local` di tengah run, dan akun tes ini harus bertahan sampai selesai.
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-peran.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"), {"n": location_name}
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


def _cleanup(decision_id: str | None, emails: list[str]) -> None:
    engine = _db()
    try:
        if decision_id:
            with engine.begin() as conn:
                for tabel in (
                    "sap_mock_purchase_orders",
                    "decision_evidence",
                    "approvals",
                    "agent_traces",
                ):
                    conn.execute(
                        text(f"DELETE FROM {tabel} WHERE decision_id = :d"), {"d": decision_id}
                    )
                conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
    finally:
        engine.dispose()
    for email in emails:
        _drop_user(email)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client, user) -> dict:
    resp = client.post("/auth/login", json={"email": user["email"], "password": user["password"]})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _mk_decision(client, head) -> str:
    resp = client.post(
        "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, head)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["decision_id"]


# ---------- 1. Nutritionist tidak boleh propose / repropose / execute ----------


def test_nutritionist_tidak_boleh_propose(client):
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        decision_id = _mk_decision(client, head)
        resp = client.post(
            "/actions/propose", json={"decision_id": decision_id}, headers=_login(client, nut)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])


def test_nutritionist_tidak_boleh_repropose(client):
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        decision_id = _mk_decision(client, head)
        resp = client.post(
            "/actions/repropose", json={"decision_id": decision_id}, headers=_login(client, nut)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])


def test_nutritionist_tidak_boleh_execute(client):
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        decision_id = _mk_decision(client, head)
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id}, headers=_login(client, nut)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])


# ---------- 2. Head tetap boleh propose; Nutritionist tetap boleh verify ----------


def test_head_tetap_boleh_propose(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = None
    try:
        decision_id = _mk_decision(client, head)
        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MC-TEST-01"},
            headers=_login(client, head),
        )
        assert resp.status_code == 201, resp.text
    finally:
        _cleanup(decision_id, [head["email"]])


def test_nutritionist_tetap_lolos_gerbang_verify(client):
    head = _mk_user("sppg_head", "Jakarta")
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = None
    try:
        decision_id = _mk_decision(client, head)
        resp = client.post(
            "/actions/verify", json={"decision_id": decision_id}, headers=_login(client, nut)
        )
        assert resp.status_code != 403, f"nutritionist harus tetap boleh verify: {resp.text}"
    finally:
        _cleanup(decision_id, [head["email"], nut["email"]])


# ---------- 3. Requirement approval: operasional wajib dua role ----------


class _Keputusan:
    def __init__(self, decision_type: str, verdict: str | None = "consistent"):
        self.decision_type = decision_type
        self.verifier_note = verdict


def test_keputusan_operasional_wajib_dua_role_meski_consistent():
    req = _requirement_for(_Keputusan("regional_balance", "consistent"))
    assert req["min_approvals"] == 2
    assert len(req["required_roles"]) == 2


def test_keputusan_administrasi_tetap_ikut_verdict():
    req = _requirement_for(_Keputusan("supplier_exclusion", "consistent"))
    assert req["min_approvals"] == 1


# ---------- 4. Monitor: boleh tata kelola, tidak boleh ubah perannya sendiri ----------


def test_monitor_tidak_boleh_ubah_peran_sendiri(client):
    monitor = _mk_user("bgn_monitor")
    another = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.patch(
            f"/admin/users/{monitor['id']}",
            json={"role": "sppg_head", "location_id": None},
            headers=_login(client, monitor),
        )
        assert resp.status_code == 422, resp.text
        assert "sendiri" in resp.json()["detail"].lower()
    finally:
        _drop_user(monitor["email"])
        _drop_user(another["email"])


def test_monitor_tetap_boleh_atasi_pengguna_lain(client):
    monitor = _mk_user("bgn_monitor")
    target = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.patch(
            f"/admin/users/{target['id']}",
            json={"role": "sppg_nutritionist"},
            headers=_login(client, monitor),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user"]["role"] == "sppg_nutritionist"
    finally:
        _drop_user(monitor["email"])
        _drop_user(target["email"])


# ---------- 5. Proposal supplier exclusion milik Head saja ----------


def test_nutritionist_tidak_boleh_usul_supplier_exclusion(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post(
            "/supplier-exclusions/proposals",
            json={
                "supplier_id": str(uuid.uuid4()),
                "reason": "uji peran",
                "target_location_id": None,
            },
            headers=_login(client, nut),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _drop_user(nut["email"])
