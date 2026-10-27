"""Fase 8 MG — Joule: cakupan, periode, dan estimasi pada laporan KPI.

Yang dipaku di sini (rencana `phase-08-kpi-provenance.md` butir 6):

- `kpi()` menerima opsi cakupan/sesi **sesuai konteks backend**: bawaan
  operasional (tanpa `include_demo`), dan cakupan demo hanya bila sesinya
  disebut eksplisit. Menebak "sesi terbaru" dilarang karena angkanya milik
  sesi lain.
- Laporan menyebut periode, asal angka (operasional vs sesi demo), dan
  menandai nilai yang hanya estimasi — satu kalimat, tanpa jargon.
- Permintaan cakupan yang tidak bisa dijawab ditolak dengan kalimat sebabnya,
  bukan dijawab angka cakupan lain.

Tanpa backend hidup: `httpx.MockTransport` untuk klien, objek palsu untuk
`render_skill`.
"""

from __future__ import annotations

import httpx
import pytest

import report
import server
from mealchain_client import MealchainClient

API = "http://backend.test"


def _client(handler, **kwargs) -> MealchainClient:
    return MealchainClient(
        base_url=API,
        username="bgn.monitor@demo.local",
        password="Demo#BGN2026",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _kpi_envelope(**tambahan) -> dict:
    amplop = {
        "period": {
            "key": "7d",
            "label": "7 hari terakhir",
            "timezone": "Asia/Jakarta",
            "start": "2026-10-20T00:00:00+07:00",
            "end": "2026-10-27T00:00:00+07:00",
        },
        "data_mode": "operational",
        "metrics": [
            {
                "name": "Meal Continuity Rate",
                "unit": "percent",
                "state": "available",
                "value": "90.00",
                "reason": None,
                "provenance": {"evidence_kind": "recorded_fact"},
            },
            {
                "name": "Avoidable Food Loss",
                "unit": "percent",
                "state": "available",
                "value": "2.89",
                "reason": None,
                "provenance": {"evidence_kind": "recorded_fact"},
                "estimate": {
                    "state": "available",
                    "value": "3.40",
                    "unit": "percent",
                    "evidence_kind": "simulated_estimate",
                    "definition": "proyeksi susut dari skor kesegaran",
                },
            },
        ],
    }
    amplop.update(tambahan)
    return amplop


# --------------------------------------------------------------- 1. cakupan


def test_kpi_bawaan_meminta_cakupan_operasional():
    """Tanpa opsi, klien TIDAK meminta data demo: `include_demo` tidak dikirim."""
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1", "role": "bgn_monitor"})
        panggilan.append(request)
        return httpx.Response(200, json=_kpi_envelope())

    with _client(handler) as client:
        client.kpi(days=7)

    params = panggilan[-1].url.params
    assert panggilan[-1].url.path == "/kpi"
    assert "include_demo" not in params
    assert "demo_session_id" not in params


def test_kpi_cakupan_demo_mengirim_sesi_eksplisit():
    """Cakupan demo = `include_demo=true` + satu `demo_session_id` yang disebut."""
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1", "role": "bgn_monitor"})
        panggilan.append(request)
        return httpx.Response(200, json=_kpi_envelope(data_mode="demo"))

    with _client(handler) as client:
        client.kpi(scope="demo", demo_session_id="sesi-abc")

    params = panggilan[-1].url.params
    assert params["include_demo"] == "true"
    assert params["demo_session_id"] == "sesi-abc"


def test_kpi_cakupan_demo_tanpa_sesi_ditolak_tanpa_panggilan():
    """Tidak ada jalur 'sesi terbaru': menolak sebelum HTTP, bukan menebak."""
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        panggilan.append(request)
        return httpx.Response(200, json=_kpi_envelope())

    with _client(handler) as client, pytest.raises(ValueError) as exc:
        client.kpi(scope="demo")

    assert "demo_session_id" in str(exc.value)
    assert all(r.url.path != "/kpi" for r in panggilan)


def test_kpi_cakupan_asing_ditolak():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_kpi_envelope())

    with _client(handler) as client, pytest.raises(ValueError):
        client.kpi(scope="campur")


# ---------------------------------------------------------------- 2. laporan


def test_laporan_operasional_menyebut_periode_dan_asal():
    teks = report.kpi_report(_kpi_envelope())
    assert "Periode:" in teks
    assert "20 Okt 2026" in teks
    assert "catatan operasional" in teks
    assert "sesi demo" not in teks.lower()


def test_laporan_demo_menyebut_simulasi_bukan_hasil_lapangan():
    teks = report.kpi_report(_kpi_envelope(data_mode="demo"))
    kecil = teks.lower()
    assert "sesi demo" in kecil
    assert "simulasi" in kecil
    assert "bukan hasil lapangan" in kecil


def test_laporan_menandai_nilai_estimasi():
    """Nilai proyeksi wajib berlabel `estimasi` — tidak boleh terbaca sebagai fakta."""
    teks = report.kpi_report(_kpi_envelope())
    assert "estimasi 3,4%" in teks
    assert "proyeksi model" in teks.lower()


def test_laporan_tanpa_metrik_tidak_mengarang_angka():
    teks = report.kpi_report({})
    assert report.MISSING in teks or "belum" in teks.lower()
    assert "0%" not in teks


def test_penolakan_cakupan_menyebut_sebab_dan_tidak_mengklaim_demo():
    teks = report.kpi_scope_problem("cakupan demo butuh demo_session_id eksplisit")
    assert "demo_session_id eksplisit" in teks
    assert "catatan operasional" in teks


# ------------------------------------------------- 3. render_skill (server)


class _KlienPalsu:
    """Backend baca-saja palsu: mencatat opsi cakupan yang diminta."""

    def __init__(self) -> None:
        self.opsi: list[dict] = []

    def health(self) -> dict:
        return {"sap": {"data_source": "mock"}}

    def kpi(self, days=None, *, scope="operational", demo_session_id=None):
        # Kontrak `scope` (Fase 8): jawaban menolak cakupan demo tanpa sesi,
        # sama seperti `MealchainClient.kpi` — kalau fake ini lebih longgar,
        # tes render_skill akan lulus atas perilaku yang tidak ada di produksi.
        cakupan = str(scope or "").strip().lower()
        if cakupan not in ("operational", "demo"):
            raise ValueError("scope KPI harus 'operational' atau 'demo'")
        if cakupan == "demo" and not str(demo_session_id or "").strip():
            raise ValueError("cakupan demo butuh demo_session_id eksplisit")
        self.opsi.append({"scope": cakupan, "demo_session_id": demo_session_id})
        return _kpi_envelope(data_mode="demo" if cakupan == "demo" else "operational")


def test_render_skill_meneruskan_cakupan_dan_sesi():
    klien = _KlienPalsu()
    teks = server.render_skill(
        klien,
        server.SKILL_KPI,
        payload={"scope": "demo", "demo_session_id": "sesi-xyz"},
    )
    assert klien.opsi == [{"scope": "demo", "demo_session_id": "sesi-xyz"}]
    assert "simulasi" in teks.lower()


def test_render_skill_menolak_demo_tanpa_sesi_dengan_kalimat():
    klien = _KlienPalsu()
    teks = server.render_skill(klien, server.SKILL_KPI, payload={"scope": "demo"})
    assert "tidak bisa ditampilkan" in teks.lower()
    assert "demo_session_id" in teks
