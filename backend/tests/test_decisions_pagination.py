"""Kontrak paginasi `GET /decisions` (audit 21 Okt 2026, temuan P6).

Sebelum ini `/decisions` mengabaikan `limit`/`offset` tanpa galat dan tidak punya
`total`: UI yang meminta 10 baris tetap menerima semuanya, dan tidak ada cara tahu
berapa yang belum tampil. `/batches` sudah benar (`count`/`total`/`offset`, `limit`
0 dan 1000 ditolak 422) — endpoint ini disamakan supaya dua daftar besar berperilaku
sama.

Tes ini SENGAJA baca-saja dan tidak membuat keputusan: autentikasi diganti dependency
override (bukan login sungguhan) karena login pada DB salinan tidak sah — fixture
akun menghasilkan 401 di sana, dan membuat baris uji di DB demo akan mengubah angka
yang dipakai juri.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.main import app
from app.models import User

#: Peran pemantau nasional: tanpa batas lokasi, jadi `total` = seluruh tabel.
PENONTON = User(
    id=uuid.uuid4(),
    email="audit-baca@demo.local",
    name="Audit Baca",
    role="bgn_monitor",
    password_hash="tidak-dipakai",
)


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: PENONTON
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_tanpa_parameter_daftar_penuh_dan_total_konsisten(client):
    body = client.get("/decisions").json()
    assert isinstance(body.get("items"), list)
    assert body["total"] == len(body["items"]), "tanpa limit, total = seluruh baris"
    assert body["count"] == len(body["items"])
    assert body["offset"] == 0


def test_limit_memotong_daftar_tapi_total_tetap_penuh(client):
    penuh = client.get("/decisions").json()
    if penuh["total"] < 2:
        pytest.skip("butuh minimal 2 keputusan di DB untuk menguji pemotongan")
    body = client.get("/decisions?limit=1").json()
    assert len(body["items"]) == 1
    assert body["count"] == 1
    assert body["total"] == penuh["total"], "total harus jumlah SELURUH baris, bukan halaman"
    assert body["items"][0]["decision_id"] == penuh["items"][0]["decision_id"]


def test_offset_menggeser_halaman_tanpa_tumpang_tindih(client):
    penuh = client.get("/decisions").json()
    if penuh["total"] < 2:
        pytest.skip("butuh minimal 2 keputusan di DB")
    hal1 = client.get("/decisions?limit=1&offset=0").json()
    hal2 = client.get("/decisions?limit=1&offset=1").json()
    assert hal1["items"][0]["decision_id"] != hal2["items"][0]["decision_id"]
    assert hal2["offset"] == 1
    assert hal2["items"][0]["decision_id"] == penuh["items"][1]["decision_id"]


def test_offset_di_luar_batas_mengembalikan_daftar_kosong(client):
    penuh = client.get("/decisions").json()
    body = client.get(f"/decisions?offset={penuh['total'] + 50}").json()
    assert body["items"] == []
    assert body["total"] == penuh["total"]


@pytest.mark.parametrize("query", ["limit=0", "limit=1000", "offset=-1", "limit=abc"])
def test_batas_tidak_masuk_akal_ditolak_422(client, query):
    resp = client.get(f"/decisions?{query}")
    assert resp.status_code == 422, f"{query} seharusnya 422, bukan {resp.status_code}"
