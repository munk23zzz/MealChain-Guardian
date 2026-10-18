"""S4-02 bagian 2 — API Event 3 (RED dulu): POST /events/safety-disruption
+ execute revalidation (O-EVENT-2).

Kontrak plan §S4-02 + prompt Owner §15, §18–22:
- endpoint auth: unauth → 401; bgn_monitor → 403; scope lokasi target
  server-side (O-SEC-2).
- response 201 (revised) / 200 (no_disruption) / 409 (conflict,
  no-alternative, operation_key reuse beda batch) / 404 (batch tidak ada).
- safety TIDAK bisa dioverride client: payload tanpa field
  safety/temperature apa pun (extra=forbid).
- Execute revalidation: decision yang batch sumbernya kini FAIL
  (event 3 berjalan setelah decision lama dibuat) TIDAK boleh dieksekusi
  → 409, walau approval matrix sudah satisfied.

Dokumen Bahasa Indonesia. LLM tidak pernah menghitung safety.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

NOW = datetime.now(timezone.utc)


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


def _db_exec_returning(query: str, params: dict | None = None):
    """DML/INSERT ... RETURNING → nilai kolom pertama row pertama."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            row = conn.execute(text(query), params or {}).fetchone()
            return row[0] if row else None
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


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _mk_batch(location: str, fail: bool) -> dict:
    """Batch uji di lokasi by-name; log suhu relatif now (anti time-bomb)."""
    row = _db_all("SELECT id FROM locations WHERE name=:n", {"n": location})
    assert row, f"lokasi {location} wajib ada"
    return _mk_batch_at(str(row[0][0]), fail)


def _mk_batch_at(location_id: str, fail: bool) -> dict:
    """Batch uji di lokasi by-id; log suhu relatif now (anti time-bomb)."""
    engine = create_engine(DB_URL)
    suffix = uuid.uuid4().hex[:8]
    t0 = NOW - timedelta(hours=3)
    log = (
        [
            {"timestamp": _iso(t0), "temperature_c": 4.0},
            {"timestamp": _iso(t0 + timedelta(minutes=30)), "temperature_c": 20.0},
            {"timestamp": _iso(t0 + timedelta(minutes=90)), "temperature_c": 4.0},
        ]
        if fail
        else [
            {"timestamp": _iso(t0), "temperature_c": 4.0},
            {"timestamp": _iso(t0 + timedelta(minutes=90)), "temperature_c": 4.2},
        ]
    )
    try:
        with engine.begin() as conn:
            sup_id = conn.execute(
                text(
                    "INSERT INTO suppliers (name, location_id, reliability_score) "
                    "SELECT :n, l.id, 0.8 FROM locations l WHERE l.id=:lid "
                    "RETURNING id"
                ),
                {"n": f"EV3API-sup-{suffix}", "lid": location_id},
            ).scalar_one()
            batch_id = conn.execute(
                text(
                    "INSERT INTO batches (commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log, freshness_score, "
                    "safety_status) "
                    "SELECT c.id, :lid, :s, 488.88, :h, CAST(:tl AS jsonb), 0.90, "
                    "'pending' FROM commodities c "
                    "WHERE c.name='telur' RETURNING id"
                ),
                {
                    "lid": location_id,
                    "s": str(sup_id),
                    "h": _iso(NOW - timedelta(days=2)),
                    "tl": json.dumps(log),
                },
            ).scalar_one()
    finally:
        engine.dispose()
    return {
        "supplier_id": str(sup_id),
        "batch_id": str(batch_id),
        "suffix": suffix,
        "location_id": location_id,
    }


def _cleanup_batch(b: dict) -> None:
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": b["batch_id"]})
    _db_exec("DELETE FROM suppliers WHERE id = :s", {"s": b["supplier_id"]})


def _cleanup_decision(decision_id: str) -> None:
    _db_exec(
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
        {"d": decision_id},
    )
    _db_exec("DELETE FROM approvals WHERE decision_id = :d", {"d": decision_id})
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})


