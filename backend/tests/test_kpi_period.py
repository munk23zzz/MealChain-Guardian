"""Periode KPI dihitung SERVER — kontrak `app.core.kpi_period`.

Kenapa tes ini ada terpisah: sebelum langkah ini, rentang `today`/`7d` dihitung
klien sebagai jam bergulir (24 jam / 168 jam), sehingga "hari ini" bukan hari
kalender dan "7 hari" bukan tujuh tanggal. Kontrak yang diuji di sini memakai
hari kalender Asia/Jakarta, dengan `now` disuntikkan supaya batas tengah malam
dan pergantian bulan bisa diuji tanpa menunggu jam sungguhan.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.kpi_period import (
    LABEL_PERIODE,
    PERIODE_KPI,
    resolve_periode,
)

WIB = timezone(timedelta(hours=7))


def test_kunci_periode_tertutup_dan_berlabel():
    assert PERIODE_KPI == ("today", "7d", "1bulan")
    assert LABEL_PERIODE["today"] == "Hari ini"
    assert LABEL_PERIODE["7d"] == "7 hari"
    assert LABEL_PERIODE["1bulan"] == "1 bulan"


def test_hari_ini_mulai_tengah_malam_wib_bukan_24_jam_bergulir():
    now = datetime(2026, 10, 25, 23, 59, 59, tzinfo=WIB)
    awal, akhir = resolve_periode("today", now)
    # 25 Okt 00.00 WIB = 24 Okt 17.00 UTC
    assert awal == datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
    assert akhir == now
    # 24 jam bergulir akan menghasilkan 2026-10-24T16:59:59Z — bukan itu.


def test_tengah_malam_menggeser_awal_hari_ini():
    sebelum = datetime(2026, 10, 25, 23, 59, 59, tzinfo=WIB)
    sesudah = datetime(2026, 10, 26, 0, 0, 1, tzinfo=WIB)
    awal_sebelum, _ = resolve_periode("today", sebelum)
    awal_sesudah, _ = resolve_periode("today", sesudah)
    assert awal_sebelum == datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
    assert awal_sesudah == datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc)
    assert awal_sesudah - awal_sebelum == timedelta(days=1)


def test_waktu_utc_dikonversi_ke_tanggal_jakarta():
    # 25 Okt 20.00 UTC sudah 26 Okt 03.00 WIB → "hari ini" = 26 Okt.
    now = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
    awal, _ = resolve_periode("today", now)
    assert awal == datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc)


def test_tujuh_hari_adalah_tujuh_tanggal_kalender_termasuk_hari_ini():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=WIB)
    awal, akhir = resolve_periode("7d", now)
    # H-6 = 19 Okt 00.00 WIB = 18 Okt 17.00 UTC
    assert awal == datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)
    assert akhir == now
    tanggal = {awal.astimezone(WIB).date() + timedelta(days=i) for i in range(8)}
    assert (akhir.astimezone(WIB).date()) in tanggal
    assert (akhir.astimezone(WIB).date() - awal.astimezone(WIB).date()).days == 6


def test_satu_bulan_adalah_bulan_berjalan_wib():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=WIB)
    awal, _ = resolve_periode("1bulan", now)
    assert awal == datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)


def test_pergantian_bulan_menggeser_awal_bulan():
    now = datetime(2026, 11, 1, 0, 30, tzinfo=WIB)
    awal_bulan, _ = resolve_periode("1bulan", now)
    awal_hari, _ = resolve_periode("today", now)
    assert awal_bulan == datetime(2026, 10, 31, 17, 0, tzinfo=timezone.utc)
    assert awal_hari == awal_bulan  # 1 Nov 00.00 WIB


def test_akhir_bulan_februari_tidak_melewati_bulan():
    now = datetime(2027, 2, 28, 23, 30, tzinfo=WIB)
    awal, _ = resolve_periode("1bulan", now)
    assert awal == datetime(2027, 1, 31, 17, 0, tzinfo=timezone.utc)
    assert awal.astimezone(WIB).date() == datetime(2027, 2, 1).date()


def test_semua_periode_berakhir_di_now_dan_tidak_terbalik():
    now = datetime(2026, 10, 25, 12, 0, tzinfo=WIB)
    for kunci in PERIODE_KPI:
        awal, akhir = resolve_periode(kunci, now)
        assert akhir == now, kunci
        assert awal < akhir, kunci
        assert awal.tzinfo is not None and akhir.tzinfo is not None


def test_kunci_tak_dikenal_ditolak():
    with pytest.raises(KeyError):
        resolve_periode("30d", datetime(2026, 10, 25, tzinfo=WIB))


def test_now_tanpa_zona_ditolak():
    with pytest.raises(ValueError):
        resolve_periode("today", datetime(2026, 10, 25, 12, 0))
