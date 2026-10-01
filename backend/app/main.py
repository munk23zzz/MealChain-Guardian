"""MealChain Guardian — FastAPI backend (Sprint 0: health only)."""

from fastapi import FastAPI

app = FastAPI(
    title="MealChain Guardian",
    description="Agentic AI untuk cross-regional food supply balancing",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint backend."""
    return {"status": "healthy", "service": "mealchain-backend"}
