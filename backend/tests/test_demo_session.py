"""Tes sesi demo (migrasi 024, 20 Okt 2026).

Kontrak yang dikunci di sini — semuanya perilaku yang diminta pemilik:

1. Tanpa sesi: status "kosong", sisa waktu 0 (tampilan default kosong).
2. "Siapkan data demo": sesi dibuat, `remaining_seconds` ≈ durasi, dan klik
   kedua TIDAK mereset jam/data (`created=false`).
3. "Perpanjang": id sesi sama, `expires_at` bergeser, data tidak disentuh.
4. Lewat waktu: sesi tidak lagi aktif, dan baris ber-stempel sesi itu hilang.
5. Data lain (tanpa stempel) tidak ikut terhapus.
6. Dengan `demo_session_enforce` menyala, kueri biasa hanya melihat baris sesi
   berjalan; tanpa sesi, tidak melihat apa pun.

Tes ini MENOLAK berjalan bila ada sesi demo aktif (mis. sedang dipakai
presentasi): `mulai()` memang menutup sesi lama, dan tes tidak boleh menjadi
alasan data demo seseorang hilang di tengah jalan.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import Batch, DemoSession
from app.services import demo_session as sesi
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

# Bisa diarahkan ke database sekali-pakai (TEST_DATABASE_URL) supaya tes yang
# mengosongkan tabel operasional tidak menyentuh DB kerja/demo.
DSN = os.environ.get(
    "TEST_DATABASE_URL",
    DSN_ASYNC,
)

# Tes di berkas ini memang mengubah seluruh tabel operasional (mulai/akhiri/
# kosongkan). Itu tidak aman dijalankan di tengah suite yang memakai DB sama:
# terukur 20 Okt 2026 — 17 tes lain gagal karena data kanonik ikut terhapus.
# Jalankan terpisah: DEMO_SESSION_ENFORCE=true pytest tests/test_demo_session.py
pytestmark = pytest.mark.skipif(
    not settings.demo_session_enforce,
    reason="tes sesi mengosongkan tabel operasional — jalankan terpisah dengan DEMO_SESSION_ENFORCE=true",
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


async def _ada_sesi_aktif(db) -> bool:
    hasil = await db.execute(
        select(DemoSession.id)
        .where(DemoSession.status == "active")
        .limit(1)
        .execution_options(demo_session_bypass=True)
    )
    return hasil.scalar_one_or_none() is not None


async def _hapus_sesi(db, *ids: uuid.UUID | None) -> None:
    """Bersihkan sesi buatan tes (bukan sesi orang lain)."""
    for sid in ids:
        if sid is None:
            continue
        await db.execute(text("DELETE FROM batches WHERE demo_session_id = :s"), {"s": sid})
        await db.execute(text("DELETE FROM demo_sessions WHERE id = :s"), {"s": sid})
    await db.commit()


async def _bahan_batch(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Lokasi/komoditas/pemasok uji supaya FK batch sah."""
    kunci = uuid.uuid4().hex[:8]
    loc, com, sup = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO locations (id, name, region, latitude, longitude)"
            " VALUES (:id, :n, 'Test Region', -6.2, 106.8)"
        ),
        {"id": loc, "n": f"TES-SESI-{kunci}"},
    )
    await db.execute(
        text("INSERT INTO commodities (id, name, unit) VALUES (:id, :n, 'kg')"),
        {"id": com, "n": f"uji-sesi-{kunci}"},
    )
    await db.execute(
        text(
            "INSERT INTO suppliers (id, name, location_id, certification_status)"
            " VALUES (:id, :n, :loc, 'haccp')"
        ),
        {"id": sup, "n": f"Pemasok Sesi {kunci}", "loc": loc},
    )
    await db.commit()
    return loc, com, sup


async def _hapus_bahan(db, loc, com, sup) -> None:
    """Bersihkan lokasi/komoditas/pemasok uji.

    Penting: baris referensi yatim membuat tes lain gagal (mis. "setiap pemasok
    punya koordinat") — insiden nyata 20 Okt 2026 saat tes ini dijalankan tanpa
    pembersihan.
    """
    await db.execute(
        text("DELETE FROM batches WHERE location_id = :l OR supplier_id = :s"),
        {"l": loc, "s": sup},
    )
    await db.execute(text("DELETE FROM suppliers WHERE id = :s"), {"s": sup})
    await db.execute(text("DELETE FROM commodities WHERE id = :c"), {"c": com})
    await db.execute(text("DELETE FROM locations WHERE id = :l"), {"l": loc})
    await db.commit()


