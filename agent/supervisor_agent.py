"""Supervisor Agent — Strands SDK (S0-06/S0-07), sasaran deploy: AgentCore Runtime.

Modul ini adalah agent yang di-deploy ke Amazon Bedrock AgentCore Runtime.
Ia SENGAJA terpisah dari `backend/app/services/supervisor_client.py`
(klien narasi REST di backend): backend tetap jalur yang tersertifikasi
lokal, sedangkan modul ini jalur agent penuh via Strands + Gateway.

Status jujur: jalur live-nya masih BLOCKED karena `AGENTCORE_RUNTIME_ARN`
kosong (lihat `docs/verification/sprint-3.md` §Blockers). Yang tersertifikasi
di sini adalah kontrak S0-06: agent bisa dibangun dan hello-world dijalankan.

Kontrak modul (dipakai `backend/tests/test_supervisor_agent.py`, host-only):
- `load_system_prompt()` — prompt dari `prompts/supervisor_system_prompt.md`
- `build_tools()` — 4 tool baca (lihat `tools.py`) dibungkus decorator Strands
- `build_agent(model_id)` — BedrockModel + Agent dengan 4 tool baca
- `run_hello_world()` — butuh `SUPERVISOR_MODEL_PRIMARY`; kosong → RuntimeError
  berisi `missing_config`

Catatan hasil ukur (16 Okt 2026): di bawah MOCK, `run_hello_world()` mengembalikan
echo literal `MEALCHAIN_STRANDS_OK` (kontrak S0-06). Saat dijalankan LIVE ke
Bedrock, agent menjawab mengikuti system prompt (JSON `{"ringkasan": ...}`),
bukan echo token itu — jadi jangan memakai echo literal sebagai bukti jalur live.
Yang dibuktikan jalur live: agent terbangun, model dipanggil, prompt dipatuhi.

Tool memanggil API backend (bukan menghitung ulang). Kredensial dibaca dari
`MEALCHAIN_API_URL` + `MEALCHAIN_API_TOKEN`; tanpa token tool menolak dengan
`missing_config`, bukan mengarang angka.

Catatan penting soal `strands`: atribut dipakai lewat modul (`strands.Agent`,
`strands.models.BedrockModel`, `strands.tool`) supaya bisa di-mock dengan
`patch("strands.Agent")` / `patch("strands.models.BedrockModel")`.

Impor `strands` SEPENUHNYA LAZY (27 Okt 2026). Sebelumnya modul ini mengimpor
`strands` di tingkat atas, sehingga di image backend (yang tidak punya SDK itu)
modul supervisor sama sekali tidak bisa diimpor — supervisor mati bukan karena
tidak ada model, tetapi karena satu-satunya pintu butuh SDK. Kini narasi
supervisor memakai pintu resolusi yang sama dengan sembilan agent lain
(`agent/workers/reasoner.py`): rantai provider backend → boto3
`bedrock-runtime.converse` → `strands`. `build_agent`/`build_tools` (jalur
AgentCore penuh) tetap memerlukan `strands` dan gagal dengan `missing_config`
yang jujur bila SDK tidak ada.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

try:  # dipakai sebagai paket `agent.supervisor_agent` (runtime image)
    from .tools import (
        get_cost_eligibility,
        get_evidence_digest,
        get_safety_freshness,
        get_supply_demand,
    )
except ImportError:  # dijalankan sebagai skrip tunggal oleh tes lama
    from tools import (  # type: ignore[no-redef]
        get_cost_eligibility,
        get_evidence_digest,
        get_safety_freshness,
        get_supply_demand,
    )

AGENT_SUPERVISOR = "supervisor"

PROMPT_RELATIVE_PATH = Path("prompts") / "supervisor_system_prompt.md"
HELLO_WORLD_PROMPT = "Balas tepat: MEALCHAIN_STRANDS_OK"
HELLO_WORLD_EXPECTED = "MEALCHAIN_STRANDS_OK"

ENV_MODEL_ID = "SUPERVISOR_MODEL_PRIMARY"
ENV_REGION = "AWS_REGION"

TOOL_FUNCTIONS = (
    get_supply_demand,
    get_safety_freshness,
    get_cost_eligibility,
    get_evidence_digest,
)

ModelCallable = Callable[[str], str]


def _impor_strands():
    """Modul `strands` atau `None` — jalur narasi tidak boleh bergantung padanya."""
    try:
        import strands  # noqa: PLC0415 - dependensi opsional (runtime AgentCore)
    except Exception:  # noqa: BLE001 - image backend memang tidak punya SDK ini
        return None
    return strands


def load_system_prompt() -> str:
    """System prompt supervisor dari berkas di paket ini."""
    return (Path(__file__).resolve().parent / PROMPT_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )


def build_tools() -> list:
    """Empat tool baca, dibungkus decorator Strands (schema dari docstring)."""
    strands = _impor_strands()
    if strands is None:
        raise RuntimeError(
            "missing_config: SDK strands tidak terpasang — tool supervisor "
            "hanya tersedia di image runtime AgentCore"
        )
    return [strands.tool(fn) for fn in TOOL_FUNCTIONS]


def build_agent(model_id: str):
    """Bangun agent Strands dengan 4 tool baca ke API MealChain."""
    strands = _impor_strands()
    if strands is None:
        raise RuntimeError(
            "missing_config: SDK strands tidak terpasang — agent penuh tidak "
            "dapat dibangun; pakai `narasi()` untuk jalur tanpa SDK"
        )
    model_kwargs: dict[str, object] = {"model_id": model_id}
    region = (os.environ.get(ENV_REGION) or "").strip()
    if region:
        model_kwargs["region_name"] = region
    model = strands.models.BedrockModel(**model_kwargs)
    return strands.Agent(
        model=model,
        tools=build_tools(),
        system_prompt=load_system_prompt(),
    )


def model_supervisor_dari_env() -> ModelCallable | None:
    """Model narasi supervisor lewat pintu resolusi bersama (9 agent).

    Prompt system yang ditempel adalah prompt SUPERVISOR, bukan prompt
    verifier; independensi itu milik `agent/workers/reasoner.prompt_sistem`.
    Impor resolver sengaja lazy: impor tingkat atas `workers.reasoner`
    memakai impor relatif, dan modul ini masih dipakai sebagai skrip tunggal
    oleh tes S0-06 lama.
    """
    try:
        from .workers.reasoner import reasoner_dan_jalur_dari_env
    except ImportError:
        from workers.reasoner import reasoner_dan_jalur_dari_env  # type: ignore[no-redef]
    return reasoner_dan_jalur_dari_env(agent=AGENT_SUPERVISOR)[1]


def narasi(prompt: str, *, model: ModelCallable | None = None) -> str:
    """Satu panggilan narasi supervisor — tanpa `strands`, tanpa tool.

    Kontrak keluaran TIDAK berubah: hanya teks narasi. Angka/status tetap milik
    kode deterministik, dan model yang tidak tersedia gagal jujur
    (`missing_config`), bukan mengarang ringkasan.
    """
    panggil = model if model is not None else model_supervisor_dari_env()
    if panggil is None:
        raise RuntimeError(
            f"missing_config: model supervisor tidak tersedia ({ENV_MODEL_ID} "
            "kosong atau tidak ada provider yang bisa dipanggil)"
        )
    return str(panggil(prompt))


def run_hello_world() -> str:
    """S0-06: panggil agent sekali dengan prompt tetap; kembalikan teksnya."""
    model_id = (os.environ.get(ENV_MODEL_ID) or "").strip()
    if not model_id:
        raise RuntimeError(
            f"missing_config: {ENV_MODEL_ID} belum diisi — agent Strands tidak "
            "bisa dibangun tanpa model id"
        )
    agent = build_agent(model_id)
    return str(agent(HELLO_WORLD_PROMPT))


if __name__ == "__main__":  # pragma: no cover - jalur manual
    print(run_hello_world())
