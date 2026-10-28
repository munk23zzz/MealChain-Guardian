"""Surplus per WILAYAH untuk panel di samping grafik kecukupan (28 Okt 2026).

MASALAH yang dipaku. Kartu "Kecukupan pasokan" hanya menjawab satu sisi: lokasi
pengguna × empat komoditas. Pertanyaan berikutnya — "surplusnya ada di mana?" —
tidak bisa dijawab `GET /balance/map`, karena peta akun SPPG dibatasi cakupan
(Ruling 2026-10-14): satu lokasi, jadi tidak ada "daerah lain" untuk dibandingkan.

ATURAN yang ditegakkan di sini:
1. Agregasi per `Location.region`, urut menurun — angka wilayah harus bisa
   ditelusuri ke lokasi sumbernya (jumlah `sources` = `surplus_kg` wilayah).
2. `exclude` membuang lokasi pengguna; kg yang dibuang tetap dilaporkan
   (`totals.excluded_surplus_kg`) supaya tidak ada angka yang menghilang.
3. Surplus hanya dari lokasi yang PERMINTAANNYA tercatat (PLAN-023): pasokan
   besar tanpa baris permintaan bukan surplus.
4. Tanpa data → `available: false` + `reason`, bukan daftar kosong tanpa sebab.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _region(client, params: str, headers) -> dict:
    resp = client.get(f"/surplus/regions?{params}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_agregasi_per_wilayah_urut_menurun(client, auth_headers) -> None:
    body = _region(client, "commodity=beras", auth_headers)
    assert body["available"] is True
    assert body["commodities"] == ["beras"]
    regions = body["regions"]
    assert regions, "empat komoditas kanonik punya surplus beras di beberapa wilayah"

    kg = [r["surplus_kg"] for r in regions]
    assert kg == sorted(kg, reverse=True), "wilayah surplus terbesar harus di atas"

    for r in regions:
        # Angka wilayah harus terurai: nama wilayah, jumlah lokasi, sumber.
        assert r["region"] and r["region"] != "Tanpa wilayah"
        assert r["locations"] == len(r["sources"])
        assert r["surplus_kg"] > 0
        assert r["layak_kg"] <= r["surplus_kg"] + 0.01
        # Sumber per wilayah urut menurun juga.
        sumber = [s["surplus_kg"] for s in r["sources"]]
        assert sumber == sorted(sumber, reverse=True)
        # Jumlah komoditas di wilayah = pecahan yang dilaporkan.
        assert abs(sum(c["surplus_kg"] for c in r["by_commodity"]) - r["surplus_kg"]) < 0.05


def test_total_sama_dengan_jumlah_wilayah(client, auth_headers) -> None:
    body = _region(client, "commodity=telur", auth_headers)
    total = body["totals"]["surplus_kg"]
    jumlah = round(sum(r["surplus_kg"] for r in body["regions"]), 2)
    assert abs(total - jumlah) < 0.05
    assert body["totals"]["source_locations"] == sum(
        r["locations"] for r in body["regions"]
    )
    assert body["totals"]["regions"] == len(body["regions"])


def test_exclude_membuang_lokasi_sendiri_dan_melaporkan_kgnya(
    client, auth_headers
) -> None:
    semua = _region(client, "commodity=telur", auth_headers)
    tanpa_bandung = _region(
        client, "commodity=telur&exclude=Bandung", auth_headers
    )
    assert tanpa_bandung["excluded_location"] == "Bandung"

    nama_sumber = {s["location"] for r in tanpa_bandung["regions"] for s in r["sources"]}
    assert "Bandung" not in nama_sumber, "lokasi pengguna tidak boleh masuk panel"

    selisih = round(
        (semua["totals"]["surplus_kg"] - tanpa_bandung["totals"]["surplus_kg"]), 2
    )
    assert abs(selisih - tanpa_bandung["totals"]["excluded_surplus_kg"]) < 0.05


def test_nama_lokasi_tidak_dikenal_tidak_menggagalkan_panel(
    client, auth_headers
) -> None:
    """Lebih jujur: tidak ada filter yang diam-diam diklaim berhasil."""
    body = _region(client, "commodity=telur&exclude=SPPG-Entah", auth_headers)
    assert body["excluded_location"] is None
    assert body["available"] is True


def test_banyak_komoditas_sekali_panggil(client, auth_headers) -> None:
    """Grafik kecukupan memakai EMPAT komoditas; panel harus satu panggilan."""
    body = _region(
        client,
        "commodity=ayam&commodity=beras&commodity=telur&commodity=wortel",
        auth_headers,
    )
    assert body["commodities"] == ["ayam", "beras", "telur", "wortel"]
    komoditas_pecahan = {
        c["commodity"] for r in body["regions"] for c in r["by_commodity"]
    }
    assert komoditas_pecahan <= set(body["commodities"])
    assert len(komoditas_pecahan) >= 2, "satu panggilan harus memuat >1 komoditas"


def test_tanpa_parameter_komoditas_memakai_semua(client, auth_headers) -> None:
    body = _region(client, "", auth_headers)
    assert set(body["commodities"]) >= {"ayam", "beras", "telur", "wortel"}


def test_ambang_layak_bisa_diatur(client, auth_headers) -> None:
    body = _region(client, "commodity=beras&min_kg=1000", auth_headers)
    assert body["min_surplus_kg"] == 1000.0
    for r in body["regions"]:
        # Hanya sumber ≥ 1.000 kg yang dianggap layak dialihkan.
        layak = sum(s["surplus_kg"] for s in r["sources"] if s["surplus_kg"] >= 1000)
        assert abs(r["layak_kg"] - round(layak, 2)) < 0.05


def test_tanpa_data_menjawab_alasan_bukan_daftar_kosong(
    client, auth_headers
) -> None:
    body = _region(client, "commodity=telur&as_of=2000-01-01T00:00:00Z", auth_headers)
    assert body["available"] is False
    assert body["regions"] == []
    assert body["reason"] == "tidak_ada_surplus_terukur"
    assert body["totals"]["surplus_kg"] == 0.0


def test_komoditas_tidak_dikenal_404(client, auth_headers) -> None:
    resp = client.get("/surplus/regions?commodity=tidak-ada", headers=auth_headers)
    assert resp.status_code == 404


def test_tanpa_token_ditolak(client) -> None:
    assert client.get("/surplus/regions").status_code == 401
