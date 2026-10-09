"""P2/P3 (paket 1-6, keputusan Roy 2026-10-09): dossier konten-addressed
+ ECDSA secp256k1 signing.

Kontrak:
- GET /decisions/{id}/dossier → 200 dengan content_address (mc1-...),
  signature (state signed/unsigned jujur), verify True saat signed.
- Address berubah bila dossier berubah (konten-addressed).
- Unit: content_address deterministik & berbeda utk payload beda;
  sign/verify round-trip; tanpa kunci → unsigned (tidak ada tanda palsu).
"""

import os
import uuid

import pytest


def test_content_address_deterministic_and_distinct():
    from app.services.dossier_service import content_address

    a = content_address({"x": 1})
    b = content_address({"x": 1})
    c = content_address({"x": 2})
    assert a == b
    assert a != c
    assert a.startswith("mc1-")


def test_sign_verify_roundtrip(monkeypatch):
    from app.services import signing_service

    key = os.urandom(32).hex()
    monkeypatch.setenv("SIGNING_KEY_HEX", key)
    payload = b"dossier-payload"
    sig = signing_service.sign_payload(payload)
    assert sig["state"] == "signed"
    assert signing_service.verify_signature(
        payload, sig["signature"], sig["public_key"]
    )
    assert not signing_service.verify_signature(
        b"tampered", sig["signature"], sig["public_key"]
    )


def test_sign_without_key_is_honest_unsigned(monkeypatch):
    from app.services import signing_service

    monkeypatch.delenv("SIGNING_KEY_HEX", raising=False)
    sig = signing_service.sign_payload(b"no-key")
    assert sig["state"] == "unsigned"
    assert "reason" in sig


def test_dossier_endpoint(auth_headers):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from app.main import app

    eng = create_engine(
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    try:
        with eng.begin() as conn:
            row = conn.execute(
                text("SELECT id FROM decisions ORDER BY created_at LIMIT 1")
            ).fetchone()
    finally:
        eng.dispose()
    if not row:
        pytest.skip("tidak ada decision")
    with TestClient(app) as c:
        r = c.get(f"/decisions/{row[0]}/dossier", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["content_address"].startswith("mc1-")
        assert data["signature"]["state"] in ("signed", "unsigned")
        if data["signature"]["state"] == "signed":
            assert data["verify"] is True
        # address stabil untuk konten sama
        r2 = c.get(f"/decisions/{row[0]}/dossier", headers=auth_headers)
        assert r2.json()["content_address"] == data["content_address"]


def test_dossier_404(auth_headers):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        r = c.get(f"/decisions/{uuid.uuid4()}/dossier", headers=auth_headers)
        assert r.status_code == 404
