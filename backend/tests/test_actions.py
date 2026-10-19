"""Test /actions lifecycle (S3-01/S3-11, TDD).

propose → verify → approve → execute. Tanpa eksekusi otomatis.
Semua user test dibuat sendiri + dibersihkan; decision test dibuat via
POST /decisions lalu dibersihkan.
"""

import uuid
from datetime import datetime, timedelta, timezone

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


def _mk_user(role: str, location_name: str | None = None) -> dict:
    engine = _db()
    user_id = str(uuid.uuid4())
    email = f"{role}-{uuid.uuid4().hex[:8]}@test.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    try:
        with engine.begin() as conn:
            loc_id = None
            if location_name:
                loc_id = conn.execute(
                    text("SELECT id FROM locations WHERE name = :n"),
                    {"n": location_name},
                ).scalar_one_or_none()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (:id, :n, :e, :h, :r, :l)"
                ),
                {"id": user_id, "n": f"T {role}", "e": email, "h": digest, "r": role, "l": loc_id},
            )
        return {"id": user_id, "email": email, "password": PW, "role": role}
    finally:
        engine.dispose()


def _drop_user(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


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


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _login(client, user) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _ikat_binding(decision_id: str) -> None:
    """Ikat keputusan ke SATU batch Cianjur/telur lewat bukti `allocation_binding`.

    Sejak dataset 19 Okt 2026 Cianjur punya EMPAT pemasok telur, jadi
    `resolve_binding` — yang memang menolak menebak pemasok — menjawab
    `supplier_unknown` untuk keputusan tanpa binding. Tes ini menguji alur
    approve/execute, bukan penebakan itu, jadi batch sumbernya diikat eksplisit
    dengan bentuk yang SAMA seperti penulis produksi (`allocation_binding: true`
    di akar payload + `supplier_id`/`batch_ids`).
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


def _mk_decision(client, user=None) -> str:
    """Buat decision target Jakarta via API (auth kontrak baru S4-00).

    POST /decisions kini butuh JWT sppg_head/sppg_nutritionist dan target
    lokasi = lokasi user. RECOMMENDATION bawaan target Jakarta; user tanpa
    lokasi (mis. monitor) dipinjamkan lokasi Jakarta agar tidak memecah
    test baca/monitor.
    """
    if user is None:
        user = _mk_user("sppg_head", "Jakarta")
    elif user["role"] == "bgn_monitor":
        user = {**user, "role": "sppg_head"}
    headers = _login(client, user)
    resp = client.post(
        "/decisions", json={"recommendation": RECOMMENDATION}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    did = resp.json()["decision_id"]
    _ikat_binding(did)
    return did


def _cleanup(decision_id: str | None, emails: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM decision_evidence WHERE decision_id = :d"),
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
    for e in emails:
        _drop_user(e)


def test_actions_propose_requires_auth(client):
    resp = client.post(
        "/actions/propose", json={"decision_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 401


def test_actions_propose_then_requirement_is_unverified(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        resp = client.post(
            "/actions/propose",
            json={
                "decision_id": decision_id,
                "supplier_id": None,
                "material_number": "MAT-TELUR-JKT",
            },
            headers=_login(client, head),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "pending_approval"
        assert body["verified"] is False
        # Belum terverifikasi → requirement konservatif = unavailable (dual approval)
        assert body["approval_requirement"]["min_approvals"] == 2
    finally:
        _cleanup(decision_id, [head["email"]])


def test_execute_rejects_unverified_decision(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        assert "verifikasi" in resp.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])


def test_bgn_monitor_cannot_approve_or_execute(client):
    monitor = _mk_user("bgn_monitor")
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, monitor),
        )
        assert resp.status_code == 403
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, monitor),
        )
        assert resp.status_code == 403
    finally:
        _cleanup(decision_id, [monitor["email"], head["email"]])


def _verify_decision(decision_id: str, verdict: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE decisions SET verified_by = 'verifier-agent', "
                    "verifier_note = :v WHERE id = :d"
                ),
                {"v": verdict, "d": decision_id},
            )
    finally:
        engine.dispose()


def test_execute_success_operasional_butuh_dua_approval_writes_mock_po(client):
    head = _mk_user("sppg_head", "Jakarta")
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _verify_decision(decision_id, "consistent")
        # Belum ada approval → execute ditolak
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        # PLAN.md §13.3: transfer butuh DUA approval (Head lalu Nutritionist),
        # meski verdict verifier CONSISTENT.
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409, "approval Nutritionist belum ada"
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, nutritionist),
        )
        assert resp.status_code == 200, resp.text
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data_source"] == "MOCK"
        assert body["po_number"].startswith("MC-")
        # PO mock tertulis + decision executed
        engine = _db()
        with engine.begin() as conn:
            po = conn.execute(
                text(
                    "SELECT status, decision_id FROM sap_mock_purchase_orders "
                    "WHERE decision_id = :d"
                ),
                {"d": decision_id},
            ).mappings().first()
            assert po is not None
            assert po["status"] == "submitted"
            status = conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"), {"d": decision_id}
            ).scalar_one()
            assert status == "executed"
        engine.dispose()
        # executed → tidak bisa dieksekusi lagi
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_execute_flagged_requires_both_roles(client):
    head = _mk_user("sppg_head", "Jakarta")
    # Ruling 2026-10-14 §3: approver kedua wajib berasal dari SPPG yang SAMA
    # dengan lokasi target. Ahli gizi di Bogor tidak lagi boleh menyetujui
    # keputusan yang menyasar Jakarta — aturan itu baru ditegakkan di jalur
    # tulis /actions/* pada 2026-10-17, jadi fixture di sini (dulu Bogor)
    # dipindah ke Jakarta supaya yang diuji tetap "dua role", bukan cakupan.
    nutritionist = _mk_user("sppg_nutritionist", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _verify_decision(decision_id, "flagged")
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        # Hanya sppg_head → masih ditolak
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, nutritionist),
        )
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
    finally:
        _cleanup(decision_id, [head["email"], nutritionist["email"]])


def test_execute_expired_decision_rejected(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _verify_decision(decision_id, "consistent")
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        engine = _db()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE decisions SET expires_at = :t WHERE id = :d"
                ),
                {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "d": decision_id},
            )
        engine.dispose()
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
        assert "expired" in resp.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])


def test_execute_rejected_decision_blocked(client):
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _verify_decision(decision_id, "consistent")
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": False, "comment": "tidak setuju"},
            headers=_login(client, head),
        )
        engine = _db()
        status = engine.begin() and None
        with engine.begin() as conn:
            status = conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"), {"d": decision_id}
            ).scalar_one()
        engine.dispose()
        assert status == "rejected"
        resp = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409
    finally:
        _cleanup(decision_id, [head["email"]])


# --- Ruling Owner 2026-10-16: penjaga kedaluwarsa per endpoint ---


def _expire(decision_id: str, minutes: int = 1) -> None:
    """Mundurkan tenggat keputusan supaya benar-benar kedaluwarsa."""
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE decisions SET expires_at = :t WHERE id = :d"),
                {
                    "t": datetime.now(timezone.utc) - timedelta(minutes=minutes),
                    "d": decision_id,
                },
            )
    finally:
        engine.dispose()


def test_verify_expired_decision_rejected(client):
    """Keputusan 2b: /actions/verify dulu TIDAK memeriksa kedaluwarsa sama sekali —
    hanya status pra-approval — sehingga verifikasi pada keputusan yang sudah lewat
    tenggat diterima, berbeda dari /actions/propose yang menolaknya tanpa syarat.
    Penjaganya sekarang disamakan dengan propose."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _expire(decision_id)
        resp = client.post(
            "/actions/verify", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 409, resp.text
        assert "expired" in resp.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])


