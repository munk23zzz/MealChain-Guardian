"""Kontrak kebijakan jendela kirim (Fase 4 MG poin 6).

Modul murni: tidak ada DB, HTTP, atau jam dinding. Semua waktu datang dari
pemanggil (`evaluation_time`), karena jendela kirim yang dihitung dari
"sekarang" tidak bisa diuji dan tidak bisa direproduksi saat demo replay.

Kenapa modul ini ada: `estimate_logistics()` punya parameter
`delivery_window_min` sejak Sprint 1, tetapi TIDAK ADA satu pun pemanggil
produksi yang mengisinya. Akibatnya setiap kandidat selalu `feasible=True` —
bukan karena jadwalnya terpenuhi, melainkan karena tidak ada batas yang
diperiksa. Tes di berkas ini mengunci rumus yang dipakai:
`window = (needed_by - evaluation_time) - lead_time`, dijepit ke nol, dan
`needed_by` yang sudah lewat berarti kandidat gugur.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core import delivery_policy as dp

SEKARANG = datetime(2026, 10, 27, 8, 0, tzinfo=UTC)


def test_jendela_dihitung_dari_kebutuhan_dikurangi_lead_time() -> None:
    """needed_by 4 jam lagi, lead time 30 menit → anggaran angkut 210 menit."""
    hasil = dp.jendela_kirim(
        needed_by=SEKARANG + timedelta(hours=4),
        evaluation_time=SEKARANG,
        lead_time_min=30.0,
    )
    assert hasil.window_min == pytest.approx(210.0)
    assert hasil.state == dp.TERPERNUHI
    assert hasil.needed_by == SEKARANG + timedelta(hours=4)


def test_kebutuhan_yang_sudah_lewat_menghasilkan_terlampaui_dan_nol() -> None:
    hasil = dp.jendela_kirim(
        needed_by=SEKARANG - timedelta(minutes=1),
        evaluation_time=SEKARANG,
        lead_time_min=0.0,
    )
    assert hasil.state == dp.TERLAMPAUI
    # Dijepit ke nol: anggaran negatif tidak boleh menjadi angka yang bisa
    # lolos perbandingan `estimated <= window`.
    assert hasil.window_min == 0.0


def test_tanpa_baris_permintaan_bukan_berarti_jadwal_terpenuhi() -> None:
    """Tanpa `needed_by`, jendela TIDAK BOLEH diklaim terpenuhi."""
    hasil = dp.jendela_kirim(
        needed_by=None, evaluation_time=SEKARANG, lead_time_min=0.0
    )
    assert hasil.state == dp.TIDAK_TERCATAT
    assert hasil.window_min is None


def test_arrival_due_at_diturunkan_dari_estimasi_logistik() -> None:
    tiba = dp.arrival_due_at(SEKARANG, 150.0)
    assert tiba == SEKARANG + timedelta(minutes=150)


def test_lead_time_negatif_ditolak() -> None:
    with pytest.raises(ValueError):
        dp.jendela_kirim(
            needed_by=SEKARANG + timedelta(hours=1),
            evaluation_time=SEKARANG,
            lead_time_min=-1.0,
        )


def test_zona_waktu_campuran_ditolak() -> None:
    """Waktu sadar-zona dicampur waktu naif = perbandingan yang tidak sah."""
    with pytest.raises(ValueError):
        dp.jendela_kirim(
            needed_by=datetime(2026, 10, 27, 12, 0),  # naif
            evaluation_time=SEKARANG,
            lead_time_min=0.0,
        )


def test_kandidat_gugur_bila_estimasi_melebihi_jendela() -> None:
    """Perilaku yang diuji lewat `estimate_logistics`: jendela 60 menit tidak
    cukup untuk perjalanan 150 menit."""
    jendela = dp.jendela_kirim(
        needed_by=SEKARANG + timedelta(minutes=90),
        evaluation_time=SEKARANG,
        lead_time_min=30.0,
    )
    assert jendela.window_min == pytest.approx(60.0)
    assert dp.muat_terlampaui(jendela, estimated_time_min=150.0) is True
    assert dp.muat_terlampaui(jendela, estimated_time_min=45.0) is False


def test_tanpa_jendela_tidak_dianggap_terlampaui_tetapi_ditandai() -> None:
    jendela = dp.jendela_kirim(
        needed_by=None, evaluation_time=SEKARANG, lead_time_min=0.0
    )
    assert dp.muat_terlampaui(jendela, estimated_time_min=999.0) is False
