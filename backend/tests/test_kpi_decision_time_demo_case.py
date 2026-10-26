"""Decision Time HARUS menghitung keputusan demo (`demo_case` terisi).

Latar (26 Okt 2026): `compute_kpis` menyaring `d.demo_case IS NULL` pada metrik
Decision Time. Filter itu tidak tercatat di kamus KPI, dan akibatnya metrik ini
mustahil bergerak saat operator menjalankan kartu demo di panggung — trace
DETECT/ACT dan PO-nya nyata, tetapi selalu dibuang dari sampel.

Kontrak sekarang:
1. keputusan ber-`demo_case` ikut dihitung (DETECT → ACT, ACT committed);
2. keputusan yang belum punya PO committed tetap jadi `eligible`, bukan sampel
   (coverage < 1) — rata-rata tidak boleh diisi aksi yang belum tuntas.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.services.kpi_service import compute_kpis
from tests.dsn import DSN_SYNC

LOKASI = uuid.uuid4()
SEKARANG = datetime.now(UTC).replace(microsecond=0)


def _eksekusi(stmt: str, params: dict | None = None):
    eng = create_engine(DSN_SYNC)
    try:
        with eng.begin() as conn:
            hasil = conn.execute(text(stmt), params or {})
            return hasil.fetchall() if hasil.returns_rows else []
    finally:
        eng.dispose()


@pytest.fixture()
def keputusan_demo():
    supplier = _eksekusi("SELECT id FROM suppliers LIMIT 1")[0][0]
    komoditas = _eksekusi("SELECT id FROM commodities LIMIT 1")[0][0]
    # Idempoten: sisa run yang gagal di tengah bisa meninggalkan baris uji.
    _eksekusi("DELETE FROM locations WHERE name LIKE 'UJI-DECISION-TIME%'")
    _eksekusi(
        "INSERT INTO locations (id,name,region,latitude,longitude) "
        "VALUES (:i,'UJI-DECISION-TIME','Jawa',-6.2,106.8)",
        {"i": str(LOKASI)},
    )
    demo_id = uuid.uuid4()
    _eksekusi(
        "INSERT INTO decisions (id,decision_type,status,proposed_by,expires_at,"
        "created_at,iteration,origin,generated_at,target_location_id,commodity_id,"
        "demo_case) VALUES (:i,'safety_disruption','executed','uji',:exp,:crt,1,"
        "'demo',:crt,:loc,:kom,'uji-decision-time')",
        {
            "i": str(demo_id),
            "exp": SEKARANG + timedelta(hours=2),
            "crt": SEKARANG - timedelta(minutes=60),
            "loc": str(LOKASI),
            "kom": str(komoditas),
        },
    )
    _eksekusi(
        "INSERT INTO agent_traces (id,decision_id,step_name,step_at) VALUES "
        "(:a,:d,'DETECT',:t1), (:b,:d,'ACT',:t2)",
        {
            "a": str(uuid.uuid4()),
            "b": str(uuid.uuid4()),
            "d": str(demo_id),
            "t1": SEKARANG - timedelta(minutes=40),
            "t2": SEKARANG - timedelta(minutes=10),
        },
    )
    _eksekusi(
        "INSERT INTO sap_mock_purchase_orders (po_number,supplier_id,material_number,"
        "ordered_quantity,price,decision_id,status,created_at,origin) VALUES "
        "(:po,:s,'M-1',10,1000,:d,'confirmed',:crt,'demo')",
        {
            "po": f"UJI-{uuid.uuid4().hex[:10]}",
            "s": str(supplier),
            "d": str(demo_id),
            "crt": SEKARANG - timedelta(minutes=5),
        },
    )
    try:
        yield {"decision": str(demo_id), "supplier": str(supplier)}
    finally:
        _eksekusi(
            "DELETE FROM sap_mock_purchase_orders WHERE decision_id = :d",
            {"d": str(demo_id)},
        )
        _eksekusi("DELETE FROM agent_traces WHERE decision_id = :d", {"d": str(demo_id)})
        _eksekusi("DELETE FROM decisions WHERE id = :d", {"d": str(demo_id)})
        _eksekusi("DELETE FROM locations WHERE id = :i", {"i": str(LOKASI)})


def _decision_time() -> dict:
    async def _isi() -> dict:
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                metrics = await compute_kpis(
                    session,
                    SEKARANG - timedelta(hours=2),
                    SEKARANG,
                    LOKASI,
                )
                return next(m for m in metrics if m["name"] == "Decision Time")
        finally:
            await engine.dispose()

    return asyncio.run(_isi())


def test_decision_time_menghitung_keputusan_demo(keputusan_demo) -> None:
    metrik = _decision_time()
    assert metrik["state"] == "available", metrik
    # DETECT 40 menit lalu → ACT 10 menit lalu = 30 menit.
    assert Decimal(metrik["value"]) == Decimal("30.00")
    assert metrik["sample_count"] == 1
    assert Decimal(metrik["coverage"]) == Decimal("1.00")
