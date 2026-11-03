"""AgentCore Runtime caller — invoke_agent_runtime nyata (O-AI, S4-00).

Menggantikan stub NotImplementedError: ARN terpasang → caller memanggil
`bedrock-agentcore` client (`invoke_agent_runtime`) sesuai kontrak plan §11
(application → Supervisor → AgentCore Runtime → Gateway → tool).

Perilaku (selaras bedrock_caller):
- payload JSON `{"prompt": <teks>}` (tanpa secret); runtime_id dari ARN
- retry dikunci 0 — retry/fallback adalah urusan chain S3-05
- error dibungkus AgentCoreInvocationError; status HTTP dipertahankan bila
  ada (429/5xx → retryable di chain; 403 auth → lanjut slot berikutnya)
- boto3 tidak terpasang → RuntimeError eksplisit (jujur)
- response body diurai toleran: JSON `{"response": ...}` / teks polos;
  output tak terbaca → error (chain memutuskan), BUKAN hasil palsu
"""

from __future__ import annotations

import json
from typing import Callable


class AgentCoreInvocationError(RuntimeError):
    """Kegagalan invoke AgentCore Runtime (status HTTP bila tersedia)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _status_from_exception(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        meta = response.get("ResponseMetadata") or {}
        status = meta.get("HTTPStatusCode")
        if isinstance(status, int):
            return status
    return None


def is_agentcore_caller(fn) -> bool:
    """Penanda caller AgentCore nyata (untuk pengujian & audit chain)."""
    return getattr(fn, "_is_agentcore_caller", False) is True


def _extract_text(response) -> str | None:
    """Ekstrak teks jawaban runtime; struktur tak dikenal → None (jujur)."""
    if not isinstance(response, dict):
        return None
    body = response.get("response")
    if body is None:
        return None
    raw = body.read() if hasattr(body, "read") else body
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return None
    start, end = raw.find("{"), raw.rfind("}")
    candidate = raw[start : end + 1] if (start != -1 and end > start) else raw
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return raw.strip() or None
    if isinstance(data, dict):
        for key in ("response", "output", "completion", "text"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for key in ("output", "content"):
            value = data.get(key)
            if isinstance(value, list):
                parts = [p.get("text", "") for p in value if isinstance(p, dict)]
                joined = "".join(parts).strip()
                if joined:
                    return joined
    return raw.strip()


def build_runtime_caller(arn: str) -> Callable[[str], str]:
    """Caller tertutup untuk satu AgentCore Runtime ARN."""
    parts = (arn or "").strip().split(":")
    region = parts[3] if len(parts) > 3 and parts[3] else "us-west-2"
    runtime_id = parts[-1].rstrip("/").split("/")[-1]
    if not runtime_id:
        raise RuntimeError("AGENTCORE_RUNTIME_ARN kosong — caller tidak dibuat")

    def _call(prompt: str) -> str:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # boto3 opsional di host
            raise RuntimeError(
                "boto3 tidak tersedia; caller AgentCore tidak dapat berjalan"
            ) from exc

        payload = json.dumps({"prompt": prompt}, ensure_ascii=False)
        try:
            client = boto3.client(
                "bedrock-agentcore",
                region_name=region,
                config=Config(retries={"max_attempts": 0}, read_timeout=120),
            )
            response = client.invoke_agent_runtime(
                agentRuntimeArn=arn,
                contentType="application/json",
                accept="application/json",
                payload=payload,
            )
        except Exception as exc:
            # Konstruksi client pun bisa gagal (mis. botocore lama tak
            # mengenal service bedrock-agentcore) — dibungkus rapi agar
            # chain lanjut ke slot berikutnya, bukan error mentah naik.
            raise AgentCoreInvocationError(
                f"{type(exc).__name__}: {exc}",
                status_code=_status_from_exception(exc),
            ) from exc
        text = _extract_text(response)
        if not text:
            raise AgentCoreInvocationError(
                "struktur response AgentCore tidak dikenal / kosong"
            )
        return text

    _call._is_agentcore_caller = True  # type: ignore[attr-defined]
    return _call
