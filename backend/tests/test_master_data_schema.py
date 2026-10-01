"""Integrasi schema master data — dijalankan TERHADAP PostgreSQL nyata
di dalam container backend (butuh `docker compose up` + `alembic upgrade head`).

Membuktikan kontrak Schema.md §1:
- 4 tabel ada
- role lama (sppg_staff/dinas_admin) DITOLAK
- sppg_head/nutritionist tanpa lokasi DITOLAK
- bgn_monitor dengan lokasi DITOLAK
- reliability_score di luar 0-1 DITOLAK
"""

import os

import pytest
from sqlalchemy import create_engine, text

DB_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")

EXPECTED_TABLES = {"locations", "commodities", "suppliers", "users"}


@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


def _insert_user(engine, role: str, with_location: bool) -> None:
    with engine.connect() as conn:
        if with_location:
            loc_id = conn.execute(
                text(
                    "INSERT INTO locations (name, region, latitude, longitude) "
                    "VALUES ('TEST-LOC-' || gen_random_uuid(), 'West', -6.9, 107.6) "
                    "RETURNING id"
                )
            ).scalar_one()
            conn.commit()
            conn.execute(
                text(
                    "INSERT INTO users (name, email, password_hash, role, location_id) "
                    "VALUES ('T', 't-' || gen_random_uuid() || '@x.id', 'h', "
                    f"'{role}', :loc_id)"
                ),
                {"loc_id": str(loc_id)},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO users (name, email, password_hash, role) "
                    "VALUES ('T', 't-' || gen_random_uuid() || '@x.id', 'h', "
                    f"'{role}')"
                )
            )
        conn.commit()


def test_four_master_tables_exist(sync_engine) -> None:
    with sync_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename IN "
                "('locations','commodities','suppliers','users')"
            )
        )
        tables = {r[0] for r in rows}
    assert tables == EXPECTED_TABLES


def test_old_roles_rejected(sync_engine) -> None:
    for old_role in ("sppg_staff", "dinas_admin"):
        with pytest.raises(Exception):
            _insert_user(sync_engine, old_role, with_location=False)


def test_monitor_roles_require_location(sync_engine) -> None:
    for role in ("sppg_head", "sppg_nutritionist"):
        with pytest.raises(Exception):
            _insert_user(sync_engine, role, with_location=False)


def test_bgn_monitor_must_have_null_location(sync_engine) -> None:
    with pytest.raises(Exception):
        _insert_user(sync_engine, "bgn_monitor", with_location=True)


def test_valid_three_roles_accepted(sync_engine) -> None:
    _insert_user(sync_engine, "sppg_head", with_location=True)
    _insert_user(sync_engine, "sppg_nutritionist", with_location=True)
    _insert_user(sync_engine, "bgn_monitor", with_location=False)


def test_reliability_score_bounds(sync_engine) -> None:
    with sync_engine.connect() as conn:
        loc = conn.execute(
            text(
                "INSERT INTO locations (name, region, latitude, longitude) "
                "VALUES ('S-BOUND-' || gen_random_uuid(), 'West', 0, 0) RETURNING id"
            )
        ).scalar_one()
        conn.commit()
    for bad in ("1.5", "-0.1"):
        with pytest.raises(Exception):
            with sync_engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO suppliers (name, location_id, reliability_score) "
                        f"VALUES ('s', '{loc}', {bad})"
                    )
                )
                conn.commit()
