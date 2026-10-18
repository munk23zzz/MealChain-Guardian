"""P4 — daftar keputusan harus memberi tahu mana yang punya review 7 agen.

Kenapa di backend: frontend tidak boleh menebak dengan mengambil trace satu per
satu (N permintaan) atau menandai semua keputusan "punya review". Fakta ini lahir
dari data (`agent_traces` dengan `agent_name` terisi), jadi produsen yang
menghitungnya — konsumen hanya membaca.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DSN = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
PW = "TestPass#2026"


def _mk_user(email: str) -> None:
    from bcrypt import gensalt, hashpw

    engine = create_engine(DSN)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), 'Review Reader', :e, :h, 'bgn_monitor', NULL)"
                ),
                {"e": email, "h": hashpw(PW.encode(), gensalt()).decode()},
            )
    finally:
        engine.dispose()


def _hapus(email: str) -> None:
    engine = create_engine(DSN)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _id_dengan_review() -> str:
    engine = create_engine(DSN)
    try:
        with engine.connect() as conn:
            return str(
                conn.execute(
                    text(
                        "SELECT decision_id FROM agent_traces WHERE agent_name IS NOT NULL "
                        "LIMIT 1"
                    )
                ).scalar_one()
            )
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_daftar_keputusan_membawa_has_agent_review(client):
    email = f"review-{uuid.uuid4().hex[:8]}@test.local"
    _mk_user(email)
    try:
        login = client.post("/auth/login", json={"email": email, "password": PW})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get("/decisions", headers=headers)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items, "tidak ada keputusan untuk diuji"
        id_review = _id_dengan_review()

        for item in items:
            assert "has_agent_review" in item, item["decision_id"]
            assert isinstance(item["has_agent_review"], bool)

        baris = next(i for i in items if i["decision_id"] == id_review)
        assert baris["has_agent_review"] is True

        # Kontrol negatif: keputusan tanpa satu pun baris worker harus False.
        tanpa = [i for i in items if i["decision_id"] != id_review]
        if tanpa:
            assert any(i["has_agent_review"] is False for i in tanpa)
    finally:
        _hapus(email)
