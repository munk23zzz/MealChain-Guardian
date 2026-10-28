"""MealChain Guardian — FastAPI backend (Sprint 1: domain tools + supply/demand)."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.actions import router as actions_router
from app.api.admin import router as admin_router
from app.api.agenda import router as agenda_router
from app.api.auth import router as auth_router
from app.api.balance import router as balance_router
from app.api.batches import router as batches_router
from app.api.compliance import router as compliance_router
from app.api.cost import router as cost_router
from app.api.decisions import router as decisions_router
from app.api.demand import forecast_router
from app.api.demand import router as demand_router
from app.api.demo import router as demo_router
from app.api.demo_session import router as demo_session_router
from app.api.dependencies import lifespan
from app.api.dossier import router as dossier_router
from app.api.events import router as events_router
from app.api.evidence import router as evidence_router
from app.api.freshness import router as freshness_router
from app.api.integrations import router as integrations_router
from app.api.kpi import router as kpi_router
from app.api.ledger import router as ledger_router
from app.api.logistics import router as logistics_router
from app.api.price import router as price_router
from app.api.procurement import router as procurement_router
from app.api.quarantine import router as quarantine_router
from app.api.receipts import router as receipts_router
from app.api.safety import router as safety_router
from app.api.sap_orders import router as sap_orders_router
from app.api.supplier_exclusion_context import router as supplier_exclusion_context_router
from app.api.supplier_exclusions import router as supplier_exclusions_router
from app.api.supplier_routes import router as supplier_routes_router
from app.api.suppliers import router as suppliers_router
from app.api.supply import router as supply_router

# 2026-10-20: rencana alokasi surplus lintas lokasi. Panel "Rencana alokasi
# surplus" (halaman Surplus & Limbah) sebelumnya dihitung klien dari
# /balance/map yang dibatasi cakupan peran -> selalu kosong untuk peran SPPG.
from app.api.surplus import router as surplus_router
from app.api.waste import router as waste_router


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

# ── SEC-04: dokumentasi API hanya terbuka bila diminta ────────────────────
# Audit 24 Okt 2026: `/docs`, `/redoc`, dan `/openapi.json` terbuka tanpa
# autentikasi. Peta endpoint selengkap itu memudahkan pemetaan serangan, dan
# tidak dibutuhkan UI (UI memakai path eksplisit). Default TERTUTUP; buka
# sadar-sadar dengan ENABLE_DOCS=true (atau DEBUG=true) saat mengembangkan.
_DOKUMEN_PATHS = ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect")


def _dokumen_boleh() -> bool:
    """True bila dokumentasi API boleh disajikan (ENABLE_DOCS/DEBUG)."""
    def _nyala(nama: str) -> bool:
        return os.environ.get(nama, "").strip().lower() in {"1", "true", "yes", "on"}

    return _nyala("ENABLE_DOCS") or _nyala("DEBUG")


@app.middleware("http")
async def _kunci_dokumen(request, call_next):
    if request.url.path in _DOKUMEN_PATHS and not _dokumen_boleh():
        # 404, bukan 403: jangan mengonfirmasi bahwa rutenya ada.
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


# ── SEC-05: header keamanan ───────────────────────────────────────────────
# Backend hanya menyajikan JSON, jadi CSP-nya boleh seketat mungkin. Halaman
# HTML (Next.js) punya kebijakan sendiri di frontend/next.config.js — dua sisi
# ini sengaja terpisah karena kebutuhannya berbeda.
@app.middleware("http")
async def _header_keamanan(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    h.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'none'",
    )
    # HSTS hanya di HTTPS (atau di belakang proxy TLS); pada HTTP lokal header
    # ini diabaikan browser, tetapi mengirimnya membuat perilaku dev vs prod
    # berbeda tanpa alasan.
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    if request.url.scheme == "https" or proto == "https":
        h.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
    return resp


# ── Konteks sesi demo (024) ────────────────────────────────────────────────
# `do_orm_execute` menyaring kueri berdasarkan ContextVar; ContextVar itu diisi
# di sini, satu kali per request, hanya bila DEMO_SESSION_ENFORCE menyala.
# Tanpa flag, middleware hanya meneruskan request (biaya nol, tes tidak berubah).
#: Endpoint yang tetap boleh dipanggil TANPA sesi aktif saat enforcement menyala:
#: pengelola sesi itu sendiri (`start`/`extend`/`end`), login, kesehatan, dan
#: dokumentasi. Semua pembacaan (GET/HEAD/OPTIONS) selalu terbuka — yang ditolak
#: hanyalah MUTASI, karena hanya mutasi yang bisa mengubah data demo.
_JALUR_TANPA_SESI = frozenset(
    {
        "/health",
        "/auth/login",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/demo/session/start",
        "/demo/session/extend",
        "/demo/session/end",
        # Menjalankan agent DARI Demo Control boleh membuka sesi sendiri:
        # tanpanya, setelah "Akhiri sesi"/sesi kedaluwarsa setiap klik
        # "Jalankan Agent" dijawab 409 oleh middleware ini dan panel tampak
        # rusak (terukur 28 Okt 2026). Handler `/demo/agent/run` membuka sesi
        # realtime dengan `kosongkan=False`, jadi keputusan tetap terikat.
        "/demo/agent/run",
    }
)
_METODE_MUTASI = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@app.middleware("http")
async def _konteks_sesi_demo(request, call_next):
    from app.core.config import settings as _settings
    from app.services import demo_session as _sesi

    _sesi.pasang_penjaga()
    if not _settings.demo_session_enforce:
        return await call_next(request)
    if request.url.path in {"/health", "/auth/login", "/docs", "/openapi.json"}:
        return await call_next(request)

    maker = request.app.state.session_maker
    try:
        async with maker() as db:
            # `aktif()` juga menutup sesi yang sudah lewat waktu (kedaluwarsa malas).
            aktif = await _sesi.aktif(db)
        # Permintaan produk (25 Okt 2026): sesudah sesi kedaluwarsa, backend
        # MENOLAK aksi — bukan hanya berhenti menyapu data. Tanpa gerbang ini
        # keputusan tetap bisa disetujui/dieksekusi lewat API walau sesi sudah
        # habis, dan klien hanya mendapati datanya berubah tanpa sebab.
        if (
            aktif is None
            and request.method in _METODE_MUTASI
            and request.url.path not in _JALUR_TANPA_SESI
        ):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": (
                        "sesi demo belum aktif atau sudah kedaluwarsa — tekan "
                        "\"Siapkan data demo\" lebih dulu; aksi tulis ditolak"
                    )
                },
            )
        return await call_next(request)
    finally:
        _sesi.set_sesi(None)


# ── Gerbang mode demo (Fase 12 MG butir 4) ─────────────────────────────────
# `DEMO_MODE=False` berarti aplikasi berjalan sebagai OPERASIONAL: namespace
# `/demo` tidak diakui sama sekali. Sebelum gerbang ini ada, `DEMO_MODE` hanya
# dibaca di beberapa tempat (pesan `freshness.as_of`, seed kredensial), sehingga
# mematikan variabel itu TIDAK menutup `/demo/seed`: siapa pun yang memegang token
# masih bisa menyemai kasus demo ke data operasional.
#
# Keputusan bentuk:
# - **404, bukan 403/409.** Rute demo tidak dianggap ada di mode operasional,
#   jadi jawabannya sama dengan jalur yang tidak pernah didaftarkan. 409 tetap
#   milik pagar sesi (`DEMO_SESSION_ENFORCE`), sehingga operator bisa membedakan
#   "mode operasional" dari "sesi demo kedaluwarsa".
# - **Didaftarkan SESUDAH middleware sesi** supaya ia berjalan lebih dulu
#   (Starlette menyusun middleware: yang terakhir ditambahkan = terluar). Dengan
#   begitu 404 keluar tanpa membuka koneksi DB, dan aplikasi operasional yang
#   tidak punya tabel demo tetap menjawab 404, bukan 500.
_DEMO_PATH = "/demo"


def _jalur_demo(path: str) -> bool:
    return path == _DEMO_PATH or path.startswith(_DEMO_PATH + "/")


@app.middleware("http")
async def _gerbang_mode_demo(request, call_next):
    from app.core.config import settings as _settings

    if not _settings.demo_mode and _jalur_demo(request.url.path):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


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
app.include_router(quarantine_router)
# 016: catatan penerimaan barang ("Lainnya" dari kartu Penerimaan barang).
app.include_router(receipts_router)
app.include_router(cost_router)
app.include_router(evidence_router)
app.include_router(decisions_router)
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(actions_router)
# W-5 (2026-10-17): sisi BACA purchase order mock SAP. Selama ini tabel
# `sap_mock_purchase_orders` hanya ditulis `actions.py` dan dibaca agregat KPI,
# sehingga PO yang terbit setelah eksekusi tidak bisa ditunjukkan di layar.
app.include_router(sap_orders_router)
app.include_router(demo_router)
app.include_router(demo_session_router)
app.include_router(kpi_router)
app.include_router(procurement_router)
app.include_router(waste_router)
app.include_router(surplus_router)
app.include_router(agenda_router)
app.include_router(ledger_router)
app.include_router(dossier_router)
app.include_router(compliance_router)

app.include_router(supplier_exclusions_router)
app.include_router(suppliers_router)
app.include_router(supplier_routes_router)
app.include_router(supplier_exclusion_context_router)
app.include_router(admin_router)
app.include_router(integrations_router)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint backend."""
    return {"status": "healthy", "service": "mealchain-backend"}
