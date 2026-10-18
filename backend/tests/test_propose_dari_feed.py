"""Ajukan keputusan `proposed` untuk persetujuan (Fase 0 butir 1, 18 Okt 2026).

Masalah yang ditutup: Event 1/2/3 dan `POST /decisions` melahirkan keputusan
berstatus `proposed`, tetapi satu-satunya jalan ke `pending_approval` adalah
`POST /actions/propose` — dan UI tidak pernah menawarkannya untuk keputusan
yang sudah ada. Hasilnya keputusan berhenti permanen (audit BLOCKER A1).

Karena UI tidak tahu `material_number` (dulu WAJIB di payload), endpoint ini
kini menurunkannya dari komoditas keputusan: `MAT-<KOMODITAS>`. Nilai eksplisit
tetap dihormati supaya pemanggil lama (Demo Control) tidak berubah perilaku.

Yang dipaku:
1. `POST /actions/propose` hanya dengan `decision_id` → 201, status berpindah
   ke `pending_approval`, `material_number` terisi turunan (bukan kosong).
2. `material_number` eksplisit tetap dipakai apa adanya.
3. Ahli Gizi tetap 403 (propose milik Kepala SPPG).
4. Keputusan yang sudah `pending_approval` tetap 409 (tidak bisa diajukan dua kali).
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


def _mk_user(role: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@propose-feed.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    engine = _db()
    try:
        with engine.begin() as conn:
            loc = conn.execute(
                text("SELECT id FROM locations WHERE name = 'Jakarta'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l)"
                ),
                {"n": f"T {role}", "e": email, "h": digest, "r": role, "l": loc},
            )
        return {"email": email, "password": PW}
    finally:
        engine.dispose()


def _drop(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _status(decision_id: str) -> str:
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"), {"d": decision_id}
            ).scalar_one()
    finally:
        engine.dispose()


def _cleanup(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _buat_keputusan(client, kepala) -> str:
    resp = client.post(
        "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, kepala)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["decision_id"]


def test_ajukan_tanpa_material_number_menurunkan_dari_komoditas(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _buat_keputusan(client, kepala)
        assert _status(did) == "proposed"
        resp = client.post(
            "/actions/propose",
            json={"decision_id": did},
            headers=_login(client, kepala),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "pending_approval"
        assert body["material_number"] == "MAT-TELUR", body
        assert _status(did) == "pending_approval"
    finally:
        _cleanup(did)
        _drop(kepala["email"])


def test_material_number_eksplisit_tetap_dihormati(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _buat_keputusan(client, kepala)
        resp = client.post(
            "/actions/propose",
            json={"decision_id": did, "material_number": "MAT-KHUSUS-01"},
            headers=_login(client, kepala),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["material_number"] == "MAT-KHUSUS-01"
    finally:
        _cleanup(did)
        _drop(kepala["email"])


def test_ahli_gizi_tetap_tidak_boleh_mengajukan(client):
    kepala = _mk_user("sppg_head")
    gizi = _mk_user("sppg_nutritionist")
    did = None
    try:
        did = _buat_keputusan(client, kepala)
        resp = client.post(
            "/actions/propose",
            json={"decision_id": did},
            headers=_login(client, gizi),
        )
        assert resp.status_code == 403, resp.text
        assert _status(did) == "proposed"
    finally:
        _cleanup(did)
        _drop(kepala["email"])
        _drop(gizi["email"])


def test_ajukan_dua_kali_409(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _buat_keputusan(client, kepala)
        headers = _login(client, kepala)
        assert (
            client.post(
                "/actions/propose", json={"decision_id": did}, headers=headers
            ).status_code
            == 201
        )
        resp = client.post(
            "/actions/propose", json={"decision_id": did}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "tidak dapat dipropose" in resp.json()["detail"]
    finally:
        _cleanup(did)
        _drop(kepala["email"])
