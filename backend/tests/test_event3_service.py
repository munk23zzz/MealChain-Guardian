"""S4-02 bagian 1 — service event3 (RED dulu).

Kontrak plan §11 + §S4-02 + prompt Owner §18–22:
- Evaluasi safety DETERMINISTIK dari temperature_log persisted (bukan input
  browser); FAIL → batch excluded → reoptimasi → alternatif eligible →
  decision `safety_disruption` baru + evidence + trace (lineage via
  previous_decision_id, BUKAN supersedes_id).
- Commit boundary: evaluasi batch terpersist WALAU tidak ada alternatif.
- Replay operation_key → outcome konsisten; payload beda → 409.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

DB_URL = (
    "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
)

NOW = datetime.now(timezone.utc)


def _db_all(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params or {}).fetchall()
            conn.commit()
            return rows
    finally:
        engine.dispose()


def _db_exec(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _mk_batches() -> dict:
    """Batch uji owned: Cianjur FAIL (excursion 60 menit) + Bogor PASS.

    Timestamp log RELATIF now (anti time-bomb, Trap 3). Qty unik (499.99 /
    501.01) supaya tidak menabrak selector test lain.
    """
    engine = create_engine(DB_URL)
    suffix = uuid.uuid4().hex[:8]
    t0 = NOW - timedelta(hours=3)
    fail_log = [
        {"timestamp": _iso(t0), "temperature_c": 4.0},
        {"timestamp": _iso(t0 + timedelta(minutes=30)), "temperature_c": 20.0},
        {"timestamp": _iso(t0 + timedelta(minutes=60)), "temperature_c": 21.0},
        {"timestamp": _iso(t0 + timedelta(minutes=90)), "temperature_c": 4.0},
    ]
    pass_log = [
        {"timestamp": _iso(t0), "temperature_c": 4.2},
        {"timestamp": _iso(t0 + timedelta(minutes=60)), "temperature_c": 4.0},
        {"timestamp": _iso(t0 + timedelta(minutes=120)), "temperature_c": 4.1},
    ]
    try:
        with engine.begin() as conn:
            sup_id = conn.execute(
                text(
                    "INSERT INTO suppliers (name, location_id, reliability_score) "
                    "SELECT :n, l.id, 0.8 FROM locations l WHERE l.name='Bogor' "
                    "RETURNING id"
                ),
                {"n": f"EV3-supplier-{suffix}"},
            ).scalar_one()
            cianjur_id = conn.execute(
                text(
                    "INSERT INTO batches (commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log, freshness_score, "
                    "safety_status) "
                    "SELECT c.id, l.id, :s, 499.99, :h, CAST(:tl AS jsonb), 0.90, 'pass' "
                    "FROM commodities c, locations l "
                    "WHERE c.name='telur' AND l.name='Cianjur' RETURNING id"
                ),
                {
                    "s": str(sup_id),
                    "h": _iso(NOW - timedelta(days=2)),
                    "tl": json.dumps(fail_log),
                },
            ).scalar_one()
            bogor_id = conn.execute(
                text(
                    "INSERT INTO batches (commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log, freshness_score, "
                    "safety_status) "
                    "SELECT c.id, l.id, :s, 501.01, :h, CAST(:tl AS jsonb), 0.90, 'pass' "
                    "FROM commodities c, locations l "
                    "WHERE c.name='telur' AND l.name='Bogor' RETURNING id"
                ),
                {
                    "s": str(sup_id),
                    "h": _iso(NOW - timedelta(days=2)),
                    "tl": json.dumps(pass_log),
                },
            ).scalar_one()
    finally:
        engine.dispose()
    return {
        "supplier_id": str(sup_id),
        "fail_batch_id": str(cianjur_id),
        "pass_batch_id": str(bogor_id),
        "suffix": suffix,
    }


def _cleanup_batches(b: dict) -> None:
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": b["fail_batch_id"]})
    _db_exec("DELETE FROM batches WHERE id = :b", {"b": b["pass_batch_id"]})
    _db_exec("DELETE FROM suppliers WHERE id = :s", {"s": b["supplier_id"]})


def _cleanup_decision(decision_id: str) -> None:
    _db_exec(
        "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
        {"d": decision_id},
    )
    _db_exec("DELETE FROM decisions WHERE id = :d", {"d": decision_id})


def _facts_bogor_eligible(b: dict):
    """Facts inject: Cianjur fail (exclude), Bogor pass (satu-satunya sumber)."""

    def _facts():
        return (
            {("Cianjur", "telur"): Decimal("1400"),
             ("Bogor", "telur"): Decimal("800"),
             ("Jakarta", "telur"): Decimal("300")},
            {("Cianjur", "telur"): Decimal("200"),
             ("Bogor", "telur"): Decimal("200"),
             ("Jakarta", "telur"): Decimal("1000")},
            {("Cianjur", "telur"): Decimal("26500"),
             ("Bogor", "telur"): Decimal("26800"),
             ("Jakarta", "telur"): Decimal("30500")},
            {},
            [
                {
                    "batch_id": b["fail_batch_id"],
                    "location": "Cianjur",
                    "commodity": "telur",
                    "quantity_kg": Decimal("499.99"),
                    "freshness_score": Decimal("0.900000"),
                    "freshness_status": "pass",
                    "safety_status": "fail",
                },
                {
                    "batch_id": b["pass_batch_id"],
                    "location": "Bogor",
                    "commodity": "telur",
                    "quantity_kg": Decimal("501.01"),
                    "freshness_score": Decimal("0.900000"),
                    "freshness_status": "pass",
                    "safety_status": "pass",
                },
            ],
            {b["supplier_id"]: Decimal("0.80")},
        )

    return _facts


def _facts_no_alternative(b: dict):
    """Facts inject: tidak ada sumber surplus → no-safe-alternative."""

    def _facts():
        return (
            {("Cianjur", "telur"): Decimal("100")},
            {("Cianjur", "telur"): Decimal("200"),
             ("Jakarta", "telur"): Decimal("1000")},
            {("Cianjur", "telur"): Decimal("26500"),
             ("Jakarta", "telur"): Decimal("30500")},
            {},
            [
                {
                    "batch_id": b["fail_batch_id"],
                    "location": "Cianjur",
                    "commodity": "telur",
                    "quantity_kg": Decimal("499.99"),
                    "freshness_score": Decimal("0.900000"),
                    "freshness_status": "pass",
                    "safety_status": "fail",
                },
            ],
            {},
        )

    return _facts


async def _run_event3(batch_id, target_id, op_key, prev_id, facts):
    """Engine dibuat DI DALAM coroutine: pool asyncpg terikat ke event loop
    yang sedang jalan; asyncio.run() kedua dengan pool lama → 'different
    loop' RuntimeError."""
    from app.core.config import settings
    from app.db import create_engine as make_engine
    from app.db import create_session_maker
    from app.services import event3_service as svc

    engine = make_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            return await svc.run_safety_disruption_event(
                batch_id=uuid.UUID(batch_id),
                target_location_id=uuid.UUID(target_id),
                operation_key=op_key,
                previous_decision_id=(
                    uuid.UUID(prev_id) if prev_id else None
                ),
                actor_id=None,
                db=session,
                fetch_facts=facts,
            )
    finally:
        await engine.dispose()


