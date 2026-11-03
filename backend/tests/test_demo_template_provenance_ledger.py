"""Provenance data demo & cakupan ledger setelah bangun-ulang.

Dua temuan audit 26 Okt 2026 dikunci di sini:

- **D-04** `_bekukan()` dulu menulis `origin='seed'` untuk semua baris demo.
  Provenance-nya hilang (26 keputusan `demo_case` ber-`origin='seed'`), dan
  invarian "baris kanonik tidak boleh berstempel" lulus secara VAKUM karena
  tidak ada satu pun baris `origin='demo'`. Kontrak sekarang: `origin` tidak
  pernah ditulis ulang; penanda beku adalah stempel ke sesi sentinel `cetakan`
  yang tidak pernah aktif, sehingga penyapu sesi tidak menghapus template.
- **D-02** menghapus keputusan yang sudah punya blok ledger (mis.
  `_seed_demo_cases(force=True)`) meninggalkan blok yatim di generasi aktif.
  Kontrak sekarang: generasi dinaikkan saat baris berblok dihapus.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.services import demo_session as sesi


def _jalankan(fn):
    async def _main():
        eng = create_engine(settings.database_url)
        maker = create_session_maker(eng)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await eng.dispose()

    return asyncio.run(_main())


def _koneksi():
    from sqlalchemy import create_engine as create_sync_engine

    from tests.dsn import DSN_SYNC

    return create_sync_engine(DSN_SYNC, pool_pre_ping=True)


# ── D-04: penanda beku tidak boleh mengubah provenance ──────────────────────


@pytest.fixture(scope="module", autouse=True)
def _kasus_demo_ada():
    """Pastikan KASUS DEMO ada sebelum modul ini mengukur provenance.

    Modul sebelumnya (mis. `test_demo_seed*`, reset template, purge) menghapus
    keputusan demo. Tanpa prasyarat ini `_bekukan()` tidak menemukan satu pun
    baris `demo_case`, dan tes gagal dengan "keputusan demo_case tidak lagi
    ber-origin demo" — pesan yang menyalahkan kontrak provenance padahal yang
    kosong adalah datanya (terukur: merah di suite penuh, lulus sendiri).
    Penyemaian memakai jalur resmi `_seed_demo_cases(force=True)`, bukan INSERT
    karangan, dan idempoten.
    """
    from app.api.demo import _seed_demo_cases
    from app.models import Location

    async def _siapkan(db) -> None:
        jakarta = (
            await db.execute(select(Location).where(Location.name == "Jakarta"))
        ).scalar_one()
        await _seed_demo_cases(db, True, jakarta)
        await db.commit()

    _jalankan(_siapkan)


def test_bekukan_mempertahankan_origin_demo():
    """`_bekukan` menstempel cetakan; `origin` TIDAK ditulis ulang."""
    from app.seed import demo_template as dt

    laporan = _jalankan(dt._bekukan)
    assert laporan["baris_dibekukan"] > 0

    cetakan = str(sesi.CETAKAN_ID)
    with _koneksi().connect() as conn:
        origin_demo = conn.execute(
            text("SELECT count(*) FROM decisions WHERE origin = 'demo'")
        ).scalar_one()
        kasus_demo = conn.execute(
            text(
                "SELECT count(*) FROM decisions "
                "WHERE demo_case IS NOT NULL AND origin = 'demo'"
            )
        ).scalar_one()
        kasus_tercampur = conn.execute(
            text(
                "SELECT count(*) FROM decisions "
                "WHERE demo_case IS NOT NULL AND origin = 'seed'"
            )
        ).scalar_one()
        demo_tanpa_cetakan = conn.execute(
            text(
                "SELECT count(*) FROM decisions "
                "WHERE origin = 'demo' AND demo_session_id IS DISTINCT FROM :c"
            ),
            {"c": cetakan},
        ).scalar_one()
        kanonik_berstempel = conn.execute(
            text(
                "SELECT count(*) FROM decisions "
                "WHERE origin = 'seed' AND demo_session_id IS NOT NULL"
            )
        ).scalar_one()

    assert origin_demo > 0, "provenance demo hilang — cek kanonik akan lulus vakum"
    assert kasus_demo > 0, "keputusan demo_case tidak lagi ber-origin demo"
    assert kasus_tercampur == 0, "masih ada keputusan demo_case ber-origin 'seed'"
    assert demo_tanpa_cetakan == 0, "baris demo belum ditandai cetakan"
    assert kanonik_berstempel == 0


def test_cetakan_sesi_tidak_pernah_aktif():
    """Sesi sentinel tidak boleh muncul sebagai sesi aktif."""
    sentinel = _jalankan(lambda db: sesi.cetakan(db))
    assert sentinel == sesi.CETAKAN_ID

    aktif = _jalankan(lambda db: sesi._sesi_aktif_terakhir(db))
    assert aktif is None or aktif.id != sesi.CETAKAN_ID

    with _koneksi().connect() as conn:
        status, versi = conn.execute(
            text("SELECT status, template_version FROM demo_sessions WHERE id = :i"),
            {"i": sentinel},
        ).one()

    assert status == "expired"
    assert versi == "cetakan"


# ── D-02: tidak ada blok ledger yatim di generasi aktif ─────────────────────

ORPHAN_SQL = """
SELECT count(*) FROM ledger_blocks lb
WHERE lb.generation = :g AND lb.entity_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.id = lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM batches b WHERE b.id = lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM locations l WHERE l.id = lb.entity_id)
"""


def test_hapus_kasus_demo_menaikkan_generasi_ledger():
    """Menghapus keputusan berblok tidak boleh menyisakan yatim di generasi aktif.

    Blok ledger **dibuat di dalam tes**, bukan diharapkan dari data demo: pada
    suite penuh tes lain sudah membersihkan keputusan demo, sehingga keputusan
    yang dihapus tidak punya blok dan versi yang mengandalkan keadaan DB gagal
    dengan "generasi tidak naik" — merah palsu yang menyalahkan kode padahal
    keadaan data (terukur: 1 kegagalan di suite penuh, lulus saat berdiri sendiri).

    Keputusan yang dipilih WAJIB ber-`demo_case` di `DEMO_CASES`: itulah himpunan
    yang benar-benar dihapus `_seed_demo_cases(force=True)`. Dulu tes mengambil
    `limit(1)` tanpa filter, sehingga di suite penuh ia bisa memilih baris
    `bukti-hari-ini` (dari seeder lain) yang TIDAK ikut terhapus — generasi
    memang tidak naik, dan tes merah padahal kode benar.
    """
    from app.api.demo import DEMO_CASES, _seed_demo_cases
    from app.models import Decision, Location
    from app.services.ledger_service import append_block

    dipilih: list = []

    async def _siapkan(db) -> None:
        jakarta = (
            await db.execute(select(Location).where(Location.name == "Jakarta"))
        ).scalar_one()
        await _seed_demo_cases(db, True, jakarta)
        await db.flush()
        kasus = (
            await db.execute(
                select(Decision.id)
                .where(
                    Decision.demo_case.in_(DEMO_CASES),
                    Decision.target_location_id == jakarta.id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        assert kasus is not None, "seed demo tidak menghasilkan kasus Jakarta"
        dipilih.append(kasus)
        # Satu blok di generasi aktif menunjuk keputusan yang akan dihapus.
        await append_block(db, "uji_generasi", kasus, None, {"uji": True})
        await db.commit()

    async def _hapus(db) -> None:
        jakarta = (
            await db.execute(select(Location).where(Location.name == "Jakarta"))
        ).scalar_one()
        await _seed_demo_cases(db, True, jakarta)
        # Prasyarat yang dulu tersirat: keputusan berblok benar-benar terhapus.
        tersisa = (
            await db.execute(select(Decision.id).where(Decision.id == dipilih[0]))
        ).scalar_one_or_none()
        assert tersisa is None, (
            "prasyarat: keputusan berblok harus ikut terhapus oleh "
            "`_seed_demo_cases(force=True)` — kalau tidak, generasi memang "
            "tidak akan naik"
        )
        await db.commit()

    _jalankan(_siapkan)

    with _koneksi().connect() as conn:
        sebelum = conn.execute(
            text("SELECT generation FROM ledger_meta WHERE id = 1")
        ).scalar_one()

    _jalankan(_hapus)

    with _koneksi().connect() as conn:
        generasi = conn.execute(
            text("SELECT generation FROM ledger_meta WHERE id = 1")
        ).scalar_one()
        yatim = conn.execute(text(ORPHAN_SQL), {"g": generasi}).scalar_one()

    assert generasi > sebelum, "generasi tidak naik padahal keputusan berblok dihapus"
    assert yatim == 0, f"{yatim} blok generasi aktif menunjuk entitas yang sudah dihapus"
