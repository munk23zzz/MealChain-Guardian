"""`FLAGGED` dari model verifier hanya sah bila menunjuk ketidaksesuaian NYATA.

Konteks (27 Okt 2026): verifier model menjawab `flagged` dengan `catatan` prosa
("empat klaim kritis gagal …") tanpa satu pun `checks` yang menunjuk nilai fakta,
lalu veto itu dipakai untuk memblokir putaran. Guard `jaga_verdict` dulu
meloloskan `flagged` apa pun dari model, jadi prosa saja cukup untuk memveto.

Yang dikunci tes ini:

1. `flagged` tanpa cek gagal yang menunjuk fakta → `unavailable`
   (bukan `flagged`, dan tetap bukan `consistent`).
2. `flagged` dengan cek gagal yang menunjuk field/nilai fakta → tetap `flagged`.
3. Prompt audit membawa FAKTA_RUN (status run + safety_veto) sehingga klaim
   narasi tentang putaran ini bisa diperiksa terhadap objek yang benar —
   bukan disamakan dengan status keputusan di `audit-facts`.
4. `consistent` tetap butuh cek lulus + sitasi + gerbang pass (guard tidak
   dilunakkan).
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

pytest.importorskip("agent")

from agent.contracts import (  # noqa: E402
    AgentRun,
    RunStatus,
    VerifyResult,
)
from agent.workers import build_stub_findings  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402

from tests.test_agent_verifier import FAKTA_KONSISTEN  # noqa: E402


def _run(narrative: str = "ringkasan", *, status: RunStatus = RunStatus.COMPLETED) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        decision_id="decision-1",
        mode="advisory",
        status=status,
        findings=build_stub_findings(uuid4(), "decision-1"),
        narrative=narrative,
        verification=VerifyResult(verdict="pass"),
    )


def _model(verdict: str, *, checks: list[dict], catatan: str = "") -> object:
    def _jawab(prompt: str) -> str:
        return json.dumps(
            {
                "verdict": verdict,
                "checks": checks,
                "citations": [{"decision_id": "decision-1"}],
                "catatan": catatan,
            },
            ensure_ascii=False,
        )

    return _jawab


def test_flagged_tanpa_cek_gagal_tidak_diterima() -> None:
    """Prosa "klaim kritis gagal" tanpa cek yang menunjuk fakta ≠ veto sah."""
    model = _model(
        "flagged",
        checks=[
            {
                "nama": "sdc_vs_cost_breakdown",
                "klaim": "SDC sama dengan rincian",
                "aktual": "cocok=true",
                "lulus": True,
            }
        ],
        catatan=(
            "Empat klaim kritis gagal: (1) status diklaim vetoed tetapi FAKTA "
            "mencatat proposed; (2) safety_veto=true tidak didukung FAKTA."
        ),
    )

    finding = VerifierWorker(model=model).audit(
        _run("Review 7 agen selesai."), fakta=dict(FAKTA_KONSISTEN)
    )

    assert finding.facts["model_verdict"] == "flagged"
    assert finding.facts["audit_verdict"] == "unavailable", (
        "FLAGGED tanpa cek pendukung tidak boleh menjadi veto"
    )
    assert any("tanpa cek" in warning for warning in finding.warnings)


def test_flagged_dengan_cek_gagal_yang_menunjuk_fakta_tetap_flagged() -> None:
    model = _model(
        "flagged",
        checks=[
            {
                "nama": "kesegaran_certified",
                "klaim": "kesegaran memenuhi ambang certified",
                "aktual": "freshness_status=needs_verification (bukan pass)",
                "lulus": False,
            }
        ],
        catatan="kesegaran belum certified",
    )

    finding = VerifierWorker(model=model).audit(
        _run("Kesegaran sudah pass."), fakta=dict(FAKTA_KONSISTEN)
    )

    assert finding.facts["audit_verdict"] == "flagged"


def test_prompt_membawa_fakta_run_supaya_klaim_narasi_bisa_diaudit() -> None:
    prompt_diterima: list[str] = []

    def model(prompt: str) -> str:
        prompt_diterima.append(prompt)
        return json.dumps(
            {
                "verdict": "consistent",
                "checks": [
                    {
                        "nama": "sdc_vs_cost_breakdown",
                        "klaim": "SDC sama dengan rincian",
                        "aktual": "cocok=true",
                        "lulus": True,
                    }
                ],
                "citations": [{"decision_id": "decision-1"}],
                "catatan": "konsisten",
            }
        )

    VerifierWorker(model=model).audit(
        _run("Status run: completed; safety_veto=false."), fakta=dict(FAKTA_KONSISTEN)
    )

    prompt = prompt_diterima[0]
    assert "### FAKTA_RUN" in prompt
    assert '"safety_veto": false' in prompt
    assert '"status_run": "completed"' in prompt


def test_system_prompt_menjelaskan_objek_status_dan_syarat_flagged() -> None:
    """Prompt verifier ikut menjaga agar `status` tidak disamakan antarobjek."""
    from agent.workers.verifier import load_system_prompt  # noqa: PLC0415

    teks = load_system_prompt()
    assert "FAKTA_RUN" in teks
    assert "status KEPUTUSAN" in teks
    assert "lulus: false" in teks
    assert "Bukan alasan `flagged`" in teks
