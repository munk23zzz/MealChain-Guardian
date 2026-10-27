"""Verifier sebagai AGENT (agent ke-8) — bukan sekadar gerbang di dalam fungsi.

Yang dikunci tes ini:

1. Auditor selalu menghasilkan `AgentFinding` sendiri, terpisah dari tujuh
   temuan analitik, sehingga ia punya baris trace `agent.verifier`.
2. Auditor TIDAK boleh melonggarkan: verdict `flag` dari gerbang deterministik
   tetap `flag` walau model yang disuntikkan mengaku "CONSISTENT".
3. Auditor tidak pernah memblokir; memblokir tetap milik guardian.
4. Model yang mati/rusak tidak menggagalkan audit — tetapi juga TIDAK boleh
   membuat audit dianggap lulus. Sejak AUD-9A-03 jawaban yang tidak sahih
   berakhir `unavailable` (fail-closed), bukan `ok`.
"""

from __future__ import annotations

import json
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

#: Fakta minimal yang konsisten — dipakai tes yang ingin audit benar-benar
#: menilai (bukan sekadar mewarisi verdict gerbang).
FAKTA_KONSISTEN = {
    "decision_id": "decision-1",
    "decision_type": "regional_balance",
    "status": "proposed",
    "iteration": 1,
    "quantity_kg": 100.0,
    "safe_delivered_cost": 11000.0,
    "sdc_check": {
        "safe_delivered_cost": 11000.0,
        "breakdown_total": 11000.0,
        "selisih": 0.0,
        "toleransi": 0.01,
        "cocok": True,
        "alasan": None,
    },
    "evidence": {"count": 2, "ids": ["ev-1", "ev-2"], "types": ["gps", "temperature"]},
    "batch_sumber": {
        "batch_ids": ["batch-1"],
        "count": 1,
        "statuses": ["pass"],
        "worst_status": "pass",
        "failed_batch_ids": [],
        "quarantined_batch_ids": [],
        "penghalang": None,
        "worst_freshness_score": 0.95,
        "freshness_status": "pass",
        "freshness_ambang": {"pass": 0.85, "needs_verification": 0.6},
    },
    "exclusion": {"dapat_dinilai": True, "aktif": False, "ids": [], "alasan": None},
    "ledger": {"count": 1, "block_ids": ["ledger-1"], "actions": ["propose"]},
    "citations": {
        "decision_id": "decision-1",
        "batch_ids": ["batch-1"],
        "evidence_ids": ["ev-1", "ev-2"],
        "ledger_block_ids": ["ledger-1"],
        "exclusion_ids": [],
    },
}


def _model_jawab(verdict: str = "consistent", *, citations: list | None = None):
    """Model palsu yang menjawab JSON SAH (skema verifier)."""

    def _jawab(prompt: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "verdict": verdict,
                "checks": [
                    {
                        "nama": "sdc_vs_cost_breakdown",
                        "klaim": "SDC sama dengan rincian",
                        "aktual": "cocok=true",
                        "lulus": True,
                    }
                ],
                "citations": citations
                if citations is not None
                else [{"decision_id": "decision-1"}],
                "catatan": "fakta konsisten dengan klaim supervisor",
            },
            ensure_ascii=False,
        )

    return _jawab


def _run(
    verification: VerifyResult | None, *, narrative: str | None = "ringkasan"
) -> AgentRun:
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
    assert finding.facts["audit_verdict"] in {"flagged", "unavailable"}
    assert any("narasi" in warning for warning in finding.warnings)


def test_audit_sepakat_saat_fakta_dan_model_sahih() -> None:
    """Verdict `consistent` harus berasal dari fakta + jawaban model sahih."""
    run = _run(VerifyResult(verdict="pass"))

    finding = VerifierWorker(model=_model_jawab("consistent")).audit(
        run, fakta=FAKTA_KONSISTEN
    )

    assert finding.status is WorkerStatus.OK
    assert finding.blocking is False
    assert finding.facts["verdict"] == "pass"
    assert finding.facts["audit_verdict"] == "consistent"
    assert finding.facts["checks_failed"] == 0
    assert finding.citations, "audit konsisten wajib membawa sitasi"


def test_tanpa_model_tidak_menyatakan_consistent() -> None:
    """Tidak ada auditor model ≠ tidak ada masalah (fail-closed)."""
    finding = VerifierWorker().audit(
        _run(VerifyResult(verdict="pass")), fakta=FAKTA_KONSISTEN
    )

    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["audit_verdict"] == "unavailable"


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

    assert jawaban_model, "model seharusnya dipanggil untuk menilai klaim"
    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["verdict"] == "flag"
    # Tanpa fakta terbaca audit tidak boleh menyimpulkan apa pun: `unavailable`.
    assert finding.facts["audit_verdict"] == "unavailable"
    assert any(reason.startswith("model: ") for reason in finding.facts["reasons"])


def test_model_optimistis_dengan_fakta_gagal_tetap_flagged() -> None:
    """Model menjawab CONSISTENT (JSON sah) padahal gerbang flag → guarded."""
    finding = VerifierWorker(model=_model_jawab("consistent")).audit(
        _run(
            VerifyResult(verdict="flag", reasons=["narasi_tidak_menyebut_penurunan"]),
            narrative="Semua aman.",
        ),
        fakta=FAKTA_KONSISTEN,
    )

    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["model_verdict"] == "consistent"
    assert finding.facts["audit_verdict"] == "flagged"
    assert any("gerbang" in warning for warning in finding.warnings)


def test_model_rusak_tidak_menggagalkan_audit_tetapi_tidak_lolos() -> None:
    def model_meledak(prompt: str) -> str:  # noqa: ARG001
        raise RuntimeError("provider mati")

    finding = VerifierWorker(model=model_meledak).audit(
        _run(VerifyResult(verdict="pass")), fakta=FAKTA_KONSISTEN
    )

    assert finding.agent is AgentName.VERIFIER
    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["audit_verdict"] == "unavailable"
    assert any("model gagal" in warning for warning in finding.warnings)


def test_model_mengembalikan_teks_sampah_diabaikan() -> None:
    """Output sampah tidak boleh menambah alasan maupun menaikkan verdict."""
    finding = VerifierWorker(model=lambda prompt: "bukan json sama sekali").audit(
        _run(VerifyResult(verdict="pass")), fakta=FAKTA_KONSISTEN
    )

    assert finding.status is WorkerStatus.DEGRADED
    assert finding.facts["audit_verdict"] == "unavailable"
    assert finding.facts["model_verdict"] is None
    assert not any(
        str(reason).startswith("model: tepat") for reason in finding.facts["reasons"]
    )
