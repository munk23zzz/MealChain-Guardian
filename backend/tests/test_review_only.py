"""Temuan `price_anomaly` lahir sebagai `review_only` (audit M6, 18 Okt 2026).

Masalah: Event 2 membuat keputusan `price_anomaly` berstatus `proposed` tanpa
`quantity_kg`. `/actions/propose` menawarkannya sebagai usulan transfer, tetapi
`/actions/execute` selalu menolak (422 "quantity decision tidak valid") dan tidak
ada jalan menutupnya. Keputusan seperti itu menggantung selamanya di antrean.

Aturan sekarang: temuan lahir `review_only` — terminal, tidak menuntut approval,
tidak bisa dieksekusi, tetapi tetap terbaca sebagai bukti. Semua endpoint tulis
menolaknya dengan alasan yang menyebut statusnya.
"""

import json
import urllib.error
import urllib.request
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")
BASE = "http://localhost:8000"


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


def _login_demo(email: str = "sppg.head@demo.local") -> dict:
    """Login akun demo lewat HTTP; sandi dibaca dari seed (tidak dicetak)."""
    from app.seed.seed_data import DEMO_USERS

    sandi = next(u["password"] for u in DEMO_USERS if u["email"] == email)
    req = urllib.request.Request(
        BASE + "/auth/login",
        data=json.dumps({"email": email, "password": sandi}).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return {"Authorization": f"Bearer {json.loads(r.read())['access_token']}"}


def _buat_quote_sintetis() -> tuple[str, str]:
    """Quote 2x harga acuan → Event 2 pasti 'anomaly'."""
    baris = _exec(
        "SELECT c.id, l.id, s.id, "
        "(SELECT price_per_kg FROM price_signals WHERE commodity_id = c.id "
        " AND source = 'pihps_reference' ORDER BY recorded_at DESC LIMIT 1) AS ref "
        "FROM commodities c, locations l, suppliers s "
        "WHERE c.name = 'telur' AND l.name = 'Cianjur' AND s.name = 'Supplier A Cianjur'"
    )
    assert baris, "butuh komoditas/lokasi/pemasok kanonik"
    komoditas, lokasi, supplier, ref = baris[0]
    assert ref is not None, "butuh harga acuan pihps_reference untuk telur"
    quote_id = _exec(
        "INSERT INTO price_signals (location_id, commodity_id, price_per_kg, recorded_at, "
        "source, supplier_id, origin) VALUES (:l, :c, :p, now(), 'supplier_quote', :s, 'demo') "
        "RETURNING id",
        {"l": lokasi, "c": komoditas, "p": ref * 2, "s": supplier},
    )[0][0]
    jakarta = _exec("SELECT id FROM locations WHERE name = 'Jakarta'")[0][0]
    return str(quote_id), str(jakarta)


def _event2(headers: dict) -> dict:
    quote_id, target = _buat_quote_sintetis()
    req = urllib.request.Request(
        BASE + "/events/price-anomaly",
        data=json.dumps(
            {
                "quote_id": quote_id,
                "target_location_id": target,
                "operation_key": str(uuid.uuid4()),
            }
        ).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", headers["Authorization"])
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read())
    body["_quote_id"] = quote_id
    return body


def _bersihkan(decision_id: str | None, quote_id: str | None) -> None:
    if decision_id:
        _exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})
    if quote_id:
        _exec("DELETE FROM price_signals WHERE id = :q", {"q": quote_id})


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_event2_menghasilkan_review_only():
    headers = _login_demo()
    body = _event2(headers)
    did = body.get("decision_id")
    try:
        assert body["status"] != "no_anomaly", body
        assert did, body
        baris = _exec("SELECT status FROM decisions WHERE id = :d", {"d": did})
        assert baris[0][0] == "review_only", baris
        with TestClient(app) as c:
            summary = c.get(f"/decisions/{did}/approval-summary", headers=headers).json()
        assert summary["status"] == "review_only"
        assert summary["can_execute"] is False
        assert summary["can_approve"] is False
        assert any("review-only" in r or "tinjauan" in r for r in summary["blocking_reasons"]), (
            summary["blocking_reasons"]
        )
    finally:
        _bersihkan(did, body.get("_quote_id"))


def test_review_only_menolak_semua_jalur_tulis():
    headers = _login_demo()
    body = _event2(headers)
    did = body.get("decision_id")
    try:
        assert did, body
        with TestClient(app) as c:
            for path, payload in (
                ("/actions/propose", {"decision_id": did}),
                ("/actions/verify", {"decision_id": did}),
                ("/actions/approve", {"decision_id": did, "approved": True}),
                ("/actions/execute", {"decision_id": did}),
            ):
                resp = c.post(path, json=payload, headers=headers)
                assert resp.status_code == 409, (path, resp.status_code, resp.text)
                detail = str(resp.json().get("detail", "")).lower()
                assert "review" in detail or "tinjauan" in detail, (path, detail)
    finally:
        _bersihkan(did, body.get("_quote_id"))
