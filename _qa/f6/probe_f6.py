import asyncio, json, os
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.services import recommendation_service as rs

async def main():
    eng = create_engine(settings.database_url)
    async with create_session_maker(eng)() as db:
        class F:
            def __init__(self, db): self.db = db
            async def fetch(self, *a, **k):
                raise NotImplementedError
        from app.api.balance import _AsyncFetcher
        f = _AsyncFetcher(db, None)
        out = await rs.build_recommendations(f, commodity="telur")
        print("candidates_total", len(out.get("recommendations") or []))
        print("held_total", len(out.get("held") or []))
        for h in (out.get("held") or [])[:8]:
            print("HELD", h.get("source_location"), h.get("destination_location"), h.get("status"), h.get("blocking_reasons"), h.get("next_step"))
    await eng.dispose()

asyncio.run(main())
