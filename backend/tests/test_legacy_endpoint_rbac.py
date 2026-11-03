"""RBAC endpoint lama Sprint 1/2 (residual debt — arah Roy 2026-10-08).

Kontrak:
- Architecture.md §232: "Semua endpoint backend butuh JWT valid" — termasuk
  endpoint legacy supply/demand/forecast/freshness/safety/price/logistics/
  balance/cost/evidence yang selama ini terbuka.
- PRD §77: bgn_monitor read-only → endpoint mutasi (POST) ditolak 403;
  endpoint baca boleh lintas lokasi (Schema.md: location NULL = semua lokasi).
- Token garbage → 401 (guard memvalidasi JWT, bukan sekadar kehadiran header).
- Role sah → lewat guard (200 pada endpoint murni-komputasi; 404 pada data
  yang memang tidak ada = bukan penolakan auth).

TDD RED: test ini ditulis SEBELUM guard dipasang — endpoint legacy saat ini
mengembalikan 200/404 tanpa token. Tanpa mengubah architecture/domain logic:
hanya dependency auth yang ditambahkan.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC


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


def _login(client, email: str, pw: str) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# 13 endpoint legacy Sprint 1/2 (body valid — satu-satunya variabel adalah auth).
# GET (baca):
GET_PATHS = [
    "/supply/Jakarta/telur",
    "/demand/Jakarta/telur",
    "/demand/forecast/Jakarta/telur",
    "/balance/Jakarta/telur",
    "/price/Jakarta/telur",
]
# POST (mutasi/komputasi):
POST_CASES = [
    ("/freshness/evaluate", {"batch_id": "00000000-0000-0000-0000-000000000000"}),
    ("/safety/evaluate", {"batch_id": "00000000-0000-0000-0000-000000000000"}),
    ("/logistics/estimate", {"source": "Bogor", "target": "Jakarta", "quantity_kg": 100}),
    (
        "/cost/safe-delivered",
        {"purchase_cost": "100000", "freshness_score": "0.9", "safety_status": "pass"},
    ),
    (
        "/evidence/fuse",
        {"recommendation": {"candidate": {"a": 1}, "evidence": {"batch_ids": ["b1"]}}},
    ),
    ("/balance/recommend", None),
    ("/balance/analyze", None),
]


def test_semua_endpoint_legacy_menolak_tanpa_token_401(client):
    for path in GET_PATHS:
        assert client.get(path).status_code == 401, path
    for path, body in POST_CASES:
        assert client.post(path, json=body).status_code == 401, path


def test_token_garbage_ditolak_401(client):
    bad = {"Authorization": "Bearer bukan-jwt"}
    get_no_auth = client.get("/balance/Jakarta/telur", headers=bad)
    post_no_auth = client.post("/logistics/estimate", json=_LOGISTICS_BODY_SMALL, headers=bad)
    assert get_no_auth.status_code == 401
    assert post_no_auth.status_code == 401


def test_bgn_monitor_baca_semua_lokasi_200(client):
    email = f"bgn-{uuid.uuid4().hex[:8]}@test.local"
    _, email, pw = _mk_user(email, "bgn_monitor", None)
    try:
        headers = _login(client, email, pw)
        for path in GET_PATHS:
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, f"{path} → {resp.status_code}"
    finally:
        _cleanup_user(email)


def test_bgn_monitor_mutasi_ditolak_403(client):
    """POST yang MENULIS tetap ditolak untuk peran baca.

    Catatan perubahan (P2, 18 Okt): `/price/deviation` dikeluarkan dari daftar ini
    karena endpoint itu komputasi murni (baca satu baris harga referensi + hitung,
    tanpa tulisan apa pun). Menjaganya dengan MUTATING_ROLES membuat worker Price
    milik agent read-only selalu 403 → review jadi `partial` tanpa data yang
    dilindungi. Perilaku barunya diuji di `test_price_deviation_readonly.py`,
    termasuk kontrol bahwa `/safety/evaluate` (yang menulis) tetap 403.
    """
    email = f"bgn-{uuid.uuid4().hex[:8]}@test.local"
    _, email, pw = _mk_user(email, "bgn_monitor", None)
    try:
        headers = _login(client, email, pw)
        for path, body in POST_CASES:
            resp = client.post(path, json=body, headers=headers)
            assert resp.status_code == 403, f"{path} → {resp.status_code}"
    finally:
        _cleanup_user(email)


_LOGISTICS_BODY = {"source": "Bogor", "target": "Jakarta", "quantity_kg": 100}
_LOGISTICS_BODY_SMALL = {"source": "Bogor", "target": "Jakarta", "quantity_kg": 1}
_SDC_BODY = {
    "purchase_cost": "100000",
    "freshness_score": "0.9",
    "safety_status": "pass",
    # Sejak 29 Okt 2026 susut gudang dihitung dari umur simpan + lama simpan,
    # jadi komoditas (atau shelf_life_days) wajib disebut. Kesegaran tidak lagi
    # menjadi pengali susut.
    "commodity": "telur",
}


def test_role_sppg_head_lewat_guard(client):
    """Role sah: guard lolos — endpoint komputasi murni 200, data tak ada → 404."""
    email = f"head-{uuid.uuid4().hex[:8]}@test.local"
    _, email, pw = _mk_user(email, "sppg_head", "Jakarta")
    try:
        headers = _login(client, email, pw)
        assert client.get("/balance/Jakarta/telur", headers=headers).status_code == 200
        logistics_ok = client.post("/logistics/estimate", json=_LOGISTICS_BODY, headers=headers)
        sdc_ok = client.post("/cost/safe-delivered", json=_SDC_BODY, headers=headers)
        assert logistics_ok.status_code == 200
        assert sdc_ok.status_code == 200
        resp = client.post(
            "/freshness/evaluate",
            json={"batch_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert resp.status_code == 404, resp.status_code  # auth lolos, data memang tak ada
    finally:
        _cleanup_user(email)
