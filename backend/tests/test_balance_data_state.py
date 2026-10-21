"""Kejujuran data neraca lokasi (PLAN-023 · 2026-10-17).

MASALAH yang dipaku di sini. `GET /balance/map` mengisi supply/demand yang
TIDAK ADA dengan `0`, lalu menghitung gap dari angka itu. Akibatnya lokasi yang
sama sekali tidak punya baris permintaan (terukur live: Bandung & Cianjur untuk
komoditas telur) dilaporkan `status="surplus"` dengan `surplus_kg` ratusan kilo
— angka yang tampak seperti fakta terukur padahal cuma hasil pengisian nol.

ATURAN yang ditegakkan. Angka `0` TETAP dikirim (aturan tampilan tidak berubah:
`0 kg` tetap `0 kg`), tetapi payload WAJIB membawa asal nilai per sisi:
`supply_state` / `demand_state` (`terukur` | `tidak_ada_baris`), `data_state`
ringkas per lokasi (`terukur` | `sebagian` | `tidak_ada_baris`), dan stempel
waktu baris yang benar-benar dipakai (`*_recorded_at`, `null` bila tidak ada
baris) supaya konsumen bisa memisahkan "nol terukur" dari "tidak ada catatan".

Selain itu ada KONTRAK DERET: bila cakupan data demo menyusut diam-diam,
gate ini yang harus gagal — bukan pengisian nol yang menyamar jadi data.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC
KOMODITAS_DEMO = ("telur", "ayam", "wortel", "beras")
# Cakupan minimum deret demo per komoditas (terukur 2026-10-17: supply 10/10,
# demand 8/10 lokasi — beras ikut: supply 10/10, demand 8/10). Nilai 8 memberi
# ruang satu-dua lokasi tanpa catatan — yang memang ada dan harus DIKATAKAN —
# tetapi menolak penyusutan diam-diam.
MIN_LOKASI_TERUKUR = 8


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _buat_lokasi(
    komoditas: str = "telur",
    supply_kg: float | None = None,
    demand_kg: float | None = None,
) -> tuple[str, str]:
    """Lokasi test terisolasi; `None` = baris itu SENGAJA tidak dibuat."""
    key = f"ds-{uuid.uuid4().hex[:10]}"
    nama = f"TEST-{key}"
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            loc_id = conn.execute(
                text(
                    "INSERT INTO locations (name, region, latitude, longitude)"
                    " VALUES (:n, 'Test Region', -6.2, 106.8) RETURNING id"
                ),
                {"n": nama},
            ).scalar_one()
            com_id = conn.execute(
                text("SELECT id FROM commodities WHERE name=:n"), {"n": komoditas}
            ).scalar_one()
            if supply_kg is not None:
                conn.execute(
                    text(
                        "INSERT INTO supply_records (location_id, commodity_id,"
                        " quantity_kg, recorded_at, source)"
                        " VALUES (:l, :c, :q, now(), 'manual')"
                    ),
                    {"l": loc_id, "c": com_id, "q": supply_kg},
                )
            if demand_kg is not None:
                conn.execute(
                    text(
                        "INSERT INTO demand_records (location_id, commodity_id,"
                        " quantity_kg, needed_by, recorded_at)"
                        " VALUES (:l, :c, :q, now(), now())"
                    ),
                    {"l": loc_id, "c": com_id, "q": demand_kg},
                )
    finally:
        engine.dispose()
    return nama, loc_id


def _hapus_lokasi(loc_id: str) -> None:
    """Bersihkan residu test FK-safe (lokasi ikut terlihat endpoint peta)."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            for tabel in ("supply_records", "demand_records"):
                conn.execute(
                    text(f"DELETE FROM {tabel} WHERE location_id=:l"), {"l": loc_id}
                )
            conn.execute(text("DELETE FROM locations WHERE id=:l"), {"l": loc_id})
    finally:
        engine.dispose()


def _ambil_lokasi(items: list[dict], nama: str) -> dict:
    for item in items:
        if item.get("location") == nama:
            return item
    raise AssertionError(f"lokasi {nama} tidak muncul di payload peta")


