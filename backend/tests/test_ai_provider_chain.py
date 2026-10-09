"""Chain default per agent dari registry env (permintaan Roy).

Kontrak:
- build_default_callers(agent) → list[(label_slot, callable, kind)] dari env;
  label jujur `primary:bedrock`, `fallback_1:inferhub`, dst.
- ARN AgentCore → caller stub yang melempar NotImplementedError eksplisit
  (honest-unavailable sampai AgentCore benar-benar disiapkan)
- run_verifier / run_forecast tanpa argumen provider → memakai default env;
  env kosong → perilaku lama (UNAVAILABLE / statistical fallback)
- label provider hasil = label slot pemenang (bukan asumsi posisi)
"""

import pytest

from app.ai_providers import ai_provider_chain as chain_mod
from app.ai_providers.ai_provider_chain import build_default_callers


def _strip_model_env(monkeypatch):
    for key in (
        "AGENTCORE_RUNTIME_ARN",
        "SUPERVISOR_MODEL_PRIMARY",
        "SUPERVISOR_MODEL_FALLBACK",
        "SUPERVISOR_MODEL_FALLBACK_1",
        "SUPERVISOR_MODEL_FALLBACK_2",
        "VERIFIER_MODEL_PRIMARY",
        "VERIFIER_MODEL_FALLBACK_1",
        "VERIFIER_MODEL_FALLBACK_2",
        "FORECAST_MODEL",
        "FORECAST_MODEL_FALLBACK_1",
        "FORECAST_MODEL_FALLBACK_2",
        "INFERHUB_URL",
        "INFERHUB_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_empty_env_yields_no_callers(monkeypatch):
    _strip_model_env(monkeypatch)
    assert build_default_callers("verifier") == []
    assert build_default_callers("forecast") == []


def test_verifier_default_chain_labels_and_kinds(monkeypatch):
    _strip_model_env(monkeypatch)
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_1", "cb/kimi-k3")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_2", "ali/qwen3.8-max-0902")
    chain = build_default_callers("verifier")
    assert [label for label, _, _ in chain] == [
        "primary:bedrock",
        "fallback_1:inferhub",
        "fallback_2:inferhub",
    ]
    assert all(callable(fn) for _, fn, _ in chain)


def test_agentcore_slot_builds_real_runtime_caller(monkeypatch):
    """Kontrak O-AI (S4-00): ARN terpasang → caller runtime NYATA, bukan stub.

    Stub NotImplementedError digantikan invoke_agent_runtime sungguhan;
    tanpa kredensial/jaringan, pemanggilan gagal eksplisit via error class
    AgentCoreInvocationError (chain lanjut slot berikutnya) — bukan
    NotImplementedError "belum diimplementasi".
    """
    _strip_model_env(monkeypatch)
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock:us-west-2:1:agent-runtime/abc",
    )
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.")
    chain = build_default_callers("supervisor")
    assert chain[0][0] == "primary:agentcore"
    from app.ai_providers.agentcore_caller import (
        AgentCoreInvocationError,
        is_agentcore_caller,
    )

    caller = chain[0][1]
    assert is_agentcore_caller(caller)
    with pytest.raises(AgentCoreInvocationError) as excinfo:
        caller("prompt apa pun")  # tanpa kredensial AWS di env test
    assert "NotImplementedError" not in str(excinfo.value)


def test_unknown_agent_raises(monkeypatch):
    _strip_model_env(monkeypatch)
    with pytest.raises(ValueError):
        build_default_callers("tidak_ada")


# ------------------------------------------------- integrasi verifier/forecast


def test_run_verifier_uses_env_default_chain(monkeypatch):
    _strip_model_env(monkeypatch)
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_1", "cb/kimi-k3")

    def stub_caller(prompt: str) -> str:
        return '{"verdict": "CONSISTENT", "reason": "stub"}'

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: [("primary:bedrock", stub_caller, "bedrock")],
    )
    from app.ai_providers.verifier_client import run_verifier

    result = run_verifier({"safety_status": "PASS"})
    assert result.verdict == "CONSISTENT"
    assert result.provider == "primary:bedrock"
    assert result.fallback_used is False


def test_run_forecast_uses_env_default_chain(monkeypatch):
    _strip_model_env(monkeypatch)
    monkeypatch.setenv("FORECAST_MODEL", "qwen.qwen3-vl-235b-a22b")
    monkeypatch.setenv("FORECAST_MODEL_FALLBACK_1", "cbcn/kimi-k3")

    def dead_primary(prompt: str) -> str:
        raise RuntimeError("primary mati")

    def good_fallback(prompt: str) -> str:
        return '{"forecast_qty_kg": 123.5, "confidence": 0.8}'

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: [
            ("primary:bedrock", dead_primary, "bedrock"),
            ("fallback_1:inferhub", good_fallback, "inferhub"),
        ],
    )
    from app.ai_providers.forecast_client import run_forecast

    result = run_forecast([100.0, 120.0, 90.0], horizon_days=7)
    assert result.forecast_qty_kg == 123.5
    assert result.method == "provider_forecast"  # bukan SAP, bukan statistik
    assert result.provider == "fallback_1:inferhub"
    assert result.fallback_used is True
    assert len(result.attempts) == 2


def test_run_forecast_unparseable_success_falls_back_to_statistical(monkeypatch):
    _strip_model_env(monkeypatch)
    monkeypatch.setenv("FORECAST_MODEL", "qwen.qwen3-vl-235b-a22b")

    def garbage_success(prompt: str) -> str:
        return "bukan json"

    monkeypatch.setattr(
        chain_mod,
        "build_default_callers",
        lambda agent: [("primary:bedrock", garbage_success, "bedrock")],
    )
    from app.ai_providers.forecast_client import run_forecast

    result = run_forecast([100.0, 120.0, 90.0], horizon_days=7)
    assert result.method == "statistical_fallback"
    assert result.fallback_used is True
    assert len(result.attempts) == 1  # jejak attempt model tetap tercatat


def test_forecast_parses_daily_array_shape(monkeypatch):
    """Bentuk jawaban model nyata (probe 2026-10-06): array harian + mean."""
    from app.ai_providers.forecast_client import _parse_forecast_response

    raw = (
        '{"forecast": [315.0, 318.0, 320.0, 322.0, 325.0, 328.0, 330.0], '
        '"confidence": 0.85}'
    )
    parsed = _parse_forecast_response(raw, 7)
    assert parsed is not None
    qty, confidence = parsed
    # total = mean harian × horizon = (sum 7 hari / 7) × 7 = 2258.0
    assert abs(qty - 2258.0) < 1e-6
    assert confidence == 0.85


def test_forecast_prompt_contains_output_contract(monkeypatch):
    """Prompt WAJIB mengajarkan format jawaban (akar bug demo live)."""
    from app.ai_providers.forecast_client import _build_prompt

    prompt = _build_prompt([300.0, 320.0, 310.0], 7)
    assert "forecast_qty_kg" in prompt
    assert "horizon_days" in prompt
    assert "JSON" in prompt


def test_run_verifier_empty_env_still_unavailable(monkeypatch):
    _strip_model_env(monkeypatch)
    from app.ai_providers.verifier_client import run_verifier

    result = run_verifier({"safety_status": "PASS"})
    assert result.verdict == "UNAVAILABLE"
    assert result.attempts == []
