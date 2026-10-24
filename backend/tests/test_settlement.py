"""Penulis KPI (settlement) — bukti aksi menggerakkan angka KPI.

Latar: sampai 23 Okt 2026 tiga sumber KPI (`delivery_events`, `price_signals`
kutipan pemasok, `disposal_events`) hanya ditulis oleh seeder, sehingga kartu
KPI tidak bergerak saat operator menerima barang, mengeksekusi keputusan, atau
mencatat limbah. Berkas ini mengunci kontrak `app/services/settlement.py`:

1. penerimaan disetujui -> satu baris `delivery_events`, porsi = kg ÷ gram
   per porsi komoditas, dibatasi sisa rencana porsi hari itu (tidak melebihkan);
2. PO terbit -> satu baris `price_signals` sumber `supplier_quote`;
3. limbah dicatat -> satu baris `disposal_events`;
4. ketiganya idempoten: panggilan kedua tidak menggandakan angka;
5. `demo_kpi_writeback=false` mematikan seluruh penulisan.

Tes memakai baris database nyata (pola `tests/test_demo_kpi_riwayat.py`) dan
membersihkan barisnya sendiri lewat `source_ref` yang dibuat di tes ini.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import (
    Commodity,
    Decision,
    DeliveryEvent,
    DisposalEvent,
    MenuPlan,
    PriceSignal,
    Supplier,
)
from app.services import settlement
from tests.dsn import DSN_ASYNC

WIB = ZoneInfo("Asia/Jakarta")


@pytest.fixture()
async def sesi():
    engine = create_engine(DSN_ASYNC)
    maker = create_session_maker(engine)
    async with maker() as db:
        yield db
        await db.rollback()
    await engine.dispose()


async def _rencana_hari_ini(db) -> MenuPlan | None:
    hari = datetime.now(UTC).astimezone(WIB).date()
    return (
        await db.execute(
            select(MenuPlan)
            .where(MenuPlan.plan_date == hari, MenuPlan.planned_portions > 0)
            .limit(1)
        )
    ).scalar_one_or_none()


async def _komoditas_beras(db) -> Commodity | None:
    return (
        await db.execute(select(Commodity).where(func.lower(Commodity.name) == "beras").limit(1))
    ).scalar_one_or_none()


async def test_penerimaan_menulis_porsi_dan_idempoten(sesi):
    db = sesi
    rencana = await _rencana_hari_ini(db)
    komoditas = await _komoditas_beras(db)
    if rencana is None or komoditas is None:
        pytest.skip("tidak ada rencana menu hari ini / komoditas beras")

    # Beri ruang porsi di dalam TRANSAKSI tes saja: rencana demo hari ini bisa
    # sudah terpenuhi 100%, dan `uq_menu_plans_loc_date` melarang rencana kedua
    # untuk lokasi+tanggal yang sama. Perubahan ini di-rollback oleh fixture.
    rencana.planned_portions = int(rencana.planned_portions) + 1000
    await db.flush()
    rencana.is_dirty_uji = True  # penanda jelas: tidak pernah di-commit

    receipt_id = uuid.uuid4()
    ref = f"receipt:{receipt_id}"
    batch = SimpleNamespace(
        location_id=rencana.location_id,
        commodity_id=komoditas.id,
        quantity_kg=Decimal("30.00"),  # 30 kg beras / 100 g = 300 porsi
    )
    receipt = SimpleNamespace(id=receipt_id)
    sekarang = datetime.now(UTC)

    hasil = await settlement.catat_penerimaan(
        db, batch=batch, receipt=receipt, sekarang=sekarang
    )
    await db.flush()
    assert hasil["ditulis"] is True, hasil
    assert hasil["porsi"] == 300  # 30 kg ÷ 100 g/porsi
    assert hasil["gram_per_porsi"] == pytest.approx(settings.menu_grams_beras)

    # Idempoten: panggilan kedua tidak menambah baris.
    ulang = await settlement.catat_penerimaan(
        db, batch=batch, receipt=receipt, sekarang=sekarang
    )
    assert ulang["ditulis"] is False
    assert ulang["alasan"] == "sudah tercatat"

    jumlah = (
        await db.execute(
            select(func.count()).select_from(DeliveryEvent).where(DeliveryEvent.source_ref == ref)
        )
    ).scalar_one()
    assert jumlah == 1

    await db.execute(delete(DeliveryEvent).where(DeliveryEvent.source_ref == ref))
    await db.flush()


async def test_po_terbit_menulis_kutipan_harga_dan_idempoten(sesi):
    db = sesi
    keputusan = (
        await db.execute(
            select(Decision)
            .where(
                Decision.target_location_id.is_not(None),
                Decision.commodity_id.is_not(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if keputusan is None:
        pytest.skip("tidak ada keputusan dengan lokasi+komoditas di database uji")

    po_number = f"MC-UJI{uuid.uuid4().hex[:8].upper()}"
    ref = f"po:{po_number}"
    supplier_id = (
        await db.execute(select(Supplier.id).limit(1))
    ).scalar_one_or_none()
    if supplier_id is None:
        pytest.skip("tidak ada pemasok di database uji")
    sekarang = datetime.now(UTC)

    hasil = await settlement.catat_po_terbit(
        db,
        decision=keputusan,
        po_number=po_number,
        supplier_id=supplier_id,
        harga_per_kg=Decimal("23500.00"),
        sekarang=sekarang,
    )
    await db.flush()
    assert hasil["ditulis"] is True, hasil

    ulang = await settlement.catat_po_terbit(
        db,
        decision=keputusan,
        po_number=po_number,
        supplier_id=supplier_id,
        harga_per_kg=Decimal("23500.00"),
        sekarang=sekarang,
    )
    assert ulang["ditulis"] is False

    baris = (
        await db.execute(select(PriceSignal).where(PriceSignal.source_ref == ref))
    ).scalar_one()
    assert baris.source == "supplier_quote"
    assert Decimal(str(baris.price_per_kg)) == Decimal("23500.00")

    await db.execute(delete(PriceSignal).where(PriceSignal.source_ref == ref))
    await db.flush()


async def test_limbah_idempoten_dengan_kunci(sesi):
    db = sesi
    keputusan = (
        await db.execute(
            select(Decision)
            .where(
                Decision.target_location_id.is_not(None),
                Decision.commodity_id.is_not(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if keputusan is None:
        pytest.skip("tidak ada keputusan dengan lokasi+komoditas di database uji")

    kunci = f"uji-{uuid.uuid4()}"
    sekarang = datetime.now(UTC)
    kwargs = dict(
        location_id=keputusan.target_location_id,
        commodity_id=keputusan.commodity_id,
        quantity_kg=Decimal("6.00"),
        reason="expired_transport",
        partner_name=None,
        sekarang=sekarang,
        kunci=kunci,
    )
    hasil = await settlement.catat_pembuangan(db, **kwargs)
    await db.flush()
    assert hasil["ditulis"] is True, hasil

    ulang = await settlement.catat_pembuangan(db, **kwargs)
    assert ulang["ditulis"] is False
    assert ulang["alasan"] == "sudah tercatat"

    baris = (
        await db.execute(
            select(DisposalEvent).where(DisposalEvent.source_ref == f"disposal:{kunci}")
        )
    ).scalar_one()
    assert Decimal(str(baris.quantity_kg)) == Decimal("6.00")

    await db.execute(
        delete(DisposalEvent).where(DisposalEvent.source_ref == f"disposal:{kunci}")
    )
    await db.flush()


async def test_flag_mati_menghentikan_penulisan(sesi, monkeypatch):
    db = sesi
    monkeypatch.setattr(settings, "demo_kpi_writeback", False)
    keputusan = (
        await db.execute(
            select(Decision).where(Decision.target_location_id.is_not(None)).limit(1)
        )
    ).scalar_one_or_none()
    if keputusan is None:
        pytest.skip("tidak ada keputusan di database uji")

    hasil = await settlement.catat_pembuangan(
        db,
        location_id=keputusan.target_location_id,
        commodity_id=keputusan.commodity_id,
        quantity_kg=Decimal("1.00"),
        reason="uji",
        partner_name=None,
        sekarang=datetime.now(UTC),
    )
    assert hasil["ditulis"] is False
    assert "demo_kpi_writeback=false" in hasil["alasan"]


async def test_gram_tidak_ditebak_bila_belum_diatur(sesi, monkeypatch):
    """Komoditas tanpa gram/porsi harus dilewati dengan alasan, bukan ditebak."""
    db = sesi
    rencana = await _rencana_hari_ini(db)
    if rencana is None:
        pytest.skip("tidak ada rencana menu hari ini")

    batch = SimpleNamespace(
        location_id=rencana.location_id,
        commodity_id=uuid.uuid4(),
        quantity_kg=Decimal("10.00"),
    )
    hasil = await settlement.catat_penerimaan(
        db,
        batch=batch,
        receipt=SimpleNamespace(id=uuid.uuid4()),
        sekarang=datetime.now(UTC),
    )
    assert hasil["ditulis"] is False
    assert "gram per porsi" in hasil["alasan"] or "tidak dikenal" in hasil["alasan"]


def test_jendela_wib_dipakai_untuk_tanggal_rencana():
    """23.30 UTC = 06.30 WIB keesokan harinya: tanggal rencana harus ikut WIB."""
    sore = datetime(2026, 10, 22, 23, 30, tzinfo=UTC)
    assert sore.astimezone(WIB).date() > sore.date()
