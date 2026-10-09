"""P4 (paket 1-6): GET /batches read-only untuk chaos panel Event 3.

Kontrak: 200 dengan daftar batch (id/location/commodity/safety_status),
401 tanpa token. TIDAK ada endpoint mutasi di sini.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_batches_requires_auth():
    with TestClient(app) as c:
        r = c.get("/batches")
        assert r.status_code == 401


def test_batches_list(auth_headers):
    with TestClient(app) as c:
        r = c.get("/batches", headers=auth_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data["batches"], list)
        for b in data["batches"]:
            assert set(b) >= {
                "id", "location", "commodity", "quantity_kg",
                "safety_status",
            }
