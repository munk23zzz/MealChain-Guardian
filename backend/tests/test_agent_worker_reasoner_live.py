"""Jalur model NYATA untuk lapisan penalaran SEMBILAN agent (TDD, 27 Okt 2026).

Konteks masalah. Sebelum berkas ini, `agent/workers/reasoner.py` hanya bisa
membangun model lewat SDK `strands`, dan `strands` TIDAK terpasang di image
backend. Akibatnya jalur in-process (`AGENT_REVIEW_MODE=local`,
`MULTI_AGENT_REVIEW=true`) selalu berakhir `unavailable` walau runtime sudah
punya kredensial: lapisan penalaran mati bukan karena tidak ada model, tetapi
karena satu-satunya pintu memerlukan SDK yang tidak ada.

Kontrak yang dikunci berkas ini:

1. `panggil_bedrock_converse()` mengirim payload `converse` yang benar
   (`modelId`, `messages`, `inferenceConfig`) dan mengembalikan teks dari
   `response["output"]["message"]["content"][0]["text"]`.
2. Kegagalan klien diteruskan APA ADANYA (pemanggil yang menandai
   `unavailable`), tidak ditelan menjadi string kosong.
3. `reasoner_dari_env()` memilih jalur berurutan: rantai provider backend
   (`build_default_callers("supervisor")`) → boto3 `bedrock-runtime` converse →
   `strands` → `None`. Semua jalur berlaku untuk SEMBILAN agent (tujuh worker +
   supervisor + verifier).
4. Prompt sistem tidak boleh saling pinjam: supervisor memakai
   `prompts/supervisor_system_prompt.md`, verifier memakai
   `prompts/verifier_system_prompt.md`. Independensi verifier (AUD-9A-03)
   dijaga di sini, bukan hanya di dokumentasi.
5. Verifier tetap fail-closed: tanpa model, audit deterministik tetap berjalan
   dan verdict `unavailable` — bukan `consistent` karangan.

Seam yang dipakai tes: klien boto3 PALSU (AWS tidak boleh dipanggil) dan
modul `strands` tiruan. Tidak ada jaringan.
"""

from __future__ import annotations

import pytest
from agent.workers import reasoner as modul

MODEL_BEDROCK = "us.anthropic.claude-sonnet-4-20250514-v1:0"
ENV_MODEL = {
    "WORKER_AGENT_MODEL": MODEL_BEDROCK,
    "SUPERVISOR_MODEL_PRIMARY": MODEL_BEDROCK,
    "VERIFIER_AGENT_MODEL": MODEL_BEDROCK,
    "AWS_REGION": "us-west-2",
}


# ---------------------------------------------------------------------------
# Perkakas: klien & SDK tiruan (tanpa jaringan)
# ---------------------------------------------------------------------------


class KlienBedrockPalsu:
    """Klien `bedrock-runtime` palsu: merekam payload, tidak pernah ke AWS."""

    def __init__(
        self,
        *,
        teks: str = '{"summary":"ok","rationale":"tes"}',
        galat: BaseException | None = None,
        respons: dict | None = None,
    ) -> None:
        self.teks = teks
        self.galat = galat
        self.respons = respons
        self.payload: dict = {}

    def converse(self, **kwargs):
        self.payload = kwargs
        if self.galat is not None:
            raise self.galat
        if self.respons is not None:
            return self.respons
        return {"output": {"message": {"content": [{"text": self.teks}]}}}


def _strands_palsu(hasil: str = "dari-strands"):
    """Tiruan minimal `strands`: `Agent(...)` dapat dipanggil, kwargs direkam."""
    rekam: dict = {}

    class BedrockModel:
        def __init__(self, **kwargs) -> None:
            rekam["model"] = kwargs

    class Agent:
        def __init__(self, **kwargs) -> None:
            rekam["agent"] = kwargs

        def __call__(self, prompt: str) -> str:
            rekam["prompt"] = prompt
            return hasil

    strands = type(
        "StrandsPalsu",
        (),
        {"Agent": Agent, "models": type("models", (), {"BedrockModel": BedrockModel})},
    )()
    return strands, rekam


def _slot(label: str, fn, kind: str) -> tuple[str, object, str]:
    return (label, fn, kind)


# ---------------------------------------------------------------------------
# 1. Panggilan converse: payload & ekstraksi teks
# ---------------------------------------------------------------------------


