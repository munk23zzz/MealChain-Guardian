"""S4-01 bagian 2 — service + API /events/price-anomaly (RED dulu)."""

import uuid

import pytest
from sqlalchemy import create_engine, text

from app.core.price import price_deviation

DB_URL = (
    "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
).replace("+asyncpg", "+psycopg")


def _db_one(query: str, params: dict | None = None):
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(text(query), params or {}).fetchone()
            conn.commit()
            return row
    finally:
        engine.dispose()


def _seed_pair(deviation_factor: str) -> tuple[str, str, str, dict]:
    """Buat pasangan quote+reference (lokasi test terisolasi) → (quote_id,
    reference_id, target_location_id, handles utk cleanup).

    REVISI S4-05 (2026-10-08): versi lama TIDAK membersihkan residu
    (locations/commodities/suppliers/price_signals tertinggal) dan
    mempolusi test kontrak dataset lain pada full suite (orphan check,
    row counts). Fixture `event2_pair` membersihkan FK-safe di teardown.
    """
    engine = create_engine(DB_URL)
    op_key = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            loc_id = conn.execute(
                text(
                    "INSERT INTO locations (name, region, latitude, longitude) "
                    "VALUES (:n, 'test-region', 0, 0) RETURNING id"
                ),
                {"n": f"EV2-{op_key[:8]}"},
            ).scalar_one()
            com_id = conn.execute(
                text(
                    "INSERT INTO commodities (name) VALUES (:n) RETURNING id"
                ),
                {"n": f"komoditas-{op_key[:8]}"},
            ).scalar_one()
            sup_id = conn.execute(
                text(
                    "INSERT INTO suppliers (name, location_id, reliability_score) "
                    "VALUES (:n, :l, 0.8) RETURNING id"
                ),
                {"n": f"supplier-{op_key[:8]}", "l": str(loc_id)},
            ).scalar_one()
            ref_price = "20000"
            quote_price = str(round(20000 * float(deviation_factor)))
            ref_id = conn.execute(
                text(
                    "INSERT INTO price_signals (location_id, commodity_id, "
                    "price_per_kg, supplier_id, recorded_at, source) "
                    "VALUES (:l, :c, :p, NULL, now(), 'pihps_reference') "
                    "RETURNING id"
                ),
                {"l": str(loc_id), "c": str(com_id), "p": ref_price},
            ).scalar_one()
            quote_id = conn.execute(
                text(
                    "INSERT INTO price_signals (location_id, commodity_id, "
                    "price_per_kg, supplier_id, recorded_at, source) "
                    "VALUES (:l, :c, :p, :s, now(), 'supplier_quote') "
                    "RETURNING id"
                ),
                {
                    "l": str(loc_id),
                    "c": str(com_id),
                    "p": quote_price,
                    "s": str(sup_id),
                },
            ).scalar_one()
    finally:
        engine.dispose()
    handles = {
        "op_key": op_key,
        "loc_name": f"EV2-{op_key[:8]}",
        "com_name": f"komoditas-{op_key[:8]}",
        "sup_name": f"supplier-{op_key[:8]}",
    }
    return str(quote_id), str(ref_id), str(loc_id), handles


def _cleanup_pair(handles: dict) -> None:
    """Hapus seluruh residu pasangan seed — FK-safe, urutan FK.

    agent_traces → decision_evidence → approvals → sap_mock_purchase_orders
    → decisions → price_signals → suppliers → locations → commodities
    (semua dikunci pada nama unik op_key).
    """
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            ln, cn = handles["loc_name"], handles["com_name"]
            conn.execute(text(
                "DELETE FROM agent_traces t USING decisions d, "
                "commodities c WHERE t.decision_id=d.id "
                "AND d.commodity_id=c.id AND c.name=:cn"
            ), {"cn": cn})
            conn.execute(text(
                "DELETE FROM decision_evidence de USING decisions d, "
                "commodities c WHERE de.decision_id=d.id "
                "AND d.commodity_id=c.id AND c.name=:cn"
            ), {"cn": cn})
            conn.execute(text(
                "DELETE FROM approvals a USING decisions d, "
                "commodities c WHERE a.decision_id=d.id "
                "AND d.commodity_id=c.id AND c.name=:cn"
            ), {"cn": cn})
            conn.execute(text(
                "DELETE FROM sap_mock_purchase_orders po USING "
                "decisions d, commodities c WHERE po.decision_id=d.id "
                "AND d.commodity_id=c.id AND c.name=:cn"
            ), {"cn": cn})
            conn.execute(text(
                "DELETE FROM decisions d USING commodities c "
                "WHERE d.commodity_id=c.id AND c.name=:cn"
            ), {"cn": cn})
            conn.execute(text(
                "DELETE FROM price_signals ps USING locations l, "
                "commodities c WHERE ps.location_id=l.id "
                "AND ps.commodity_id=c.id "
                "AND (l.name=:ln OR c.name=:cn)"
            ), {"ln": ln, "cn": cn})
            conn.execute(text(
                "DELETE FROM suppliers s USING locations l "
                "WHERE s.location_id=l.id AND l.name=:ln"
            ), {"ln": ln})
            conn.execute(text(
                "DELETE FROM locations WHERE name=:ln"
            ), {"ln": ln})
            conn.execute(text(
                "DELETE FROM commodities WHERE name=:cn"
            ), {"cn": cn})
    finally:
        engine.dispose()


