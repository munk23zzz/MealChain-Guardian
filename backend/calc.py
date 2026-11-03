# Query ORM persis endpoint TAPI di dalam TestClient portal loop
# (mode async di-anyio portal). Jalankan endpoint-nya manual: panggil fungsi
# get_supply via portal yang sama → cari masalah di sana.
# Simpler: jalankan ORM query di thread portal TestClient.
import anyio
import bcrypt
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import case, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.models import Commodity, Location, SupplyRecord

DB = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
eng = sqlalchemy.create_engine(DB)
pw = "TestPass#2026"
digest = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
EMAIL = "pytest-legacy-rbac@test.local"

_SOURCE_PRECEDENCE = {"mock_sap": 0, "manual": 1, "sensor": 2}


def _src():
    return case(_SOURCE_PRECEDENCE, value=SupplyRecord.source, else_=99)


with TestClient(app) as client:
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": EMAIL})
        loc_id = conn.execute(
            text("SELECT id FROM locations WHERE name = 'Jakarta'")
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO users (id, name, email, password_hash, role, location_id) "
                "VALUES (gen_random_uuid(), 'T', :e, :h, 'sppg_head', :l)"
            ),
            {"e": EMAIL, "h": digest, "l": str(loc_id)},
        )
    resp = client.post("/auth/login", json={"email": EMAIL, "password": pw})
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO supply_records (id, location_id, commodity_id, "
                "quantity_kg, recorded_at, source) "
                "SELECT gen_random_uuid(), l.id, c.id, 777, "
                "'2026-10-05T00:00:00+00'::timestamptz, 'manual' "
                "FROM locations l, commodities c "
                "WHERE l.name='Cianjur' AND c.name='telur'"
            )
        )

    async def orm_dump():
        maker: async_sessionmaker = app.state.session_maker
        async with maker() as s:
            loc = (
                await s.execute(select(Location).where(Location.name == "Cianjur"))
            ).scalar_one()
            com = (
                await s.execute(select(Commodity).where(Commodity.name == "telur"))
            ).scalar_one()
            recs = (
                await s.execute(
                    select(SupplyRecord)
                    .where(
                        SupplyRecord.location_id == loc.id,
                        SupplyRecord.commodity_id == com.id,
                    )
                    .order_by(SupplyRecord.recorded_at.desc(), _src())
                )
            ).scalars().all()
            for r in recs:
                print("ORM-in-portal:", r.quantity_kg, r.source, r.recorded_at)

    anyio.run(orm_dump)

    resp1 = client.get("/supply/Cianjur/telur")
    print("api:", resp1.status_code, resp1.json())

    with eng.begin() as conn:
        conn.execute(
            text("DELETE FROM supply_records WHERE source='manual' AND quantity_kg=777")
        )
        conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": EMAIL})
