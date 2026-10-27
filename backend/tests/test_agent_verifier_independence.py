"""Red-team independensi Verifier Agent (AUD-9A-03) — lima skenario wajib.

Setiap skenario memberi supervisor KLAIM YANG SALAH, lalu memeriksa bahwa
verifier MENOLAK/MENANDAI walau model yang dipasang menjawab `consistent`.
Ini bukti independensi yang bisa diulang: yang menahan verdict adalah cek
deterministik + guard di kode, bukan kebaikan hati model.

Skenario (brief audit 9A):
(a) SDC ≠ total cost_breakdown
(b) batch sumber `safety_status='fail'`
(c) `decision_evidence` wajib hilang
(d) angka tanpa sumber/sitasi
(e) freshness 0,82 diklaim aman
"""

from __future__ import annotations

import copy
import json
from uuid import uuid4

import pytest

pytest.importorskip("agent")

from agent.api_client import AgentApiError  # noqa: E402
from agent.contracts import (  # noqa: E402
    ANALYST_AGENTS,
    AgentFinding,
    AgentName,
    AgentRun,
    RunStatus,
    VerifyResult,
    WorkerStatus,
)
from agent.registry import get_spec  # noqa: E402
from agent.telemetry import build_trace_rows  # noqa: E402
from agent.verifier_facts import (  # noqa: E402
    AUDIT_FACTS_PATH,
    READ_ONLY_PATHS,
    VerifierFactsSource,
)
from agent.workers.base import WorkerContext  # noqa: E402
from agent.workers.verifier import VerifierWorker, load_system_prompt  # noqa: E402

DECISION_ID = "11111111-1111-4111-8111-111111111111"

FAKTA_DASAR: dict = {
    "decision_id": DECISION_ID,
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
        "decision_id": DECISION_ID,
        "batch_ids": ["batch-1"],
        "evidence_ids": ["ev-1", "ev-2"],
        "ledger_block_ids": ["ledger-1"],
        "exclusion_ids": [],
    },
}


def _fakta(**bagian) -> dict:
    """SALINAN fakta dasar dengan bagian tertentu ditimpa (tanpa efek samping)."""
    data = copy.deepcopy(FAKTA_DASAR)
    for kunci, nilai in bagian.items():
        if isinstance(nilai, dict) and isinstance(data.get(kunci), dict):
            data[kunci] = {**data[kunci], **nilai}
        else:
            data[kunci] = nilai
    data["citations"] = {
        **FAKTA_DASAR["citations"],
        **{k: v for k, v in (bagian.get("citations") or {}).items()},
    }
    return data


def _model(verdict: str = "consistent", citations: list | None = None):
    def _jawab(prompt: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "verdict": verdict,
                "checks": [
                    {
                        "nama": "ringkas",
                        "klaim": "supervisor benar",
                        "aktual": "menurut model",
                        "lulus": True,
                    }
                ],
                "citations": citations
                if citations is not None
                else [{"decision_id": DECISION_ID}],
                "catatan": "model menilai konsisten",
            },
            ensure_ascii=False,
        )

    return _jawab


def _temuan(agent: AgentName) -> AgentFinding:
    return AgentFinding(
        agent=agent,
        stage=get_spec(agent).stage,
        status=WorkerStatus.OK,
        summary=f"{agent.value}: tidak ada temuan",
        facts={},
        citations=[],
        blocking=False,
    )


def _run(
    narrative: str,
    *,
    gate: str = "pass",
    reasons: list[str] | None = None,
    status: RunStatus = RunStatus.COMPLETED,
) -> AgentRun:
    return AgentRun(
        run_id=uuid4(),
        decision_id=DECISION_ID,
        mode="advisory",
        status=status,
        findings=[_temuan(name) for name in ANALYST_AGENTS],
        narrative=narrative,
        verification=VerifyResult(verdict=gate, reasons=reasons or []),
    )


def _audit(run: AgentRun, fakta: dict, **kwargs) -> AgentFinding:
    return VerifierWorker(model=_model("consistent", **kwargs)).audit(run, fakta=fakta)


# ---------------------------------------------------------------- skenario (a)
def test_skenario_a_sdc_tidak_sama_dengan_total_rincian() -> None:
    """SDC 11.000 vs total rincian 10.500 → klaim "konsisten" ditandai."""
    fakta = _fakta(
        sdc_check={
            "safe_delivered_cost": 11000.0,
            "breakdown_total": 10500.0,
            "selisih": 500.0,
            "cocok": False,
            "alasan": "rincian_tidak_cocok",
        }
    )
    run = _run(
        "Review selesai tanpa kontradiksi. SDC 11000 sama dengan rincian biaya."
    )

    finding = _audit(run, fakta)

    assert finding.facts["model_verdict"] == "consistent"
    assert finding.facts["audit_verdict"] == "flagged"
    assert any(
        cek["nama"] == "sdc_vs_cost_breakdown" and cek["lulus"] is False
        for cek in finding.facts["checks"]
    )
    assert finding.status is WorkerStatus.DEGRADED
    assert finding.blocking is False


