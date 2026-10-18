"""Kontrak data tujuh worker agent — belum memanggil model atau API.

Aturan penting:
- `null` berarti data tidak tersedia; `0` adalah nilai nyata.
- Setiap angka di `facts` wajib punya sitasi dengan path dan nilai yang cocok.
- Hanya Safety, Freshness, dan Evidence yang boleh `blocking=True`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentName(str, Enum):
    SUPPLY = "supply"
    DEMAND = "demand"
    FRESHNESS = "freshness"
    SAFETY = "safety"
    PRICE = "price"
    LOGISTICS = "logistics"
    EVIDENCE = "evidence"


class Stage(str, Enum):
    DETECT = "DETECT"
    VERIFY = "VERIFY"
    TRACE = "TRACE"
    PREDICT = "PREDICT"
    OPTIMIZE = "OPTIMIZE"
    DECIDE = "DECIDE"
    ACT = "ACT"
    LEARN = "LEARN"
    SUPERVISE = "SUPERVISE"


class WorkerStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


GUARDIAN_AGENTS = frozenset(
    {AgentName.SAFETY, AgentName.FRESHNESS, AgentName.EVIDENCE}
)


class Citation(BaseModel):
    """Satu jejak dari klaim worker ke nilai API/sumber."""

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    source_value: Any

    @field_validator("source_value")
    @classmethod
    def _scalar_source_value(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise ValueError("source_value harus skalar JSON: string, angka, bool, atau null")


def _iter_numeric_facts(
    value: Any, prefix: str = ""
) -> list[tuple[str, int | float]]:
    """Ratapi facts dan kembalikan path angka; bool bukan angka."""
    numbers: list[tuple[str, int | float]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            numbers.extend(_iter_numeric_facts(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            numbers.extend(_iter_numeric_facts(item, path))
    elif isinstance(value, bool):
        return numbers
    elif isinstance(value, (int, float)):
        numbers.append((prefix, value))
    return numbers


def _same_scalar(left: Any, right: Any) -> bool:
    """Bandingkan nilai dan tipe; 0 dan 0.0 tidak dianggap sama."""
    return type(left) is type(right) and left == right


class AgentFinding(BaseModel):
    """Output satu worker; bentuk ini yang nanti masuk ke `agent_traces`."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    stage: Stage
    status: WorkerStatus
    summary: str = Field(min_length=1)
    facts: dict[str, Any]
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    blocking: bool = False
    latency_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_guardian_and_numbers(self) -> AgentFinding:
        if self.blocking and self.agent not in GUARDIAN_AGENTS:
            raise ValueError(
                f"agent {self.agent.value} tidak boleh blocking; hanya Safety/Freshness/Evidence"
            )

        by_claim: dict[str, list[Citation]] = {}
        for citation in self.citations:
            by_claim.setdefault(citation.claim, []).append(citation)

        for path, value in _iter_numeric_facts(self.facts):
            candidates = by_claim.get(path, [])
            if not candidates:
                raise ValueError(
                    f"facts.{path} berisi angka {value!r} tetapi tidak punya "
                    f"sitasi dengan claim '{path}'"
                )
            if any(_same_scalar(citation.source_value, value) for citation in candidates):
                continue
            if any(citation.source_value is None for citation in candidates):
                raise ValueError(
                    f"facts.{path}={value!r} tidak boleh disimpulkan dari sumber null"
                )
            sources = ", ".join(repr(citation.source_value) for citation in candidates)
            raise ValueError(
                f"nilai facts.{path}={value!r} tidak cocok dengan sitasi ({sources})"
            )

        return self


class Contradiction(BaseModel):
    """Perbedaan fakta antar-worker; tidak mengubah nilai secara diam-diam."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    agents: list[AgentName] = Field(min_length=2)
    values: list[Any] = Field(min_length=2)
    message: str = Field(min_length=1)


class VerifyResult(BaseModel):
    """Hasil gerbang verifikasi deterministik atas rangkuman supervisor.

    `flag` berarti ada ketidaksesuaian yang harus dibaca manusia; gerbang ini
    tidak pernah memveto dan tidak mengubah status keputusan.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "flag"]
    reasons: list[str] = Field(default_factory=list)


class AgentRun(BaseModel):
    """Satu putaran review tujuh worker; bukan keputusan dan bukan approval."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    decision_id: str = Field(min_length=1)
    mode: Literal["advisory", "predecision"]
    status: RunStatus
    findings: list[AgentFinding] = Field(min_length=7, max_length=7)
    contradictions: list[Contradiction] = Field(default_factory=list)
    safety_veto: bool = False
    narrative: str | None = None
    # Hasil gerbang verifikasi deterministik (dijalankan SETELAH supervisor).
    # None berarti belum diverifikasi, bukan berarti lolos.
    verification: VerifyResult | None = None
    total_latency_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_seven_unique_agents_and_veto(self) -> AgentRun:
        names = [finding.agent for finding in self.findings]
        if len(set(names)) != len(AgentName):
            raise ValueError("findings harus berisi tepat tujuh agent unik")
        if set(names) != set(AgentName):
            missing = set(AgentName) - set(names)
            raise ValueError(f"agent belum lengkap: {sorted(a.value for a in missing)}")

        actual_veto = any(
            finding.blocking
            for finding in self.findings
            if finding.agent in GUARDIAN_AGENTS
        )
        if self.safety_veto != actual_veto:
            raise ValueError(
                f"safety_veto={self.safety_veto} tidak cocok dengan blocking={actual_veto}"
            )
        return self
