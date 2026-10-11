"""MealChain Guardian — FastAPI backend (Sprint 1: domain tools + supply/demand)."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.actions import router as actions_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.balance import router as balance_router
from app.api.batches import router as batches_router
from app.api.compliance import router as compliance_router
from app.api.cost import router as cost_router
from app.api.decisions import router as decisions_router
from app.api.demand import forecast_router
from app.api.demand import router as demand_router
from app.api.demo import router as demo_router
from app.api.dependencies import lifespan
from app.api.dossier import router as dossier_router
from app.api.events import router as events_router
from app.api.evidence import router as evidence_router
from app.api.freshness import router as freshness_router
from app.api.kpi import router as kpi_router
from app.api.ledger import router as ledger_router
from app.api.logistics import router as logistics_router
from app.api.price import router as price_router
from app.api.safety import router as safety_router
from app.api.supplier_exclusion_context import router as supplier_exclusion_context_router
from app.api.supplier_exclusions import router as supplier_exclusions_router
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

def _cors_origins() -> list[str]:
    """Origin browser yang boleh memanggil API lintas-origin.

    Bawaan memuat port 3000 (nilai lama) DAN 3010 (port konsol resmi sejak
    S4-19) — keduanya perlu, karena port host dapat diubah lewat FRONTEND_PORT
    di .env. Untuk origin lain (mis. domain Codespaces) set CORS_ORIGINS
    sebagai daftar dipisah koma.
    """
    bawaan = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]
    mentah = os.environ.get("CORS_ORIGINS", "").strip()
    if not mentah:
        return bawaan
    return [asal.strip() for asal in mentah.split(",") if asal.strip()]


# CORS: frontend Next.js fetch API lintas origin (dipakai hanya kalau UI
# dijalankan dengan NEXT_PUBLIC_API_URL absolut; dalam mode proxy Next,
# browser memakai origin sendiri sehingga CORS tidak terlibat).
# Allow-list eksplisit — jangan wildcard (kredensial JWT tetap via header).
# PATCH wajib ada: tab Pengaturan memakai PATCH /admin/users/{id} dan
# /admin/locations/{id} (S4-11).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
app.include_router(batches_router)
app.include_router(cost_router)
app.include_router(evidence_router)
app.include_router(decisions_router)
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(actions_router)
app.include_router(demo_router)
app.include_router(kpi_router)
app.include_router(ledger_router)
app.include_router(dossier_router)
app.include_router(compliance_router)

app.include_router(supplier_exclusions_router)
app.include_router(supplier_exclusion_context_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint backend."""
    return {"status": "healthy", "service": "mealchain-backend"}
