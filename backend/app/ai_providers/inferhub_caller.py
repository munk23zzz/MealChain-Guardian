"""Inferhub caller — HTTP OpenAI-compatible ke INFERHUB_URL.

Perilaku (lihat probe live 2026-10-06):
- POST {model, messages, max_tokens, temperature:0}; key di header Bearer
- thinking model (kimi-k3) butuh max_tokens besar (4000) agar `content`
  tidak kosong setelah reasoning — probe membuktikannya
- key HANYA dipakai di header; tidak pernah masuk prompt/log/error message
- HTTP error → InferhubInvocationError dengan status_code (chain yang
  memutuskan retry untuk 429/5xx)
- INFERHUB_URL / INFERHUB_API_KEY kosong → RuntimeError saat build_caller
  (jujur; tanpa panggilan jaringan)
"""

from __future__ import annotations

import json
import os
import urllib.error
from typing import Callable
from urllib.request import Request, urlopen

INFERHUB_DEFAULT_MAX_TOKENS = 4000


class InferhubInvocationError(RuntimeError):
    """Kegagalan invoke Inferhub (status_code HTTP bila ada)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def build_caller(
    model_id: str,
    *,
    url: str | None = None,
    api_key: str | None = None,
    max_tokens: int = INFERHUB_DEFAULT_MAX_TOKENS,
) -> Callable[[str], str]:
    """Bangun caller tertutup untuk satu model Inferhub."""
    endpoint = (url or os.environ.get("INFERHUB_URL") or "").strip()
    key = (api_key or os.environ.get("INFERHUB_API_KEY") or "").strip()
    if not endpoint or not key:
        raise RuntimeError(
            "INFERHUB_URL / INFERHUB_API_KEY belum dikonfigurasi"
        )

    def _call(prompt: str) -> str:
        payload = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise InferhubInvocationError(
                f"inferhub http {exc.code}", status_code=exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise InferhubInvocationError(
                f"{type(exc).__name__}: {exc}", status_code=None
            ) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InferhubInvocationError(
                "struktur response inferhub tidak dikenal"
            ) from exc
        return content if isinstance(content, str) else ""

    return _call
