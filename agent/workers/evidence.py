"""Evidence Fusion Agent — dossier, chain, compliance, dan ledger read-only."""

from __future__ import annotations

from time import monotonic
from urllib.parse import quote

from ..api_client import AgentApiError
from ..contracts import AgentFinding, AgentName
from .base import ReadOnlyWorker, WorkerContext, as_number


class EvidenceWorker(ReadOnlyWorker):
    name = AgentName.EVIDENCE

    def _run_deterministik(self, context: WorkerContext) -> AgentFinding:
        started = monotonic()
        try:
            api = self._api(context)
        except AgentApiError as exc:
            return self._error(str(exc), latency_ms=self._latency_ms(started))
        if not context.decision_id.strip():
            return self._error("decision_id wajib diisi untuk Evidence Agent", latency_ms=self._latency_ms(started))

        did = quote(context.decision_id, safe="")
        dossier_path = f"/decisions/{did}/dossier"
        compliance_path = f"/decisions/{did}/compliance"
        chain_path = f"/decisions/{did}/chain"
        summary_path = f"/decisions/{did}/approval-summary"
        warnings: list[str] = []

        try:
            dossier = api.get(dossier_path)
        except AgentApiError as exc:
            return self._error(f"dossier tidak terbaca: {exc}", latency_ms=self._latency_ms(started))

        try:
            compliance = api.get(compliance_path)
        except AgentApiError as exc:
            return self._error(f"compliance tidak terbaca: {exc}", latency_ms=self._latency_ms(started))

        chain = None
        try:
            chain_payload = api.get(chain_path)
            raw_chain = chain_payload.get("chain")
            chain = raw_chain if isinstance(raw_chain, list) else None
            if chain is None:
                warnings.append("respons chain tidak memuat daftar chain")
        except AgentApiError as exc:
            warnings.append(f"chain tidak terbaca: {exc}")

        approval = None
        try:
            approval = api.get(summary_path)
        except AgentApiError as exc:
            warnings.append(f"approval-summary tidak terbaca: {exc}")

        ledger = None
        try:
            ledger = api.get("/ledger/verify")
        except AgentApiError as exc:
            warnings.append(f"ledger tidak terbaca: {exc}")

        raw_evidence = compliance.get("evidence")
        evidence = raw_evidence if isinstance(raw_evidence, list) else []
        evidence_complete = isinstance(raw_evidence, list)
        if not evidence_complete:
            warnings.append("compliance tidak memuat daftar evidence")
        raw_approvals = compliance.get("approvals")
        approvals = raw_approvals if isinstance(raw_approvals, list) else []
        approvals_complete = isinstance(raw_approvals, list)
        if not approvals_complete:
            warnings.append("compliance tidak memuat daftar approvals")
        raw_traces = compliance.get("traces")
        traces = raw_traces if isinstance(raw_traces, list) else []
        traces_complete = isinstance(raw_traces, list)
        if not traces_complete:
            warnings.append("compliance tidak memuat daftar traces")

        raw_decision = compliance.get("decision")
        decision = raw_decision if isinstance(raw_decision, dict) else {}
        decision_status = decision.get("status")
        decision_quantity = as_number(
            decision.get("quantity_kg"), allow_numeric_string=True
        )
        decision_sdc = as_number(
            decision.get("safe_delivered_cost"), allow_numeric_string=True
        )
        signature = compliance.get("signature") if isinstance(compliance.get("signature"), dict) else {}
        signature_state = signature.get("state") if isinstance(signature.get("state"), str) else None
        raw_verify = compliance.get("verify")
        signature_verified = raw_verify if isinstance(raw_verify, bool) else None
        inconsistent = sum(
            1
            for item in evidence
            if isinstance(item, dict) and item.get("is_consistent") is False
        )
        ledger_valid = ledger.get("valid") if ledger and isinstance(ledger.get("valid"), bool) else None
        ledger_blocks = as_number(ledger.get("blocks")) if ledger else None

        approval_valid = None
        can_execute = None
        if approval:
            expiry = approval.get("expiry")
            if isinstance(expiry, dict) and isinstance(expiry.get("valid"), bool):
                approval_valid = expiry["valid"]
            raw_can_execute = approval.get("can_execute")
            can_execute = raw_can_execute if isinstance(raw_can_execute, bool) else None

        facts = {
            "decision_id": context.decision_id,
            "decision_status": decision_status,
            "decision_quantity_kg": decision_quantity,
            "decision_safe_delivered_cost": decision_sdc,
            "chain_length": len(chain) if chain is not None else None,
            "evidence_count": len(evidence),
            "approval_count": len(approvals),
            "trace_count": len(traces),
            "inconsistent_evidence_count": inconsistent,
            "evidence_types": [
                item.get("evidence_type")
                for item in evidence
                if isinstance(item, dict) and item.get("evidence_type") is not None
            ],
            "ledger_valid": ledger_valid,
            "ledger_blocks": ledger_blocks,
            "signature_state": signature_state,
            "signature_verified": signature_verified,
            "decision_valid": approval_valid,
            "can_execute": can_execute,
            "content_address": dossier.get("content_address"),
        }
        citations = [
            self._citation("evidence_count", compliance_path, "evidence (count)", len(evidence)),
            self._citation("approval_count", compliance_path, "approvals (count)", len(approvals)),
            self._citation("trace_count", compliance_path, "traces (count)", len(traces)),
            self._citation(
                "inconsistent_evidence_count",
                compliance_path,
                "evidence[].is_consistent (count)",
                inconsistent,
            ),
        ]
        if chain is not None:
            citations.append(
                self._citation("chain_length", chain_path, "chain (count)", len(chain))
            )
        if ledger_blocks is not None:
            citations.append(
                self._citation("ledger_blocks", "/ledger/verify", "blocks", ledger_blocks)
            )
        if decision_quantity is not None:
            citations.append(
                self._citation(
                    "decision_quantity_kg",
                    compliance_path,
                    "decision.quantity_kg",
                    decision_quantity,
                )
            )
        if decision_sdc is not None:
            citations.append(
                self._citation(
                    "decision_safe_delivered_cost",
                    compliance_path,
                    "decision.safe_delivered_cost",
                    decision_sdc,
                )
            )

        if inconsistent:
            warnings.append(f"{inconsistent} evidence ditandai tidak konsisten")
        if ledger_valid is False:
            warnings.append("ledger tidak valid")
        if signature_verified is False:
            warnings.append("tanda tangan dossier tidak valid")
        if ledger_valid is None:
            warnings.append("validitas ledger tidak tersedia")
        if approval_valid is False:
            warnings.append("keputusan kedaluwarsa; jangan menyarankan eksekusi")
        if can_execute is False:
            warnings.append("keputusan belum dapat dieksekusi menurut read model")

        blocking = bool(
            ledger_valid is False
            or inconsistent > 0
            or signature_verified is False
        )
        degraded = bool(
            chain is None
            or ledger_valid is None
            or signature_state is None
            or approval is None
            or not evidence_complete
            or not approvals_complete
            or not traces_complete
            or not isinstance(raw_decision, dict)
        )
        summary = (
            f"Keputusan {facts['decision_status'] or 'tidak diketahui'}; "
            f"evidence {len(evidence)}, approval {len(approvals)}, trace {len(traces)}, "
            f"chain {len(chain) if chain is not None else 'tidak tersedia'}; "
            f"ledger {'valid' if ledger_valid else 'tidak valid' if ledger_valid is False else 'tidak tersedia'}; "
            f"tanda tangan {signature_state or 'tidak tersedia'}."
        )
        if degraded:
            return self._degraded(
                summary,
                facts=facts,
                citations=citations,
                warnings=warnings,
                blocking=blocking,
                latency_ms=self._latency_ms(started),
            )
        return self._ok(
            summary,
            facts=facts,
            citations=citations,
            warnings=warnings,
            blocking=blocking,
            latency_ms=self._latency_ms(started),
        )

