"""Wiring konsistensi bukti ke kartu KPI (TDD, 16 Okt 2026).

Berkas ini menguji DUA hal yang sebelumnya tidak bisa dibuktikan:

1. **Penulisnya benar-benar menilai.** Empat penulis bukti
   (`event2_service`, `event3_service`, `supplier_eligibility`,
   `supplier_exclusion_service`) dulu menulis `is_consistent=None` apa adanya.
   Sekarang setiap baris bukti yang ditulis pipeline WAJIB punya nilai
   (`True`/`False`), bukan `None` — diuji dari baris DB sesudah alur nyata.
2. **Metrik Evidence Completeness menjadi jujur.** Penyebutnya kini hanya
   keputusan yang punya cutoff approval (bisa dinilai), dengan `coverage`
   melaporkan bagian yang bisa dinilai; tanpa satu pun approval metriknya
   `no_data` beralasan, bukan 0,00% berlabel "tersedia".

Semua baris uji dibersihkan (lokasi/komoditas/keputusan/user) supaya DB demo
tidak terkotori.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL
from tests.test_event2_service import mk_pair

DB_URL = DSN_SYNC


def _db_all(query: str, params: dict | None = None):
    """SELECT / INSERT ... RETURNING → daftar row."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            return conn.execute(text(query), params or {}).fetchall()
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None) -> None:
    """DML tanpa row kembali (INSERT/DELETE polos)."""
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


def _head_user(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


def _monitor_user(client: TestClient) -> dict:
    return _login(client, "bgn.monitor@demo.local", "Demo#BGN2026")


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _evidence_rows(decision_id: str) -> list[tuple]:
    return _db_all(
        "SELECT evidence_type, is_consistent FROM decision_evidence "
        "WHERE decision_id = :d ORDER BY evidence_type",
        {"d": decision_id},
    )


# ---------------------------------------------------------------------------
# 1. Penulis menilai buktinya
# ---------------------------------------------------------------------------


def test_event2_menulis_bukti_harga_dengan_penilaian(client, request):
    """Event 2 menulis market_price, `is_consistent` True (bukan NULL)."""
    quote_id, _ref_id, _loc_id = mk_pair(request, "1.2")  # +20% anomalous
    resp = client.post(
        "/events/price-anomaly",
        json={
            "quote_id": quote_id,
            "target_location_id": str(
                _db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0]
            ),
            "operation_key": str(uuid.uuid4()),
        },
        headers=_head_user(client),
    )
    assert resp.status_code == 201, resp.text
    decision_id = resp.json()["decision_id"]
    try:
        rows = _evidence_rows(decision_id)
        assert rows, "event 2 wajib menulis bukti"
        assert all(row[1] is not None for row in rows), rows
        assert ("market_price", True) in rows
    finally:
        _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})


