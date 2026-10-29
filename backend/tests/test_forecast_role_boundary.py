"""Batas peran peramalan (`Rules.md` §1.1).

Angka dari model tabular hanya boleh mengisi **kebutuhan**. Biaya, kesegaran,
masa layak, dan status keamanan pangan harus tetap deterministik dari
`backend/app/core/*`. Tes ini menegakkan batas itu di tingkat impor: kalau suatu
saat ada yang menyambungkan keluaran model ke modul keselamatan/biaya, tes gagal
sebelum kode itu sempat dipakai di demo.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[1] / "app"

#: Modul yang angkanya menentukan keselamatan, biaya, atau keputusan.
TERLARANG = [
    "core/temperature.py",
    "core/safety.py",
    "core/safe_delivered_cost.py",
    "core/commercial_cost.py",
    "core/receipt_scoring.py",
    "core/batch_eligibility.py",
    "services/batch_eligibility_service.py",
]

#: Apa pun yang boleh membawa keluaran model ke dalam perhitungan.
TERLARANG_IMPOR = ("app.ai_providers", "app.services.forecast_service")


def _impor(path: Path) -> set[str]:
    pohon = ast.parse(path.read_text(encoding="utf-8"))
    nama: set[str] = set()
    for node in ast.walk(pohon):
        if isinstance(node, ast.ImportFrom) and node.module:
            nama.add(node.module)
            for alias in node.names:
                nama.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                nama.add(alias.name)
    return nama


@pytest.mark.parametrize("relatif", TERLARANG)
def test_modul_keselamatan_dan_biaya_tidak_mengimpor_model(relatif: str):
    path = AKAR / relatif
    if not path.is_file():
        pytest.skip(f"{relatif} tidak ada pada repo ini")

    dipakai = _impor(path)
    pelanggaran = sorted(
        nama
        for nama in dipakai
        if any(
            nama == terlarang or nama.startswith(f"{terlarang}.")
            for terlarang in TERLARANG_IMPOR
        )
    )

    assert not pelanggaran, (
        f"{relatif} mengimpor {pelanggaran}. Keluaran model peramalan tidak boleh "
        "menentukan biaya/kesegaran/keamanan pangan (Rules.md §1.1)."
    )


def test_hanya_satu_modul_yang_memanggil_model_peramalan():
    """`run_forecast`/`sap_rpt_caller_from_env` hanya boleh dipakai satu pintu."""
    pemakai: list[str] = []
    for path in AKAR.rglob("*.py"):
        teks = path.read_text(encoding="utf-8")
        if "run_forecast(" in teks or "sap_rpt_caller_from_env(" in teks:
            pemakai.append(str(path.relative_to(AKAR)).replace("\\", "/"))

    diizinkan = {
        "ai_providers/forecast_client.py",  # definisi
        "services/forecast_service.py",  # satu-satunya pemanggil
    }
    assert set(pemakai) <= diizinkan, (
        "pemanggilan model peramalan di luar satu pintu: "
        f"{sorted(set(pemakai) - diizinkan)}"
    )
