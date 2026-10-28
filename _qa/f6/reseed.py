import asyncio
from datetime import UTC, datetime
from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.seed.demo_activity import (
    seed_demo_activity,
    seed_demo_completed_decisions,
    seed_demo_daily_prices,
)

async def main():
    eng = create_engine(settings.database_url)
    try:
        async with create_session_maker(eng)() as sesi:
            sekarang = datetime.now(UTC)
            await seed_demo_activity(sesi, sekarang)
            await seed_demo_completed_decisions(sesi, sekarang)
            await seed_demo_daily_prices(sesi, sekarang)
            await sesi.commit()
        print("reseed ok")
    finally:
        await eng.dispose()

asyncio.run(main())
