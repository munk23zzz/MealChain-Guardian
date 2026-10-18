"""Validasi lintas-worker: kelengkapan, kontradiksi, status run."""

from agent.contracts import AgentFinding, AgentName, Citation, Contradiction, WorkerStatus
from agent.registry import get_spec
from agent.validation import (
    detect_contradictions,
    run_status,
    safety_veto,
    validate_findings,
)


def _finding(
    agent: AgentName,
    *,
    status: WorkerStatus = WorkerStatus.OK,
    facts: dict | None = None,
    citations: list[Citation] | None = None,
    blocking: bool = False,
) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        stage=get_spec(agent).stage,
        status=status,
        summary=f"{agent.value} finding",
        facts=facts or {},
        citations=citations or [],
        blocking=blocking,
    )


def _all_findings(**overrides: AgentFinding) -> list[AgentFinding]:
    return [overrides.get(name.value, _finding(name)) for name in AgentName]


def test_validate_tujuh_worker_lengkap() -> None:
    assert validate_findings(_all_findings()) == []


def test_validate_duplikat_dan_hilang() -> None:
    findings = [_finding(AgentName.SUPPLY), _finding(AgentName.SUPPLY)] + [
        _finding(name) for name in list(AgentName)[2:]
    ]

    issues = validate_findings(findings)

    codes = {issue.code for issue in issues}
    assert "duplicate_worker" in codes
    assert "missing_worker" in codes


def test_validate_kurang_satu_worker() -> None:
    issues = validate_findings([_finding(AgentName.SUPPLY), _finding(AgentName.DEMAND)])

    codes = {issue.code for issue in issues}
    assert "worker_count" in codes
    assert "missing_worker" in codes


def test_kontradiksi_lokasi_antar_worker() -> None:
    findings = _all_findings(
        **{
            "supply": _finding(AgentName.SUPPLY, facts={"location": "Jakarta"}),
            "demand": _finding(AgentName.DEMAND, facts={"location": "Bandung"}),
        }
    )

    contradictions = detect_contradictions(findings)

    assert len(contradictions) == 1
    assert contradictions[0].field == "location"
    assert set(contradictions[0].agents) == {AgentName.SUPPLY, AgentName.DEMAND}
    assert "Jakarta" in contradictions[0].message
    assert "Bandung" in contradictions[0].message


def test_kontradiksi_jumlah_batch_safety_freshness() -> None:
    findings = _all_findings(
        **{
            "safety": _finding(
                AgentName.SAFETY,
                facts={"batch_count": 3},
                citations=[
                    Citation(
                        claim="batch_count",
                        source_path="/batches",
                        source_field="batches (count)",
                        source_value=3,
                    )
                ],
            ),
            "freshness": _finding(
                AgentName.FRESHNESS,
                facts={"batch_count": 2},
                citations=[
                    Citation(
                        claim="batch_count",
                        source_path="/batches",
                        source_field="batches (count)",
                        source_value=2,
                    )
                ],
            ),
        }
    )

    contradictions = detect_contradictions(findings)

    assert len(contradictions) == 1
    assert contradictions[0].field == "batch_count"


def test_kontradiksi_status_eksekusi_price_evidence() -> None:
    findings = _all_findings(
        **{
            "price": _finding(AgentName.PRICE, facts={"can_execute": True}),
            "evidence": _finding(AgentName.EVIDENCE, facts={"can_execute": False}),
        }
    )

    contradictions = detect_contradictions(findings)

    assert len(contradictions) == 1
    assert contradictions[0].field == "can_execute"


def test_kontradiksi_angka_price_evidence() -> None:
    findings = _all_findings(
        **{
            "price": _finding(
                AgentName.PRICE,
                facts={
                    "quantity_kg": 600.0,
                    "safe_delivered_cost": 16206000.0,
                    "can_execute": False,
                },
                citations=[
                    Citation(
                        claim="quantity_kg",
                        source_path="/decisions/d1/approval-summary",
                        source_field="quantity_kg",
                        source_value=600.0,
                    ),
                    Citation(
                        claim="safe_delivered_cost",
                        source_path="/decisions/d1/approval-summary",
                        source_field="safe_delivered_cost",
                        source_value=16206000.0,
                    ),
                ],
            ),
            "evidence": _finding(
                AgentName.EVIDENCE,
                facts={
                    "decision_quantity_kg": 600.0,
                    "decision_safe_delivered_cost": 16210000.0,
                    "can_execute": False,
                },
                citations=[
                    Citation(
                        claim="decision_quantity_kg",
                        source_path="/decisions/d1/compliance",
                        source_field="decision.quantity_kg",
                        source_value=600.0,
                    ),
                    Citation(
                        claim="decision_safe_delivered_cost",
                        source_path="/decisions/d1/compliance",
                        source_field="decision.safe_delivered_cost",
                        source_value=16210000.0,
                    ),
                ],
            ),
        }
    )

    contradictions = detect_contradictions(findings)

    assert len(contradictions) == 1
    assert contradictions[0].field == "safe_delivered_cost"
    assert set(contradictions[0].agents) == {AgentName.PRICE, AgentName.EVIDENCE}
    assert run_status(findings, contradictions) == "partial"


def test_status_completed_saat_semua_ok() -> None:
    findings = _all_findings()

    assert run_status(findings) == "completed"


def test_status_partial_saat_degraded_atau_kontradiksi() -> None:
    findings = _all_findings(
        **{"freshness": _finding(AgentName.FRESHNESS, status=WorkerStatus.DEGRADED)}
    )
    contradiction = Contradiction(
        field="location",
        agents=[AgentName.SUPPLY, AgentName.DEMAND],
        values=["Jakarta", "Bandung"],
        message="lokasi berbeda",
    )

    assert run_status(findings, [contradiction]) == "partial"


def test_status_partial_saat_worker_error() -> None:
    findings = _all_findings(
        **{"price": _finding(AgentName.PRICE, status=WorkerStatus.ERROR)}
    )

    assert run_status(findings) == "partial"


def test_status_failed_saat_tidak_lengkap() -> None:
    assert run_status([]) == "failed"


def test_safety_veto_hanya_guardian_blocking() -> None:
    safety = _finding(AgentName.SAFETY, blocking=True)
    findings = _all_findings(**{"safety": safety})

    assert safety_veto(findings) is True


def test_safety_veto_false_saat_blocking_bukan_guardian() -> None:
    # AgentFinding menolak blocking non-guardian, jadi gunakan guardian false.
    findings = _all_findings()
    assert safety_veto(findings) is False
