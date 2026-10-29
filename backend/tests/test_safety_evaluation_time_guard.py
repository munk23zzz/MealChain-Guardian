"""Guard `evaluation_time` pada `POST /safety/evaluate` (audit 2026-10-29, AUD-008).

`None` tetap diizinkan: artinya "nilai pada sampel terakhir", perilaku yang
didokumentasikan di `core/safety.py` supaya log historis tidak otomatis stale.
Yang ditutup: pemanggil menggeser jam ke DEPAN sehingga observasi tua tampak
segar dan gerbang staleness lumpuh tanpa mengubah data apa pun.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api.safety import validasi_waktu_evaluasi

SEKARANG = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def test_none_diizinkan_karena_berarti_sampel_terakhir():
    assert validasi_waktu_evaluasi(None, SEKARANG) is None


def test_waktu_lampau_diizinkan():
    assert validasi_waktu_evaluasi(SEKARANG - timedelta(days=2), SEKARANG) is None


def test_waktu_masa_depan_ditolak():
    with pytest.raises(HTTPException) as galat:
        validasi_waktu_evaluasi(SEKARANG + timedelta(days=1), SEKARANG)

    assert galat.value.status_code == 422
    assert "masa depan" in str(galat.value.detail)


def test_toleransi_skew_kecil_masih_diterima():
    assert validasi_waktu_evaluasi(SEKARANG + timedelta(seconds=60), SEKARANG) is None


def test_tanpa_offset_zona_waktu_ditolak():
    with pytest.raises(HTTPException) as galat:
        validasi_waktu_evaluasi(datetime(2026, 10, 29, 12, 0), SEKARANG)

    assert galat.value.status_code == 422
    assert "offset" in str(galat.value.detail)