def test_converse_mengirim_payload_dan_mengembalikan_teks():
    klien = KlienBedrockPalsu(teks='{"summary":"ok","rationale":"tes"}')

    hasil = modul.panggil_bedrock_converse(
        "Balas JSON", model_id=MODEL_BEDROCK, region="us-west-2", client=klien
    )

    assert hasil == '{"summary":"ok","rationale":"tes"}'
    assert klien.payload["modelId"] == MODEL_BEDROCK
    assert klien.payload["messages"] == [
        {"role": "user", "content": [{"text": "Balas JSON"}]}
    ]
    inference = klien.payload["inferenceConfig"]
    assert isinstance(inference["maxTokens"], int)
    assert inference["maxTokens"] > 0
    # Suhu 0.0: lapisan advisory tidak boleh berimprovisasi di atas fakta.
    assert inference["temperature"] == 0.0


def test_converse_meneruskan_system_prompt_bila_diberikan():
    klien = KlienBedrockPalsu()

    modul.panggil_bedrock_converse(
        "audit",
        model_id=MODEL_BEDROCK,
        region="us-west-2",
        client=klien,
        system="Kamu adalah **VERIFIER** MealChain Guardian.",
    )

    assert klien.payload["system"] == [
        {"text": "Kamu adalah **VERIFIER** MealChain Guardian."}
    ]


def test_converse_tanpa_system_tidak_mengirim_blok_system():
    klien = KlienBedrockPalsu()

    modul.panggil_bedrock_converse(
        "narasi", model_id=MODEL_BEDROCK, region="us-west-2", client=klien
    )

    assert "system" not in klien.payload


# ---------------------------------------------------------------------------
# 2. Kegagalan klien TIDAK ditelan
# ---------------------------------------------------------------------------


def test_converse_meneruskan_galat_klien_apa_adanya():
    galat = RuntimeError("ThrottlingException: too many requests")
    klien = KlienBedrockPalsu(galat=galat)

    with pytest.raises(RuntimeError) as info:
        modul.panggil_bedrock_converse(
            "Balas JSON", model_id=MODEL_BEDROCK, region="us-west-2", client=klien
        )

    assert info.value is galat
    assert "ThrottlingException" in str(info.value)


def test_converse_menolak_jawaban_kosong():
    klien = KlienBedrockPalsu(teks="   ")

    with pytest.raises(RuntimeError):
        modul.panggil_bedrock_converse(
            "Balas JSON", model_id=MODEL_BEDROCK, region="us-west-2", client=klien
        )


def test_converse_menolak_struktur_tak_dikenal():
    klien = KlienBedrockPalsu(respons={"output": {"message": {}}})

    with pytest.raises(RuntimeError):
        modul.panggil_bedrock_converse(
            "Balas JSON", model_id=MODEL_BEDROCK, region="us-west-2", client=klien
        )


# ---------------------------------------------------------------------------
# 3. Urutan pemilihan jalur: rantai provider → boto3 → strands → None
# ---------------------------------------------------------------------------


def test_rantai_provider_dipilih_lebih_dulu(monkeypatch):
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:bedrock", lambda p: "dari-rantai", "bedrock")],
    )
    monkeypatch.setattr(
        modul, "_impor_boto3", lambda: pytest.fail("boto3 tidak boleh dipakai")
    )

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    assert jalur == "provider_chain"
    assert panggil is not None
    assert panggil("prompt") == "dari-rantai"


def test_rantai_melewati_slot_agentcore_dan_slot_mati(monkeypatch):
    """Slot AgentCore = runtime supervisor; memanggilnya dari worker = rekursi."""
    urutan: list[str] = []

    def arn_luar(prompt: str) -> str:
        urutan.append("agentcore")
        return '{"narasi":"dari-agentcore"}'

    def mati(prompt: str) -> str:
        urutan.append("mati")
        raise RuntimeError("503 Service Unavailable")

    def hidup(prompt: str) -> str:
        urutan.append("hidup")
        return '{"summary":"ok"}'

    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [
            _slot("primary:agentcore", arn_luar, "agentcore"),
            _slot("fallback_1:bedrock", mati, "bedrock"),
            _slot("fallback_2:sap_ai_core", hidup, "sap_ai_core"),
        ],
    )

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    assert jalur == "provider_chain"
    assert panggil("prompt") == '{"summary":"ok"}'
    assert urutan == ["mati", "hidup"]


def test_rantai_dengan_hanya_slot_agentcore_bukan_jalur_sah(monkeypatch):
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:agentcore", lambda p: "x", "agentcore")],
    )
    # Jalur berikutnya dimatikan supaya yang diuji hanya keputusan atas rantai.
    monkeypatch.setattr(modul, "_impor_boto3", lambda: None)
    monkeypatch.setattr(modul, "_impor_strands", lambda: None)

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    # Rantai berisi hanya slot AgentCore yang sengaja dilewati → bukan jalur sah.
    assert jalur != "provider_chain"
    assert panggil is None


