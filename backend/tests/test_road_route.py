"""Rute jalan (OSRM) — modul murni, TDD RED dulu.

Keputusan pemilik 2026-10-16 (dua tanya-jawab):
1. Garis di peta = **mengikuti JALAN** lewat OSRM (bukan garis lurus).
2. Geometri diambil **saat seeding/sync** dan disimpan di DB (tabel cache),
   supaya demo tidak butuh internet dan server OSRM demo tidak dibanjiri.

Yang diuji di sini hanya bagian MURNI (tanpa jaringan, tanpa DB):
- URL permintaan benar (OSRM memakai urutan lon,lat — tertukar = rute salah benua)
- kunci cache stabil & normal (4 desimal), beda profil = beda kunci
- penguraian respons NYATA (fixture hasil panggilan sungguhan ke OSRM)
- kegagalan dijelaskan dengan alasan, TIDAK pernah menghasilkan geometri karangan
- rencana sinkronisasi: yang sudah ada dilewati, duplikat dalam satu permintaan dihitung
- perakitan payload endpoint: jarak lurus dari server + jarak jalan dari cache; tanpa
  cache → `road` null + alasan jujur "belum_disinkron"
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.road_route import (
    ALASAN_BELUM_DISINKRON,
    ALASAN_RESPONS_TIDAK_DIKENAL,
    ALASAN_RUTE_TIDAK_DITEMUKAN,
    RoadRouteError,
    build_route_payloads,
    osrm_url,
    parse_osrm_route,
    plan_route_sync,
    route_key,
)

FIXTURE = Path(__file__).parent / "fixtures" / "osrm_cianjur_jakarta.json"

# Koordinat nyata: Supplier A Cianjur (7a/Fase 9) -> SPPG Jakarta (seed)
ORIGIN = (-6.8420, 107.1426)
DEST = (-6.2088, 106.8456)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


# ---------------------------------------------------------------------------
# URL permintaan
# ---------------------------------------------------------------------------


def test_url_memakai_urutan_lon_lat():
    """OSRM menuntut `lon,lat`. Tertukar → rute salah benua, bukan error jelas."""
    url = osrm_url("https://router.project-osrm.org", ORIGIN[0], ORIGIN[1], DEST[0], DEST[1])
    assert "107.1426,-6.8420;106.8456,-6.2088" in url
    assert "/route/v1/driving/" in url


def test_url_meminta_geometri_ringkas_geojson():
    url = osrm_url("https://contoh.test", ORIGIN[0], ORIGIN[1], DEST[0], DEST[1])
    assert "overview=full" in url
    assert "geometries=geojson" in url
    assert "alternatives=false" in url
    assert "steps=false" in url


def test_url_membuang_garis_miring_di_ujung_base():
    url = osrm_url("https://contoh.test/", ORIGIN[0], ORIGIN[1], DEST[0], DEST[1])
    assert "contoh.test/route/v1" in url
    assert "contoh.test//route" not in url


# ---------------------------------------------------------------------------
# Kunci cache
# ---------------------------------------------------------------------------


def test_kunci_normal_empat_desimal():
    """Pembulatan 4 desimal: nilai yang mirip tapi beda <11 m → kunci sama.

    Sengaja TIDAK memakai nilai tepat di tengah pembulatan (mis. -6.84205):
    perilaku tie-rounding float bukan yang sedang diuji di sini — yang penting
    kunci stabil untuk titik yang praktis sama.
    """
    k1 = route_key(-6.842049, 107.14261, -6.20881, 106.84561)
    k2 = route_key(-6.8420, 107.1426, -6.2088, 106.8456)
    assert k1 == k2 == "driving:-6.8420,107.1426>-6.2088,106.8456"


def test_kunci_arah_dan_profil_dibedakan():
    maju = route_key(*ORIGIN, *DEST)
    balik = route_key(*DEST, *ORIGIN)
    assert maju != balik
    assert route_key(*ORIGIN, *DEST, profile="bike") != maju


# ---------------------------------------------------------------------------
# Penguraian respons NYATA
# ---------------------------------------------------------------------------


def test_urai_fixture_nyata_osrm():
    hasil = parse_osrm_route(_fixture())
    assert hasil["distance_m"] == 111230  # 111229.5 m dibulatkan
    assert hasil["duration_s"] == 5126  # 5126.4 s dibulatkan
    assert hasil["geometry"]["type"] == "LineString"
    assert len(hasil["geometry"]["coordinates"]) == 36
    assert hasil["source"] == "osrm"


def test_urai_tidak_menukar_lon_lat():
    """Titik pertama = Cianjur: lon ~107,14 (bukan lat ~-6,84)."""
    titik = parse_osrm_route(_fixture())["geometry"]["coordinates"][0]
    assert titik[0] == pytest.approx(107.1427, abs=0.001)
    assert titik[1] == pytest.approx(-6.8422, abs=0.001)


def test_urai_jarak_dan_durasi_bulat_positif():
    hasil = parse_osrm_route(_fixture())
    assert isinstance(hasil["distance_m"], int)
    assert isinstance(hasil["duration_s"], int)
    assert hasil["distance_m"] > 0 and hasil["duration_s"] > 0


def test_kode_noroute_menjelaskan_rute_tidak_ditemukan():
    with pytest.raises(RoadRouteError) as err:
        parse_osrm_route({"code": "NoRoute", "routes": []})
    assert err.value.reason == ALASAN_RUTE_TIDAK_DITEMUKAN


def test_kode_aneh_menjelaskan_respons_tidak_dikenal():
    with pytest.raises(RoadRouteError) as err:
        parse_osrm_route({"code": "InvalidQuery"})
    assert err.value.reason == ALASAN_RESPONS_TIDAK_DIKENAL


def test_geometri_kurang_dua_titik_ditolak():
    """Satu titik bukan garis: menggambarnya = mengarang rute."""
    payload = _fixture()
    payload["routes"][0]["geometry"]["coordinates"] = [[107.142666, -6.842156]]
    with pytest.raises(RoadRouteError) as err:
        parse_osrm_route(payload)
    assert err.value.reason == ALASAN_RESPONS_TIDAK_DIKENAL


def test_tipe_geometri_bukan_linestring_ditolak():
    payload = _fixture()
    payload["routes"][0]["geometry"]["type"] = "Point"
    with pytest.raises(RoadRouteError):
        parse_osrm_route(payload)


def test_jarak_bukan_angka_ditolak():
    payload = _fixture()
    payload["routes"][0]["distance"] = "jauh"
    with pytest.raises(RoadRouteError) as err:
        parse_osrm_route(payload)
    assert err.value.reason == ALASAN_RESPONS_TIDAK_DIKENAL


def test_respons_bukan_objek_ditolak():
    with pytest.raises(RoadRouteError):
        parse_osrm_route("bukan json")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Rencana sinkronisasi
# ---------------------------------------------------------------------------


def _permintaan(key: str, nama: str = "A") -> dict:
    return {
        "key": key,
        "nama": nama,
        "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1]},
        "destination": {"latitude": DEST[0], "longitude": DEST[1]},
    }


def test_rencana_melewati_yang_sudah_ada():
    k1 = route_key(*ORIGIN, *DEST)
    k2 = route_key(-6.5950, 106.8166, *DEST)
    rencana = plan_route_sync([_permintaan(k1), _permintaan(k2)], cached_keys={k1})
    assert [r["key"] for r in rencana["perlu_diambil"]] == [k2]
    assert rencana["sudah_ada"] == 1
    assert rencana["duplikat"] == 0


def test_rencana_menghitung_duplikat_dalam_satu_permintaan():
    """Dua batch dari pemasok→tujuan sama = SATU panggilan OSRM."""
    k1 = route_key(*ORIGIN, *DEST)
    rencana = plan_route_sync(
        [_permintaan(k1, "A"), _permintaan(k1, "B")], cached_keys=set()
    )
    assert len(rencana["perlu_diambil"]) == 1
    assert rencana["duplikat"] == 1
    assert rencana["sudah_ada"] == 0


def test_rencana_kosong_tanpa_permintaan():
    rencana = plan_route_sync([], cached_keys=set())
    assert rencana == {"perlu_diambil": [], "sudah_ada": 0, "duplikat": 0}


# ---------------------------------------------------------------------------
# Perakitan payload endpoint
# ---------------------------------------------------------------------------


def _kiriman(**ubah) -> dict:
    row = {
        "batch_id": "b-1",
        "supplier_id": "s-1",
        "supplier_name": "Supplier A Cianjur",
        "origin": {"latitude": ORIGIN[0], "longitude": ORIGIN[1], "name": "Cianjur"},
        "destination_id": "l-1",
        "destination_name": "Jakarta",
        "destination": {
            "latitude": DEST[0],
            "longitude": DEST[1],
            "name": "Jakarta",
        },
        "commodity": "telur",
        "quantity_kg": 800.0,
        "usable_until": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        "safety_status": "pass",
    }
    row.update(ubah)
    return row


def _cache_osrm(fixture: dict) -> dict:
    urai = parse_osrm_route(fixture)
    return {
        route_key(*ORIGIN, *DEST): {
            "distance_m": urai["distance_m"],
            "duration_s": urai["duration_s"],
            "geometry": urai["geometry"],
            "source": urai["source"],
            "fetched_at": datetime(2026, 10, 16, 6, 0, tzinfo=UTC),
        }
    }


def test_payload_tanpa_cache_alasan_belum_disinkron():
    hasil = build_route_payloads([_kiriman()], cache={})
    assert len(hasil["routes"]) == 1
    route = hasil["routes"][0]
    assert route["road"] is None
    assert route["road_missing_reason"] == ALASAN_BELUM_DISINKRON
    # jarak lurus tetap ada (dihitung server) — itu fakta, bukan karangan
    assert route["straight_km"] == pytest.approx(77.68, abs=0.05)
    assert hasil["dilewati_tanpa_koordinat"] == 0


def test_payload_dengan_cache_membawa_geometri_jalan():
    hasil = build_route_payloads([_kiriman()], cache=_cache_osrm(_fixture()))
    road = hasil["routes"][0]["road"]
    assert road is not None
    assert road["distance_km"] == pytest.approx(111.2, abs=0.05)
    assert road["duration_min"] == pytest.approx(85.4, abs=0.1)
    assert road["source"] == "osrm"
    assert len(road["geometry"]["coordinates"]) == 36
    assert road["fetched_at"].startswith("2026-10-16T06:00")
    assert hasil["routes"][0]["road_missing_reason"] is None


def test_payload_menyebut_rasio_jalan_terhadap_lurus():
    """Jalur jalan selalu ≥ lurus; rasionya dipakai UI untuk jujur soal jarak."""
    hasil = build_route_payloads([_kiriman()], cache=_cache_osrm(_fixture()))
    assert hasil["routes"][0]["road"]["ratio_vs_straight"] == pytest.approx(1.43, abs=0.02)


def test_payload_melewati_kiriman_tanpa_koordinat():
    """Tujuan tanpa koordinat tidak bisa digambar → dilewati, bukan diberi titik karangan."""
    rusak = _kiriman(destination={"latitude": None, "longitude": None, "name": "Tanpa"})
    hasil = build_route_payloads([rusak, _kiriman()], cache={})
    assert len(hasil["routes"]) == 1
    assert hasil["dilewati_tanpa_koordinat"] == 1


def test_payload_aman_untuk_daftar_kosong():
    hasil = build_route_payloads([], cache={})
    assert hasil == {"routes": [], "dilewati_tanpa_koordinat": 0}
