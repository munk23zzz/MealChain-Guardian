"""Kanal kemajuan putaran agent (29 Okt 2026).

Yang diuji di sini adalah KONTRAK, bukan implementasi: bentuk baris log, isi
yang dibuang, dan janji bahwa siaran tidak pernah menggagalkan putaran.
"""

from __future__ import annotations

from app.services import agent_progress
from app.services.demo_procurement_orchestrator import _TraceStep


def _langkah(nama: str = "DETECT", tool: str | None = "supply.gap", keluaran=None) -> _TraceStep:
    return _TraceStep(
        step_name=nama,
        tool_called=tool,
        input_summary=None,
        output_summary=keluaran if keluaran is not None else {"gap_kg": 780, "supplier_total": 14},
    )


def test_tanpa_token_tidak_ada_siaran() -> None:
    """Klien yang tidak minta streaming tidak membayar apa pun."""
    assert agent_progress.penerbit(None) is None
    assert agent_progress.penerbit("") is None


def test_langkah_terkirim_apa_adanya() -> None:
    antrean = agent_progress.buka("token-uji-1")
    kirim = agent_progress.penerbit("token-uji-1")
    assert kirim is not None
    kirim(_langkah())

    data = antrean.get_nowait()
    assert data["step"] == "DETECT"
    assert data["tool"] == "supply.gap"
    assert data["ringkas"] == "gap_kg=780 · supplier_total=14"
    assert data["at"].endswith("Z")


def test_kanal_ditutup_tidak_melempar() -> None:
    """Peramban menutup tab di tengah putaran — putaran tetap jalan."""
    agent_progress.buka("token-uji-2")
    kirim = agent_progress.penerbit("token-uji-2")
    assert kirim is not None
    agent_progress.tutup("token-uji-2")
    kirim(_langkah())  # tidak boleh melempar


def test_antrean_penuh_tidak_melempar() -> None:
    antrean = agent_progress.buka("token-uji-3")
    kirim = agent_progress.penerbit("token-uji-3")
    assert kirim is not None
    for _ in range(antrean.maxsize):
        kirim(_langkah())
    assert antrean.full()
    kirim(_langkah())  # kelebihan ditelan


def test_ringkas_hanya_skalar_dan_dipotong() -> None:
    teks = agent_progress.ringkas(
        {
            "aktif": True,
            "n": 3,
            "rasio": 0.5,
            "catatan": "x" * 80,
            "bersarang": {"a": 1},
            "daftar": [1, 2],
        }
    )
    assert teks.startswith("aktif=ya · n=3 · rasio=0.5 · catatan=")
    assert "bersarang" not in teks and "daftar" not in teks
    assert "…" in teks


def test_ringkas_kosong_untuk_bukan_dict() -> None:
    assert agent_progress.ringkas(None) == ""
    assert agent_progress.ringkas("teks") == ""
    assert agent_progress.ringkas({}) == ""
