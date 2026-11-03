"""Fase 3 butir 6 — Joule meneruskan label observasi & waktu, tanpa skor baru.

Kutipan kontrak (`MG/phase-03-commodity-evidence.md`):

> **6. Uji agregasi dan Joule.** Campuran batch tidak boleh membuat bukti
> terlemah hilang. Joule meneruskan label observasi dan waktu, tanpa menghitung
> skor baru.

Dan gerbang keluar:

> API dan UI menyebut sumber log dan kelengkapan bukti dengan label yang dapat
> dibedakan pengguna.

Yang dikunci berkas ini:

1. Laporan Joule menyebut **kelengkapan bukti** (`cukup`/`tidak cukup`) dan
   **sumber log** ("log simulasi" untuk seed) dari payload backend — apa adanya.
2. Joule **tidak** mengarang "sensor aktif"/"live" untuk log simulasi.
3. Joule **tidak** menghitung ulang skor: angka yang tidak dikirim backend tidak
   muncul sebagai angka baru.
4. Batch dengan bukti tidak cukup tetap muncul di laporan sebagai "perlu
   verifikasi", tidak dihilangkan.
"""

from __future__ import annotations

import report


def _baris(**ubah) -> dict:
    dasar = {
        "location": "SPPG Cianjur",
        "commodity": "telur",
        "quantity_kg": "300",
        "safety_status": "needs_verification",
        "freshness_score": "0.95",
        "usable_until": "2026-10-12T12:00:00+00:00",
        "quarantine_status": "none",
        "evidence": {
            "temperature_observation": "missing",
            "evidence_state": "insufficient",
            "source": "seed",
            "source_label": "log simulasi",
            "observed_at": None,
            "sample_count": 0,
            "evidence_sufficient": False,
        },
    }
    dasar.update(ubah)
    return dasar


def _teks_dari_report(baris) -> str:
    """Seluruh keluaran laporan yang memuat tabel batch (`supply_report`)."""
    return report.supply_report(baris)


def test_laporan_menyebut_bukti_tidak_cukup():
    teks = _teks_dari_report([_baris()])
    assert "bukti" in teks.lower(), teks
    assert "tidak cukup" in teks.lower(), teks


def test_laporan_menyebut_log_simulasi_bukan_sensor_aktif():
    teks = _teks_dari_report([_baris()]).lower()
    assert "log simulasi" in teks, teks
    assert "sensor aktif" not in teks, teks
    assert " sensor " not in teks, teks


def test_laporan_meneruskan_waktu_observasi():
    baris = _baris(
        evidence={
            "temperature_observation": "observed",
            "evidence_state": "sufficient",
            "source": "seed",
            "source_label": "log simulasi",
            "observed_at": "2026-10-08T11:00:00+00:00",
            "sample_count": 2,
            "evidence_sufficient": True,
        }
    )
    teks = _teks_dari_report([baris])
    # Waktu dirender untuk manusia (WIB), bukan ISO mentah — yang penting
    # tanggal observasinya benar-benar diteruskan, bukan dikarang.
    assert "8 Okt 2026" in teks, teks
    assert "WIB" in teks, teks


def test_batch_tanpa_blok_bukti_tidak_dikarang_sebagai_cukup():
    """Payload lama tanpa `evidence`: jangan mengaku cukup, jangan pula menghapus."""
    baris = _baris()
    baris.pop("evidence")
    teks = _teks_dari_report([baris]).lower()
    assert "tidak tercatat" in teks or "tidak diketahui" in teks, teks


def test_tanpa_skor_baru_yang_tidak_dikirim_backend():
    """Joule tidak boleh memunculkan angka yang tidak ada di payload."""
    baris = _baris(freshness_score=None)
    teks = _teks_dari_report([baris])
    assert "0.95" not in teks
