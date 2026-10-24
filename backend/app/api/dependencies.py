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
    await _kosongkan_bila_tanpa_sesi(app.state.session_maker)
    yield
    await app.state.engine.dispose()


def _database_url() -> str:
    import os

    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
    )


async def _kosongkan_bila_tanpa_sesi(maker) -> None:
    """Default kosong saat boot: bersihkan hanya baris MILIK SESI (ber-stempel).

    Ini yang membuat "tampilan default kosong" benar bahkan pada boot pertama
    setelah fitur dinyalakan. Bila sesi sedang aktif (restart di tengah demo),
    data TIDAK disentuh.

    Audit 21 Okt 2026: sebelumnya fungsi ini memanggil `bersihkan_warisan()` =
    `kosongkan_kecuali(None)`, yang menghapus SELURUH baris operasional. Efeknya
    terukur: setiap restart backend (uvicorn --reload saat menyunting kode) saat
    tidak ada sesi aktif memusnahkan template demo 121 batch, dan operator harus
    menyemai ulang. Tampilan tetap kosong tanpa sesi karena UI menyembunyikan
    data, jadi pembersihan menyeluruh tidak pernah dibutuhkan untuk perilaku itu.
    """
    from app.core.config import settings

    async def _bersihkan(fn) -> None:
        try:
            async with maker() as db:
                await fn(db)
        except Exception:  # noqa: BLE001 — boot tidak boleh gagal karena pembersihan
            import logging

            logging.getLogger(__name__).warning(
                "pembersihan data demo saat boot gagal", exc_info=True
            )

    if not settings.demo_session_enforce:
        # Mode dev/tes: JANGAN membersihkan apa pun. Percobaan 21 Okt 2026 yang
        # memanggil `bersihkan_warisan` di sini menghapus 121 batch kanonik pada
        # boot TestClient pertama, lalu 47 tes gagal karena kehabisan data.
        # Penjagaan sesi memang tidak berlaku saat flag ini mati.
        return

    await _bersihkan(_tanpa_stempel)


async def _tanpa_stempel(db) -> None:
    """Jalur mode sesi: hapus baris MILIK SESI saja bila tidak ada sesi aktif.

    Template demo (baris kanonik yang tidak ber-stempel) harus selamat dari
    restart backend, karena membangunnya butuh +-70 detik dan operator tidak
    selalu punya akses shell saat demo. Tampilan tetap kosong tanpa sesi karena
    UI menyembunyikan data.
    """
    from app.services import demo_session as ds

    if await ds.aktif(db) is None:
        await ds.kosongkan_bertanda(db)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency sesi per-request dari engine lifespan (satu engine, dipakai ulang)."""
    maker = request.app.state.session_maker
    async with maker() as session:
        yield session
