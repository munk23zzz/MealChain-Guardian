"""Worker Supply — membaca /balance dan tidak menghitung ulang angka."""

from __future__ import annotations

from time import monotonic
from urllib.parse import quote

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


class SupplyWorker(ReadOnlyWorker):
    name = AgentName.SUPPLY

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            path = f"/balance/{quote(location, safe='')}/{quote(commodity, safe='')}"
            data = self._api(context).get(path)
        except AgentApiError as exc:
            latency = self._latency_ms(started)
            if exc.status_code == 404:
                return self._degraded(
                    "Data supply/demand tidak tersedia untuk pasangan ini.",
                    facts={
                        "location": context.location,
                        "commodity": context.commodity,
                        "supply_kg": None,
                        "demand_kg": None,
                        "surplus_kg": None,
                        "shortage_kg": None,
                        "data_state": "tidak_ada_baris",
                    },
                    warnings=[f"api_404: {exc}"],
                    latency_ms=latency,
                )
            return self._error(str(exc), latency_ms=latency)
        except ValueError as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        latency = self._latency_ms(started)
        if not isinstance(data, dict):
            return self._error("respons /balance bukan object", latency_ms=latency)

        supply_state = str(data.get("supply_state") or "terukur").lower()
        demand_state = str(data.get("demand_state") or "terukur").lower()
        data_state = str(data.get("data_state") or "terukur").lower()

        supply_kg = as_number(data.get("supply_kg")) if supply_state == "terukur" else None
        demand_kg = as_number(data.get("demand_kg")) if demand_state == "terukur" else None
        gaps_measured = data_state == "terukur" and supply_kg is not None and demand_kg is not None
        surplus_kg = as_number(data.get("surplus_kg")) if gaps_measured else None
        shortage_kg = as_number(data.get("shortage_kg")) if gaps_measured else None

        facts = {
            "location": data.get("location", context.location),
            "commodity": data.get("commodity", context.commodity),
            "supply_state": supply_state,
            "demand_state": demand_state,
            "data_state": data_state,
            "status": (
                data.get("status")
                if data_state == "terukur" and supply_kg is not None and demand_kg is not None
                else None
            ),
            "supply_kg": supply_kg,
            "demand_kg": demand_kg,
            "surplus_kg": surplus_kg,
            "shortage_kg": shortage_kg,
        }
        citations = []
        for field, value in (
            ("supply_kg", supply_kg),
            ("demand_kg", demand_kg),
            ("surplus_kg", surplus_kg),
            ("shortage_kg", shortage_kg),
        ):
            if value is not None:
                citations.append(
                    self._citation(field, path, field, data.get(field))
                )

        warnings: list[str] = []
        if supply_kg is None:
            warnings.append("supply tidak terukur; nilai kosong, bukan 0")
        if demand_kg is None:
            warnings.append("demand tidak terukur; nilai kosong, bukan 0")
        if supply_kg is not None and demand_kg is not None and not gaps_measured:
            warnings.append("gap tidak dihitung karena data tidak lengkap")

        complete = gaps_measured and surplus_kg is not None and shortage_kg is not None
        summary = (
            f"Pasokan {f'{supply_kg} kg' if supply_kg is not None else 'tidak tersedia'}; "
            f"permintaan {f'{demand_kg} kg' if demand_kg is not None else 'tidak tersedia'}; "
            f"status {facts['status'] or 'tidak dapat disimpulkan'}."
        )
        if complete:
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
            warnings=warnings + ["data supply/demand belum lengkap"],
            latency_ms=latency,
        )

