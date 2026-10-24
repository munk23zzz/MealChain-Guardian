"""Verifier sebagai AGENT (agent ke-8) — bukan sekadar gerbang di dalam fungsi.

Yang dikunci tes ini:

1. Auditor selalu menghasilkan `AgentFinding` sendiri, terpisah dari tujuh
   temuan analitik, sehingga ia punya baris trace `agent.verifier`.
2. Auditor TIDAK boleh melonggarkan: verdict `flag` dari gerbang deterministik
   tetap `flag` walau model yang disuntikkan mengaku "CONSISTENT".
3. Auditor tidak pernah memblokir; memblokir tetap milik guardian.
4. Model yang mati/rusak tidak menggagalkan audit (deterministik yang jadi dasar).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

# `agent/` adalah runtime terpisah di akar repo (image sendiri). Tanpa mount
# ./agent:/agent (lihat docker-compose.yml), impor di bawah gagal dan pytest
# berhenti dengan "Interrupted: 1 error during collection" (audit DEP-04).
pytest.importorskip("agent")

from agent.contracts import (  # noqa: E402
    AgentName,
    AgentRun,
    RunStatus,
    VerifyResult,
    WorkerStatus,
)
from agent.workers import build_stub_findings  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402


def _run(verification: VerifyResult | None, *, narrative: str | None = "ringkasan") -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        decision_id="decision-1",
        mode="advisory",
        status=RunStatus.COMPLETED,
        findings=build_stub_findings(uuid4(), "decision-1"),
        narrative=narrative,
        verification=verification,
    )


def test_audit_mewarisi_verdict_flag_dan_tidak_memblokir() -> None:
    run = _run(VerifyResult(verdict="flag", reasons=["narasi_menghaluskan: safety"]))

    finding = VerifierWorker().audit(run)

    assert finding.agent is AgentName.VERIFIER
    assert finding.status is WorkerStatus.DEGRADED
    assert finding.blocking is False
    assert finding.facts["verdict"] == "flag"
    assert finding.facts["dasar"] == "agent/verify.py"
    assert any("narasi" in warning for warning in finding.warnings)


def test_audit_sepakat_saat_verdict_pass() -> None:
    run = _run(VerifyResult(verdict="pass"))

    finding = VerifierWorker().audit(run)

    assert finding.status is WorkerStatus.OK
    assert finding.blocking is False
    assert finding.facts["verdict"] == "pass"


def test_audit_tanpa_hasil_verifikasi_tidak_mengaku_lolos() -> None:
    """Ketiadaan hasil verifikasi bukan persetujuan (fail-closed)."""
    finding = VerifierWorker().audit(_run(None))

    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["verdict"] is None
    assert "verification_missing" in finding.warnings


def test_model_tidak_boleh_melonggarkan_verdict_deterministik() -> None:
    """Model mengaku CONSISTENT saat gerbang menandai flag → tetap degraded."""
    jawaban_model: list[str] = []

    def model_optimistis(prompt: str) -> str:
        jawaban_model.append(prompt)
        return '{"verdict": "CONSISTENT", "reason": "menurut saya semua baik"}'

    run = _run(VerifyResult(verdict="flag", reasons=["angka_price_tidak_utuh"]))
    finding = VerifierWorker(model=model_optimistis).audit(run)

    assert jawaban_model, "model seharusnya dipanggil untuk alasan tambahan"
    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["verdict"] == "flag"
    assert any(reason.startswith("model: ") for reason in finding.facts["reasons"])


def test_model_rusak_tidak_menggagalkan_audit() -> None:
    def model_meledak(prompt: str) -> str:
        raise RuntimeError("provider mati")

    finding = VerifierWorker(model=model_meledak).audit(
        _run(VerifyResult(verdict="pass"))
    )

    assert finding.status is WorkerStatus.OK
    assert finding.facts["verdict"] == "pass"


def test_model_mengembalikan_teks_sampah_diabaikan() -> None:
    finding = VerifierWorker(model=lambda prompt: "bukan json sama sekali").audit(
        _run(VerifyResult(verdict="pass"))
    )

    assert finding.status is WorkerStatus.OK
    assert not any(
        str(reason).startswith("model: ") for reason in finding.facts.get("reasons", [])
    )
