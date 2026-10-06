"""Agent decision-session memory (S3-08) — isolation + sanitasi.

AgentCore Memory belum tersedia (memory_id kosong) → adapter `local`
dengan isolasi session eksplisit; provider AgentCore yang tidak
terkonfigurasi SELALU error eksplisit, tidak pernah fallback diam ke
state global bersama.
"""

from __future__ import annotations

import os
from typing import Any

_SECRET_HINTS = (
    "credential",
    "secret",
    "password",
    "token",
    "api_key",
    "authorization",
)


class MemoryUnavailableError(RuntimeError):
    """Provider memory tidak dapat dipakai — eksplisit, bukan silent."""


def sanitize_memory_payload(payload: Any) -> Any:
    """Buang key yang berbau secret/credential (rekursif, case-insensitive)."""
    if isinstance(payload, dict):
        clean = {}
        for key, value in payload.items():
            if any(hint in str(key).lower() for hint in _SECRET_HINTS):
                continue
            clean[key] = sanitize_memory_payload(value)
        return clean
    if isinstance(payload, list):
        return [sanitize_memory_payload(item) for item in payload]
    return payload


class LocalMemoryBackend:
    """Memory per-session in-memory; state A tidak pernah bocor ke B."""

    provider = "local"

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], Any] = {}

    def write(self, session_id: str, key: str, value: Any) -> None:
        self._store[(session_id, key)] = sanitize_memory_payload(value)

    def read(self, session_id: str, key: str) -> Any:
        return self._store.get((session_id, key))

    def list_keys(self, session_id: str) -> list[str]:
        return sorted(k for (sid, k) in self._store if sid == session_id)

    def describe(self, session_id: str, key: str) -> dict:
        return {"session_id": session_id, "key": key}


class AgentCoreMemoryBackend:
    """Adapter AgentCore Memory — hanya bila memory_id benar-benar ada."""

    provider = "agentcore"

    def __init__(self, memory_id: str, runtime_endpoint: str | None) -> None:
        self._memory_id = memory_id
        # AgentCore Memory runtime endpoint belum tersedia di environment;
        # adapter menolak operasi sampai endpoint nyata dikonfigurasi.
        self._runtime_endpoint = (runtime_endpoint or "").strip()

    def write(self, session_id: str, key: str, value: Any) -> None:
        raise MemoryUnavailableError(
            "AgentCore Memory runtime endpoint belum dikonfigurasi "
            f"(memory_id={self._memory_id!r}); tidak ada fallback silent"
        )

    def read(self, session_id: str, key: str) -> Any:
        raise MemoryUnavailableError(
            "AgentCore Memory runtime endpoint belum dikonfigurasi "
            f"(memory_id={self._memory_id!r}); tidak ada fallback silent"
        )


def create_memory(
    provider: str | None = None,
    memory_id: str | None = None,
    runtime_endpoint: str | None = None,
):
    """Factory memory: agentcore hanya bila dikonfigurasi penuh."""
    if provider == "agentcore":
        if not memory_id:
            raise MemoryUnavailableError(
                "AGENTCORE_MEMORY_ID kosong — AgentCore Memory tidak "
                "dapat dipakai; beri memory_id atau pakai provider local"
            )
        return AgentCoreMemoryBackend(memory_id, runtime_endpoint)
    return LocalMemoryBackend()


def memory_provider_from_env() -> str:
    """Provider aktif dari env; agentcore hanya bila ID tersedia."""
    if (os.environ.get("AGENTCORE_MEMORY_ID") or "").strip():
        return "agentcore"
    return "local"
