"""Konfigurasi aplikasi (Sprint 0).

Semua nilai integrasi (AWS/SAP) TIDAK punya default secret — wajib diisi
lewat environment/.env (lihat .env.example). DEMO_MODE default False
(Rules.md §1.4).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"

    # App
    debug: bool = False
    demo_mode: bool = False
    app_name: str = "MealChain Guardian"

    # Review 7 worker agent (P4: orkestrasi siap, flag default MATI sampai panel P5).
    # `advisory` = agen hanya meninjau keputusan deterministik; bukan pre-decision.
    multi_agent_review: bool = False
    agent_review_mode: str = "advisory"
    agent_review_timeout_seconds: int = 75

    # Konfigurasi demo komoditas (plan Sprint 1 — bukan kolom Schema.md):
    # shelf life dalam hari: telur 28, ayam 5, wortel 21
    shelf_life_days_telur: float = 28.0
    shelf_life_days_ayam: float = 5.0
    shelf_life_days_wortel: float = 21.0
    shelf_life_days_beras: float = 180.0

    # Hierarki keputusan lapis 2 & 3 (proposal): gram per porsi untuk
    # menghitung kebutuhan menu, dan berapa hari cadangan yang HARUS tinggal di
    # lokasi asal supaya pengiriman antarwilayah tidak memutus makan di sana.
    # Angka gram adalah asumsi porsi demo — dinyatakan terbuka, bukan data gizi
    # resmi; ubah lewat env bila komposisi menu berbeda.
    menu_grams_telur: float = 60.0
    menu_grams_ayam: float = 50.0
    menu_grams_wortel: float = 40.0
    continuity_reserve_days: float = 1.0

    # Safe range suhu rantai dingin demo (°C)
    safe_temp_min_c: float = 0.0
    safe_temp_max_c: float = 8.0

    # Integrasi — TANPA default; diisi lewat env saat dibutuhkan (Sprint 3+)
    aws_region: str = "us-west-2"
    supervisor_model_primary: str = ""

    # SAP lewat AWS for SAP MCP Server (A4). Default TETAP mock: adapter MCP
    # hanya dipakai bila diminta eksplisit DAN endpoint-nya ada. Endpoint/token
    # kosong = penolakan di factory, bukan fallback diam-diam ke data simulasi.
    sap_provider: str = "mock"
    sap_mcp_endpoint: str = ""
    sap_mcp_token: str = ""
    sap_mcp_timeout_seconds: float = 10.0
    sap_mcp_allow_write: bool = False
    sap_mcp_tool_stock: str = "sap_material_stock"
    sap_mcp_tool_purchase_orders: str = "sap_purchase_orders"
    sap_mcp_tool_create_purchase_order: str = "sap_create_purchase_order"
    sap_mcp_tool_business_partner: str = "sap_business_partner"
    sap_mcp_tool_product_master: str = "sap_product_master"


settings = Settings()
