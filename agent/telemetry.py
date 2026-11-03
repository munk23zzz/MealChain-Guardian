"""Telemetry review — sembilan baris trace dari satu `AgentRun`.

Tujuh baris worker analitik + satu baris verifier + satu baris ringkasan
supervisor. Modul ini hanya membentuk payload; persist ke `agent_traces` tetap
urusan backend (P5).
"""

from __future__ import annotations

from .contracts import AgentRun


def build_trace_rows(run: AgentRun) -> list[dict]:
    """Bentuk 9 baris trace; angka tetap dari finding, bukan dihitung ulang."""
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

    # Agent verifier (ke-8) tampil sebagai baris sendiri SEBELUM ringkasan
    # supervisor: ia mengaudit hasilnya, jadi urutan baca yang wajar adalah
    # temuan analitik → audit → ringkasan.
    audit = run.verifier_finding
    if audit is not None:
        # Run anak (AUD-9A-03): baris VERIFY punya identitas run sendiri dan
        # menunjuk run review yang diauditnya lewat `parent_run_id`. Dengan
        # begitu jejak audit bisa direkonstruksi dari DB tanpa menebak.
        verifier_run_id = str(run.verifier_run_id or run.run_id)
        # `parent_run_id` hanya diisi bila run verifier punya identitas SENDIRI;
        # tanpa itu baris ini adalah baris biasa dari run induk (runtime lama),
        # bukan run anak — jangan menulis induk yang sama dengan run_id.
        parent_run_id = str(run.run_id) if run.verifier_run_id else None
        rows.append(
            {
                "run_id": verifier_run_id,
                "parent_run_id": parent_run_id,
                "decision_id": run.decision_id,
                "step_name": "VERIFY",
                "agent_name": audit.agent.value,
                "tool_called": f"agent.{audit.agent.value}",
                "status": audit.status.value,
                "summary": audit.summary,
                "duration_ms": audit.latency_ms,
                "confidence": audit.confidence,
                "citations": [c.model_dump() for c in audit.citations],
                "input_summary": {
                    "run_id": verifier_run_id,
                    "parent_run_id": parent_run_id,
                    "agent": audit.agent.value,
                    "dasar": "agent/verify.py + /decisions/{id}/audit-facts",
                    "fakta_sumber": audit.facts.get("fakta_sumber", []),
                },
                "output_summary": {
                    "status": audit.status.value,
                    "blocking": audit.blocking,
                    "summary": audit.summary,
                    "warning_count": len(audit.warnings),
                    "warnings": audit.warnings,
                    "citation_count": len(audit.citations),
                    # Verdict audit + cek + sitasi id disimpan supaya putaran
                    # ini bisa direkonstruksi dari `agent_traces` saja.
                    "audit_verdict": audit.facts.get("audit_verdict"),
                    "verdict_gerbang": audit.facts.get("verdict"),
                    "checks": audit.facts.get("checks", []),
                    "checks_total": audit.facts.get("checks_total"),
                    "checks_failed": audit.facts.get("checks_failed"),
                    "citations": audit.facts.get("citations", []),
                    "catatan": audit.facts.get("catatan"),
                    "model_verdict": audit.facts.get("model_verdict"),
                    "facts": {
                        kunci: nilai
                        for kunci, nilai in audit.facts.items()
                        if kunci
                        not in {
                            "checks",
                            "model_checks",
                            "reasons",
                            "citations",
                        }
                    },
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
            # Durasi baris SUPERVISE = durasi narasi itu sendiri bila model
            # dipanggil; `run.total_latency_ms` (seluruh review) dipakai hanya
            # bila tidak ada catatan lineage. Dulu barisnya selalu memakai
            # total, sehingga 20 detik "supervisor" sebenarnya waktu tujuh
            # worker — bukan panggilan model.
            "duration_ms": (
                run.narration.get("latency_ms")
                if isinstance(run.narration, dict)
                and run.narration.get("source") == "model"
                else run.total_latency_ms
            ),
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
                # Asal narasi + provider + latensi: bukti bahwa agent ke-9
                # benar-benar memanggil model, atau jujur menyatakan template.
                "narration": run.narration,
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
