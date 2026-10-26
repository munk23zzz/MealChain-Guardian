"""Builder tidak boleh mengubah nama/alamat pemasok demo.

Riwayat: `pastikan_pemasok_unicode` dulu MENGGANTI NAMA satu pemasok terpilih
agar UI punya contoh em dash. Efeknya dua:

1. Direktori demo tidak lagi sama dengan `data/seed/suppliers_demo.json`
   (nama asli hilang, dan seed berikutnya menambah baris baru), sehingga
   hitungan 60 pemasok bergeser menjadi 61 dan tidak pulih lewat reset.
2. Nama pengganti mewarisi koordinat pemasok lain, jadi dua pin peta
   bertumpuk di titik yang sama.

Kontrak sekarang: helper hanya MEMBACA. Ia mengembalikan id pemasok yang
kebetulan sudah memuat em dash (bila berkas demo menyediakannya) dan tidak
pernah menulis kolom apa pun.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Supplier
from app.seed.demo_extra import pastikan_pemasok_unicode
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


def test_pemasok_unicode_tidak_mengubah_apa_pun():
    async def _t(db):
        asal = list((await db.execute(select(Supplier))).scalars())
        assert asal, "butuh direktori pemasok di DB"

        sebelum = {str(s.id): (s.name, s.address, s.contact_name) for s in asal}
        jumlah_awal = len(asal)

        pertama = await pastikan_pemasok_unicode(db, asal)
        kedua = await pastikan_pemasok_unicode(db, asal)
        await db.commit()

        total = int((await db.execute(text("SELECT count(*) FROM suppliers"))).scalar())
        assert total == jumlah_awal, "builder tidak boleh menambah/menghapus baris"

        sesudah = {
            str(r[0]): (r[1], r[2], r[3])
            for r in await db.execute(
                text("SELECT id, name, address, contact_name FROM suppliers")
            )
        }
        assert sesudah == sebelum, "nama/alamat/kontak tidak boleh diubah builder"
        assert pertama == kedua, "hasil harus deterministik"

    _jalankan(_t)
