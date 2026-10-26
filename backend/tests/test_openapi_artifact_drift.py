"""S7: `openapi.json` di repo harus sama dengan skema yang dihasilkan aplikasi.

Sebelum ini artefak berisi 26 path sementara aplikasi punya ±75, sehingga siapa
pun yang memakai berkas itu (klien, dokumentasi, review) membaca kontrak yang
salah. Tes ini mengunci kesamaan HIMPUNAN path + operasi, bukan isi lengkapnya:
perubahan deskripsi/skema tidak boleh memaksa regenerasi manual, tetapi
endpoint baru/hilang harus terlihat.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.main import app

BERKAS = Path(__file__).resolve().parents[1] / "openapi.json"


def _pasangan(skema: dict) -> set[tuple[str, str]]:
    """Himpunan (path, method) — satu entri per operasi nyata."""
    return {
        (path, method)
        for path, isi in skema.get("paths", {}).items()
        for method in isi
    }


def test_artefak_openapi_tidak_basi():
    if not BERKAS.is_file():
        pytest.fail(f"{BERKAS.name} hilang dari repo; regenerasi atau hapus tesnya")

    artefak = json.loads(BERKAS.read_text(encoding="utf-8"))
    nyata = app.openapi()

    kurang = _pasangan(nyata) - _pasangan(artefak)
    lebih = _pasangan(artefak) - _pasangan(nyata)
    assert not kurang, f"endpoint baru belum masuk artefak: {sorted(kurang)[:5]}"
    assert not lebih, f"artefak memuat endpoint yang tidak ada: {sorted(lebih)[:5]}"
