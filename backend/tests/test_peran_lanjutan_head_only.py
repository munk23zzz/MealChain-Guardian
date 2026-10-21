"""Lanjutan kebijakan peran (PLAN.md §13) — usul, pemicu event, dan pemulihan.

Keputusan owner 2026-10-17 (lanjutan):
- `POST /decisions` = mengusulkan keputusan operasional → Head saja.
- Pemicu yang MEMBUAT keputusan operasional (`/events/*`, `/demo/event1`) → Head saja.
- `restore` supplier exclusion = tindakan tata kelola → Head saja.
- Alat data (`/demo/seed`, `/demo/timeseries`, `/demo/refresh`) TETAP dua role:
  itu penyiapan data demo, bukan usul keputusan.

Metode bukti: body sengaja tidak valid. Dependency `require_roles` dinilai
sebelum validasi body → **403 = diblokir**, **422 = lolos gerbang**. Untuk
`POST /decisions` (penjaga di dalam handler) dipakai body valid supaya 403
benar-benar dari pemeriksaan peran, bukan dari validasi.
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC
PW = "RahasiaUji#2026"

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
    # Domain unik: fixture sesi lain menyapu `%@test.local` di tengah run.
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-peran.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name is not None:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"), {"n": location_name}
                ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (:i, :n, :e, :p, :r, :l)"
                ),
                {
                    "i": user_id,
                    "n": f"uji-{role}",
                    "e": email,
                    "p": digest,
                    "r": role,
                    "l": loc_id,
                },
            )
    finally:
        engine.dispose()
    return {"id": user_id, "email": email, "password": PW, "role": role}


def _login(client, user) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _hapus(users: list[dict], decisions: list[str] | None = None) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            for did in decisions or []:
                for tabel in (
                    "sap_mock_purchase_orders",
                    "decision_evidence",
                    "approvals",
                    "agent_traces",
                ):
                    conn.execute(
                        text(f"DELETE FROM {tabel} WHERE decision_id = :d"), {"d": did}
                    )
                conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": did})
            for u in users:
                conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": u["id"]})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------
# 1. POST /decisions — draf keputusan operasional = usul → Head saja
# --------------------------------------------------------------------------


def test_nutritionist_tidak_boleh_membuat_keputusan(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post(
            "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, nut)
        )
        assert resp.status_code == 403, resp.text
        assert "role" in resp.json()["detail"].lower()
    finally:
        _hapus([nut])


def test_head_tetap_boleh_membuat_keputusan(client):
    head = _mk_user("sppg_head", "Jakarta")
    did = None
    try:
        resp = client.post(
            "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, head)
        )
        assert resp.status_code == 201, resp.text
        did = resp.json()["decision_id"]
    finally:
        _hapus([head], [did] if did else [])


def test_monitor_tetap_ditolak_membuat_keputusan(client):
    mon = _mk_user("bgn_monitor")
    try:
        resp = client.post(
            "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, mon)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _hapus([mon])


# --------------------------------------------------------------------------
# 2. Pemicu event yang MEMBUAT keputusan operasional → Head saja
# --------------------------------------------------------------------------


def test_nutritionist_tidak_boleh_memicu_event_safety(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post(
            "/events/safety-disruption", json={}, headers=_login(client, nut)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _hapus([nut])


def test_head_lolos_gerbang_event_safety(client):
    head = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.post(
            "/events/safety-disruption", json={}, headers=_login(client, head)
        )
        assert resp.status_code != 403, resp.text
        assert resp.status_code == 422, "body kosong harus ditolak validasi, bukan peran"
    finally:
        _hapus([head])


def test_nutritionist_tidak_boleh_memicu_event_harga(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post("/events/price-anomaly", json={}, headers=_login(client, nut))
        assert resp.status_code == 403, resp.text
    finally:
        _hapus([nut])


def test_nutritionist_tidak_boleh_menjalankan_event1(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post("/demo/event1", json={}, headers=_login(client, nut))
        assert resp.status_code == 403, resp.text
    finally:
        _hapus([nut])


def test_head_lolos_gerbang_event1(client):
    head = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.post("/demo/event1", json={}, headers=_login(client, head))
        assert resp.status_code == 422, resp.text
    finally:
        _hapus([head])


# --------------------------------------------------------------------------
# 3. Pemulihan supplier exclusion = tata kelola → Head saja
# --------------------------------------------------------------------------


def test_nutritionist_tidak_boleh_memulihkan_supplier(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post(
            f"/supplier-exclusions/{uuid.uuid4()}/restore",
            json={},
            headers=_login(client, nut),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _hapus([nut])


def test_head_lolos_gerbang_pemulihan_supplier(client):
    head = _mk_user("sppg_head", "Jakarta")
    try:
        resp = client.post(
            f"/supplier-exclusions/{uuid.uuid4()}/restore",
            json={},
            headers=_login(client, head),
        )
        assert resp.status_code != 403, resp.text
    finally:
        _hapus([head])


# --------------------------------------------------------------------------
# 4. Alat data demo TETAP dua role (bukan usul keputusan)
# --------------------------------------------------------------------------


def test_nutritionist_tetap_boleh_seed_demo(client):
    nut = _mk_user("sppg_nutritionist", "Jakarta")
    try:
        resp = client.post("/demo/seed", json={"force": "bukan-bool"}, headers=_login(client, nut))
        assert resp.status_code == 422, "seed demo tetap lolos gerbang peran"
    finally:
        _hapus([nut])
