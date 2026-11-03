"""Test Observability trace contract (S3-09, TDD).

Kontrak:
- Trace aktual memuat: supervisor invocation, tool call/result, model
  call, fallback HANYA bila terjadi, timestamp, decision context.
- Test double/sintetis diberi label `synthetic` dan tidak boleh
  dipromosikan sebagai bukti produksi.
- Sink AgentCore Observability tidak dikonfigurasi → error eksplisit.
"""

import pytest

from app.services.agent_observability import (
    ObservabilityUnavailableError,
    TraceRecorder,
    create_observability_sink,
)


def test_trace_contains_required_event_kinds_with_timestamps():
    rec = TraceRecorder(decision_id="dec-1")
    rec.record_supervisor_invocation(model="us.anthropic.test")
    rec.record_tool_call(
        tool="balance.recommend", request={"commodity": "telur"},
        result={"candidates": 2},
    )
    rec.record_model_call(provider="bedrock_final", outcome="succeeded")

    events = rec.events()
    kinds = [e["kind"] for e in events]
    assert kinds == ["supervisor_invocation", "tool_call", "model_call"]
    for e in events:
        assert e["event_at"]  # timestamp ISO terisi
        assert e["decision_id"] == "dec-1"


def test_fallback_recorded_only_when_it_occurs():
    rec = TraceRecorder(decision_id="dec-1")
    rec.record_model_call(provider="primary", outcome="succeeded")
    assert [e["kind"] for e in rec.events()] == ["model_call"]
    # tidak ada event fallback yang direkayasa dari udara
    assert not any(e["kind"] == "fallback" for e in rec.events())

    rec.record_fallback(from_provider="primary", to_provider="fallback_1")
    kinds = [e["kind"] for e in rec.events()]
    assert kinds[-1] == "fallback"


def test_tool_call_records_result_summary():
    rec = TraceRecorder(decision_id="dec-1")
    rec.record_tool_call(
        tool="cost.safe_delivered", request={"freshness": "0.90"},
        result={"total": "16206000.00"},
    )
    event = rec.events()[0]
    assert event["tool"] == "cost.safe_delivered"
    assert event["request"] == {"freshness": "0.90"}
    assert event["result"] == {"total": "16206000.00"}


def test_synthetic_entries_labeled_and_not_promoted():
    rec = TraceRecorder(decision_id="dec-1")
    rec.record_supervisor_invocation(model="us.anthropic.test")
    rec.record_tool_call(
        tool="balance.recommend", request={}, result={},
        synthetic=True,  # test double eksplisit
    )
    events = rec.events()
    assert events[1]["synthetic"] is True
    assert events[0]["synthetic"] is False
    with pytest.raises(Exception) as excinfo:
        rec.assert_production_ready()
    assert "synthetic" in str(excinfo.value).lower()
    # tanpa sintetis → siap dipromosikan
    rec2 = TraceRecorder(decision_id="dec-2")
    rec2.record_supervisor_invocation(model="m")
    rec2.assert_production_ready()  # tidak raise


def test_decision_context_attached():
    rec = TraceRecorder(
        decision_id="dec-1",
        context={"commodity": "telur", "target_location": "Jakarta"},
    )
    rec.record_tool_call(tool="supply.get", request={}, result={})
    event = rec.events()[0]
    assert event["context"] == {
        "commodity": "telur",
        "target_location": "Jakarta",
    }


def test_agentcore_sink_unconfigured_is_explicit():
    with pytest.raises(ObservabilityUnavailableError) as excinfo:
        create_observability_sink(provider="agentcore", endpoint=None)
    assert "endpoint" in str(excinfo.value).lower()


def test_local_sink_ships_recorded_events():
    rec = TraceRecorder(decision_id="dec-1")
    rec.record_model_call(provider="primary", outcome="succeeded")
    sink = create_observability_sink(provider="local")
    shipped = sink.ship(rec)
    assert len(shipped) == 1
    assert shipped[0]["kind"] == "model_call"
