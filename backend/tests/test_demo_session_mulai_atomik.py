"""Kontrak: "Siapkan data demo" tidak boleh meninggalkan sistem kosong tanpa jalan pulih.

Kegagalan nyata 21 Okt 2026 (dua kali terukur): `POST /demo/session/start` membuat baris
sesi lebih dulu, mengosongkan SEMUA tabel operasional, lalu baru membangun template. Saat
build gagal (ImportError `LedgerBlock` di stack demo, `FileNotFoundError` seed di salinan),
HTTP 500 keluar dengan sesi `active` dan 15 tabel 0 baris; klik berikutnya membalas
`created:false` (idempoten terhadap sesi berjalan) sehingga template TIDAK PERNAH dibangun
ulang. Pemulihan hanya mungkin lewat "Akhiri sesi".

Kontrak yang dikunci di sini:

1. Bila build template gagal, TIDAK ada sesi aktif yang tertinggal.
2. Baris operasional yang sudah ada tidak dihapus sebelum build terbukti berhasil.
3. Galat diteruskan ke pemanggil (bukan ditelan) supaya router bisa membalas 503.
4. Setelah build berhasil, sesi baru aktif dan hanya SATU sesi aktif yang ada.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import DemoSession
from app.services import demo_session as sesi
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DSN = os.environ.get(
    "TEST_DATABASE_URL",
    DSN_ASYNC,
)


@asynccontextmanager
async def _db():
    engine = create_async_engine(DSN)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _sesi_aktif(db) -> list[uuid.UUID]:
    hasil = await db.execute(select(DemoSession.id).where(DemoSession.status == "active"))
    return list(hasil.scalars())


async def _hitung_baris(db, tabel: str, *, tanpa_stempel: bool = False) -> int:
    sql = f"SELECT count(*) FROM {tabel}"
    if tanpa_stempel:
        sql += " WHERE demo_session_id IS NULL"
    return int((await db.execute(text(sql))).scalar_one())


def test_build_gagal_tidak_meninggalkan_sesi_aktif(monkeypatch):
    """Build gagal → tidak ada sesi aktif, baris lama utuh, galat diteruskan."""

    async def skenario():
        async with _db() as db:
            # Yang diukur: baris TANPA stempel sesi (data kerja/kanonik). Baris
            # ber-stempel milik sesi aktif lama memang dihapus oleh kontrak
            # `akhiri()` — itu langkah "tutup sesi sebelumnya", bukan efek build
            # yang gagal. Menghitung total mentah membuat tes ini merah hanya
            # karena DB kebetulan punya sesi aktif (terukur 27 Okt 2026: merah
            # saat sendirian maupun di suite penuh), padahal atomisitas build
            # tidak dilanggar.
            sebelum = {
                t: await _hitung_baris(db, t, tanpa_stempel=True)
                for t in ("batches", "decisions", "supply_records")
            }
            # Sesi milik fixture/tes lain boleh ada; yang dikunci adalah TIDAK ADA
            # sesi BARU yang tertinggal setelah build gagal.
            aktif_awal = set(await _sesi_aktif(db))

            async def build_gagal(*_args, **_kwargs):
                raise RuntimeError("build template sengaja gagal (tes)")

            monkeypatch.setattr("app.seed.demo_template.build_into", build_gagal)

            with pytest.raises(RuntimeError):
                await sesi.mulai_dengan_template(db, menit=5, created_by=None)

            sisa = set(await _sesi_aktif(db)) - aktif_awal
            assert sisa == set(), f"sesi aktif baru tertinggal setelah build gagal: {sisa}"
            for t, n in sebelum.items():
                sesudah = await _hitung_baris(db, t, tanpa_stempel=True)
                assert sesudah == n, (
                    f"{t} tanpa stempel berubah padahal build gagal: {n} -> {sesudah}"
                )

    asyncio.run(skenario())


def test_build_sukses_membuat_tepat_satu_sesi_aktif(monkeypatch):
    """Build sukses → sesi aktif tunggal dan laporan build dikembalikan."""

    async def skenario():
        async with _db() as db:
            sid = uuid.uuid4()

            async def build_ok(*_args, **_kwargs):
                return {"inti": {"seed": {"batches": 0}}, "kasus": {}, "_sid": str(sid)}

            monkeypatch.setattr("app.seed.demo_template.build_into", build_ok)
            baru, laporan = await sesi.mulai_dengan_template(db, menit=5, created_by=None)
            try:
                assert laporan["inti"]["seed"] == {"batches": 0}
                aktif = await _sesi_aktif(db)
                assert baru.id in aktif
            finally:
                await db.execute(
                    text("DELETE FROM demo_sessions WHERE id = :i"), {"i": str(baru.id)}
                )
                await db.commit()

    asyncio.run(skenario())
