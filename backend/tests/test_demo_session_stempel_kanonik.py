"""Invarian: baris kanonik (`origin='seed'`) TIDAK PERNAH berstempel sesi demo.

Regresi 27 Okt 2026 (gate `verify/invariants.spec.json` FAIL 4): penjaga
`before_flush` di `app/services/demo_session.py` menstempel SETIAP objek ORM baru
selama sesi aktif. Jalur "Siapkan data demo" membangun ulang template SAAT sesi
berjalan (`services/demo_template_reset.py`), dan `load_seed` menulis snapshot
kanonik lewat `merge()` (ORM) — hasilnya 78 batch + 40 fakta pasokan + 7
keputusan ber-`origin='seed'` ikut berstempel sesi aktif.

Kontrak yang dikunci di sini:

1. `boleh_distempel()` = hanya baris DEMO; baris tanpa `origin` (default DB
   `'seed'`) dianggap kanonik; tabel jembatan tanpa kolom `origin` tetap boleh
   distempel karena barisnya memang lahir dari sesi.
2. Penjaga flush nyata memakai aturan itu (bukan hanya fungsi murninya).
3. `_bekukan()` melepas stempel yang terlanjur menempel pada baris non-demo
   (jaring untuk data lama), tanpa menulis ulang `origin`.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import Batch, BatchReceipt, Commodity, DemoSession, Location, Supplier
from app.services import demo_session as sesi
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DSN = os.environ.get("TEST_DATABASE_URL", DSN_ASYNC)


@asynccontextmanager
async def _db():
    engine = create_async_engine(DSN)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _referensi(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Satu (lokasi, komoditas, pemasok) yang SUDAH ada — tanpa menambah baris."""
    lok = (await db.execute(select(Location.id).limit(1))).scalar_one_or_none()
    kom = (await db.execute(select(Commodity.id).limit(1))).scalar_one_or_none()
    sup = (await db.execute(select(Supplier.id).limit(1))).scalar_one_or_none()
    if lok is None or kom is None or sup is None:
        pytest.skip("DB tanpa data referensi — semai dulu (init-demo)")
    return lok, kom, sup


def _batch(lok, kom, sup, *, origin: str | None) -> Batch:
    nilai: dict[str, object] = {
        "commodity_id": kom,
        "location_id": lok,
        "supplier_id": sup,
        "quantity_kg": 10,
        "harvested_at": datetime.now(UTC) - timedelta(hours=2),
    }
    if origin is not None:
        nilai["origin"] = origin
    return Batch(**nilai)


# ── 1. Aturan fungsi murni ─────────────────────────────────────────────────


def test_boleh_distempel_hanya_baris_demo():
    assert sesi.boleh_distempel(_batch(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), origin="demo"))
    assert not sesi.boleh_distempel(
        _batch(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), origin="seed")
    )
    # `origin` kosong = default kolom 'seed' (kanonik) -> tidak distempel.
    assert not sesi.boleh_distempel(_batch(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), origin=None))


def test_tabel_jembatan_tanpa_origin_tetap_distempel():
    """Tabel tanpa kolom `origin` tidak bisa dibedakan; barisnya lahir dari sesi."""
    assert sesi.boleh_distempel(BatchReceipt())


# ── 2. Penjaga flush nyata ─────────────────────────────────────────────────


async def _sesi_sementara(db, *, commit: bool) -> DemoSession:
    """Baris `demo_sessions` sungguhan untuk stempel (FK `batches`).

    `commit=False` dipakai saat skenario akan rollback (tidak meninggalkan apa
    pun); `commit=True` dipakai skenario yang harus commit, dan pemanggil
    menghapusnya di `finally`.
    """
    saat = datetime.now(UTC)
    baris = DemoSession(
        id=uuid.uuid4(),
        status="active",
        started_at=saat,
        expires_at=saat + timedelta(hours=1),
        anchor_now=saat,
        template_version="uji-stempel",
    )
    db.add(baris)
    await db.flush()
    if commit:
        await db.commit()
    return baris


def test_penjaga_flush_tidak_menstempel_baris_kanonik(monkeypatch):
    """Baris `origin='seed'` yang lahir saat sesi aktif tetap tanpa stempel."""
    monkeypatch.setattr(settings, "demo_session_enforce", True)
    sid = uuid.uuid4()

    async def _skenario() -> None:
        async with _db() as db:
            lok, kom, sup = await _referensi(db)
            semu = await _sesi_sementara(db, commit=False)
            sid_nyata = semu.id
            sesi.set_sesi(sid_nyata)
            kanonik = _batch(lok, kom, sup, origin="seed")
            bawaan = _batch(lok, kom, sup, origin=None)
            demo = _batch(lok, kom, sup, origin="demo")
            db.add_all([kanonik, bawaan, demo])
            try:
                await db.flush()
                assert kanonik.demo_session_id is None, "baris seed berstempel sesi"
                assert bawaan.demo_session_id is None, "baris default-seed berstempel sesi"
                assert demo.demo_session_id == sid_nyata, "baris demo tidak distempel"
            finally:
                # Tidak pernah commit: tidak ada baris uji yang tertinggal.
                await db.rollback()

    sesi.set_sesi(sid)
    try:
        asyncio.run(_skenario())
    finally:
        sesi.set_sesi(None)


# ── 3. `_bekukan` melepas stempel kanonik yang terlanjur ada ───────────────


def test_bekukan_melepas_stempel_kanonik():
    """Data lama: stempel pada baris non-demo dilepas pada level query."""
    from app.seed import demo_template as dt

    bid = uuid.uuid4()

    async def _jalankan():
        async with _db() as db:
            lok, kom, sup = await _referensi(db)
            semu = await _sesi_sementara(db, commit=True)
            try:
                db.add(
                    Batch(
                        id=bid,
                        commodity_id=kom,
                        location_id=lok,
                        supplier_id=sup,
                        quantity_kg=10,
                        harvested_at=datetime.now(UTC) - timedelta(hours=2),
                        origin="seed",
                        demo_session_id=semu.id,  # stempel yang seharusnya tidak ada
                    )
                )
                await db.commit()
                laporan = await dt._bekukan(db)
                bersih = (
                    await db.execute(
                        text("SELECT demo_session_id FROM batches WHERE id = :i"),
                        {"i": bid},
                    )
                ).scalar_one()
                asal = (
                    await db.execute(
                        text("SELECT origin FROM batches WHERE id = :i"), {"i": bid}
                    )
                ).scalar_one()
                return laporan, bersih, asal
            finally:
                await db.execute(text("DELETE FROM batches WHERE id = :i"), {"i": bid})
                await db.execute(
                    text("DELETE FROM demo_sessions WHERE id = :i"), {"i": semu.id}
                )
                await db.commit()

    laporan, bersih, asal = asyncio.run(_jalankan())
    assert laporan["stempel_kanonik_dilepas"] >= 1
    assert bersih is None, "stempel sesi masih menempel pada baris kanonik"
    assert asal == "seed", "`_bekukan` tidak boleh menulis ulang origin"
