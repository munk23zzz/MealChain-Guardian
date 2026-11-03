"""Fase 10 MG — Joule: mode, sesi, dan waktu acuan pada jawaban.

Yang dipaku di sini (rencana `phase-10-demo-joule.md` butir 4):

1. **Sesi dan mode sampai ke backend.** `kpi()` menerima `demo_session_id`
   hanya bila cakupan demo diminta eksplisit; tidak ada jalur "sesi terbaru".
2. **Waktu acuan ditulis.** Laporan simulasi menyebut jangkar evaluasi sesi
   (`8 Okt 2026 19:00 WIB` untuk jangkar kanon 12:00 UTC) — bukan "hari ini"
   yang membuat angka 8 Oktober terbaca sebagai kejadian hari ini.
3. **Tidak mengarang acuan.** Sesi tanpa jangkar (baris lama) tidak diberi
   tanggal; kalimat itu dilewati.
4. **Tidak ada klaim palsu.** Laporan tidak menyebut "sensor aktif" atau
   "SAP production" untuk dataset simulasi.
5. **Approval tetap ditolak** dan diarahkan ke UI MealChain; jembatan ini tidak
   punya jalur tulis.

Tanpa backend hidup: `httpx.MockTransport` untuk klien, objek palsu untuk
`render_skill`.
"""

from __future__ import annotations

import httpx

import report
import server
from mealchain_client import MealchainClient

API = "http://backend.test"

#: Jangkar kanon replay (12:00 UTC) — di WIB menjadi 19:00.
JANGKAR_KANON = "2026-10-08T12:00:00+00:00"


def _client(handler) -> MealchainClient:
    return MealchainClient(
        base_url=API,
        username="bgn.monitor@demo.local",
        password="Demo#BGN2026",
        transport=httpx.MockTransport(handler),
    )


def _envelope(**tambahan) -> dict:
    amplop = {
        "period": {
            "key": "today",
            "label": "hari ini",
            "timezone": "Asia/Jakarta",
            "start": "2026-10-08T00:00:00+07:00",
            "end": "2026-10-08T23:59:59+07:00",
        },
        "data_mode": "demo",
        "demo_session_id": "sesi-demo-1",
        "demo_session": {
            "id": "sesi-demo-1",
            "mode": "replay",
            "evaluation_anchor": JANGKAR_KANON,
            "dataset_version": "kanon-2026-10-08T12:00:00Z",
        },
        "metrics": [
            {
                "name": "Meal Continuity Rate",
                "unit": "percent",
                "state": "available",
                "value": "90.00",
                "reason": None,
                "provenance": {"evidence_kind": "recorded_fact"},
            }
        ],
    }
    amplop.update(tambahan)
    return amplop


# ------------------------------------------------- 1. sesi sampai ke backend


def test_kpi_membawa_sesi_yang_diminta():
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t", "role": "bgn_monitor"})
        panggilan.append(request)
        return httpx.Response(200, json=_envelope())

    with _client(handler) as client:
        client.kpi(scope="demo", demo_session_id="sesi-demo-1")

    params = panggilan[-1].url.params
    assert params["include_demo"] == "true"
    assert params["demo_session_id"] == "sesi-demo-1"


# ---------------------------------------------------------- 2. waktu acuan


def test_laporan_demo_menyebut_waktu_acuan_dalam_wib():
    teks = report.kpi_report(_envelope())
    assert "Waktu acuan dataset simulasi" in teks
    assert "8 Okt 2026 19:00 WIB" in teks
    assert "mode replay" in teks


def test_laporan_realtime_memakai_jangkar_sesi_bukan_tanggal_kanon():
    teks = report.kpi_report(
        _envelope(
            # Periode sengaja BUKAN 8 Okt: kalau periode ikut 8 Okt, asersi
            # "tanggal kanon tidak muncul" akan lulus/gagal karena tanggal
            # periode, bukan karena jangkar sesi.
            period={
                "key": "today",
                "label": "hari ini",
                "timezone": "Asia/Jakarta",
                "start": "2026-10-27T00:00:00+07:00",
                "end": "2026-10-27T23:59:59+07:00",
            },
            demo_session={
                "id": "sesi-demo-2",
                "mode": "realtime",
                "evaluation_anchor": "2026-10-27T08:15:00+00:00",
            },
        )
    )
    assert "27 Okt 2026 15:15 WIB" in teks
    assert "mode realtime" in teks
    assert "8 Okt 2026" not in teks


