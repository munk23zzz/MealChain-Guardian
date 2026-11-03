"""Meal Continuity hanya menilai rencana yang JENDELA KIRIMNYA sudah lewat.

Latar (26 Okt 2026): pagi hari, rencana menu hari ini sudah ada tetapi kiriman
hari ini belum terjadi (generator hanya menulis kiriman hari ini setelah 21.00
WIB — `app/seed/timeseries.py:kiriman_sudah_terjadi`). Dengan penyebut lama,
metrik terbaca `available 0,00%` (1 sampel) sepanjang pagi — angka yang
mengklaim "tidak ada porsi terkirim" padahal kirimannya memang belum berjalan.
Aturan proyek: nilai yang belum diketahui ditulis "—", tidak pernah diganti 0.

Kontrak yang dikunci di sini:
1. sebelum 21.00 WIB, rencana hari ini TIDAK masuk penyebut;
2. sesudah 21.00 WIB (instan `end` sudah melewati jendela kirim), rencana hari
   ini masuk penyebut seperti biasa;
3. bila satu-satunya rencana di jendela adalah rencana hari ini yang belum
   berjalan, metrik `no_data` dengan alasan yang menyebut jendela kirim.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.services.kpi_service import compute_kpis
from tests.dsn import DSN_SYNC

WIB = timedelta(hours=7)

#: Lokasi uji terpisah supaya angka Jakarta yang asli tidak tersentuh.
LOKASI_UJI = uuid.uuid4()


def _hari_ini_wib() -> date:
    return (datetime.now(UTC) + WIB).date()


def _instan(hari: date, jam_utc: int) -> datetime:
    return datetime.combine(hari, time(jam_utc, 0), tzinfo=UTC)


def _tanam() -> dict:
    """Dua rencana: kemarin (sudah dikirim) + hari ini (belum berjalan)."""
    kemarin = _hari_ini_wib() - timedelta(days=1)
    hari_ini = _hari_ini_wib()
    ids = {
        "lokasi": LOKASI_UJI,
        "kemarin": uuid.uuid4(),
        "hari_ini": uuid.uuid4(),
        "kirim": uuid.uuid4(),
    }
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO locations (id,name,region,latitude,longitude) "
                    "VALUES (:i,'UJI-JENDELA-KIRIM','Jawa',-6.2,106.8)"
                ),
                {"i": str(LOKASI_UJI)},
            )
            conn.execute(
                text(
                    "INSERT INTO menu_plans (id,location_id,plan_date,planned_portions) "
                    "VALUES (:a,:l,:d,500), (:b,:l,:d2,1000)"
                ),
                {
                    "a": str(ids["kemarin"]),
                    "b": str(ids["hari_ini"]),
                    "l": str(LOKASI_UJI),
                    "d": kemarin,
                    "d2": hari_ini,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO delivery_events "
                    "(id,menu_plan_id,delivered_portions,status,delivered_at) "
                    "VALUES (:i,:m,450,'delivered',:at)"
                ),
                {
                    "i": str(ids["kirim"]),
                    "m": str(ids["kemarin"]),
                    "at": _instan(kemarin, 14),
                },
            )
    finally:
        engine.dispose()
    return ids


def _hapus(ids: dict) -> None:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM delivery_events WHERE id = :i"), {"i": str(ids["kirim"])}
            )
            conn.execute(
                text("DELETE FROM menu_plans WHERE location_id = :l"),
                {"l": str(LOKASI_UJI)},
            )
            conn.execute(text("DELETE FROM locations WHERE id = :l"), {"l": str(LOKASI_UJI)})
    finally:
        engine.dispose()


def _kpi(end: datetime) -> dict:
    async def _isi() -> dict:
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                hasil = await compute_kpis(
                    session, end - timedelta(days=3), end, LOKASI_UJI
                )
                return next(
                    m for m in hasil if m["name"] == "Meal Continuity Rate"
                )
        finally:
            await engine.dispose()

    return asyncio.run(_isi())


@pytest.fixture()
def rencana() -> Iterator[dict]:
    ids = _tanam()
    try:
        yield ids
    finally:
        _hapus(ids)


def test_pagi_hari_rencana_hari_ini_belum_masuk_penyebut(rencana: dict) -> None:
    """end = 09.00 WIB hari ini → hanya rencana kemarin yang dinilai."""
    hari_ini = _hari_ini_wib()
    metrik = _kpi(_instan(hari_ini, 2))  # 02:00 UTC = 09:00 WIB
    assert metrik["state"] == "available", metrik
    # 450 dari 500 — bukan 450 dari 1500.
    assert Decimal(metrik["value"]) == Decimal("90.00")
    assert metrik["sample_count"] == 1


def test_sesudah_jam_kirim_hari_ini_ikut_dinilai(rencana: dict) -> None:
    """end = 22.00 WIB hari ini → rencana hari ini masuk penyebut (belum dikirim)."""
    hari_ini = _hari_ini_wib()
    metrik = _kpi(_instan(hari_ini, 15))  # 15:00 UTC = 22:00 WIB
    assert metrik["state"] == "available", metrik
    # 450 dari 1500 (500 kemarin + 1000 hari ini yang belum dikirim).
    assert Decimal(metrik["value"]) == Decimal("30.00")
    assert metrik["sample_count"] == 2


def test_hanya_rencana_hari_ini_yang_belum_berjalan_jadi_no_data(rencana: dict) -> None:
    """Tanpa rencana kemarin, metrik tidak boleh mengaku 0,00%."""
    hari_ini = _hari_ini_wib()
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM menu_plans WHERE id = :i"), {"i": str(rencana["kemarin"])}
            )
    finally:
        engine.dispose()
    metrik = _kpi(_instan(hari_ini, 2))
    assert metrik["state"] == "no_data", metrik
    assert "jendela kirim" in (metrik["reason"] or "").lower(), metrik["reason"]
    assert metrik["value"] is None
