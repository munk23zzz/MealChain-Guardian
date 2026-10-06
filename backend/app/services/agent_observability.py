"""AgentCore observability trace (S3-09) — jejak aktual, label sintetis.

TraceRecorder mengumpulkan event aktual (supervisor invocation, tool
call/result, model call, fallback hanya bila terjadi) dengan timestamp
ISO. Entri sintetis (test double) diberi label `synthetic: true` dan
MENGHALANGI promosi ke bukti produksi via `assert_production_ready()`.
Sink AgentCore Observability tanpa endpoint = error eksplisit.
"""

from __future__ import annotations

from datetime import datetime, timezone

_UTC = timezone.utc


class ObservabilityUnavailableError(RuntimeError):
    """Sink observability tidak dapat dipakai — eksplisit."""


def _now_iso() -> str:
    return datetime.now(_UTC).isoformat()


class TraceRecorder:
    """Kumpulkan event trace aktual dengan timestamp + decision context."""

    def __init__(self, decision_id: str, context: dict | None = None) -> None:
        self._decision_id = decision_id
        self._context = dict(context or {})
        self._events: list[dict] = []

    # -- event constructors ---------------------------------------------------

    def record_supervisor_invocation(self, *, model: str, **extra) -> dict:
        return self._add(
            "supervisor_invocation", {"model": model, **extra}
        )

    def record_tool_call(
        self,
        *,
        tool: str,
        request: dict,
        result: dict | None,
        synthetic: bool = False,
    ) -> dict:
        return self._add(
            "tool_call",
            {
                "tool": tool,
                "request": request,
                "result": result,
                "synthetic": bool(synthetic),
            },
        )

    def record_model_call(self, *, provider: str, outcome: str) -> dict:
        return self._add(
            "model_call", {"provider": provider, "outcome": outcome}
        )

    def record_fallback(self, *, from_provider: str, to_provider: str) -> dict:
        return self._add(
            "fallback",
            {"from_provider": from_provider, "to_provider": to_provider},
        )

    # -- access ---------------------------------------------------------------

    def events(self) -> list[dict]:
        return [dict(e) for e in self._events]

    def assert_production_ready(self) -> None:
        """Tolak promosi bukti produksi bila ada entri sintetis."""
        synthetic = [e for e in self._events if e.get("synthetic")]
        if synthetic:
            raise ObservabilityUnavailableError(
                f"trace memuat {len(synthetic)} entri synthetic — "
                "tidak boleh dipromosikan sebagai bukti produksi"
            )

    # -- internals ------------------------------------------------------------

    def _add(self, kind: str, payload: dict) -> dict:
        event = {
            "kind": kind,
            "decision_id": self._decision_id,
            "event_at": _now_iso(),
            "context": dict(self._context),
            # flag eksplisit di SEMUA event agar pemeriksaan promosi
            # bukti produksi seragam
            "synthetic": False,
            **payload,
        }
        self._events.append(event)
        return event


class LocalObservabilitySink:
    """Sink lokal: kirim event tercatat (untuk persist/pengiriman)."""

    provider = "local"

    def ship(self, recorder: TraceRecorder) -> list[dict]:
        return recorder.events()


class AgentCoreObservabilitySink:
    """Sink AgentCore Observability — butuh endpoint nyata."""

    provider = "agentcore"

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint

    def ship(self, recorder: TraceRecorder) -> list[dict]:
        raise ObservabilityUnavailableError(
            f"AgentCore Observability endpoint {self._endpoint!r} belum "
            "dapat dihubungi; tidak ada trace palsu sebagai gantinya"
        )


def create_observability_sink(provider: str | None = None, endpoint=None):
    """Factory sink: agentcore tanpa endpoint = error eksplisit."""
    if provider == "agentcore":
        if not endpoint:
            raise ObservabilityUnavailableError(
                "AgentCore Observability membutuhkan endpoint; endpoint "
                "kosong = observability tidak tersedia (eksplisit)"
            )
        return AgentCoreObservabilitySink(endpoint)
    return LocalObservabilitySink()