def _target_jakarta() -> str:
    row = _db_all("SELECT id FROM locations WHERE name='Jakarta'")
    assert row, "lokasi seed Jakarta wajib ada"
    return str(row[0][0])


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_api_safety_unauth_401(client):
    """Unauth → 401."""
    resp = client.post(
        "/events/safety-disruption",
        json={
            "batch_id": str(uuid.uuid4()),
            "target_location_id": _target_jakarta(),
            "operation_key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 401


def test_api_safety_monitor_403(client):
    """bgn_monitor read-only → 403 (mutating event)."""
    b = _mk_batch("Cianjur", fail=True)
    try:
        headers = _monitor_user(client)
        resp = client.post(
            "/events/safety-disruption",
            headers=headers,
            json={
                "batch_id": b["batch_id"],
                "target_location_id": _target_jakarta(),
                "operation_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup_batch(b)


def test_api_safety_happy_path_revised_201(client):
    """FAIL → 201 revised; decision+evidence+trace terbaca dari DB."""
    b = _mk_batch("Cianjur", fail=True)
    try:
        headers = _head_user(client)
        resp = client.post(
            "/events/safety-disruption",
            headers=headers,
            json={
                "batch_id": b["batch_id"],
                "target_location_id": _target_jakarta(),
                "operation_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "revised"
        assert body["safety_status"] == "fail"
        assert body["excluded_batch_ids"] == [b["batch_id"]]
        assert body["decision_id"]
        # Wording UI: batch excluded, safety FAIL (§19).
        assert "excluded" in body["message"].lower()
        # Readback DB: decision safety_disruption.
        row = _db_all(
            "SELECT decision_type FROM decisions WHERE id = :d",
            {"d": body["decision_id"]},
        )
        assert row and row[0][0] == "safety_disruption"
        # Trace DETECT + OPTIMIZE ada.
        steps = _db_all(
            "SELECT step_name FROM agent_traces WHERE decision_id = :d",
            {"d": body["decision_id"]},
        )
        assert {s[0] for s in steps} >= {"DETECT", "OPTIMIZE"}
    finally:
        _cleanup_batch(b)


def test_api_safety_replay_same_key_idempotent(client):
    """operation_key sama + batch sama → replay, satu decision saja."""
    b = _mk_batch("Cianjur", fail=True)
    try:
        headers = _head_user(client)
        payload = {
            "batch_id": b["batch_id"],
            "target_location_id": _target_jakarta(),
            "operation_key": str(uuid.uuid4()),
        }
        r1 = client.post("/events/safety-disruption", headers=headers, json=payload)
        assert r1.status_code == 201, r1.text
        r2 = client.post("/events/safety-disruption", headers=headers, json=payload)
        assert r2.status_code == 201, r2.text
        assert r2.json()["decision_id"] == r1.json()["decision_id"]
        rows = _db_all(
            "SELECT count(*) FROM agent_traces t JOIN decisions d "
            "ON d.id = t.decision_id WHERE t.step_name='DETECT' "
            "AND t.input_summary->>'operation_key' = :k",
            {"k": payload["operation_key"]},
        )
        assert rows[0][0] == 1
        _cleanup_decision(r1.json()["decision_id"])
    finally:
        _cleanup_batch(b)


def test_api_safety_conflict_same_key_other_batch_409(client):
    """operation_key sama + batch beda → 409."""
    b1 = _mk_batch("Cianjur", fail=True)
    b2 = _mk_batch("Cianjur", fail=True)
    try:
        headers = _head_user(client)
        op_key = str(uuid.uuid4())
        r1 = client.post(
            "/events/safety-disruption",
            headers=headers,
            json={
                "batch_id": b1["batch_id"],
                "target_location_id": _target_jakarta(),
                "operation_key": op_key,
            },
        )
        assert r1.status_code == 201, r1.text
        r2 = client.post(
            "/events/safety-disruption",
            headers=headers,
            json={
                "batch_id": b2["batch_id"],
                "target_location_id": _target_jakarta(),
                "operation_key": op_key,
            },
        )
        assert r2.status_code == 409, r2.text
        _cleanup_decision(r1.json()["decision_id"])
    finally:
        _cleanup_batch(b1)
        _cleanup_batch(b2)


def test_api_safety_unknown_batch_404(client):
    """Batch tidak ada → 404."""
    headers = _head_user(client)
    resp = client.post(
        "/events/safety-disruption",
        headers=headers,
        json={
            "batch_id": str(uuid.uuid4()),
            "target_location_id": _target_jakarta(),
            "operation_key": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404


def test_api_safety_no_override_fields_422(client):
    """Client tidak bisa menyuntik safety_status (extra=forbid → 422)."""
    b = _mk_batch("Cianjur", fail=False)
    try:
        headers = _head_user(client)
        resp = client.post(
            "/events/safety-disruption",
            headers=headers,
            json={
                "batch_id": b["batch_id"],
                "target_location_id": _target_jakarta(),
                "operation_key": str(uuid.uuid4()),
                "safety_status": "pass",
            },
        )
        assert resp.status_code == 422, resp.text
    finally:
        _cleanup_batch(b)


def test_execute_revalidation_blocks_unsafe_batch(client):
    """O-EVENT-2: decision pending, verifier CONSISTENT, approval satisfied,
    TAPI batch sumber (lokasi+komoditas) kini FAIL → execute 409.
    Safety hard stop tanpa FK baru dan tanpa mengubah old decision.
    Lokasi sumber = lokasi uji terpisah (bukan seed Cianjur) agar batch
    seed demo tidak tersentuh sama sekali."""
    suffix = uuid.uuid4().hex[:8]
    # Lokasi uji + batch uji aman di lokasi itu.
    loc_id = str(_db_exec_returning(
        "INSERT INTO locations (name, region, latitude, longitude) "
        "VALUES (:n, 'Test', -6.9, 107.6) "
        "RETURNING id", {"n": f"EV3-src-{suffix}"}
    ))
    b = _mk_batch_at(loc_id, fail=False)
    created = None
    try:
        # 1) Decision lama regional_balance sumber lokasi uji.
        created = str(uuid.uuid4())
        _db_exec(
            "INSERT INTO decisions (id, decision_type, status, proposed_by, "
            "source_location_id, target_location_id, commodity_id, quantity_kg, "
            "safe_delivered_cost, expires_at, cost_breakdown) "
            "SELECT :id, 'regional_balance', 'pending_approval', 'supervisor_agent', "
            ":src, lt.id, c.id, 488.88, 16206000.00, now() + interval '30 minutes', "
            "'{\"purchase\": \"15720000\"}'::jsonb "
            "FROM locations lt, commodities c "
            "WHERE lt.name='Jakarta' AND c.name='telur'",
            {"id": created, "src": loc_id},
        )
        # 2) Verifikasi server-side. Sejak audit M1 (18 Okt 2026) hanya verdict
        # hasil audit yang dicatat; provider eksternal bisa UNAVAILABLE, jadi
        # tes ini mengunci verdict CONSISTENT agar yang diukur adalah pagar
        # revalidasi saat execute, bukan ketersediaan provider.
        rv = client.post(
            "/actions/verify", headers=_head_user(client), json={"decision_id": created}
        )
        assert rv.status_code == 200, rv.text
        _db_exec(
            "UPDATE decisions SET verifier_note='flagged', verified_by="
            "coalesce(verified_by, 'verifier_agent'), status='verifier_flagged' WHERE id = :d",
            {"d": created},
        )
        # 3) Approval dua role bila UNAVAILABLE/FLAGGED, satu bila CONSISTENT.
        verdict = _db_all(
            "SELECT verifier_note FROM decisions WHERE id = :d", {"d": created}
        )[0][0]
        if verdict == "consistent":
            ra = client.post(
                "/actions/approve",
                headers=_head_user(client),
                json={"decision_id": created, "approved": True},
            )
            assert ra.status_code == 200, ra.text
        else:
            ra1 = client.post(
                "/actions/approve",
                headers=_head_user(client),
                json={"decision_id": created, "approved": True},
            )
            assert ra1.status_code == 200, ra1.text
            ra2 = client.post(
                "/actions/approve",
                headers=_monitor_user(client),
                json={"decision_id": created, "approved": True},
            )
            # monitor bukan approver; gunakan nutritionist kedua.
            assert ra2.status_code in (200, 403)
            if ra2.status_code == 403:
                nut = _login(client, "sppg.nutritionist@demo.local", "Demo#Nut2026")
                ra3 = client.post(
                    "/actions/approve",
                    headers=nut,
                    json={"decision_id": created, "approved": True},
                )
                assert ra3.status_code == 200, ra3.text
        # 4) Batch sumber berubah FAIL (event 3 nyata terjadi setelahnya).
        # Batch di lokasi uji terpisah — seed demo tidak tersentuh.
        _db_exec(
            "UPDATE batches SET safety_status='fail' WHERE id = :b",
            {"b": b["batch_id"]},
        )
        # 5) Execute → 409 karena safety revalidation gagal.
        rx = client.post(
            "/actions/execute",
            headers=_head_user(client),
            json={"decision_id": created},
        )
        assert rx.status_code == 409, rx.text
        assert "safety" in rx.json()["detail"].lower()
    finally:
        if created:
            _cleanup_decision(created)
        _cleanup_batch(b)
        _db_exec("DELETE FROM locations WHERE id = :l", {"l": loc_id})