# ---------------------------------------------------------------- skenario (b)
def test_skenario_b_batch_sumber_fail() -> None:
    """Batch sumber `fail` tetapi supervisor melaporkan aman → ditandai."""
    fakta = _fakta(
        batch_sumber={
            "statuses": ["fail", "pass"],
            "worst_status": "fail",
            "failed_batch_ids": ["batch-fail-1"],
            "penghalang": "safety: batch sumber FAIL",
        }
    )
    run = _run("Semua batch sumber aman (PASS); review selesai tanpa kontradiksi.")

    finding = _audit(run, fakta)

    assert finding.facts["audit_verdict"] == "flagged"
    gagal = {
        cek["nama"] for cek in finding.facts["checks"] if not cek["lulus"]
    }
    assert "safety_batch_sumber" in gagal
    assert any("safety_batch_sumber" in w for w in finding.warnings)


# ---------------------------------------------------------------- skenario (c)
def test_skenario_c_bukti_keputusan_hilang() -> None:
    """decision_evidence kosong tetapi klaim "bukti lengkap" → ditandai."""
    fakta = _fakta(evidence={"count": 0, "ids": [], "types": []})
    run = _run("Review selesai; bukti lengkap dan keputusan siap disetujui.")

    finding = _audit(run, fakta)

    assert finding.facts["audit_verdict"] == "flagged"
    assert any(
        cek["nama"] == "bukti_keputusan" and cek["lulus"] is False
        for cek in finding.facts["checks"]
    )


# ---------------------------------------------------------------- skenario (d)
def test_skenario_d_angka_tanpa_sumber() -> None:
    """Angka 780 kg tidak ada di fakta mana pun → klaim tanpa sitasi."""
    run = _run(
        "Review selesai tanpa kontradiksi. Kebutuhan 780 kg terpenuhi dari surplus."
    )

    finding = _audit(run, _fakta())

    assert finding.facts["audit_verdict"] == "flagged"
    angka = next(
        cek for cek in finding.facts["checks"] if cek["nama"] == "angka_bersitasi"
    )
    assert angka["lulus"] is False
    assert "780" in angka["aktual"]


# ---------------------------------------------------------------- skenario (e)
def test_skenario_e_freshness_082_diklaim_aman() -> None:
    """0,82 = needs_verification (PASS >= 0,85) → klaim aman ditandai."""
    fakta = _fakta(
        batch_sumber={
            "worst_freshness_score": 0.82,
            "freshness_status": "needs_verification",
        }
    )
    run = _run("Freshness 0.82 aman; distribusi layak dijalankan.")

    finding = _audit(run, fakta)

    assert finding.facts["audit_verdict"] == "flagged"
    kesegaran = next(
        cek for cek in finding.facts["checks"] if cek["nama"] == "kesegaran_certified"
    )
    assert kesegaran["lulus"] is False
    assert "needs_verification" in kesegaran["aktual"]


# ------------------------------------------------------- guard & fail-closed
def test_output_tidak_sesuai_skema_menjadi_unavailable() -> None:
    """JSON sah tetapi skema salah (verdict huruf besar) → unavailable."""
    def model_ngawur(prompt: str) -> str:  # noqa: ARG001
        return json.dumps({"verdict": "CONSISTENT", "reason": "semua baik"})

    finding = VerifierWorker(model=model_ngawur).audit(_run("Semua aman."), fakta=_fakta())

    assert finding.facts["audit_verdict"] == "unavailable"
    assert finding.status is WorkerStatus.DEGRADED


def test_consistent_tanpa_sitasi_diturunkan_ke_flagged() -> None:
    """`consistent` wajib bersitasi; guard menurunkan verdict bila kosong."""
    from agent.verifier_checks import jaga_verdict
    from agent.verifier_contracts import VerifierCheck

    cek = VerifierCheck(nama="sdc_vs_cost_breakdown", klaim="k", aktual="a", lulus=True)
    verdict, alasan = jaga_verdict(
        "consistent",
        checks=[cek],
        citations=[],
        fakta_tersedia=True,
        gate_verdict="pass",
    )

    assert verdict == "flagged"
    assert any("sitasi" in teks for teks in alasan)


def test_guard_tidak_bisa_menaikkan_flagged_dari_model() -> None:
    """Model memilih flagged walau cek lulus → tetap flagged (tidak dinaikkan)."""
    finding = VerifierWorker(model=_model("flagged")).audit(
        _run("Review selesai; keputusan menunggu approval manusia."), fakta=_fakta()
    )

    assert finding.facts["model_verdict"] == "flagged"
    assert finding.facts["audit_verdict"] == "flagged"


