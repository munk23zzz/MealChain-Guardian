"""Kontrak runtime: task review_decision mengembalikan JSON AgentRun.

SDK AgentCore/Strands di-inject palsu supaya tes tidak butuh paket runtime;
yang diuji adalah cabang payload, bukan model.
"""

from __future__ import annotations

import json
import sys
import types
from uuid import uuid4

from agent.contracts import AgentRun, RunStatus
from agent.workers import build_stub_findings


def _pasang_sdk_palsu(monkeypatch) -> None:
    agentcore = types.ModuleType("bedrock_agentcore")
    agentcore.__path__ = []  # type: ignore[attr-defined]
    runtime = types.ModuleType("bedrock_agentcore.runtime")

    class FakeApp:
        def entrypoint(self, fn):
            return fn

        def run(self):
            return None

    runtime.BedrockAgentCoreApp = FakeApp  # type: ignore[attr-defined]
    agentcore.runtime = runtime  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bedrock_agentcore", agentcore)
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.runtime", runtime)

    strands = types.ModuleType("strands")
    models = types.ModuleType("strands.models")

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __call__(self, prompt):
            return "fake"

    class FakeBedrockModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    strands.Agent = FakeAgent  # type: ignore[attr-defined]
    strands.models = models  # type: ignore[attr-defined]
    strands.tool = lambda fn: fn  # type: ignore[attr-defined]
    models.BedrockModel = FakeBedrockModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "strands", strands)
    monkeypatch.setitem(sys.modules, "strands.models", models)
    sys.modules.pop("agent.runtime_server", None)


def test_runtime_task_review_decision(monkeypatch) -> None:
    _pasang_sdk_palsu(monkeypatch)
    from agent import runtime_server

    run_id = uuid4()
    findings = build_stub_findings(run_id, "decision-1")
    run = AgentRun(
        run_id=run_id,
        decision_id="decision-1",
        mode="advisory",
        status=RunStatus.PARTIAL,
        findings=findings,
        safety_veto=False,
        narrative="review uji",
    )
    monkeypatch.setattr(runtime_server, "run_review", lambda decision_id: run)

    result = runtime_server.invoke(
        {"task": "review_decision", "decision_id": "decision-1"}
    )

    payload = json.loads(result["response"])
    assert payload["run_id"] == str(run_id)
    assert payload["status"] == "partial"
    assert len(payload["findings"]) == 7
    assert len(payload["trace_rows"]) == 8
    assert payload["trace_rows"][-1]["step_name"] == "SUPERVISE"
    sys.modules.pop("agent.runtime_server", None)


def test_runtime_tanpa_decision_id_tidak_memanggil_review(monkeypatch) -> None:
    _pasang_sdk_palsu(monkeypatch)
    from agent import runtime_server

    def _boom(decision_id):
        raise AssertionError("run_review tidak boleh dipanggil tanpa decision_id")

    monkeypatch.setattr(runtime_server, "run_review", _boom)

    result = runtime_server.invoke({"task": "review_decision"})

    payload = json.loads(result["response"])
    assert payload["status"] == "failed"
    sys.modules.pop("agent.runtime_server", None)
