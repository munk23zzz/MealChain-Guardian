"""Test Forecast provider client (S3-07, TDD).

Kontrak:
- label `SAP-RPT-1.6` HANYA untuk response provider yang benar-benar
  sukses dan terbaca — tidak ada SAP response yang di-fabricate
- provider tidak tersedia/gagal/output tak terbaca → statistical_fallback
  dari core Sprint 1 (weighted moving average 0.5/0.3/0.2) — dipakai
  ulang, bukan dihitung ulang di sini
- semua panggilan eksternal lewat chain S3-05
"""

import json

from app.ai_providers.forecast_client import run_forecast
from app.core.forecasting_fallback import statistical_forecast

_HISTORY = [100.0, 120.0, 90.0]


def _sap_ok(prompt):
    return json.dumps({"forecast_qty_kg": 714.0, "confidence": 0.92})


def test_sap_success_label_only_on_real_response():
    calls = []

    def sap_rpt(prompt):
        calls.append(prompt)
        return json.dumps({"forecast_qty_kg": 714.0, "confidence": 0.92})

    result = run_forecast(_HISTORY, horizon_days=7, sap_rpt=sap_rpt)

    assert result.provider == "SAP-RPT-1.6"
    assert result.method == "sap_rpt_1_6"
    assert result.forecast_qty_kg == 714.0
    assert result.fallback_used is False
    assert [a.name for a in result.attempts] == ["primary"]
    # prompt memuat input forecast, bukan secret
    assert "120.0" in calls[0] and "horizon" in calls[0]


def test_sap_unavailable_falls_back_to_statistical_503020():
    def sap_rpt(prompt):
        raise RuntimeError("SAP-RPT-1.6 tidak tersedia")

    result = run_forecast(_HISTORY, horizon_days=7, sap_rpt=sap_rpt)

    expected = statistical_forecast(_HISTORY, horizon_days=7)
    assert result.method == "statistical_fallback"
    assert result.provider == "statistical_fallback"
    assert result.forecast_qty_kg == expected["forecast_qty_kg"]
    assert result.fallback_used is True
    assert [a.name for a in result.attempts] == ["primary"]


def test_no_provider_configured_statistical_without_calls():
    result = run_forecast(_HISTORY, horizon_days=7)  # tanpa provider

    assert result.method == "statistical_fallback"
    assert result.attempts == []  # jujur: tidak ada attempt eksternal
    assert result.fallback_used is True


def test_unparseable_sap_output_is_not_labeled_sap():
    def sap_rpt(prompt):
        return "<<< respons tidak terbaca >>>"

    result = run_forecast(_HISTORY, horizon_days=7, sap_rpt=sap_rpt)

    # tidak boleh memakai label SAP untuk output yang tak terbaca
    assert result.method == "statistical_fallback"
    assert result.provider == "statistical_fallback"
    assert [a.name for a in result.attempts] == ["primary"]


def test_sap_success_without_qty_is_rejected():
    def sap_rpt(prompt):
        return json.dumps({"note": "sukses tapi tanpa angka"})

    result = run_forecast(_HISTORY, horizon_days=7, sap_rpt=sap_rpt)

    assert result.method == "statistical_fallback"


def test_horizon_delegated_to_statistical_core():
    result = run_forecast(_HISTORY, horizon_days=2)

    expected = statistical_forecast(_HISTORY, horizon_days=2)
    assert result.forecast_qty_kg == expected["forecast_qty_kg"]


def _mati(pesan):
    def fn(prompt):
        raise RuntimeError(pesan)

    return fn


def test_chain_panjang_tidak_dipotong_tiga_slot():
    """Slot ke-4 dan seterusnya harus benar-benar dicoba.

    Uji audit 2026-10-11: `_run_forecast_via_chain` hanya meneruskan
    fallback_1/fallback_2, jadi provider ke-4+ tidak pernah dipanggil walau
    `with_fallback_chain` sudah mendukung `fallbacks=[...]` panjang — dan rantai
    yang dipotong membuat forecast jatuh ke statistik padahal provider masih ada.
    """
    chain = [
        ("primary:bedrock", _mati("primary mati"), "bedrock"),
        ("fallback_1:inferhub", _mati("fallback_1 mati"), "inferhub"),
        ("fallback_2:inferhub", _mati("fallback_2 mati"), "inferhub"),
        (
            "fallback_3:inferhub",
            lambda prompt: json.dumps({"forecast_qty_kg": 714.0, "confidence": 0.9}),
            "inferhub",
        ),
    ]
    result = run_forecast(_HISTORY, horizon_days=7, default_chain=chain)

    assert result.method == "provider_forecast"
    assert result.provider == "fallback_3:inferhub"
    assert result.forecast_qty_kg == 714.0
    assert len(result.attempts) == 4
