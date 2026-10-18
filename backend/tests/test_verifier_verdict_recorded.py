"""Verdict verifier: dicatat hanya bila ADA hasil audit (audit M1, 18 Okt 2026).

Masalah: `/actions/verify` selalu menulis `verified_by`, termasuk saat provider
menjawab UNAVAILABLE. `verified_by` lalu dipakai sebagai pagar approve, jadi
"terverifikasi" bisa berarti "belum pernah dinilai" — bukti yang tidak bisa
dipertahankan di depan auditor.

Aturan sekarang:
1. Verdict UNAVAILABLE tidak menulis `verified_by`; respons menyatakan
   `recorded: false` dan `verifier_note = "unavailable"`.
2. Verdict CONSISTENT/FLAGGED dicatat seperti biasa (`recorded: true`).
3. Approve mensyaratkan verdict hasil audit, bukan sekadar baris verifikasi.
4. Konteks verifier diisi dari data kanonik (safety/freshness batch sumber,
   kandidat dari trace OPTIMIZE, logistik dari cost breakdown) supaya model
   benar-benar punya bahan untuk menilai — bukan null semua.
"""

import asyncio
import json
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

from app.api.actions import _verifier_ctx, get_verifier_chain
from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.main import app
from app.models import Commodity, Decision

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
    email = f"{role}-{uuid.uuid4().hex[:8]}@verdict.local"
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


def _login(client: TestClient, user: dict) -> dict:
    resp = client.post(
        "/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _status_verify(decision_id: str) -> dict:
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


def _cleanup(decision_id: str | None) -> None:
    if not decision_id:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
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


def test_unavailable_tidak_mencatat_verified_by(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _force_verdict("UNAVAILABLE")
    try:
        did = _siapkan(client, kepala)
        resp = client.post(
            "/actions/verify", json={"decision_id": did}, headers=_login(client, kepala)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["recorded"] is False
        baris = _status_verify(did)
        assert baris["verified_by"] is None
        assert baris["verifier_note"] == "unavailable"
    finally:
        restore()
        _cleanup(did)
        _drop(kepala["email"])


def test_unavailable_memblokir_approve_dengan_alasan_jelas(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _force_verdict("UNAVAILABLE")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        resp = client.post(
            "/actions/approve", json={"decision_id": did, "approved": True}, headers=headers
        )
        assert resp.status_code == 409, resp.text
        assert "belum diverifikasi" in resp.json()["detail"].lower()
    finally:
        restore()
        _cleanup(did)
        _drop(kepala["email"])


def test_consistent_mencatat_verified_by(client):
    kepala = _mk_user("sppg_head")
    did = None
    restore = _force_verdict("CONSISTENT")
    try:
        did = _siapkan(client, kepala)
        headers = _login(client, kepala)
        resp = client.post("/actions/verify", json={"decision_id": did}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["recorded"] is True
        baris = _status_verify(did)
        assert baris["verified_by"] is not None
        assert baris["verifier_note"] == "consistent"
        ok = client.post(
            "/actions/approve", json={"decision_id": did, "approved": True}, headers=headers
        )
        assert ok.status_code == 200, ok.text
    finally:
        restore()
        _cleanup(did)
        _drop(kepala["email"])


def test_ctx_verifier_membawa_dimensi_kanonik():
    """Konteks harus berisi safety/freshness/kandidat/logistik dari DB, bukan null.

    Tanpa ini model hanya bisa menjawab UNAVAILABLE — itulah akar M1.
    """

    async def _ambil():
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as db:
                row = (
                    await db.execute(
                        text(
                            "SELECT d.id FROM decisions d "
                            "JOIN batches b ON b.location_id = d.source_location_id "
                            "AND b.commodity_id = d.commodity_id "
                            "WHERE d.cost_breakdown::jsonb ? 'candidate_score' "
                            "LIMIT 1"
                        )
                    )
                ).first()
                if row is None:
                    pytest.skip("tidak ada keputusan dengan batch sumber di DB")
                decision = (
                    await db.execute(select(Decision).where(Decision.id == row[0]))
                ).scalar_one()
                commodity = (
                    await db.execute(
                        select(Commodity).where(Commodity.id == decision.commodity_id)
                    )
                ).scalar_one_or_none()
                return await _verifier_ctx(db, decision, commodity)
        finally:
            await engine.dispose()

    ctx = asyncio.run(_ambil())
    assert ctx["safety_status"] is not None, ctx
    assert ctx["freshness_score"] is not None, ctx
    assert isinstance(ctx["candidates"], list) and ctx["candidates"], ctx
    # Logistik opsional: hanya diisi bila snapshot biaya menyimpan komponen
    # supplier leg atau cache rute OSRM punya pasangan koordinat ini. Yang
    # dilarang adalah mengarangnya — jadi None sah, asal kuncinya ada.
    assert "logistics" in ctx, ctx
    assert ctx["cost"]["safe_delivered_cost"] is not None
