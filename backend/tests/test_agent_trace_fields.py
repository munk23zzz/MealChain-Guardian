"""Kontrak skema P5: metadata worker ada di model dan di database (migrasi 018)."""

from sqlalchemy import create_engine, text

from app.models.decisions import AgentTrace

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

WORKER_FIELDS = {
    "run_id",
    "agent_name",
    "duration_ms",
    "confidence",
    "citations",
    "input_summary",
    "output_summary",
}


def test_model_agent_trace_memiliki_metadata_worker():
    columns = {column.name: column for column in AgentTrace.__table__.columns}
    assert WORKER_FIELDS.issubset(columns)
    for name in ("run_id", "agent_name", "duration_ms", "confidence", "citations"):
        assert columns[name].nullable is True


def test_database_sudah_migrasi_018():
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'agent_traces'"
                    )
                )
            }
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()
    assert WORKER_FIELDS.issubset(names)
    # Head boleh maju (019 = karantina batch); yang dijaga tes ini adalah kolom
    # worker sudah ada, bukan bahwa tidak ada migrasi sesudahnya.
    assert version >= "018_agent_trace_worker_fields"
