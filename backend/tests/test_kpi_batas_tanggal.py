"""KPI Meal Continuity — batas tanggal & sumbu waktu (audit 2026-10-23, KPI-01).

Dua cacat yang dikunci di sini:

1. Predikat ``plan_date < CAST(:end AS date)`` membuat rencana **hari ini** tidak
   pernah masuk jendela (``end`` = sekarang, jadi ``end::date`` = hari ini).
   Akibat nyata: KPI 24 jam Meal Continuity 0,00% walau kiriman hari ini ada.
2. Pembilang memakai ``delivered_at`` di dalam jendela sementara penyebut memakai
   ``plan_date``. Rencana kemarin ikut penyebut, kirimannya (kemarin) sudah keluar
   jendela 24 jam → rasio terstruktur mentok ~50%, bukan 100%.

Kontrak yang diinginkan: continuity = porsi terkirim **untuk rencana yang tanggalnya
di dalam jendela** ÷ porsi rencana pada jendela itu. Kedua sisi memakai sumbu
``plan_date``; ``delivered_at`` hanya identitas baris, bukan filter.

RED dulu: kedua tes ini gagal pada implementasi sebelum perbaikan.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.services.kpi_service import compute_kpis
from tests.dsn import DSN_ASYNC, DSN_SYNC

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
HARI_INI = NOW.date()
KEMARIN = (NOW - timedelta(days=1)).date()


def _db_exec(stmt, params=None):
    eng = create_engine(DSN_SYNC)
    with eng.begin() as conn:
        res = conn.execute(text(stmt), params or {})
        try:
            return res.fetchall()
        except Exception:
            return []


def _run(fn):
    return asyncio.run(_with_session(fn))


async def _with_session(fn):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    eng = create_async_engine(DSN_ASYNC)
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            return await fn(session)
    finally:
        await eng.dispose()


def _plan(loc, plan_date, planned, created_at):
    return str(_db_exec(
        "INSERT INTO menu_plans (location_id, plan_date, planned_portions, created_at) "
        "VALUES (:l, :d, :p, :t) RETURNING id",
        {"l": loc, "d": plan_date, "p": planned, "t": created_at},
    )[0][0])


def _kirim(menu_plan_id, porsi, delivered_at):
    return str(_db_exec(
        "INSERT INTO delivery_events (menu_plan_id, delivered_portions, status, delivered_at) "
        "VALUES (:m, :q, 'delivered', :t) RETURNING id",
        {"m": menu_plan_id, "q": porsi, "t": delivered_at},
    )[0][0])


def _bersihkan(loc):
    _db_exec(
        "DELETE FROM delivery_events WHERE menu_plan_id IN "
        "(SELECT id FROM menu_plans WHERE location_id=:l)", {"l": loc})
    _db_exec("DELETE FROM menu_plans WHERE location_id=:l", {"l": loc})


def _kartu(loc, start, end):
    metrics = _run(lambda s: compute_kpis(s, start, end, loc))
    return {m["name"]: m for m in metrics}["Meal Continuity Rate"]


@pytest.fixture
def lokasi():
    """Lokasi uji milik sendiri (bukan lokasi seed) — dibersihkan sesudah tes."""
    nama = f"EVK-batas-{uuid.uuid4().hex[:8]}"
    loc = str(_db_exec(
        "INSERT INTO locations (name, region, latitude, longitude) "
        "VALUES (:n, 'test', -6.9, 107.6) RETURNING id", {"n": nama})[0][0])
    yield loc
    _bersihkan(loc)
    _db_exec("DELETE FROM locations WHERE id=:l", {"l": loc})


def test_rencana_hari_ini_masuk_jendela_24_jam(lokasi):
    """Rencana bertanggal hari ini + kiriman hari ini harus dihitung, bukan no_data."""
    mp = _plan(lokasi, HARI_INI, 100, NOW - timedelta(hours=6))
    _kirim(mp, 100, NOW - timedelta(hours=1))
    try:
        m = _kartu(lokasi, NOW - timedelta(hours=24), NOW)
        assert m["state"] == "available", (
            f"rencana hari ini tidak masuk jendela 24 jam (state={m['state']}) — "
            "predikat plan_date memakai '<' bukan '<='")
        assert Decimal(m["value"]) == Decimal("100.00")
        assert m["sample_count"] == 1
    finally:
        _bersihkan(lokasi)


def test_kiriman_kemarin_di_luar_jendela_tetap_menghitung_rencana_kemarin(lokasi):
    """Sumbu waktu pembilang & penyebut harus sama (plan_date), bukan delivered_at.

    Rencana kemarin 100 porsi, kirimannya kemarin 08.00 UTC (28 jam sebelum NOW →
    di luar jendela 24 jam). Rencana hari ini 100 porsi, kiriman hari ini.
    Kontrak: 200/200 = 100,00%. Implementasi lama: 100/200 = 50,00%.
    """
    mp_kemarin = _plan(lokasi, KEMARIN, 100, NOW - timedelta(days=1, hours=4))
    _kirim(mp_kemarin, 100, NOW - timedelta(hours=28))
    mp_hari_ini = _plan(lokasi, HARI_INI, 100, NOW - timedelta(hours=6))
    _kirim(mp_hari_ini, 100, NOW - timedelta(hours=1))
    try:
        m = _kartu(lokasi, NOW - timedelta(hours=24), NOW)
        assert m["state"] == "available"
        assert Decimal(m["value"]) == Decimal("100.00"), (
            f"nilai {m['value']} — pembilang masih difilter delivered_at "
            "(rasio mentok ~50% untuk jendela bergulir)")
        assert m["sample_count"] == 2
    finally:
        _bersihkan(lokasi)


def test_kiriman_berlebih_tetap_dibatasi_100_persen(lokasi):
    """Over-delivery tidak boleh membuat continuity > 100% (dibatasi per plan-day)."""
    mp = _plan(lokasi, HARI_INI, 100, NOW - timedelta(hours=6))
    _kirim(mp, 150, NOW - timedelta(hours=1))
    try:
        m = _kartu(lokasi, NOW - timedelta(hours=24), NOW)
        assert Decimal(m["value"]) == Decimal("100.00")
    finally:
        _bersihkan(lokasi)


@pytest.mark.parametrize("hari", [7, 30])
def test_jendela_panjang_tetap_masuk_jendela(lokasi, hari):
    """Jendela 7/30 hari juga tidak boleh membuang hari ini dari penyebut."""
    mp = _plan(lokasi, HARI_INI, 50, NOW - timedelta(hours=6))
    _kirim(mp, 50, NOW - timedelta(hours=1))
    try:
        m = _kartu(lokasi, NOW - timedelta(days=hari), NOW)
        assert m["state"] == "available"
        assert Decimal(m["value"]) == Decimal("100.00")
        assert m["sample_count"] == 1
    finally:
        _bersihkan(lokasi)
