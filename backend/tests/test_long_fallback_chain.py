"""Chain panjang per agent (permintaan Roy, 2026-10-06 — pasca model chain 3).

Kontrak baru:
- rantai agent = SATU model per slot env yang terisi, TANPA batas 3 slot
  (fallback_1..fallback_9); AgentCore ARN (bila terisi) tetap primary.
- with_fallback_chain menerima `fallbacks: list` untuk chain panjang; kwargs
  fallback_1..3 tetap didukung (kompatibilitas lama).
- label slot konsisten: `primary`, `fallback_1` .. `fallback_N` (build
  default callers mengikuti panjang chain).
- isolasi env unit test mencakup fallback_3..9 (tanpa bocor env live).
"""

from app.ai_providers.ai_provider_chain import build_default_callers
from app.ai_providers.model_registry import get_agent_chain

# ------------------------------------------------------- registry tanpa cap 3

def test_chain_reads_all_numbered_fallback_slots(monkeypatch):
    for i, mid in enumerate(
        [
            "cb/kimi-k3",
            "ali/qwen3.8-max-0902",
            "cbcn/kimi-k3",
            "cb/gpt-6-astra",
            "cc/claude-sonnet-5",
        ],
        start=1,
    ):
        monkeypatch.setenv(f"VERIFIER_MODEL_FALLBACK_{i}", mid)
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    chain = get_agent_chain("verifier")
    assert len(chain) == 6
    assert [r.model_id for r in chain] == [
        "us.anthropic.claude-opus-4-6-v1",
        "cb/kimi-k3",
        "ali/qwen3.8-max-0902",
        "cbcn/kimi-k3",
        "cb/gpt-6-astra",
        "cc/claude-sonnet-5",
    ]


def test_chain_recognizes_cx_prefix_as_inferhub(monkeypatch):
    # cx/ adalah prefix Inferhub valid (probe 2026-10-07: cx/gpt-6-astra &
    # cx/gpt-6.1-sol LIVE 'pong') — sebelumnya salah diklasifikasi bedrock
    # karena INFERHUB_PREFIXES tidak memuat cx/.
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_1", "cx/gpt-6-astra")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_2", "cx/gpt-6.1-sol")
    chain = get_agent_chain("verifier")
    assert [r.kind for r in chain] == ["inferhub", "inferhub"]
    assert [r.model_id for r in chain] == ["cx/gpt-6-astra", "cx/gpt-6.1-sol"]


def test_chain_gap_in_numbering_stops_collection(monkeypatch):
    # gap (fallback_2 kosong) menghentikan koleksi — slot setelah gap diabaikan
    monkeypatch.setenv("VERIFIER_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_1", "cb/kimi-k3")
    monkeypatch.delenv("VERIFIER_MODEL_FALLBACK_2", raising=False)
    monkeypatch.setenv("VERIFIER_MODEL_FALLBACK_3", "cbcn/kimi-k3")
    chain = get_agent_chain("verifier")
    assert [r.model_id for r in chain] == [
        "us.anthropic.claude-opus-4-6-v1",
        "cb/kimi-k3",
    ]


def test_agentcore_arn_prepends_and_env_chain_kept_full(monkeypatch):
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN", "arn:aws:bedrock:us-west-2:1:agent-runtime/abc")
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.claude-opus-4-6-v1")
    for i, mid in enumerate(["cb/kimi-k3", "ali/qwen3.8-max-0902"], start=1):
        monkeypatch.setenv(f"SUPERVISOR_MODEL_FALLBACK_{i}", mid)
    chain = get_agent_chain("supervisor")
    assert [r.kind for r in chain] == ["agentcore", "bedrock", "inferhub", "inferhub"]


# ----------------------------------------------------- with_fallback_chain panjang

def test_with_fallback_chain_accepts_fallbacks_list():
    from app.ai_providers.resilience import with_fallback_chain

    def ok(text: str) -> str:
        return "fine"

    def boom(text: str) -> str:
        raise RuntimeError("mati")

    result = with_fallback_chain(
        primary=boom,
        prompt="p",
        fallbacks=[boom, ok, boom],
    )
    assert result.text == "fine"
    assert result.provider == "fallback_2"
    assert result.fallback_used is True
    assert [a.name for a in result.attempts] == [
        "primary",
        "fallback_1",
        "fallback_2",
    ]


def test_with_fallback_chain_legacy_kwargs_still_work():
    from app.ai_providers.resilience import with_fallback_chain

    def ok(text: str) -> str:
        return "legacy"

    result = with_fallback_chain(primary=ok, prompt="p")
    assert result.provider == "primary"
    assert result.fallback_used is False


# ------------------------------------------------------- label slot dinamis

def test_build_default_callers_labels_follow_chain_length(monkeypatch):
    monkeypatch.setenv("FORECAST_MODEL", "qwen.qwen3-vl-235b-a22b")
    for i, mid in enumerate(["cbcn/kimi-k3", "cb/kimi-k3", "cb/gpt-6-astra"], start=1):
        monkeypatch.setenv(f"FORECAST_MODEL_FALLBACK_{i}", mid)
    callers = build_default_callers("forecast")
    assert [label for label, _fn, _kind in callers] == [
        "primary:bedrock",
        "fallback_1:inferhub",
        "fallback_2:inferhub",
        "fallback_3:inferhub",
    ]


def test_conftest_isolation_covers_fallback_3_to_9(monkeypatch):
    # simulasikan fixture isolation: setelah strip, slot 3..9 harus kosong
    for i in range(3, 10):
        monkeypatch.setenv(f"VERIFIER_MODEL_FALLBACK_{i}", "cb/kimi-k3")
    model_env_keys = _load_conftest_keys()

    for key in model_env_keys:
        monkeypatch.delenv(key, raising=False)
    import os

    for i in range(1, 10):
        assert not os.environ.get(f"VERIFIER_MODEL_FALLBACK_{i}")


def test_conftest_model_env_keys_has_9_slots_per_agent():
    model_env_keys = _load_conftest_keys()

    for agent in ("SUPERVISOR", "VERIFIER", "FORECAST"):
        for i in range(1, 10):
            assert f"{agent}_MODEL_FALLBACK_{i}" in model_env_keys


def _load_conftest_keys() -> list[str]:
    """Muat conftest dari path file (bukan package import) agar idempoten
    di host maupun container — sama seperti yang dieksekusi pytest."""
    import importlib.util
    from pathlib import Path

    conftest_path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("mc_conftest_probe", conftest_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MODEL_ENV_KEYS
