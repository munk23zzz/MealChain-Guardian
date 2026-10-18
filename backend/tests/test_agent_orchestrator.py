"""P4 — orkestrasi 7 worker: lane, trace 8 baris, veto, timeout."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from agent.contracts import AgentFinding, AgentName, WorkerStatus
from agent.orchestrator import context_from_approval, run_review
from agent.registry import get_spec
from agent.telemetry import build_trace_rows
from agent.workers.base import WorkerContext


class FixedWorker:
    """Worker palsu deterministik; tidak memanggil API/model."""

    def __init__(
        self,
        name: AgentName,
        *,
        status: WorkerStatus = WorkerStatus.OK,
        blocking: bool = False,
        delay: float = 0.0,
    ) -> None:
        self.name = name
        self.status = status
        self.blocking = blocking
        self.delay = delay

    def run(self, context: WorkerContext) -> AgentFinding:
        if self.delay:
            time.sleep(self.delay)
        return AgentFinding(
            agent=self.name,
            stage=get_spec(self.name).stage,
            status=self.status,
            summary=f"{self.name.value} selesai",
            facts={},
            citations=[],
            blocking=self.blocking,
        )


def _workers(**overrides) -> dict[AgentName, FixedWorker]:
    workers: dict[AgentName, FixedWorker] = {}
    for name in AgentName:
        workers[name] = overrides.get(name, FixedWorker(name))
    return workers


def _context() -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location="Jakarta",
        commodity="telur",
        api=object(),
    )


class SummaryApi:
    def __init__(self, summary: dict) -> None:
        self.summary = summary
        self.paths: list[str] = []

    def get(self, path: str) -> dict:
        self.paths.append(path)
        return self.summary


def test_review_tujuh_worker_dan_delapan_trace() -> None:
    run = run_review("decision-1", context=_context(), workers=_workers())

    assert len(run.findings) == 7
    assert {finding.agent for finding in run.findings} == set(AgentName)
    assert run.status == "completed"
    assert run.safety_veto is False
    rows = build_trace_rows(run)
    assert len(rows) == 8
    assert [row["agent_name"] for row in rows][:7] == [
        name.value for name in AgentName
    ]
    assert rows[-1]["step_name"] == "SUPERVISE"
    assert rows[-1]["agent_name"] == "supervisor"


def test_dua_run_id_berbeda() -> None:
    first = run_review("decision-1", context=_context(), workers=_workers())
    second = run_review("decision-1", context=_context(), workers=_workers())

    assert first.run_id != second.run_id


def test_safety_veto_narrative_jangan_eksekusi() -> None:
    run = run_review(
        "decision-1",
        context=_context(),
        workers=_workers(
            **{AgentName.SAFETY: FixedWorker(AgentName.SAFETY, blocking=True)}
        ),
    )

    assert run.safety_veto is True
    assert "jangan eksekusi" in (run.narrative or "").lower()


def test_worker_error_menjadi_partial() -> None:
    run = run_review(
        "decision-1",
        context=_context(),
        workers=_workers(
            **{
                AgentName.PRICE: FixedWorker(
                    AgentName.PRICE, status=WorkerStatus.ERROR
                )
            }
        ),
    )

    assert run.status == "partial"
    price = next(f for f in run.findings if f.agent is AgentName.PRICE)
    assert price.status is WorkerStatus.ERROR


def test_context_diambil_dari_approval_summary() -> None:
    summary = {
        "target_location": "Jakarta",
        "source_location": "Cianjur",
        "commodity": "telur",
        "quantity_kg": 600.0,
    }
    api = SummaryApi(summary)
    captured: dict = {}

    class CaptureWorker(FixedWorker):
        def run(self, context: WorkerContext) -> AgentFinding:
            captured.update(
                location=context.location,
                commodity=context.commodity,
                source_location=context.source_location,
                quantity_kg=context.quantity_kg,
            )
            return super().run(context)

    workers = {name: CaptureWorker(name) for name in AgentName}
    run = run_review("decision-9", api=api, workers=workers)

    assert api.paths == ["/decisions/decision-9/approval-summary"]
    assert captured == {
        "location": "Jakarta",
        "commodity": "telur",
        "source_location": "Cianjur",
        "quantity_kg": 600.0,
    }
    assert run.decision_id == "decision-9"


def test_context_wajib_punya_lokasi_dan_komoditas() -> None:
    with pytest.raises(ValueError, match="target_location"):
        context_from_approval("d1", {"commodity": "telur"})


def test_timeout_tidak_mengarang_sukses() -> None:
    workers = {name: FixedWorker(name, delay=0.2) for name in AgentName}
    run = run_review(
        "decision-1",
        context=_context(),
        workers=workers,
        timeout_seconds=0.01,
        retry_errors=False,
    )

    assert run.status == "timeout"
    assert len(run.findings) == 7
    assert all(finding.status is WorkerStatus.ERROR for finding in run.findings)
    assert run.safety_veto is False
