"""Fase 12 MG — Joule menyebut konteks sesi demo pada jawaban KPI.

Yang dipaku:

- Bila operator sudah memuat sesi (replay/realtime) dan pemanggil TIDAK
  menyebut cakupan, jembatan mengikuti **sesi yang aktif di backend**
  (`GET /demo/session`), bukan menebak "sesi terbaru".
- Jawaban KPI menyebut mode + jangkar + **id sesi** (8 karakter pertama) supaya
  bisa dicocokkan dengan `GET /demo/session`.
- Tanpa sesi aktif (mode operasional, `/demo/session` 404) cakupannya tetap
  operasional dan kalimat "Waktu acuan" TIDAK muncul.
"""

from __future__ import annotations

import report
import server


def _envelope_demo(sesi_id: str = "8d0f08d9-5c98-45d5-a3fe-ef9d461bca41") -> dict:
    return {
        "period": {
            "key": "today",
            "label": "hari ini",
            "timezone": "Asia/Jakarta",
            "start": "2026-10-27T00:00:00+07:00",
            "end": "2026-10-27T23:59:59+07:00",
        },
        "data_mode": "demo",
        "demo_session_id": sesi_id,
        "demo_session": {
            "id": sesi_id,
            "mode": "replay",
            "evaluation_anchor": "2026-10-08T12:00:00+00:00",
            "dataset_version": "kanon-2026-10-08T12:00:00Z",
        },
        "metrics": [
            {
                "name": "Kelengkapan bukti",
                "unit": "%",
                "state": "available",
                "value": 42.5,
                "provenance": {
                    "evidence_kind": "recorded_fact",
                    "data_basis": "historical_seed",
                    "classification": {"historical_seed": 10, "live": 0},
                },
            }
        ],
    }


class _KlienSesiAktif:
    """Klien palsu: sesi aktif ada, dan opsi KPI dicatat."""

    def __init__(self, sesi: dict | None = None) -> None:
        self.opsi: list[dict] = []
        self._sesi = sesi if sesi is not None else {
            "active": True,
            "session_id": "8d0f08d9-5c98-45d5-a3fe-ef9d461bca41",
            "mode": "replay",
            "evaluation_anchor": "2026-10-08T12:00:00+00:00",
        }

    def health(self) -> dict:
        return {"status": "ok", "sap": {"data_source": "mock"}}

    def demo_session(self) -> dict:
        return self._sesi

    def kpi(self, days: int = 7, *, scope: str = "operational", demo_session_id=None):
        self.opsi.append({"scope": scope, "demo_session_id": demo_session_id})
        if scope == "demo":
            return _envelope_demo(str(demo_session_id))
        return {
            "period": {
                "key": "today",
                "label": "hari ini",
                "timezone": "Asia/Jakarta",
                "start": "2026-10-27T00:00:00+07:00",
                "end": "2026-10-27T23:59:59+07:00",
            },
            "data_mode": "operational",
            "demo_session": None,
            "metrics": [],
        }


def test_kpi_tanpa_cakupan_tetap_operasional_tapi_menyebut_sesi():
    """Angka tetap catatan operasional; konteks sesi WAJIB disebut."""
    klien = _KlienSesiAktif()
    teks = server.render_skill(klien, server.SKILL_KPI, payload={})

    assert klien.opsi == [{"scope": "operational", "demo_session_id": None}]
    assert "Sesi demo aktif" in teks
    assert "mode replay" in teks
    assert "jangkar 8 Okt 2026 19:00 WIB" in teks
    # id sesi ikut disebut supaya bisa dicocokkan dengan /demo/session
    assert "sesi 8d0f08d9" in teks
    assert "bukan hasil simulasi" in teks


def test_kpi_tanpa_sesi_aktif_tetap_operasional():
    klien = _KlienSesiAktif(sesi={"active": False})
    teks = server.render_skill(klien, server.SKILL_KPI, payload={})

    assert klien.opsi == [{"scope": "operational", "demo_session_id": None}]
    assert "Sesi demo aktif" not in teks


def test_cakupan_eksplisit_tetap_dihormati():
    """Pemanggil yang menyebut cakupan tidak dibelokkan oleh sesi aktif."""
    klien = _KlienSesiAktif()
    server.render_skill(klien, server.SKILL_KPI, payload={"scope": "operational"})
    assert klien.opsi == [{"scope": "operational", "demo_session_id": None}]


def test_kalimat_waktu_acuan_menyebut_id_sesi():
    teks = report.kpi_report(_envelope_demo())
    assert "8 Okt 2026 19:00 WIB" in teks
    assert "mode replay" in teks
    assert "sesi 8d0f08d9" in teks
