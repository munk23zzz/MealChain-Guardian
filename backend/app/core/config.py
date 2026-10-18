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

    # Review 7 worker agent (P0: default MATI, belum ada worker yang berjalan).
    # `advisory` = agen hanya meninjau keputusan deterministik; bukan pre-decision.
    multi_agent_review: bool = False
    agent_review_mode: str = "advisory"
    agent_review_timeout_seconds: int = 75

    # Konfigurasi demo komoditas (plan Sprint 1 — bukan kolom Schema.md):
    # shelf life dalam hari: telur 28, ayam 5, wortel 21
    shelf_life_days_telur: float = 28.0
    shelf_life_days_ayam: float = 5.0
    shelf_life_days_wortel: float = 21.0

    # Safe range suhu rantai dingin demo (°C)
    safe_temp_min_c: float = 0.0
    safe_temp_max_c: float = 8.0

    # Integrasi — TANPA default; diisi lewat env saat dibutuhkan (Sprint 3+)
    aws_region: str = "us-west-2"
    supervisor_model_primary: str = ""


settings = Settings()
