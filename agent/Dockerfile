# AgentCore Runtime — Supervisor Agent MealChain Guardian
# Dibangun dari folder agent/ (konteks build = agent/).
#
# AgentCore Runtime mengharapkan server HTTP di 0.0.0.0:8080 dengan
# /ping (health) + /invocations (payload JSON {"prompt": ...}).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    AWS_REGION=us-west-2

WORKDIR /app

COPY requirements.txt ./requirements.txt
# requirements-runtime.txt memuat bedrock-agentcore (SDK runtime) — dipisah supaya
# image runtime tidak membawa dependensi backend FastAPI.
COPY requirements-runtime.txt ./requirements-runtime.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-runtime.txt

# Seluruh paket agent (supervisor + orchestrator + tujuh worker + kontrak).
# Runtime dijalankan sebagai modul `agent.runtime_server` supaya import relatif
# antar worker/orchestrator tetap valid.
COPY __init__.py supervisor_agent.py tools.py runtime_server.py \
     orchestrator.py telemetry.py api_client.py contracts.py registry.py \
     validation.py hierarchy.json ./agent/
COPY prompts/ ./agent/prompts/
COPY workers/ ./agent/workers/

EXPOSE 8080

# Non-root, sesuai anjuran AgentCore Runtime.
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

CMD ["python", "-m", "agent.runtime_server"]