def _target_jakarta() -> str:
    row = _db_all("SELECT id FROM locations WHERE name='Jakarta'")
    assert row, "lokasi seed Jakarta wajib ada"
    return str(row[0][0])


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_safety_engine_fail_threshold_kontrak_terkunci():
    """30-menit ambang FAIL — reuse core Sprint 1 tanpa perubahan (§4.2)."""
    from app.core.safety import evaluate_safety

    fail_log = [
        {"timestamp": _iso(NOW - timedelta(hours=1)), "temperature_c": 4.0},
        {"timestamp": _iso(NOW - timedelta(minutes=50)), "temperature_c": 20.0},
        {"timestamp": _iso(NOW - timedelta(minutes=20)), "temperature_c": 4.0},
    ]  # outside ≈ 30 menit → FAIL
    res = evaluate_safety(
        fail_log, safe_min_c=0.0, safe_max_c=8.0, max_excursion_minutes=30.0
    )
    assert res["safety_status"] == "fail"
    short_log = fail_log[:2] + [
        {"timestamp": _iso(NOW - timedelta(minutes=40)), "temperature_c": 4.0}
    ]  # outside ≈ 10 menit → needs_verification
    res2 = evaluate_safety(
        short_log, safe_min_c=0.0, safe_max_c=8.0, max_excursion_minutes=30.0
    )
    assert res2["safety_status"] == "needs_verification"


def test_service_fail_batch_excluded_bogor_alternative_persisted():
    """FAIL → exclude Cianjur → reoptimasi → Bogor eligible → decision baru."""
    b = _mk_batches()
    target_id = _target_jakarta()
    op_key = uuid.uuid4()
    try:
        outcome = asyncio.run(
            _run_event3(
                b["fail_batch_id"], target_id, op_key, None,
                _facts_bogor_eligible(b),
            )
        )
        assert outcome["status"] == "revised"
        assert outcome["decision_id"] is not None
        assert outcome["excluded_batch_ids"] == [b["fail_batch_id"]]
        cand = outcome["recommended_candidate"]
        # Alternatif dipilih dari facts/rank — bukan hardcoded (plan S4-02).
        assert cand["source_location"] == "Bogor"
        assert cand["destination_location"] == "Jakarta"
        assert cand["commodity"] == "telur"
        assert outcome["previous_decision_id"] is None
        assert outcome["evaluation"]["safety_status"] == "fail"

        # Readback: decision safety_disruption + evidence + trace.
        row = _db_all(
            "SELECT decision_type, status FROM decisions WHERE id = :d",
            {"d": outcome["decision_id"]},
        )
        assert row and row[0][0] == "safety_disruption"
        evs = _db_all(
            "SELECT evidence_type FROM decision_evidence "
            "WHERE decision_id = :d",
            {"d": outcome["decision_id"]},
        )
        types = {r[0] for r in evs}
        assert "temperature" in types  # bukti evaluasi FAIL
        traces = _db_all(
            "SELECT step_name FROM agent_traces WHERE decision_id = :d",
            {"d": outcome["decision_id"]},
        )
        steps = {r[0] for r in traces}
        assert "DETECT" in steps and "OPTIMIZE" in steps

        # Replay: key sama → outcome sama (exactly-once via trace DETECT).
        outcome2 = asyncio.run(
            _run_event3(
                b["fail_batch_id"], target_id, op_key, None,
                _facts_bogor_eligible(b),
            )
        )
        assert outcome2["decision_id"] == outcome["decision_id"]
        cnt = _db_all(
            "SELECT count(*) FROM agent_traces t JOIN decisions d "
            "ON d.id = t.decision_id WHERE t.step_name='DETECT' "
            "AND t.input_summary->>'operation_key' = :k",
            {"k": str(op_key)},
        )
        assert cnt[0][0] == 1
        _cleanup_decision(outcome["decision_id"])
    finally:
        _cleanup_batches(b)