def test_rantai_mati_semua_slot_boleh_dilempar_ke_pemanggil(monkeypatch):
    def mati(prompt: str) -> str:
        raise RuntimeError("403 AccessDenied")

    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [
            _slot("primary:bedrock", mati, "bedrock"),
            _slot("fallback_1:inferhub", mati, "inferhub"),
        ],
    )

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    assert jalur == "provider_chain"
    with pytest.raises(RuntimeError) as info:
        panggil("prompt")
    assert "403" in str(info.value)


def test_bedrock_converse_dipakai_bila_rantai_kosong(monkeypatch):
    monkeypatch.setattr(modul, "_rantai_provider_supervisor", lambda: [])
    klien = KlienBedrockPalsu(teks='{"summary":"ok"}')
    monkeypatch.setattr(modul, "_klien_bedrock", lambda region: klien)

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    assert jalur == "bedrock_converse"
    assert panggil is not None
    assert panggil("Balas JSON") == '{"summary":"ok"}'
    assert klien.payload["modelId"] == MODEL_BEDROCK


def test_strands_dipakai_bila_rantai_dan_boto3_tidak_ada(monkeypatch):
    monkeypatch.setattr(modul, "_rantai_provider_supervisor", lambda: [])
    monkeypatch.setattr(modul, "_impor_boto3", lambda: None)
    strands, rekam = _strands_palsu()
    monkeypatch.setattr(modul, "_impor_strands", lambda: strands)

    jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))

    assert jalur == "strands"
    assert panggil is not None
    assert panggil("prompt") == "dari-strands"
    assert rekam["model"]["model_id"] == MODEL_BEDROCK


def test_none_bila_semua_jalur_tidak_tersedia(monkeypatch):
    monkeypatch.setattr(modul, "_rantai_provider_supervisor", lambda: [])
    monkeypatch.setattr(modul, "_impor_boto3", lambda: None)
    monkeypatch.setattr(modul, "_impor_strands", lambda: None)

    assert modul.reasoner_dari_env(dict(ENV_MODEL)) is None
    assert modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL))[0] == "none"


def test_tanpa_model_id_tetap_none_walau_rantai_ada(monkeypatch):
    """Kontrak lama dipertahankan: tanpa env model, lapisan ini TIDAK aktif."""
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:bedrock", lambda p: "x", "bedrock")],
    )

    assert modul.reasoner_dari_env({}) is None
    assert modul.reasoner_dan_jalur_dari_env({"AWS_REGION": "us-west-2"})[0] == "none"


def test_id_provider_lain_tidak_dikirim_ke_bedrock_runtime(monkeypatch):
    """`sap-ai-core:llm` bukan model id Bedrock — jangan dikirim ke converse."""
    monkeypatch.setattr(modul, "_rantai_provider_supervisor", lambda: [])
    monkeypatch.setattr(
        modul,
        "_klien_bedrock",
        lambda region: pytest.fail("bedrock tidak boleh dipanggil untuk sap-ai-core:llm"),
    )
    monkeypatch.setattr(modul, "_impor_strands", lambda: None)

    env = {"SUPERVISOR_MODEL_PRIMARY": "sap-ai-core:llm", "AWS_REGION": "us-west-2"}

    assert modul.reasoner_dari_env(env) is None


# ---------------------------------------------------------------------------
# 4. Sembilan agent: prompt sendiri + jalur model yang sama
# ---------------------------------------------------------------------------

SEMBILAN = (
    "supply",
    "demand",
    "freshness",
    "safety",
    "price",
    "logistics",
    "evidence",
    "supervisor",
    "verifier",
)

#: Baris identitas tiap prompt. Dipakai untuk membuktikan prompt TIDAK tertukar
#: (independensi verifier, AUD-9A-03) tanpa mengandalkan kata "supervisor" yang
#: juga muncul sebagai konteks di prompt verifier.
IDENTITAS_SUPERVISOR = "KAMU ADALAH SUPERVISOR MEALCHAIN GUARDIAN"
IDENTITAS_VERIFIER = "KAMU ADALAH **VERIFIER** MEALCHAIN GUARDIAN"


def _normal(prompt: str) -> str:
    return " ".join(prompt.upper().split())


def test_sembilan_agent_terdaftar_dengan_prompt_sendiri():
    assert tuple(modul.AGENT_PENALARAN) == SEMBILAN

    semua: dict[str, str] = {}
    for nama in SEMBILAN:
        prompt = modul.prompt_sistem(nama)
        assert prompt.strip(), f"prompt {nama} kosong"
        semua[nama] = prompt

    # Tidak ada dua agent yang berbagi prompt identik (terutama s/v).
    assert len(set(semua.values())) == len(SEMBILAN)


