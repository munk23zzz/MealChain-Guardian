"""Narasi supervisor wajib berasal dari FAKTA yang ia terima, bukan karangan.

Konteks (27 Okt 2026): satu putaran review berakhir `vetoed` setiap kali karena
narasi menyebut "guardian yang memblokir"/"JANGAN EKSEKUSI" sementara fakta
yang dibaca verifier mencatat `safety_veto=false` dan seluruh cek deterministik
lulus. Verifier model lalu memveto narasi itu — veto palsu yang mengulang di
setiap putaran.

Yang dikunci tes ini:

1. Narasi hanya boleh menyebut status/veto yang benar-benar ada di fakta run:
   putaran bersih TIDAK boleh menghasilkan kata "memblokir"/"jangan eksekusi".
2. Bila narator (model) mengarang klaim yang bertentangan dengan fakta,
   narasinya diganti narasi deterministik dari fakta — bukan diloloskan.
3. Putaran dengan guardian yang benar-benar memblokir tetap menyebut veto dan
   menyebut guardian + fakta pemblokirnya (gerbang keselamatan tidak dilunakkan).
4. Context worker dilengkapi `batch_ids` dari `/decisions/{id}/audit-facts` bila
   approval-summary tidak membawanya; bila fakta itu tidak terbaca, context
   dibiarkan kosong (fail-closed), bukan ditebak.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("agent")

from agent.api_client import AgentApiError  # noqa: E402
from agent.contracts import AgentFinding, AgentName, WorkerStatus  # noqa: E402
from agent.orchestrator import (  # noqa: E402
    narasi_dari_fakta,
    pelanggaran_narasi,
    run_review,
)
from agent.registry import get_spec  # noqa: E402
from agent.workers.base import WorkerContext  # noqa: E402
from agent.workers.freshness import FreshnessWorker  # noqa: E402
from agent.workers.safety import SafetyWorker  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402

#: Fakta audit untuk keputusan pengadaan: 2 batch sumber, satu `pending`,
#: kesegaran terburuk 0.82 (butuh verifikasi). Semua gerbang deterministik lulus.
FAKTA_BERSIH = {
    "decision_id": "decision-1",
    "decision_type": "supplier_procurement",
    "status": "proposed",
    "iteration": 1,
    "quantity_kg": 1100.0,
    "safe_delivered_cost": 16132417.4,
    "sdc_check": {
        "safe_delivered_cost": 16132417.4,
        "breakdown_total": 16132417.4,
        "selisih": 0.0,
        "toleransi": 0.01,
        "cocok": True,
        "alasan": None,
    },
    "evidence": {"count": 1, "ids": ["ev-1"], "types": ["human_inspection"]},
    "batch_sumber": {
        "batch_ids": ["batch-1", "batch-2"],
        "count": 2,
        "statuses": ["pending", "pass"],
        "worst_status": "pending",
        "failed_batch_ids": [],
        "quarantined_batch_ids": [],
        "penghalang": None,
        "worst_freshness_score": 0.82,
        "freshness_status": "needs_verification",
        "freshness_ambang": {"pass": 0.85, "needs_verification": 0.6},
    },
    "exclusion": {"dapat_dinilai": True, "aktif": False, "ids": [], "alasan": None},
    "ledger": {"count": 0, "block_ids": [], "actions": []},
    "citations": {
        "decision_id": "decision-1",
        "batch_ids": ["batch-1", "batch-2"],
        "evidence_ids": ["ev-1"],
        "ledger_block_ids": [],
        "exclusion_ids": [],
    },
}

SUMMARY = {
    "target_location": "Jakarta",
    "commodity": "beras",
    "quantity_kg": 1100.0,
    "supplier": {"id": "supplier-1", "name": "UD Rorotan Jaya Beras"},
    "safety": {"batch_ids": []},
}


class ApiFakta:
    """API palsu: approval-summary + audit-facts (keduanya GET baca-saja)."""

    def __init__(self, *, fakta: dict | None = None, audit_gagal: bool = False) -> None:
        self.fakta = fakta or FAKTA_BERSIH
        self.audit_gagal = audit_gagal
        self.paths: list[str] = []

    def semua_batch(self, page_size: int = 500, max_rows: int = 5000) -> list[dict]:
        return self.get("/batches")["batches"]

    def get(self, path: str, params: dict | None = None) -> dict:
        self.paths.append(path)
        if path.endswith("/approval-summary"):
            return dict(SUMMARY)
        if path.endswith("/audit-facts"):
            if self.audit_gagal:
                raise AgentApiError("HTTP 500 pada audit-facts", status_code=500)
            return dict(self.fakta)
        if path == "/supplier-exclusions":
            return {"items": []}
        if path == "/batches":
            return {
                "total": 2,
                "batches": [
                    {
                        "id": "batch-1",
                        "location": "Jakarta",
                        "commodity": "beras",
                        "safety_status": "pending",
                        "quarantine_status": "none",
                        "freshness_score": 0.95,
                        "usable_until": "2099-01-01T00:00:00+00:00",
                    },
                    {
                        "id": "batch-2",
                        "location": "Jakarta",
                        "commodity": "beras",
                        "safety_status": "pass",
                        "quarantine_status": "none",
                        "freshness_score": 0.82,
                        "usable_until": "2099-01-01T00:00:00+00:00",
                    },
                ],
            }
        raise AgentApiError(f"path tidak dikenal: {path}")


class FixedWorker:
    """Worker palsu deterministik; tidak memanggil model/API."""

    def __init__(
        self,
        name: AgentName,
        *,
        status: WorkerStatus = WorkerStatus.OK,
        blocking: bool = False,
        facts: dict | None = None,
    ) -> None:
        self.name = name
        self.status = status
        self.blocking = blocking
        self.facts = facts or {}

    def run(self, context: WorkerContext) -> AgentFinding:
        return AgentFinding(
            agent=self.name,
            stage=get_spec(self.name).stage,
            status=self.status,
            summary=f"{self.name.value} selesai",
            facts=dict(self.facts),
            citations=[],
            blocking=self.blocking,
        )


def _workers(**overrides) -> dict:
    workers: dict = {}
    for name in AgentName:
        if name is AgentName.VERIFIER:
            workers[name] = VerifierWorker()
        else:
            workers[name] = overrides.get(name, FixedWorker(name))
    return workers


def _context() -> WorkerContext:
    return WorkerContext(
        run_id=uuid4(),
        decision_id="decision-1",
        location="Jakarta",
        commodity="beras",
        api=object(),
    )


# ---------------------------------------------------------------------------
# 1. Narasi bersih tidak boleh mengklaim veto
# ---------------------------------------------------------------------------


def test_narasi_putaran_bersih_tidak_menyebut_veto_atau_blokir() -> None:
    run = run_review("decision-1", context=_context(), workers=_workers())

    assert run.status == "completed"
    assert run.safety_veto is False

    teks = (run.narrative or "").lower()
    assert "safety_veto=false" in teks, "narasi wajib menyebut fakta veto apa adanya"
    assert "vetoed" not in teks
    assert "memblokir" not in teks
    assert "jangan eksekusi" not in teks
    assert "safety_veto=true" not in teks


def test_narasi_veto_yang_benar_tetap_menyebut_guardian_dan_faktanya() -> None:
    """Gerbang keselamatan tidak dilunakkan: blokir nyata tetap dinyatakan."""

    run = run_review(
        "decision-1",
        context=_context(),
        workers=_workers(
            **{
                AgentName.SAFETY: FixedWorker(
                    AgentName.SAFETY,
                    status=WorkerStatus.DEGRADED,
                    blocking=True,
                    facts={"batch_count": None, "failed_count": None},
                )
            }
        ),
    )

    assert run.status == "vetoed"
    assert run.safety_veto is True
    teks = (run.narrative or "").lower()
    assert "vetoed" in teks and "safety_veto=true" in teks
    assert "jangan eksekusi" in teks
    assert "safety" in teks
    assert "batch sumber tidak teridentifikasi" in teks


# ---------------------------------------------------------------------------
# 2. Narator yang mengarang tidak diloloskan
# ---------------------------------------------------------------------------

KARANGAN = (
    "Review 7 agen menemukan guardian yang memblokir. JANGAN EKSEKUSI keputusan "
    "ini sebelum bukti diperbaiki; status vetoed, safety_veto=true."
)


def test_narator_karangan_diganti_narasi_dari_fakta() -> None:
    run = run_review(
        "decision-1",
        context=_context(),
        workers=_workers(),
        narrator=lambda fakta: KARANGAN,
    )

    teks = run.narrative or ""
    assert teks != KARANGAN, "narasi karangan tidak boleh lolos"
    assert "completed" in teks.lower()
    assert "memblokir" not in teks.lower()
    # Status run tetap milik tujuh worker, bukan milik narator.
    assert run.status == "completed"
    assert run.safety_veto is False


def test_pelanggaran_narasi_menangkap_klaim_veto_palsu() -> None:
    run = run_review("decision-1", context=_context(), workers=_workers())

    assert pelanggaran_narasi(KARANGAN, run), "klaim veto palsu harus terdeteksi"
    assert pelanggaran_narasi(run.narrative, run) == []


def test_narasi_dari_fakta_konsisten_dengan_pelanggaran_narasi() -> None:
    run = run_review("decision-1", context=_context(), workers=_workers())
    assert narasi_dari_fakta(run) == run.narrative


# ---------------------------------------------------------------------------
# 3. Context batch sumber dilengkapi dari audit-facts (bukan ditebak)
# ---------------------------------------------------------------------------


class CaptureWorker(FixedWorker):
    def __init__(self, name: AgentName, captured: dict) -> None:
        super().__init__(name)
        self.captured = captured

    def run(self, context: WorkerContext) -> AgentFinding:
        self.captured[self.name.value] = {
            "source_batch_ids": tuple(context.source_batch_ids or ()),
            "source_location": context.source_location,
        }
        return super().run(context)


def test_context_melengkapi_batch_sumber_dari_audit_facts() -> None:
    """approval-summary pengadaan tidak membawa batch_ids → audit-facts dipakai."""
    api = ApiFakta()
    captured: dict = {}
    workers = {name: CaptureWorker(name, captured) for name in AgentName}

    run_review("decision-1", api=api, workers=workers)

    assert captured["safety"]["source_batch_ids"] == ("batch-1", "batch-2")
    assert captured["freshness"]["source_batch_ids"] == ("batch-1", "batch-2")
    assert "/decisions/decision-1/audit-facts" in api.paths


def test_context_tidak_menebak_bila_audit_facts_tidak_terbaca() -> None:
    api = ApiFakta(audit_gagal=True)
    captured: dict = {}
    workers = {name: CaptureWorker(name, captured) for name in AgentName}

    run_review("decision-1", api=api, workers=workers)

    assert captured["safety"]["source_batch_ids"] == ()
    assert captured["safety"]["source_location"] is None


# ---------------------------------------------------------------------------
# 4. Putaran bersih dengan worker NYATA berakhir tidak vetoed
# ---------------------------------------------------------------------------


def test_putaran_bersih_dengan_worker_nyata_tidak_dihukum_veto() -> None:
    """Worker safety/freshness nyata membaca batch dari fakta → tidak memblokir.

    Inilah regresi inti: context tanpa batch sumber membuat kedua guardian
    fail-closed (`batch_count=null`) lalu memveto setiap putaran demo, padahal
    fakta audit mencatat dua batch.
    """

    api = ApiFakta()
    workers = {name: FixedWorker(name) for name in AgentName if name is not AgentName.VERIFIER}
    workers[AgentName.SAFETY] = SafetyWorker()
    workers[AgentName.FRESHNESS] = FreshnessWorker()
    workers[AgentName.VERIFIER] = VerifierWorker()
    run = run_review("decision-1", api=api, workers=workers)

    safety = next(f for f in run.findings if f.agent is AgentName.SAFETY)
    freshness = next(f for f in run.findings if f.agent is AgentName.FRESHNESS)

    assert safety.facts.get("batch_count") == 2, safety.facts
    assert freshness.facts.get("batch_count") == 2, freshness.facts
    assert safety.blocking is False
    assert freshness.blocking is False
    assert run.safety_veto is False
    assert run.status != "vetoed"
    assert "memblokir" not in (run.narrative or "").lower()
