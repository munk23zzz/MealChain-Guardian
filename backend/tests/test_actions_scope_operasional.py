"""Cakupan lokasi pada JALUR TULIS keputusan operasional (Ruling 2026-10-14 §3).

Latar temuan (2026-10-17). `require_scope()` hanya dipanggil di cabang
`exclusions.ADMIN_TYPES` (supplier_exclusion / supplier_exclusion_restoration),
sehingga untuk keputusan operasional — `regional_balance`, `safety_disruption`,
`price_anomaly` — keempat endpoint jalur tulis tidak memeriksa lokasi pemakai:

- `/actions/propose`  — tanpa cek scope + tanpa cek kedaluwarsa
- `/actions/verify`   — cek scope hanya untuk tipe administrasi
- `/actions/approve`  — tanpa cek scope, TANPA cek kedaluwarsa, dan TANPA
  penjaga "satu user hanya sekali approve" (ketiganya berada di dalam cabang
  ADMIN_TYPES)
- `/actions/execute`  — tanpa cek scope; matriks approval tidak difilter lokasi,
  sehingga approval dari approver SPPG lain ikut dihitung

Ini bertentangan dengan ruling pemilik 2026-10-14 §3: "Keputusan yang menyasar
SPPG X hanya bisa disetujui oleh approver dari SPPG X (kepala + ahli gizi X).
Verifier kedua tidak lagi boleh berasal dari SPPG lain." Karena itu berkas ini
memaku aturan tersebut pada KEEMPAT endpoint, untuk semua tipe keputusan.

Tes ditulis RED lebih dulu: sebelum perbaikan, semua tes 403 di bawah ini gagal
(server membalas 200/409), dan dua tes 409 (approval ganda + kedaluwarsa) gagal
karena penjaganya hanya ada di cabang administrasi.
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

# Keputusan operasional (BUKAN ADMIN_TYPES) yang menyasar Jakarta.
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
                assert loc_id is not None, f"lokasi seed tidak ada: {location_name}"
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


def _mk_decision(client, user) -> str:
    headers = _login(client, user)
    resp = client.post("/decisions", json={"recommendation": RECOMMENDATION}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["decision_id"]


def _propose(client, decision_id: str, user) -> None:
    """Bawa keputusan ke status `pending_approval` (syarat approve/execute)."""
    resp = client.post(
        "/actions/propose",
        json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
        headers=_login(client, user),
    )
    assert resp.status_code == 201, resp.text


def _verify_decision(decision_id: str, verdict: str) -> None:
    """Tulis verdict verifier langsung ke DB (tanpa jaringan ke provider)."""
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


def _expire_decision(decision_id: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE decisions SET expires_at = now() - interval '1 hour' WHERE id = :d"),
                {"d": decision_id},
            )
    finally:
        engine.dispose()


def _insert_foreign_approval(decision_id: str, user_id: str) -> None:
    """Tiru baris approval LAMA dari approver SPPG lain (mis. data sebelum ruling)."""
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO approvals (id, decision_id, approved_by, approved) "
                    "VALUES (:id, :d, :u, true)"
                ),
                {"id": str(uuid.uuid4()), "d": decision_id, "u": user_id},
            )
    finally:
        engine.dispose()


def _cleanup(decision_id: str | None, emails: list[str]) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM decision_evidence WHERE decision_id = :d"), {"d": decision_id}
            )
            conn.execute(text("DELETE FROM approvals WHERE decision_id = :d"), {"d": decision_id})
            conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
    finally:
        engine.dispose()
    for e in emails:
        _drop_user(e)


# ---------------------------------------------------------------------------
# PROPOSE
# ---------------------------------------------------------------------------


def test_propose_lintas_sppg_ditolak_403(client):
    """Kepala SPPG Bogor tidak boleh mem-propose keputusan yang menyasar Jakarta."""
    jakarta = _mk_user("sppg_head", "Jakarta")
    bogor = _mk_user("sppg_head", "Bogor")
    decision_id = _mk_decision(client, jakarta)
    try:
        # Putar status kembali ke `proposed` agar propose masih sah secara status.
        engine = _db()
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE decisions SET status = 'proposed' WHERE id = :d"), {"d": decision_id}
            )
        engine.dispose()

        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, bogor),
        )
        assert resp.status_code == 403, resp.text
        assert "cakupan lokasi" in resp.json()["detail"] or "scope" in resp.json()["detail"]
    finally:
        _cleanup(decision_id, [jakarta["email"], bogor["email"]])


def test_propose_lokasi_sendiri_tetap_201(client):
    """Kontrol positif: pemakai di lokasi target tidak terhalang perubahan ini."""
    jakarta = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client, jakarta)
    try:
        resp = client.post(
            "/actions/propose",
            json={"decision_id": decision_id, "material_number": "MAT-TELUR-JKT"},
            headers=_login(client, jakarta),
        )
        assert resp.status_code == 201, resp.text
    finally:
        _cleanup(decision_id, [jakarta["email"]])


# ---------------------------------------------------------------------------
# VERIFY
# ---------------------------------------------------------------------------


def test_verify_lintas_sppg_ditolak_403(client):
    """Verifier dari SPPG lain tidak boleh menjalankan verifikasi keputusan ini."""
    jakarta = _mk_user("sppg_head", "Jakarta")
    surabaya = _mk_user("sppg_nutritionist", "Surabaya")
    decision_id = _mk_decision(client, jakarta)
    try:
        resp = client.post(
            "/actions/verify",
            json={"decision_id": decision_id},
            headers=_login(client, surabaya),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [jakarta["email"], surabaya["email"]])


# ---------------------------------------------------------------------------
# APPROVE
# ---------------------------------------------------------------------------


def test_approve_lintas_sppg_ditolak_403(client):
    jakarta = _mk_user("sppg_head", "Jakarta")
    bandung = _mk_user("sppg_head", "Bandung")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "consistent")
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, bandung),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [jakarta["email"], bandung["email"]])


def test_approve_dua_kali_user_sama_ditolak_409(client):
    """Satu user tidak boleh menjadi dua approver (jejak approval harus dua orang)."""
    jakarta = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "consistent")
        headers = _login(client, jakarta)
        pertama = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=headers,
        )
        assert pertama.status_code == 200, pertama.text
        kedua = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=headers,
        )
        assert kedua.status_code == 409, kedua.text
        assert "tercatat" in kedua.json()["detail"]
    finally:
        _cleanup(decision_id, [jakarta["email"]])


def test_approve_setelah_kedaluwarsa_tetap_diterima_keputusan_owner_1b(client):
    """Keputusan owner 1b: approve pada keputusan kedaluwarsa JENIS BIASA tetap
    diterima; eksekusinya tetap ditolak (`/actions/execute` memeriksa kedaluwarsa
    tanpa syarat).

    Tes ini menjaga agar penjaga cakupan + duplikat yang baru dinaikkan ke jalur
    umum TIDAK diam-diam mengubah kebijakan kedaluwarsa yang sudah diputuskan
    owner (`test_approve_expired_ordinary_decision_accepted` di test_actions.py).
    """
    jakarta = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "consistent")
        _expire_decision(decision_id)
        resp = client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, jakarta),
        )
        assert resp.status_code == 200, resp.text
        eksekusi = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, jakarta),
        )
        assert eksekusi.status_code == 409, eksekusi.text
        assert "expired" in eksekusi.json()["detail"].lower()
    finally:
        _cleanup(decision_id, [jakarta["email"]])


# ---------------------------------------------------------------------------
# EXECUTE
# ---------------------------------------------------------------------------


def test_execute_lintas_sppg_ditolak_403(client):
    jakarta = _mk_user("sppg_head", "Jakarta")
    medan = _mk_user("sppg_head", "Medan")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "consistent")
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, jakarta),
        )
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, medan),
        )
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(decision_id, [jakarta["email"], medan["email"]])


def test_matriks_abaikan_approval_lokasi_lain_409(client):
    """Approval dari approver SPPG lain TIDAK boleh memenuhi matriks.

    Baris approval disisipkan langsung ke DB (meniru data lama), karena jalur
    HTTP-nya sudah ditolak 403 oleh tes di atas.
    """
    jakarta = _mk_user("sppg_head", "Jakarta")
    bogor = _mk_user("sppg_nutritionist", "Bogor")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "flagged")  # butuh head DAN nutritionist
        _insert_foreign_approval(decision_id, jakarta["id"])  # head Jakarta (sah)
        _insert_foreign_approval(decision_id, bogor["id"])  # nutritionist Bogor (luar scope)
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, jakarta),
        )
        assert resp.status_code == 409, resp.text
        assert "scope" in resp.json()["detail"]
    finally:
        _cleanup(decision_id, [jakarta["email"], bogor["email"]])


def test_execute_lokasi_sendiri_lolos_sampai_provider(client):
    """Kontrol positif: approver lokasi target tetap bisa menembus gerbang scope."""
    jakarta = _mk_user("sppg_head", "Jakarta")
    decision_id = _mk_decision(client, jakarta)
    try:
        _propose(client, decision_id, jakarta)
        _verify_decision(decision_id, "consistent")
        client.post(
            "/actions/approve",
            json={"decision_id": decision_id, "approved": True},
            headers=_login(client, jakarta),
        )
        resp = client.post(
            "/actions/execute",
            json={"decision_id": decision_id},
            headers=_login(client, jakarta),
        )
        # 200 = PO mock tertulis; 409 hanya boleh dari gerbang LAIN (mis. safety
        # revalidation), bukan dari cakupan lokasi.
        assert resp.status_code == 200, resp.text
        assert resp.json()["data_source"] == "MOCK"
    finally:
        _cleanup(decision_id, [jakarta["email"]])
