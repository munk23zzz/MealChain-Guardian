"""Blok ledger per keputusan — `GET /decisions/{id}/ledger` (dokumen 06).

MASALAH yang dipaku. Dokumen 06 invarian 3: "ACT punya rumah sendiri di
ledger. Menampilkannya sebagai `belum tercatat` padahal blok ledger ada adalah
kesalahan fakta." Sebelum endpoint ini, klien tidak punya jalan membaca
`ledger_blocks` sama sekali — jadi satu-satunya pilihan jujur adalah menulis
"belum dimuat" selamanya.

Yang diuji di sini:
1. Hanya blok milik keputusan itu (entity_id), bukan blok lain.
2. Blok tanpa entity (mis. anchor) tidak ikut.
3. Keputusan tak dikenal → 404, bukan daftar kosong yang menyamar sebagai
   "tidak ada eksekusi".
4. Tanpa token → 401.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _keputusan_pertama(client, headers) -> str:
    resp = client.get("/decisions?limit=5", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    assert items, "seed demo harus punya keputusan"
    return items[0]["id"] if "id" in items[0] else items[0]["decision_id"]


def test_mengembalikan_blok_milik_keputusan_itu(client, auth_headers) -> None:
    decision_id = _keputusan_pertama(client, auth_headers)
    resp = client.get(f"/decisions/{decision_id}/ledger", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision_id"] == decision_id
    assert isinstance(body["blocks"], list)
    # Bentuk tiap blok: tinggi (urut), aksi, waktu. Tidak ada payload_hash di
    # API publik: klien tidak perlu memverifikasi rantai di sini.
    for blok in body["blocks"]:
        assert set(blok) == {"height", "action", "created_at"}
        assert isinstance(blok["height"], int)
        assert isinstance(blok["action"], str)
    tinggi = [b["height"] for b in body["blocks"]]
    assert tinggi == sorted(tinggi), "blok harus urut tinggi"


def test_tidak_menyertakan_blok_keputusan_lain(client, auth_headers) -> None:
    resp = client.get("/decisions?limit=5", headers=auth_headers)
    body = resp.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    if len(items) < 2:
        pytest.skip("seed hanya punya satu keputusan")

    id_1 = items[0].get("id") or items[0].get("decision_id")
    id_2 = items[1].get("id") or items[1].get("decision_id")
    kunci_1 = {
        (b["height"], b["action"])
        for b in client.get(
            f"/decisions/{id_1}/ledger", headers=auth_headers
        ).json()["blocks"]
    }
    kunci_2 = {
        (b["height"], b["action"])
        for b in client.get(
            f"/decisions/{id_2}/ledger", headers=auth_headers
        ).json()["blocks"]
    }
    assert kunci_1.isdisjoint(kunci_2), "satu blok tidak boleh muncul di dua keputusan"


def test_keputusan_tak_dikenal_404(client, auth_headers) -> None:
    resp = client.get(f"/decisions/{uuid.uuid4()}/ledger", headers=auth_headers)
    assert resp.status_code == 404


def test_tanpa_token_401(client) -> None:
    resp = client.get(f"/decisions/{uuid.uuid4()}/ledger")
    assert resp.status_code == 401
