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

    # Integrasi — TANPA default; diisi lewat env saat dibutuhkan (Sprint 3+)
    aws_region: str = "us-west-2"
    supervisor_model_primary: str = ""


settings = Settings()
