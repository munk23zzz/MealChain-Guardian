"""Re-propose pengadaan harus mewarisi pemasok + binding (temuan F6 audit 27 Okt 2026).

Sebelum perbaikan, iterasi baru dari keputusan pengadaan yang ditolak hanya
menyalin lokasi/komoditas/jumlah; `supplier_id` dan bukti `allocation_binding`
tertinggal di induknya. Akibatnya iterasi baru tidak punya pemasok, dan
eksekusinya ditolak `409 supplier_unknown` — tombol "Minta re-propose" di
halaman Decision & Evidence bekerja, tetapi hasilnya keputusan yang mati.
"""

from __future__ import annotations

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC

DB_URL = DSN_ASYNC.replace("+asyncpg", "+psycopg")
PW = "TestPass#2026"


def _exec(sql: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        engine.dispose()


def _batch() -> dict:
    row = _exec(
        "SELECT b.id, b.supplier_id, b.location_id, b.commodity_id, l.name "
        "FROM batches b JOIN suppliers s ON s.id = b.supplier_id "
        "JOIN locations l ON l.id = b.location_id "
        "WHERE b.location_id = s.location_id AND b.safety_status = 'pass' "
        "ORDER BY b.created_at DESC LIMIT 1"
    )
    assert row, "butuh batch pemasok-di-SPPG untuk fixture"
    return {
        "batch_id": str(row[0][0]),
        "supplier_id": str(row[0][1]),
        "location_id": str(row[0][2]),
        "commodity_id": str(row[0][3]),
        "kota": row[0][4],
    }


def _mk_head(kota: str) -> dict:
    email = f"sppg_head-{uuid.uuid4().hex[:8]}@uji-repropose.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT gen_random_uuid(), 'Uji repropose', :e, :h, 'sppg_head', l.id "
        "FROM locations l WHERE l.name = :k",
        {"e": email, "h": digest, "k": kota},
    )
    return {"email": email, "password": PW}


def _siapkan() -> dict:
    b = _batch()
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note, supplier_id, rejection_reason) "
        "VALUES (:id, 'supplier_procurement', 'rejected', 'supervisor_agent', "
        "NULL, CAST(:tgt AS uuid), CAST(:kom AS uuid), 240, 7200000, "
        "now() + interval '45 minutes', '{}'::jsonb, 1, 'verifier_agent', "
        "'consistent', CAST(:sup AS uuid), 'Kuota SPPG penuh minggu ini')",
        {
            "id": did,
            "tgt": b["location_id"],
            "kom": b["commodity_id"],
            "sup": b["supplier_id"],
        },
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload, is_consistent) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb), true)",
        {
            "d": did,
            "p": (
                '{"allocation_binding": true, "procurement": true, "supplier_id": "'
                + b["supplier_id"]
                + '", "target_location_id": "'
                + b["location_id"]
                + '", "batch_ids": ["'
                + b["batch_id"]
                + '"]}'
            ),
        },
    )
    return {"decision_id": did, "kepala": _mk_head(b["kota"]), "batch": b}


def _bersihkan(h: dict) -> None:
    for sql in (
        "DELETE FROM agent_traces WHERE decision_id IN "
        "(SELECT id FROM decisions WHERE supersedes_id = :d) OR decision_id = :d",
        "DELETE FROM decision_evidence WHERE decision_id IN "
        "(SELECT id FROM decisions WHERE supersedes_id = :d) OR decision_id = :d",
        "DELETE FROM approvals WHERE decision_id IN "
        "(SELECT id FROM decisions WHERE supersedes_id = :d) OR decision_id = :d",
        "DELETE FROM decisions WHERE supersedes_id = :d",
        "DELETE FROM decisions WHERE id = :d",
    ):
        _exec(sql, {"d": h["decision_id"]})
    _exec("DELETE FROM users WHERE email = :e", {"e": h["kepala"]["email"]})


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_repropose_pengadaan_mewarisi_pemasok_dan_binding(client):
    h = _siapkan()
    try:
        resp = client.post(
            "/actions/repropose",
            json={"decision_id": h["decision_id"]},
            headers=_login(client, h["kepala"]),
        )
        assert resp.status_code == 201, resp.text
        anak = resp.json()["decision_id"]

        baris = _exec(
            "SELECT decision_type, status, supplier_id, source_location_id, iteration "
            "FROM decisions WHERE id = :a",
            {"a": anak},
        )
        assert baris, "iterasi baru tidak tersimpan"
        jenis, status, supplier, source, iteration = baris[0]
        assert jenis == "supplier_procurement"
        assert status == "proposed"
        assert str(supplier) == h["batch"]["supplier_id"], "pemasok tidak diwarisi"
        assert source is None, "pengadaan tidak boleh mendapat lokasi asal"
        assert iteration == 2

        bukti = _exec(
            "SELECT payload, is_consistent FROM decision_evidence "
            "WHERE decision_id = :a AND (payload->>'allocation_binding')::boolean IS TRUE",
            {"a": anak},
        )
        assert len(bukti) == 1, "binding induk tidak disalin ke iterasi baru"
        assert bukti[0][0]["supplier_id"] == h["batch"]["supplier_id"]
        assert bukti[0][0]["batch_ids"] == [h["batch"]["batch_id"]]
        assert bukti[0][1] is True
    finally:
        _bersihkan(h)
