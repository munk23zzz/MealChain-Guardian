"""Uji LIVE SAP AI Core (S4-10) — dijalankan EKSPLISIT: `pytest -m live`.

Kenapa ditandai `live`: suite default sengaja hermetik (tanpa jaringan), jadi
`tests/conftest.py` mengosongkan kredensial SAP AI Core untuk semua tes biasa.
Tes di berkas ini justru MEMBUKTIKAN akses nyata — jalankan hanya saat ingin
memverifikasi akses, bukan di setiap `pytest`.

Kredensial tidak ditulis di sini; dibaca dari env kontainer (docker compose).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live

HISTORY = [420.0, 455.0, 430.0, 410.0, 480.0, 500.0, 470.0]


def _client():
    from app.ai_providers.sap_ai_core_caller import (
        SapAiCoreClient,
        SapAiCoreConfig,
    )

    return SapAiCoreClient(SapAiCoreConfig.from_env(), timeout=120.0)


def test_live_llm_invoke_menjawab():
    """General model AI Core menjawab lewat `/invoke` (gaya Bedrock)."""
    teks = _client().invoke("Balas tepat satu kata: pong", max_tokens=24)
    assert isinstance(teks, str)
    assert teks.strip(), "jawaban kosong dari SAP AI Core"


def test_live_rpt_predict_angka_nyata():
    """SAP-RPT-1.6 mengembalikan SATU prediksi per baris query (horizon)."""
    hasil = _client().predict(HISTORY, horizon=7)

    assert len(hasil["predictions"]) == 7
    assert all(p > 0 for p in hasil["predictions"])
    assert hasil["total_kg"] == pytest.approx(sum(hasil["predictions"]))
    # total dijumlahkan KODE (bukan klaim model)
    assert hasil["confidence"] is None or 0.0 <= hasil["confidence"] <= 1.0


def test_live_rpt_lolos_jalur_forecast_dengan_label_jujur():
    """Jalur produksi: `run_forecast` + RPT nyata → label SAP-RPT-1.6."""
    from app.ai_providers.forecast_client import (
        run_forecast,
        sap_rpt_caller_from_env,
    )

    caller = sap_rpt_caller_from_env()
    assert caller is not None, "env SAP AI Core tidak lengkap di kontainer"

    hasil = run_forecast(HISTORY, horizon_days=7, sap_rpt=caller)

    assert hasil.method == "sap_rpt_1_6"
    assert hasil.provider == "SAP-RPT-1.6"
    assert hasil.fallback_used is False
    assert hasil.forecast_qty_kg > 0