def test_laporan_tanpa_jangkar_tidak_mengarang_tanggal():
    teks = report.kpi_report(
        _envelope(demo_session={"id": "sesi-lama", "mode": None, "evaluation_anchor": None})
    )
    assert "Waktu acuan" not in teks
    # Asal data tetap disebut, karena itu yang diketahui.
    assert "sesi demo" in teks.lower()


def test_laporan_operasional_tidak_menyebut_dataset_simulasi():
    teks = report.kpi_report(_envelope(data_mode="operational", demo_session=None))
    assert "Waktu acuan" not in teks
    assert "catatan operasional" in teks


def test_laporan_tidak_mengklaim_sensor_aktif_atau_sap_produksi():
    teks = report.kpi_report(_envelope()).lower()
    assert "sensor aktif" not in teks
    assert "sap production" not in teks
    assert "live sensor" not in teks


# ------------------------------------------------- 3. render_skill (server)


class _KlienBersesi:
    """Backend baca-saja palsu yang mengembalikan amplop berjangkar."""

    def __init__(self) -> None:
        self.opsi: list[dict] = []

    def health(self) -> dict:
        return {"sap": {"data_source": "mock"}}

    def kpi(self, days=None, *, scope="operational", demo_session_id=None):
        cakupan = str(scope or "").strip().lower()
        if cakupan not in ("operational", "demo"):
            raise ValueError("scope KPI harus 'operational' atau 'demo'")
        if cakupan == "demo" and not str(demo_session_id or "").strip():
            raise ValueError("cakupan demo butuh demo_session_id eksplisit")
        self.opsi.append({"scope": cakupan, "demo_session_id": demo_session_id})
        if cakupan == "demo":
            return _envelope()
        return _envelope(data_mode="operational", demo_session=None)


def test_render_skill_menulis_waktu_acuan_dari_sesi():
    klien = _KlienBersesi()
    teks = server.render_skill(
        klien, server.SKILL_KPI, payload={"scope": "demo", "demo_session_id": "sesi-demo-1"}
    )
    assert klien.opsi == [{"scope": "demo", "demo_session_id": "sesi-demo-1"}]
    assert "8 Okt 2026 19:00 WIB" in teks
    assert "simulasi" in teks.lower()


def test_render_skill_operasional_tanpa_sesi_tetap_menyebut_asal():
    klien = _KlienBersesi()
    teks = server.render_skill(klien, server.SKILL_KPI, payload={})
    assert klien.opsi == [{"scope": "operational", "demo_session_id": None}]
    assert "catatan operasional" in teks
    assert "Waktu acuan" not in teks


# ------------------------------------------------------- 4. tidak ada jalur tulis


def test_antrean_persetujuan_mengarahkan_ke_ui_bukan_menyetujui():
    # Satu baris usulan: kalimat "tidak bisa disetujui dari Joule" hanya muncul
    # pada laporan berisi baris (bukan pada jawaban "belum ada usulan").
    baris = {
        "id": "590ce354-dff4-4a86-af13-1d01ecb05c5c",
        "decisionType": "supplier_procurement",
        "sourceLocation": "Cianjur",
        "targetLocation": "Jakarta",
        "commodity": "beras",
        "quantityKg": "1257.14",
        "status": "pending_approval",
    }
    teks = report.approval_queue_report([baris], note=None, total_belum=1)
    kecil = teks.lower()
    assert "ui mealchain" in kecil
    assert "tidak ada persetujuan otomatis" in kecil
    # Jembatan ini hanya membaca; tidak boleh ada kalimat yang mengaku menyetujui.
    assert "sudah saya setujui" not in kecil
    assert "saya setujui" not in kecil


def test_klien_joule_tidak_punya_metode_tulis():
    for nama in ("approve", "reject", "execute", "post", "put", "delete", "create_po"):
        assert not hasattr(MealchainClient, nama), f"jembatan tidak boleh punya {nama}()"
