"""KPI × penerimaan: cakupan sesi demo dan kg yang benar-benar DITIMBANG.

Dua cacat yang ditutup di sini (demo "kasus pengiriman", 29 Okt 2026):

1. **Penerimaan yang disetujui tidak pernah terlihat KPI.** Baris
   `batch_receipts` distempel `demo_session_id` sesi yang sedang berjalan
   (tabel itu tidak punya kolom `origin`, jadi `boleh_distempel` selalu
   mengizinkannya), sementara batch-nya sering baris kanonik `origin='seed'`
   tanpa stempel. Predikat cakupan lama menuntut KEDUA sisi cocok:
   - cakupan operasional (`r.demo_session_id IS NULL`) → baris berstempel, gugur;
   - cakupan demo (`r.demo_session_id = :sesi AND b.demo_session_id = :sesi`)
     → batch tanpa stempel, gugur.
   Hasil terukur: menyetujui penerimaan menambah stok (Overview bergerak) tetapi
   NOL metrik KPI bergerak. Kontrak sekarang: yang menentukan cakupan adalah
   BARIS FAKTANYA (penerimaan), batch hanya dimensi.

2. **Proyeksi porsi & estimasi susut memakai berat PESANAN.** Keduanya
   menjumlahkan `batches.quantity_kg`, padahal yang masuk dapur adalah
   `batch_receipts.accepted_kg` (timbangan) — Dok 05 §5.1: memakai berat batch
   berarti mengklaim bahan yang tidak pernah sampai. Kontrak sekarang:
   `COALESCE(accepted_kg, quantity_kg)`; baris lama tanpa timbangan tetap sah.

Jendela uji 2032 sengaja jauh dari data kanon/demo, dan semua baris dibersihkan
di `finally` supaya DB gate bisa dipakai ulang.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import settlement
from app.services.kpi_service import compute_kpis
from tests.dsn import DSN_ASYNC

AWAL = datetime(2032, 3, 1, tzinfo=timezone.utc)
AKHIR = datetime(2032, 3, 31, tzinfo=timezone.utc)
KOMODITAS_UJI = ("beras", "telur", "ayam", "wortel")


def _jalankan(fn):
    async def _main():
        eng = create_async_engine(DSN_ASYNC)
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await eng.dispose()

    return asyncio.run(_main())


def _metrik(hasil) -> dict[str, dict]:
    return {m["name"]: m for m in hasil}


async def _sesi_demo(db) -> uuid.UUID:
    """Sesi demo 'expired' — cukup sebagai pemilik fakta, tidak perlu aktif."""
    sesi = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO demo_sessions (id, status, started_at, expires_at, anchor_now, "
            "mode, evaluation_anchor) VALUES (:id, 'expired', :d, :d, :d, 'replay', :d)"
        ),
        {"id": sesi, "d": AWAL},
    )
    return sesi


async def _dimensi(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str, float]:
    """(lokasi, komoditas, pemasok, nama komoditas, gram per porsi)."""
    lokasi = (await db.execute(text("SELECT id FROM locations ORDER BY name LIMIT 1"))).scalar()
    pemasok = (await db.execute(text("SELECT id FROM suppliers ORDER BY name LIMIT 1"))).scalar()
    for nama in KOMODITAS_UJI:
        baris = (
            await db.execute(
                text("SELECT id FROM commodities WHERE lower(name) = :n LIMIT 1"),
                {"n": nama},
            )
        ).scalar()
        gram = settlement._gram_per_porsi(nama)
        if baris is not None and gram:
            return lokasi, baris, pemasok, nama, float(gram)
    pytest.fail("DB uji butuh satu komoditas ber-gram/porsi (beras/telur/ayam/wortel)")


async def _batch_dan_penerimaan(
    db,
    *,
    sesi: uuid.UUID | None,
    pesanan_kg: float,
    timbangan_kg: float | None,
    origin_batch: str = "seed",
    stempel_batch: bool = True,
) -> uuid.UUID:
    """Batch + satu penerimaan DISETUJUI di jendela uji. Kembalikan id batch.

    `stempel_batch=False` meniru keadaan nyata yang paling sering terjadi:
    penerimaan dicatat di dalam sesi demo (jadi barisnya berstempel), tetapi
    batch-nya baris kanonik `origin='seed'` yang TIDAK boleh berstempel
    (`boleh_distempel`). Itulah kombinasi yang dulu menghilang dari kedua
    cakupan KPI.
    """
    lokasi, komoditas, pemasok, _, _ = await _dimensi(db)
    batch_id = uuid.uuid4()
    sekarang = AWAL + timedelta(days=2)
    await db.execute(
        text(
            "INSERT INTO batches (id, commodity_id, location_id, supplier_id, quantity_kg, "
            "harvested_at, temperature_log, certification_status, freshness_score, "
            "safety_status, usable_until, origin, demo_session_id) VALUES "
            "(:id, :komoditas, :lokasi, :pemasok, :kg, :panen, :log, 'hygiene', 0.95, "
            "'pass', :layak, :origin, :sesi)"
        ),
        {
            "id": batch_id,
            "komoditas": komoditas,
            "lokasi": lokasi,
            "pemasok": pemasok,
            "kg": pesanan_kg,
            "panen": sekarang - timedelta(hours=6),
            "log": json.dumps([{"jam": (sekarang - timedelta(hours=6)).isoformat(), "suhu_c": 4}]),
            "layak": sekarang + timedelta(days=20),
            "origin": origin_batch,
            "sesi": sesi if stempel_batch else None,
        },
    )
    await db.execute(
        text(
            "INSERT INTO batch_receipts (id, batch_id, checked, recorded_by, recorded_at, "
            "status, reviewed_at, ordered_kg, accepted_kg, demo_session_id) VALUES "
            "(:id, :batch, CAST(:cek AS jsonb), :oleh, :catat, 'disetujui', :tinjau, "
            ":pesan, :terima, :sesi)"
        ),
        {
            "id": uuid.uuid4(),
            "batch": batch_id,
            "cek": json.dumps({"suhu": True, "kemasan": True, "jumlah": True}),
            "oleh": (await db.execute(text("SELECT id FROM users LIMIT 1"))).scalar(),
            "catat": sekarang - timedelta(minutes=30),
            "tinjau": sekarang,
            "pesan": pesanan_kg,
            "terima": timbangan_kg,
            "sesi": sesi,
        },
    )
    return batch_id


async def _bersihkan(db, batch_id: uuid.UUID) -> None:
    await db.execute(
        text("DELETE FROM batch_receipts WHERE batch_id = :b"), {"b": batch_id}
    )
    await db.execute(text("DELETE FROM batches WHERE id = :b"), {"b": batch_id})
    await db.execute(
        text("DELETE FROM demo_sessions WHERE anchor_now = :d"), {"d": AWAL}
    )
    await db.commit()


def test_penerimaan_sesi_demo_menggerakkan_kpi_walau_batch_kanonik():
    """Disetujui di sesi demo, batch kanonik → KPI cakupan sesi itu WAJIB memuatnya."""

    async def _skenario(db):
        sesi = await _sesi_demo(db)
        batch = await _batch_dan_penerimaan(
            db,
            sesi=sesi,
            pesanan_kg=540,
            timbangan_kg=None,
            origin_batch="seed",
            stempel_batch=False,
        )
        await db.commit()
        try:
            demo = _metrik(await compute_kpis(
                db, AWAL, AKHIR, None, include_demo=True, demo_session_id=sesi))
            operasional = _metrik(await compute_kpis(
                db, AWAL, AKHIR, None, include_demo=False))
            return demo, operasional
        finally:
            await _bersihkan(db, batch)

    demo, operasional = _jalankan(_skenario)
    est = demo["Meal Continuity Rate"]["estimate"]
    assert est["state"] == "available", est
    # Cadangan berat pesanan sah untuk baris tanpa timbangan: 540 kg.
    assert float(est["value"]) == pytest.approx(5400.0), est
    # Fakta sesi demo tidak boleh bocor ke angka operasional.
    assert operasional["Meal Continuity Rate"]["estimate"]["state"] == "no_data"


def test_proyeksi_dan_susut_memakai_kg_timbangan():
    """`accepted_kg` (timbangan) menang atas `batches.quantity_kg` (pesanan)."""

    async def _skenario(db):
        sesi = await _sesi_demo(db)
        batch = await _batch_dan_penerimaan(
            db, sesi=sesi, pesanan_kg=540, timbangan_kg=512, origin_batch="demo"
        )
        await db.commit()
        try:
            demo = _metrik(await compute_kpis(
                db, AWAL, AKHIR, None, include_demo=True, demo_session_id=sesi))
            return demo
        finally:
            await _bersihkan(db, batch)

    demo = _jalankan(_skenario)
    est = demo["Meal Continuity Rate"]["estimate"]
    assert est["state"] == "available", est
    # 512 kg beras ÷ 100 g/porsi = 5.120 porsi (bukan 5.400 dari berat pesanan).
    assert float(est["value"]) == pytest.approx(5120.0), est
    susut = demo["Avoidable Food Loss"]["estimate"]
    assert susut["state"] == "available", susut
    # Susut diperkirakan dari kg DITERIMA: 512 × (1 − 0,95) = 25,6 kg.
    assert float(susut["value"]) == pytest.approx(25.6, abs=0.05), susut


def test_penerimaan_tidak_bocor_ke_sesi_lain():
    """Sesi lain tidak boleh mewarisi penerimaan milik sesi ini."""

    async def _skenario(db):
        sesi = await _sesi_demo(db)
        sesi_lain = await _sesi_demo(db)
        batch = await _batch_dan_penerimaan(
            db, sesi=sesi, pesanan_kg=300, timbangan_kg=290, origin_batch="demo"
        )
        await db.commit()
        try:
            lain = _metrik(await compute_kpis(
                db, AWAL, AKHIR, None, include_demo=True, demo_session_id=sesi_lain))
            return lain
        finally:
            await _bersihkan(db, batch)

    lain = _jalankan(_skenario)
    assert lain["Meal Continuity Rate"]["estimate"]["state"] == "no_data"
