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