def test_supervisor_tidak_memakai_prompt_verifier_dan_sebaliknya():
    supervisor = _normal(modul.prompt_sistem("supervisor"))
    verifier = _normal(modul.prompt_sistem("verifier"))

    assert IDENTITAS_SUPERVISOR in supervisor
    assert IDENTITAS_VERIFIER not in supervisor
    assert IDENTITAS_VERIFIER in verifier
    assert IDENTITAS_SUPERVISOR not in verifier


def test_sembilan_agent_ikut_jalur_model_yang_sama(monkeypatch):
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:bedrock", lambda p: "ok", "bedrock")],
    )

    for nama in SEMBILAN:
        jalur, panggil = modul.reasoner_dan_jalur_dari_env(dict(ENV_MODEL), agent=nama)
        assert jalur == "provider_chain", nama
        assert panggil is not None, nama


def test_sembilan_agent_sama_sama_none_bila_semua_jalur_mati(monkeypatch):
    monkeypatch.setattr(modul, "_rantai_provider_supervisor", lambda: [])
    monkeypatch.setattr(modul, "_impor_boto3", lambda: None)
    monkeypatch.setattr(modul, "_impor_strands", lambda: None)

    for nama in SEMBILAN:
        assert modul.reasoner_dari_env(dict(ENV_MODEL), agent=nama) is None, nama


def test_prompt_sistem_agent_tak_dikenal_ditolak():
    with pytest.raises((ValueError, FileNotFoundError)):
        modul.prompt_sistem("tidak_ada")


# ---------------------------------------------------------------------------
# 5. Supervisor & verifier memakai jalur resolusi yang sama (tanpa strands)
# ---------------------------------------------------------------------------


def test_supervisor_agent_impor_tanpa_strands():
    """Modul supervisor harus bisa diimpor walau `strands` tidak terpasang."""
    import importlib

    import agent.supervisor_agent as supervisor

    importlib.reload(supervisor)
    assert hasattr(supervisor, "model_supervisor_dari_env")


def test_supervisor_narasi_memakai_prompt_supervisor(monkeypatch):
    """Jalur supervisor memakai prompt supervisor — bukan prompt verifier."""
    import agent.supervisor_agent as supervisor

    direkam: dict = {}

    def slot(prompt: str) -> str:
        direkam["prompt"] = prompt
        return '{"ringkasan":"ok"}'

    monkeypatch.setenv("SUPERVISOR_MODEL_PRIMARY", MODEL_BEDROCK)
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:bedrock", slot, "bedrock")],
    )

    hasil = supervisor.narasi("Ringkas keputusan ini.")

    assert hasil == '{"ringkasan":"ok"}'
    teks = _normal(direkam["prompt"])
    assert IDENTITAS_SUPERVISOR in teks
    assert IDENTITAS_VERIFIER not in teks
    assert "Ringkas keputusan ini." in direkam["prompt"]


def test_supervisor_tanpa_model_gagal_jujur_bukan_mengarang(monkeypatch):
    import agent.supervisor_agent as supervisor

    monkeypatch.setattr(supervisor, "model_supervisor_dari_env", lambda: None)

    with pytest.raises(RuntimeError, match="missing_config"):
        supervisor.narasi("Ringkas keputusan ini.")


def test_verifier_model_memakai_prompt_verifier(monkeypatch):
    """`verifier_model.model_dari_env()` mewarisi jalur baru + prompt verifier."""
    from agent import verifier_model

    direkam: dict = {}

    def slot(prompt: str) -> str:
        direkam["prompt"] = prompt
        return "{}"

    monkeypatch.setenv("VERIFIER_AGENT_MODEL", MODEL_BEDROCK)
    monkeypatch.setattr(
        modul,
        "_rantai_provider_supervisor",
        lambda: [_slot("primary:bedrock", slot, "bedrock")],
    )

    verifier_model.model_dari_env.cache_clear()
    try:
        model = verifier_model.model_dari_env()
        assert model is not None
        model("audit putaran ini")
    finally:
        verifier_model.model_dari_env.cache_clear()

    teks = _normal(direkam["prompt"])
    assert IDENTITAS_VERIFIER in teks
    assert IDENTITAS_SUPERVISOR not in teks
    assert "audit putaran ini" in direkam["prompt"]


def test_verifier_tanpa_model_tetap_unavailable(monkeypatch):
    """Fail-closed: tanpa model, audit deterministik jalan; `consistent` haram."""
    from uuid import uuid4

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
    assert temuan.status.value != "ok" or temuan.blocking is False
