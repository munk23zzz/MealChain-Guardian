"""Kontrak tujuh worker agent (P1).

Tes ini mengunci bentuk `AgentFinding`/`AgentRun` SEBELUM worker memanggil
LLM atau API. Fokus: angka wajib punya sitasi, `null` berbeda dari `0`,
hanya guardian yang boleh memblokir, dan tujuh stub menghasilkan finding valid.
"""

from uuid import uuid4  # noqa: I001

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
    Citation,
    Stage,
)
from agent.registry import AGENTS, LANES, get_spec  # noqa: E402
from agent.workers import build_stub_findings  # noqa: E402
from pydantic import ValidationError  # noqa: E402


def _finding(**overrides: object) -> AgentFinding:
    data: dict[str, object] = {
        "agent": "safety",
        "stage": "VERIFY",
        "status": "ok",
        "summary": "Tidak ada batch FAIL.",
        "facts": {"blocked": False},
        "citations": [],
        "confidence": 0.9,
        "warnings": [],
        "blocking": False,
    }
    data.update(overrides)
    return AgentFinding(**data)


def _numeric_finding(value: object, source_value: object) -> AgentFinding:
    return _finding(
        agent="supply",
        stage="DETECT",
        facts={"shortage_kg": value},
        citations=[
            Citation(
                claim="shortage_kg",
                source_path="/balance/Jakarta/telur",
                source_field="kekurangan_kg",
                source_value=source_value,
            )
        ],
    )


def test_tujuh_stub_menghasilkan_tujuh_finding_valid() -> None:
    findings = build_stub_findings(run_id=uuid4(), decision_id="decision-1")

    assert len(findings) == 7
    assert {finding.agent for finding in findings} == set(ANALYST_AGENTS)
    assert all(finding.status == "skipped" for finding in findings)
    assert all(finding.facts == {} for finding in findings)
    assert all(finding.citations == [] for finding in findings)
    assert all(finding.confidence is None for finding in findings)
    assert all(finding.blocking is False for finding in findings)

    run = AgentRun(
        run_id=uuid4(),
        decision_id="decision-1",
        mode="advisory",
        status="partial",
        findings=findings,
    )
    assert len(run.findings) == 7
    assert run.safety_veto is False


def test_registry_berisi_delapan_agent_dan_guardian_yang_benar() -> None:
    assert len(AGENTS) == 8
    assert {spec.name for spec in AGENTS} == set(AgentName)
    assert all(spec.endpoints for spec in AGENTS)

    blocking = {spec.name for spec in AGENTS if spec.blocking_allowed}
    assert blocking == {AgentName.SAFETY, AgentName.FRESHNESS, AgentName.EVIDENCE}

    verifier = next(spec for spec in AGENTS if spec.name is AgentName.VERIFIER)
    assert verifier.stage is Stage.VERIFY
    assert verifier.blocking_allowed is False

    flat_lanes = {name for lane in LANES for name in lane}
    assert flat_lanes == {
        AgentName.SUPPLY,
        AgentName.DEMAND,
        AgentName.SAFETY,
        AgentName.FRESHNESS,
        AgentName.PRICE,
        AgentName.LOGISTICS,
    }
    assert get_spec("supply").stage is Stage.DETECT


def test_agent_tidak_dikenal_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(agent="oracle")


def test_stage_tidak_dikenal_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(stage="FORECAST")


def test_field_wajib_dan_field_asing_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(summary=None)
    with pytest.raises(ValidationError):
        _finding(unexpected_field="tidak boleh")


def test_confidence_di_luar_0_sampai_1_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(confidence=1.5)
    with pytest.raises(ValidationError):
        _finding(confidence=-0.1)


@pytest.mark.parametrize("agent", ["supply", "demand", "price", "logistics"])
def test_worker_non_guardian_tidak_boleh_blocking(agent: str) -> None:
    with pytest.raises(ValidationError):
        _finding(agent=agent, blocking=True)


def test_angka_tanpa_sitasi_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(
            agent="supply",
            stage="DETECT",
            facts={"shortage_kg": 765.8},
            citations=[],
        )


def test_angka_nol_tanpa_sumber_ditolak() -> None:
    with pytest.raises(ValidationError):
        _numeric_finding(0, None)


def test_angka_nol_dengan_sumber_nol_diterima() -> None:
    finding = _numeric_finding(0, 0)
    assert finding.facts["shortage_kg"] == 0


def test_nilai_hilang_null_tidak_perlu_sitasi() -> None:
    finding = _finding(
        agent="supply",
        stage="DETECT",
        facts={"shortage_kg": None},
        citations=[],
    )
    assert finding.facts["shortage_kg"] is None


def test_angka_berbeda_dari_sumber_ditolak() -> None:
    with pytest.raises(ValidationError):
        _numeric_finding(765.8, 765.0)


def test_tipe_angka_berbeda_dari_sumber_ditolak() -> None:
    with pytest.raises(ValidationError):
        _numeric_finding(0, "0")


def test_sitasi_nested_memakai_path_lengkap() -> None:
    finding = _finding(
        agent="supply",
        stage="DETECT",
        facts={"coverage": {"locations": 5}},
        citations=[
            Citation(
                claim="coverage.locations",
                source_path="/balance/map",
                source_field="locations",
                source_value=5,
            )
        ],
    )
    assert finding.facts["coverage"]["locations"] == 5


def test_sitasi_nested_tanpa_path_lengkap_ditolak() -> None:
    with pytest.raises(ValidationError):
        _finding(
            agent="supply",
            stage="DETECT",
            facts={"coverage": {"locations": 5}},
            citations=[
                Citation(
                    claim="locations",
                    source_path="/balance/map",
                    source_field="locations",
                    source_value=5,
                )
            ],
        )


def test_agent_run_menolak_jumlah_finding_kurang_dari_tujuh() -> None:
    findings = build_stub_findings(run_id=uuid4(), decision_id="decision-1")
    with pytest.raises(ValidationError):
        AgentRun(
            run_id=uuid4(),
            decision_id="decision-1",
            mode="advisory",
            status="partial",
            findings=findings[:-1],
        )


def test_agent_run_menolak_agent_ganda() -> None:
    findings = build_stub_findings(run_id=uuid4(), decision_id="decision-1")
    duplicated = [findings[0], findings[0], *findings[2:]]
    with pytest.raises(ValidationError):
        AgentRun(
            run_id=uuid4(),
            decision_id="decision-1",
            mode="advisory",
            status="partial",
            findings=duplicated,
        )


def test_agent_run_safety_veto_harus_cocok_dengan_blocking() -> None:
    findings = build_stub_findings(run_id=uuid4(), decision_id="decision-1")
    safety = next(finding for finding in findings if finding.agent is AgentName.SAFETY)
    blocking_findings = [
        safety.model_copy(update={"blocking": True})
        if finding.agent is AgentName.SAFETY
        else finding
        for finding in findings
    ]

    with pytest.raises(ValidationError):
        AgentRun(
            run_id=uuid4(),
            decision_id="decision-1",
            mode="advisory",
            status="partial",
            findings=blocking_findings,
            safety_veto=False,
        )

    run = AgentRun(
        run_id=uuid4(),
        decision_id="decision-1",
        mode="advisory",
        status="partial",
        findings=blocking_findings,
        safety_veto=True,
    )
    assert run.safety_veto is True
