"""S4-01 UI prerequisite — daftar quote untuk pemilihan Event 2 (RED dulu).

Kontrak: read-only, semua role ter-autentikasi (termasuk bgn_monitor),
mengembalikan quote persisted + reference terkini pada lokasi/komoditas
yang SAMA (anti pencampuran lintas lokasi).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_hdr():
    """JWT user legacy-rbac (pola conftest.auth_headers, dipakai via client)."""

    # auth_headers adalah fixture session; akses via request tidak tersedia
    # di luar pytest, jadi login manual dengan user demo Jakarta.
    resp = client_no_fixture().post(
        "/auth/login",
        json={"email": "sppg.head@demo.local", "password": "Demo#SPPG2026"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def client_no_fixture():
    with TestClient(app) as c:
        return c


def test_quotes_lists_persisted_quotes_with_reference(client, auth_hdr):
    """200: quotes[] + reference; harga dari DB, bukan karangan."""
    r = client.get("/price/quotes/Jakarta/telur", headers=auth_hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["quotes"], list) and body["quotes"], body
    q0 = body["quotes"][0]
    for key in ("id", "supplier_name", "price_per_kg", "recorded_at"):
        assert key in q0, (key, q0)
    ref = body["reference"]
    assert isinstance(ref["price_per_kg"], (int, float)), ref


def test_quotes_requires_auth(client):
    """401 tanpa JWT; 404 lokasi tak dikenal."""
    assert client.get("/price/quotes/Jakarta/telur").status_code == 401
    hdr = auth_hdr_static()
    r = client.get("/price/quotes/Narnia/telur", headers=hdr)
    assert r.status_code == 404


def auth_hdr_static():
    with TestClient(app) as c:
        resp = c.post(
            "/auth/login",
            json={"email": "sppg.head@demo.local", "password": "Demo#SPPG2026"},
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
