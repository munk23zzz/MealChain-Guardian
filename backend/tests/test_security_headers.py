"""SEC-04 & SEC-05 (audit 24 Okt 2026): dokumentasi API dan header keamanan.

SEC-04 — `/docs`, `/redoc`, dan `/openapi.json` dulu terbuka tanpa autentikasi.
Peta endpoint selengkap itu memudahkan pemetaan serangan dan tidak dibutuhkan UI.
Sekarang default TERTUTUP (404, bukan 403 — jangan mengonfirmasi rutenya ada) dan
hanya terbuka bila `ENABLE_DOCS`/`DEBUG` dinyalakan.

SEC-05 — respons backend dulu tanpa header keamanan sama sekali. Sekarang setiap
respons membawa `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, dan CSP
ketat (backend hanya JSON); HSTS hanya dikirim di HTTPS.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _env_bersih(monkeypatch):
    monkeypatch.delenv("ENABLE_DOCS", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)


def test_dokumentasi_tertutup_secara_bawaan(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        resp = client.get(path)
        assert resp.status_code == 404, f"{path}: {resp.status_code}"
        # 404 polos — jangan membocorkan bahwa rute itu ada.
        assert "detail" in resp.json()


def test_dokumentasi_terbuka_bila_diminta(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DOCS", "true")
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_debug_ikut_membuka_dokumentasi(client, monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    assert client.get("/openapi.json").status_code == 200


def test_header_keamanan_ada_di_respons_biasa(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    h = resp.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in h["permissions-policy"]
    csp = h["content-security-policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    # HTTP biasa → HSTS tidak dikirim.
    assert "strict-transport-security" not in h


def test_hsts_hanya_di_https(client):
    resp = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert resp.status_code == 200
    assert resp.headers["strict-transport-security"].startswith("max-age=")


def test_header_keamanan_juga_menempel_pada_404(client):
    resp = client.get("/tidak-ada-endpoint-ini")
    assert resp.status_code == 404
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
