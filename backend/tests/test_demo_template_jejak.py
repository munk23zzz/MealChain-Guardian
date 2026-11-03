"""Jejak agent pada template demo harus berupa FAKTA keputusan, bukan teks template.

Audit data 26 Okt 2026 menemukan 8 dari 85 `agent_traces` berisi
"Langkah DETECT (template status demo)." dan tampil di tab Agent Log sebagai
jejak penalaran. Selain itu `sdc` di trace DECIDE (14.787.096,28) berbeda dari
SDC keputusan (22.080.862,39) untuk keputusan yang sama.
"""

from decimal import Decimal
from types import SimpleNamespace

from app.seed.demo_template import _ringkas_jejak


def putusan(**over):
    dasar = dict(
        decision_type="regional_balance",
        status="executed",
        quantity_kg=Decimal("780"),
        safe_delivered_cost=Decimal("22080862.39"),
    )
    dasar.update(over)
    return SimpleNamespace(**dasar)


def test_tidak_ada_teks_template_di_ringkasan():
    for langkah in ("DETECT", "PREDICT", "DECIDE", "ACT"):
        keluaran = _ringkas_jejak(langkah, putusan())
        teks = str(keluaran).lower()
        assert "template status demo" not in teks
        assert keluaran["status"] == "completed"
        assert keluaran["summary"]


def test_sdc_di_trace_sama_dengan_sdc_keputusan():
    keluaran = _ringkas_jejak("DECIDE", putusan())
    assert keluaran["sdc"] == 22080862.39
    assert "22.080.862,39" in keluaran["summary"]
    assert "780 kg" in keluaran["summary"]


def test_keputusan_tanpa_sdc_tidak_mengarang_angka():
    keluaran = _ringkas_jejak("DECIDE", putusan(safe_delivered_cost=None))
    assert "sdc" not in keluaran
    assert "SDC belum dihitung" in keluaran["summary"]


def test_berat_tidak_diketahui_ditulis_apa_adanya():
    keluaran = _ringkas_jejak("DETECT", putusan(quantity_kg=None))
    assert "berat tidak diketahui" in keluaran["summary"]
    assert "0 kg" not in keluaran["summary"]
