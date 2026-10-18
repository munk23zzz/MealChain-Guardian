"""Worker Demand — membaca demand dan forecast, tanpa menghitung ulang."""

from __future__ import annotations

from time import monotonic
from urllib.parse import quote

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


class DemandWorker(ReadOnlyWorker):
    name = AgentName.DEMAND

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        loc = quote(location, safe="")
        com = quote(commodity, safe="")
        demand_path = f"/demand/{loc}/{com}"
        forecast_path = f"/demand/forecast/{loc}/{com}?horizon_days=7"

        demand_data: dict | None = None
        forecast_data: dict | None = None
        warnings: list[str] = []
        demand_ok = False
        forecast_ok = False

        try:
            demand_data = api.get(demand_path)
            demand_ok = True
        except AgentApiError as exc:
            if exc.status_code == 404:
                warnings.append(f"demand tidak ditemukan: {exc}")
            else:
                return self._error(str(exc), latency_ms=self._latency_ms(started))

        try:
            forecast_data = api.get(forecast_path)
            forecast_ok = True
        except AgentApiError as exc:
            if exc.status_code == 404:
                warnings.append(f"forecast tidak tersedia: {exc}")
            elif demand_data is None:
                return self._error(str(exc), latency_ms=self._latency_ms(started))
            else:
                warnings.append(f"forecast gagal: {exc}")

        latency = self._latency_ms(started)
        quantity_kg = as_number(demand_data.get("quantity_kg")) if demand_data else None
        forecast_qty_kg = as_number(forecast_data.get("forecast_qty_kg")) if forecast_data else None
        forecast_confidence = as_number(forecast_data.get("confidence")) if forecast_data else None

        facts = {
            "location": location,
            "commodity": commodity,
            "quantity_kg": quantity_kg,
            "needed_by": demand_data.get("needed_by") if demand_data else None,
            "forecast_qty_kg": forecast_qty_kg,
            "forecast_method": forecast_data.get("method") if forecast_data else None,
            "forecast_confidence": forecast_confidence,
            "forecast_horizon": "7 hari",
        }
        citations = []
        if quantity_kg is not None:
            citations.append(
                self._citation("quantity_kg", demand_path, "quantity_kg", demand_data.get("quantity_kg"))
            )
        if forecast_qty_kg is not None:
            citations.append(
                self._citation(
                    "forecast_qty_kg",
                    forecast_path,
                    "forecast_qty_kg",
                    forecast_data.get("forecast_qty_kg"),
                )
            )
        if forecast_confidence is not None:
            citations.append(
                self._citation(
                    "forecast_confidence",
                    forecast_path,
                    "confidence",
                    forecast_data.get("confidence"),
                )
            )

        if quantity_kg is None:
            warnings.append("demand tidak terukur; nilai kosong, bukan 0")
        if forecast_qty_kg is None:
            warnings.append("forecast tidak tersedia; nilai kosong, bukan 0")

        summary = (
            f"Permintaan {f'{quantity_kg} kg' if quantity_kg is not None else 'tidak tersedia'}; "
            f"forecast 7 hari {f'{forecast_qty_kg} kg' if forecast_qty_kg is not None else 'tidak tersedia'}."
        )
        if demand_ok and forecast_ok:
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                latency_ms=latency,
            )
        return self._degraded(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            latency_ms=latency,
        )

