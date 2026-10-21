"""Rencana alokasi surplus lintas lokasi (2026-10-20).

MASALAH yang dipaku. Panel "Rencana alokasi surplus" di halaman Surplus & Limbah
SELALU kosong: halaman itu hanya dibuka peran SPPG, sedangkan `/balance/map`
untuk peran SPPG hanya mengirim lokasinya sendiri (Ruling 2026-10-14). Panel
memasangkan surplus -> kekurangan dari daftar itu, jadi satu lokasi tidak pernah
menghasilkan pasangan (terukur: Kepala Bandung melihat "0 lokasi surplus").

ATURAN yang ditegakkan di sini:
1. Hitungan greedy murni benar (kebutuhan terbesar diisi surplus terbesar) —
   tanpa DB, cepat.
2. `GET /surplus/allocations` mengirim pasangan lintas wilayah JUGA untuk peran
   SPPG, karena nilainya pasangan hasil olahan (dari, ke, kg, jarak), bukan
   angka mentah supply/demand per lokasi.
3. Tanpa data, endpoint menjawab `available: false` + `reason` — bukan daftar
   kosong tanpa sebab.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.allocation import Node, build_allocations, haversine_km
from app.main import app

JAKARTA = {"region": "DKI Jakarta", "latitude": -6.2088, "longitude": 106.8456}
BANDUNG = {"region": "Jawa Barat", "latitude": -6.9175, "longitude": 107.6191}
BOGOR = {"region": "Jawa Barat", "latitude": -6.5950, "longitude": 106.8166}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _node(nama: str, kg: float, **meta) -> Node:
    return Node(location=nama, kg=Decimal(str(kg)), **meta)


# ---------------------------------------------------------------- hitungan murni


def test_kebutuhan_terbesar_diisi_surplus_terbesar() -> None:
    """Bogor (kebutuhan terbesar) diisi Cianjur (surplus terbesar) lebih dulu."""
    rows = build_allocations(
        [_node("Cianjur", 460.44, **{"region": "Jawa Barat"}),
         _node("Jakarta", 202.0, **JAKARTA)],
        [_node("Bogor", 204.83, **BOGOR),
         _node("Bandung", 35.96, **BANDUNG)],
        limit=6,
    )
    assert [(r["from"], r["to"]) for r in rows] == [
        ("Cianjur", "Bogor"),
        ("Cianjur", "Bandung"),
    ]
    assert rows[0]["kg"] == 204.83
    assert rows[1]["kg"] == 35.96


def test_satu_sumber_melayani_beberapa_tujuan_dan_limit_dihormati() -> None:
    rows = build_allocations(
        [_node("Cianjur", 1000.0, **{"region": "Jawa Barat"})],
        [_node(f"Tujuan{i}", 100.0, **BOGOR) for i in range(5)],
        limit=3,
    )
    assert len(rows) == 3
    assert {r["from"] for r in rows} == {"Cianjur"}


def test_surplus_lokasi_di_bawah_150_kg_tidak_direncanakan() -> None:
    """Permintaan pemilik 20 Okt 2026: surplus < 150 kg jangan masuk rencana."""
    rows = build_allocations(
        [_node("Kecil", 149.99), _node("Besar", 150.0)],
        [_node("Butuh", 500.0)],
        min_surplus_kg=Decimal("150"),
    )
    assert [(r["from"], r["kg"]) for r in rows] == [("Besar", 150.0)]

    kosong = build_allocations(
        [_node("Kecil", 149.99)],
        [_node("Butuh", 500.0)],
        min_surplus_kg=Decimal("150"),
    )
    assert kosong == []


def test_sisi_nol_atau_negatif_tidak_menghasilkan_pasangan() -> None:
    assert build_allocations([_node("A", 0.0)], [_node("B", 100.0)]) == []
    assert build_allocations([_node("A", 100.0)], [_node("B", 0.0)]) == []


def test_region_adalah_wilayah_tujuan_dan_jarak_dibulatkan() -> None:
    rows = build_allocations([_node("Jakarta", 500.0, **JAKARTA)],
                             [_node("Bandung", 120.0, **BANDUNG)])
    assert rows[0]["region"] == "Jawa Barat"
    assert isinstance(rows[0]["distance_km"], int)
    # Jakarta -> Bandung ±118 km; bulatan besar, bukan jarak jalan.
    assert 110 <= rows[0]["distance_km"] <= 125


def test_tanpa_koordinat_jarak_none_bukan_angka_karangan() -> None:
    rows = build_allocations([_node("A", 10.0)], [_node("B", 10.0)])
    assert rows[0]["distance_km"] is None
    assert haversine_km(_node("A", 1.0), _node("B", 1.0)) is None


# ---------------------------------------------------------------- endpoint


def test_peran_sppg_menerima_pasangan_lintas_wilayah(client, auth_headers) -> None:
    """Regresi inti: dulu panel kosong karena peta dibatasi cakupan peran."""
    resp = client.get("/surplus/allocations?commodity=telur", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commodity"] == "telur"
    assert body["available"] is True
    assert body["min_surplus_kg"] == 150.0
    assert body["pairs"], "peran SPPG harus menerima pasangan lintas lokasi"
    for pair in body["pairs"]:
        assert pair["from"] and pair["to"] and pair["from"] != pair["to"]
        assert pair["kg"] >= 150, "alokasi di bawah ambang tidak boleh direncanakan"
    # Kontrak: hanya pasangan hasil olahan, bukan tabel supply/demand mentah.
    assert "locations" not in body
    assert "supply_kg" not in body


def test_tanpa_data_menjawab_alasan_bukan_daftar_kosong(client, auth_headers) -> None:
    resp = client.get(
        "/surplus/allocations?commodity=telur&as_of=2000-01-01T00:00:00Z",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is False
    assert body["pairs"] == []
    assert body["reason"] == "tidak_ada_sisi_terukur"


def test_pasangan_membawa_kelayakan_biaya(client, auth_headers) -> None:
    """6 kg lintas 1.400 km harus terbaca mahal, bukan sekadar "rencana"."""
    resp = client.get("/surplus/allocations?commodity=telur", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    pairs = resp.json()["pairs"]
    assert pairs
    for pair in pairs:
        assert pair["price_per_kg"] > 0
        assert pair["cost_idr"] >= 150_000  # penanganan tetap selalu kena
        assert pair["cost_share_pct"] > 0


def test_komoditas_tidak_dikenal_404(client, auth_headers) -> None:
    resp = client.get("/surplus/allocations?commodity=tidak-ada", headers=auth_headers)
    assert resp.status_code == 404


def test_limit_di_luar_batas_ditolak(client, auth_headers) -> None:
    assert (
        client.get("/surplus/allocations?commodity=telur&limit=99", headers=auth_headers)
        .status_code
        == 422
    )
