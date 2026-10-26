"""Kontrak skrip demo: penyemaian akun demo harus menyatakan DEMO_MODE.

Sejak temuan D-01 (25 Okt 2026) `app.seed.seed_data --with-demo-users` menolak
berjalan bila `DEMO_MODE` tidak aktif. Skrip `scripts/semai-demo.sh` adalah
jalur yang dipakai tepat sebelum demo, jadi ia WAJIB menyalakan flag itu —
kalau tidak, seluruh persiapan demo berhenti dengan `SystemExit`.

Tes ini murni membaca berkas (tanpa DB, tanpa Docker) supaya bisa dijalankan
di gate mana pun.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _cari_skrip() -> Path | None:
    """Telusuri ke atas: repo bisa di-mount di `/app` (backend saja) atau di root."""
    for induk in Path(__file__).resolve().parents:
        kandidat = induk / "scripts" / "semai-demo.sh"
        if kandidat.is_file():
            return kandidat
    return None


_skrip = _cari_skrip()
if _skrip is None:  # pragma: no cover - hanya di dalam image backend
    pytest.skip(
        "scripts/semai-demo.sh tidak ada di gambar ini; jalankan tes di host",
        allow_module_level=True,
    )
SKRIP: Path = _skrip


def _baris_penyemaian() -> list[str]:
    teks = SKRIP.read_text(encoding="utf-8")
    # gabungkan baris bersambung (backslash) agar satu perintah = satu string
    teks = re.sub(r"\\\n", " ", teks)
    return [
        baris.strip()
        for baris in teks.splitlines()
        if "--with-demo-users" in baris
    ]


def test_skrip_demo_ada():
    assert SKRIP.is_file(), f"skrip demo tidak ditemukan: {SKRIP}"


def test_setiap_penyemaian_akun_demo_menyalakan_demo_mode():
    baris = _baris_penyemaian()
    assert baris, "tidak ada pemanggilan --with-demo-users di skrip demo"
    for perintah in baris:
        assert "DEMO_MODE=true" in perintah, (
            "penyemaian akun demo tanpa DEMO_MODE akan menolak berjalan "
            f"(temuan D-01): {perintah}"
        )
