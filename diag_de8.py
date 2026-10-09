import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


async def main():
    eng = create_async_engine(
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    sfx = uuid.uuid4().hex[:8]
    async with maker() as session:
        r = await session.execute(text(
            "INSERT INTO disposal_events (location_id, commodity_id, quantity_kg, "
            "reason, disposed_at, id) SELECT :l, c2.id, 12, 'diag', :t, "
            "gen_random_uuid() FROM commodities c2 WHERE c2.name='telur' RETURNING id, disposed_at, disposed_at AT TIME ZONE 'UTC' AS naive"),
            {"l": None, "t": NOW})
        print(r.fetchall())
    await eng.dispose()


asyncio.run(main())