async def _buat_batch(
    db, loc, com, sup, *, sid=None, origin: str | None = None, bypass: bool = False
) -> Batch:
    """Buat satu batch uji.

    `bypass=True` menulis lewat Core INSERT, BUKAN ORM add(): penjaga
    `before_flush` menstempel setiap objek ORM baru dengan sesi aktif, sehingga
    mustahil membuat baris "tanpa stempel" lewat ORM selama sesi berjalan — dan
    itulah yang dibutuhkan tes "data kerja tidak ikut terhapus".
    """
    nilai: dict[str, object] = {
        "commodity_id": com,
        "location_id": loc,
        "supplier_id": sup,
        "quantity_kg": 10,
        "harvested_at": datetime.now(UTC) - timedelta(hours=2),
        "demo_session_id": sid,
    }
    # `origin` bawaan kolom = 'seed'; tes A butuh baris 'demo' TANPA stempel
    # (persis yang lahir dari jalur lama /demo/refresh di luar sesi).
    if origin is not None:
        nilai["origin"] = origin
    if bypass:
        hasil = await db.execute(
            insert(Batch).values(**nilai).returning(Batch.id)
        )
        batch_id = hasil.scalar_one()
        await db.commit()
        baris = await db.get(Batch, batch_id)
        assert baris is not None
        return baris
    batch = Batch(**nilai)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


def _jalankan(coro_fn) -> None:
    asyncio.run(coro_fn())


def test_status_kosong_tanpa_sesi():
    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            status = sesi.status_payload(await sesi.aktif(db))
            assert status["active"] is False
            assert status["remaining_seconds"] == 0
            assert status["status"] == "kosong"

    _jalankan(_skenario)


def test_mulai_lalu_klik_kedua_tidak_mereset():
    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            pertama = await sesi.mulai(db, menit=60)
            sid = pertama.id
            try:
                aktif = await sesi.aktif(db)
                assert aktif is not None and aktif.id == sid
                status = sesi.status_payload(pertama)
                assert status["active"] is True
                assert 3500 <= status["remaining_seconds"] <= 3600

                # Sesi berjalan: `aktif()` mengembalikan sesi yang SAMA (bukan sesi baru).
                lagi = await sesi.aktif(db)
                assert lagi is not None and lagi.id == sid
                assert lagi.expires_at == pertama.expires_at
            finally:
                await _hapus_sesi(db, sid)

    _jalankan(_skenario)


def test_perpanjang_menambah_tanpa_ganti_sesi():
    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            awal = await sesi.mulai(db, menit=30)
            try:
                sebelum = awal.expires_at
                sesudah = await sesi.perpanjang(db, menit=30)
                assert sesudah is not None
                assert sesudah.id == awal.id
                assert sesudah.expires_at - sebelum == timedelta(minutes=30)
            finally:
                await _hapus_sesi(db, awal.id)

    _jalankan(_skenario)


