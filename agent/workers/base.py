"""Dasar worker agent dan stub P1.

Stub tidak memanggil model/API. Ia hanya menghasilkan `AgentFinding` yang
valid dengan status `skipped`, supaya orkestrasi dan UI bisa diuji sebelum
worker nyata diimplementasikan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ..contracts import AgentFinding, AgentName, WorkerStatus
from ..registry import AgentSpec, get_spec


@dataclass(frozen=True)
class WorkerContext:
    run_id: UUID
    decision_id: str
    location: str | None = None
    commodity: str | None = None
    api: Any = None


class StubWorker:
    name: AgentName

    def __init__(self) -> None:
        self.spec: AgentSpec = get_spec(self.name)

    def run(self, context: WorkerContext) -> AgentFinding:
        if not context.decision_id.strip():
            raise ValueError("decision_id wajib diisi")
        return AgentFinding(
            agent=self.name,
            stage=self.spec.stage,
            status=WorkerStatus.SKIPPED,
            summary=f"{self.spec.role} belum dijalankan pada P1 (stub).",
            facts={},
            citations=[],
            confidence=None,
            warnings=["Stub P1: belum ada pembacaan API atau panggilan model."],
            blocking=False,
            latency_ms=None,
        )
