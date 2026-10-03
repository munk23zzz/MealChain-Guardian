"""Lifespan + dependency database (Task 11).

Satu async engine dibuat sekali saat startup, dipakai ulang antar request,
dan di-dispose saat shutdown — tidak ada engine bocor per-request.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import create_engine, create_session_maker


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = _database_url()
    app.state.engine = create_engine(database_url)
    app.state.session_maker = create_session_maker(app.state.engine)
    yield
    await app.state.engine.dispose()


def _database_url() -> str:
    import os

    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
    )


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency sesi per-request dari engine lifespan (satu engine, dipakai ulang)."""
    maker = request.app.state.session_maker
    async with maker() as session:
        yield session
