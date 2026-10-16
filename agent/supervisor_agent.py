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
- `build_agent(model_id)` — BedrockModel + Agent TANPA tool (hello-world)
- `run_hello_world()` — butuh `SUPERVISOR_MODEL_PRIMARY`; kosong → RuntimeError
  berisi `missing_config`

Catatan hasil ukur (16 Okt 2026): di bawah MOCK, `run_hello_world()` mengembalikan
echo literal `MEALCHAIN_STRANDS_OK` (kontrak S0-06). Saat dijalankan LIVE ke
Bedrock, agent menjawab mengikuti system prompt (JSON `{"ringkasan": ...}`),
bukan echo token itu — jadi jangan memakai echo literal sebagai bukti jalur live.
Yang dibuktikan jalur live: agent terbangun, model dipanggil, prompt dipatuhi.

Catatan penting soal `strands`: atribut dipakai lewat modul (`strands.Agent`,
`strands.models.BedrockModel`) supaya bisa di-mock dengan
`patch("strands.Agent")` / `patch("strands.models.BedrockModel")`.
"""

from __future__ import annotations

import os
from pathlib import Path

import strands
import strands.models

PROMPT_RELATIVE_PATH = Path("prompts") / "supervisor_system_prompt.md"
HELLO_WORLD_PROMPT = "Balas tepat: MEALCHAIN_STRANDS_OK"
HELLO_WORLD_EXPECTED = "MEALCHAIN_STRANDS_OK"

ENV_MODEL_ID = "SUPERVISOR_MODEL_PRIMARY"
ENV_REGION = "AWS_REGION"


def load_system_prompt() -> str:
    """System prompt supervisor dari berkas di paket ini."""
    return (Path(__file__).resolve().parent / PROMPT_RELATIVE_PATH).read_text(
        encoding="utf-8"
    )


def build_agent(model_id: str):
    """Bangun agent Strands minimal (satu model, tanpa tool) untuk hello-world."""
    model_kwargs: dict[str, object] = {"model_id": model_id}
    region = (os.environ.get(ENV_REGION) or "").strip()
    if region:
        model_kwargs["region_name"] = region
    model = strands.models.BedrockModel(**model_kwargs)
    return strands.Agent(
        model=model,
        tools=[],
        system_prompt=load_system_prompt(),
    )


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
