"""Skill surplus wilayah: laporan surplus per wilayah + rencana alih antar SPPG.

Berkas ini ditulis SEBELUM kodenya (RED dulu, sesuai aturan repo). Tiga hal yang
dikunci di sini pernah jadi sumber jawaban menyesatkan:

1. `/surplus/allocations` bisa mengirim `available: false` dengan `pairs: []` padahal
   ada surplus 232 kg. Perender yang hanya mencetak `pairs` akan berbunyi "tidak ada
   alokasi" — padahal surplusnya sengaja tidak dialihkan karena di bawah ambang.
2. Kata kunci baru tidak boleh merebut pertanyaan pasokan/kebutuhan/limbah yang sudah
   benar (`resolve_skill` deterministik: salah tebak = jawaban salah domain, tanpa error).
3. Nama endpoint, nama field, dan token enum backend tidak boleh bocor ke teks chat.
"""

from __future__ import annotations

import json

import httpx
import pytest

import report
import server
from mealchain_client import MealchainClient

REGIONS = {
    "as_of": "2026-10-30T14:47:42.633694+00:00",
    "commodities": ["ayam", "beras", "telur", "wortel"],
    "excluded_location": None,
    "min_surplus_kg": 150.0,
    "locations_total": 10,
    "available": True,
    "reason": None,
    "totals": {
        "surplus_kg": 3784.0,
        "layak_kg": 3723.0,
        "source_locations": 3,
        "regions": 2,
        "excluded_surplus_kg": 0.0,
        "surplus_unmeasured_locations": 0,
    },
    "regions": [
        {
            "region": "Jawa Barat",
            "surplus_kg": 3454.0,
            "layak_kg": 3454.0,
            "locations": 2,
            "by_commodity": [
                {"commodity": "beras", "surplus_kg": 1580.0},
                {"commodity": "telur", "surplus_kg": 1177.0},
                {"commodity": "wortel", "surplus_kg": 465.0},
                {"commodity": "ayam", "surplus_kg": 232.0},
            ],
            "sources": [
                {"location": "Cianjur", "surplus_kg": 2667.0, "by_commodity": []},
                {"location": "Bogor", "surplus_kg": 787.0, "by_commodity": []},
            ],
        },
        {
            "region": "DKI Jakarta",
            "surplus_kg": 330.0,
            "layak_kg": 269.0,
            "locations": 1,
            "by_commodity": [{"commodity": "telur", "surplus_kg": 330.0}],
            "sources": [{"location": "Jakarta Pusat", "surplus_kg": 330.0, "by_commodity": []}],
        },
    ],
}

ALOKASI_KOSONG = {
    "commodity": "ayam",
    "as_of": "2026-10-30T14:47:42.725734+00:00",
    "locations_total": 10,
    "surplus_locations": 1,
    "shortage_locations": 8,
    "min_surplus_kg": 150.0,
    "totals": {
        "surplus_kg": 232.0,
        "shortage_kg": 100.0,
        "allocatable_kg": 0.0,
        "surplus_below_min_kg": 61.0,
    },
    "available": False,
    "reason": "alokasi_di_bawah_ambang",
    "pairs": [],
}

ALOKASI_ADA = {
    "commodity": "beras",
    "as_of": "2026-10-30T14:47:42.725734+00:00",
    "locations_total": 10,
    "surplus_locations": 2,
    "shortage_locations": 1,
    "min_surplus_kg": 150.0,
    "totals": {
        "surplus_kg": 1580.0,
        "shortage_kg": 400.0,
        "allocatable_kg": 1180.0,
        "surplus_below_min_kg": 0.0,
    },
    "available": True,
    "reason": None,
    "pairs": [
        {
            "from_location": "Cianjur",
            "to_location": "Bandung",
            "quantity_kg": 400.0,
            "distance_km": 61.2,
            "priority": 1,
        }
    ],
}


# --- perender murni -----------------------------------------------------------------------


def test_laporan_memuat_wilayah_dan_angka_dari_backend():
    teks = report.surplus_region_report(REGIONS, [ALOKASI_KOSONG])
    assert "Jawa Barat" in teks and "DKI Jakarta" in teks
    # angka backend, gaya Indonesia (bukan hasil hitungan jembatan)
    assert "3.454 kg" in teks
    assert "330 kg" in teks
    # wilayah sumber ikut terbaca supaya jawabannya bisa ditindaklanjuti
    assert "Cianjur" in teks and "Bogor" in teks


def test_alokasi_kosong_dijelaskan_ambangnya_bukan_dibilang_tidak_ada_alokasi():
    teks = report.surplus_region_report(REGIONS, [ALOKASI_KOSONG])
    assert "ambang" in teks.lower()
    # token enum mentah tidak boleh muncul sebagai kalimat jawaban
    assert "alokasi_di_bawah_ambang" not in teks
    # dan tidak boleh menyimpulkan "tidak ada surplus" — surplusnya ada 232 kg
    assert "232 kg" in teks


def test_pasangan_alih_tampil_saat_tersedia():
    teks = report.surplus_region_report(REGIONS, [ALOKASI_ADA])
    assert "Cianjur" in teks and "Bandung" in teks
    assert "1.180 kg" in teks  # allocatable_kg dari backend


