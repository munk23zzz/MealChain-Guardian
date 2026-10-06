"""Test trace persistence service (S3-10, TDD).

Kontrak:
- satu row AgentTrace per langkah aktual, FK decision valid;
- payload input/output DISANITASI (secret tidak boleh masuk DB);
- step_name di luar whitelist ditolak eksplisit (bukan didrop diam);
- tidak ada langkah LEARN fiktif yang pernah ditulis.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text

from app.services.trace_persistence import persist_trace_steps

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

STEPS = [
    ("DETECT", "supply.get+demand.get", {"commodity": "telur"},
     {"shortage": {"location": "Jakarta"}}),
    ("VERIFY", "verifier.rest", {"safety_status": "pass"},
     {"verdict": "UNAVAILABLE"}),
    ("DECIDE", "POST /decisions", {"status": "proposed"},
     {"approved": False}),
]


@pytest.fixture()
def decision_id():
    """Decision sekali pakai untuk FK trace; dihapus di akhir."""
    engine = create_engine(DB_URL)
    did = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO decisions (id, decision_type, status, "
                "proposed_by, expires_at) VALUES (:id, 'regional_balance', "
                "'proposed', 'test', now() + interval '30 minutes')"
            ),
            {"id": did},
        )
    yield did
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM agent_traces WHERE decision_id = :d"), {"d": did}
        )
        conn.execute(
            text("DELETE FROM decisions WHERE id = :d"), {"d": did}
        )


def _run_sync(coroutine_factory):
    """Jalankan coroutine factory dengan sesi async nyata."""
    import asyncio

    from app.core.config import settings
    from app.db import create_engine as make_engine
    from app.db import create_session_maker

    async def _inner():
        engine = make_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            result = coroutine_factory(session)
            await session.commit()
        await engine.dispose()
        return result

    return asyncio.run(_inner())


def test_persists_one_row_per_actual_step(decision_id):
    def _do(session):
        return _run_persist(session, decision_id, STEPS)

    written = _run_sync(_do)
    assert written == 3

    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT step_name, tool_called FROM agent_traces "
                "WHERE decision_id = :d ORDER BY step_at, id"
            ),
            {"d": decision_id},
        ).all()
    engine.dispose()
    assert [r[0] for r in rows] == ["DETECT", "VERIFY", "DECIDE"]
    assert rows[0][1] == "supply.get+demand.get"


def test_payload_sanitized_before_write(decision_id):
    dirty = [
        (
            "DETECT",
            "supply.get",
            {"commodity": "telur", "token": "rahasia"},
            {"ok": True, "password": "pw"},
        )
    ]

    def _do(session):
        return _run_persist(session, decision_id, dirty)

    _run_sync(_do)
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT input_summary, output_summary FROM agent_traces "
                "WHERE decision_id = :d"
            ),
            {"d": decision_id},
        ).one()
    engine.dispose()
    assert row[0] == {"commodity": "telur"}
    assert row[1] == {"ok": True}


def test_invalid_step_name_rejected_explicitly(decision_id):
    bad = [("MADE_UP", None, {}, {})]

    def _do(session):
        return _run_persist(session, decision_id, bad)

    with pytest.raises(ValueError) as excinfo:
        _run_sync(_do)
    assert "MADE_UP" in str(excinfo.value)
    # tidak ada row yang tertulis dari batch tidak valid
    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM agent_traces WHERE decision_id = :d"
            ),
            {"d": decision_id},
        ).scalar_one()
    engine.dispose()
    assert count == 0


def _run_persist(session, decision_id, steps):
    return persist_trace_steps(
        session,
        decision_id=decision_id,
        steps=[
            {"step_name": s, "tool_called": t, "input_summary": i,
             "output_summary": o}
            for (s, t, i, o) in steps
        ],
    )
