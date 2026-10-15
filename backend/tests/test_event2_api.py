"""S4-01 bagian 3 — API /events/price-anomaly (RED dulu → GREEN).

Kontrak §11 + prompt Owner §8/9/15:
- 401 unauth; monitor 403 (mutating); location scope
- (Ruling 2026-10-14) target event = lokasi SPPG pemakai; quote tetap boleh
  berasal dari lokasi uji terisolasi (sisi SUMBER)
- 201 anomaly (decision_id, deviation_pct, classification, trace)
- 200 no-anomaly, decision_id null, TIDAK menulis decision
- replay key+payload sama → outcome sama (satu decision saja)
- key sama + quote beda → 409
- tanpa PO dalam semua kasus
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

MONITOR_EMAIL = "bgn.monitor@demo.local"


def _db_all(query: str, params: dict | None = None):
    """Query SELECT → list rows."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None):
    """DML (DELETE/UPDATE) tanpa rows."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# Password demo statis (seed_data.py DEMO_USERS; bukan secret produksi).
def _head_user(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


def _monitor_user(client: TestClient) -> dict:
    return _login(client, "bgn.monitor@demo.local", "Demo#BGN2026")


# ---------------------------------------------------------------------------
# Seed pair helper diimpor dari test_event2_service (reuse).
# ---------------------------------------------------------------------------
from tests.test_event2_service import mk_pair  # noqa: E402


def _sppg_target() -> str:
    """Lokasi TUJUAN event = SPPG pemakai (kepala demo di Jakarta).

    Ruling 2026-10-14 mengunci target ke lokasi SPPG sendiri, sedangkan
    `mk_pair` sengaja membuat lokasi uji terisolasi. Quote/pasokan tetap di
    lokasi itu (sisi SUMBER — tetap lintas lokasi), tetapi keputusannya harus
    menyasar SPPG pemakai.
    """
    return str(_db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0])


def test_api_price_anomaly_unauth_401(client, request):
    quote_id, _ref, _loc = mk_pair(request, "1.2")
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


def test_api_price_anomaly_monitor_403(client, request):
    quote_id, _ref, _loc = mk_pair(request, "1.2")
    headers = _monitor_user(client)
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_api_price_anomaly_anomaly_201(client, request):
    quote_id, ref_id, loc_id = mk_pair(request, "1.2")  # +20% anomalous
    headers = _head_user(client)
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["event_type"] == "price_anomaly"
    assert body["decision_id"]
    assert abs(float(body["deviation_pct"]) - 20.0) < 0.05
    assert body["classification"] == "anomalous"
    assert body["quote_id"] == quote_id
    assert body["reference_id"] == ref_id
    # Wording review, bukan tuduhan fraud (§16).
    assert "review required" in body["message"].lower()
    assert "fraud" not in body["message"].lower()
    # Decision benar terpersist sebagai price_anomaly.
    row = _db_all(
        "SELECT decision_type FROM decisions WHERE id = :d",
        {"d": body["decision_id"]},
    )
    assert row and row[0][0] == "price_anomaly"
    # Bersihan: hapus decision test ini.
    _db_exec(
        "DELETE FROM decisions WHERE id = :d", {"d": body["decision_id"]}
    )


def test_api_price_anomaly_no_anomaly_200_no_write(client, request):
    quote_id, _ref, _loc = mk_pair(request, "1.025")  # +2.5% normal
    headers = _head_user(client)
    before = _db_all("SELECT count(*) FROM decisions")[0][0]
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision_id"] is None
    assert body["classification"] == "normal"
    after = _db_all("SELECT count(*) FROM decisions")[0][0]
    assert after == before  # TIDAK menulis decision (§11)


def test_api_price_anomaly_replay_idempotent(client, request):
    quote_id, _ref, _loc = mk_pair(request, "1.2")
    headers = _head_user(client)
    op_key = str(uuid.uuid4())
    payload = {
        "quote_id": quote_id,
        "target_location_id": _sppg_target(),
        "operation_key": op_key,
    }
    r1 = client.post("/events/price-anomaly", json=payload, headers=headers)
    assert r1.status_code == 201
    r2 = client.post("/events/price-anomaly", json=payload, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.json()["decision_id"] == r1.json()["decision_id"]
    # Tidak ada duplikat decision untuk operation_key ini.
    rows = _db_all(
        "SELECT count(*) FROM agent_traces t JOIN decisions d ON d.id=t.decision_id "
        "WHERE t.step_name='DETECT' AND t.input_summary->>'operation_key' = :k",
        {"k": op_key},
    )
    assert rows[0][0] == 1
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": r1.json()["decision_id"]})


def test_api_price_anomaly_key_reuse_other_quote_409(client, request):
    quote_id, _ref, _loc = mk_pair(request, "1.2")
    other_quote, _ref2, _loc2 = mk_pair(request, "1.3")
    headers = _head_user(client)
    op_key = str(uuid.uuid4())
    r1 = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": op_key,
        },
        headers=headers,
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": other_quote,
            "target_location_id": _sppg_target(),
            "operation_key": op_key,
        },
        headers=headers,
    )
    assert r2.status_code == 409
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": r1.json()["decision_id"]})


def test_api_price_anomaly_unknown_quote_404(client):
    headers = _head_user(client)
    loc_row = _db_all("SELECT id FROM locations WHERE name='Jakarta'")[0]
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": str(uuid.uuid4()),
            "target_location_id": str(loc_row[0]),
            "operation_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_api_price_anomaly_no_po_created(client, request):
    """Zero PO selama Event 2 review-only (ruling O-PO, §15–17)."""
    quote_id, _ref, _loc = mk_pair(request, "1.25")
    headers = _head_user(client)
    before = _db_all("SELECT count(*) FROM sap_mock_purchase_orders")[0][0]
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": _sppg_target(),
            "operation_key": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    after = _db_all("SELECT count(*) FROM sap_mock_purchase_orders")[0][0]
    assert after == before
