"""Status `approved` saat kuorum penuh — keputusan produk 2A (18 Okt 2026).

Sebelum ini `approve` TIDAK PERNAH mengubah status: dua approval lengkap pun
tetap `pending_approval` sampai dieksekusi. Akibatnya:

* tidak ada keadaan "disetujui, menunggu eksekusi" yang bisa dilaporkan;
* blok ledger approval ke-1 dan ke-2 sama-sama menyimpan `pending_approval`,
  sehingga auditor tidak bisa membedakan kuorum 1 dari kuorum 2;
* UI punya cabang `approved` yang tidak pernah tercapai (kosakata mati).

Yang dipaku di berkas ini:

1. approval pertama (salah satu role) → status TETAP `pending_approval`;
2. approval kedua (role berbeda) → status `approved`, di respons DAN di DB;
3. `/actions/execute` menerima `approved` dan menuntaskannya ke `executed`;
4. blok ledger approval kedua mencatat `status: "approved"`;
5. approve lagi oleh user yang sama → 409 (perilaku lama tidak berubah);
6. verify setelah kuorum → 409 (approval sudah tercatat).

Domain email `@status-approved.local`, BUKAN `@test.local`: fixture autouse sesi
lain menyapu `%@test.local` di DB bersama dan token tes ini bisa jadi 401.
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

# Keputusan operasional (bukan ADMIN_TYPES) yang menyasar Jakarta.
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


def _mk_user(role: str, location_name: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@status-approved.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    engine = _db()
    try:
        with engine.begin() as conn:
            loc = conn.execute(
                text("SELECT id FROM locations WHERE name = :n"), {"n": location_name}
            ).scalar_one()
            uid = conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l) RETURNING id"
                ),
                {"n": f"T {role}", "e": email, "h": digest, "r": role, "l": loc},
            ).scalar_one()
        return {"id": str(uid), "email": email, "password": PW, "role": role}
    finally:
        engine.dispose()


def _drop_user(email: str) -> None:
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


def _status_db(decision_id: str) -> str:
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"), {"d": decision_id}
            ).scalar_one()
    finally:
        engine.dispose()


def _verdict(decision_id: str) -> None:
    """Verifier dianggap sudah jalan (tanpa jaringan ke provider)."""
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE decisions SET verified_by = 'verifier-agent', "
                    "verifier_note = 'consistent' WHERE id = :d"
                ),
                {"d": decision_id},
            )
    finally:
        engine.dispose()


def _cleanup(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM approvals WHERE decision_id = :d"), {"d": decision_id}
            )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


def _ikat_binding(decision_id: str) -> None:
    """Ikat keputusan ke SATU batch Cianjur/telur lewat bukti `allocation_binding`.

    Sejak dataset 19 Okt 2026 Cianjur punya EMPAT pemasok telur, jadi
    `resolve_binding` (yang menolak menebak pemasok) menjawab `supplier_unknown`
    untuk keputusan tanpa binding. Tes ini menguji status `approved` +
    eksekusi, bukan penebakan, jadi batch sumbernya diikat eksplisit.
    """
    engine = _db()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT b.id, b.supplier_id FROM batches b "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "JOIN locations l ON l.id = b.location_id "
                    "WHERE c.name = 'telur' AND l.name = 'Cianjur' "
                    "AND b.origin = 'seed' ORDER BY b.id LIMIT 1"
                )
            ).one()
            conn.execute(
                text(
                    "INSERT INTO decision_evidence (decision_id, evidence_type, payload) "
                    "VALUES (:d, 'human_inspection', CAST(:p AS jsonb))"
                ),
                {
                    "d": decision_id,
                    "p": __import__("json").dumps(
                        {
                            "allocation_binding": True,
                            "supplier_id": str(row[1]),
                            "batch_ids": [str(row[0])],
                        }
                    ),
                },
            )
    finally:
        engine.dispose()


def _siapkan(client: TestClient, kepala: dict) -> str:
    """Buat keputusan lewat API, ajukan, lalu tandai terverifikasi."""
    headers = _login(client, kepala)
    resp = client.post("/decisions", json={"recommendation": RECOMMENDATION}, headers=headers)
    assert resp.status_code == 201, resp.text
    decision_id = resp.json()["decision_id"]
    _ikat_binding(decision_id)
    resp = client.post(
        "/actions/propose",
        json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    _verdict(decision_id)
    return decision_id


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def akun():
    kepala = _mk_user("sppg_head", "Jakarta")
    gizi = _mk_user("sppg_nutritionist", "Jakarta")
    yield kepala, gizi
    _drop_user(kepala["email"])
    _drop_user(gizi["email"])


def _approve(client: TestClient, decision_id: str, user: dict):
    return client.post(
        "/actions/approve",
        json={"decision_id": decision_id, "approved": True},
        headers=_login(client, user),
    )


def test_approval_pertama_belum_mengubah_status(client, akun):
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        resp = _approve(client, decision_id, gizi)
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_status"] == "pending_approval"
        assert resp.json()["approval_state"]["satisfied"] is False
        assert _status_db(decision_id) == "pending_approval"
    finally:
        _cleanup(decision_id)


def test_approval_kedua_menjadikan_status_approved(client, akun):
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        assert _approve(client, decision_id, gizi).status_code == 200
        resp = _approve(client, decision_id, kepala)
        assert resp.status_code == 200, resp.text
        assert resp.json()["decision_status"] == "approved"
        assert resp.json()["approval_state"]["satisfied"] is True
        assert _status_db(decision_id) == "approved"
    finally:
        _cleanup(decision_id)


def test_ledger_mencatat_status_approved_pada_kuorum(client, akun):
    """Blok approval terakhir harus membedakan kuorum penuh dari kuorum separuh."""
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        assert _approve(client, decision_id, gizi).status_code == 200
        assert _approve(client, decision_id, kepala).status_code == 200
        engine = _db()
        try:
            with engine.connect() as conn:
                status_blok = conn.execute(
                    text(
                        "SELECT (payload::jsonb)->>'status' FROM ledger_blocks "
                        "WHERE entity_id = :d AND action = 'approve' "
                        "ORDER BY height"
                    ),
                    {"d": decision_id},
                ).scalars().all()
        finally:
            engine.dispose()
        assert status_blok == ["pending_approval", "approved"], status_blok
    finally:
        _cleanup(decision_id)


def test_execute_menerima_status_approved(client, akun):
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        assert _approve(client, decision_id, gizi).status_code == 200
        assert _approve(client, decision_id, kepala).status_code == 200
        assert _status_db(decision_id) == "approved"

        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, kepala),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "executed"
        assert resp.json()["po_number"].startswith("MC-")
        assert _status_db(decision_id) == "executed"
    finally:
        _cleanup(decision_id)


def test_approve_ketiga_tetap_409(client, akun):
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        assert _approve(client, decision_id, gizi).status_code == 200
        assert _approve(client, decision_id, kepala).status_code == 200
        resp = _approve(client, decision_id, kepala)
        assert resp.status_code == 409, resp.text
        assert "approval sudah tercatat" in resp.json()["detail"]
    finally:
        _cleanup(decision_id)


def test_verify_setelah_kuorum_tetap_409(client, akun):
    kepala, gizi = akun
    decision_id = None
    try:
        decision_id = _siapkan(client, kepala)
        assert _approve(client, decision_id, gizi).status_code == 200
        assert _approve(client, decision_id, kepala).status_code == 200
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, kepala),
        )
        assert resp.status_code == 409, resp.text
    finally:
        _cleanup(decision_id)
