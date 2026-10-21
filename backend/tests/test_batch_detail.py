"""Kontrak `GET /batches/{batch_id}` (audit 21 Okt 2026, temuan P6).

Daftar batch ada, tetapi satu batch tidak bisa dibuka: semua peran menerima 404
routing. Akibatnya tautan dalam (deep link) ke batch, dan pertanyaan Joule "batch
ini apa?", tidak punya jalur selain menarik seluruh daftar lalu menyaring sendiri.

Kontrak yang dikunci:
- bentuk baris SAMA dengan elemen `batches` pada daftar (tidak ada kolom baru);
- batch tak dikenal → 404 dengan pesan, bukan 200 kosong;
- tanpa token → 401 (tetap terproteksi seperti daftar).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.main import app
from app.models import User

PENONTON = User(
    id=uuid.uuid4(),
    email="audit-batch@demo.local",
    name="Audit Batch",
    role="bgn_monitor",
    password_hash="tidak-dipakai",
)

#: Kolom yang sudah ada di elemen daftar; detail tidak boleh menambah/mengurangi.
KOLOM = {
    "id",
    "location",
    "location_id",
    "commodity",
    "quantity_kg",
    "safety_status",
    "freshness_score",
    "usable_until",
    "receipt_status",
    "quarantine_status",
}


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: PENONTON
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_detail_batch_memakai_bentuk_baris_daftar(client):
    daftar = client.get("/batches").json()
    if not daftar.get("batches"):
        pytest.skip("butuh minimal satu batch di DB")
    baris = daftar["batches"][0]

    resp = client.get(f"/batches/{baris['id']}")
    assert resp.status_code == 200, resp.text
    detail = resp.json()["batch"]
    assert set(detail) == KOLOM
    for kunci in ("id", "location", "commodity", "quantity_kg", "safety_status"):
        assert detail[kunci] == baris[kunci], f"{kunci} berbeda antara daftar dan detail"


def test_detail_batch_tak_dikenal_404(client):
    resp = client.get(f"/batches/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert "tidak ditemukan" in resp.json()["detail"].lower()


def test_detail_batch_id_bukan_uuid_ditolak_422(client):
    resp = client.get("/batches/bukan-uuid")
    assert resp.status_code == 422


def test_detail_batch_tetap_butuh_login(client):
    app.dependency_overrides.clear()
    resp = client.get(f"/batches/{uuid.uuid4()}")
    assert resp.status_code == 401
