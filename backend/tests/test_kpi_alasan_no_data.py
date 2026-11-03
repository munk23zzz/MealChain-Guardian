"""KPI-02 (audit 24 Okt 2026): `no_data` harus menyebut SEBABNYA.

Dulu semua keadaan kosong jatuh ke satu kalimat umum ("tidak ada record pada
periode ini"), sehingga UI tidak bisa membedakan:

- **belum ada data** — memang tidak ada baris pada periode itu, dan
- **penyebut nol** — barisnya ada, tetapi totalnya 0 (mis. rencana tanpa porsi,
  atau kutipan pemasok tanpa pembanding harga).

Dua keadaan itu butuh tindakan berbeda saat demo: yang pertama menunggu data
masuk, yang kedua menandakan data yang salah bentuk. Tes ini mengunci bahwa
alasan setiap metrik menyebut sebabnya, dan bahwa cabang "penyebut nol" benar-
benar terpakai saat datanya ada tetapi bernilai nol.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.kpi_service import METRIC_NAMES, compute_kpis
from tests.dsn import DSN_ASYNC, DSN_SYNC

# Jendela yang dijamin kosong: jauh sebelum data demo dibuat.
KOSONG_AWAL = datetime(2019, 3, 1, tzinfo=timezone.utc)
KOSONG_AKHIR = datetime(2019, 3, 2, tzinfo=timezone.utc)


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


def _kpi(start: datetime, end: datetime) -> dict[str, dict]:
    async def _t(db):
        hasil = await compute_kpis(db, start, end, None)
        return {m["name"]: m for m in hasil}

    return _jalankan(_t)


def test_jendela_kosong_menyebut_sebab_per_metrik():
    metrik = _kpi(KOSONG_AWAL, KOSONG_AKHIR)
    assert list(metrik) == list(METRIC_NAMES)

    for nama, m in metrik.items():
        assert m["state"] == "no_data", f"{nama}: {m}"
        assert m["value"] is None, f"{nama} tidak boleh mengarang angka"
        assert m["reason"], f"{nama} wajib menyebut sebab"
        # Bukan kalimat generik yang sama untuk semua metrik.
        assert "tidak ada" in m["reason"].lower(), (nama, m["reason"])

    assert "menu plan" in metrik["Meal Continuity Rate"]["reason"]
    assert "DETECT" in metrik["Decision Time"]["reason"]
    assert "keputusan" in metrik["Evidence Completeness"]["reason"]
    assert "supplier_quote" in metrik["Procurement Price Deviation"]["reason"]


def test_rencana_tanpa_porsi_disebut_penyebut_nol():
    """Baris ada, totalnya 0 → alasan harus membedakan dari 'tidak ada data'."""
    eng = create_engine(DSN_SYNC)
    lokasi = None
    try:
        with eng.begin() as conn:
            lokasi = conn.execute(text("SELECT id FROM locations LIMIT 1")).scalar()
            assert lokasi is not None, "butuh minimal satu lokasi di DB"
            conn.execute(
                text(
                    "INSERT INTO menu_plans (location_id, plan_date, planned_portions, origin) "
                    "VALUES (:l, DATE '2019-03-01', 0, 'demo')"
                ),
                {"l": lokasi},
            )

        metrik = _kpi(KOSONG_AWAL, KOSONG_AKHIR)
        mc = metrik["Meal Continuity Rate"]
        assert mc["state"] == "no_data"
        assert "penyebut nol" in mc["reason"], mc["reason"]
        assert mc["sample_count"] == 1
    finally:
        with eng.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM menu_plans WHERE plan_date = DATE '2019-03-01' "
                    "AND planned_portions = 0"
                )
            )
        eng.dispose()


def test_tidak_ada_data_dan_penyebut_nol_tidak_sama_kalimatnya():
    kosong = _kpi(KOSONG_AWAL, KOSONG_AKHIR)["Meal Continuity Rate"]["reason"]

    eng = create_engine(DSN_SYNC)
    try:
        with eng.begin() as conn:
            lokasi = conn.execute(text("SELECT id FROM locations LIMIT 1")).scalar()
            conn.execute(
                text(
                    "INSERT INTO menu_plans (location_id, plan_date, planned_portions, origin) "
                    "VALUES (:l, DATE '2019-03-01', 0, 'demo')"
                ),
                {"l": lokasi},
            )
        nol = _kpi(KOSONG_AWAL, KOSONG_AKHIR)["Meal Continuity Rate"]["reason"]
    finally:
        with eng.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM menu_plans WHERE plan_date = DATE '2019-03-01' "
                    "AND planned_portions = 0"
                )
            )
        eng.dispose()

    assert kosong != nol
    assert "tidak ada menu plan" in kosong
    assert "penyebut nol" in nol
