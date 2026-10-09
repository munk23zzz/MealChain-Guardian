"""S4-00 O-AI: provider chain jujur + adapter AgentCore nyata bila tersedia.

Kontrak (plan §11 + prompt Owner §31):
- slot agentcore dengan ARN terpasang → caller invoke runtime NYATA
  (bedrock-agentcore `invoke_agent_runtime`); bukan stub NotImplementedError.
- AgentCore tidak terkonfigurasi (ARN kosong) → TIDAK masuk chain sama
  sekali (tanpa slot mati di depan).
- chain habis di SEMUA client (verifier/forecast/supervisor) → status
  unavailable yang ditangani rapi, BUKAN ProviderUnavailableError yang
  tidak tertangkap (500 rehearsal blocker).
- with_fallback_chain dipakai dengan `fallbacks` list penuh — slot 4+.
"""


from app.ai_providers import ai_provider_chain as chain_mod
from app.ai_providers.ai_provider_chain import build_default_callers


def _strip_model_env(monkeypatch):
    keys = [
        "AGENTCORE_RUNTIME_ARN",
        "SUPERVISOR_MODEL_PRIMARY",
        "SUPERVISOR_MODEL_FALLBACK",
    ]
    for agent in ("SUPERVISOR", "VERIFIER", "FORECAST"):
        keys.append(f"{agent}_MODEL_PRIMARY")
        for i in range(1, 13):
            keys.append(f"{agent}_MODEL_FALLBACK_{i}")
    keys += ["INFERHUB_URL", "INFERHUB_API_KEY"]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_agentcore_arn_tanpa_env_kosong_membuat_caller_nyata(monkeypatch):
    """ARN terpasang → caller AgentCore nyata (bukan stub NotImplementedError)."""
    _strip_model_env(monkeypatch)
    monkeypatch.setenv(
        "AGENTCORE_RUNTIME_ARN",
        "arn:aws:bedrock:us-west-2:1:agent-runtime/abc",
    )
    chain = build_default_callers("supervisor")
    assert chain[0][0] == "primary:agentcore"
    caller = chain[0][1]
    assert callable(caller)
    from app.ai_providers import agentcore_caller

    assert agentcore_caller.is_agentcore_caller(caller)


def test_agentcore_tanpa_arn_tidak_menyisipkan_slot_mati(monkeypatch):
    _strip_model_env(monkeypatch)
    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", "us.anthropic.")
    chain = build_default_callers("supervisor")
    assert [label for label, _, _ in chain] == ["primary:bedrock"]


# --------------------------------------------- chain panjang & exhaustion


def test_run_verifier_meneruskan_seluruh_chain_slot_4(monkeypatch):
    """Slot 4+ harus benar-benar dipanggil — tidak lagi terpotong di 3."""
    _strip_model_env(monkeypatch)
    import json as _json

    from app.ai_providers import verifier_client as vc

    def _ok(prompt):
        return _json.dumps({"verdict": "CONSISTENT", "reason": "slot4"})

    chain = [
        ("primary:bedrock", lambda p: (_ for _ in ()).throw(RuntimeError("x")), "bedrock"),
        ("fallback_1:inferhub", lambda p: (_ for _ in ()).throw(RuntimeError("x")), "inferhub"),
        ("fallback_2:inferhub", lambda p: (_ for _ in ()).throw(RuntimeError("x")), "inferhub"),
        ("fallback_3:inferhub", _ok, "inferhub"),
    ]
    monkeypatch.setattr(
        chain_mod, "build_default_callers", lambda agent: chain
    )
    result = vc.run_verifier({"safety_status": "PASS"})
    assert result.verdict == "CONSISTENT"
    assert result.provider == "fallback_3:inferhub"


def test_verifier_chain_habis_unavailable_bukan_exception_naik(monkeypatch):
    """Chain kosong/semua mati → UNAVAILABLE rapi, bukan ProviderUnavailableError."""
    _strip_model_env(monkeypatch)
    from app.ai_providers import verifier_client as vc

    monkeypatch.setattr(chain_mod, "build_default_callers", lambda agent: [])
    result = vc.run_verifier({"safety_status": "PASS"})
    assert result.verdict == "UNAVAILABLE"


def test_supervisor_chain_habis_status_unavailable(monkeypatch):
    from app.services import supervisor_client as sc

    chain = [
        ("primary:bedrock", lambda p: (_ for _ in ()).throw(RuntimeError("mati")), "bedrock"),
        ("fallback_1:inferhub", lambda p: (_ for _ in ()).throw(RuntimeError("mati")), "inferhub"),
    ]
    monkeypatch.setattr(chain_mod, "build_default_callers", lambda agent: chain)
    result = sc.run_supervisor({"commodity": "telur"})
    assert result.status == "unavailable"
    assert result.summary is None

