"""Test AgentCore Memory adapter (S3-08, TDD).

Kontrak:
- Session A dan B TIDAK bisa membaca state satu sama lain.
- Key memori menyertakan identitas session/decision.
- Payload disanitasi: secret/credential tidak boleh tersimpan.
- Provider AgentCore tidak dikonfigurasi → unavailable EKSPLISIT
  (tidak diam-diam memakai state global bersama).
"""

from unittest.mock import MagicMock

import pytest

from app.services.agent_memory import (
    LocalMemoryBackend,
    MemoryUnavailableError,
    create_memory,
    sanitize_memory_payload,
)


def test_sessions_a_and_b_cannot_read_each_other():
    mem = LocalMemoryBackend()
    mem.write("session-A", "plan", {"step": "DETECT"})
    mem.write("session-B", "plan", {"step": "OPTIMIZE"})

    assert mem.read("session-A", "plan") == {"step": "DETECT"}
    assert mem.read("session-B", "plan") == {"step": "OPTIMIZE"}
    # A tidak melihat milik B untuk key lain
    mem.write("session-B", "private", {"x": 1})
    assert mem.read("session-A", "private") is None


def test_missing_key_returns_none_not_shared_state():
    mem = LocalMemoryBackend()
    mem.write("session-A", "context", {"commodity": "telur"})
    assert mem.read("session-A", "tidak_ada") is None
    # session baru tanpa write apa pun
    assert mem.read("session-Z", "context") is None


def test_keys_carry_session_identity_in_storage():
    mem = LocalMemoryBackend()
    mem.write("decision-123", "snapshot", {"rank": 1})
    listing = mem.list_keys("decision-123")
    assert listing == ["snapshot"]
    # identitas session eksplisit pada metadata rekaman
    assert mem.describe("decision-123", "snapshot")["session_id"] == (
        "decision-123"
    )


def test_payload_sanitized_no_secrets():
    dirty = {
        "commodity": "telur",
        "credentials": {"aws_secret_access_key": "x"},
        "nested": {"api_key": "sk-123", "note": "ok"},
        "Authorization": "Bearer abc",
        "password": "pw",
    }
    clean = sanitize_memory_payload(dirty)
    assert clean["commodity"] == "telur"
    assert "credentials" not in clean
    assert "api_key" not in clean["nested"]
    assert clean["nested"]["note"] == "ok"
    assert "Authorization" not in clean
    assert "password" not in clean
    # write juga otomatis menyanitasi
    mem = LocalMemoryBackend()
    mem.write("s1", "leak", {"token": "rahasia", "data": 1})
    assert mem.read("s1", "leak") == {"data": 1}


def test_agentcore_backend_without_config_is_explicitly_unavailable():
    with pytest.raises(MemoryUnavailableError) as excinfo:
        create_memory(provider="agentcore", memory_id=None)
    assert "AGENTCORE_MEMORY_ID" in str(excinfo.value)


def test_create_memory_local_default_is_explicit_about_provider():
    mem = create_memory(provider=None, memory_id=None)
    assert mem.provider == "local"  # jujur: bukan klaim AgentCore


def test_catat_learn_tanpa_kredensial_melapor_tanpa_melempar(monkeypatch):
    """Butir 6: kegagalan Memory dilaporkan sebagai status, bukan exception."""
    from app.services.agent_memory import catat_learn

    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "mem-uji")
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tidak-ada")
    monkeypatch.setenv("AWS_CONFIG_FILE", "/tidak-ada")

    status = catat_learn("sesi-tanpa-izin", "learn", {"commodity": "telur"})
    assert status["status"] in {"unavailable", "error"}
    assert status["key"] == "learn"
    assert "commodity" not in status


def test_agentcore_backend_reports_client_error_explicitly():
    """Adapter AgentCore nyata: galat AWS → error eksplisit, bukan fallback diam."""
    from botocore.exceptions import ClientError

    mem = create_memory(provider="agentcore", memory_id="mem-xyz", runtime_endpoint=None)
    klien = MagicMock()
    klien.create_event.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "CreateEvent"
    )
    mem._client = klien
    with pytest.raises(MemoryUnavailableError) as excinfo:
        mem.write("session-A", "plan", {"step": "DETECT"})
    assert "mem-xyz" in str(excinfo.value)
    assert "AccessDeniedException" in str(excinfo.value)


def test_agentcore_backend_namespace_isolates_sessions():
    """Tulis di sesi A tidak terbaca dari sesi B — memakai API actor+session."""
    import datetime as dt
    import json

    tersimpan: dict[str, list] = {}

    def _create_event(**kwargs):
        tersimpan.setdefault(kwargs["sessionId"], []).append(
            {
                "eventId": f"ev-{len(tersimpan[kwargs['sessionId']])}",
                "payload": kwargs["payload"],
            }
        )
        return {"eventId": "ev-x", "eventTimestamp": dt.datetime.now(dt.UTC)}

    def _list_events(**kwargs):
        return {"events": tersimpan.get(kwargs["sessionId"], [])}

    mem = create_memory(provider="agentcore", memory_id="mem-xyz", runtime_endpoint=None)
    klien = MagicMock()
    klien.create_event.side_effect = _create_event
    klien.list_events.side_effect = _list_events
    mem._client = klien

    mem.write("session-A", "plan", {"step": "DETECT", "password": "bocor"})
    assert mem.read("session-A", "plan") == {"step": "DETECT"}
    assert mem.read("session-B", "plan") is None
    # payload yang dikirim ke AWS sudah disanitasi
    teks = tersimpan["session-A"][0]["payload"][0]["conversational"]["content"]["text"]
    assert "bocor" not in teks
    assert json.loads(teks)["key"] == "plan"
