"""Tujuh worker sebagai AGENT: lapisan penalaran model di atas fakta deterministik.

Kontrak yang dikunci berkas ini (TDD, 27 Okt 2026):

1. Mode `off` (default) → model tidak pernah dipanggil; perilaku lama utuh.
2. Mode `advisory` + model tersedia → ringkasan boleh diperkaya model, tetapi
   **status dan `blocking` tetap milik pemeriksa deterministik**.
3. Model tidak boleh menambah angka yang tidak ada di fakta (anti-karang).
4. Model gagal / JSON rusak / mencoba melonggarkan blokir → temuan deterministik
   dipertahankan, alasannya dicatat sebagai warning.
5. Ketujuh worker (supply, demand, freshness, safety, price, logistics, evidence)
   benar-benar melewati lapisan ini dan punya prompt sendiri.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from agent.contracts import AgentFinding, AgentName, WorkerStatus
from agent.workers import base as worker_base
from agent.workers.reasoner import (
    PromptWorker,
    mode_dari_env,
    reasoner_dari_env,
    terapkan_penalaran,
)

TUJUH_WORKER = (
    AgentName.SUPPLY,
    AgentName.DEMAND,
    AgentName.FRESHNESS,
    AgentName.SAFETY,
    AgentName.PRICE,
    AgentName.LOGISTICS,
    AgentName.EVIDENCE,
)


def _temuan(
    *,
    status: WorkerStatus = WorkerStatus.OK,
    blocking: bool = False,
    summary: str = "3 batch sumber: 2 pass, 1 pending.",
    facts: dict | None = None,
) -> AgentFinding:
    from agent.contracts import Citation

    fakta = facts if facts is not None else {"batch_count": 3, "pass_count": 2}
    sitasi = [
        Citation(
            claim=kunci,
            source_path="/batches",
            source_field="batches[].safety_status (count)",
            source_value=nilai,
        )
        for kunci, nilai in fakta.items()
        if isinstance(nilai, int)
    ]
    return AgentFinding(
        agent=AgentName.SAFETY,
        stage="DETECT",
        status=status,
        summary=summary,
        facts=fakta,
        citations=sitasi,
        confidence=None,
        warnings=[],
        blocking=blocking,
        latency_ms=7,
    )


class ModelPalsu:
    """Callable model yang mencatat prompt dan mengembalikan jawaban tetap."""

    def __init__(self, jawaban: str | Exception) -> None:
        self.jawaban = jawaban
        self.prompt: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompt.append(prompt)
        if isinstance(self.jawaban, Exception):
            raise self.jawaban
        return self.jawaban


def test_mode_default_off_dan_tidak_memanggil_model(monkeypatch):
    monkeypatch.delenv("WORKER_AGENT_MODE", raising=False)
    model = ModelPalsu('{"summary": "diperkaya model"}')

    hasil = terapkan_penalaran(
        _temuan(),
        prompt="prompt",
        mode=mode_dari_env(),
        model=model,
        role="Safety Agent",
    )

    assert mode_dari_env() == "off"
    assert model.prompt == []
    assert hasil.summary == _temuan().summary
    assert hasil.facts["reasoning"]["status"] == "off"


def test_mode_advisory_memperkaya_ringkasan_tanpa_mengubah_status():
    blocking = _temuan(status=WorkerStatus.DEGRADED, blocking=True)
    model = ModelPalsu(
        json.dumps(
            {
                "summary": "Bukti batch sumber belum lengkap; perlu verifikasi manusia.",
                "rationale": "satu batch berstatus pending dan exclusion belum terbaca",
            }
        )
    )

    hasil = terapkan_penalaran(
        blocking,
        prompt="prompt",
        mode="advisory",
        model=model,
        role="Safety Agent",
    )

    assert hasil.summary != blocking.summary
    assert hasil.status is blocking.status
    assert hasil.blocking is True
    assert hasil.facts["reasoning"]["status"] == "applied"
    assert hasil.facts["reasoning"]["rationale"].startswith("satu batch")


def test_model_tidak_boleh_menambah_angka_yang_tidak_ada_di_fakta():
    asli = _temuan(facts={"batch_count": 3, "pass_count": 2})
    model = ModelPalsu(json.dumps({"summary": "Ada 9 batch bermasalah di lokasi ini."}))

    hasil = terapkan_penalaran(asli, prompt="p", mode="advisory", model=model, role="Safety Agent")

    assert hasil.summary == asli.summary
    assert hasil.facts["reasoning"]["status"] == "rejected"
    assert any("angka" in w for w in hasil.warnings)


def test_model_tidak_boleh_melonggarkan_blokir():
    asli = _temuan(status=WorkerStatus.DEGRADED, blocking=True)
    model = ModelPalsu(json.dumps({"summary": "Semua aman.", "blocking": False, "status": "ok"}))

    hasil = terapkan_penalaran(asli, prompt="p", mode="advisory", model=model, role="Safety Agent")

    assert hasil.blocking is True
    assert hasil.status is WorkerStatus.DEGRADED
    assert hasil.facts["reasoning"]["status"] == "guarded"
    assert any("blokir" in w for w in hasil.warnings)


def test_model_gagal_temuan_deterministik_dipertahankan():
    asli = _temuan()
    model = ModelPalsu(RuntimeError("provider mati"))

    hasil = terapkan_penalaran(asli, prompt="p", mode="advisory", model=model, role="Safety Agent")

    assert hasil.summary == asli.summary
    assert hasil.status is asli.status
    assert hasil.facts["reasoning"]["status"] == "unavailable"
    assert any("model" in w for w in hasil.warnings)


def test_json_rusak_tidak_mengganti_ringkasan():
    asli = _temuan()
    model = ModelPalsu("ini bukan json")

    hasil = terapkan_penalaran(asli, prompt="p", mode="advisory", model=model, role="Safety Agent")

    assert hasil.summary == asli.summary
    assert hasil.facts["reasoning"]["status"] == "invalid"


def test_temuan_error_tidak_dinilai_model():
    """Temuan ERROR = fakta tidak terbaca; model tidak boleh menempelkan penalaran."""
    dipanggil = {"n": 0}

    def model(prompt):
        dipanggil["n"] += 1
        return '{"summary": "seharusnya tidak dipanggil"}'

    temuan = _temuan(status=WorkerStatus.ERROR, blocking=True, facts={})
    hasil = terapkan_penalaran(
        temuan, prompt="p", mode="advisory", model=model, role="Safety Agent"
    )

    assert hasil is temuan
    assert "reasoning" not in hasil.facts
    assert dipanggil["n"] == 0


def test_hasil_penalaran_lolos_validasi_kontrak_agent_finding():
    """Temuan hasil penalaran harus tetap sah menurut kontrak AgentFinding.

    Kontrak menuntut SETIAP angka di `facts` punya sitasi. Metadata penalaran
    (latensi model) bukan fakta yang disitasi, jadi ia tidak boleh berupa angka
    telanjang — kalau lolos ke sini, seluruh AgentRun gagal validasi dan review
    7 worker mati dengan `agent_review.status="failed"`.
    """
    model = ModelPalsu(
        json.dumps({"summary": "Bukti batch sumber lengkap; tidak ada yang perlu ditahan."})
    )

    hasil = terapkan_penalaran(
        _temuan(), prompt="p", mode="advisory", model=model, role="Safety Agent"
    )

    # Validasi ulang dari dump (model_copy tidak menjalankan validator).
    AgentFinding.model_validate(hasil.model_dump())

    def _angka(obj):
        if isinstance(obj, bool):
            return []
        if isinstance(obj, (int, float)):
            return [obj]
        if isinstance(obj, dict):
            return [n for v in obj.values() for n in _angka(v)]
        if isinstance(obj, list):
            return [n for v in obj for n in _angka(v)]
        return []

    assert _angka(hasil.facts["reasoning"]) == []


def test_verifier_tidak_meminjam_model_supervisor_atau_worker(monkeypatch):
    """Independensi model: tiap agent hanya memakai kuncinya sendiri.

    Cadangan lintas-agent berbahaya — verifier sempat ikut memakai
    `SUPERVISOR_MODEL_PRIMARY` tanpa ada yang memintanya, sehingga audit model
    hidup diam-diam dan memveto setiap putaran demo. Verifier adalah pemeriksa
    independen: ia hanya boleh menalar bila `VERIFIER_AGENT_MODEL` diset eksplisit.
    """
    monkeypatch.setenv("WORKER_AGENT_MODE", "advisory")
    monkeypatch.setenv("WORKER_AGENT_MODEL", "sap-ai-core:llm")
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "sap-ai-core:llm")
    monkeypatch.delenv("VERIFIER_AGENT_MODEL", raising=False)

    assert reasoner_dari_env(agent="verifier") is None
    assert reasoner_dari_env(agent="supply") is not None


def test_worker_tidak_meminjam_model_verifier(monkeypatch):
    monkeypatch.setenv("WORKER_AGENT_MODE", "advisory")
    monkeypatch.setenv("VERIFIER_AGENT_MODEL", "sap-ai-core:llm")
    monkeypatch.delenv("WORKER_AGENT_MODEL", raising=False)

    assert reasoner_dari_env(agent="safety") is None


def test_supervisor_memakai_kuncinya_sendiri(monkeypatch):
    monkeypatch.setenv("WORKER_AGENT_MODE", "advisory")
    monkeypatch.setenv("WORKER_AGENT_MODEL", "sap-ai-core:llm")
    monkeypatch.delenv("SUPERVISOR_MODEL_PRIMARY", raising=False)

    assert reasoner_dari_env(agent="supervisor") is None


def test_reasoner_dari_env_none_tanpa_model_id(monkeypatch):
    monkeypatch.delenv("WORKER_AGENT_MODEL", raising=False)
    monkeypatch.delenv("VERIFIER_AGENT_MODEL", raising=False)
    monkeypatch.delenv("SUPERVISOR_MODEL_PRIMARY", raising=False)

    assert reasoner_dari_env() is None


@pytest.mark.parametrize("nama", TUJUH_WORKER)
def test_setiap_worker_punya_prompt_dan_lapisan_penalaran(nama, monkeypatch):
    """Ketujuh worker harus benar-benar lewat lapisan ini, bukan hanya 1-2."""
    import importlib

    modul = importlib.import_module(f"agent.workers.{nama.value}")
    kelas = next(
        obj
        for obj in vars(modul).values()
        if isinstance(obj, type)
        and issubclass(obj, worker_base.ReadOnlyWorker)
        and getattr(obj, "name", None) == nama
    )

    assert callable(getattr(kelas, "_run_deterministik", None)), (
        f"{nama.value} belum memisahkan jalur deterministik"
    )
    assert kelas.run is worker_base.ReadOnlyWorker.run, (
        f"{nama.value} memakai run sendiri sehingga melewati penalaran model"
    )

    prompt = PromptWorker.muat_prompt(nama)
    assert nama.value in prompt.lower() or "agent" in prompt.lower()
    assert len(prompt) > 200


def test_prompt_worker_memuat_fakta_tanpa_kredensial():
    prompt = PromptWorker.bangun_prompt(
        AgentName.PRICE,
        facts={"unit_price": Decimal("12500.50"), "sample_count": 4},
        summary="harga 12.500,50 dari 4 sampel",
    )

    assert "12500.50" in prompt or "12.500,50" in prompt
    assert "sample_count" in prompt
    # Tidak ada nilai rahasia yang ikut ke prompt.
    for terlarang in ("bearer ", "demo_password", "api_key=", "password="):
        assert terlarang not in prompt.lower()
