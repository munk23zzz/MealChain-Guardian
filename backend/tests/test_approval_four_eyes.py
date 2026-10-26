"""Four-eyes ditegakkan database (migrasi 030, 23 Okt 2026).

Masalah yang ditutup: quorum dihitung dari BARIS approval, bukan dari user unik.
Sebelum kunci unik `(decision_id, approved_by)`, satu akun yang mengirim dua
permintaan approve dapat memenuhi syarat "dua approver role berbeda" — empat
mata runtuh tanpa satu baris kode pun yang salah.

Kontrak yang dikunci berkas ini:
1. Akun yang sama tidak bisa memberi keputusan kedua → 409, dan jumlah baris
   approval tidak bertambah.
2. Kuorum dua approver role berbeda tetap berjalan normal (FLAGGED), dan
   keputusan baru `approved` setelah keduanya memberi suara.
3. Database menolak duplikat walau API dilewati (unique index benar-benar ada).
"""

import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.api.actions import get_verifier_chain
from app.main import app
from tests.dsn import DSN_ASYNC

DB_URL = DSN_ASYNC.replace("+asyncpg", "+psycopg")
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
    email = f"{role}-{uuid.uuid4().hex[:8]}@four-eyes.local"
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
        return {"email": email, "password": PW, "role": role}
    finally:
        engine.dispose()


def _drop(user: dict) -> None:
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": user["email"]})
    finally:
        engine.dispose()


def _force_verdict(verdict: str):
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


def _bersihkan(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            # Ledger append-only: blok dibiarkan, hanya baris aksi yang dibuang.
            conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _siapkan_dan_verifikasi(client, kepala: dict, verdict: str, headers: dict) -> str:
    did = None
    resp = client.post(
        "/decisions", json={"recommendation": RECOMMENDATION}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    did = resp.json()["decision_id"]
    resp = client.post("/actions/propose", json={"decision_id": did}, headers=headers)
    assert resp.status_code == 201, resp.text
    resp = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
    assert resp.status_code == 200, resp.text
    return did


def test_akun_sama_tidak_bisa_memberi_keputusan_dua_kali(client):
    kepala = _mk_user("sppg_head")
    pulihkan = _force_verdict("CONSISTENT")
    did = None
    try:
        headers = _login(client, kepala)
        did = _siapkan_dan_verifikasi(client, kepala, "CONSISTENT", headers)

        pertama = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=headers,
        )
        assert pertama.status_code == 200, pertama.text
        # Keputusan operasional (transfer) tetap menuntut dua role berbeda —
        # satu approval belum memenuhi kuorum. Status `verifier_flagged` (bukan
        # `pending_approval`) muncul karena guard certified menurunkan CONSISTENT
        # model untuk freshness 0,82 data demo — AUD-9A-03.
        assert pertama.json()["decision_status"] == "verifier_flagged"
        assert _jumlah_approval(did) == 1

        kedua = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=headers,
        )
        assert kedua.status_code == 409, kedua.text
        assert "empat mata" in kedua.json()["detail"].lower()
        assert _jumlah_approval(did) == 1, "approval kedua tidak boleh tercatat"

        # Database menolak duplikat walau API dilewati.
        engine = _db()
        try:
            with engine.begin() as conn:
                user_id = conn.execute(
                    text("SELECT id FROM users WHERE email = :e"), {"e": kepala["email"]}
                ).scalar_one()
                with pytest.raises(IntegrityError):
                    conn.execute(
                        text(
                            "INSERT INTO approvals (decision_id, approved_by, approved) "
                            "VALUES (:d, :u, true)"
                        ),
                        {"d": did, "u": user_id},
                    )
        finally:
            engine.dispose()
    finally:
        pulihkan()
        _bersihkan(did)
        _drop(kepala)


def test_kuorum_dua_role_berbeda_tetap_jalan(client):
    kepala = _mk_user("sppg_head")
    ahli_gizi = _mk_user("sppg_nutritionist")
    pulihkan = _force_verdict("FLAGGED")
    did = None
    try:
        headers_kepala = _login(client, kepala)
        did = _siapkan_dan_verifikasi(client, kepala, "FLAGGED", headers_kepala)

        satu = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=headers_kepala,
        )
        assert satu.status_code == 200, satu.text
        assert satu.json()["approval_state"]["satisfied"] is False
        assert satu.json()["decision_status"] != "approved"

        # Akun yang sama mencoba lagi: ditolak, kuorum tidak bertambah.
        ulang = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=headers_kepala,
        )
        assert ulang.status_code == 409, ulang.text

        dua = client.post(
            "/actions/approve",
            json={"decision_id": did, "approved": True},
            headers=_login(client, ahli_gizi),
        )
        assert dua.status_code == 200, dua.text
        assert dua.json()["approval_state"]["satisfied"] is True
        assert dua.json()["decision_status"] == "approved"
        assert _jumlah_approval(did) == 2
        assert _status(did) == "approved"
    finally:
        pulihkan()
        _bersihkan(did)
        _drop(kepala)
        _drop(ahli_gizi)
