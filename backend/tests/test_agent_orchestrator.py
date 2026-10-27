"""P4 — orkestrasi 7 worker: lane, trace 8 baris, veto, timeout."""

from __future__ import annotations  # noqa: I001

import time
from uuid import uuid4

import pytest
# `agent/` adalah runtime TERPISAH di akar repo (image sendiri). Tanpa mount
# ./agent:/agent (lihat docker-compose.yml), impor di bawah gagal dan pytest
# berhenti "Interrupted: 1 error during collection" (audit DEP-04).
pytest.importorskip("agent")

from agent.contracts import ANALYST_AGENTS, AgentFinding, AgentName, WorkerStatus  # noqa: E402
from agent.orchestrator import context_from_approval, run_review  # noqa: E402
from agent.registry import get_spec  # noqa: E402
from agent.telemetry import build_trace_rows  # noqa: E402
from agent.workers.base import WorkerContext  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402


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
    """Worker palsu untuk tujuh analitik; auditor memakai VerifierWorker nyata.

    Verifier harus nyata karena temuannya diturunkan dari hasil verifikasi,
    bukan dari data palsu.
    """
    workers: dict[AgentName, FixedWorker] = {}
    for name in AgentName:
        if name is AgentName.VERIFIER:
            workers[name] = VerifierWorker()
        else:
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


def test_review_tujuh_worker_dan_sembilan_trace() -> None:
    run = run_review("decision-1", context=_context(), workers=_workers())

    assert len(run.findings) == 7
    assert {finding.agent for finding in run.findings} == set(ANALYST_AGENTS)
    assert run.status == "completed"
    assert run.safety_veto is False

    # Agent ke-8: auditor. Temuannya terpisah dari findings supaya status dan
    # veto tetap milik tujuh worker analitik.
    assert run.verifier_finding is not None
    assert run.verifier_finding.agent is AgentName.VERIFIER
    assert run.verifier_finding.agent not in {f.agent for f in run.findings}

    rows = build_trace_rows(run)
    assert len(rows) == 9
    assert [row["agent_name"] for row in rows][:7] == [
        "supply", "demand", "freshness", "safety", "price", "logistics",
        "evidence",
    ]
    assert rows[7]["agent_name"] == "verifier"
    assert rows[7]["step_name"] == "VERIFY"
    assert rows[7]["tool_called"] == "agent.verifier"
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

    # Tiga bacaan: (1) orkestrator mengambil context dari approval-summary,
    # (2) melengkapi `batch_ids` batch SUMBER dari fakta audit (27 Okt 2026:
    # approval-summary pengadaan tidak membawanya, sehingga guardian
    # fail-closed dan memveto setiap putaran), (3) verifier (agent ke-8)
    # mengambil FAKTA-nya sendiri sesudah narasi. Urutan ini mengunci bahwa
    # verifier tidak menerima narasi sebagai sumber data.
    assert api.paths == [
        "/decisions/decision-9/approval-summary",
        "/decisions/decision-9/audit-facts",
        "/decisions/decision-9/audit-facts",
    ]
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
