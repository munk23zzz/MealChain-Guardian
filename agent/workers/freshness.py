"""Freshness Guardian — membaca batch; tidak memanggil endpoint tulis."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


def _usable_until(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


class FreshnessWorker(ReadOnlyWorker):
    name = AgentName.FRESHNESS

    def run(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            location, commodity = self._target(context)
            api = self._api(context)
        except (AgentApiError, ValueError) as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))

        try:
            payload = api.get("/batches")
        except AgentApiError as exc:
            latency = self._latency_ms(started)
            if exc.status_code == 404:
                return self._degraded(
                    "Daftar batch tidak tersedia; kesegaran tidak diketahui.",
                    facts={
                        "location": location,
                        "commodity": commodity,
                        "batch_count": None,
                        "expired_count": None,
                        "worst_freshness_score": None,
                        "expired_batch_ids": [],
                    },
                    warnings=[f"api_404: {exc}"],
                    latency_ms=latency,
                )
            return self._error(str(exc), latency_ms=latency)

        batches = payload.get("batches") if isinstance(payload, dict) else None
        if not isinstance(batches, list):
            return self._error("respons /batches tidak memuat daftar 'batches'", latency_ms=self._latency_ms(started))

        selected = [
            batch
            for batch in batches
            if isinstance(batch, dict)
            and str(batch.get("location", "")).strip().lower() == location.lower()
            and str(batch.get("commodity", "")).strip().lower() == commodity.lower()
        ]

        now = datetime.now(timezone.utc)
        scores: list[float] = []
        expired_ids: list[str] = []
        earliest: datetime | None = None
        unparsed = 0
        for batch in selected:
            score = as_number(batch.get("freshness_score"))
            if score is not None:
                scores.append(float(score))
            usable = _usable_until(batch.get("usable_until"))
            if usable is None:
                unparsed += 1
            else:
                if earliest is None or usable < earliest:
                    earliest = usable
                if usable <= now and batch.get("id") is not None:
                    expired_ids.append(str(batch["id"]))

        worst_score = min(scores) if scores else None
        facts = {
            "location": location,
            "commodity": commodity,
            "batch_count": len(selected),
            "expired_count": len(expired_ids),
            "worst_freshness_score": worst_score,
            "earliest_usable_until": earliest.isoformat() if earliest else None,
            "expired_batch_ids": expired_ids,
        }
        citations = [
            self._citation("batch_count", "/batches", "batches[].usable_until (count)", len(selected)),
            self._citation("expired_count", "/batches", "batches[].usable_until (count)", len(expired_ids)),
        ]
        if worst_score is not None:
            citations.append(
                self._citation(
                    "worst_freshness_score",
                    "/batches",
                    "batches[].freshness_score (min)",
                    worst_score,
                )
            )

        warnings: list[str] = []
        if not selected:
            warnings.append("tidak ada batch untuk lokasi/komoditas ini")
        if not scores:
            warnings.append("freshness_score tidak tersedia")
        if worst_score is not None and worst_score < 1.0:
            warnings.append(
                f"skor kesegaran terburuk {worst_score}; belum sempurna, jangan menyimpulkan aman"
            )
        if unparsed:
            warnings.append(f"{unparsed} batch tidak memiliki usable_until yang bisa dibaca")

        blocking = len(expired_ids) > 0
        summary = (
            f"{len(selected)} batch; {len(expired_ids)} kedaluwarsa; "
            f"skor kesegaran terburuk {worst_score if worst_score is not None else 'tidak tersedia'}."
        )
        if selected:
            return self._ok(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=blocking,
                latency_ms=self._latency_ms(started),
            )
        return self._degraded(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=self._latency_ms(started),
        )

