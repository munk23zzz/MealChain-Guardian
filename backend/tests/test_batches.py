"""P4 (paket 1-6): GET /batches read-only untuk chaos panel Event 3.

Kontrak: 200 dengan daftar batch (id/location/commodity/safety_status),
401 tanpa token. TIDAK ada endpoint mutasi di sini.
"""

from fastapi.testclient import TestClient

from app.api.batches import BATAS_MAKS
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


def test_batches_default_masih_50_untuk_ui_lama(auth_headers):
    """UI chaos panel memakai default; kontrak lama tidak boleh berubah diam-diam."""
    with TestClient(app) as c:
        data = c.get("/batches", headers=auth_headers).json()
    assert data["limit"] == 50
    assert len(data["batches"]) <= 50
    assert data["total"] >= len(data["batches"])


def test_batches_limit_bisa_dinaikkan_dan_total_melaporkan_semua(auth_headers):
    """Pembaca inventaris (jembatan Joule) butuh SEMUA baris, bukan 50 terbaru.

    Sebelum perbaikan 2026-10-20, `limit` tidak ada dan query memakai `.limit(50)` di kode:
    158 batch di database hanya 50 yang pernah terbaca, tanpa satu pun galat.
    """
    with TestClient(app) as c:
        penuh = c.get("/batches", params={"limit": BATAS_MAKS}, headers=auth_headers).json()
        kecil = c.get("/batches", params={"limit": 5}, headers=auth_headers).json()

    assert penuh["total"] == kecil["total"], "total tidak boleh bergantung pada limit"
    assert len(penuh["batches"]) == min(penuh["total"], BATAS_MAKS)
    assert len(kecil["batches"]) == min(5, kecil["total"])


def test_batches_offset_menggeser_halaman(auth_headers):
    with TestClient(app) as c:
        semua = c.get("/batches", params={"limit": BATAS_MAKS}, headers=auth_headers).json()
        geser = c.get(
            "/batches", params={"limit": 5, "offset": 3}, headers=auth_headers
        ).json()

    ids = [b["id"] for b in semua["batches"]]
    assert [b["id"] for b in geser["batches"]] == ids[3:8]


def test_batches_limit_di_luar_batas_ditolak_422(auth_headers):
    with TestClient(app) as c:
        assert c.get("/batches", params={"limit": 0}, headers=auth_headers).status_code == 422
        assert (
            c.get("/batches", params={"limit": BATAS_MAKS + 1}, headers=auth_headers).status_code
            == 422
        )
        assert c.get("/batches", params={"offset": -1}, headers=auth_headers).status_code == 422

def test_batches_membawa_status_penerimaan_terakhir(auth_headers):
    """Layar Penerimaan hanya menawarkan batch yang belum disetujui.

    `receipt_status` = status catatan TERAKHIR per batch; null bila belum
    pernah dicatat. Tanpa kolom ini UI harus menebak atau memanggil
    GET /receipts satu per satu untuk 40+ batch.
    """
    with TestClient(app) as c:
        data = c.get("/batches", headers=auth_headers).json()
    for b in data["batches"]:
        assert "receipt_status" in b
        assert b["receipt_status"] in (None, "menunggu", "disetujui", "ditolak")
