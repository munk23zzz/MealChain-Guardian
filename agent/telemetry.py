"""Telemetry review — delapan baris trace dari satu `AgentRun`.

Tujuh baris worker + satu baris ringkasan supervisor. Modul ini hanya
membentuk payload; persist ke `agent_traces` tetap urusan backend (P5).
"""

from __future__ import annotations

from .contracts import AgentRun


def build_trace_rows(run: AgentRun) -> list[dict]:
    """Bentuk 8 baris trace; angka tetap dari finding, bukan dihitung ulang."""
    rows: list[dict] = []
    for finding in run.findings:
        rows.append(
            {
                "run_id": str(run.run_id),
                "decision_id": run.decision_id,
                "step_name": finding.stage.value,
                "agent_name": finding.agent.value,
                "tool_called": f"agent.{finding.agent.value}",
                "status": finding.status.value,
                "summary": finding.summary,
                "duration_ms": finding.latency_ms,
                "confidence": finding.confidence,
                "citations": [citation.model_dump() for citation in finding.citations],
                "input_summary": {
                    "run_id": str(run.run_id),
                    "agent": finding.agent.value,
                },
                "output_summary": {
                    "status": finding.status.value,
                    "blocking": finding.blocking,
                    "summary": finding.summary,
                    "warning_count": len(finding.warnings),
                    "warnings": finding.warnings,
                    "citation_count": len(finding.citations),
                    "facts": finding.facts,
                },
            }
        )

    rows.append(
        {
            "run_id": str(run.run_id),
            "decision_id": run.decision_id,
            "step_name": "SUPERVISE",
            "agent_name": "supervisor",
            "tool_called": "agent.review_summary",
            "status": run.status.value,
            "summary": run.narrative,
            "duration_ms": run.total_latency_ms,
            "confidence": None,
            "citations": [],
            "input_summary": {
                "run_id": str(run.run_id),
                "decision_id": run.decision_id,
                "finding_count": len(run.findings),
            },
            "output_summary": {
                "status": run.status.value,
                "narrative": run.narrative,
                "safety_veto": run.safety_veto,
                "contradiction_count": len(run.contradictions),
                "contradictions": [
                    contradiction.model_dump() for contradiction in run.contradictions
                ],
                "verification": (
                    run.verification.model_dump() if run.verification is not None else None
                ),
            },
        }
    )
    return rows


__all__ = ["build_trace_rows"]
