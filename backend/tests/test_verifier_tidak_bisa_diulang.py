"""Verdict audit tidak boleh ditimpa (audit M2, 18 Okt 2026).

Masalah yang ditutup: `/actions/verify` boleh dipanggil berulang selama belum ada
approval. Setiap panggilan menimpa `verifier_note`, tanpa baris jejak dan tanpa
blok ledger. Artinya hasil audit bisa "diulang sampai menyenangkan" — FLAGGED
bisa berubah jadi CONSISTENT, dan itu MENURUNKAN syarat persetujuan. Di depan
auditor, catatan yang bisa diedit ulang bukan bukti.

Aturan sekarang:
1. Verdict yang sudah tercatat (consistent/flagged) bersifat final: verify
   berikutnya 409 "verdict sudah tercatat", `verifier_note` tidak berubah.
2. Retry hanya sah bila percobaan sebelumnya tidak menghasilkan verdict
   (unavailable) — provider boleh pulih.
3. Setiap percobaan meninggalkan satu baris `agent_traces` VERIFY (siapa, verdict,
   provider, alasan), sehingga riwayat percobaan terbaca.
4. Verdict yang TERCATAT menambah satu blok ledger `action='verify'`; percobaan
   tanpa verdict tidak menambah blok (tidak ada perubahan keadaan untuk dicatat).
"""

import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.actions import get_verifier_chain
from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = (
    DSN_ASYNC
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
    email = f"{role}-{uuid.uuid4().hex[:8]}@uji-verdict.local"
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
                {"n": f"U {role}", "e": email, "h": digest, "r": role, "l": loc},
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


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _kunci_verdict(verdict: str):
    def _chain():
        return [
            (
                "test_provider",
                lambda prompt: json.dumps({"verdict": verdict, "reason": "uji"}),
                "test",
            )
        ]

    app.dependency_overrides[get_verifier_chain] = _chain
    return lambda: app.dependency_overrides.pop(get_verifier_chain, None)


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


def _baris(decision_id: str) -> dict:
    engine = _db()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT verified_by, verifier_note, status FROM decisions WHERE id = :d"
                ),
                {"d": decision_id},
            ).mappings().one()
        return dict(row)
    finally:
        engine.dispose()


def _hitung(sql: str, params: dict) -> int:
    engine = _db()
    try:
        with engine.connect() as conn:
            return int(conn.execute(text(sql), params).scalar_one())
    finally:
        engine.dispose()


def _bersihkan(decision_id: str | None) -> None:
    if not decision_id:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
    finally:
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_verdict_tercatat_tidak_bisa_ditimpa(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _kunci_verdict("CONSISTENT")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        pertama = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert pertama.status_code == 200, pertama.text
        assert pertama.json()["recorded"] is True
        assert _baris(did)["verifier_note"] == "consistent"

        # Provider sekarang akan menjawab FLAGGED; hasilnya TIDAK boleh menimpa.
        restore()
        restore = _kunci_verdict("FLAGGED")
        kedua = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert kedua.status_code == 409, kedua.text
        assert "verdict sudah tercatat" in kedua.json()["detail"].lower()
        baris = _baris(did)
        assert baris["verifier_note"] == "consistent"
        assert baris["status"] == "pending_approval"
    finally:
        restore()
        _bersihkan(did)
        _drop(kepala["email"])


def test_retry_setelah_unavailable_tetap_boleh(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _kunci_verdict("UNAVAILABLE")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        satu = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert satu.status_code == 200, satu.text
        assert satu.json()["recorded"] is False
        assert _baris(did)["verified_by"] is None

        restore()
        restore = _kunci_verdict("CONSISTENT")
        dua = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert dua.status_code == 200, dua.text
        assert dua.json()["recorded"] is True
        assert _baris(did)["verifier_note"] == "consistent"
    finally:
        restore()
        _bersihkan(did)
        _drop(kepala["email"])


def test_setiap_percobaan_meninggalkan_trace_verify(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _kunci_verdict("UNAVAILABLE")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        restore()
        restore = _kunci_verdict("CONSISTENT")
        client.post("/actions/verify", json={"decision_id": did}, headers=headers)

        jumlah = _hitung(
            "SELECT count(*) FROM agent_traces WHERE decision_id = :d AND step_name = 'VERIFY'",
            {"d": did},
        )
        assert jumlah == 2, f"harus ada 2 baris VERIFY (2 percobaan), dapat {jumlah}"
        terakhir = _hitung(
            "SELECT count(*) FROM agent_traces WHERE decision_id = :d AND step_name = 'VERIFY' "
            "AND output_summary->>'verdict' = 'CONSISTENT'",
            {"d": did},
        )
        assert terakhir == 1
    finally:
        restore()
        _bersihkan(did)
        _drop(kepala["email"])


def test_verdict_tercatat_menambah_satu_blok_ledger(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _kunci_verdict("UNAVAILABLE")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        sebelum = _hitung("SELECT count(*) FROM ledger_blocks", {})
        client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        setelah_unavailable = _hitung("SELECT count(*) FROM ledger_blocks", {})
        assert setelah_unavailable == sebelum, "percobaan tanpa verdict tidak boleh menambah blok"

        restore()
        restore = _kunci_verdict("CONSISTENT")
        client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        sesudah = _hitung("SELECT count(*) FROM ledger_blocks", {})
        assert sesudah == sebelum + 1
        blok = _hitung(
            "SELECT count(*) FROM ledger_blocks WHERE action = 'verify' "
            "AND entity_id = :d AND payload::jsonb->>'verdict' = 'CONSISTENT'",
            {"d": did},
        )
        assert blok == 1
    finally:
        restore()
        _bersihkan(did)
        _drop(kepala["email"])
