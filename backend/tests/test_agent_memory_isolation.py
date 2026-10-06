"""Test AgentCore Memory adapter (S3-08, TDD).

Kontrak:
- Session A dan B TIDAK bisa membaca state satu sama lain.
- Key memori menyertakan identitas session/decision.
- Payload disanitasi: secret/credential tidak boleh tersimpan.
- Provider AgentCore tidak dikonfigurasi → unavailable EKSPLISIT
  (tidak diam-diam memakai state global bersama).
"""

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


def test_agentcore_backend_with_config_unavailable_is_explicit_on_use():
    """Adapter AgentCore terpasang tapi runtime tidak dapat dihubungi →
    error eksplisit saat dipakai, bukan fallback diam ke state global."""
    mem = create_memory(
        provider="agentcore", memory_id="mem-xyz", runtime_endpoint=None
    )
    with pytest.raises(MemoryUnavailableError):
        mem.write("session-A", "plan", {"step": "DETECT"})
