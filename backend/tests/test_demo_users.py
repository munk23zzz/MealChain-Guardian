"""Test seed demo users 3 role (S3-01, TDD).

ensure_demo_users() idempoten: memastikan 3 akun demo ada dengan role
dan scope lokasi yang benar (bgn_monitor tanpa lokasi).
"""

from sqlalchemy import create_engine, text

from app.seed.seed_data import DEMO_USERS, ensure_demo_users

DB_URL = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


def test_demo_users_constant_has_exactly_three_roles():
    roles = sorted(u["role"] for u in DEMO_USERS)
    assert roles == ["bgn_monitor", "sppg_head", "sppg_nutritionist"]


def test_ensure_demo_users_idempotent_and_scoped():
    ensure_demo_users()
    ensure_demo_users()  # panggil dua kali — tetap 1 set akun

    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT u.role, l.name AS location_name, u.email "
                    "FROM users u LEFT JOIN locations l ON l.id = u.location_id "
                    "WHERE u.email LIKE '%@demo.local'"
                )
            ).mappings().all()
        by_role = {r["role"]: r for r in rows}
        assert set(by_role) == {"sppg_head", "sppg_nutritionist", "bgn_monitor"}
        assert by_role["sppg_head"]["location_name"] == "Jakarta"
        # Ruling 2026-10-14: ahli gizi demo ikut Jakarta (satu SPPG dengan
        # kepala) supaya matriks AND dua verifier bisa didemokan.
        assert by_role["sppg_nutritionist"]["location_name"] == "Jakarta"
        assert by_role["bgn_monitor"]["location_name"] is None
        # idempoten: tidak ada duplikat
        assert len(rows) == 3
    finally:
        engine.dispose()
