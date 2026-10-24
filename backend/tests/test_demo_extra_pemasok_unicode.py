"""Pemasok Unicode tidak boleh menambah baris ke direktori demo.

Residu audit 24 Okt 2026: `build_demo_extra` dulu MEMBUAT pemasok baru bernama
"Koperasi Tani Makmur — Cianjur (Unit SPPG)" untuk menguji rendering em dash.
Akibatnya direktori demo berubah 60 -> 61 setiap "Siapkan data demo", sedangkan
runbook dan laporan menyebut 60. Tabel `suppliers` tidak punya kolom `origin`
dan tidak ikut dibersihkan purge, jadi baris ke-61 itu menetap selamanya dan
angkanya tidak bisa pulih dengan reset apa pun.

Kontrak baru: nama Unicode dipasang pada pemasok yang SUDAH ada (deterministik:
yang sudah bernama itu, jika tidak ada maka id terkecil). Jumlah baris tidak
berubah, dan menjalankannya dua kali memilih baris yang sama.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Supplier
from app.seed.demo_extra import PEMASOK_UNICODE, pastikan_pemasok_unicode
from tests.dsn import DSN_ASYNC


def _jalankan(fn):
    async def _main():
        engine = create_async_engine(DSN_ASYNC)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await engine.dispose()

    return asyncio.run(_main())


def test_pemasok_unicode_tidak_menambah_baris_dan_idempoten():
    async def _t(db):
        asal = list((await db.execute(select(Supplier))).scalars())
        assert asal, "butuh direktori pemasok di DB"

        # Snapshot SEBELUM helper mengubah objek ORM di memori.
        asli = {s.id: (s.name, s.address, s.contact_name) for s in asal}
        jumlah_awal = len(asal)

        try:
            pertama = await pastikan_pemasok_unicode(db, asal)
            await db.commit()

            total = int(
                (await db.execute(text("SELECT count(*) FROM suppliers"))).scalar()
            )
            assert total == jumlah_awal, "jumlah pemasok tidak boleh bertambah"

            unicode_rows = int(
                (
                    await db.execute(
                        text("SELECT count(*) FROM suppliers WHERE name = :n"),
                        {"n": PEMASOK_UNICODE},
                    )
                ).scalar()
            )
            assert unicode_rows == 1, "tepat satu baris memakai nama Unicode"

            kedua = await pastikan_pemasok_unicode(db, asal)
            await db.commit()
            assert pertama == kedua, "pilihan pemasok harus deterministik"

            total_lagi = int(
                (await db.execute(text("SELECT count(*) FROM suppliers"))).scalar()
            )
            assert total_lagi == jumlah_awal
        finally:
            # Pulihkan nilai asli baris yang mungkin tersentuh helper.
            for sid, (nama, alamat, kontak) in asli.items():
                await db.execute(
                    text(
                        "UPDATE suppliers SET name=:n, address=:a, contact_name=:c "
                        "WHERE id=:i"
                    ),
                    {"n": nama, "a": alamat, "c": kontak, "i": sid},
                )
            await db.commit()

    _jalankan(_t)
