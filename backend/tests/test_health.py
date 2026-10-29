"""Health endpoint backend Sprint 0 + penghitung peramalan.

`/health` kini juga melaporkan anggaran panggilan model peramalan. Kontraknya:
field lama tetap ada, dan blok `forecast` tidak boleh memuat rahasia — hanya
angka dan boolean.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

KUNCI_FORECAST = {
    "forecast_calls_total",
    "forecast_fallback_total",
    "forecast_cache_hit_total",
    "forecast_breaker_open_total",
    "sap_rpt_configured",
    "cache_entries",
    "breaker_open",
}


def test_backend_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    badan = response.json()
    assert badan["status"] == "healthy"
    assert badan["service"] == "mealchain-backend"
    assert KUNCI_FORECAST <= set(badan["forecast"])


def test_health_tidak_membocorkan_rahasia() -> None:
    """Jangan pernah mengirim isi kredensial lewat endpoint publik."""
    teks = client.get("/health").text.lower()
    for kata in ("client_secret", "client_id", "api_key", "password", "token"):
        assert kata not in teks
