"""Test Event 1 orchestration (S3-04, TDD).

Alur DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE:
- DETECT dari data seed nyata (Cianjur surplus telur → Jakarta shortage)
- VERIFY memakai run_verifier (S3-06); provider kosong → UNAVAILABLE
- TRACE menulis AgentTrace dengan nama tool/step ASLI (bukan teks buatan)
- PREDICT memakai run_forecast (S3-07) + fallback statistik core
- OPTIMIZE memakai rekomendasi deterministik (score/SDC = output backend)
- DECIDE menyimpan Decision status `proposed`, expiry terisi, TIDAK
  pernah auto-approve, tidak ada eksekusi otomatis.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


def _db():
    return create_engine(DB_URL)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _cleanup(decision_id: str | None) -> None:
    if decision_id is None:
        return
    engine = _db()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM agent_traces WHERE decision_id = :d"),
                {"d": decision_id},
            )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id}
            )
    finally:
        engine.dispose()


def _persisted_status(decision_id: str) -> str | None:
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(
                text("SELECT status FROM decisions WHERE id = :d"),
                {"d": decision_id},
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _trace_rows(decision_id: str) -> list[dict]:
    engine = _db()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT step_name, tool_called, input_summary, "
                    "output_summary, step_at FROM agent_traces "
                    "WHERE decision_id = :d "
                    "ORDER BY step_at ASC, id ASC"
                ),
                {"d": decision_id},
            ).mappings().all()
            return [dict(r) for r in rows]
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Skenario 1: provider kosong (unit deterministik penuh)
# ---------------------------------------------------------------------------


def test_event1_unverified_full_flow_persists_proposed(client):
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")

    try:
        # DETECT: surplus sumber nyata → Jakarta shortage (engine menentukan
        # sumber terbaik; seed memuat surplus telur Bogor/Cianjur)
        surplus_loc = outcome["detect"]["surplus"]["location"]
        assert surplus_loc in {"Bogor", "Cianjur"}
        assert Decimalish(outcome["detect"]["surplus"]["quantity_kg"]) > 0
        assert outcome["detect"]["shortage"]["location"] == "Jakarta"
        assert Decimalish(outcome["detect"]["shortage"]["quantity_kg"]) > 0

        # VERIFY: verifier UNAVAILABLE (tanpa provider terpasang)
        assert outcome["verifier"]["verdict"] == "UNAVAILABLE"
        assert outcome["verifier"]["attempts"] == []

        # OPTIMIZE: kandidat memakai angka deterministik backend
        chosen = outcome["decision_snapshot"]["recommendation"]
        assert chosen["eligible"] is True
        recs = outcome["recommendations"]
        by_id = {r["candidate_id"]: r for r in recs}
        assert chosen["score"] == by_id[chosen["candidate_id"]]["score"]
        assert (
            chosen["safe_delivered_cost"]
            == by_id[chosen["candidate_id"]]["safe_delivered_cost"]
        )
        # kandidat ineligible tidak pernah masuk rekomendasi
        assert all(r["eligible"] for r in recs)
        # chosen = kandidat eligible peringkat terbaik utk komoditas+tujuan
        pool = [
            r
            for r in recs
            if r["candidate"]["commodity"] == "telur"
            and r["candidate"]["destination_location"] == "Jakarta"
        ]
        best = min(pool, key=lambda r: r["rank"])
        assert chosen["candidate_id"] == best["candidate_id"]
        # DETECT konsisten dengan kandidat terpilih (sumber surplus sama)
        assert surplus_loc == chosen["candidate"]["source_location"]

        # DECIDE: persisted `proposed`, expiry terisi, TIDAK approved
        decision_id = outcome["decision_id"]
        assert _persisted_status(decision_id) == "proposed"
        snap = outcome["decision_snapshot"]
        assert snap["expires_at"] is not None
        exp = datetime.fromisoformat(snap["expires_at"])
        assert exp.tzinfo is not None and exp > datetime.now(timezone.utc)
        status = outcome["decision_snapshot"]["status"]
        assert status in {"proposed", "pending_approval"}
        assert outcome["decision_snapshot"].get("approved") is not True
    finally:
        _cleanup(outcome.get("decision_id"))


def test_event1_unverified_persists_agent_traces_with_real_steps(client):
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        rows = _trace_rows(outcome["decision_id"])
        steps = [r["step_name"] for r in rows]
        for expected in ("DETECT", "VERIFY", "TRACE", "PREDICT", "OPTIMIZE", "DECIDE"):
            assert expected in steps
        # PREDICT mengisi forecast: fallback statistik, bukan angka karangan
        predict = next(r for r in rows if r["step_name"] == "PREDICT")
        out = predict["output_summary"] or {}
        assert out.get("forecast_qty_kg") is not None
        assert out.get("method") in {"sap_rpt_1_6", "statistical_fallback"}
        # VERIFY merekam verdict UNAVAILABLE, bukan klaim keberhasilan model
        verify = next(r for r in rows if r["step_name"] == "VERIFY")
        vout = verify["output_summary"] or {}
        assert vout.get("verdict") == "UNAVAILABLE"
        assert vout.get("provider") is None
        # OPTIMIZE mencatat tool deterministik yang benar
        optimize = next(r for r in rows if r["step_name"] == "OPTIMIZE")
        assert optimize["tool_called"] == "balance.recommend"
    finally:
        _cleanup(outcome.get("decision_id"))


def test_event1_expiry_enforced_later(client):
    """Decision Event 1 harus punya expires_at yang nanti dipakai guard."""
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        engine = _db()
        with engine.begin() as conn:
            exp = conn.execute(
                text("SELECT expires_at FROM decisions WHERE id = :d"),
                {"d": outcome["decision_id"]},
            ).scalar_one()
        assert exp is not None  # NOT NULL — kontrak Schema.md
        engine.dispose()
    finally:
        _cleanup(outcome.get("decision_id"))


# ---------------------------------------------------------------------------
# Skenario 2: verifier sink yang menjawab (injeksi callable S3-06)
# ---------------------------------------------------------------------------


def test_event1_consistent_verdict_records_verifier_attempt(client):
    from app.services.event1_orchestrator import run_event1

    def bedrock_ok(prompt):
        return '{"verdict": "CONSISTENT", "reason": "evidence konsisten"}'

    outcome = run_event1(
        commodity="telur",
        target_location="Jakarta",
        verifier_bedrock=bedrock_ok,
    )
    try:
        assert outcome["verifier"]["verdict"] == "CONSISTENT"
        # jejak provider jujur: bedrock tersuntik menempati slot `primary`
        # chain yang aktif (label = slot aktual, bukan klaim nomor fallback)
        assert [a["name"] for a in outcome["verifier"]["attempts"]] == [
            "primary"
        ]
        # DECIDE dengan verdict CONSISTENT tetap status lifecycle sah,
        # tanpa approval otomatis
        assert _persisted_status(outcome["decision_id"]) in {
            "proposed",
            "pending_approval",
        }
    finally:
        _cleanup(outcome.get("decision_id"))


def test_event1_safety_fail_never_consistent(client):
    """Guard: safety FAIL core tidak bisa diangkat model (S3-06 dipakai ulang)."""
    from app.services.event1_orchestrator import run_event1

    def stubborn_model(prompt):
        return '{"verdict": "CONSISTENT"}'

    outcome = run_event1(
        commodity="telur",
        target_location="Jakarta",
        verifier_bedrock=stubborn_model,
        safety_status_override="FAIL",
    )
    try:
        # guard menurunkan klaim model → FLAGGED (bukan CONSISTENT)
        assert outcome["verifier"]["verdict"] == "FLAGGED"
        # decision tetap tersimpan tanpa eksekusi (guard bukan jalur approve)
        assert _persisted_status(outcome["decision_id"]) in {
            "proposed",
            "pending_approval",
        }
    finally:
        _cleanup(outcome.get("decision_id"))


def test_event1_no_auto_execution(client):
    """Tidak ada eksekusi otomatis: tidak ada PO mock, status bukan executed."""
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        engine = _db()
        with engine.begin() as conn:
            po = conn.execute(
                text(
                    "SELECT COUNT(*) FROM sap_mock_purchase_orders "
                    "WHERE decision_id = :d"
                ),
                {"d": outcome["decision_id"]},
            ).scalar_one()
        engine.dispose()
        assert po == 0
        assert _persisted_status(outcome["decision_id"]) != "executed"
    finally:
        _cleanup(outcome.get("decision_id"))


def test_event1_kpi_traceable_to_backend_outputs(client):
    """Semua angka di KPI/outcome harus bersumber output tools."""
    from app.services.event1_orchestrator import run_event1

    outcome = run_event1(commodity="telur", target_location="Jakarta")
    try:
        recs = outcome["recommendations"]
        kpi = outcome["kpi"]
        # nilai KPI = agregasi dari rekomendasi deterministik
        assert kpi["candidates_total"] == len(recs)
        assert kpi["eligible"] == sum(1 for r in recs if r["eligible"])
        chosen = outcome["decision_snapshot"]["recommendation"]
        assert Decimalish(chosen["safe_delivered_cost"]) >= 0
        assert Decimalish(chosen["score"]) >= 0
    finally:
        _cleanup(outcome.get("decision_id"))


class Decimalish(float):
    """Bandingkan angka dari string/Decimal tanpa drama floating point."""

    def __new__(cls, value):
        return super().__new__(cls, str(value))
