"""Forecast provider client (S3-07).

Kontrak provider SAP-RPT-1.6 dengan fallback statistik yang jujur:
- label SAP-RPT-1.6 hanya untuk response provider nyata yang terbaca
- gagal / tak terbaca / tidak terkonfigurasi → statistical_fallback
  dari core Sprint 1 (0.5/0.3/0.2) — dipakai ulang, bukan dihitung ulang
- semua panggilan eksternal lewat shared chain S3-05
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

from app.ai_providers.resilience import (
    ProviderUnavailableError,
    with_fallback_chain,
)
from app.core.forecasting_fallback import statistical_forecast

SAP_RPT_LABEL = "SAP-RPT-1.6"


@dataclass
class ForecastResult:
    """Hasil forecast + sumber eksplisit (SAP nyata vs fallback)."""

    forecast_qty_kg: float
    method: str  # "sap_rpt_1_6" | "statistical_fallback"
    provider: str  # "SAP-RPT-1.6" | "statistical_fallback"
    confidence: float | None = None
    fallback_used: bool = False
    attempts: list = field(default_factory=list)


def _build_prompt(history: list[float], horizon_days: int) -> str:
    """Prompt input forecast — data operasional + kontrak output (tanpa
    secret). Kontrak output eksplisit: tanpa ini model menjawab bentuk lain
    (array harian) dan parser menolak → fallback statistik tidak perlu.
    """
    return json.dumps(
        {
            "task": "forecast demand",
            "instruction": (
                "Prediksi total demand untuk horizon di bawah. Jawab HANYA "
                'JSON valid dengan bentuk PERSIS: {"forecast_qty_kg": <angka '
                'total>, "confidence": <0..1>} — tanpa teks lain. Bila lebih '
                'nyaman, boleh {"forecast": [<angka per hari>...]} sepanjang '
                "panjang array = horizon_days; total dihitung dari rata-rata "
                "harian dikali horizon."
            ),
            "history_daily_kg": list(history),
            "horizon_days": horizon_days,
        }
    )


def _parse_sap_response(raw: str) -> tuple[float, float | None] | None:
    """Parse response SAP-RPT-1.6; None bila tidak valid/tanpa angka."""
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    qty = data.get("forecast_qty_kg")
    if not isinstance(qty, (int, float)) or isinstance(qty, bool):
        return None
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = None
    return float(qty), float(confidence) if confidence is not None else None


def _parse_forecast_response(
    raw: str, horizon_days: int
) -> tuple[float, float | None] | None:
    """Parser generik chain model: `forecast_qty_kg` tunggal ATAU array
    harian (`forecast`) — total = rata-rata harian × horizon (det.
    deterministik, bukan hitungan model). None bila tak terbaca."""
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None
    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = None
    qty = data.get("forecast_qty_kg")
    if isinstance(qty, (int, float)) and not isinstance(qty, bool):
        return (
            float(qty),
            float(confidence) if confidence is not None else None,
        )
    daily = data.get("forecast")
    if (
        isinstance(daily, list)
        and daily
        and all(
            isinstance(x, (int, float)) and not isinstance(x, bool)
            for x in daily
        )
    ):
        mean_daily = sum(float(x) for x in daily) / len(daily)
        return (
            mean_daily * max(1, int(horizon_days)),
            float(confidence) if confidence is not None else None,
        )
    return None


def run_forecast(
    history_daily_kg: list[float],
    *,
    horizon_days: int = 7,
    sap_rpt: Callable[[str], str] | None = None,
    timeout_seconds: float | None = 30.0,
    default_chain: list | None = None,
) -> ForecastResult:
    """Forecast demand: SAP-RPT-1.6 bila nyata tersedia, else fallback.

    Urutan prioritas: (1) `sap_rpt` eksplisit (kontrak S3-07, label SAP
    hanya untuk response nyata), (2) `default_chain`/env (label slot:kind
    jujur, method `provider_forecast`), (3) statistical fallback core.
    """
    if sap_rpt is not None:
        return _run_forecast_via_sap(
            history_daily_kg, sap_rpt=sap_rpt, horizon_days=horizon_days,
            timeout_seconds=timeout_seconds,
        )

    chain = default_chain if default_chain is not None else _default_env_chain()
    if chain:
        return _run_forecast_via_chain(
            history_daily_kg, chain=chain, horizon_days=horizon_days,
            timeout_seconds=timeout_seconds,
        )
    return _statistical_result(history_daily_kg, horizon_days, attempts=[])


def _statistical_result(
    history_daily_kg: list[float], horizon_days: int, attempts: list
) -> ForecastResult:
    stat = statistical_forecast(history_daily_kg, horizon_days=horizon_days)
    return ForecastResult(
        forecast_qty_kg=stat["forecast_qty_kg"],
        method="statistical_fallback",
        provider="statistical_fallback",
        confidence=stat["confidence"],
        fallback_used=True,
        attempts=attempts,
    )


def _run_forecast_via_chain(
    history_daily_kg: list[float],
    *,
    chain: list,
    horizon_days: int,
    timeout_seconds: float | None,
) -> ForecastResult:
    """Forecast lewat chain model generik (env); output angka tervalidasi."""
    prompt = _build_prompt(history_daily_kg, horizon_days)
    result = with_fallback_chain(
        primary=chain[0][1],
        prompt=prompt,
        fallback_1=chain[1][1] if len(chain) > 1 else None,
        fallback_2=chain[2][1] if len(chain) > 2 else None,
        timeout_seconds=timeout_seconds,
    )
    parsed = _parse_forecast_response(result.text, horizon_days)
    if parsed is None:
        # output model tak terbaca/tanpa angka → fallback statistik (jujur)
        return _statistical_result(
            history_daily_kg, horizon_days, attempts=result.attempts
        )
    # nama pemenang chain posisional → translasi label jujur slot:kind
    slot_to_index = {"primary": 0, "fallback_1": 1, "fallback_2": 2}
    winner_index = slot_to_index.get(result.provider, 0)
    winner_label = (
        chain[winner_index][0]
        if winner_index < len(chain)
        else result.provider
    )
    qty, confidence = parsed
    return ForecastResult(
        forecast_qty_kg=qty,
        method="provider_forecast",
        provider=winner_label,  # label slot:kind aktual (bukan asumsi)
        confidence=confidence,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
    )


def _run_forecast_via_sap(
    history_daily_kg: list[float],
    *,
    sap_rpt: Callable[[str], str],
    horizon_days: int,
    timeout_seconds: float | None,
) -> ForecastResult:
    """Jalur SAP-RPT-1.6 asli (kontrak S3-07, perilaku tak berubah)."""
    try:
        result = with_fallback_chain(
            primary=sap_rpt,
            prompt=_build_prompt(history_daily_kg, horizon_days),
            timeout_seconds=timeout_seconds,
        )
    except ProviderUnavailableError as exc:
        return _statistical_result(
            history_daily_kg, horizon_days, attempts=exc.attempts
        )
    parsed = _parse_sap_response(result.text)
    if parsed is None:
        return _statistical_result(
            history_daily_kg, horizon_days, attempts=result.attempts
        )
    qty, confidence = parsed
    return ForecastResult(
        forecast_qty_kg=qty,
        method="sap_rpt_1_6",
        provider=SAP_RPT_LABEL,
        confidence=confidence,
        fallback_used=False,
        attempts=result.attempts,
    )


def _default_env_chain() -> list:
    """Chain default forecast dari env (lazy import hindari siklus modul)."""
    from app.ai_providers.ai_provider_chain import build_default_callers

    return build_default_callers("forecast")


def _default_sap_rpt_caller() -> Callable | None:
    """Factory caller SAP-RPT-1.6 dari env (kosong → None, jujur).

    S4-10: mengembalikan pemanggil NYATA ke deployment SAP-RPT-1.6 di SAP AI
    Core (`/predict`). Tak ada panggilan jaringan saat membangun — hanya
    validasi env; env belum lengkap → None supaya `run_forecast` memakai
    chain/statistik dan tidak mengklaim SAP.
    """
    from app.ai_providers.sap_ai_core_caller import build_rpt_caller

    try:
        return build_rpt_caller()
    except RuntimeError:
        return None


def sap_rpt_caller_from_env() -> Callable | None:
    """Alias publik untuk pemanggil produksi (orkestrator Event 1)."""
    return _default_sap_rpt_caller()