def test_verify_valid_decision_still_accepted(client):
    """Penjaga baru jangan sampai kebablasan: yang belum lewat tenggat tetap bisa
    diverifikasi (verifikasi adalah penilaian, bukan persetujuan)."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        resp = client.post(
            "/actions/verify", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["verdict"] in {"CONSISTENT", "FLAGGED", "UNAVAILABLE"}
    finally:
        _cleanup(decision_id, [head["email"]])


def test_approve_expired_ordinary_decision_accepted(client):
    """Keputusan 1b: read model sekarang mengikuti ENDPOINT, dan endpoint hanya
    menjaga kedaluwarsa untuk jenis administratif. Jadi approval pada keputusan
    kedaluwarsa jenis biasa memang diterima — sengaja, bukan kelalaian.

    Batasnya diuji juga: eksekusinya TETAP ditolak, karena /actions/execute
    memeriksa kedaluwarsa tanpa syarat. Artinya keputusan ini bisa disetujui tapi
    tidak bisa dijalankan, dan itu memang keadaan yang dipilih owner."""
    head = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client)
    try:
        client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, head),
        )
        _verify_decision(decision_id, "consistent")
        _expire(decision_id)
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, head),
        )
        assert resp.status_code == 200, resp.text
        eksekusi = client.post(
            "/actions/execute", json={"decision_id": decision_id},
            headers=_login(client, head),
        )
        assert eksekusi.status_code == 409, eksekusi.text
        assert "expired" in eksekusi.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [head["email"]])
