"""Status run harus mencerminkan veto guardian; durasi audit tidak boleh 0.

Dua defek yang dikunci di sini (temuan C-09 `INDEPENDENT_PROJECT_REVIEW.md`):

1. `run.status` dilaporkan `completed` padahal ada guardian `blocking=True`.
   Supervisor menghitung status dari `run_status(findings, contradictions)` yang
   tidak melihat veto, sehingga verifier menandai
   `safety_veto_aktif ... status run dilaporkan completed` dan kartu bukti Demo
   Control menampilkan "Verifikasi: Terbatas" untuk putaran yang sebenarnya
   lengkap. Perbaikannya di PENGHITUNG status, bukan dengan melemahkan verifier.
2. Baris VERIFY hasil `_degraded` menyimpan `duration_ms = 0` karena latency
   sub-milidetik dipotong `int()`; UI lalu menampilkan "Durasi: 0 md" seolah
   tidak ada pekerjaan yang berjalan.
"""

from __future__ import annotations

import json
import time
import uuid
from uuid import uuid4

import pytest

# `agent/` adalah runtime TERPISAH di akar repo (image sendiri). Tanpa mount
# ./agent:/agent (lihat docker-compose.yml), impor di bawah gagal dan pytest
# berhenti "Interrupted: 1 error during collection" (audit DEP-04).
pytest.importorskip("agent")

from agent.contracts import (  # noqa: E402
    ANALYST_AGENTS,
    AgentFinding,
    AgentName,
    AgentRun,
    RunStatus,
    VerifyResult,
    WorkerStatus,
)
from agent.orchestrator import run_review  # noqa: E402
from agent.registry import get_spec  # noqa: E402
from agent.telemetry import build_trace_rows  # noqa: E402
from agent.validation import run_status, safety_veto  # noqa: E402
from agent.verify import verify_run  # noqa: E402
from agent.workers.base import StubWorker, WorkerContext  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402

ALASAN_LAMA = "status run dilaporkan completed"


class FixedWorker:
    """Worker palsu deterministik; tidak memanggil API/model."""

    def __init__(
        self,
        name: AgentName,
        *,
        status: WorkerStatus = WorkerStatus.OK,
        blocking: bool = False,
    ) -> None:
        self.name = name
        self.status = status
        self.blocking = blocking

    def run(self, context: WorkerContext) -> AgentFinding:  # noqa: ARG002
        return _finding(self.name, status=self.status, blocking=self.blocking)


def _finding(
    agent: AgentName,
    *,
    status: WorkerStatus = WorkerStatus.OK,
    blocking: bool = False,
) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        stage=get_spec(agent).stage,
        status=status,
        summary=f"{agent.value} finding",
        facts={},
        citations=[],
        blocking=blocking,
    )


def _veto_findings() -> list[AgentFinding]:
    """Tujuh temuan dengan SAFETY memblokir sedangkan status worker tetap ok.

    Ini bentuk nyata di jejak demo: guardian `ok` tetapi `blocking=True`
    (exclusion/batch aktif) — bukan worker error.
    """
    findings = [_finding(name) for name in sorted(ANALYST_AGENTS, key=lambda n: n.value)]
    index = next(i for i, f in enumerate(findings) if f.agent is AgentName.SAFETY)
    findings[index] = _finding(AgentName.SAFETY, blocking=True)
    return findings


def _workers(**overrides: FixedWorker) -> dict[AgentName, FixedWorker]:
    workers: dict[AgentName, FixedWorker] = {}
    for name in AgentName:
        if name is AgentName.VERIFIER:
            # Auditor nyata: temuannya diturunkan dari hasil verifikasi.
            workers[name] = VerifierWorker()
        else:
            workers[name] = overrides.get(name, FixedWorker(name))
    return workers


def _context() -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-veto",
        location="Jakarta",
        commodity="telur",
        api=object(),
    )


def _run(*, status: RunStatus, findings: list[AgentFinding], narrative: str) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        decision_id="decision-veto",
        mode="advisory",
        status=status,
        findings=findings,
        narrative=narrative,
        safety_veto=safety_veto(findings),
    )


# ---------------------------------------------------------------- status run
def test_run_status_vetoed_saat_guardian_blocking() -> None:
    """Veto guardian bukan "selesai": status runnya sendiri harus berubah."""
    findings = _veto_findings()

    assert safety_veto(findings) is True
    assert run_status(findings) is RunStatus.VETOED


def test_run_review_dengan_veto_tidak_dilaporkan_completed() -> None:
    run = run_review(
        "decision-veto",
        context=_context(),
        workers=_workers(
            **{AgentName.SAFETY: FixedWorker(AgentName.SAFETY, blocking=True)}
        ),
    )

    assert run.safety_veto is True
    assert run.status is RunStatus.VETOED
    assert run.status is not RunStatus.COMPLETED
    # Jejak yang dibaca UI (baris SUPERVISE) memakai status yang sama.
    supervise = build_trace_rows(run)[-1]
    assert supervise["step_name"] == "SUPERVISE"
    assert supervise["status"] == "vetoed"
    assert supervise["output_summary"]["status"] == "vetoed"
    # Narasi tetap melarang eksekusi (tidak dilunakkan oleh perbaikan status).
    assert "jangan eksekusi" in (run.narrative or "").lower()