def test_event3_menulis_seluruh_bukti_dengan_penilaian(client):
    """Event 3 (suhu + binding) menulis penilaian, tidak ada yang NULL."""
    from tests.test_event3_api import _cleanup_batch, _cleanup_decision, _mk_batch

    b = _mk_batch("Cianjur", fail=True)
    decision_id = None
    try:
        resp = client.post(
            "/events/safety-disruption",
            headers=_head_user(client),
            json={
                "batch_id": b["batch_id"],
                "target_location_id": str(
                    _db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0]
                ),
                "operation_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 201, resp.text
        decision_id = resp.json()["decision_id"]
        rows = _evidence_rows(decision_id)
        assert rows
        assert all(row[1] is not None for row in rows), rows
        assert ("temperature", True) in rows
    finally:
        if decision_id:
            _cleanup_decision(decision_id)
        _cleanup_batch(b)


# ---------------------------------------------------------------------------
# 2. Metrik Evidence Completeness
# ---------------------------------------------------------------------------


@pytest.fixture()
def metric_ctx():
    """Lokasi uji terisolasi + user approver; dibersihkan setelah dipakai."""
    suffix = uuid.uuid4().hex[:8]
    loc_ids = [
        _db_all(
            "INSERT INTO locations (name, region, latitude, longitude) "
            "VALUES (:n, 'test', -6.9, 107.6) RETURNING id",
            {"n": f"EVK-cons-{suffix}-{suffix[:2]}"},
        )[0][0],
    ]
    user_id = _db_all(
        "INSERT INTO users (name, email, password_hash, role, location_id) "
        "VALUES ('EVK Approver', :e, 'x', 'sppg_head', :l) RETURNING id",
        {"e": f"evk-cons-{suffix}@test.local", "l": str(loc_ids[0])},
    )[0][0]
    commodity_id = _db_all("SELECT id FROM commodities LIMIT 1")[0][0]
    try:
        yield {
            "loc": str(loc_ids[0]),
            "user": str(user_id),
            "commodity": str(commodity_id),
        }
    finally:
        # Urutan FK: approvals (NO ACTION) → decisions → user → lokasi.
        # Keputusan uji tidak boleh dibiarkan menahan lokasi uji: kalau
        # teardown gagal di tengah, barisnya tertinggal di DB demo dan
        # mengotori layar juri.
        for loc in loc_ids:
            _db_exec(
                "DELETE FROM approvals WHERE decision_id IN ("
                "SELECT id FROM decisions WHERE source_location_id = :l "
                "OR target_location_id = :l)",
                {"l": str(loc)},
            )
            _db_exec(
                "DELETE FROM decisions WHERE source_location_id = :l "
                "OR target_location_id = :l",
                {"l": str(loc)},
            )
        _db_exec("DELETE FROM users WHERE id = :u", {"u": str(user_id)})
        for loc in loc_ids:
            _db_exec("DELETE FROM locations WHERE id = :l", {"l": str(loc)})


def _mk_decision(ctx, *, with_approval: bool, evidence_types=()) -> str:
    """Keputusan uji: bukti dicatat 10 menit sebelum approval (cutoff)."""
    decision_id = _db_all(
        "INSERT INTO decisions (decision_type, status, proposed_by, "
        "target_location_id, source_location_id, commodity_id, quantity_kg, "
        "expires_at) VALUES ('regional_balance', :st, 'test', :loc, :loc, "
        ":com, 10, now() + interval '1 hour') RETURNING id",
        {
            "st": "approved" if with_approval else "pending_approval",
            "loc": ctx["loc"],
            "com": ctx["commodity"],
        },
    )[0][0]
    for evidence_type in evidence_types:
        _db_exec(
            "INSERT INTO decision_evidence (decision_id, evidence_type, payload, "
            "is_consistent, recorded_at) VALUES (:d, :t, '{}'::jsonb, true, "
            "now() - interval '10 minutes')",
            {"d": str(decision_id), "t": evidence_type},
        )
    if with_approval:
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved, "
            "approved_at) VALUES (:d, :u, true, now())",
            {"d": str(decision_id), "u": ctx["user"]},
        )
    return str(decision_id)


def _kpi(client, name: str, ctx) -> dict:
    now = datetime.now(timezone.utc)
    resp = client.get(
        "/kpi",
        params={
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1)).isoformat(),
            "location_id": ctx["loc"],
        },
        headers=_monitor_user(client),
    )
    assert resp.status_code == 200, resp.text
    return {m["name"]: m for m in resp.json()["metrics"]}[name]


def test_evidence_completeness_menghitung_hanya_yang_punya_approval(client, metric_ctx):
    """1 dari 2 keputusan punya approval + 2 tipe bukti konsisten → 100%,
    dan coverage melaporkan bahwa hanya separuh keputusan bisa dinilai."""
    _mk_decision(
        metric_ctx,
        with_approval=True,
        evidence_types=["temperature", "human_inspection"],
    )
    _mk_decision(metric_ctx, with_approval=False)
    metric = _kpi(client, "Evidence Completeness", metric_ctx)
    assert metric["state"] == "available", metric
    assert metric["value"] == "100.00", metric
    assert metric["sample_count"] == 1, metric
    assert metric["coverage"] == "0.50", metric


def test_evidence_completeness_no_data_tanpa_approval(client, metric_ctx):
    """Tidak ada satu pun approval → `no_data` beralasan, bukan 0,00%."""
    _mk_decision(metric_ctx, with_approval=False)
    metric = _kpi(client, "Evidence Completeness", metric_ctx)
    assert metric["state"] == "no_data", metric
    assert "disetujui" in (metric["reason"] or ""), metric
