"""Cek verifier yang tadinya menandai SEMUA putaran demo (28 Okt 2026).

Tiga perilaku yang dikunci di sini:

1. Potongan id (`2e8154ac` → `8154`) bukan besaran, jadi tidak boleh dianggap
   angka tanpa sumber.
2. Tahun (`2026`, `2027`) bukan besaran.
3. Angka yang ditulis sebagai TEKS di fakta (`"900 kg"`, `"55,606 km"`) harus
   masuk `angka_dikenal`; sebelumnya string hanya dibaca utuh sehingga besaran
   berbentuk teks selalu dituduh tanpa sumber.

Keempat, `ledger_tercatat` tidak boleh menuntut blok ledger pada keputusan yang
belum punya aksi — penentunya ada-tidaknya aksi, bukan label status.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.verifier_checks import (  # noqa: E402
    KlaimSupervisor,
    _tahun,
    angka_dalam_teks,
    cek_angka_bersitasi,
    cek_ledger,
)
from agent.verifier_facts import _iter_angka  # noqa: E402


def _klaim(teks: str, status: str = "pending_approval") -> KlaimSupervisor:
    return KlaimSupervisor(
        decision_id="d",
        narrative=teks,
        status=status,
        safety_veto=False,
        gate_verdict="pass",
    )


def test_potongan_id_bukan_angka() -> None:
    assert [r for r, _ in angka_dalam_teks("keputusan 2e8154ac dan bf6fccbd")] == []


def test_tahun_dikenali() -> None:
    assert _tahun("2026") is True
    assert _tahun("2027") is True
    assert _tahun("3010") is False  # besaran, bukan tahun
    assert _tahun("2.026") is False  # bertitik = ribuan


def test_angka_tertanam_di_teks_fakta_masuk_dikenal() -> None:
    nilai = set(_iter_angka({"pasokan": "900 kg", "jarak": "55,606 km"}))
    assert 900.0 in nilai
    assert any(abs(v - 55.606) < 1e-9 for v in nilai)


def test_narasi_dengan_tahun_dan_angka_fakta_lulus() -> None:
    klaim = _klaim("Per 2026: pasokan 900 kg, jarak 55,606 km.")
    hasil = cek_angka_bersitasi(klaim, {}, {900.0, 55.606})
    assert hasil.lulus is True


def test_angka_yang_tidak_ada_di_fakta_tetap_gagal() -> None:
    klaim = _klaim("Pasokan 2.110 kg.")  # 2110 tidak ada di fakta
    hasil = cek_angka_bersitasi(klaim, {}, {900.0})
    assert hasil.lulus is False
    assert "2.110" in hasil.aktual


def test_ledger_tanpa_aksi_lulus_apa_pun_statusnya() -> None:
    for status in ("proposed", "pending_approval", "verifier_flagged"):
        klaim = _klaim("Ledger sudah tercatat.", status)
        hasil = cek_ledger(klaim, {"ledger": {"count": 0, "actions": []}})
        assert hasil.lulus is True, status


def test_ledger_dengan_aksi_tetap_diaudit() -> None:
    klaim = _klaim("Ledger sudah tercatat.", "executed")
    hasil = cek_ledger(klaim, {"ledger": {"count": 0, "actions": ["PO"]}})
    assert hasil.lulus is False
