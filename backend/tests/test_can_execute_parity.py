"""`can_execute` harus sama ketatnya dengan `/actions/execute` (audit M5).

Masalah: read model menyatakan `can_execute=True` tetapi endpoint menolak 422
(kuantitas/harga tidak valid, komoditas hilang) atau 409 (supplier dikecualikan).
Juri melihat tombol "Eksekusi" aktif lalu menerima galat — janji yang tidak
ditepati. Pagar di endpoint tetap satu-satunya penentu; read model harus
MENCERMINKANNYA, bukan menebak lebih longgar.

Yang diuji di sini hanya kesamaan itu: satu cacat -> satu alasan yang sama
dengan pesan endpoint.
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


def _db():
    return create_engine(DB_URL)


def _exec(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        engine.dispose()


def _mk_head(kota: str = "Jakarta") -> dict:
    email = f"sppg_head-{uuid.uuid4().hex[:8]}@uji-canexec.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT gen_random_uuid(), 'Uji can_execute', :e, :h, 'sppg_head', l.id "
        "FROM locations l WHERE l.name = :k",
        {"e": email, "h": digest, "k": kota},
    )
    return {"email": email, "password": PW}


def _drop(email: str) -> None:
    _exec("DELETE FROM users WHERE email = :e", {"e": email})


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _sumber():
    row = _exec(
        "SELECT b.id, b.supplier_id FROM batches b "
        "JOIN locations l ON l.id = b.location_id "
        "JOIN commodities c ON c.id = b.commodity_id "
        "JOIN suppliers s ON s.id = b.supplier_id "
        "WHERE l.name = 'Cianjur' AND c.name = 'telur' AND b.safety_status = 'pass' "
        "ORDER BY b.created_at DESC LIMIT 1"
    )
    assert row, "butuh batch telur Cianjur yang aman untuk fixture"
    return str(row[0][0]), str(row[0][1])


def _siapkan(approver_email: str) -> str:
    """Keputusan pending yang sudah verified + dua approval Jakarta."""
    batch_id, supplier_id = _sumber()
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "verified_by, verifier_note) "
        "SELECT :id, 'regional_balance', 'pending_approval', 'supervisor_agent', "
        "ls.id, lt.id, c.id, 600, 16206000, now() + interval '45 minutes', "
        "'{\"purchase\": \"15720000\", \"candidate_score\": \"0.36\"}'::jsonb, 1, "
        "'verifier_agent', 'consistent' "
        "FROM locations lt, locations ls, commodities c "
        "WHERE lt.name = 'Jakarta' AND ls.name = 'Cianjur' AND c.name = 'telur'",
        {"id": did},
    )
    _exec(
        "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
        "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))",
        {
            "d": did,
            "p": (
                # Bentuk FLAT — sama dengan penulis produksi
                # (`supplier_eligibility`): flag di akar payload. Bentuk
                # bersarang tidak pernah dibaca `resolve_binding`, dan dulu
                # lolos hanya karena Cianjur/telur punya satu pemasok.
                '{"allocation_binding": true, "supplier_id": "'
                + supplier_id
                + '", "batch_ids": ["'
                + batch_id
                + '"]}'
            ),
        },
    )
    _exec(
        "INSERT INTO approvals (decision_id, approved_by, approved, comment) "
        "SELECT :d, u.id, true, 'fixture' FROM users u "
        "WHERE u.role IN ('sppg_head','sppg_nutritionist') AND u.email LIKE '%@demo.local' "
        "AND u.location_id = (SELECT id FROM locations WHERE name='Jakarta') "
        "GROUP BY u.id, u.role ORDER BY u.role LIMIT 2",
        {"d": did},
    )
    return did


def _bersihkan(did: str | None) -> None:
    if not did:
        return
    _exec("DELETE FROM supplier_exclusions WHERE source_decision_id = :d", {"d": did})
    _exec("DELETE FROM decisions WHERE id = :d", {"d": did})


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _summary(client, did: str, kepala: dict) -> dict:
    resp = client.get(f"/decisions/{did}/approval-summary", headers=_login(client, kepala))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_kendali_semua_syarat_terpenuhi(client):
    kepala = _mk_head()
    did = None
    try:
        did = _siapkan(kepala["email"])
        body = _summary(client, did, kepala)
        assert body["approval_state"]["satisfied"] is True, body["approval_state"]
        assert body["blocking_reasons"] == [], body["blocking_reasons"]
        assert body["can_execute"] is True
    finally:
        _bersihkan(did)
        _drop(kepala["email"])


def test_kuantitas_kosong_memblokir_eksekusi(client):
    kepala = _mk_head()
    did = None
    try:
        did = _siapkan(kepala["email"])
        _exec("UPDATE decisions SET quantity_kg = NULL WHERE id = :d", {"d": did})
        body = _summary(client, did, kepala)
        assert body["can_execute"] is False
        assert "quantity decision tidak valid" in body["blocking_reasons"]
    finally:
        _bersihkan(did)
        _drop(kepala["email"])


def test_biaya_kosong_memblokir_eksekusi(client):
    kepala = _mk_head()
    did = None
    try:
        did = _siapkan(kepala["email"])
        _exec("UPDATE decisions SET safe_delivered_cost = NULL WHERE id = :d", {"d": did})
        body = _summary(client, did, kepala)
        assert body["can_execute"] is False
        assert "unit price decision tidak valid" in body["blocking_reasons"]
    finally:
        _bersihkan(did)
        _drop(kepala["email"])


def test_komoditas_hilang_memblokir_eksekusi(client):
    kepala = _mk_head()
    did = None
    try:
        did = _siapkan(kepala["email"])
        _exec("UPDATE decisions SET commodity_id = NULL WHERE id = :d", {"d": did})
        body = _summary(client, did, kepala)
        assert body["can_execute"] is False
        assert "commodity decision tidak valid" in body["blocking_reasons"]
    finally:
        _bersihkan(did)
        _drop(kepala["email"])


def test_supplier_dikecualikan_memblokir_eksekusi(client):
    kepala = _mk_head()
    did = None
    try:
        did = _siapkan(kepala["email"])
        _, supplier_id = _sumber()
        _exec(
            "INSERT INTO supplier_exclusions (supplier_id, scope_location_id, status, "
            "reason, evidence_refs, source_decision_id, proposed_by) "
            "SELECT :sup, lt.id, 'active', 'uji exclusion', '[]'::jsonb, :d, u.id "
            "FROM locations lt, decisions d, users u "
            "WHERE lt.name = 'Jakarta' AND d.id = :d AND u.email = :e",
            {"sup": supplier_id, "d": did, "e": kepala["email"]},
        )
        body = _summary(client, did, kepala)
        assert body["can_execute"] is False
        # Pesan SAMA dengan endpoint /actions/execute (satu sumber kalimat).
        assert "supplier excluded pada SPPG penerima" in body["blocking_reasons"]
    finally:
        _bersihkan(did)
        _drop(kepala["email"])
