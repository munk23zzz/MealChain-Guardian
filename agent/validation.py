"""Validasi lintas-worker untuk review tujuh agent.

Modul ini tidak memanggil API dan tidak menghitung ulang angka. Ia hanya
memeriksa kelengkapan worker, mendeteksi fakta yang saling bertentangan, dan
menentukan status run secara jujur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import AgentFinding, AgentName, Contradiction, RunStatus, WorkerStatus

ANALYST_AGENTS = frozenset(
    name for name in AgentName if name is not AgentName.VERIFIER
)
GUARDIANS = frozenset({AgentName.SAFETY, AgentName.FRESHNESS, AgentName.EVIDENCE})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    agents: tuple[AgentName, ...] = ()


def validate_findings(findings: list[AgentFinding]) -> list[ValidationIssue]:
    """Periksa kelengkapan dan duplikasi; schema/citation sudah dijaga kontrak."""
    issues: list[ValidationIssue] = []
    if len(findings) != len(ANALYST_AGENTS):
        issues.append(
            ValidationIssue(
                code="worker_count",
                message=(
                    f"review harus berisi {len(ANALYST_AGENTS)} worker analitik, "
                    f"dapat {len(findings)}"
                ),
            )
        )
    names = [finding.agent for finding in findings]
    duplicated = sorted({name.value for name in names if names.count(name) > 1})
    if duplicated:
        issues.append(
            ValidationIssue(
                code="duplicate_worker",
                message=f"worker ganda: {', '.join(duplicated)}",
            )
        )
    missing = sorted(ANALYST_AGENTS - set(names), key=lambda name: name.value)
    if missing:
        issues.append(
            ValidationIssue(
                code="missing_worker",
                message=f"worker belum ada: {', '.join(name.value for name in missing)}",
                agents=tuple(missing),
            )
        )
    return issues


def _shared_values(
    findings: list[AgentFinding], field: str
) -> list[tuple[AgentName, Any]]:
    values: list[tuple[AgentName, Any]] = []
    for finding in findings:
        value = finding.facts.get(field)
        if value is not None and not (isinstance(value, str) and not value.strip()):
            values.append((finding.agent, value))
    return values


def _contradiction(
    field: str, values: list[tuple[AgentName, Any]], label: str
) -> Contradiction:
    distinct = {repr(value) for _, value in values}
    return Contradiction(
        field=field,
        agents=[agent for agent, _ in values],
        values=[value for _, value in values],
        message=(
            f"{label} berbeda antar-worker: "
            + ", ".join(f"{agent.value}={value!r}" for agent, value in values)
            if len(distinct) > 1
            else f"{label} sama"
        ),
    )


def detect_contradictions(findings: list[AgentFinding]) -> list[Contradiction]:
    """Deteksi fakta yang saling bertentangan; nilai tidak diubah."""
    contradictions: list[Contradiction] = []
    by_agent = {finding.agent: finding for finding in findings}

    for field, label in (("location", "lokasi"), ("commodity", "komoditas")):
        values = _shared_values(findings, field)
        if len({repr(value) for _, value in values}) > 1:
            contradictions.append(_contradiction(field, values, label))

    safety = by_agent.get(AgentName.SAFETY)
    freshness = by_agent.get(AgentName.FRESHNESS)
    if safety and freshness:
        values = []
        for finding in (safety, freshness):
            value = finding.facts.get("batch_count")
            if isinstance(value, int) and not isinstance(value, bool):
                values.append((finding.agent, value))
        if len({repr(value) for _, value in values}) > 1:
            contradictions.append(_contradiction("batch_count", values, "jumlah batch"))

    price = by_agent.get(AgentName.PRICE)
    evidence = by_agent.get(AgentName.EVIDENCE)
    if price and evidence:
        for field, label in (
            ("decision_valid", "validitas keputusan"),
            ("can_execute", "status dapat dieksekusi"),
        ):
            values = []
            for finding in (price, evidence):
                value = finding.facts.get(field)
                if isinstance(value, bool):
                    values.append((finding.agent, value))
            if len({repr(value) for _, value in values}) > 1:
                contradictions.append(_contradiction(field, values, label))

        for price_field, evidence_field, label in (
            ("quantity_kg", "decision_quantity_kg", "kuantitas keputusan"),
            (
                "safe_delivered_cost",
                "decision_safe_delivered_cost",
                "safe delivered cost",
            ),
        ):
            left = price.facts.get(price_field)
            right = evidence.facts.get(evidence_field)
            if (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and isinstance(right, (int, float))
                and not isinstance(right, bool)
                and abs(float(left) - float(right)) > 1e-6
            ):
                contradictions.append(
                    _contradiction(
                        price_field,
                        [(price.agent, left), (evidence.agent, right)],
                        label,
                    )
                )

    return contradictions


def run_status(
    findings: list[AgentFinding], contradictions: list[Contradiction] | None = None
) -> RunStatus:
    """Status jujur untuk satu putaran review."""
    if not findings or validate_findings(findings):
        return RunStatus.FAILED
    if any(finding.status is WorkerStatus.ERROR for finding in findings):
        return RunStatus.PARTIAL
    if contradictions or any(
        finding.status in {WorkerStatus.DEGRADED, WorkerStatus.SKIPPED}
        for finding in findings
    ):
        return RunStatus.PARTIAL
    return RunStatus.COMPLETED


def safety_veto(findings: list[AgentFinding]) -> bool:
    return any(
        finding.blocking and finding.agent in GUARDIANS for finding in findings
    )
