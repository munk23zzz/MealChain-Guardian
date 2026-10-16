"""Endpoint `GET /supplier-routes` — rute JALAN pemasok → tujuan (Fase 10).

TDD RED dulu. Kontrak yang dikunci di sini:

- **Read-only + JWT**: 401 tanpa token, seperti endpoint lain.
- **Cakupan per lokasi**: kiriman adalah data sisi TUJUAN, jadi kepala SPPG
  hanya melihat kiriman yang menuju SPPG-nya (Ruling 2026-10-14: cakupan
  ditegakkan di server, bukan di UI). `bgn_monitor` (tanpa lokasi) melihat
  semua kiriman aktif — itu tugasnya memantau.
- **Hanya kiriman layak**: `usable_until >= now`; kiriman kedaluwarsa tidak
  digambar dan tidak dihitung.
- **Jujur soal rute**: tiap baris punya `road` ATAU `road_missing_reason`
  (tidak keduanya, tidak juga kosong-dua-duanya). Jarak lurus selalu ada
  sebagai fakta terpisah, dan jarak jalan (data OSRM) tidak pernah lebih
  pendek dari jarak lurus.

Tes ini memakai basis data yang sudah di-seed kanonik + cache rute yang sudah
disinkronkan (lihat `docs/verification/fase-10.md`), jadi angkanya nyata —
bukan angka karangan tes.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

KUNCI_WAJIB = {
    "batch_id",
    "supplier_id",
    "supplier_name",
    "origin",
    "destination_id",
    "destination_name",
    "destination",
    "commodity",
    "quantity_kg",
    "usable_until",
    "safety_status",
    "straight_km",
    "road",
    "road_missing_reason",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_routes_unauth_401(client):
    r = client.get("/supplier-routes")
    assert r.status_code == 401


def test_kepala_sppg_jakarta_hanya_melihat_kiriman_ke_lokasinya(client, auth_headers):
    r = client.get("/supplier-routes", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["routes"], "harus ada kiriman aktif menuju SPPG Jakarta"
    tujuan = {row["destination_name"] for row in data["routes"]}
    assert tujuan == {"Jakarta"}, f"kepala SPPG Jakarta melihat kiriman lain: {tujuan}"
    assert data["summary"]["scope"] == "lokasi user"
    assert data["summary"]["reference_location"] == "Jakarta"


def test_kiriman_ke_jakarta_punya_koordinat_dan_jarak_lurus(client, auth_headers):
    data = client.get("/supplier-routes", headers=auth_headers).json()
    row = data["routes"][0]
    assert row["supplier_name"] == "Supplier A Cianjur"
    assert row["commodity"] == "telur"
    assert row["quantity_kg"] == 800.0
    assert row["usable_until"].startswith("2026-11-07")
    assert row["safety_status"] == "pass"
    assert row["origin"]["latitude"] is not None
    assert row["destination"]["longitude"] is not None
    # Jarak lurus Cianjur -> Jakarta ~76 km (haversine server, bukan karangan)
    assert 70.0 < row["straight_km"] < 85.0


def test_rute_jalan_dari_cache_membawa_geometri_dan_lebih_panjang_dari_lurus(
    client, auth_headers
):
    data = client.get("/supplier-routes", headers=auth_headers).json()
    road = data["routes"][0]["road"]
    assert road is not None, "cache rute harus sudah tersinkron (lihat fase-10)"
    assert road["source"] == "osrm"
    assert road["geometry"]["type"] == "LineString"
    assert len(road["geometry"]["coordinates"]) >= 2
    # Titik pertama harus di dekat Cianjur (lon ~107,13) — bukan tertukar lat/lon
    lon, lat = road["geometry"]["coordinates"][0]
    assert 106.5 < lon < 107.5 and -7.2 < lat < -6.4
    # Jalan selalu >= lurus; kalau tidak, berarti ada yang salah hitung
    assert road["distance_km"] >= data["routes"][0]["straight_km"]
    assert road["ratio_vs_straight"] >= 1.0


def test_monitor_nasional_melihat_semua_kiriman_aktif(client, monitor_headers):
    data = client.get("/supplier-routes", headers=monitor_headers).json()
    tujuan = {row["destination_name"] for row in data["routes"]}
    assert {"Jakarta", "Bogor", "Cianjur", "Bandung", "Surabaya"} <= tujuan
    assert data["summary"]["scope"] == "nasional"
    assert data["summary"]["reference_location"] is None


def test_kiriman_kedaluwarsa_tidak_digambar(client, monitor_headers):
    data = client.get("/supplier-routes", headers=monitor_headers).json()
    tujuan = {row["destination_name"] for row in data["routes"]}
    # Semarang habis 5 Okt 2026, Palembang habis 10 Sep 2026 (REF demo 16 Okt)
    assert "Semarang" not in tujuan
    assert "Palembang" not in tujuan


def test_sppg_lain_tidak_melihat_kiriman_jakarta(client, far_nutritionist_headers):
    data = client.get("/supplier-routes", headers=far_nutritionist_headers).json()
    tujuan = {row["destination_name"] for row in data["routes"]}
    assert "Jakarta" not in tujuan
    assert tujuan == {"Bogor"}


def test_setiap_baris_jujur_soal_rute(client, monitor_headers):
    """`road` dan `road_missing_reason` saling meniadakan — tidak boleh keduanya."""
    data = client.get("/supplier-routes", headers=monitor_headers).json()
    for row in data["routes"]:
        ada_road = row["road"] is not None
        ada_alasan = row["road_missing_reason"] is not None
        assert ada_road != ada_alasan, f"{row['destination_name']}: {row}"
        if not ada_road:
            assert row["road_missing_reason"] == "belum_disinkron"


def test_kontrak_json_stabil(client, auth_headers):
    data = client.get("/supplier-routes", headers=auth_headers).json()
    assert set(data) == {"routes", "summary"}
    assert KUNCI_WAJIB == set(data["routes"][0])
    summary = data["summary"]
    assert summary["routes"] == len(data["routes"])
    assert summary["with_road"] + summary["without_road"] == summary["routes"]
    assert summary["active_only"] is True


def test_filter_komoditas_dihormati(client, monitor_headers):
    telur = client.get("/supplier-routes?commodity=telur", headers=monitor_headers).json()
    assert telur["routes"] and all(r["commodity"] == "telur" for r in telur["routes"])
    # ayam hanya dipakai kiriman Semarang yang sudah kedaluwarsa → nol, bukan semua
    ayam = client.get("/supplier-routes?commodity=ayam", headers=monitor_headers).json()
    assert ayam["routes"] == []
    assert ayam["summary"]["routes"] == 0


def test_filter_lokasi_tidak_menembus_cakupan_user(client, auth_headers):
    """Kepala SPPG Jakarta minta lokasi lain → tetap hanya Jakarta (cakupan menang)."""
    data = client.get("/supplier-routes?location=Bogor", headers=auth_headers).json()
    tujuan = {row["destination_name"] for row in data["routes"]}
    assert tujuan <= {"Jakarta"}


def test_limit_divalidasi(client, auth_headers):
    assert client.get("/supplier-routes?limit=0", headers=auth_headers).status_code == 422
    assert client.get("/supplier-routes?limit=201", headers=auth_headers).status_code == 422


def test_kiriman_aktif_tanpa_koordinat_dihitung_jujur(client, monitor_headers):
    """Tujuan tanpa koordinat dilewati dan DILAPORKAN, bukan diberi titik tebakan."""
    from app.core.road_route import build_route_payloads

    kiriman = [
        {
            "batch_id": "x",
            "supplier_id": "y",
            "supplier_name": "Tanpa Koordinat",
            "origin": {"latitude": None, "longitude": None, "name": "?"},
            "destination_id": "z",
            "destination_name": "?",
            "destination": {"latitude": None, "longitude": None, "name": "?"},
            "commodity": "telur",
            "quantity_kg": 1.0,
            "usable_until": None,
            "safety_status": "pass",
        }
    ]
    hasil = build_route_payloads(kiriman, cache={})
    assert hasil["routes"] == []
    assert hasil["dilewati_tanpa_koordinat"] == 1

    # dan endpoint melaporkan hitungan itu apa adanya
    nyata = client.get("/supplier-routes", headers=monitor_headers).json()
    assert "dilewati_tanpa_koordinat" in nyata["summary"]


def test_tanpa_cache_peta_menyebut_belum_disinkron(client, auth_headers):
    """Kalau cache kosong (mis. belum disinkron), endpoint tidak mengarang garis."""
    with patch("app.api.supplier_routes._read_cache", return_value={}):
        data = client.get("/supplier-routes", headers=auth_headers).json()
    assert data["routes"], "kiriman tetap dilaporkan"
    assert all(row["road"] is None for row in data["routes"])
    assert all(row["road_missing_reason"] == "belum_disinkron" for row in data["routes"])
    assert data["summary"]["with_road"] == 0
