"""P1 (paket 1-6, keputusan Roy 2026-10-09): Merkle ledger append-only.

Kontrak:
- Setiap approve/execute/reject menambah block ledger: sha256(prev_hash +
  payload). prev_hash block pertama = 64 karakter '0' (genesis).
- Rantai diverifikasi GET /ledger/verify → {valid, blocks}.
- Manipulasi payload_hash (UPDATE langsung) → valid: false.
- Endpoint read-only, wajib token (semua role terautentikasi).
- ledger_blocks TANPA FK ke users (integritas dari hash, bukan FK).
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB = DSN_SYNC
PW = "TestPass#2026"


def _db_exec(stmt, params=None):
    eng = create_engine(DB)
    try:
        with eng.begin() as conn:
            res = conn.execute(text(stmt), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        eng.dispose()


@pytest.fixture()
def ledger_approver():
    """User approver sekali pakai; semua jejak dibersihkan di akhir."""
    uid = str(uuid.uuid4())
    email = f"ledger-{uuid.uuid4().hex[:8]}@test.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    loc_id = _db_exec(
        "SELECT id FROM locations WHERE name = 'Jakarta'"
    )[0][0]
    _db_exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "VALUES (:i, 'Ledger Tester', :e, :h, 'sppg_head', :l)",
        {"i": uid, "e": email, "h": digest, "l": str(loc_id)},
    )
    yield {"id": uid, "email": email, "password": PW}
    # cleanup: approvals + ledger block milik user ini, lalu user-nya.
    _db_exec(
        "DELETE FROM ledger_blocks WHERE actor_id = :u", {"u": uid}
    )
    _db_exec(
        "DELETE FROM approvals WHERE approved_by = :u", {"u": uid}
    )
    _db_exec("DELETE FROM users WHERE id = :u", {"u": uid})


def _client() -> TestClient:
    return TestClient(__import__("app.main", fromlist=["app"]).app)


def _login(user) -> dict:
    with _client() as c:
        r = c.post(
            "/auth/login", json={"email": user["email"], "password": user["password"]}
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_ledger_verify_empty_chain(auth_headers):
    with _client() as c:
        r = c.get("/ledger/verify", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["valid"] is True
        assert isinstance(data["blocks"], int)


def test_ledger_requires_auth():
    with _client() as c:
        r = c.get("/ledger/verify")
        assert r.status_code == 401


def test_ledger_verify_detects_tamper(auth_headers):
    rows = _db_exec(
        "SELECT id, payload_hash FROM ledger_blocks ORDER BY height LIMIT 1"
    )
    if not rows:
        pytest.skip("ledger kosong (belum ada aksi approve/execute)")
    block_id, original = rows[0][0], rows[0][1]
    try:
        with _client() as c:
            _db_exec(
                "UPDATE ledger_blocks SET payload_hash = :p WHERE id = :i",
                {"p": "f" * 64, "i": block_id},
            )
            r = c.get("/ledger/verify", headers=auth_headers)
            assert r.status_code == 200, r.text
            assert r.json()["valid"] is False
    finally:
        _db_exec(
            "UPDATE ledger_blocks SET payload_hash = :p WHERE id = :i",
            {"p": original, "i": block_id},
        )


def test_approve_appends_ledger_block(ledger_approver):
    """Approve sebuah decision → block ledger bertambah + rantai valid.

    Pilihan baris HARUS mengikuti cakupan token: approver ini Kepala Jakarta,
    sedangkan DB demo kini juga memuat keputusan Bandung/Surabaya (seed per
    kota + suite lain). Dulu tes mengambil `pending_approval` APA SAJA dan
    merah 403 begitu yang terambil bukan Jakarta — kegagalan yang terbaca
    seperti regresi pagar cakupan padahal cakupannya benar.
    """
    dec = _db_exec(
        "SELECT d.id FROM decisions d "
        "JOIN locations l ON l.id = d.target_location_id "
        "WHERE d.status = 'pending_approval' AND l.name = 'Jakarta' "
        "AND d.verified_by IS NOT NULL "
        "AND d.verifier_note IN ('consistent', 'flagged') "
        "AND NOT EXISTS (SELECT 1 FROM approvals a WHERE a.decision_id = d.id "
        "                AND a.approved_by = :u) "
        "ORDER BY d.created_at DESC LIMIT 1",
        {"u": ledger_approver["id"]},
    )
    if not dec:
        pytest.skip("tidak ada decision Jakarta yang siap di-approve di DB")
    decision_id = str(dec[0][0])
    before = _db_exec("SELECT COUNT(*) FROM ledger_blocks")[0][0]
    headers = _login(ledger_approver)

    with _client() as c:
        r = c.post(
            "/actions/approve",
            headers=headers,
            json={"decision_id": decision_id, "approved": True, "comment": "ledger test"},
        )
        assert r.status_code == 200, r.text

    after = _db_exec("SELECT COUNT(*) FROM ledger_blocks")[0][0]
    assert after == before + 1

    with _client() as c:
        r = c.get("/ledger/verify", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["valid"] is True


def test_ledger_no_fk_to_users():
    """Integritas rantai dari hash, bukan FK — user test boleh terhapus."""
    fk = _db_exec(
        "SELECT count(*) FROM pg_constraint WHERE conname = "
        "'ledger_blocks_actor_id_fkey'"
    )[0][0]
    assert fk == 0
