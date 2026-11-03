"""Kebenaran laporan `bangun_ulang` (temuan F7, 26 Okt 2026).

Dua hal yang dibuktikan, dan keduanya hanya bisa dibuktikan dengan build
sungguhan di DB terpisah:

1. **Angka yang dilaporkan = isi tabel.** `bangun_ulang` menjalankan tiga
   langkah sesudah `build_into` (deret waktu, aktivitas, pelengkap cakupan).
   Langkah-langkah itu menambah baris. Laporan yang diambil dari `build_into`
   saja melaporkan keadaan di tengah proses — terukur 26 Okt 2026 di DB klon:
   endpoint melaporkan 36 keputusan/120 batch, isi tabel 48/125.
2. **Build kedua tidak mengubah jumlah baris.** Rebuild dipakai berulang saat
   geladi; kalau idempoten, angka awal selalu kembali.

Kenapa di-skip secara default: satu build memakan ±40 detik dan mem-purge
seluruh baris operasional. `pytest` biasa tidak boleh melakukannya pada DB
bersama (lihat `AGENTS.md`: AUD-TEST-02). Jalankan eksplisit:

    MCG_BUILD_IT=1 DATABASE_URL=.../mealchain_gate \
        pytest tests/test_demo_template_reset_laporan.py -q
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import demo_template_reset as reset

pytestmark = pytest.mark.skipif(
    os.environ.get("MCG_BUILD_IT") != "1",
    reason="build sungguhan: set MCG_BUILD_IT=1 dan DATABASE_URL ke DB terpisah",
)

_SQL = text(
    "select (select count(*) from decisions) as keputusan,"
    " (select count(*) from batches) as batch,"
    " (select count(*) from approvals) as persetujuan,"
    " (select count(*) from ledger_blocks) as blok"
)


async def _angka(db) -> dict:
    baris = (await db.execute(_SQL)).mappings().one()
    return dict(baris)


async def test_laporan_bangun_ulang_sama_dengan_isi_tabel():
    """Yang dilaporkan ke operator harus keadaan AKHIR, bukan keadaan tengah."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    buat_sesi = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with buat_sesi() as db:
            laporan = await reset.bangun_ulang(db)
            nyata = await _angka(db)
    finally:
        await engine.dispose()

    dilaporkan = laporan["hitung"]
    assert dilaporkan["decisions"] == nyata["keputusan"], (
        f"laporan keputusan {dilaporkan['decisions']} != tabel {nyata['keputusan']}"
    )
    assert dilaporkan["batches"] == nyata["batch"], (
        f"laporan batch {dilaporkan['batches']} != tabel {nyata['batch']}"
    )
    assert dilaporkan["ledger"] == nyata["blok"], (
        f"laporan blok ledger {dilaporkan['ledger']} != tabel {nyata['blok']}"
    )


async def test_bangun_ulang_dua_kali_tidak_mengubah_jumlah_baris():
    """Rebuild kedua harus mengembalikan angka yang sama, bukan menumpuk."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    buat_sesi = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with buat_sesi() as db:
            await reset.bangun_ulang(db)
            pertama = await _angka(db)
            await reset.bangun_ulang(db)
            kedua = await _angka(db)
    finally:
        await engine.dispose()

    for kunci in ("keputusan", "batch", "persetujuan"):
        assert kedua[kunci] == pertama[kunci], (
            f"{kunci}: build pertama {pertama[kunci]}, build kedua {kedua[kunci]}"
        )


async def test_setiap_keputusan_punya_minimal_satu_jejak():
    """Keputusan tanpa jejak = kartu yang tidak bisa dipertanggungjawabkan.

    Gerbang `verify/invariants.spec.json` mengecek ini dan sempat gagal
    (9 keputusan `extra:*` tanpa satu pun langkah). Tes ini menjaga penyebabnya.
    """
    engine = create_async_engine(os.environ["DATABASE_URL"])
    buat_sesi = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with buat_sesi() as db:
            await reset.bangun_ulang(db)
            yatim = (
                await db.execute(
                    text(
                        "select count(*) from decisions d "
                        "left join agent_traces t on t.decision_id = d.id "
                        "where t.id is null"
                    )
                )
            ).scalar_one()
    finally:
        await engine.dispose()

    assert yatim == 0, f"{yatim} keputusan tanpa jejak langkah"