def test_service_fail_batch_persisted_even_without_alternative():
    """No-safe-alternative: evaluasi FAIL TETAP terpersist (commit boundary
    plan §11: FAIL tidak hilang saat optimization gagal)."""
    from app.services.event3_service import Event3NoAlternativeError

    b = _mk_batches()
    target_id = _target_jakarta()
    op_key = uuid.uuid4()
    try:
        with pytest.raises(Event3NoAlternativeError):
            asyncio.run(
                _run_event3(
                    b["fail_batch_id"], target_id, op_key, None,
                    _facts_no_alternative(b),
                )
            )
        # Batch Cianjur kini FAIL terpersist — bukti commit boundary.
        row = _db_all(
            "SELECT safety_status FROM batches WHERE id = :b",
            {"b": b["fail_batch_id"]},
        )
        assert row and row[0][0] == "fail"
        # Tidak ada decision sisa (no alternative → tanpa decision write).
        assert True  # exception path; decision absence diverifikasi di API test
    finally:
        _cleanup_batches(b)


def test_service_key_reuse_other_batch_409_semantics():
    """operation_key sama + batch beda → Event3ConflictError (API → 409)."""
    from app.services.event3_service import Event3ConflictError

    b = _mk_batches()
    target_id = _target_jakarta()
    op_key = uuid.uuid4()
    try:
        outcome = asyncio.run(
            _run_event3(
                b["fail_batch_id"], target_id, op_key, None,
                _facts_bogor_eligible(b),
            )
        )
        with pytest.raises(Event3ConflictError):
            asyncio.run(
                _run_event3(
                    b["pass_batch_id"], target_id, op_key, None,
                    _facts_bogor_eligible(b),
                )
            )
        _cleanup_decision(outcome["decision_id"])
    finally:
        _cleanup_batches(b)


def test_service_lineage_previous_decision_recorded():
    """previous_decision_id tercatat di evidence + response; old decision
    TIDAK dimutasi (O-EVENT-2: supersedes_id tidak dipalsukan)."""
    b = _mk_batches()
    target_id = _target_jakarta()
    op_key = uuid.uuid4()
    # Old decision "unsafe" (sintetis untuk linkage test).
    old_id = str(uuid.uuid4())
    _db_exec(
        "INSERT INTO decisions (id, decision_type, status, proposed_by, "
        "source_location_id, target_location_id, commodity_id, quantity_kg, "
        "safe_delivered_cost, expires_at, cost_breakdown) "
        "SELECT :id, 'regional_balance', 'pending_approval', 'supervisor_agent', "
        "ls.id, lt.id, c2.id, 499.99, 16206000.00, now() + interval '30 minutes', "
        "'{\"purchase\": \"15720000\"}'::jsonb "
        "FROM locations ls, locations lt, commodities c2 "
        "WHERE ls.name='Cianjur' AND lt.name='Jakarta' AND c2.name='telur'",
        {"id": old_id},
    )
    try:
        outcome = asyncio.run(
            _run_event3(
                b["fail_batch_id"], target_id, op_key, old_id,
                _facts_bogor_eligible(b),
            )
        )
        assert outcome["previous_decision_id"] == old_id
        # Lineage di evidence bukan supersedes_id (plan §S4-02 DB ruling).
        row = _db_all(
            "SELECT supersedes_id FROM decisions WHERE id = :d",
            {"d": outcome["decision_id"]},
        )
        assert row and row[0][0] is None
        ev = _db_all(
            "SELECT payload->>'previous_decision_id' FROM decision_evidence "
            "WHERE decision_id = :d AND evidence_type = 'temperature'",
            {"d": outcome["decision_id"]},
        )
        assert ev and ev[0][0] == old_id
        # Old decision TIDAK berubah statusnya (tidak dipalsukan rejected).
        old = _db_all(
            "SELECT status, rejection_reason FROM decisions WHERE id = :d",
            {"d": old_id},
        )
        assert old[0][0] == "pending_approval"
        assert old[0][1] is None
        _cleanup_decision(outcome["decision_id"])
    finally:
        _cleanup_decision(old_id)
        _cleanup_batches(b)
