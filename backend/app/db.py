"""Database engine + session (async SQLAlchemy 2)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class semua model SQLAlchemy."""


def create_engine(database_url: str, echo: bool = False):
    return create_async_engine(database_url, echo=echo)


def create_session_maker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI: sesi database per-request."""
    from app.core.config import settings

    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.close()
