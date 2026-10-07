"""Test /demo/seed (TDD): 4 kasus demo idempotent."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

CASES = {
    "rejection-loop-kuota",
    "shortage-darurat",
    "supplier-janggal",
    "gangguan-logistik",
}


def _db():
    return create_engine(DB_URL)


def test_seed_idempotent_dan_lengkap():
    engine = _db()
    try:
        with TestClient(app) as c:
            # Login user SPPG existing dari seed_data (punya location).
            email = "sppg.head@demo.local"
            with engine.begin() as conn:
                row = conn.execute(
                    text("SELECT count(*) FROM users WHERE email = :e"),
                    {"e": email},
                ).scalar()
            if row:
                tok = c.post(
                    "/auth/login",
                    json={"email": email, "password": "Demo#SPPG2026"},
                ).json()["access_token"]
            else:
                tok = None
            auth_headers = {"Authorization": f"Bearer {tok}"} if tok else {}

            # Reset dulu (force) supaya test deterministik.
            r1 = c.post("/demo/seed", json={"force": True}, headers=auth_headers)
            assert r1.status_code == 200, r1.text
            assert r1.json()["seeded"] is True
            assert r1.json()["decisions"] == 7

            # Idempotent: seed ulang tanpa force → skip.
            r2 = c.post("/demo/seed", json={}, headers=auth_headers)
            assert r2.json()["seeded"] is False

            # Kasus lengkap + shape timeline benar.
            with engine.begin() as conn:
                per_case = dict(
                    conn.execute(
                        text(
                            "SELECT demo_case, count(*) FROM decisions "
                            "WHERE demo_case IS NOT NULL GROUP BY demo_case"
                        )
                    ).all()
                )
            assert set(per_case) == CASES
            assert per_case["rejection-loop-kuota"] == 3
            assert per_case["gangguan-logistik"] == 2

            # v3 kuota: pending_approval FRESH, chain utuh v1→v2→v3.
            with engine.begin() as conn:
                v3 = conn.execute(
                    text(
                        "SELECT id, status, iteration, expires_at > now() "
                        "FROM decisions WHERE demo_case = 'rejection-loop-kuota' "
                        "AND iteration = 3"
                    )
                ).one()
            assert v3[1] == "pending_approval"
            assert v3[2] == 3
            assert v3[3] is True

            # LEARN trace ada di v2/v3 (bahan memory agent).
            with engine.begin() as conn:
                learns = conn.execute(
                    text(
                        "SELECT count(*) FROM agent_traces t "
                        "JOIN decisions d ON d.id = t.decision_id "
                        "WHERE d.demo_case = 'rejection-loop-kuota' "
                        "AND t.step_name = 'LEARN'"
                    )
                ).scalar()
            assert learns >= 2
    finally:
        engine.dispose()
