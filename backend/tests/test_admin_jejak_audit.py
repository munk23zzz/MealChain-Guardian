"""AUTH-01 (audit 24 Okt 2026): jejak audit perubahan pengguna & lokasi.

Latar: skema tidak punya peran `admin` (Schema.md §1: 3 peran final), jadi
pengelolaan pengguna/lokasi dipegang `bgn_monitor` — peran yang sebenarnya
"read-only lintas kota". Keputusan itu sadar (`app/core/admin_rules.py`), tetapi
tanpa jejak audit, perubahan hak akses tidak bisa dipertanggungjawabkan setelah
kejadian. Tes ini mengunci dua hal:

1. Setiap perubahan pengguna/lokasi yang benar-benar mengubah data menambah satu
   blok ledger (`admin.user.update` / `admin.location.update`) dengan aktor dan
   nilai sebelum/sesudah.
2. Pagar tata kelola tetap berlaku: `bgn_monitor` tidak boleh mengubah perannya
   sendiri, dan penolakan itu TIDAK meninggalkan blok palsu.

Blok yang dibuat tes dihapus lagi di teardown (hanya dari ekor rantai, sehingga
`prev_hash` blok sebelumnya tidak putus).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.auth import get_current_user
from app.main import app
from app.models import User
from tests.dsn import DSN_SYNC
from tests.ledger_pemeliharaan import buka_pintu

DB_URL = DSN_SYNC


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
    simpan = dict(app.dependency_overrides)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(simpan)


@pytest.fixture
def skenario():
    """Snapshot master data + tinggi rantai; semuanya dipulihkan sesudah tes."""
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
        tinggi_awal = int(
            conn.execute(text("SELECT coalesce(max(height), 0) FROM ledger_blocks")).scalar()
        )
    try:
        yield engine, users_awal, lokasi_awal, tinggi_awal
    finally:
        with engine.begin() as conn:
            for u in users_awal:
                conn.execute(
                    text("UPDATE users SET role=:r, location_id=:l WHERE id=:i"),
                    {"r": u["role"], "l": u["location_id"], "i": u["id"]},
                )
            for lok in lokasi_awal:
                conn.execute(
                    text(
                        "UPDATE locations SET name=:n, region=:g, latitude=:la, "
                        "longitude=:lo WHERE id=:i"
                    ),
                    {
                        "n": lok["name"],
                        "g": lok["region"],
                        "la": lok["latitude"],
                        "lo": lok["longitude"],
                        "i": lok["id"],
                    },
                )
            # Hapus hanya blok yang dibuat tes (ekor rantai) — rantai lama utuh.
            # Fase 11: trigger menolak DELETE biasa; buka pintu pemeliharaan.
            buka_pintu(conn)
            conn.execute(
                text("DELETE FROM ledger_blocks WHERE height > :h"), {"h": tinggi_awal}
            )
        engine.dispose()


def _client_sebagai(user: User) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _blok_baru(engine, tinggi_awal: int) -> list[dict]:
    with engine.begin() as conn:
        baris = (
            conn.execute(
                text(
                    "SELECT action, entity_id, actor_id, payload FROM ledger_blocks "
                    "WHERE height > :h ORDER BY height"
                ),
                {"h": tinggi_awal},
            )
            .mappings()
            .all()
        )
    return [
        {**dict(r), "payload": json.loads(r["payload"])}
        for r in baris
    ]


def test_perubahan_pengguna_tercatat_di_ledger(skenario):
    engine, users_awal, lokasi_awal, tinggi_awal = skenario
    admin = _user("bgn_monitor")
    target = next(u for u in users_awal if u["role"] == "sppg_head")
    lokasi_baru = next(
        lok["id"] for lok in lokasi_awal if lok["id"] != target["location_id"]
    )

    resp = _client_sebagai(admin).patch(
        f"/admin/users/{target['id']}", json={"location_id": str(lokasi_baru)}
    )
    assert resp.status_code == 200, resp.text

    blok = _blok_baru(engine, tinggi_awal)
    assert len(blok) == 1
    assert blok[0]["action"] == "admin.user.update"
    assert str(blok[0]["entity_id"]) == str(target["id"])
    assert str(blok[0]["actor_id"]) == str(admin.id)
    isi = blok[0]["payload"]
    assert isi["role_sesudah"] == "sppg_head"
    assert isi["lokasi_sesudah"] == str(lokasi_baru)
    assert isi["lokasi_sebelum"] == (
        str(target["location_id"]) if target["location_id"] else None
    )


def test_perubahan_lokasi_tercatat_di_ledger(skenario):
    engine, _users, lokasi_awal, tinggi_awal = skenario
    admin = _user("bgn_monitor")
    lok = lokasi_awal[0]
    nama_baru = f"{lok['name']} (uji audit)"

    try:
        resp = _client_sebagai(admin).patch(
            f"/admin/locations/{lok['id']}", json={"name": nama_baru}
        )
        assert resp.status_code == 200, resp.text

        blok = _blok_baru(engine, tinggi_awal)
        assert [b["action"] for b in blok] == ["admin.location.update"]
        assert blok[0]["payload"]["perubahan"]["name"] == {
            "sebelum": lok["name"],
            "sesudah": nama_baru,
        }
        assert str(blok[0]["actor_id"]) == str(admin.id)
    finally:
        # Higiene suite: nama lokasi WAJIB dipulihkan. Tanpa ini, tes sesudahnya
        # (event1/logistik) gagal dengan "lokasi tidak dikenal: ... (uji audit)"
        # dan seluruh gate jadi merah karena polusi, bukan karena kode.
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE locations SET name = :n WHERE id = :i"),
                {"n": lok["name"], "i": lok["id"]},
            )


def test_ubah_peran_sendiri_ditolak_tanpa_jejak_palsu(skenario):
    engine, users_awal, _lokasi, tinggi_awal = skenario
    target = next(u for u in users_awal if u["role"] == "bgn_monitor")
    # Aktor = pengguna itu sendiri, dengan peran monitor.
    pelaku = User(
        id=target["id"],
        name="Monitor Uji",
        email="monitor-uji@demo.local",
        password_hash="tidak-dipakai",
        role="bgn_monitor",
        location_id=None,
    )

    resp = _client_sebagai(pelaku).patch(
        f"/admin/users/{target['id']}", json={"role": "sppg_head"}
    )
    assert resp.status_code == 422
    assert "sendiri" in resp.json()["detail"]
    assert _blok_baru(engine, tinggi_awal) == []


def test_perubahan_tanpa_selisih_tidak_membuat_blok(skenario):
    """PATCH yang tidak mengubah apa pun tidak boleh menambah blok palsu."""
    engine, users_awal, _lokasi, tinggi_awal = skenario
    admin = _user("bgn_monitor")
    target = next(u for u in users_awal if u["role"] == "sppg_head")

    resp = _client_sebagai(admin).patch(
        f"/admin/users/{target['id']}", json={"role": "sppg_head"}
    )
    assert resp.status_code == 200, resp.text
    assert _blok_baru(engine, tinggi_awal) == []


def test_rantai_tetap_valid_setelah_perubahan(skenario):
    engine, users_awal, lokasi_awal, tinggi_awal = skenario
    admin = _user("bgn_monitor")
    target = next(u for u in users_awal if u["role"] == "sppg_head")

    client = _client_sebagai(admin)
    sebelum = client.get("/ledger/verify")
    assert sebelum.status_code == 200, sebelum.text
    awal = sebelum.json()

    resp = client.patch(
        f"/admin/users/{target['id']}", json={"role": "sppg_nutritionist"}
    )
    assert resp.status_code == 200, resp.text

    sesudah = client.get("/ledger/verify")
    assert sesudah.status_code == 200, sesudah.text
    isi = sesudah.json()
    assert isi["valid"] is True
    # Jangan memaku "0 yatim": suite penuh meninggalkan blok milik tes lain di DB
    # bersama. Yang harus benar: blok admin baru TIDAK menjadi yatim dan tidak
    # menambah yatim sama sekali.
    assert isi["entity_blocks"] == awal["entity_blocks"] + 1
    assert isi["orphan_blocks"] == awal["orphan_blocks"]
    assert len(_blok_baru(engine, tinggi_awal)) == 1
