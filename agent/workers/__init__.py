"""Kumpulan tujuh worker; P1 hanya stub, belum ada model/API."""

from __future__ import annotations

from uuid import UUID

from ..contracts import AgentFinding, AgentName
from .base import StubWorker, WorkerContext
from .demand import DemandWorker
from .evidence import EvidenceWorker
from .freshness import FreshnessWorker
from .logistics import LogisticsWorker
from .price import PriceWorker
from .safety import SafetyWorker
from .supply import SupplyWorker

WORKER_CLASSES = (
    SupplyWorker,
    DemandWorker,
    FreshnessWorker,
    SafetyWorker,
    PriceWorker,
    LogisticsWorker,
    EvidenceWorker,
)

WORKERS: tuple[StubWorker, ...] = tuple(worker_class() for worker_class in WORKER_CLASSES)
STUB_WORKERS: tuple[StubWorker, ...] = tuple(StubWorker(name) for name in AgentName)


def build_workers() -> list[StubWorker]:
    return list(WORKERS)


def build_stub_findings(run_id: UUID, decision_id: str) -> list[AgentFinding]:
    """Stub P1 tetap tersedia untuk tes kontrak; tidak memanggil API."""
    context = WorkerContext(run_id=run_id, decision_id=decision_id)
    return [worker.run(context) for worker in STUB_WORKERS]


__all__ = [
    "WORKER_CLASSES",
    "WORKERS",
    "build_stub_findings",
    "build_workers",
]
