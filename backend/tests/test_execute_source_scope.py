"""Cakupan SUMBER pada jalur eksekusi & konteks agen (AUD-9B-29).

Tiga kontrak yang dikunci di sini:

1. `approval-summary` memberi agen identitas yang benar untuk menilai batch
   SUMBER: `source_location_id`/`target_location_id` (cakupan exclusion) dan
   `safety.batch_ids` (himpunan yang SAMA dengan `batch_sumber_transfer`).
2. Exclusion hanya memblokir bila cakupannya cocok dengan SPPG penerima:
   exclusion `active` untuk pemasok yang sama tetapi lokasi lain TIDAK boleh
   memblokir `can_execute` (dulu satu exclusion aktif di Jakarta memveto
   review Bandung — probe e7150da4), sedangkan exclusion berlokasi target
   tetap memblokir.
3. `_source_batches_still_safe` fail-closed bila identitas sumber tidak lengkap.

Semua tes membuat barisnya sendiri (lokasi/pemasok/batch/decision/exclusion)
dan membersihkannya; tidak ada baris demo yang diubah.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC

DB_URL = DSN_SYNC
NOW = datetime.now(timezone.utc)


def _db_all(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None) -> None:
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _db_exec_returning(query: str, params: dict | None = None):
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


def _head(client: TestClient) -> dict:
    return _login(client, "sppg.head@demo.local", "Demo#SPPG2026")


def _jakarta_id() -> str:
    return str(_db_all("SELECT id FROM locations WHERE name='Jakarta'")[0][0])


@pytest.fixture()
def sumber():
    """Lokasi sumber + pemasok + batch + decision terikat, siap dieksekusi."""
    suffix = uuid.uuid4().hex[:8]
    log = [
        {"timestamp": (NOW - timedelta(hours=2)).isoformat(), "temperature_c": 4.0},
        {"timestamp": (NOW - timedelta(hours=1)).isoformat(), "temperature_c": 4.2},
    ]
    loc_id = str(
        _db_exec_returning(
            "INSERT INTO locations (name, region, latitude, longitude) "
            "VALUES (:n, 'Test', -6.9, 107.6) RETURNING id",
            {"n": f"A9B29-src-{suffix}"},
        )
    )
    sup_id = str(
        _db_exec_returning(
            "INSERT INTO suppliers (name, location_id, reliability_score) "
            "VALUES (:n, :l, 0.8) RETURNING id",
            {"n": f"A9B29-sup-{suffix}", "l": loc_id},
        )
    )
    batch_id = str(
        _db_exec_returning(
            "INSERT INTO batches (commodity_id, location_id, supplier_id, quantity_kg, "
            "harvested_at, temperature_log, freshness_score, safety_status, usable_until) "
            "SELECT c.id, :l, :s, 600.00, :h, CAST(:tl AS jsonb), 0.95, 'pass', "
            "now() + interval '6 hours' FROM commodities c WHERE c.name='telur' RETURNING id",
            {
                "l": loc_id,
                "s": sup_id,
                "h": (NOW - timedelta(days=1)).isoformat(),
                "tl": json.dumps(log),
            },
        )
    )
    decision_id = str(
        _db_exec_returning(
            "INSERT INTO decisions (id, decision_type, status, proposed_by, "
            "source_location_id, target_location_id, commodity_id, quantity_kg, "
            "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
            "verifier_note, verified_by) "
            "SELECT :id, 'regional_balance', 'pending_approval', 'supervisor_agent', "
            ":src, :tgt, c.id, 600.00, 16206000.00, now() + interval '30 minutes', "
            "'{\"purchase\": \"15720000\"}'::jsonb, 1, 'consistent', 'verifier_agent' "
            "FROM commodities c WHERE c.name='telur' RETURNING id",
            {"id": str(uuid.uuid4()), "src": loc_id, "tgt": _jakarta_id()},
        )
    )
    _db_exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": decision_id,
            "p": json.dumps(
                {
                    "allocation_binding": True,
                    "supplier_id": sup_id,
                    "batch_ids": [batch_id],
                }
            ),
        },
    )
    head, nut = _db_all(
        "SELECT id FROM users WHERE email IN "
        "('sppg.head@demo.local','sppg.nutritionist@demo.local') ORDER BY email"
    )
    for user_id in (head[0], nut[0]):
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved) "
            "VALUES (:d, :u, True)",
            {"d": decision_id, "u": str(user_id)},
        )
    _db_exec("UPDATE decisions SET status='approved' WHERE id=:d", {"d": decision_id})

    data = {
        "suffix": suffix,
        "location_id": loc_id,
        "supplier_id": sup_id,
        "batch_id": batch_id,
        "decision_id": decision_id,
        "exclusion_ids": [],
    }
    yield data
    for exclusion_id in data["exclusion_ids"]:
        _db_exec("DELETE FROM supplier_exclusions WHERE id = :e", {"e": exclusion_id})
    _db_exec(
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d", {"d": decision_id}
    )
    _db_exec("DELETE FROM approvals WHERE decision_id = :d", {"d": decision_id})
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": batch_id})
    _db_exec("DELETE FROM suppliers WHERE id = :s", {"s": sup_id})
    _db_exec("DELETE FROM locations WHERE id = :l", {"l": loc_id})


def _buat_exclusion(sumber: dict, scope_location_id: str) -> str:
    """Exclusion `active` untuk pemasok batch sumber, pada lokasi tertentu."""
    source_decision = str(
        _db_all(
            "SELECT id FROM decisions WHERE id <> :d ORDER BY created_at LIMIT 1",
            {"d": sumber["decision_id"]},
        )[0][0]
    )
    proposed_by = str(
        _db_all("SELECT id FROM users WHERE email='sppg.head@demo.local'")[0][0]
    )
    exclusion_id = str(
        _db_exec_returning(
            "INSERT INTO supplier_exclusions (supplier_id, scope_location_id, status, "
            "reason, evidence_refs, source_decision_id, proposed_by, activated_at) "
            "VALUES (:s, :l, 'active', 'uji cakupan AUD-9B-29', '[]'::jsonb, :d, :u, now()) "
            "RETURNING id",
            {
                "s": sumber["supplier_id"],
                "l": scope_location_id,
                "d": source_decision,
                "u": proposed_by,
            },
        )
    )
    sumber["exclusion_ids"].append(exclusion_id)
    return exclusion_id


def test_exclusion_lokasi_lain_tidak_memblokir_can_execute(client, sumber) -> None:
    """Exclusion Jakarta/telur tidak boleh memveto keputusan ber-target lain.

    Inilah galat probe e7150da4: satu exclusion aktif di Jakarta membuat SEMUA
    review ber-`active_exclusion_ids=[55bb6ed8…]` dan `safety_veto=True`.
    """
    bandung = str(_db_all("SELECT id FROM locations WHERE name='Bandung'")[0][0])
    _buat_exclusion(sumber, bandung)

    summary = client.get(
        f"/decisions/{sumber['decision_id']}/approval-summary", headers=_head(client)
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert not any("excluded" in alasan for alasan in body["blocking_reasons"]), body[
        "blocking_reasons"
    ]
    assert body["can_execute"] is True


def test_exclusion_lokasi_target_tetap_memblokir_can_execute(client, sumber) -> None:
    _buat_exclusion(sumber, _jakarta_id())

    summary = client.get(
        f"/decisions/{sumber['decision_id']}/approval-summary", headers=_head(client)
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["can_execute"] is False
    assert any("excluded" in alasan for alasan in body["blocking_reasons"])


def test_approval_summary_mengekspos_identitas_batch_sumber(client, sumber) -> None:
    """Agen butuh id, bukan nama, untuk mencakupkan exclusion & batch sumber."""
    body = client.get(
        f"/decisions/{sumber['decision_id']}/approval-summary", headers=_head(client)
    ).json()

    assert body["source_location_id"] == sumber["location_id"]
    assert body["target_location_id"] == _jakarta_id()
    assert body["supplier"]["id"] == sumber["supplier_id"]
    assert body["safety"]["batch_ids"] == [sumber["batch_id"]]
    assert body["safety"]["blocked"] is False
