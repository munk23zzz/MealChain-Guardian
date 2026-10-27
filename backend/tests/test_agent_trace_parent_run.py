"""Jejak verifier sebagai RUN ANAK (AUD-9A-03, migrasi 039).

Yang dikunci:

1. Baris VERIFY yang dihasilkan `build_trace_rows` membawa `run_id` sendiri
   (run verifier) dan `parent_run_id` = run review yang diauditnya.
2. `persist_agent_review` menerima bentuk itu dan menyimpan kedua kolom, plus
   verdict + sitasi di `output_summary`/`citations` sehingga putaran audit bisa
   direkonstruksi dari DB.
3. Kontrak lama tetap dijaga: baris tanpa `parent_run_id` wajib satu run_id;
   `parent_run_id` yang menunjuk run lain ditolak.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text

pytest.importorskip("agent")

from agent.contracts import (  # noqa: E402
    ANALYST_AGENTS,
    AgentFinding,
    AgentRun,
    RunStatus,
    VerifyResult,
    WorkerStatus,
)
from agent.registry import get_spec  # noqa: E402
from agent.telemetry import build_trace_rows  # noqa: E402
from agent.workers.verifier import VerifierWorker  # noqa: E402

from app.services.trace_persistence import persist_agent_review  # noqa: E402
from tests.dsn import DSN_ASYNC  # noqa: E402

DB_URL = DSN_ASYNC.replace("+asyncpg", "+psycopg")


@pytest.fixture()
def decision_id():
    engine = create_engine(DB_URL)
    did = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                "expires_at) VALUES (:id, 'regional_balance', 'proposed', 'test', "
                "now() + interval '30 minutes')"
            ),
            {"id": did},
        )
    yield did
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM agent_traces WHERE decision_id = :d"), {"d": did}
        )
        conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": did})
    engine.dispose()


def _run_sync(coroutine_factory):
    import asyncio

    from app.core.config import settings
    from app.db import create_engine as make_engine
    from app.db import create_session_maker

    async def _inner():
        engine = make_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            result = coroutine_factory(session)
            if hasattr(result, "__await__"):
                result = await result
            await session.commit()
        await engine.dispose()
        return result

    return asyncio.run(_inner())


FAKTA = {
    "decision_id": "d",
    "sdc_check": {"cocok": True},
    "evidence": {"count": 1, "ids": ["ev-1"], "types": ["gps"]},
    "batch_sumber": {"worst_status": "pass", "freshness_status": "pass"},
    "exclusion": {"aktif": False, "ids": []},
    "ledger": {"count": 1, "block_ids": ["ledger-1"]},
    "citations": {
        "decision_id": "d",
        "batch_ids": ["batch-1"],
        "evidence_ids": ["ev-1"],
        "ledger_block_ids": ["ledger-1"],
    },
}


def _model_verifier():
    """Model palsu yang menjawab JSON sah — supaya verdict dapat diuji."""
    import json

    def _jawab(prompt: str) -> str:  # noqa: ARG001
        return json.dumps(
            {
                "verdict": "consistent",
                "checks": [
                    {
                        "nama": "sdc_vs_cost_breakdown",
                        "klaim": "SDC sama dengan rincian",
                        "aktual": "cocok=true",
                        "lulus": True,
                    }
                ],
                "citations": [{"decision_id": "d"}],
                "catatan": "klaim sesuai fakta",
            }
        )

    return _jawab


def _run_dengan_verifier(decision_id: str) -> AgentRun:
    temuan = [
        AgentFinding(
            agent=name,
            stage=get_spec(name).stage,
            status=WorkerStatus.OK,
            summary=f"{name.value}: tidak ada temuan",
            facts={},
            citations=[],
            blocking=False,
        )
        for name in ANALYST_AGENTS
    ]
    run = AgentRun(
        run_id=uuid.uuid4(),
        decision_id=decision_id,
        mode="advisory",
        status=RunStatus.COMPLETED,
        findings=temuan,
        narrative="Review 7 agen selesai tanpa kontradiksi.",
        verification=VerifyResult(verdict="pass"),
    )
    verifier_run_id = uuid.uuid4()
    audit = VerifierWorker(model=_model_verifier()).audit(
        run, run_id=verifier_run_id, fakta=FAKTA
    )
    return run.model_copy(
        update={"verifier_finding": audit, "verifier_run_id": verifier_run_id}
    )


def test_baris_verify_punya_run_id_sendiri_dan_parent(decision_id) -> None:
    run = _run_dengan_verifier(decision_id)
    rows = build_trace_rows(run)
    baris = next(row for row in rows if row["agent_name"] == "verifier")

    assert baris["run_id"] == str(run.verifier_run_id)
    assert baris["parent_run_id"] == str(run.run_id)
    assert run.verifier_run_id != run.run_id
    # Baris analitik tetap langkah run induk (tanpa parent).
    for row in rows:
        if row["agent_name"] != "verifier":
            assert row["run_id"] == str(run.run_id)
            assert row.get("parent_run_id") is None


def test_persist_menyimpan_parent_run_id_dan_jejak_verdict(decision_id) -> None:
    run = _run_dengan_verifier(decision_id)
    rows = build_trace_rows(run)

    def _do(session):
        return persist_agent_review(session, decision_id=decision_id, trace_rows=rows)

    assert _run_sync(_do) == 9

    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        baris = conn.execute(
            text(
                "SELECT run_id, parent_run_id, output_summary, citations "
                "FROM agent_traces WHERE decision_id = :d AND agent_name = 'verifier'"
            ),
            {"d": decision_id},
        ).one()
    engine.dispose()

    assert str(baris[0]) == str(run.verifier_run_id)
    assert str(baris[1]) == str(run.run_id)
    output = baris[2]
    assert output["audit_verdict"] == "consistent"
    assert output["checks_total"] >= 1
    # Sitasi ikut tersimpan: verdict bisa direkonstruksi dari DB tanpa memanggil
    # ulang model/API.
    assert baris[3], "sitasi baris VERIFY wajib tersimpan"


def test_parent_run_id_asing_ditolak(decision_id) -> None:
    run = _run_dengan_verifier(decision_id)
    rows = build_trace_rows(run)
    for row in rows:
        if row["agent_name"] == "verifier":
            row["parent_run_id"] = str(uuid.uuid4())

    with pytest.raises(ValueError, match="parent_run_id harus menunjuk run induk"):
        _run_sync(
            lambda session: persist_agent_review(
                session, decision_id=decision_id, trace_rows=rows
            )
        )

    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        jumlah = conn.execute(
            text("SELECT COUNT(*) FROM agent_traces WHERE decision_id = :d"),
            {"d": decision_id},
        ).scalar_one()
    engine.dispose()
    assert jumlah == 0
