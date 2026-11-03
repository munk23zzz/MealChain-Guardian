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

    def purge(self, session_id: str) -> int:
        """Hapus semua kunci sesi ini (dipakai tes)."""
        kunci = [k for k in self._store if k[0] == session_id]
        for k in kunci:
            del self._store[k]
        return len(kunci)


class AgentCoreMemoryBackend:
    """Adapter AgentCore Memory — data plane nyata (`bedrock-agentcore`).

    Namespace = satu sesi (`sessionId`) milik satu aktor (`actorId`), sesuai
    bentuk API AgentCore: `CreateEvent`/`ListEvents`/`DeleteEvent` selalu
    meminta pasangan actor+session. Kunci (`key`) disimpan di `metadata` dan di
    isi payload, sehingga sesi lain tidak dapat membacanya walau tahu kuncinya.

    Bila kredensial/izin tidak ada, operasi melempar `MemoryUnavailableError`
    dengan sebab apa adanya — tidak pernah fallback diam ke state bersama.
    """

    provider = "agentcore"

    def __init__(
        self,
        memory_id: str,
        runtime_endpoint: str | None = None,
        actor_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self._memory_id = memory_id
        self._runtime_endpoint = (runtime_endpoint or "").strip()
        self._actor_id = (
            actor_id
            or os.environ.get("AGENTCORE_MEMORY_ACTOR")
            or "mealchain-guardian"
        ).strip()
        self._region = (region or os.environ.get("AWS_REGION") or "us-west-2").strip()
        self._client = None

    # -- infrastruktur ------------------------------------------------------
    def _klien(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - tergantung image
                raise MemoryUnavailableError(
                    f"boto3 tidak tersedia untuk AgentCore Memory: {exc}"
                ) from exc
            self._client = boto3.client("bedrock-agentcore", region_name=self._region)
        return self._client

    def _session(self, session_id: str) -> str:
        return session_id

    # -- operasi ------------------------------------------------------------
    def write(self, session_id: str, key: str, value: Any) -> None:
        import datetime as _dt
        import json as _json

        bersih = sanitize_memory_payload(value)
        try:
            self._klien().create_event(
                memoryId=self._memory_id,
                actorId=self._actor_id,
                sessionId=self._session(session_id),
                eventTimestamp=_dt.datetime.now(_dt.UTC),
                payload=[
                    {
                        "conversational": {
                            "role": "ASSISTANT",
                            "content": {
                                "text": _json.dumps(
                                    {"key": key, "value": bersih},
                                    ensure_ascii=False,
                                    sort_keys=True,
                                )
                            },
                        }
                    }
                ],
                metadata={"key": {"stringValue": key}},
            )
        except MemoryUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - dilaporkan sebagai tak tersedia
            raise MemoryUnavailableError(
                f"AgentCore Memory write gagal (memory_id={self._memory_id!r}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def _events(self, session_id: str) -> list[dict]:
        try:
            resp = self._klien().list_events(
                memoryId=self._memory_id,
                actorId=self._actor_id,
                sessionId=self._session(session_id),
                includePayloads=True,
                maxResults=50,
            )
        except MemoryUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MemoryUnavailableError(
                f"AgentCore Memory read gagal (memory_id={self._memory_id!r}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return resp.get("events", [])

    @staticmethod
    def _isi_event(event: dict) -> dict | None:
        import json as _json

        for item in event.get("payload", []) or []:
            teks = ((item.get("conversational") or {}).get("content") or {}).get("text")
            if not teks:
                continue
            try:
                muatan = _json.loads(teks)
            except _json.JSONDecodeError:
                continue
            if isinstance(muatan, dict) and "key" in muatan:
                return muatan
        return None

    def read(self, session_id: str, key: str) -> Any:
        terbaru = None
        for event in self._events(session_id):
            muatan = self._isi_event(event)
            if muatan is not None and muatan.get("key") == key:
                terbaru = muatan.get("value")
        return terbaru

    def list_keys(self, session_id: str) -> list[str]:
        keys = set()
        for event in self._events(session_id):
            muatan = self._isi_event(event)
            if muatan and muatan.get("key"):
                keys.add(str(muatan["key"]))
        return sorted(keys)

    def describe(self, session_id: str, key: str) -> dict:
        return {
            "provider": self.provider,
            "memory_id": self._memory_id,
            "actor_id": self._actor_id,
            "session_id": self._session(session_id),
            "key": key,
            "region": self._region,
        }

    def purge(self, session_id: str) -> int:
        """Hapus semua event sesi ini (dipakai tes; bukan jalur aplikasi)."""
        jumlah = 0
        klien = self._klien()
        for event in self._events(session_id):
            event_id = event.get("eventId")
            if not event_id:
                continue
            klien.delete_event(
                memoryId=self._memory_id,
                actorId=self._actor_id,
                sessionId=self._session(session_id),
                eventId=event_id,
            )
            jumlah += 1
        return jumlah


def create_memory(
    provider: str | None = None,
    memory_id: str | None = None,
    runtime_endpoint: str | None = None,
) -> LocalMemoryBackend | AgentCoreMemoryBackend:
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


def catat_learn(session_id: str, key: str, value: Any) -> dict:
    """Simpan pelajaran LEARN ke Memory; TIDAK PERNAH melempar exception.

    Fase 11 butir 6: kegagalan Memory tidak boleh mengubah verdict, angka, atau
    keputusan. Pemanggil mendapat laporan status (`saved`/`unavailable`/`error`)
    untuk ditulis ke jejak, bukan exception yang menggagalkan permintaan.
    """
    provider = memory_provider_from_env()
    try:
        mem = create_memory(provider, os.environ.get("AGENTCORE_MEMORY_ID"))
        mem.write(session_id, key, value)
        return {
            "provider": provider,
            "status": "saved",
            "session_id": session_id,
            "key": key,
        }
    except MemoryUnavailableError as exc:
        return {
            "provider": provider,
            "status": "unavailable",
            "session_id": session_id,
            "key": key,
            "detail": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - butir 6: jangan memutus alur
        return {
            "provider": provider,
            "status": "error",
            "session_id": session_id,
            "key": key,
            "detail": f"{type(exc).__name__}: {exc}",
        }
