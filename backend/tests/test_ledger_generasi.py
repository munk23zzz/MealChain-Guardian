"""N3 (audit ulang 24 Okt 2026): generasi ledger.

Latar: `ledger_blocks` append-only, sedangkan reset data demo menghapus
keputusan/batch. Sebelum perbaikan, setiap reset meninggalkan blok yang menunjuk
entitas yang sudah tidak ada — terukur 1437 dari 1541 blok (93%) yatim, dan
angka itu terus memburuk setiap "Siapkan data demo".

Kontrak yang dijaga di sini:
- `ledger_meta.generation` naik tepat satu langkah setiap kali generasi dinaikkan
  (dipanggil oleh reset data demo).
- Blok baru menulis generasi aktif; blok lama TIDAK dihapus, sehingga rantai
  hash tetap utuh dan bisa diverifikasi.
- Cakupan (`linked_ratio`, `orphan_blocks`) hanya menghitung generasi aktif;
  blok generasi lama dilaporkan terpisah sebagai `archived_blocks`.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import ledger_service
from tests.dsn import DSN_ASYNC


def _jalankan(fn):
    """Jalankan `fn(db)` dalam satu sesi async, lalu tutup engine-nya."""

    async def _main():
        eng = create_async_engine(DSN_ASYNC, pool_pre_ping=True)
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await eng.dispose()

    return asyncio.run(_main())


def _kembalikan(db, puncak: int, generasi: int):
    """Buang HANYA blok uji di ujung rantai + pulihkan generasi.

    Memotong ujung rantai tidak merusak verifikasi (tinggi tetap berurutan dari
    1). Menghapus blok di tengah justru akan memutus `prev_hash`.
    """

    async def _kerja():
        await db.execute(
            text("DELETE FROM ledger_blocks WHERE height > :p"), {"p": puncak}
        )
        await db.execute(
            text("UPDATE ledger_meta SET generation = :g WHERE id = 1"),
            {"g": generasi},
        )
        await db.commit()

    return _kerja()


def test_bump_menaikkan_generasi_satu_langkah():
    async def _t(db):
        awal = await ledger_service.current_generation(db)
        puncak = (await db.execute(
            text("SELECT coalesce(max(height), 0) FROM ledger_blocks")
        )).scalar_one()
        baru = await ledger_service.bump_generation(db)
        try:
            assert baru == awal + 1
            assert await ledger_service.current_generation(db) == awal + 1
        finally:
            await _kembalikan(db, puncak, awal)

    _jalankan(_t)


def test_cakupan_hanya_menghitung_generasi_aktif():
    async def _t(db):
        awal = await ledger_service.current_generation(db)
        puncak = (await db.execute(
            text("SELECT coalesce(max(height), 0) FROM ledger_blocks")
        )).scalar_one()
        try:
            keputusan = (await db.execute(
                text("SELECT id FROM decisions ORDER BY created_at LIMIT 1")
            )).scalar_one_or_none()
            if keputusan is None:
                pytest.skip("tidak ada keputusan di DB uji")

            # Generasi lama: blok menunjuk entitas yang tidak ada (yatim).
            await ledger_service.append_block(
                db, "verify", uuid.uuid4(), None, {"catatan": "uji N3 gen lama"}
            )
            await db.commit()
            gen_lama = await ledger_service.current_generation(db)

            # Reset data demo -> generasi baru.
            await ledger_service.bump_generation(db)
            await db.commit()

            blok = await ledger_service.append_block(
                db, "verify", keputusan, None, {"catatan": "uji N3 gen aktif"}
            )
            await db.commit()
            assert blok["generation"] == gen_lama + 1

            hasil = await ledger_service.verify_chain(db)
            assert hasil["valid"] is True, hasil
            assert hasil["generation"] == gen_lama + 1
            # Blok yatim tadi milik generasi lama: tidak lagi mengotori cakupan.
            assert hasil["orphan_blocks"] == 0, hasil
            assert hasil["linked_ratio"] == 1.0, hasil
            assert hasil["archived_blocks"] >= 1, hasil
        finally:
            await _kembalikan(db, puncak, awal)

    _jalankan(_t)


def test_rantai_dan_generasi_tetap_konsisten_setelah_bump():
    async def _t(db):
        awal = await ledger_service.current_generation(db)
        try:
            await ledger_service.bump_generation(db)
            await db.commit()
            hasil = await ledger_service.verify_chain(db)
            assert hasil["valid"] is True, hasil
            assert hasil["generation"] == awal + 1
            assert hasil["blocks"] > 0
        finally:
            await db.execute(
                text("UPDATE ledger_meta SET generation = :g WHERE id = 1"),
                {"g": awal},
            )
            await db.commit()

    _jalankan(_t)


def test_tabel_penanda_generasi_ada_dan_satu_baris():
    async def _t(db):
        baris = (await db.execute(
            text("SELECT id, generation FROM ledger_meta")
        )).fetchall()
        assert len(baris) == 1, baris
        assert baris[0][0] == 1
        assert int(baris[0][1]) >= 1

    _jalankan(_t)