def mk_pair(request, deviation_factor: str):
    """Seed + auto-cleanup via finalizer (deviation fleksibel per test).

    REVISI S4-05 (2026-10-08): file ini dulu seed TANPA cleanup —
    residu locations/commodities/suppliers/price_signals mempolusi test
    kontrak dataset lain pada full suite. dipakai test_event2_api.
    """
    quote_id, ref_id, loc_id, handles = _seed_pair(deviation_factor)
    request.addfinalizer(lambda: _cleanup_pair(handles))
    return quote_id, ref_id, loc_id


@pytest.fixture()
def event2_pair():
    """Seed pasangan quote+reference; teardown hapus seluruh residu FK-safe."""
    quote_id, ref_id, loc_id, handles = _seed_pair("1.2")
    try:
        yield quote_id, ref_id, loc_id, handles
    finally:
        _cleanup_pair(handles)


def test_price_deviation_thresholds_kontrak_terkunci():
    """5%/15% ambang — reuse engine Sprint 1 tanpa perubahan."""
    res_anom = price_deviation("24000", "20000")  # +20%
    assert res_anom["status"] == "anomalous" and res_anom["flagged"] is True
    res_elev = price_deviation("21000", "20000")  # +5%
    assert res_elev["status"] == "elevated" and res_elev["flagged"] is False
    res_norm = price_deviation("20500", "20000")  # +2.5%
    assert res_norm["status"] == "normal"


def test_service_persist_price_anomaly_decision(event2_pair):
    """Service menyimpan decision price_anomaly + evidence + trace (TANPA PO).

    Fixture `event2_pair` seed +20% (anomalous) dan membersihkan seluruh
    residu di teardown — file ini dulu polusi DB lintas-test (REVISI S4-05).
    """
    import asyncio

    from app.core.config import settings
    from app.db import create_engine as make_engine
    from app.db import create_session_maker
    from app.services import event2_service as svc

    quote_id, ref_id, loc_id, _handles = event2_pair
    op_key = uuid.uuid4()

    async def _run():
        engine = make_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            return await svc.run_price_anomaly_event(
                quote_id=uuid.UUID(quote_id),
                target_location_id=uuid.UUID(loc_id),
                operation_key=op_key,
                actor_id=None,
                db=session,
            )

    outcome = asyncio.run(_run())
    assert outcome["status"] == "anomaly"
    assert outcome["decision_id"] is not None
    dev = outcome["deviation_pct"]
    assert abs(float(dev) - 20.0) < 0.05

    # Readback DB: decision + evidence + trace, dan TIDAK ada PO.
    row = _db_one(
        "SELECT decision_type, status FROM decisions WHERE id = :d",
        {"d": outcome["decision_id"]},
    )
    assert row is not None
    assert row[0] == "price_anomaly"
    ev = _db_one(
        "SELECT count(*) FROM decision_evidence WHERE decision_id = :d",
        {"d": outcome["decision_id"]},
    )
    assert ev[0] >= 1
    tr = _db_one(
        "SELECT count(*) FROM agent_traces WHERE decision_id = :d",
        {"d": outcome["decision_id"]},
    )
    assert tr[0] >= 1
    # Wording review, bukan tuduhan fraud.
    assert "review" in outcome["message"].lower()
    assert "fraud" not in outcome["message"].lower()
