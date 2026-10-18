"""Persetujuan wajib setelah verifikasi (Fase 0 butir 2, 18 Okt 2026).

Masalah yang ditutup (audit BLOCKER A2): `approve_action` tidak memeriksa
`verified_by`. Keputusan bisa di-approve lebih dulu, dan setelah kuorum penuh
statusnya menjadi `approved` — status yang TIDAK menerima `/actions/verify`
lagi. `execute` lalu menolak selamanya dengan "belum diverifikasi": jalan
buntu tanpa jalan keluar lewat UI.

Aturan sekarang:
1. `approve` (setuju) ditolak 409 bila `verified_by` masih kosong, dengan
   pesan yang menyebut langkah berikutnya.
2. Read model menyatakan `can_approve=False` + alasan "decision belum
   terverifikasi", sehingga tombol Setuju tidak ditawarkan.
3. MENOLAK tetap boleh tanpa verifikasi — penolakan justru menghentikan
   keputusan, tidak butuh verdict.
4. Setelah verifikasi dicatat, approve kembali normal (200).
"""

import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

PW = "TestPass#2026"

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


def _mk_user(role: str) -> dict:
    email = f"{role}-{uuid.uuid4().hex[:8]}@verifikasi-wajib.local"
    digest = bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()
    engine = _db()
    try:
        with engine.begin() as conn:
            loc = conn.execute(
                text("SELECT id FROM locations WHERE name = 'Jakarta'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                    "VALUES (gen_random_uuid(), :n, :e, :h, :r, :l)"
                ),
                {"n": f"T {role}", "e": email, "h": digest, "r": role, "l": loc},
            )
        return {"email": email, "password": PW}
    finally:
        engine.dispose()


def _drop(email: str) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})
    finally:
        engine.dispose()


def _force_verdict(verdict: str):
    """Kunci verdict provider: tes ukur pagar server, bukan ketersediaan LLM."""

    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: json.dumps({"verdict": verdict, "reason": "uji verdict"}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain
    return lambda: app.dependency_overrides.pop(get_verifier_chain, None)


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _status(decision_id: str) -> str:
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"), {"d": decision_id}
            ).scalar_one()
    finally:
        engine.dispose()


def _jumlah_approval(decision_id: str) -> int:
    engine = _db()
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT count(*) FROM approvals WHERE decision_id = :d"),
                {"d": decision_id},
            ).scalar_one()
    finally:
        engine.dispose()


def _cleanup(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            # Ledger append-only: blok dibiarkan, hanya baris aksi yang dibuang.
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _siapkan(client, kepala) -> str:
    resp = client.post(
        "/decisions", json={"recommendation": RECOMMENDATION}, headers=_login(client, kepala)
    )
    assert resp.status_code == 201, resp.text
    did = resp.json()["decision_id"]
    resp = client.post(
        "/actions/propose", json={"decision_id": did}, headers=_login(client, kepala)
    )
    assert resp.status_code == 201, resp.text
    return did


def test_approve_sebelum_verifikasi_ditolak_dengan_pesan_jelas(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _siapkan(client, kepala)
        resp = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=_login(client, kepala),
        )
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"].lower()
        assert "belum diverifikasi" in detail, detail
        assert "verifikasi" in detail
        # Tidak ada jejak approval yang tercatat, status tidak berubah.
        assert _status(did) == "pending_approval"
        assert _jumlah_approval(did) == 0
    finally:
        _cleanup(did)
        _drop(kepala["email"])


def test_ringkasan_menyembunyikan_setuju_sebelum_verifikasi(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _siapkan(client, kepala)
        resp = client.get(
            f"/decisions/{did}/approval-summary", headers=_login(client, kepala)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["can_approve"] is False
        assert body["can_reject"] is True
        assert "decision belum terverifikasi" in body["blocking_reasons"]
    finally:
        _cleanup(did)
        _drop(kepala["email"])


def test_setelah_verifikasi_approve_lolos(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _force_verdict("CONSISTENT")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        resp = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["recorded"] is True
        resp = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert _jumlah_approval(did) == 1
    finally:
        restore()
        _cleanup(did)
        _drop(kepala["email"])


def test_menolak_tetap_boleh_tanpa_verifikasi(client):
    kepala = _mk_user("sppg_head")
    did = None
    try:
        did = _siapkan(client, kepala)
        resp = client.post(
            "/actions/approve",
            json={
                "decision_id": did,
                "approved": False,
                "comment": "harga di atas pagu",
            },
            headers=_login(client, kepala),
        )
        assert resp.status_code == 200, resp.text
        assert _status(did) == "rejected"
    finally:
        _cleanup(did)
        _drop(kepala["email"])
