import asyncio
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.services import recommendation_service as rs
from app.services.decision_time import REPLAY_ANCHOR

async def main():
    eng = create_engine(settings.database_url)
    async with create_session_maker(eng)() as db:
        for label, as_of in (("anchor", REPLAY_ANCHOR), ("now", None)):
            facts = await rs.fetch_operational_facts(db, as_of)
            supply, demand = facts[0], facts[1]
            batches = facts[4]
            print("==", label, "as_of", as_of)
            print(" supply telur", {k: str(v) for k, v in supply.items() if k[1] == "telur"})
            print(" demand telur", {k: str(v) for k, v in demand.items() if k[1] == "telur"})
            tel = [b for b in batches if b.get("commodity") == "telur"]
            print(" batches telur", len(tel), [(b.get("location"), str(b.get("harvested_at"))[:10], b.get("safety_status"), len(b.get("temperature_log") or [])) for b in tel])
    await eng.dispose()

asyncio.run(main())