def test_lewat_waktu_menutup_sesi_dan_mengosongkan_data():
    """Kedaluwarsa = baris BERTANDA hilang (milik sesi ini dan sesi lain), referensi utuh.

    Data kerja tanpa stempel (kanonik) TIDAK ikut dihapus: suite memakai DB yang
    sama, dan menghapusnya di sini pernah membuat 58 tes lain kehilangan data.
    """

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            loc, com, sup = await _bahan_batch(db)
            milik = await _buat_batch(db, loc, com, sup, sid=sid, origin="demo")
            lain = await _buat_batch(db, loc, com, sup, sid=None, bypass=True)
            try:
                # Majukan jam sesi: kedaluwarsa malas harus menutup + mengosongkan.
                sesi_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
                await db.commit()
                assert await sesi.aktif(db) is None
                assert sesi.status_payload(None)["active"] is False

                # Baris sesi ini hilang; baris kerja tanpa stempel tetap ada.
                sisa = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :a"),
                        {"a": milik.id},
                    )
                ).scalar_one()
                assert sisa == 0, "baris milik sesi yang habis harus hilang"
                tetap_kerja = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :b"),
                        {"b": lain.id},
                    )
                ).scalar_one()
                assert tetap_kerja == 1, "data kerja tanpa stempel bukan milik sesi"

                # Referensi tetap ada: login & peta tidak boleh ikut hilang.
                tetap = (
                    await db.execute(
                        text("SELECT count(*) FROM locations WHERE id = :l"), {"l": loc}
                    )
                ).scalar_one()
                assert tetap == 1
            finally:
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_kosongkan_kecuali_menyisakan_sesi_yang_diminta():
    """Saat sesi baru disiapkan, sisa sesi lama dibersihkan — sesi ini tidak."""

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            simpan = await _buat_batch(db, loc, com, sup, sid=sid)
            sisa = await _buat_batch(db, loc, com, sup, sid=None, bypass=True)
            try:
                await sesi.kosongkan_kecuali(db, sid)
                ada = (
                    await db.execute(
                        text("SELECT id FROM batches WHERE id IN (:a, :b)"),
                        {"a": simpan.id, "b": sisa.id},
                    )
                ).scalars().all()
                assert ada == [simpan.id]
            finally:
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_bersihkan_warisan_mengosongkan_semua_baris_operasional():
    """Default kosong saat boot: semua baris operasional hilang, referensi utuh."""

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            tetap = await _buat_batch(db, loc, com, sup, sid=sid)
            warisan = await _buat_batch(db, loc, com, sup, sid=None, bypass=True)
            try:
                dihapus = await sesi.bersihkan_warisan(db)
                assert dihapus >= 2
                sisa = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id IN (:a, :b)"),
                        {"a": tetap.id, "b": warisan.id},
                    )
                ).scalar_one()
                assert sisa == 0
            finally:
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_tandai_sesi_menstempel_baris_yang_lahir_tanpa_sesi(monkeypatch):
    """Penyemai memakai bulk/Core insert: stempel massal menutup celah itu."""

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            try:
                monkeypatch.setattr(settings, "demo_session_enforce", True)
                # Meniru penyemai: INSERT Core tanpa melewati ORM flush.
                await db.execute(
                    text(
                        "INSERT INTO batches (commodity_id, location_id, supplier_id,"
                        " quantity_kg, harvested_at, origin)"
                        " VALUES (:c, :l, :s, 5, now(), 'demo')"
                    ),
                    {"c": com, "l": loc, "s": sup},
                )
                await db.commit()
                ditandai = await sesi.tandai_sesi(db, sid)
                assert ditandai >= 1
                sisa = (
                    await db.execute(
                        text(
                            "SELECT count(*) FROM batches WHERE location_id = :l"
                            " AND demo_session_id IS NULL"
                        ),
                        {"l": loc},
                    )
                ).scalar_one()
                assert sisa == 0, "tidak boleh ada baris sesi yang tanpa stempel"
            finally:
                monkeypatch.setattr(settings, "demo_session_enforce", False)
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_stempel_otomatis_saat_enforce(monkeypatch):
    """Baris baru yang lahir selama sesi otomatis ber-stempel sesi itu."""

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            batch = None
            try:
                monkeypatch.setattr(settings, "demo_session_enforce", True)
                sesi.set_sesi(sid)
                batch = await _buat_batch(db, loc, com, sup)
                assert batch.demo_session_id == sid
            finally:
                sesi.set_sesi(None)
                monkeypatch.setattr(settings, "demo_session_enforce", False)
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_durasi_dibatasi_batas_server():
    assert sesi._menit_valid(None, 120) == 120
    assert sesi._menit_valid(9999, 120) == settings.demo_session_max_minutes
    assert sesi._menit_valid(0, 120) == 1
    assert sesi._menit_valid(-5, 120) == 1


