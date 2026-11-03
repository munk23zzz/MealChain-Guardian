"""Mock SAP service — boundary simulasi SAP.

PENTING (Rules.md §1.6, Skill.md §6): semua response dari service ini WAJIB
dilabel sebagai simulasi — middleware header `X-Data-Source: MOCK`. Tidak ada
endpoint business logic Sprint 1 di sini.
"""

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

app = FastAPI(
    title="MealChain Mock SAP",
    description="Simulasi boundary SAP (bukan SAP asli)",
    version="0.1.0",
)


class MockDataSourceHeaderMiddleware(BaseHTTPMiddleware):
    """Tandai SEMUA response service ini sebagai data simulasi."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Data-Source"] = "MOCK"
        return response


app.add_middleware(MockDataSourceHeaderMiddleware)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint mock-sap, selalu berlabel simulasi."""
    return {
        "status": "healthy",
        "service": "mock-sap",
        "data_source": "simulation",
    }
