"""Entrypoint AgentCore Runtime untuk Supervisor Agent MealChain Guardian.

Kontrak yang dipatuhi (cocok dengan `backend/app/ai_providers/agentcore_caller.py`):
- HTTP server di 0.0.0.0:8080
- `GET  /ping`          → 200 (health check runtime AgentCore)
- `POST /invocations`   → body JSON {"prompt": "<teks>"} → balasan JSON {"response": "<teks>"}

Dipakai SDK resmi `bedrock-agentcore` (BedrockAgentCoreApp). Kalau SDK tidak ada,
server TIDAK berpura-pura jalan: ia keluar dengan pesan yang jelas.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supervisor_agent import build_agent, load_system_prompt  # noqa: E402

try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
except ImportError as exc:  # pragma: no cover - hanya untuk lingkungan tanpa SDK
    raise SystemExit(
        "bedrock-agentcore tidak terpasang. Pasang: pip install bedrock-agentcore "
        f"({exc})"
    ) from exc

app = BedrockAgentCoreApp()

MODEL_ID = os.environ.get(
    "SUPERVISOR_AGENT_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)


def _narasi(prompt: str) -> str:
    """Jalankan agent Strands untuk satu prompt; tanpa prompt → tidak memanggil model."""
    teks = (prompt or "").strip()
    if not teks:
        return "prompt kosong — tidak ada yang dinarasikan"
    agent = build_agent(MODEL_ID)
    hasil = agent(teks)
    return str(hasil)


@app.entrypoint
def invoke(payload: dict, context=None) -> dict:  # noqa: ANN001, ARG001
    """Kontrak AgentCore: payload masuk dict, keluar dict ber-kunci `response`."""
    if not isinstance(payload, dict):
        payload = {"prompt": str(payload)}
    return {"response": _narasi(payload.get("prompt", ""))}


if __name__ == "__main__":
    # Prompt sistem dimuat lebih dulu supaya berkas prompt yang hilang gagal di start,
    # bukan di tengah panggilan juri.
    print(f"[runtime] system prompt: {len(load_system_prompt())} char")
    print(f"[runtime] model: {MODEL_ID}")
    app.run()
