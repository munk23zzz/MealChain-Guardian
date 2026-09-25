"""
MealChain Guardian - FastAPI Backend
"""
from fastapi import FastAPI

app = FastAPI(
    title="MealChain Guardian",
    description="Agentic AI untuk cross-regional food supply balancing",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "mealchain-guardian"}
