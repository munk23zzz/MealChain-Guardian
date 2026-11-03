"""Kontrak pemilihan DB untuk penyemai (audit 21 Okt 2026, keselamatan data).

`_seed_database_url()` dulu HANYA membaca `SEED_DATABASE_URL` dan jatuh ke DSN
compose (`…/mealchain`) bila variabel itu tidak ada — mengabaikan `DATABASE_URL`.
Akibatnya skrip/uji yang sengaja menunjuk salinan (`DATABASE_URL=…mealchain_audit`)
tetap menulis akun & data demo ke DB demo utama. Terbukti: menjalankan
`ensure_demo_users()` dengan DATABASE_URL ke salinan membuat `users` di salinan
tetap kosong sementara DB utama menerima merge-nya.

Aturan baru (aman secara default):
- `SEED_DATABASE_URL` eksplisit selalu menang;
- kalau tidak ada, `DATABASE_URL` dipakai (asyncpg → psycopg), supaya target
  penulisan sama dengan target baca aplikasi;
- baru setelah keduanya kosong, jatuh ke DSN compose.
"""

from __future__ import annotations

import pytest

from app.seed.seed_data import _seed_database_url

SALINAN = "postgresql+asyncpg://u:p@db:5432/mealchain_audit"


@pytest.fixture()
def env(monkeypatch):
    for nama in ("SEED_DATABASE_URL", "DATABASE_URL"):
        monkeypatch.delenv(nama, raising=False)
    return monkeypatch


def test_database_url_dipakai_bila_seed_url_tidak_diset(env):
    env.setenv("DATABASE_URL", SALINAN)
    assert _seed_database_url() == "postgresql+psycopg://u:p@db:5432/mealchain_audit"


def test_seed_url_eksplisit_selalu_menang(env):
    env.setenv("DATABASE_URL", SALINAN)
    env.setenv("SEED_DATABASE_URL", "postgresql+psycopg://x:y@lain:5432/mealchain")
    assert _seed_database_url() == "postgresql+psycopg://x:y@lain:5432/mealchain"


def test_tanpa_keduanya_jatuh_ke_dsn_compose(env):
    # Menguji FALLBACK, jadi tidak boleh memakai DSN aktif (DSN_SYNC mengikuti
    # DATABASE_URL; dengan begitu tes ini merah saat suite jalan di DB lain).
    env.delenv("DATABASE_URL", raising=False)
    env.delenv("SEED_DATABASE_URL", raising=False)
    assert _seed_database_url() == (
        "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
    )


def test_driver_psycopg_dipertahankan(env):
    env.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/mealchain")
    assert _seed_database_url().endswith("/mealchain")
    assert "+psycopg" in _seed_database_url()
