"""MealChain Guardian — FastAPI backend (Sprint 1: domain tools + supply/demand)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.actions import router as actions_router
from app.api.auth import router as auth_router
from app.api.balance import router as balance_router
from app.api.decisions import router as decisions_router
from app.api.demand import forecast_router
from app.api.demand import router as demand_router
from app.api.dependencies import lifespan
from app.api.freshness import router as freshness_router
from app.api.logistics import router as logistics_router
from app.api.price import router as price_router
from app.api.safety import router as safety_router
from app.api.supply import router as supply_router


@asynccontextmanager
async def _lifespan_wrapper(app: FastAPI):
    async with lifespan(app):
        yield


app = FastAPI(
    title="MealChain Guardian",
    description="Agentic AI untuk cross-regional food supply balancing",
    version="0.2.0",
    lifespan=_lifespan_wrapper,
)

# Forecast SEBELUM demand generik (path param `/demand/{location}` bisa menelan "forecast")
app.include_router(forecast_router)
app.include_router(demand_router)
app.include_router(supply_router)
app.include_router(freshness_router)
app.include_router(safety_router)
app.include_router(price_router)
app.include_router(logistics_router)
app.include_router(balance_router)
app.include_router(decisions_router)
app.include_router(auth_router)
app.include_router(actions_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint backend."""
    return {"status": "healthy", "service": "mealchain-backend"}
