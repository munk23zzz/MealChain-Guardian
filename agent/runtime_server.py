"""Entrypoint AgentCore Runtime untuk Supervisor Agent MealChain Guardian.

Kontrak yang dipatuhi (cocok dengan `backend/app/ai_providers/agentcore_caller.py`):
- HTTP server di 0.0.0.0:8080
- `GET  /ping`          → 200 (health check runtime AgentCore)
- `POST /invocations`   → body JSON {"prompt": "<teks>"} → balasan JSON {"response": "<teks>"}

Dipakai SDK resmi `bedrock-agentcore` (BedrockAgentCoreApp). Kalau SDK tidak ada,
server TIDAK berpura-pura jalan: ia keluar dengan pesan yang jelas.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:  # runtime image menjalankan `python -m agent.runtime_server`
    from .orchestrator import run_review  # noqa: E402
    from .supervisor_agent import build_agent, load_system_prompt  # noqa: E402
    from .telemetry import build_trace_rows  # noqa: E402
except ImportError:  # dijalankan langsung dari folder agent/ (tes lama)
    from orchestrator import run_review  # type: ignore[no-redef]  # noqa: E402
    from supervisor_agent import build_agent, load_system_prompt  # type: ignore[no-redef]  # noqa: E402
    from telemetry import build_trace_rows  # type: ignore[no-redef]  # noqa: E402

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


def _parse_json_prompt(prompt: str) -> dict | None:
    """Prompt bisa berupa JSON task; teks biasa tetap jalur narasi lama."""
    text = (prompt or "").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _review_response(decision_id: str) -> dict:
    """Jalankan review 7 worker; payload hasil berbentuk JSON di `response`."""
    try:
        run = run_review(decision_id)
    except Exception as exc:  # runtime tidak boleh memalsukan hasil
        return {
            "response": json.dumps(
                {
                    "status": "unavailable",
                    "decision_id": decision_id,
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
            )
        }
    payload = run.model_dump(mode="json")
    return {
        "response": json.dumps(
            {**payload, "trace_rows": build_trace_rows(run)}, ensure_ascii=False
        )
    }


def _handle_prompt(prompt: str) -> dict:
    task = _parse_json_prompt(prompt)
    if task is not None and task.get("task") == "review_decision":
        decision_id = task.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id.strip():
            return {
                "response": json.dumps(
                    {
                        "status": "failed",
                        "error": "decision_id wajib diisi untuk task review_decision",
                    },
                    ensure_ascii=False,
                )
            }
        return _review_response(decision_id.strip())
    return {"response": _narasi(prompt)}


@app.entrypoint
def invoke(payload: dict, context=None) -> dict:  # noqa: ANN001, ARG001
    """Kontrak AgentCore: payload masuk dict, keluar dict ber-kunci `response`."""
    if not isinstance(payload, dict):
        payload = {"prompt": str(payload)}
    if payload.get("task") == "review_decision":
        decision_id = payload.get("decision_id")
        if isinstance(decision_id, str) and decision_id.strip():
            return _review_response(decision_id.strip())
        return {
            "response": json.dumps(
                {
                    "status": "failed",
                    "error": "decision_id wajib diisi untuk task review_decision",
                },
                ensure_ascii=False,
            )
        }
    return _handle_prompt(payload.get("prompt", ""))


if __name__ == "__main__":
    # Prompt sistem dimuat lebih dulu supaya berkas prompt yang hilang gagal di start,
    # bukan di tengah panggilan juri.
    print(f"[runtime] system prompt: {len(load_system_prompt())} char")
    print(f"[runtime] model: {MODEL_ID}")
    app.run()
