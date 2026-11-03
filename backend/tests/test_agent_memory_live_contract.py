"""Kontrak jalur LIVE AgentCore Memory tanpa memanggil AWS (Fase 11 MG butir 5-6).

Melengkapi `test_agent_memory_isolation.py` (isolasi + sanitasi backend lokal &
AgentCore tiruan) dengan kontrak yang HANYA relevan pada jalur nyata:

1. Namespace yang dipakai aplikasi = `"<demo_session_id>:<decision_id>"`.
2. Adapter mengirim pasangan `actorId` + `sessionId` (bentuk API AgentCore),
   dan payload yang dikirim sudah disanitasi — tidak ada secret.
3. `CreateEvent` yang ditolak IAM TIDAK PERNAH dilaporkan `saved`; hasilnya
   `unavailable` dan tidak melempar ke pemanggil (butir 6).
4. Modul tes live benar-benar opt-in: suite hijau TIDAK boleh dibaca sebagai
   bukti AWS. Tanpa `RUN_LIVE_AGENTCORE=1`, `test_agent_memory_live.py` harus
   skip, bukan lulus.

Tidak ada panggilan jaringan di berkas ini.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.agent_memory import (
    AgentCoreMemoryBackend,
    MemoryUnavailableError,
    catat_learn,
)

_TESTS_DIR = Path(__file__).resolve().parent


def _klien_tiruan_error(kode: str, operasi: str = "CreateEvent") -> MagicMock:
    """Klien boto3 tiruan yang menolak seperti IAM (AccessDeniedException)."""

    class _DeniedError(Exception):
        response = {"Error": {"Code": kode, "Message": f"not authorized: {operasi}"}}

    klien = MagicMock()
    klien.create_event.side_effect = _DeniedError("AccessDeniedException")
    return klien


# ---------------------------------------------------------------------------
# 1. Namespace
# ---------------------------------------------------------------------------


def test_namespace_jalur_learn_adalah_demo_session_plus_decision():
    """Aplikasi memakai `"<demo_session_id>:<decision_id>"`, bukan satu sesi global."""
    sumber = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "event1_orchestrator.py"
    ).read_text(encoding="utf-8")
    assert "demo_session_id or 'sesi-lokal'" in sumber, (
        "namespace LEARN harus memakai demo_session_id (dengan fallback eksplisit)"
    )
    assert "}:{decision.id}" in sumber, (
        "namespace LEARN harus menyertakan decision.id supaya sesi tidak tercampur"
    )


def test_describe_menyertakan_actor_dan_session_yang_dikirim_ke_aws():
    mem = AgentCoreMemoryBackend(
        memory_id="mealchain_memory_uji", actor_id="aktor-uji", region="us-west-2"
    )
    info = mem.describe("/demo/abc:decision-123", "learn")
    assert info["provider"] == "agentcore"
    assert info["session_id"] == "/demo/abc:decision-123"
    assert info["actor_id"] == "aktor-uji"
    assert ":" in info["session_id"] and info["session_id"].count(":") == 1


# ---------------------------------------------------------------------------
# 2. Muatan nyata yang dikirim ke API
# ---------------------------------------------------------------------------


def test_create_event_mengirim_actor_session_dan_payload_tersanitasi():
    mem = AgentCoreMemoryBackend(memory_id="mealchain_memory_uji", actor_id="aktor-uji")
    klien = MagicMock()
    mem._client = klien  # noqa: SLF001 - klien disuntik untuk kontrak ini

    mem.write(
        "/demo/abc:decision-123",
        "learn",
        {
            "decision_id": "decision-123",
            "commodity": "telur",
            "safe_delivered_cost": 12_500_000,
            "password": "jangan-disimpan",
            "nested": {"api_key": "sk-uji", "catatan": "aman"},
        },
    )

    kwargs = klien.create_event.call_args.kwargs
    assert kwargs["memoryId"] == "mealchain_memory_uji"
    assert kwargs["actorId"] == "aktor-uji"
    assert kwargs["sessionId"] == "/demo/abc:decision-123"
    assert kwargs["metadata"] == {"key": {"stringValue": "learn"}}

    teks = kwargs["payload"][0]["conversational"]["content"]["text"]
    muatan = json.loads(teks)
    assert muatan["key"] == "learn"
    assert muatan["value"]["commodity"] == "telur"
    assert muatan["value"]["nested"]["catatan"] == "aman"
    for terlarang in ("password", "api_key", "sk-uji", "jangan-disimpan"):
        assert terlarang not in teks.lower(), f"secret masuk ke payload: {terlarang}"


def test_read_mengambil_event_terbaru_untuk_kunci_yang_sama():
    mem = AgentCoreMemoryBackend(memory_id="mealchain_memory_uji", actor_id="aktor-uji")

    def _event(isi: dict[str, Any]) -> dict:
        return {
            "eventId": "e1",
            "payload": [
                {
                    "conversational": {
                        "role": "ASSISTANT",
                        "content": {"text": json.dumps(isi)},
                    }
                }
            ],
        }

    klien = MagicMock()
    klien.list_events.return_value = {
        "events": [
            _event({"key": "learn", "value": {"commodity": "telur", "putaran": 1}}),
            _event({"key": "learn", "value": {"commodity": "telur", "putaran": 2}}),
            _event({"key": "lain", "value": {"commodity": "beras"}}),
        ]
    }
    mem._client = klien  # noqa: SLF001

    assert mem.read("/demo/abc:decision-123", "learn") == {
        "commodity": "telur",
        "putaran": 2,
    }
    assert mem.list_keys("/demo/abc:decision-123") == ["lain", "learn"]


# ---------------------------------------------------------------------------
# 3. IAM menolak → `unavailable`, bukan `saved`
# ---------------------------------------------------------------------------


def test_create_event_ditolak_iam_melempar_unavailable_yang_jelas():
    mem = AgentCoreMemoryBackend(memory_id="mealchain_memory_uji")
    mem._client = _klien_tiruan_error("AccessDeniedException")  # noqa: SLF001

    with pytest.raises(MemoryUnavailableError) as galat:
        mem.write("/demo/abc:decision-123", "learn", {"commodity": "telur"})
    pesan = str(galat.value)
    assert "CreateEvent" in pesan or "AccessDenied" in pesan
    assert "memory_id" in pesan


def test_catat_learn_ditolak_iam_tidak_pernah_dilaporkan_saved(monkeypatch):
    monkeypatch.setenv("AGENTCORE_MEMORY_ID", "mealchain_memory_uji")
    monkeypatch.delenv("AGENT_MEMORY_WRITE", raising=False)

    def _tolak(*_args, **_kwargs):
        raise MemoryUnavailableError(
            "AccessDeniedException: no identity-based policy allows "
            "bedrock-agentcore:CreateEvent"
        )

    monkeypatch.setattr(
        "app.services.agent_memory.AgentCoreMemoryBackend.write", _tolak, raising=True
    )

    status = catat_learn("/demo/abc:decision-123", "learn", {"commodity": "telur"})
    assert status["status"] == "unavailable", status
    assert status["provider"] == "agentcore"
    assert status["session_id"] == "/demo/abc:decision-123"
    assert "AccessDenied" in status["detail"]
    assert status.get("saved") is None


def test_catat_learn_tanpa_memory_id_tidak_mengarang_provider_agentcore(monkeypatch):
    monkeypatch.delenv("AGENTCORE_MEMORY_ID", raising=False)
    status = catat_learn("/demo/abc:decision-123", "learn", {"commodity": "telur"})
    assert status["provider"] == "local"
    assert status["status"] == "saved"


# ---------------------------------------------------------------------------
# 4. Bukti live tidak boleh disamarkan sebagai suite hijau
# ---------------------------------------------------------------------------


def _muat_modul_live():
    jalur = _TESTS_DIR / "test_agent_memory_live.py"
    spec = importlib.util.spec_from_file_location("_kontrak_memory_live", jalur)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_modul_live_opt_in_dan_skip_tanpa_izin(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_AGENTCORE", raising=False)
    modul = _muat_modul_live()
    marks = modul.pytestmark
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    syarat = [m for m in marks if m.name == "skipif"]
    assert syarat, "test_agent_memory_live.py wajib opt-in (skipif RUN_LIVE_AGENTCORE)"
    assert syarat[0].args[0] is True, (
        "tanpa RUN_LIVE_AGENTCORE modul live harus SKIP, bukan lulus"
    )
    nama = {n for n in dir(modul) if n.startswith("test_")}
    assert "test_tulis_baca_agentcore_memory_nyata" in nama, (
        "tes live wajib membuktikan tulis-baca nyata, bukan hanya kontrak"
    )


def test_tidak_ada_tes_live_yang_menulis_tanpa_membersihkan():
    sumber = (_TESTS_DIR / "test_agent_memory_live.py").read_text(encoding="utf-8")
    assert "finally:" in sumber, "tes live harus membersihkan event di blok finally"
    assert "purge(" in sumber, "tes live harus memanggil purge (DeleteEvent)"


def test_default_demo_tidak_menulis_memory(monkeypatch):
    """Default demo: LEARN tidak menulis Memory sebelum izin tulis ada."""
    from app.services.event1_orchestrator import _memory_write_aktif

    monkeypatch.delenv("AGENT_MEMORY_WRITE", raising=False)
    assert _memory_write_aktif() is False

    monkeypatch.setenv("AGENT_MEMORY_WRITE", "1")
    assert _memory_write_aktif() is True
