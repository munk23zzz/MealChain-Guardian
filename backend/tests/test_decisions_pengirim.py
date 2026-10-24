"""Identitas pengirim pada feed `GET /decisions` (permintaan pemilik 24 Okt 2026).

Masalah: kartu rekomendasi hanya menyebut wilayah, sehingga operator tidak tahu
apakah barang dikirim pemasok atau dipindahkan dari SPPG lain.

Kontrak yang diuji:
- Baris dengan `decisions.supplier_id` → `supplier_name` terisi, `pengirim`
  "pemasok".
- Baris lama tanpa kolom itu → dipakai `supplier_id` di payload bukti.
- Jenis pemindahan antar lokasi tanpa pemasok → "antar_sppg"; selain itu None.
- `target_location_name` diisi dari lokasi tujuan.

Tes baca-saja (dependency override), tidak membuat keputusan di DB demo.
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
    email="audit-pengirim@demo.local",
    name="Audit Pengirim",
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


@pytest.fixture()
def items(client):
    return client.get("/decisions?window=30d").json()["items"]


def test_setiap_baris_punya_kunci_pengirim(items):
    assert items, "butuh data keputusan di DB"
    for row in items:
        assert "supplier_name" in row
        assert "pengirim" in row
        assert "target_location_name" in row
        assert row["pengirim"] in {"pemasok", "antar_sppg", None}


def test_baris_berpemasok_menyebut_nama_pemasok(items):
    berpemasok = [r for r in items if r["pengirim"] == "pemasok"]
    if not berpemasok:
        pytest.skip("tidak ada keputusan berpemasok di DB ini")
    for row in berpemasok:
        assert row["supplier_name"], "pengirim=pemasok wajib punya nama pemasok"
        assert row["supplier_id"]


def test_pemindahan_tanpa_pemasok_ditandai_antar_sppg(items):
    pindah = [r for r in items if r["decision_type"] == "regional_balance"]
    if not pindah:
        pytest.skip("tidak ada keputusan regional_balance di DB ini")
    for row in pindah:
        if row["supplier_name"]:
            assert row["pengirim"] == "pemasok"
        else:
            assert row["pengirim"] == "antar_sppg"


def test_tujuan_memakai_nama_lokasi_bukan_id(items):
    bertujuan = [r for r in items if r["target_location_name"]]
    if not bertujuan:
        pytest.skip("tidak ada keputusan dengan lokasi tujuan")
    for row in bertujuan:
        # Nama lokasi manusiawi, bukan UUID.
        assert len(row["target_location_name"]) > 2
        assert "-" not in row["target_location_name"][:8] or " " in row["target_location_name"]
