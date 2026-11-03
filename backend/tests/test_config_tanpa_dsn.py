"""F-08: `Settings.database_url` tidak boleh punya default berkredensial.

Kenapa: default di kode berarti setiap salinan repo membawa DSN dev lengkap dengan
kata sandi. Di lingkungan baru yang lupa menyetel env, aplikasi diam-diam menulis ke
DB dev — bukan gagal cepat. Tes ini mengunci dua hal: tidak ada literal DSN di sumber
konfigurasi, dan Settings MENOLAK dibuat tanpa `DATABASE_URL`.

Bukti audit: `DATABASE_LINEAGE_AND_USAGE_AUDIT.md` §15 F-08 (Low).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticUndefined

from app.core.config import Settings

BERKAS_CONFIG = Path(__file__).resolve().parents[1] / "app" / "core" / "config.py"


def test_database_url_tidak_punya_default_berkredensial() -> None:
    default = Settings.model_fields["database_url"].default
    nilai = "" if default is PydanticUndefined or default is None else str(default)
    assert "://" not in nilai, (
        "database_url masih punya default berupa DSN: pindahkan ke env "
        "(.env / .env.example) supaya tidak ada kredensial di dalam kode"
    )


def test_sumber_config_tidak_memuat_dsn_literal() -> None:
    teks = BERKAS_CONFIG.read_text(encoding="utf-8")
    assert "postgresql" not in teks, (
        "config.py masih menyebut DSN postgres; default harus kosong dan wajib dari env"
    )


def test_settings_menolak_dibuat_tanpa_database_url(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    kosong = tmp_path / "kosong.env"
    kosong.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError):
        Settings(_env_file=str(kosong))
