"""Registry model per agent (permintaan Roy, S3-16+).

Kontrak:
- setiap agent (supervisor/verifier/forecast) punya rantai TEPAT 3 model:
  primary + fallback_1 + fallback_2 — satu model mati, dua siap backup
- backend = sumber konfigurasi (env); frontend hanya menampilkan (display-only)
- slot AgentCore (AGENTCORE_RUNTIME_ARN) didukung eksplisit: bila terisi,
  jadi primary agent dan menggeser (bukan menambah) slot env
- prefix `cc/|cb/|cbcn/|ali/` = model Inferhub; sisanya = model Bedrock
  (inference profile us./global./qwen./deepseek.)
- env kosong → rantai kosong; pemanggil memutuskan UNAVAILABLE (jujur)
- ref tak dikenal (bukan prefix Inferhub dan bukan model Bedrock yang jelas)
  diperlakukan Bedrock — validasi final terjadi saat pemanggilan nyata
"""

from app.ai_providers.model_registry import (
    ModelRef,
    get_agent_chain,
    parse_model_ref,
)

# ---------------------------------------------------------------- parsing ref

def test_parse_bedrock_inference_profile():
    ref = parse_model_ref("us.anthropic.claude-opus-4-6-v1")
    assert ref == ModelRef(kind="bedrock", model_id="us.anthropic.claude-opus-4-6-v1")


def test_parse_inferhub_prefixed_models():
    for mid in ("cc/gpt-x", "cb/kimi-k3", "cbcn/kimi-k3", "ali/qwen3.8-max-0902"):
        ref = parse_model_ref(mid)
        assert ref is not None and ref.kind == "inferhub" and ref.model_id == mid


def test_parse_agentcore_arn():
    arn = "arn:aws:bedrock:us-west-2:123456789012:agent-runtime/abc123"
    ref = parse_model_ref(arn)
    assert ref == ModelRef(kind="agentcore", agentcore_arn=arn)


def test_parse_empty_or_blank_is_none():
    assert parse_model_ref("") is None
    assert parse_model_ref("   ") is None
    assert parse_model_ref(None) is None


# ------------------------------------------------------------- rantai 3 model

def test_verifier_chain_three_models(monkeypatch):
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_1", "cb/kimi-k3")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_2", "ali/qwen3.8-max-0902")
    chain = get_agent_chain("verifier")
    assert [r.model_id for r in chain] == [
        "us.anthropic.claude-opus-4-6-v1",
        "cb/kimi-k3",
        "ali/qwen3.8-max-0902",
    ]
    assert [r.kind for r in chain] == ["bedrock", "inferhub", "inferhub"]


def test_forecast_chain_three_models(monkeypatch):
    monkeypatch.setenv("FORECAST_MODEL", "qwen.qwen3-vl-235b-a22b")
    monkeypatch.setenv("FORECAST_MODEL_FALLBACK_1", "cbcn/kimi-k3")
    monkeypatch.setenv("FORECAST_MODEL_FALLBACK_2", "cb/kimi-k3")
    chain = get_agent_chain("forecast")
    assert len(chain) == 3
    assert chain[0].kind == "bedrock"
    assert all(r.kind == "inferhub" for r in chain[1:])


def test_supervisor_chain_three_models(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    monkeypatch.setenv("SUPERVISOR_MODEL_FALLBACK_1", "cb/kimi-k3")
    monkeypatch.setenv("SUPERVISOR_MODEL_FALLBACK_2", "cbcn/kimi-k3")
    chain = get_agent_chain("supervisor")
    assert len(chain) == 3
    assert [r.kind for r in chain] == ["bedrock", "inferhub", "inferhub"]


def test_supervisor_legacy_fallback_name_backfills_slot1(monkeypatch):
    # kompatibilitas: SUPERVISOR_MODEL_FALLBACK (tanpa angka) = fallback_1,
    # dipakai HANYA bila tidak ada slot bernomor (kontrak gap-stop baru)
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.")
    monkeypatch.setenv("SUPERVISOR_MODEL_FALLBACK", "cb/kimi-k3")
    monkeypatch.delenv("SUPERVISOR_MODEL_FALLBACK_1", raising=False)
    chain = get_agent_chain("supervisor")
    assert [r.model_id for r in chain] == ["us.anthropic.", "cb/kimi-k3"]


def test_agentcore_arn_becomes_primary_and_env_chain_kept_full(monkeypatch):
    # AgentCore terkonfigurasi → primary; slot env TIDAK dipotong (chain panjang)
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock:us-west-2:1:agent-runtime/abc",
    )
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.")
    monkeypatch.setenv("SUPERVISOR_MODEL_FALLBACK_1", "cb/kimi-k3")
    monkeypatch.setenv("SUPERVISOR_MODEL_FALLBACK_2", "cbcn/kimi-k3")
    chain = get_agent_chain("supervisor")
    assert len(chain) == 4
    assert chain[0].kind == "agentcore"
    assert chain[1] == ModelRef(kind="bedrock", model_id="us.anthropic.")
    assert chain[2].kind == "inferhub"


def test_empty_env_yields_empty_chain(monkeypatch):
    for key in (
        "VERIFIER_MODEL_PRIMARY",
        "VERIFIER_MODEL_FALLBACK_1",
        "VERIFIER_MODEL_FALLBACK_2",
    ):
        monkeypatch.delenv(key, raising=False)
    assert get_agent_chain("verifier") == []


def test_partial_env_yields_only_configured_slots(monkeypatch):
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    monkeypatch.delenv("VERIFIER_MODEL_FALLBACK_1", raising=False)
    monkeypatch.delenv("VERIFIER_MODEL_FALLBACK_2", raising=False)
    chain = get_agent_chain("verifier")
    assert [r.model_id for r in chain] == ["us.anthropic.claude-opus-4-6-v1"]


def test_unknown_agent_raises():
    import pytest

    with pytest.raises(ValueError):
        get_agent_chain("unknown_agent")
