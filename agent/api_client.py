"""Klien HTTP read-only untuk worker agent.

Worker hanya boleh membaca API MealChain. Tidak ada method tulis di sini;
aksi berisiko tetap lewat approval manusia di backend.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

ENV_API_URL = "MEALCHAIN_API_URL"
ENV_TOKEN = "MEALCHAIN_API_TOKEN"
DEFAULT_API_URL = "http://backend:8000"
DEFAULT_TIMEOUT_SECONDS = 15.0


class AgentApiError(RuntimeError):
    """Kegagalan API yang harus dilaporkan apa adanya, bukan ditebak."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path


class MealChainClient:
    """Klien GET sederhana; token tidak pernah masuk pesan error."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        token: str = "",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token.strip()
        self.timeout = timeout
        if not self._token:
            raise AgentApiError(
                "missing_config: MEALCHAIN_API_TOKEN belum diset; "
                "worker tidak boleh mengarang data"
            )

    @classmethod
    def from_env(cls) -> MealChainClient:
        return cls(
            base_url=os.environ.get(ENV_API_URL) or DEFAULT_API_URL,
            token=os.environ.get(ENV_TOKEN) or "",
        )

    def get(self, path: str, params: dict[str, object] | None = None) -> dict:
        if not path.startswith("/"):
            raise AgentApiError(f"path API harus diawali '/': {path!r}")
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
            path = f"{path}?{query}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise AgentApiError(
                f"HTTP {exc.code} pada {path}: {detail}",
                status_code=exc.code,
                path=path,
            ) from exc
        except urllib.error.URLError as exc:
            raise AgentApiError(
                f"tidak dapat menghubungi API di {self.base_url} ({exc.reason})",
                path=path,
            ) from exc
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AgentApiError(
                f"respons {path} bukan JSON yang sah", path=path
            ) from exc
        if not isinstance(parsed, dict):
            raise AgentApiError(f"respons {path} bukan objek JSON", path=path)
        return parsed


__all__ = [
    "AgentApiError",
    "DEFAULT_API_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "ENV_API_URL",
    "ENV_TOKEN",
    "MealChainClient",
]
