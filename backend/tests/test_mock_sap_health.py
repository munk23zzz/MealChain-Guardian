"""Mock SAP service: health + label simulasi WAJIB (Rules.md §1.6)."""

from fastapi.testclient import TestClient

from app.sap_integration.mock_service import app

client = TestClient(app)


def test_mock_sap_health_labeled_as_simulation() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "mock-sap",
        "data_source": "simulation",
    }
    assert response.headers.get("X-Data-Source") == "MOCK"
