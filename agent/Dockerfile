# AgentCore Runtime — Supervisor Agent MealChain Guardian
# Dibangun dari folder agent/ (konteks build = agent/).
#
# AgentCore Runtime mengharapkan server HTTP di 0.0.0.0:8080 dengan
# /ping (health) + /invocations (payload JSON {"prompt": ...}).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AWS_REGION=us-west-2

WORKDIR /app

COPY requirements.txt ./requirements.txt
# requirements-runtime.txt memuat bedrock-agentcore (SDK runtime) — dipisah supaya
# image runtime tidak membawa dependensi backend FastAPI.
COPY requirements-runtime.txt ./requirements-runtime.txt
RUN pip install --no-cache-dir -r requirements.txt -r requirements-runtime.txt

COPY supervisor_agent.py ./supervisor_agent.py
COPY tools.py ./tools.py
COPY runtime_server.py ./runtime_server.py
COPY prompts/ ./prompts/

EXPOSE 8080

# Non-root, sesuai anjuran AgentCore Runtime.
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

CMD ["python", "runtime_server.py"]