def _peta(client, headers, komoditas: str) -> list[dict]:
    resp = client.get(f"/balance/map?commodity={komoditas}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["locations"]


def test_baris_nol_terukur_tetap_dilaporkan_nol_kg(client, monitor_headers):
    """Baris ADA dengan nilai 0 → tetap `0 kg`, ditandai `terukur`."""
    nama, loc_id = _buat_lokasi(supply_kg=120, demand_kg=0)
    try:
        item = _ambil_lokasi(_peta(client, monitor_headers, "telur"), nama)
        assert item["supply_kg"] == 120.0
        assert item["demand_kg"] == 0.0  # aturan tampilan tidak berubah
        assert item["supply_state"] == "terukur"
        assert item["demand_state"] == "terukur"
        assert item["data_state"] == "terukur"
        assert item["demand_recorded_at"] is not None
    finally:
        _hapus_lokasi(loc_id)


def test_tanpa_baris_permintaan_ditandai_tidak_ada_baris(client, monitor_headers):
    """Tidak ada baris demand → angka tetap 0 tetapi HARUS bertanda asal nilai.

    Kasus nyata: Bandung/Cianjur (telur) melaporkan surplus besar semata karena
    baris permintaannya tidak ada.
    """
    nama, loc_id = _buat_lokasi(supply_kg=386.4, demand_kg=None)
    try:
        item = _ambil_lokasi(_peta(client, monitor_headers, "telur"), nama)
        assert item["demand_kg"] == 0.0
        assert item["demand_state"] == "tidak_ada_baris"
        assert item["demand_recorded_at"] is None
        assert item["supply_state"] == "terukur"
        assert item["supply_recorded_at"] is not None
        assert item["data_state"] == "sebagian"
    finally:
        _hapus_lokasi(loc_id)


def test_tanpa_kedua_baris_ditandai_tidak_ada_baris(client, monitor_headers):
    """Lokasi tanpa catatan sama sekali tidak boleh menyamar jadi `terukur`."""
    nama, loc_id = _buat_lokasi(supply_kg=None, demand_kg=None)
    try:
        item = _ambil_lokasi(_peta(client, monitor_headers, "telur"), nama)
        assert item["supply_kg"] == 0.0
        assert item["demand_kg"] == 0.0
        assert item["supply_state"] == "tidak_ada_baris"
        assert item["demand_state"] == "tidak_ada_baris"
        assert item["data_state"] == "tidak_ada_baris"
        assert item["supply_recorded_at"] is None
        assert item["demand_recorded_at"] is None
    finally:
        _hapus_lokasi(loc_id)


def test_kontrak_deret_demo_tidak_menyusut_diam_diam(client, monitor_headers):
    """Deret demo wajib tetap terukur; penyusutan cakupan = gate MERAH.

    Inilah yang membuat "data hilang" tidak bisa lolos sebagai "nol faktual":
    bila seed/deret demo hilang, jumlah lokasi `terukur` turun di bawah ambang
    dan tes ini gagal — bukan diam-diam dilaporkan sebagai 0 kg.
    """
    for komoditas in KOMODITAS_DEMO:
        items = [
            item
            for item in _peta(client, monitor_headers, komoditas)
            if not str(item.get("location", "")).startswith("TEST-")
        ]
        supply_terukur = sum(1 for i in items if i.get("supply_state") == "terukur")
        demand_terukur = sum(1 for i in items if i.get("demand_state") == "terukur")
        assert supply_terukur >= MIN_LOKASI_TERUKUR, (
            f"{komoditas}: hanya {supply_terukur} lokasi punya baris supply terukur"
        )
        assert demand_terukur >= MIN_LOKASI_TERUKUR, (
            f"{komoditas}: hanya {demand_terukur} lokasi punya baris demand terukur"
        )
        for item in items:
            assert item["data_state"] in {"terukur", "sebagian", "tidak_ada_baris"}
            # Penanda harus KONSISTEN: tidak boleh ada sisi tanpa baris tetapi
            # lokasinya menyamar `terukur`.
            if (
                item["supply_state"] == "tidak_ada_baris"
                or item["demand_state"] == "tidak_ada_baris"
            ):
                assert item["data_state"] != "terukur"


def test_balance_satu_lokasi_membawa_penanda_yang_sama(client, monitor_headers):
    """Endpoint panel (`/balance/{lokasi}/{komoditas}`) memakai aturan sama."""
    nama, loc_id = _buat_lokasi(supply_kg=250, demand_kg=None)
    try:
        resp = client.get(f"/balance/{nama}/telur", headers=monitor_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["demand_kg"] == 0.0
        assert body["demand_state"] == "tidak_ada_baris"
        assert body["supply_state"] == "terukur"
        assert body["data_state"] == "sebagian"
    finally:
        _hapus_lokasi(loc_id)

    nama2, loc_id2 = _buat_lokasi(supply_kg=None, demand_kg=None)
    try:
        # Keduanya tidak ada → tetap 404 jujur (perilaku lama, tidak dilunakkan).
        resp = client.get(f"/balance/{nama2}/telur", headers=monitor_headers)
        assert resp.status_code == 404, resp.text
    finally:
        _hapus_lokasi(loc_id2)