def test_verifier_tidak_menuduh_status_completed_untuk_run_benar() -> None:
    """Verifier tidak boleh lagi melihat veto + status completed."""
    run = run_review(
        "decision-veto",
        context=_context(),
        workers=_workers(
            **{AgentName.SAFETY: FixedWorker(AgentName.SAFETY, blocking=True)}
        ),
    )

    alasan_gerbang = list(run.verification.reasons) if run.verification else []
    assert run.verification is not None
    assert run.verification.verdict == "pass", alasan_gerbang
    assert not any(ALASAN_LAMA in alasan for alasan in alasan_gerbang), alasan_gerbang

    assert run.verifier_finding is not None
    facts = run.verifier_finding.facts
    assert facts["status_run"] == "vetoed"
    assert facts["safety_veto"] is True
    assert not any(ALASAN_LAMA in str(alasan) for alasan in facts["reasons"]), facts[
        "reasons"
    ]
    # Verdict gerbang deterministik tetap "pass" (bukan flag) → audit boleh
    # menyimpulkan tanpa mewarisi tanda.
    assert facts["verdict"] == "pass"


def test_narasi_veto_tidak_dituduh_menghaluskan_penurunan() -> None:
    """Narasi veto bukan narasi "semuanya aman" — jangan ditandai.

    Bentuk nyata (putaran demo 27 Okt): guardian SAFETY degraded + blocking,
    narasi supervisor berbunyi "guardian yang memblokir … JANGAN EKSEKUSI".
    Sebelumnya heuristik kata kunci hanya mengenal "degraded/sebagian/error",
    sehingga putaran ber-veto selalu mendapat flag `narasi_tidak_menyebut_penurunan`.
    """
    findings = [_finding(name) for name in sorted(ANALYST_AGENTS, key=lambda n: n.value)]
    index = next(i for i, f in enumerate(findings) if f.agent is AgentName.SAFETY)
    findings[index] = _finding(
        AgentName.SAFETY, status=WorkerStatus.DEGRADED, blocking=True
    )
    run = _run(
        status=RunStatus.VETOED,
        findings=findings,
        narrative=(
            "Review 7 agen menemukan guardian yang memblokir. JANGAN EKSEKUSI "
            "keputusan ini sebelum bukti diperbaiki; keputusan tetap advisory "
            "dan menunggu review manusia."
        ),
    )

    hasil = verify_run(run)

    assert hasil.verdict == "pass", hasil.reasons
    assert not any("narasi" in alasan for alasan in hasil.reasons), hasil.reasons


def test_guard_verifier_tetap_ada_untuk_status_yang_menyembunyikan_veto() -> None:
    """Cek tidak dihapus: run yang MENYEMBUNYIKAN veto tetap ditandai.

    Perbaikan ada di penghitung status; kecurigaan verifier dipertahankan
    supaya runtime lama/penulis lain tidak bisa melaporkan status palsu.
    """
    findings = _veto_findings()
    run = _run(
        status=RunStatus.PARTIAL,
        findings=findings,
        narrative="Review 7 agen selesai sebagian; keputusan menunggu review manusia.",
    )

    hasil = verify_run(run)

    assert hasil.verdict == "flag"
    assert any("safety_veto" in alasan for alasan in hasil.reasons), hasil.reasons


# ------------------------------------------------------------------- durasi
def test_latency_ms_kerja_terukur_tidak_pernah_nol() -> None:
    """0 ms hanya untuk "tidak diukur" (None), bukan untuk kerja sub-milidetik."""
    assert StubWorker._latency_ms(time.monotonic()) >= 1


def test_baris_verify_degraded_menyimpan_durasi_bukan_nol() -> None:
    """Baris VERIFY hasil `_degraded` harus membawa durasi > 0."""
    findings = [_finding(name) for name in sorted(ANALYST_AGENTS, key=lambda n: n.value)]
    run = _run(
        status=RunStatus.PARTIAL,
        findings=findings,
        narrative="Review 7 agen selesai sebagian; tidak semua temuan utuh.",
    )
    run = run.model_copy(
        update={"verification": VerifyResult(verdict="flag", reasons=["narasi_x"])}
    )

    temuan = VerifierWorker().audit(run)

    assert temuan.status is WorkerStatus.DEGRADED
    assert temuan.latency_ms is not None
    assert temuan.latency_ms > 0

    run = run.model_copy(update={"verifier_finding": temuan})
    # Tujuh worker punya stage VERIFY sendiri (freshness/safety); yang dimaksud
    # adalah baris auditor: agent_name == "verifier".
    baris = next(
        row
        for row in build_trace_rows(run)
        if row["step_name"] == "VERIFY" and row["agent_name"] == "verifier"
    )
    assert baris["duration_ms"] is not None
    assert baris["duration_ms"] > 0


# ------------------------------------------------------- klien review backend
def test_klien_review_menerima_status_vetoed() -> None:
    """Runtime yang menjawab `vetoed` bukan kegagalan: 9 baris trace tetap disimpan."""
    from app.services.agent_review_client import review_decision

    payload = {
        "run_id": str(uuid.uuid4()),
        "decision_id": "decision-veto",
        "mode": "advisory",
        "status": "vetoed",
        "findings": [{} for _ in range(7)],
        "contradictions": [],
        "safety_veto": True,
        "narrative": "Review 7 agen menemukan guardian yang memblokir.",
        "trace_rows": [],
    }

    result = review_decision(
        "decision-veto", caller=lambda prompt: json.dumps(payload)  # noqa: ARG005
    )

    assert result.status == "vetoed"
    assert result.payload is not None
    assert result.payload["status"] == "vetoed"
    assert result.completed is True
