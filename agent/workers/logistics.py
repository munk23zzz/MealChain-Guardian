"""Logistics Agent — rute aktif dan estimasi jarak/waktu dari server."""

from __future__ import annotations

from time import monotonic
from urllib.parse import urlencode

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


class LogisticsWorker(ReadOnlyWorker):
    name = AgentName.LOGISTICS

    def _run_deterministik(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        query = urlencode({"commodity": commodity, "location": location, "limit": 50})
        routes_path = f"/supplier-routes?{query}"
        try:
            payload = api.get(routes_path)
        except AgentApiError as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list):
            return self._error("respons /supplier-routes tidak memuat daftar 'routes'", latency_ms=self._latency_ms(started))
        routes = [
            route
            for route in raw_routes
            if isinstance(route, dict)
            and str(route.get("destination_name", "")).strip().lower() == location.lower()
            and str(route.get("commodity", "")).strip().lower() == commodity.lower()
        ]

        road_routes = [
            route for route in routes
            if isinstance(route.get("road"), dict) and as_number(route["road"].get("distance_km")) is not None
        ]
        warnings: list[str] = []
        if len(routes) != len(raw_routes):
            warnings.append("sebagian rute tidak cocok dengan lokasi/komoditas dan tidak dipakai")
        if len(road_routes) < len(routes):
            warnings.append("rute ada tetapi geometri jalan belum tersinkron")

        if routes:
            distances = [as_number(route["road"].get("distance_km")) for route in road_routes]
            durations = [as_number(route["road"].get("duration_min")) for route in road_routes]
            distances = [distance for distance in distances if distance is not None]
            durations = [duration for duration in durations if duration is not None]
            min_distance = min(distances) if distances else None
            max_distance = max(distances) if distances else None
            min_duration = min(durations) if durations else None
            max_duration = max(durations) if durations else None
            road_source = None
            if road_routes:
                road_source = (road_routes[0].get("road") or {}).get("source")
            facts = {
                "location": location,
                "commodity": commodity,
                "route_count": len(routes),
                "with_road_count": len(road_routes),
                "without_road_count": len(routes) - len(road_routes),
                "min_distance_km": min_distance,
                "max_distance_km": max_distance,
                "min_duration_min": min_duration,
                "max_duration_min": max_duration,
                "road_source": road_source,
            }
            citations = [
                self._citation("route_count", routes_path, "routes (count)", len(routes)),
                self._citation("with_road_count", routes_path, "routes[].road (count)", len(road_routes)),
                self._citation(
                    "without_road_count",
                    routes_path,
                    "routes[].road (count)",
                    len(routes) - len(road_routes),
                ),
            ]
            if min_distance is not None:
                citations.append(
                    self._citation(
                        "min_distance_km",
                        routes_path,
                        "routes[].road.distance_km (min)",
                        min_distance,
                    )
                )
            if max_distance is not None:
                citations.append(
                    self._citation(
                        "max_distance_km",
                        routes_path,
                        "routes[].road.distance_km (max)",
                        max_distance,
                    )
                )
            if min_duration is not None:
                citations.append(
                    self._citation(
                        "min_duration_min",
                        routes_path,
                        "routes[].road.duration_min (min)",
                        min_duration,
                    )
                )
            if max_duration is not None:
                citations.append(
                    self._citation(
                        "max_duration_min",
                        routes_path,
                        "routes[].road.duration_min (max)",
                        max_duration,
                    )
                )
            summary = (
                f"{len(routes)} rute aktif; {len(road_routes)} punya geometri jalan; "
                f"jarak {min_distance if min_distance is not None else 'tidak tersedia'}–"
                f"{max_distance if max_distance is not None else 'tidak tersedia'} km."
            )
            if not road_routes:
                return self._degraded(
                    summary,
                    facts=facts,
                    citations=citations,
                    warnings=warnings,
                    blocking=False,
                    latency_ms=self._latency_ms(started),
                )
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=False,
                latency_ms=self._latency_ms(started),
            )

        # Tidak ada kiriman aktif untuk tujuan ini. Estimasi hanya bila sumber
        # dan kuantitas diberikan oleh orkestrator/decision; endpoint estimasi
        # adalah komputasi murni, bukan tulis.
        warnings.append("tidak ada rute aktif untuk lokasi/komoditas ini")
        if context.source_location and context.quantity_kg and context.quantity_kg > 0:
            try:
                estimate = api.post_compute(
                    "/logistics/estimate",
                    {
                        "source": context.source_location,
                        "target": location,
                        "quantity_kg": context.quantity_kg,
                    },
                )
            except AgentApiError as exc:
                warnings.append(f"estimasi logistik gagal: {exc}")
                return self._degraded(
                    "Tidak ada rute aktif; estimasi jarak/waktu tidak tersedia.",
                    facts={
                        "location": location,
                        "commodity": commodity,
                        "route_count": 0,
                        "with_road_count": 0,
                        "without_road_count": 0,
                        "min_distance_km": None,
                        "max_distance_km": None,
                        "min_duration_min": None,
                        "max_duration_min": None,
                        "road_source": None,
                    },
                    citations=[
                        self._citation("route_count", routes_path, "routes (count)", 0),
                        self._citation("with_road_count", routes_path, "routes[].road (count)", 0),
                        self._citation("without_road_count", routes_path, "routes[].road (count)", 0),
                    ],
                    warnings=warnings,
                    blocking=False,
                    latency_ms=self._latency_ms(started),
                )

            distance_km = as_number(estimate.get("distance_km"))
            estimated_time_min = as_number(estimate.get("estimated_time_min"))
            feasible = estimate.get("feasible") if isinstance(estimate.get("feasible"), bool) else None
            facts = {
                "location": location,
                "commodity": commodity,
                "route_count": 0,
                "with_road_count": 0,
                "without_road_count": 0,
                "distance_km": distance_km,
                "estimated_time_min": estimated_time_min,
                "feasible": feasible,
                "source_location": context.source_location,
                "estimate_source": "/logistics/estimate",
            }
            citations = [
                self._citation("route_count", routes_path, "routes (count)", 0),
                self._citation("with_road_count", routes_path, "routes[].road (count)", 0),
                self._citation("without_road_count", routes_path, "routes[].road (count)", 0),
            ]
            if distance_km is not None:
                citations.append(
                    self._citation("distance_km", "/logistics/estimate", "distance_km", distance_km)
                )
            if estimated_time_min is not None:
                citations.append(
                    self._citation(
                        "estimated_time_min",
                        "/logistics/estimate",
                        "estimated_time_min",
                        estimated_time_min,
                    )
                )
            summary = (
                f"0 rute aktif; estimasi {context.source_location}→{location}: "
                f"{distance_km if distance_km is not None else 'tidak tersedia'} km, "
                f"{estimated_time_min if estimated_time_min is not None else 'tidak tersedia'} menit."
            )
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=False,
                latency_ms=self._latency_ms(started),
            )

        warnings.append("sumber/kuantitas tidak tersedia; estimasi tidak dibuat")
        return self._degraded(
            "Tidak ada rute aktif dan estimasi tidak dapat dibuat tanpa sumber/kuantitas.",
            facts={
                "location": location,
                "commodity": commodity,
                "route_count": 0,
                "with_road_count": 0,
                "without_road_count": 0,
                "min_distance_km": None,
                "max_distance_km": None,
                "min_duration_min": None,
                "max_duration_min": None,
                "road_source": None,
            },
            citations=[
                self._citation("route_count", routes_path, "routes (count)", 0),
                self._citation("with_road_count", routes_path, "routes[].road (count)", 0),
                self._citation("without_road_count", routes_path, "routes[].road (count)", 0),
            ],
            warnings=warnings,
            blocking=False,
            latency_ms=self._latency_ms(started),
        )

