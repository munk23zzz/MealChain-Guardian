"""F-01: tidak boleh ada DSN berkredensial tertulis di dalam kode repo.

Kredensial yang tertulis di berkas sumber ikut ke setiap salinan repo, arsip, image,
dan riwayat git. Yang diperiksa: berkas yang dijalankan dari repo (agen, skrip, dan
sebagian backend), bukan `.env` (memang tempatnya rahasia).

Dijalankan dari host (venv backend):
    python -m pytest -q tests/test_kredensial_db_tidak_di_kode.py
Di dalam image backend, direktori `agent/` dan `scripts/` tidak ikut ter-mount, jadi
tes ini di-skip — bukan berarti lulus.

Pengecualian yang disengaja: kata sandi **default dev** (`mealchain_local`) di
backend/seed tidak dihitung pelanggaran (sudah tercatat sebagai F-08, Low). Di `agent/`
dan `scripts/` pengecualian itu TIDAK berlaku.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _akar_repo() -> Path | None:
    for induk in Path(__file__).resolve().parents:
        if (induk / "agent" / "tunnel_watchdog.py").exists():
            return induk
    return None


AKAR = _akar_repo()
if AKAR is None:  # pragma: no cover - hanya di dalam image backend
    pytest.skip("agent/ tidak ada di gambar ini (tes jalan di host)", allow_module_level=True)
AKAR_REPO: Path = AKAR

# postgresql://pengguna:SANDI@host  atau postgresql+psycopg://pengguna:SANDI@host
POLA_DSN = re.compile(
    r"postgresql(?:\+\w+)?://(?P<pengguna>[^\s'\"<>:/]*):(?P<sandi>[^\s'\"@<>]+)@",
    re.IGNORECASE,
)
PETUNJUK_VARIABEL = ("${", "$(", "%(", "{{", "<", "***", "[REDACTED]", "...")
# Default dev yang sudah tercatat sebagai F-08 (Low); bukan rahasia produksi.
SANDI_DEV_DIIZINKAN = "mealchain_local"
# Di dua direktori ini pengecualian default dev TIDAK berlaku.
DIR_KETAT = ("agent/", "scripts/")

DIR_PINDAI = ("agent", "scripts", "backend/app", "backend/scripts", "sap-joule")
SUFIKS = {".py", ".sh", ".yml", ".yaml"}
LEWATI = {"__pycache__", ".venv", "node_modules", "_qa", ".next", "dist"}


def _kandidat() -> list[Path]:
    hasil: list[Path] = []
    for rel in DIR_PINDAI:
        dasar = AKAR_REPO / rel
        if not dasar.exists():
            continue
        for p in dasar.rglob("*"):
            if p.suffix.lower() not in SUFIKS or not p.is_file():
                continue
            if any(bagian in LEWATI for bagian in p.parts):
                continue
            hasil.append(p)
    return hasil


def test_tidak_ada_dsn_berkredensial_di_kode() -> None:
    pelanggaran: list[str] = []
    for p in _kandidat():
        rel = p.relative_to(AKAR_REPO).as_posix()
        isi = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for nomor, baris in enumerate(isi, 1):
            for cocok in POLA_DSN.finditer(baris):
                if any(tanda in cocok.group(0) for tanda in PETUNJUK_VARIABEL):
                    continue  # DSN dibangun dari variabel/placeholder, bukan literal
                if cocok.group("sandi") == SANDI_DEV_DIIZINKAN and not rel.startswith(DIR_KETAT):
                    continue  # default dev yang sudah didokumentasikan (F-08, Low)
                pelanggaran.append(f"{rel}:{nomor}")
    assert not pelanggaran, (
        "DSN berkredensial tertulis di kode (pindahkan ke env; jangan cetak nilainya): "
        + ", ".join(sorted(pelanggaran))
    )


def test_watchdog_membangun_dsn_dari_lingkungan() -> None:
    berkas = AKAR_REPO / "agent" / "tunnel_watchdog.py"
    teks = berkas.read_text(encoding="utf-8", errors="replace")
    assert "DATABASE_URL" in teks, (
        "watchdog harus membaca DATABASE_URL dari kontainer, bukan menyimpan DSN sendiri"
    )
    assert not re.search(r"create_engine\(\s*['\"]postgresql", teks), (
        "create_engine tidak boleh menerima DSN literal"
    )
