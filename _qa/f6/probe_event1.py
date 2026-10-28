import asyncio
from datetime import datetime, timezone
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.services import recommendation_service as rs
from app.services.decision_time import REPLAY_ANCHOR

async def main():
    eng = create_engine(settings.database_url)
    async with create_session_maker(eng)() as db:
        as_of = REPLAY_ANCHOR
        print("as_of", as_of)
        async def _fetch():
            return await rs.fetch_operational_facts(db, as_of)
        out = await rs.build_recommendations(_fetch, as_of=as_of)
        recs = out["recommendations"]
        telur_jkt = [r for r in recs if r["candidate"]["commodity"]=="telur" and r["candidate"]["destination_location"]=="Jakarta"]
        print("total recs", len(recs), "telur->Jakarta", len(telur_jkt))
        for r in telur_jkt[:5]:
            print(" REC", r["candidate"]["source_location"], r.get("eligible"), r.get("score"), r.get("blocking_reasons") if "blocking_reasons" in r else None)
        held = out.get("held") or []
        print("held", len(held))
        for h in held:
            if h.get("commodity")=="telur" and h.get("destination_location")=="Jakarta":
                print(" HELD", h.get("source_location"), h.get("status"), h.get("blocking_reasons"), h.get("next_step"))
    await eng.dispose()

asyncio.run(main())