def test_tidak_ada_kode_internal_di_jawaban_surplus():
    teks = report.surplus_region_report(REGIONS, [ALOKASI_KOSONG, ALOKASI_ADA])
    terlarang = (
        "/surplus",
        "surplus_allocations",
        "allocatable_kg",
        "surplus_unmeasured_locations",
        "from_location",
        "to_location",
        "priority",
        "backend",
        "endpoint",
        "reason",
    )
    for kata in terlarang:
        assert kata not in teks, f"kode internal bocor ke chat: {kata}"


def test_cap_komoditas_dinyatakan_bukan_disembunyikan():
    teks = report.surplus_region_report(REGIONS, [ALOKASI_KOSONG], dilewati=3)
    assert "3 komoditas" in teks


# --- routing ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kalimat",
    [
        "surplus antar wilayah sekarang bagaimana?",
        "surplus wilayah mana yang paling besar",
        "rencana alih surplus beras antar SPPG",
        "realokasi pangan lintas daerah",
        "sebaran surplus per daerah",
    ],
)
def test_kalimat_surplus_wilayah_masuk_skill_surplus(kalimat):
    skill, _ = server.resolve_skill(kalimat)
    assert skill == server.SKILL_SURPLUS, kalimat


@pytest.mark.parametrize(
    "kalimat, diharapkan",
    [
        # tidak boleh direbut: pertanyaan saldo & pasokan biasa
        ("bagaimana keseimbangan pasokan dan kebutuhan?", server.SKILL_SUPPLY),
        ("pasokan beras di Bandung masih surplus?", server.SKILL_SUPPLY),
        ("stok telur di Bandung berapa?", server.SKILL_SUPPLY),
        # domain lain tetap di domainnya
        ("kebutuhan ayam minggu depan berapa?", server.SKILL_DEMAND),
        ("limbah pangan bulan ini berapa?", server.SKILL_LOSS),
        ("pemasok mana yang berisiko?", server.SKILL_SUPPLIER_RISK),
    ],
)
def test_kata_kunci_surplus_tidak_merebut_skill_lama(kalimat, diharapkan):
    skill, _ = server.resolve_skill(kalimat)
    assert skill == diharapkan, kalimat


# --- protokol klien nyata -----------------------------------------------------------------


def test_klien_nyata_punya_metode_protokol_surplus():
    """FakeClient di tes menyembunyikan drift protokol; ini yang menjaganya."""
    for nama in ("surplus_regions", "surplus_allocations"):
        assert callable(getattr(MealchainClient, nama, None)), nama


def test_klien_memanggil_path_dan_param_surplus():
    jejak: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        jejak.append(request)
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t", "token": "t"})
        if request.url.path == "/surplus/regions":
            return httpx.Response(200, json=REGIONS)
        if request.url.path == "/surplus/allocations":
            return httpx.Response(200, json=ALOKASI_ADA)
        return httpx.Response(404, json={"detail": "tak ada"})

    client = MealchainClient(
        base_url="http://uji", username="u", password="p",
        transport=httpx.MockTransport(handler),
    )
    assert client.surplus_regions()["regions"]
    assert client.surplus_allocations("beras")["pairs"]
    path = [r.url.path for r in jejak]
    assert "/surplus/regions" in path
    alokasi = next(r for r in jejak if r.url.path == "/surplus/allocations")
    assert alokasi.url.params["commodity"] == "beras"
    assert "limit" in alokasi.url.params


# --- integrasi render_skill ---------------------------------------------------------------

_KOMPODITAS = ["ayam", "beras", "telur", "wortel", "tempe", "tahu"]


class FakeClient:
    """Backend palsu: enam komoditas, supaya cap kerja per jawaban ikut teruji."""

    def __init__(self) -> None:
        self.dipanggil: list[str] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def close(self) -> None:
        return None

    def health(self) -> dict:
        self.dipanggil.append("health")
        return {"status": "ok", "sap": {"data_source": "MOCK", "is_mixed": False}}

    def surplus_regions(self) -> dict:
        self.dipanggil.append("surplus_regions")
        return {**REGIONS, "commodities": _KOMPODITAS}

    def surplus_allocations(self, commodity: str, limit: int = 8) -> dict:
        self.dipanggil.append(f"surplus_allocations:{commodity}")
        return {**ALOKASI_KOSONG, "commodity": commodity}


def test_render_skill_surplus_membatasi_komoditas_dan_mengatakannya():
    klien = FakeClient()
    teks = server.render_skill(klien, server.SKILL_SURPLUS)
    dipanggil = [d for d in klien.dipanggil if d.startswith("surplus_allocations:")]
    assert len(dipanggil) == server.SURPLUS_COMMODITY_LIMIT, dipanggil
    assert "Surplus per wilayah" in teks
    # dua komoditas tidak diperiksa → harus dinyatakan, bukan disembunyikan
    sisa = len(_KOMPODITAS) - server.SURPLUS_COMMODITY_LIMIT
    assert f"{sisa} komoditas" in teks


def test_render_skill_surplus_memakai_komoditas_yang_disebut_pengguna():
    klien = FakeClient()
    teks = server.render_skill(klien, server.SKILL_SURPLUS, teks="alih surplus tahu")
    dipanggil = [d for d in klien.dipanggil if d.startswith("surplus_allocations:")]
    assert dipanggil[0] == "surplus_allocations:tahu", dipanggil
    assert "tahu" in teks.lower()


def test_artefak_json_skill_surplus_terbaca():
    """Kontrak JSON eksplisit: {"skill": "surplus_region"} memilih skill ini."""
    skill, payload = server.resolve_skill(json.dumps({"skill": "surplus_region"}))
    assert skill == server.SKILL_SURPLUS and payload["skill"] == "surplus_region"
