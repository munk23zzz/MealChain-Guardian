# Test CORS (TDD): browser frontend (origin localhost:3000) fetch API
# backend (port 8000) — beda origin. Tanpa CORSMiddleware, request
# preflight/POST dari browser gagal "Failed to fetch".
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_preflight_dari_origin_frontend_diizinkan():
    client = _client()
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_content_type_header_diizinkan():
    """Login kirim JSON: header Content-Type wajib diizinkan preflight."""
    client = _client()
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert "content-type" in resp.headers.get(
        "access-control-allow-headers", ""
    ).lower()


def test_origin_tak_dikenal_tidak_diizinkan():
    client = _client()
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") is None


def test_preflight_dari_port_3010_diizinkan():
    """Konsol resmi pindah 3000 → 3010 (S4-19, .env FRONTEND_PORT=3010).

    Kalau frontend dijalankan di luar Docker (npm run dev di host, sehingga
    NEXT_PUBLIC_API_URL absolut dan jalur proxy Next tidak dipakai), origin
    yang dikirim browser adalah localhost:3010 — allow-list lama menolaknya.
    """
    client = _client()
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3010",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3010"


def test_preflight_patch_dari_origin_frontend_diizinkan():
    """PATCH dipakai tab Pengaturan (PATCH /admin/users/{id}, /admin/locations/{id}).

    allow_methods tanpa PATCH membuat preflight browser menolak permintaan itu
    di mode lintas-origin.
    """
    client = _client()
    resp = client.options(
        "/admin/users/00000000-0000-0000-0000-000000000000",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type, authorization",
        },
    )
    assert resp.status_code == 200
    assert "PATCH" in resp.headers.get("access-control-allow-methods", "").upper()


def test_daftar_origin_bawaan_memuat_kedua_port_konsol():
    from app.main import _cors_origins

    asal = _cors_origins()
    assert "http://localhost:3000" in asal
    assert "http://localhost:3010" in asal


def test_daftar_origin_dapat_ditentukan_lewat_env(monkeypatch):
    """CORS_ORIGINS (dipisah koma) menimpa bawaan — mis. domain Codespaces."""
    from app.main import _cors_origins

    monkeypatch.setenv(
        "CORS_ORIGINS", "https://contoh-3010.app.github.dev, http://localhost:3010"
    )
    assert _cors_origins() == [
        "https://contoh-3010.app.github.dev",
        "http://localhost:3010",
    ]

