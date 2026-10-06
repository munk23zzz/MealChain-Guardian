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
    """Prompt input forecast — hanya data operasional, tanpa secret."""
    return json.dumps(
        {
            "task": "forecast demand",
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


def run_forecast(
    history_daily_kg: list[float],
    *,
    horizon_days: int = 7,
    sap_rpt: Callable[[str], str] | None = None,
    timeout_seconds: float | None = 30.0,
) -> ForecastResult:
    """Forecast demand: SAP-RPT-1.6 bila nyata tersedia, else fallback."""
    if sap_rpt is None:
        stat = statistical_forecast(history_daily_kg, horizon_days=horizon_days)
        return ForecastResult(
            forecast_qty_kg=stat["forecast_qty_kg"],
            method="statistical_fallback",
            provider="statistical_fallback",
            confidence=stat["confidence"],
            fallback_used=True,
            attempts=[],
        )

    try:
        result = with_fallback_chain(
            primary=sap_rpt,
            prompt=_build_prompt(history_daily_kg, horizon_days),
            timeout_seconds=timeout_seconds,
        )
    except ProviderUnavailableError as exc:
        # chain habis → fallback statistik; jejak attempt tetap eksplisit
        stat = statistical_forecast(history_daily_kg, horizon_days=horizon_days)
        return ForecastResult(
            forecast_qty_kg=stat["forecast_qty_kg"],
            method="statistical_fallback",
            provider="statistical_fallback",
            confidence=stat["confidence"],
            fallback_used=True,
            attempts=exc.attempts,
        )

    parsed = _parse_sap_response(result.text)
    if parsed is None:
        # output tak terbaca/tanpa angka → TIDAK boleh dilabeli SAP
        stat = statistical_forecast(history_daily_kg, horizon_days=horizon_days)
        return ForecastResult(
            forecast_qty_kg=stat["forecast_qty_kg"],
            method="statistical_fallback",
            provider="statistical_fallback",
            confidence=stat["confidence"],
            fallback_used=True,
            attempts=result.attempts,
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


def _default_sap_rpt_caller() -> Callable | None:
    """Factory caller SAP-RPT-1.6 dari env (kosong → None, jujur)."""
    if not (os.environ.get("SAP_AI_CORE_API_URL") or "").strip():
        return None
    if not (os.environ.get("SAP_AI_CORE_CLIENT_ID") or "").strip():
        return None

    def sap_rpt(prompt: str) -> str:  # pragma: no cover - butuh jaringan
        raise RuntimeError("SAP-RPT-1.6 caller belum terimplementasi penuh")

    return sap_rpt
