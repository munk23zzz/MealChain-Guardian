"""Jalur review `local` (in-process) — percabangan, model, dan fail-closed.

Konteks bug yang dijaga tes ini: Demo Control memanggil runtime AgentCore lewat
`AGENTCORE_RUNTIME_ARN`. Bila image runtime tertinggal dari repo, backend
menjalankan kode LAMA: verifier `unavailable`/`degraded`, `duration_ms = 0`,
dan status run `completed` walau guardian memblokir. Mode `local` menjalankan
orkestrator YANG ADA DI REPO sehingga kode yang mengaudit = kode yang diuji.

Yang dikunci:

1. Percabangan hanya lewat nilai EKSPLISIT `local`; nilai lain (termasuk
   `advisory`, `predecision`, kosong) tetap runtime AgentCore — default aman.
2. Model verifier dipilih dari env (VERIFIER_AGENT_MODEL → VERIFIER_MODEL_PRIMARY
   → SUPERVISOR_MODEL_PRIMARY); slot AgentCore DITOLAK (auditor tidak boleh
   memakai runtime/prompt supervisor).
3. Tanpa model, audit TETAP jalan deterministik dan tidak pernah dikarang
   `consistent` (fail-closed).
4. Jalan lokal mengoper model ke `VerifierWorker` dan tidak memanggil AgentCore.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_review_client import AgentReviewResult
from app.services.agent_review_local import (
    LOCAL_MODE,
    build_model,
    mode_orkestrator,
    model_id_dari_env,
    review_decision_local,
    transport,
)
from tests.test_actions import _drop_user, _login, _mk_user
from tests.test_demo_event1_api import _fake_outcome

pytest.importorskip("agent")


# ---------------------------------------------------------------------------
# 1. Percabangan
# ---------------------------------------------------------------------------


def test_transport_hanya_local_yang_eksplisit() -> None:
    assert transport("local") == "local"
    assert transport("  LOCAL ") == "local"
    assert transport(LOCAL_MODE) == "local"


@pytest.mark.parametrize("nilai", ["advisory", "predecision", "agentcore", "", None, "lain"])
def test_transport_selain_local_tetap_agentcore(nilai) -> None:
    """Default AMAN: tidak ada yang pindah jalur tanpa keputusan operator."""
    assert transport(nilai) == "agentcore"


def test_mode_orkestrator_tidak_meneruskan_local() -> None:
    assert mode_orkestrator("local") == "advisory"
    assert mode_orkestrator("predecision") == "predecision"
    assert mode_orkestrator("advisory") == "advisory"


# ---------------------------------------------------------------------------
# 2. Model verifier
# ---------------------------------------------------------------------------


def test_model_id_memilih_env_paling_eksplisit(monkeypatch) -> None:
    monkeypatch.setenv("VERIFIER_AGENT_MODEL", "sap-ai-core:llm")
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "cc/lain")
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "cb/lain-lagi")
    assert model_id_dari_env() == ("sap-ai-core:llm", "VERIFIER_AGENT_MODEL")


def test_model_id_cadangan_ke_rantai_verifier_lalu_supervisor(monkeypatch) -> None:
    monkeypatch.delenv("VERIFIER_AGENT_MODEL", raising=False)
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "sap-ai-core:llm")
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "cb/supervisor")
    assert model_id_dari_env() == ("sap-ai-core:llm", "VERIFIER_MODEL_PRIMARY")

    monkeypatch.delenv("VERIFIER_MODEL_PRIMARY", raising=False)
    assert model_id_dari_env() == ("cb/supervisor", "SUPERVISOR_MODEL_PRIMARY")


def test_tanpa_env_model_hasilnya_none_dengan_alasan(monkeypatch) -> None:
    for kunci in (
        "VERIFIER_AGENT_MODEL",
        "VERIFIER_MODEL_PRIMARY",
        "SUPERVISOR_MODEL_PRIMARY",
    ):
        monkeypatch.delenv(kunci, raising=False)
    model, alasan = build_model()
    assert model is None
    assert alasan and "tidak dikonfigurasi" in alasan


def test_arn_agentcore_ditolak_sebagai_model_verifier(monkeypatch) -> None:
    """Auditor tidak boleh memakai runtime agent supervisor (independensi)."""
    monkeypatch.setenv(
        "VERIFIER_AGENT_MODEL",
        "arn:aws:bedrock-agentcore:us-west-2:1:runtime/supervisor",
    )
    model, alasan = build_model()
    assert model is None
    assert alasan and "AgentCore" in alasan


def test_model_sap_ai_core_dibangun_lewat_pintu_publik(monkeypatch) -> None:
    monkeypatch.setenv("VERIFIER_AGENT_MODEL", "sap-ai-core:llm")
    dipakai: list = []

    def _fake_build(ref):
        dipakai.append(ref)
        return lambda prompt: "{}"

    monkeypatch.setattr(
        "app.ai_providers.ai_provider_chain.build_caller_for_ref", _fake_build
    )
    model, alasan = build_model()
    assert alasan is None
    assert callable(model)
    assert dipakai and dipakai[0].kind == "sap_ai_core"
    assert dipakai[0].model_id == "llm"


# ---------------------------------------------------------------------------
# 3. Jalan lokal: model dioper, hasil dipetakan, tidak menyentuh AgentCore
# ---------------------------------------------------------------------------


class _RunPalsu:
    class _Status:
        value = "vetoed"

    status = _Status()
    run_id = uuid4()

    def model_dump(self, mode: str = "json") -> dict:
        return {"status": "vetoed", "findings": [{} for _ in range(7)]}


def test_tanpa_token_gagal_tertutup_tanpa_memanggil_apa_pun(monkeypatch) -> None:
    def _tak_boleh(*args, **kwargs):
        raise AssertionError("orkestrator tidak boleh dipanggil tanpa token")

    monkeypatch.setattr("agent.orchestrator.run_review", _tak_boleh)
    hasil = review_decision_local("decision-1", token="   ")
    assert hasil.status == "unavailable"
    assert hasil.error and "token" in hasil.error
    assert hasil.completed is False


def test_jalan_lokal_mengoper_model_ke_verifier_dan_memetakan_status(
    monkeypatch,
) -> None:
    ditangkap: dict = {}

    def _fake_review(
        decision_id, *, api, workers, timeout_seconds, mode, narrator=None
    ):
        ditangkap.update(
            decision_id=decision_id,
            workers=workers,
            timeout_seconds=timeout_seconds,
            mode=mode,
            base_url=api.base_url,
            narrator=narrator,
        )
        return _RunPalsu()

    monkeypatch.setattr("agent.orchestrator.run_review", _fake_review)
    monkeypatch.setattr(
        "agent.telemetry.build_trace_rows",
        lambda run: [{"step_name": "VERIFY", "agent_name": "verifier"}],
    )

    model_palsu = lambda prompt: "{}"  # noqa: E731
    hasil = review_decision_local(
        "decision-1",
        token="token-uji",
        api_url="http://127.0.0.1:8000",
        model=model_palsu,
        timeout_seconds=45,
    )

    assert hasil.status == "vetoed"
    assert hasil.run_id == str(_RunPalsu.run_id)
    assert hasil.payload is not None
    assert hasil.payload["trace_rows"] == [
        {"step_name": "VERIFY", "agent_name": "verifier"}
    ]
    # Model yang disuntikkan benar-benar dipakai auditor, bukan worker lain.
    verifier = ditangkap["workers"]["verifier"]
    assert verifier.model is model_palsu
    assert ditangkap["mode"] == "advisory"
    assert ditangkap["base_url"] == "http://127.0.0.1:8000"
    assert ditangkap["decision_id"] == "decision-1"
    # Agent ke-9 (supervisor) PUNYA jalur narasi: `narrator` selalu diteruskan
    # (None hanya bila tidak ada model yang bisa dipanggil).
    assert "narrator" in ditangkap


def test_api_lokal_menghormati_env_dan_tidak_memakai_url_tunnel(monkeypatch) -> None:
    """Review lokal harus membaca backend LOKAL, bukan tunnel milik runtime."""
    ditangkap: dict = {}

    def _fake_review(
        decision_id, *, api, workers, timeout_seconds, mode, narrator=None
    ):
        ditangkap["base_url"] = api.base_url
        ditangkap["narrator"] = narrator
        return _RunPalsu()

    monkeypatch.setattr("agent.orchestrator.run_review", _fake_review)
    monkeypatch.setattr("agent.telemetry.build_trace_rows", lambda run: [])
    monkeypatch.setenv("AGENT_LOCAL_API_URL", "http://127.0.0.1:8001")

    review_decision_local("decision-1", token="t", model=lambda prompt: "{}")
    assert ditangkap["base_url"] == "http://127.0.0.1:8001"


# ---------------------------------------------------------------------------
# 4. Fail-closed pada level verifier (tanpa model → bukan `consistent`)
# ---------------------------------------------------------------------------


def test_verifier_tanpa_model_tidak_pernah_consistent() -> None:
    from agent.contracts import AgentRun, RunStatus, VerifyResult
    from agent.workers import build_stub_findings
    from agent.workers.verifier import VerifierWorker

    from tests.test_agent_verifier import FAKTA_KONSISTEN

    run_id = uuid4()
    run = AgentRun(
        run_id=run_id,
        decision_id="decision-1",
        mode="advisory",
        status=RunStatus.COMPLETED,
        findings=build_stub_findings(run_id, "decision-1"),
        contradictions=[],
        safety_veto=False,
        narrative="Review selesai tanpa kontradiksi.",
        total_latency_ms=5,
        verification=VerifyResult(verdict="pass", reasons=[]),
    )

    temuan = VerifierWorker(model=None).audit(
        run, fakta=dict(FAKTA_KONSISTEN), run_id=uuid4()
    )

    assert temuan.facts["audit_verdict"] == "unavailable"
    assert temuan.facts["model_verdict"] is None
    assert temuan.facts["checks_total"] >= 1
    assert temuan.latency_ms and temuan.latency_ms > 0


# ---------------------------------------------------------------------------
# 5. Endpoint Demo Control memilih jalur lokal
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pemakai():
    dibuat: list[str] = []

    def _buat(role: str, lokasi: str | None):
        user = _mk_user(role, lokasi)
        dibuat.append(user["email"])
        return user

    yield _buat
    for email in dibuat:
        _drop_user(email)


def test_endpoint_demo_memakai_jalur_lokal_saat_mode_local(
    client, monkeypatch, pemakai
) -> None:
    dipanggil: dict = {}

    def _fake_local(decision_id, *, token, mode, timeout_seconds):
        dipanggil.update(
            decision_id=decision_id,
            token=token,
            mode=mode,
            timeout_seconds=timeout_seconds,
        )
        return AgentReviewResult(status="unavailable", error="uji jalur lokal")

    def _agentcore_tak_boleh(*args, **kwargs):
        raise AssertionError("jalur AgentCore tidak boleh dipakai saat mode=local")

    monkeypatch.setattr(
        "app.api.demo.run_event1",
        lambda commodity, target_location, **kwargs: _fake_outcome(
            commodity=commodity
        ),
    )
    monkeypatch.setattr(
        "app.services.agent_review_local.review_decision_local", _fake_local
    )
    monkeypatch.setattr("app.api.demo.review_decision", _agentcore_tak_boleh)
    monkeypatch.setattr("app.api.demo.settings.multi_agent_review", True)
    monkeypatch.setattr("app.api.demo.settings.agent_review_mode", "local")
    monkeypatch.setattr("app.api.demo.settings.agent_review_timeout_seconds", 75)

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["agent_review"]["status"] == "unavailable"
    assert dipanggil["decision_id"] == "00000000-0000-0000-0000-000000000001"
    assert dipanggil["mode"] == "local"
    assert dipanggil["timeout_seconds"] == 75
    # Token dibuat untuk PEMANGGIL (bukan token layanan), supaya cakupan peran
    # tetap ditegakkan endpoint yang dibaca worker.
    assert dipanggil["token"]


def test_endpoint_demo_tetap_agentcore_untuk_mode_lama(
    client, monkeypatch, pemakai
) -> None:
    dipanggil: dict = {}

    def _fake_agentcore(decision_id, *, timeout_seconds):
        dipanggil["timeout_seconds"] = timeout_seconds
        return AgentReviewResult(status="unavailable", error="ARN kosong")

    def _lokal_tak_boleh(*args, **kwargs):
        raise AssertionError("jalur lokal tidak boleh dipakai tanpa mode=local")

    monkeypatch.setattr(
        "app.api.demo.run_event1",
        lambda commodity, target_location, **kwargs: _fake_outcome(
            commodity=commodity
        ),
    )
    monkeypatch.setattr("app.api.demo.review_decision", _fake_agentcore)
    monkeypatch.setattr(
        "app.services.agent_review_local.review_decision_local", _lokal_tak_boleh
    )
    monkeypatch.setattr("app.api.demo.settings.multi_agent_review", True)
    monkeypatch.setattr("app.api.demo.settings.agent_review_mode", "advisory")
    monkeypatch.setattr("app.api.demo.settings.agent_review_timeout_seconds", 75)

    head = pemakai("sppg_head", "Jakarta")
    headers = _login(client, head)
    resp = client.post(
        "/demo/event1",
        json={"commodity": "telur", "target_location": "Jakarta"},
        headers=headers,
    )

    assert resp.status_code == 201, resp.text
    assert dipanggil["timeout_seconds"] == 45.0
