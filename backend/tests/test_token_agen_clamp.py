"""S1 — token agen tidak boleh melewati umur maksimum aplikasi (D-04).

`scripts/buat_token_agen.py` menerbitkan JWT `bgn_monitor` dengan
`exp = now + hari*86400` tanpa batas, padahal `/auth/login` menjepit umur token
lewat `_expire_minutes()`. Token hasil skrip ini hidup lebih lama dari yang
dirancang aplikasi dan langsung diterima semua endpoint.

Kontrak: umur token dari skrip DIJEPIT ke umur maksimum aplikasi.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SKRIP = Path(__file__).resolve().parents[1] / "scripts" / "buat_token_agen.py"


def _modul():
    spec = importlib.util.spec_from_file_location("buat_token_agen", SKRIP)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_umur_token_dijepit_ke_maksimum():
    m = _modul()
    assert m.umur_token_detik(30, maks_detik=2 * 24 * 3600) == 2 * 24 * 3600


def test_umur_normal_dibiarkan():
    m = _modul()
    assert m.umur_token_detik(1, maks_detik=2 * 24 * 3600) == 24 * 3600


def test_nilai_tidak_masuk_akal_ditolak():
    m = _modul()
    assert m.umur_token_detik(0, maks_detik=2 * 24 * 3600) == 3600
