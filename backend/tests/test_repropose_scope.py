"""Re-propose wajib dijaga cakupan lokasi (audit M3, 18 Okt 2026).

Masalah: `POST /actions/repropose` hanya memanggil `require_scope` pada cabang
`ADMIN_TYPES`. Untuk keputusan operasional (regional_balance, safety_disruption,
price_anomaly) kepala SPPG dari kota lain bisa mengusulkan ulang keputusan yang
ditolak — anaknya menyalin `target_location_id` parent, jadi ia menciptakan
keputusan baru untuk SPPG yang bukan wilayahnya. Pagar cakupan di
propose/verify/approve/execute tidak menutup jalur ini.

Aturan sekarang: cakupan diperiksa untuk SEMUA tipe, sebelum cabang admin.
Urutannya scope → admin → status → alasan, supaya penolakan lintas lokasi
konsisten dengan endpoint tulis lain (403, bukan pesan alur).
"""

import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
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


def _mk_user(role: str, kota: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-repropose.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    _exec(
        "INSERT INTO users (id, name, email, password_hash, role, location_id) "
        "SELECT gen_random_uuid(), :n, :e, :h, :r, l.id FROM locations l WHERE l.name = :k",
        {"n": f"U {role} {kota}", "e": email, "h": digest, "r": role, "k": kota},
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


def _keputusan_ditolak(kota: str, tipe: str = "regional_balance") -> str:
    did = str(uuid.uuid4())
    _exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
        "rejection_reason) "
        "SELECT :id, :tipe, 'rejected', 'supervisor_agent', "
        "ls.id, lt.id, c.id, 600, 16206000, now() + interval '30 minutes', "
        "'{\"purchase\": \"15720000\"}'::jsonb, 1, "
        "'harga terlalu tinggi — cari sumber lebih dekat' "
        "FROM locations lt, locations ls, commodities c "
        "WHERE lt.name = :kota AND ls.name = 'Cianjur' AND c.name = 'telur'",
        {"id": did, "tipe": tipe, "kota": kota},
    )
    return did


def _anak(parent_id: str) -> int:
    rows = _exec(
        "SELECT count(*) FROM decisions WHERE supersedes_id = :p", {"p": parent_id}
    )
    return int(rows[0][0])


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _bersihkan(*ids: str | None) -> None:
    for did in ids:
        if did:
            _exec("DELETE FROM decisions WHERE id = :d", {"d": did})
    # anak hasil re-propose (supersedes_id menunjuk parent yang sudah dihapus)
    _exec(
        "DELETE FROM decisions WHERE supersedes_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM decisions p WHERE p.id = decisions.supersedes_id)"
    )


def test_repropose_lintas_lokasi_ditolak_403(client):
    bandung = _mk_user("sppg_head", "Bandung")
    parent = None
    try:
        parent = _keputusan_ditolak("Jakarta")
        resp = client.post(
            "/actions/repropose", json={"decision_id": parent}, headers=_login(client, bandung)
        )
        assert resp.status_code == 403, resp.text
        assert "sppg" in resp.json()["detail"].lower()
        assert _anak(parent) == 0, "tidak boleh ada iterasi baru dari kota lain"
    finally:
        _bersihkan(parent)
        _drop(bandung["email"])


def test_repropose_di_lokasi_sendiri_tetap_201(client):
    bandung = _mk_user("sppg_head", "Bandung")
    parent = None
    try:
        parent = _keputusan_ditolak("Bandung")
        resp = client.post(
            "/actions/repropose", json={"decision_id": parent}, headers=_login(client, bandung)
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["iteration"] == 2
        assert _anak(parent) == 1
    finally:
        _bersihkan(parent)
        _drop(bandung["email"])


def test_repropose_admin_lintas_lokasi_tetap_403(client):
    """Cabang admin dulu memakai require_scope-nya sendiri; hasilnya harus sama."""
    bandung = _mk_user("sppg_head", "Bandung")
    parent = None
    try:
        parent = _keputusan_ditolak("Jakarta", tipe="supplier_exclusion")
        resp = client.post(
            "/actions/repropose", json={"decision_id": parent}, headers=_login(client, bandung)
        )
        assert resp.status_code == 403, resp.text
    finally:
        _bersihkan(parent)
        _drop(bandung["email"])


def test_repropose_admin_di_lokasi_sendiri_tetap_409(client):
    bandung = _mk_user("sppg_head", "Bandung")
    parent = None
    try:
        parent = _keputusan_ditolak("Bandung", tipe="supplier_exclusion")
        resp = client.post(
            "/actions/repropose", json={"decision_id": parent}, headers=_login(client, bandung)
        )
        assert resp.status_code == 409, resp.text
        assert "supplier-exclusions" in resp.json()["detail"]
    finally:
        _bersihkan(parent)
        _drop(bandung["email"])
