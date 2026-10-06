"""Bedrock caller — panggilan converse() untuk model ID inference profile.

Perilaku (lihat probe live 2026-10-06):
- prompt dikirim sebagai JSON `{"prompt": <teks>}` (tanpa secret; format
  ini dijawab bersih oleh Claude/Kimi/Qwen dalam probe)
- retry dikunci 0 — retry/fallback adalah urusan chain S3-05, bukan client
- error AWS dibungkus BedrockInvocationError; HTTP status dipertahankan
  bila ada (429/5xx → retryable di chain; 403 auth → langsung lanjut slot)
- boto3 tidak terpasang → RuntimeError eksplisit (jujur)
"""

from __future__ import annotations

import json
from typing import Callable

from app.ai_providers.model_registry import ModelRef


class BedrockInvocationError(RuntimeError):
    """Kegagalan invoke Bedrock (status_code AWS bila tersedia)."""

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


def _build_ref_caller(ref: ModelRef) -> Callable[[str], str]:
    """Caller tertutup untuk satu ModelRef Bedrock."""

    def _call(prompt: str) -> str:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # boto3 opsional di host
            raise RuntimeError(
                "boto3 tidak tersedia; caller Bedrock tidak dapat berjalan"
            ) from exc

        client = boto3.client(
            "bedrock-runtime",
            region_name="us-west-2",
            config=Config(retries={"max_attempts": 0}, read_timeout=120),
        )
        body = json.dumps({"prompt": prompt}, ensure_ascii=False)
        try:
            response = client.converse(
                modelId=ref.model_id,
                messages=[{"role": "user", "content": [{"text": body}]}],
                inferenceConfig={"maxTokens": 2000, "temperature": 0.0},
            )
        except Exception as exc:
            raise BedrockInvocationError(
                f"{type(exc).__name__}: {exc}",
                status_code=_status_from_exception(exc),
            ) from exc
        try:
            parts = response["output"]["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise BedrockInvocationError(
                f"struktur converse tidak dikenal: {type(exc).__name__}"
            ) from exc
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
        return "".join(texts)

    return _call


def run_text(model_id: str, prompt: str) -> str:
    """Panggil satu model Bedrock (convenience untuk pemakaian langsung)."""
    return _build_ref_caller(ModelRef(kind="bedrock", model_id=model_id))(prompt)


def build_model_caller(ref) -> Callable[[str], str]:
    """Factory caller per ModelRef (dipakai ai_provider_chain)."""
    if getattr(ref, "kind", None) != "bedrock":
        raise ValueError(f"ref bukan bedrock: {ref}")
    return _build_ref_caller(ref)