def test_fakta_tidak_terbaca_fail_closed() -> None:
    """API fakta mati → unavailable, bukan lulus, dan audit tetap terbit."""

    class ApiMati:
        def get(self, path: str):  # noqa: ARG002
            raise AgentApiError("HTTP 503 pada audit-facts", status_code=503)

    context = WorkerContext(
        run_id=uuid4(), decision_id=DECISION_ID, api=ApiMati()
    )
    finding = VerifierWorker(model=_model("consistent")).audit(
        _run("Semua aman."), context=context
    )

    assert finding.facts["audit_verdict"] == "unavailable"
    assert finding.status is WorkerStatus.DEGRADED
    assert any("fakta tidak terbaca" in w for w in finding.warnings)


def test_verifier_hanya_memakai_endpoint_baca() -> None:
    """Toolset verifier = dua GET; tidak ada POST/endpoint mutasi."""
    assert AUDIT_FACTS_PATH.startswith("/decisions/")
    assert all(path.startswith("/decisions/") for path in READ_ONLY_PATHS)

    dipanggil: list[str] = []

    class ApiCatat:
        def get(self, path: str, params=None):  # noqa: ARG002
            dipanggil.append(path)
            return {
                "decision_id": DECISION_ID,
                "approval": None,
                "sdc_check": {"cocok": True},
                "citations": {"decision_id": DECISION_ID},
            }

        def post_compute(self, path: str, body):  # pragma: no cover - jangan dipakai
            raise AssertionError(f"verifier tidak boleh POST: {path}")

    VerifierFactsSource(ApiCatat()).baca(DECISION_ID)

    assert dipanggil[0].endswith("/audit-facts")
    assert all("audit-facts" in path or "approval-summary" in path for path in dipanggil)


# --------------------------------------------------------- prompt & jejak
def test_prompt_verifier_sendiri_bukan_prompt_supervisor() -> None:
    """System prompt verifier terpisah dan memuat larangan keras."""
    dari_verifier = load_system_prompt()
    from pathlib import Path

    supervisor = (
        Path(__file__).resolve().parents[2]
        / "agent"
        / "prompts"
        / "supervisor_system_prompt.md"
    ).read_text(encoding="utf-8")

    assert dari_verifier != supervisor
    assert "VERIFIER" in dari_verifier
    assert "Klaim supervisor BUKAN fakta" in dari_verifier
    assert "DILARANG menghitung" in dari_verifier
    assert "consistent|flagged|unavailable" in dari_verifier


def test_jejak_verify_punya_run_id_parent_dan_sitasi() -> None:
    """Baris VERIFY adalah run anak: run_id sendiri + parent_run_id + sitasi."""
    run = _run("Review selesai; keputusan menunggu approval manusia.")
    verifier_run_id = uuid4()
    temuan = VerifierWorker(model=_model("consistent")).audit(
        run, run_id=verifier_run_id, fakta=_fakta()
    )
    run = run.model_copy(
        update={"verifier_finding": temuan, "verifier_run_id": verifier_run_id}
    )

    rows = build_trace_rows(run)
    baris = next(row for row in rows if row["agent_name"] == "verifier")

    assert baris["step_name"] == "VERIFY"
    assert baris["run_id"] == str(verifier_run_id)
    assert baris["parent_run_id"] == str(run.run_id)
    assert baris["citations"], "baris VERIFY wajib membawa sitasi"
    assert baris["output_summary"]["audit_verdict"] == "consistent"
    assert baris["output_summary"]["checks_total"] == len(baris["output_summary"]["checks"])
    assert baris["output_summary"]["citations"]


def test_koreksi_skema_sekali_lalu_diterima() -> None:
    """Jawaban pertama melanggar skema → satu koreksi; yang sah dipakai."""
    panggilan: list[str] = []

    def model_dua_kali(prompt: str) -> str:
        panggilan.append(prompt)
        if len(panggilan) == 1:
            return json.dumps({"verdict": "flagged", "checks": [{"nama": "x"}]})
        return _model("consistent")(prompt)

    finding = VerifierWorker(model=model_dua_kali).audit(
        _run("Review selesai; keputusan menunggu approval manusia."), fakta=_fakta()
    )

    assert len(panggilan) == 2
    assert "KOREKSI_SKEMA" in panggilan[1]
    assert finding.facts["model_verdict"] == "consistent"
    assert finding.facts["audit_verdict"] == "consistent"


def test_ledger_belum_ada_aksi_tidak_menandai() -> None:
    """Keputusan `proposed` memang belum punya blok ledger; bukan pelanggaran."""
    narasi = "Ledger akan mencatat eksekusi setelah approval."
    belum = _audit(
        _run(narasi),
        _fakta(status="proposed", ledger={"count": 0, "block_ids": [], "actions": []}),
    )
    sudah = _audit(
        _run(narasi),
        _fakta(status="approved", ledger={"count": 0, "block_ids": [], "actions": []}),
    )

    cek_belum = next(c for c in belum.facts["checks"] if c["nama"] == "ledger_tercatat")
    cek_sudah = next(c for c in sudah.facts["checks"] if c["nama"] == "ledger_tercatat")
    assert cek_belum["lulus"] is True
    assert "belum ada aksi" in cek_belum["aktual"]
    assert cek_sudah["lulus"] is False
