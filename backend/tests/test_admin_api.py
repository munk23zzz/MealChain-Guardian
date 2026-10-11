"""Kontrak endpoint admin (S4-11): RBAC, validasi, efek DB.

Tes ini MENULIS ke tabel MASTER (`users`, `locations`) — fixture menyimpan
nilai awal dan MENGEMBALIKANNYA sesudah tes (jebakan yang sudah menimpa suite
ini sebelumnya: `client` hanya me-reset tabel dinamis).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.auth import get_current_user
from app.main import app
from app.models import User

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"


def _user(role: str, location_id: uuid.UUID | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        name=f"Uji {role}",
        email=f"uji-{uuid.uuid4().hex[:10]}@demo.local",
        password_hash="tidak-dipakai",
        role=role,
        location_id=location_id,
    )


@pytest.fixture(autouse=True)
def _pulihkan_override():
    """WAJIB: `app.dependency_overrides` bertahan antar-tes dalam satu proses.

    Tanpa pembersihan ini, identitas admin palsu bocor ke modul tes berikutnya
    (gejala: ratusan tes lain jadi 403 "role tidak diizinkan" / 200 di tempat
    yang seharusnya 401). Snapshot + restore, bukan sekadar `.clear()`.
    """
    simpan = dict(app.dependency_overrides)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(simpan)


@pytest.fixture
def skenario():
    """Klien admin + snapshot master data yang dipulihkan sesudah tes."""
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        users_awal = (
            conn.execute(text("SELECT id, role, location_id FROM users")).mappings().all()
        )
        lokasi_awal = (
            conn.execute(
                text("SELECT id, name, region, latitude, longitude FROM locations")
            )
            .mappings()
            .all()
        )
        lokasi_ids = [r["id"] for r in lokasi_awal]
    try:
        yield engine, lokasi_ids, users_awal, lokasi_awal
    finally:
        with engine.begin() as conn:
            for u in users_awal:
                conn.execute(
                    text("UPDATE users SET role=:r, location_id=:l WHERE id=:i"),
                    {"r": u["role"], "l": u["location_id"], "i": u["id"]},
                )
            for l in lokasi_awal:
                conn.execute(
                    text(
                        "UPDATE locations SET name=:n, region=:g, latitude=:la, "
                        "longitude=:lo WHERE id=:i"
                    ),
                    {
                        "n": l["name"],
                        "g": l["region"],
                        "la": l["latitude"],
                        "lo": l["longitude"],
                        "i": l["id"],
                    },
                )
        engine.dispose()


def _client_sebagai(user: User | None) -> TestClient:
    if user is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_tanpa_token_ditolak_401():
    with _client_sebagai(None) as client:
        assert client.get("/admin/users").status_code == 401


def test_peran_sppg_ditolak_403():
    with _client_sebagai(_user("sppg_head", uuid.uuid4())) as client:
        assert client.get("/admin/users").status_code == 403
        assert client.get("/admin/locations").status_code == 403


def test_daftar_pengguna_memuat_peran_dan_lokasi(skenario):
    with _client_sebagai(_user("bgn_monitor")) as client:
        body = client.get("/admin/users").json()
    assert body["users"], "daftar pengguna kosong"
    for item in body["users"]:
        assert set(item) == {
            "id",
            "name",
            "email",
            "role",
            "location_id",
            "location_name",
        }
        if item["role"] == "bgn_monitor":
            assert item["location_id"] is None
        else:
            assert item["location_id"] and item["location_name"]


def test_ubah_lokasi_pengguna_dan_efeknya_di_db(skenario):
    engine, lokasi_ids, _, _ = skenario
    with _client_sebagai(_user("bgn_monitor")) as client:
        daftar = client.get("/admin/users").json()["users"]
        target = next(u for u in daftar if u["role"] in ("sppg_head", "sppg_nutritionist"))
        tujuan = next(str(i) for i in lokasi_ids if str(i) != target["location_id"])

        res = client.patch(
            f"/admin/users/{target['id']}", json={"location_id": tujuan}
        )
        assert res.status_code == 200, res.text
        assert res.json()["user"]["location_id"] == tujuan

    with engine.begin() as conn:
        tersimpan = conn.execute(
            text("SELECT location_id FROM users WHERE id=:i"), {"i": target["id"]}
        ).scalar_one()
    assert str(tersimpan) == tujuan


def test_role_tak_dikenal_ditolak_422(skenario):
    with _client_sebagai(_user("bgn_monitor")) as client:
        daftar = client.get("/admin/users").json()["users"]
        res = client.patch(f"/admin/users/{daftar[0]['id']}", json={"role": "admin"})
    assert res.status_code == 422
    assert "role tidak dikenal" in res.json()["detail"]


def test_pengguna_tidak_ditemukan_404(skenario):
    with _client_sebagai(_user("bgn_monitor")) as client:
        assert client.patch("/admin/users/bukan-uuid", json={"role": "bgn_monitor"}).status_code == 404
        assert (
            client.patch(f"/admin/users/{uuid.uuid4()}", json={"role": "bgn_monitor"}).status_code
            == 404
        )


def test_daftar_lokasi_dan_ubah_nama(skenario):
    _, _, _, lokasi_awal = skenario
    with _client_sebagai(_user("bgn_monitor")) as client:
        body = client.get("/admin/locations").json()
        assert len(body["locations"]) == len(lokasi_awal)
        assert set(body["locations"][0]) == {
            "id",
            "name",
            "region",
            "latitude",
            "longitude",
            "role_hint",
        }
        target = body["locations"][0]
        nama_baru = f"{target['name']} (uji)"
        res = client.patch(f"/admin/locations/{target['id']}", json={"name": nama_baru})
        assert res.status_code == 200, res.text
        assert res.json()["location"]["name"] == nama_baru


def test_ubah_lokasi_nilai_tidak_valid_422(skenario):
    _, lokasi_ids, _, _ = skenario
    with _client_sebagai(_user("bgn_monitor")) as client:
        assert (
            client.patch(
                f"/admin/locations/{lokasi_ids[0]}", json={"latitude": 91.0}
            ).status_code
            == 422
        )
        assert (
            client.patch(f"/admin/locations/{lokasi_ids[0]}", json={}).status_code == 422
        )
        assert (
            client.patch(f"/admin/locations/{uuid.uuid4()}", json={"name": "X"}).status_code
            == 404
        )
