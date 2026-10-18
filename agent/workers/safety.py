"""Safety Guardian — membaca batch dan exclusion; tidak memanggil /safety/evaluate."""

from __future__ import annotations

from time import monotonic

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext


class SafetyWorker(ReadOnlyWorker):
    name = AgentName.SAFETY

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        try:
            batches_payload = api.get("/batches")
        except AgentApiError as exc:
            latency = self._latency_ms(started)
            if exc.status_code == 404:
                return self._degraded(
                    "Daftar batch tidak tersedia; status keamanan tidak diketahui.",
                    facts={
                        "location": location,
                        "commodity": commodity,
                        "batch_count": None,
                        "failed_count": None,
                        "pending_count": None,
                        "pass_count": None,
                        "active_exclusion_count": None,
                        "worst_status": None,
                        "failed_batch_ids": [],
                        "active_exclusion_ids": [],
                    },
                    warnings=[f"api_404: {exc}"],
                    latency_ms=latency,
                )
            return self._error(str(exc), latency_ms=latency)

        batches = batches_payload.get("batches") if isinstance(batches_payload, dict) else None
        if not isinstance(batches, list):
            return self._error("respons /batches tidak memuat daftar 'batches'", latency_ms=self._latency_ms(started))

        selected = [
            batch
            for batch in batches
            if isinstance(batch, dict)
            and str(batch.get("location", "")).strip().lower() == location.lower()
            and str(batch.get("commodity", "")).strip().lower() == commodity.lower()
        ]

        counts = {"pass": 0, "pending": 0, "fail": 0}
        failed_ids: list[str] = []
        unknown = 0
        for batch in selected:
            status = str(batch.get("safety_status") or "").strip().lower()
            if status in counts:
                counts[status] += 1
            else:
                unknown += 1
            if status == "fail" and batch.get("id") is not None:
                failed_ids.append(str(batch["id"]))

        worst_status = (
            "fail" if counts["fail"] else "pending" if counts["pending"] else "pass" if counts["pass"] else None
        )

        active_ids: list[str] = []
        exclusions_ok = False
        warnings: list[str] = []
        try:
            exclusions_payload = api.get("/supplier-exclusions")
            items = exclusions_payload.get("items") if isinstance(exclusions_payload, dict) else None
            if not isinstance(items, list):
                raise AgentApiError("respons /supplier-exclusions tidak memuat 'items'")
            active_ids = [
                str(item["id"])
                for item in items
                if isinstance(item, dict)
                and item.get("status") == "active"
                and item.get("id") is not None
            ]
            exclusions_ok = True
        except AgentApiError as exc:
            warnings.append(f"exclusion tidak terbaca: {exc}")

        latency = self._latency_ms(started)
        facts = {
            "location": location,
            "commodity": commodity,
            "batch_count": len(selected),
            "failed_count": counts["fail"],
            "pending_count": counts["pending"],
            "pass_count": counts["pass"],
            "active_exclusion_count": len(active_ids) if exclusions_ok else None,
            "worst_status": worst_status,
            "failed_batch_ids": failed_ids,
            "active_exclusion_ids": active_ids,
        }
        citations = [
            self._citation("batch_count", "/batches", "batches[].safety_status (count)", len(selected)),
            self._citation("failed_count", "/batches", "batches[].safety_status (count)", counts["fail"]),
            self._citation("pending_count", "/batches", "batches[].safety_status (count)", counts["pending"]),
            self._citation("pass_count", "/batches", "batches[].safety_status (count)", counts["pass"]),
        ]
        if exclusions_ok:
            citations.append(
                self._citation(
                    "active_exclusion_count",
                    "/supplier-exclusions",
                    "items[].status (count)",
                    len(active_ids),
                )
            )

        if not selected:
            warnings.append("tidak ada batch untuk lokasi/komoditas ini")
        if unknown:
            warnings.append(f"{unknown} batch memiliki safety_status tak dikenal")
        if not exclusions_ok:
            warnings.append("jumlah exclusion aktif tidak diketahui")

        blocking = counts["fail"] > 0 or (exclusions_ok and len(active_ids) > 0)
        summary = (
            f"{len(selected)} batch: {counts['pass']} pass, {counts['pending']} pending, "
            f"{counts['fail']} fail; exclusion aktif {len(active_ids) if exclusions_ok else 'tidak diketahui'}."
        )
        if exclusions_ok and selected:
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=blocking,
                latency_ms=latency,
            )
        return self._degraded(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=latency,
        )

