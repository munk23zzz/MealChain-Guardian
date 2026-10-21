"""Test auth JWT + RBAC dasar (S3-01, TDD).

Skenario:
- POST /auth/login kredensial demo valid → 200 + access_token + role.
- POST /auth/login password salah → 401.
- GET /auth/me tanpa token → 401; dengan token valid → profil user.
- Token kadaluarsa/garbage → 401.

User test dibuat sendiri (bcrypt hash asli) dan dibersihkan di finally —
tidak bergantung pada seed demo.
"""

import uuid

import bcrypt
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
).replace("+asyncpg", "+psycopg")


def _db():
    return create_engine(DB_URL)


def _mk_user(email: str, role: str, location_name: str | None):
    engine = _db()
    user_id = str(uuid.uuid4())
    pw = "TestPass#2026"
    digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name is not None:
                row = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"),
                    {"n": location_name},
                ).scalar_one_or_none()
                loc_id = str(row) if row else None
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (:id, :name, :email, :hash, :role, :loc)"
                ),
                {
                    "id": user_id,
                    "name": f"Test {role}",
                    "email": email,
                    "hash": digest,
                    "role": role,
                    "loc": loc_id,
                },
            )
        return user_id, email, pw
    finally:
        engine.dispose()


def _cleanup_user(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_login_valid_credentials_returns_jwt_with_role(client):
    _, email, pw = _mk_user(
        f"head-{uuid.uuid4().hex[:8]}@test.local", "sppg_head", "Jakarta"
    )
    try:
        resp = client.post(
            "/auth/login", json={"email": email, "password": pw}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["role"] == "sppg_head"
        assert body["access_token"]
        # Token harus ter-decode dan membawa sub (user id) + role
        claims = pyjwt.decode(
            body["access_token"],
            options={"verify_signature": False},
        )
        assert claims["role"] == "sppg_head"
        assert claims["sub"]
    finally:
        _cleanup_user(email)


def test_login_wrong_password_returns_401(client):
    _, email, pw = _mk_user(
        f"nut-{uuid.uuid4().hex[:8]}@test.local", "sppg_nutritionist", "Bogor"
    )
    try:
        resp = client.post(
            "/auth/login", json={"email": email, "password": pw + "x"}
        )
        assert resp.status_code == 401
    finally:
        _cleanup_user(email)


def test_login_unknown_email_returns_401(client):
    resp = client.post(
        "/auth/login",
        json={"email": f"ghost-{uuid.uuid4().hex[:8]}@test.local", "password": "x"},
    )
    assert resp.status_code == 401


def test_auth_me_requires_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_auth_me_with_valid_token_returns_profile(client):
    user_id, email, pw = _mk_user(
        f"mon-{uuid.uuid4().hex[:8]}@test.local", "bgn_monitor", None
    )
    try:
        token = client.post(
            "/auth/login", json={"email": email, "password": pw}
        ).json()["access_token"]
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["email"] == email
        assert body["role"] == "bgn_monitor"
        assert body["location_name"] is None
    finally:
        _cleanup_user(email)


def test_auth_me_with_garbage_token_returns_401(client):
    resp = client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401


def test_auth_me_with_tampered_signature_returns_401(client):
    user_id, email, pw = _mk_user(
        f"head2-{uuid.uuid4().hex[:8]}@test.local", "sppg_head", "Jakarta"
    )
    try:
        token = client.post(
            "/auth/login", json={"email": email, "password": pw}
        ).json()["access_token"]
        # Token dengan signature lain (secret beda) harus ditolak
        forged = pyjwt.encode(
            {"sub": user_id, "role": "sppg_head"}, "other-secret", algorithm="HS256"
        )
        assert forged != token
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401
    finally:
        _cleanup_user(email)
