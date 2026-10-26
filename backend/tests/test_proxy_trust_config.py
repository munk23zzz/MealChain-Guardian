"""S3: konfigurasi proxy produksi tidak boleh mempercayai forwarded-IP mana pun.

Berkas `docker-compose.prod.yml` hanya ada di pohon repo (host), tidak ikut ke
image backend. Karena itu tes ini mencari berkasnya dengan menelusuri ke ATAS
dari berkas tes, lalu SKIP dengan alasan jelas bila tidak ditemukan — bukan
merah karena `FileNotFoundError` (merah/hijau yang salah alasan tidak boleh
dikutip sebagai bukti gerbang).
"""

from __future__ import annotations

from pathlib import Path

import pytest

NAMA_BERKAS = "docker-compose.prod.yml"


def _cari_compose_prod() -> Path | None:
    """Telusuri ke atas dari berkas tes; None bila tidak ada di pohon ini."""
    for folder in [Path(__file__).resolve().parent, *Path(__file__).resolve().parents]:
        berkas = folder / NAMA_BERKAS
        if berkas.is_file():
            return berkas
    return None


def test_production_backend_does_not_trust_all_forwarded_ips():
    berkas = _cari_compose_prod()
    if berkas is None:
        pytest.skip(
            f"{NAMA_BERKAS} tidak ada di pohon ini (hanya di repo host, "
            "bukan di image backend)"
        )

    compose = berkas.read_text(encoding="utf-8")
    assert '--forwarded-allow-ips="*"' not in compose, (
        "mempercayai X-Forwarded-For dari sumber mana pun membuat pembatas "
        "login per-IP bisa dilewati hanya dengan mengarang header"
    )
    assert "FORWARDED_ALLOW_IPS" in compose
