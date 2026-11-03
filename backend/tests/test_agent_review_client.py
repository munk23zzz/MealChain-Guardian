"""Kontrak klien review backend → runtime (tanpa AWS/AgentCore nyata)."""

from __future__ import annotations

import json
import time

from app.services.agent_review_client import review_decision


def _payload(run_id: str = "run-1") -> dict:
    return {
        "run_id": run_id,
        "decision_id": "decision-1",
        "mode": "advisory",
        "status": "completed",
        "findings": [{} for _ in range(7)],
        "contradictions": [],
        "safety_veto": False,
        "narrative": "review selesai",
    }


def test_runtime_kosong_tidak_mengarang(monkeypatch) -> None:
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)

    result = review_decision("decision-1")

    assert result.status == "unavailable"
    assert result.run_id is None
    assert result.payload is None


def test_parse_review_tujuh_finding() -> None:
    result = review_decision(
        "decision-1", caller=lambda prompt: json.dumps(_payload("run-42"))
    )

    assert result.status == "completed"
    assert result.run_id == "run-42"
    assert result.payload is not None
    assert len(result.payload["findings"]) == 7


def test_parse_nested_review_dan_status_partial() -> None:
    body = {"review": {**_payload("run-7"), "status": "partial"}}

    result = review_decision("decision-1", caller=lambda prompt: json.dumps(body))

    assert result.status == "partial"
    assert result.run_id == "run-7"


def test_payload_bukan_tujuh_finding_ditolak() -> None:
    body = {**_payload("run-1"), "findings": [{}]}

    result = review_decision("decision-1", caller=lambda prompt: json.dumps(body))

    assert result.status == "failed"
    assert "7 finding" in (result.error or "")


def test_caller_error_menjadi_failed() -> None:
    def _boom(prompt: str) -> str:
        raise RuntimeError("runtime mati")

    result = review_decision("decision-1", caller=_boom)

    assert result.status == "failed"
    assert "runtime mati" in (result.error or "")


def test_timeout_tidak_menunggu_selamanya() -> None:
    def _slow(prompt: str) -> str:
        time.sleep(0.2)
        return json.dumps(_payload("run-lambat"))

    result = review_decision("decision-1", caller=_slow, timeout_seconds=0.01)
    time.sleep(0.25)

    assert result.status == "timeout"
    assert result.run_id is None