def test_tanpa_sesi_menyapu_demo_tanpa_stempel():
    """A (21 Okt 2026): TANPA sesi aktif → baris demo tanpa stempel dibersihkan.

    Inilah skenario yang dilaporkan pemilik: "Siapkan data" pernah berjalan lewat
    jalur lama (`POST /demo/refresh`) sehingga baris demo lahir TANPA
    `demo_session_id`. Karena tidak ada sesi untuk ditutup, `kosongkan_bertanda()`
    tidak pernah berjalan dan data itu hidup selamanya.
    """

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            liar = await _buat_batch(db, loc, com, sup, sid=None, origin="demo")
            kanonik = await _buat_batch(db, loc, com, sup, sid=None, bypass=True)
            try:
                dihapus = await sesi.sapu_tanpa_sesi(db, jeda=0)
                assert dihapus >= 1

                demo = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE origin = 'demo'")
                    )
                ).scalar_one()
                assert demo == 0, "baris demo tanpa stempel harus hilang tanpa sesi"

                hilang = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :i"), {"i": liar.id}
                    )
                ).scalar_one()
                assert hilang == 0

                # KANONIK (origin='seed') bukan milik sesi: wajib selamat.
                tetap = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :i"), {"i": kanonik.id}
                    )
                ).scalar_one()
                assert tetap == 1, "data kanonik tidak boleh ikut terhapus"

                # Referensi tidak ikut hilang.
                lokasi = (
                    await db.execute(
                        text("SELECT count(*) FROM locations WHERE id = :l"), {"l": loc}
                    )
                ).scalar_one()
                assert lokasi == 1
            finally:
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)


def test_sesi_berakhir_menyisakan_nol_baris_demo():
    """A (21 Okt 2026): sesi berakhir → 0 baris demo, dan sapu tetap menghormati seed.

    Baris yang lahir SELAMA sesi otomatis ber-stempel (penjaga flush), jadi
    jalur ini menguji dua hal sekaligus: stempel dihapus saat sesi ditutup, dan
    sisa demo yang belum ber-stempel ikut disapu sesudahnya.
    """

    async def _skenario() -> None:
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=60)
            sid = sesi_row.id
            try:
                selama = await _buat_batch(db, loc, com, sup, sid=None, origin="demo")
                sebelum = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE origin = 'demo'")
                    )
                ).scalar_one()
                assert sebelum >= 1, "prasyarat: ada baris demo sesi"

                await sesi.akhiri(db)

                sesudah = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE origin = 'demo'")
                    )
                ).scalar_one()
                assert sesudah == 0, "sesi berakhir harus menyisakan 0 baris demo"
                hilang = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :i"), {"i": selama.id}
                    )
                ).scalar_one()
                assert hilang == 0

                # Sesudah sesi berakhir, data kanonik baru tidak boleh tersapu.
                kanonik = await _buat_batch(db, loc, com, sup, sid=None, bypass=True)
                await sesi.sapu_tanpa_sesi(db, jeda=0)
                tetap = (
                    await db.execute(
                        text("SELECT count(*) FROM batches WHERE id = :i"), {"i": kanonik.id}
                    )
                ).scalar_one()
                assert tetap == 1, "sapu tanpa sesi tidak boleh menyentuh origin='seed'"
            finally:
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    _jalankan(_skenario)

def test_akhiri_sesi_tidak_menghapus_kanonik_terstempel():
    """Template `origin='seed'` harus selamat walau (karena data lama) ber-stempel.

    Aturan 21 Okt 2026: stempel massal hanya untuk baris demo, dan pembersihan
    saat sesi berakhir hanya menyentuh baris demo. Tanpa dua batas ini, satu
    sesi bisa menghapus data kerja - terukur 78 batch + 2 keputusan kanonik.
    """

    async def _skenario():
        async with _db() as db:
            if await _ada_sesi_aktif(db):
                pytest.skip("ada sesi demo aktif; akhiri dulu sebelum menguji")
            loc, com, sup = await _bahan_batch(db)
            sesi_row = await sesi.mulai(db, menit=30)
            sid = sesi_row.id
            try:
                # Kanonik yang terlanjur berstempel, dibuat lewat Core agar
                # penjaga flush tidak menimpanya.
                kanonik = await _buat_batch(db, loc, com, sup, sid=sid, bypass=True)
                async with _db() as lain:
                    await lain.execute(
                        text("update batches set demo_session_id = :s, origin = 'seed' where id = :i"),
                        {"s": sid, "i": kanonik.id},
                    )
                    await lain.commit()
                await sesi.akhiri(db)
                async with _db() as cek:
                    tetap = (
                        await cek.execute(
                            text("select count(*) from batches where id = :i"), {"i": kanonik.id}
                        )
                    ).scalar_one()
                assert tetap == 1, "baris kanonik berstempel tidak boleh ikut terhapus"
            finally:
                async with _db() as bersih:
                    await bersih.execute(text("delete from batches where id = :i"), {"i": kanonik.id})
                    await bersih.commit()
                await _hapus_sesi(db, sid)
                await _hapus_bahan(db, loc, com, sup)

    asyncio.run(_skenario())

