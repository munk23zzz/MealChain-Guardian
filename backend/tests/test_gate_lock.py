"""Kunci gerbang menolak suite kedua dan melepas kunci dengan benar.

Test ini butuh Postgres (kontainer), karena kuncinya hidup di server DB.
"""

from __future__ import annotations

import pytest

from tests.gate_lock import KUNCI_GERBANG, ambil_kunci, dsn_psycopg, lepas_kunci

DSN = dsn_psycopg(
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
)


def test_dsn_asyncpg_diubah_ke_psycopg() -> None:
    assert dsn_psycopg("postgresql+asyncpg://u:p@h:5432/db").startswith(
        "postgresql+psycopg://"
    )
    assert dsn_psycopg("postgresql+psycopg://u:p@h:5432/db").startswith(
        "postgresql+psycopg://"
    )


def test_kunci_gerbang_dipegang_oleh_sesi_ini() -> None:
    """Fixture sesi sudah memegang kunci: percobaan kedua harus ditolak."""
    assert ambil_kunci(DSN) is None


def test_suite_kedua_ditolak_dan_bisa_masuk_setelah_dilepas() -> None:
    # Kunci terpisah supaya tidak bertabrakan dengan kunci sesi ini.
    kunci = KUNCI_GERBANG + 1
    pertama = ambil_kunci(DSN, kunci)
    assert pertama is not None, "kunci gagal dipegang pada DB yang sunyi"
    try:
        assert ambil_kunci(DSN, kunci) is None, "suite kedua seharusnya ditolak"
    finally:
        lepas_kunci(pertama, kunci)
    ketiga = ambil_kunci(DSN, kunci)
    assert ketiga is not None, "kunci tidak dilepas setelah suite pertama selesai"
    lepas_kunci(ketiga, kunci)


def test_dsn_tidak_terjangkau_melempar_bukan_menggantung() -> None:
    with pytest.raises(Exception):
        ambil_kunci(
            "postgresql+psycopg://mealchain:mealchain_local@127.0.0.1:1/mealchain"
        )
