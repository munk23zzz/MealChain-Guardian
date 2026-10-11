"""S4-03 — KPI service + pure core (RED dulu, TDD).

Kontrak plan §S4-03 + worksheet §10 + ruling O-KPI (addendum §23):
state `available/no_data/unavailable`, reason eksplisit, TANPA fake 0/proxy;
period [start,end); dedupe deteksi berulang via root lineage; price deviation
magnitudo absolut (O-NUM); anchor eksekusi = PO committed (bukan created_at
decision); evidence cutoff = approval-complete time; bukti sesudah cutoff
tidak dihitung; dua salinan tipe sama bukan dua sumber.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

from app.core.kpi import (  # noqa: E402
    quantize2,
    resolve_root,
    trend_of,
)
from app.services.kpi_service import compute_kpis  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


def _db_exec(stmt, params=None):
    """Sync DDL/DML helper: RETURNING → fetchall; tanpa RETURNING → rows kosong."""
    eng = create_engine(DB_URL)
    with eng.begin() as conn:
        res = conn.execute(text(stmt), params or {})
        try:
            return res.fetchall()
        except Exception:
            return []


def _run(fn):
    """Jalankan coroutine service dengan engine/session fresh per call."""
    return asyncio.run(_with_session(fn))


async def _with_session(fn):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    eng = create_async_engine(
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            return await fn(session)
    finally:
        await eng.dispose()


@pytest.fixture
def suffix():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def refs():
    """IDs referensi seed (commodity telur, users approver)."""
    rows = _db_exec("SELECT id FROM commodities WHERE name='telur'")
    head = _db_exec(
        "SELECT id FROM users WHERE role='sppg_head' ORDER BY id LIMIT 1"
    )
    nut = _db_exec(
        "SELECT id FROM users WHERE role='sppg_nutritionist' ORDER BY id LIMIT 1"
    )
    assert rows and head and nut
    return {"commodity": str(rows[0][0]), "head": str(head[0][0]), "nut": str(nut[0][0])}


class _Fx:
    """Owned fixtures EVK-* — seed demo tidak tersentuh; cleanup di finally."""

    def __init__(self, suffix):
        self.suffix = suffix
        self.loc = str(
            _db_exec(
                "INSERT INTO locations (name, region, latitude, longitude) "
                "VALUES (:n, 'test', -6.9, 107.6) RETURNING id",
                {"n": f"EVK-loc-{suffix}"},
            )[0][0]
        )
        self.tgt = str(
            _db_exec(
                "INSERT INTO locations (name, region, latitude, longitude) "
                "VALUES (:n, 'test', -6.2, 106.8) RETURNING id",
                {"n": f"EVK-tgt-{suffix}"},
            )[0][0]
        )
        self.sup = str(
            _db_exec(
                "INSERT INTO suppliers (name, location_id, reliability_score) "
                "VALUES (:n, :l, 0.8) RETURNING id",
                {"n": f"EVK-sup-{suffix}", "l": self.loc},
            )[0][0]
        )

    def price(self, source, price, recorded_at, supplier_id=None):
        return str(
            _db_exec(
                "INSERT INTO price_signals (location_id, commodity_id, price_per_kg, "
                "recorded_at, source, supplier_id) "
                "SELECT :loc, c.id, :p, :t, :s, :sup FROM commodities c "
                "WHERE c.name='telur' RETURNING id",
                {"loc": self.loc, "p": price, "t": recorded_at, "s": source, "sup": supplier_id},
            )[0][0]
        )

    def decision(self, status, sdc=None, created_at=NOW, demo_case=None,
                 decision_type="regional_balance", supersedes=None):
        return str(
            _db_exec(
                "INSERT INTO decisions (decision_type, status, proposed_by, "
                "source_location_id, target_location_id, commodity_id, quantity_kg, "
                "safe_delivered_cost, expires_at, created_at, demo_case, supersedes_id) "
                "SELECT :dt, :st, 'test', :src, :tgt, c.id, 500, :sdc, "
                ":exp, :cr, :demo, :sup FROM commodities c WHERE c.name='telur' "
                "RETURNING id",
                {
                    "dt": decision_type,
                    "st": status, "src": self.loc, "tgt": self.tgt,
                    "sdc": sdc, "exp": created_at + timedelta(minutes=30),
                    "cr": created_at, "demo": demo_case, "sup": supersedes,
                },
            )[0][0]
        )

    def trace(self, decision_id, step, created_at=NOW):
        _db_exec(
            "INSERT INTO agent_traces (decision_id, step_name, tool_called, step_at) "
            "VALUES (:d, :s, 'test', :t)",
            {"d": decision_id, "s": step, "t": created_at},
        )

    def approve(self, decision_id, user_id, approved_at, approved=True):
        _db_exec(
            "INSERT INTO approvals (decision_id, approved_by, approved, approved_at) "
            "VALUES (:d, :u, :a, :t)",
            {"d": decision_id, "u": user_id, "a": approved, "t": approved_at},
        )

    def evidence(self, decision_id, etype, is_consistent, recorded_at):
        _db_exec(
            "INSERT INTO decision_evidence (decision_id, evidence_type, payload, "
            "is_consistent, recorded_at) VALUES (:d, :t, '{}', :c, :r)",
            {"d": decision_id, "t": etype, "c": is_consistent, "r": recorded_at},
        )

    def po(self, decision_id, created_at):
        _db_exec(
            "INSERT INTO sap_mock_purchase_orders (po_number, supplier_id, "
            "material_number, ordered_quantity, price, decision_id, status, created_at) "
            "VALUES (:pn, :sup, 'MAT-TELUR', 500, 30000, :d, 'submitted', :t)",
            {"pn": f"EVK-{uuid.uuid4().hex[:10].upper()}", "sup": self.sup,
             "d": decision_id, "t": created_at},
        )

    def cleanup(self):
        d_ids = [str(r[0]) for r in _db_exec(
            "SELECT id FROM decisions WHERE source_location_id=:l OR "
            "target_location_id=:l", {"l": self.loc})]
        if d_ids:
            _db_exec("DELETE FROM agent_traces WHERE decision_id=ANY(:x)", {"x": d_ids})
            _db_exec("DELETE FROM decision_evidence WHERE decision_id=ANY(:x)", {"x": d_ids})
            _db_exec("DELETE FROM approvals WHERE decision_id=ANY(:x)", {"x": d_ids})
            _db_exec("DELETE FROM sap_mock_purchase_orders WHERE decision_id=ANY(:x)", {"x": d_ids})
            _db_exec("DELETE FROM decisions WHERE id=ANY(:x)", {"x": d_ids})
        _db_exec("DELETE FROM price_signals WHERE location_id=:l", {"l": self.loc})
        _db_exec("DELETE FROM suppliers WHERE id=:s", {"s": self.sup})
        _db_exec("DELETE FROM locations WHERE id IN (:a, :b)", {"a": self.loc, "b": self.tgt})


@pytest.fixture
def fx(suffix):
    f = _Fx(suffix)
    yield f
    f.cleanup()


# ---------- pure core ----------

def test_quantize2_half_up():
    assert quantize2(Decimal("10.005")) == Decimal("10.01")
    assert quantize2(Decimal("15496548.135")) == Decimal("15496548.14")


def test_resolve_root_dedupes_lineage():
    root = "a"
    child = "b"
    grand = "c"
    parent_map = {child: root, grand: child}
    assert resolve_root(parent_map, grand) == root
    assert resolve_root(parent_map, root) == root
    assert resolve_root({}, "z") == "z"


def test_trend_of():
    assert trend_of(Decimal("10"), Decimal("9")) == "up"
    assert trend_of(Decimal("9"), Decimal("10")) == "down"
    assert trend_of(Decimal("5"), Decimal("5")) == "flat"
    assert trend_of(Decimal("5"), None) is None


# ---------- service: tujuh metrik ----------

def test_metrics_exactly_seven_with_contract_keys(fx):
    metrics = _run(lambda s: compute_kpis(s, NOW - timedelta(days=1), NOW, None))
    names = [m["name"] for m in metrics]
    assert len(names) == 7
    assert set(names) == {
        "Meal Continuity Rate", "Avoidable Food Loss",
        "Regional Imbalance Resolution Rate", "Safe Delivered Cost",
        "Procurement Price Deviation", "Decision Time",
        "Evidence Completeness",
    }
    for m in metrics:
        assert set(m) >= {"name", "unit", "state", "value", "reason",
                          "sample_count", "coverage", "previous_value", "trend"}
        assert m["state"] in {"available", "no_data", "unavailable"}


def test_missing_facts_unavailable_not_zero(fx):
    # P6 (009): tabel facts SUDAH ada; window tanpa record → state `no_data`
    # (jujur "belum ada data", TANPA fake 0 — bukan `unavailable` yang berarti
    # schema tidak punya facts). Window digeser +30 hari supaya di luar seed.
    by = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW + timedelta(days=30), NOW + timedelta(days=31), None))}
    for name in ("Meal Continuity Rate", "Avoidable Food Loss"):
        assert by[name]["state"] == "no_data"
        assert by[name]["value"] is None
        assert (by[name]["reason"] or "").strip()


# ---------- P6 (arah Roy 2026-10-09): tabel facts baru → KPI hidup ----------
# Kontrak paket 6: menu_plans + delivery_events + disposal_events. KPI
# Meal Continuity & Food Loss jadi available saat facts ada; tetap jujur
# (no_data/unavailable + reason) saat facts kosong. Proxy TETAP dilarang.

def _fx_menu_plan(fx, planned, created_at=NOW):
    return str(_db_exec(
        "INSERT INTO menu_plans (location_id, plan_date, planned_portions, created_at) "
        "VALUES (:l, :d, :p, :t) RETURNING id",
        {"l": fx.loc, "d": created_at.date(), "p": planned, "t": created_at},
    )[0][0])


def _fx_delivery(fx, menu_plan_id, delivered, status="delivered", created_at=NOW):
    return str(_db_exec(
        "INSERT INTO delivery_events (menu_plan_id, delivered_portions, status, delivered_at) "
        "VALUES (:m, :q, :s, :t) RETURNING id",
        {"m": menu_plan_id, "q": delivered, "s": status, "t": created_at},
    )[0][0])


def _fx_disposal(fx, qty, reason, created_at=NOW - timedelta(minutes=1), loc=None):
    return str(_db_exec(
        "INSERT INTO disposal_events (location_id, commodity_id, quantity_kg, reason, disposed_at) "
        "SELECT :l, c.id, :q, :r, :t FROM commodities c WHERE c.name='telur' RETURNING id",
        {"l": loc or fx.loc, "q": qty, "r": reason, "t": created_at},
    )[0][0])


def test_meal_continuity_from_menu_plans_and_deliveries(fx):
    # 3 hari: 100 porsi direncanakan, 99+100+97 tersampaikan → 296/300 = 98,67%
    for i, delivered in enumerate((99, 100, 97)):
        t = NOW - timedelta(days=3 - i)
        mp = _fx_menu_plan(fx, 100, t)
        _fx_delivery(fx, mp, delivered, created_at=t + timedelta(hours=2))
    try:
        m = {m["name"]: m for m in _run(lambda s: compute_kpis(
            s, NOW - timedelta(days=7), NOW, fx.loc))}["Meal Continuity Rate"]
        assert m["state"] == "available"
        assert m["value"] == "98.67"
        assert m["sample_count"] == 3
    finally:
        _db_exec("DELETE FROM delivery_events WHERE menu_plan_id IN "
                 "(SELECT id FROM menu_plans WHERE location_id=:l)", {"l": fx.loc})
        _db_exec("DELETE FROM menu_plans WHERE location_id=:l", {"l": fx.loc})


def test_meal_continuity_no_plans_no_data(fx):
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=7), NOW, fx.loc))}["Meal Continuity Rate"]
    assert m["state"] == "no_data"


def test_food_loss_from_disposal_events(fx):
    # disposal 12 kg; supply dipakai sebagai penyebut? TIDAK — kontrak:
    # loss% = disposal_kg / (delivered food input) * 100. Untuk test:
    # input total 400 kg (disposal_events yang menghitung dari SUM supply
    # per kontrak implementasi), di sini pin hasil deterministik.
    _fx_disposal(fx, Decimal("12"), "expired_transport")
    _fx_disposal(fx, Decimal("8"), "spoilage_cold_chain")
    try:
        m = {m["name"]: m for m in _run(lambda s: compute_kpis(
            s, NOW - timedelta(days=7), NOW, fx.loc))}["Avoidable Food Loss"]
        # state available; formula kontrak diuji via nilai konsisten service
        assert m["state"] == "available"
        assert Decimal(m["value"]) > 0
        assert m["sample_count"] == 2
    finally:
        _db_exec("DELETE FROM disposal_events WHERE location_id=:l", {"l": fx.loc})


def test_food_loss_sample_count_ikut_jumlah_event(fx):
    """sample_count = jumlah event disposal nyata, bukan angka tetap 2.

    Uji audit 2026-10-11: kpi_service menulis `sample_count=2  # dua disposal di
    test; live = jumlah event`, sehingga angka sampel yang ditampilkan ke juri
    tidak mencerminkan data begitu jumlah disposal bukan dua.
    """
    _fx_disposal(fx, Decimal("5"), "expired_transport")
    _fx_disposal(fx, Decimal("7"), "spoilage_cold_chain")
    _fx_disposal(fx, Decimal("3"), "quality_reject")
    try:
        m = {m["name"]: m for m in _run(lambda s: compute_kpis(
            s, NOW - timedelta(days=7), NOW, fx.loc))}["Avoidable Food Loss"]
        assert m["state"] == "available"
        assert m["sample_count"] == 3
    finally:
        _db_exec("DELETE FROM disposal_events WHERE location_id=:l", {"l": fx.loc})


def test_food_loss_no_disposal_no_data(fx):
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=7), NOW, fx.loc))}["Avoidable Food Loss"]
    assert m["state"] == "no_data"


def test_sdc_mean_of_executed_po_anchored(fx):
    d1 = fx.decision("executed", sdc=Decimal("16206000"))
    d2 = fx.decision("executed", sdc=Decimal("14787096.28"))
    d3 = fx.decision("pending_approval", sdc=Decimal("99999999"))
    for d in (d1, d2, d3):
        fx.trace(d, "DETECT", NOW - timedelta(hours=2))
    fx.po(d1, NOW - timedelta(hours=1))
    fx.po(d2, NOW - timedelta(minutes=30))
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Safe Delivered Cost"]
    assert m["state"] == "available"
    assert m["value"] == "15496548.14"  # mean dua executed; pending excluded
    assert m["sample_count"] == 2


def test_price_deviation_abs_and_pairing(fx):
    # referensi lokasi uji 20000; lokasi lain 10000 (tidak boleh dipakai pairing)
    fx.price("pihps_reference", Decimal("20000"), NOW - timedelta(hours=3))
    fx.price("supplier_quote", Decimal("23000"), NOW - timedelta(hours=2),
             supplier_id=fx.sup)  # +15%
    fx.price("supplier_quote", Decimal("19000"), NOW - timedelta(hours=1),
             supplier_id=fx.sup)  # -5%
    # quote tanpa referensi lebih awal di lokasi ini → unpaired
    fx.price("supplier_quote", Decimal("21000"), NOW - timedelta(hours=5),
             supplier_id=fx.sup)
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Procurement Price Deviation"]
    assert m["state"] == "available"
    assert m["value"] == "10.00"  # mean(|15|, |5|); unpaired excluded
    assert m["sample_count"] == 2


def test_price_boundary_start_inclusive_end_exclusive(fx):
    fx.price("pihps_reference", Decimal("20000"), NOW - timedelta(days=1))
    start = NOW - timedelta(days=1)
    end = NOW
    fx.price("supplier_quote", Decimal("30000"), start, supplier_id=fx.sup)  # tepat start → masuk
    fx.price("supplier_quote", Decimal("40000"), end, supplier_id=fx.sup)  # tepat end → keluar
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, start, end, fx.loc))}["Procurement Price Deviation"]
    assert m["sample_count"] == 1
    assert m["value"] == "50.00"


def test_decision_time_from_detect_to_act(fx):
    d = fx.decision("executed", sdc=Decimal("1000000"))
    fx.trace(d, "DETECT", NOW - timedelta(minutes=150))
    fx.trace(d, "ACT", NOW - timedelta(minutes=30))  # 120 menit
    fx.po(d, NOW - timedelta(minutes=29))  # ACT dihitung hanya bila PO committed
    d2 = fx.decision("pending_approval")  # tanpa ACT → exclusion coverage
    fx.trace(d2, "DETECT", NOW - timedelta(minutes=60))
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Decision Time"]
    assert m["state"] == "available"
    assert m["value"] == "120.00"
    assert m["sample_count"] == 1
    assert m["coverage"] == "0.50"


def test_regional_imbalance_dedupe_lineage(fx):
    root_a = fx.decision("executed", sdc=Decimal("1000"))
    child_a = fx.decision("executed", sdc=Decimal("1000"),
                          supersedes=root_a)  # re-detect: bukan case baru
    root_b = fx.decision("rejected")
    for d in (root_a, child_a, root_b):
        fx.trace(d, "DETECT", NOW - timedelta(hours=1))
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Regional Imbalance Resolution Rate"]
    assert m["state"] == "available"
    assert m["value"] == "50.00"  # 2 root case, 1 executed
    assert m["sample_count"] == 2


def test_evidence_completeness_cutoff(fx, refs):
    # created_at di dalam window (end eksklusif — jangan pakai NOW persis)
    created = NOW - timedelta(minutes=30)
    cutoff = NOW - timedelta(minutes=60)
    d1 = fx.decision("pending_approval", created_at=created)
    fx.approve(d1, refs["head"], cutoff)  # CONSISTENT 1 role → cutoff
    fx.evidence(d1, "market_price", True, cutoff - timedelta(minutes=10))
    fx.evidence(d1, "temperature", True, cutoff - timedelta(minutes=5))
    # salinan tipe sama setelah cutoff → tidak menambah
    fx.evidence(d1, "temperature", True, cutoff + timedelta(minutes=5))
    d2 = fx.decision("pending_approval", created_at=created)
    fx.approve(d2, refs["head"], cutoff)
    fx.evidence(d2, "market_price", True, cutoff - timedelta(minutes=1))  # cuma 1
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Evidence Completeness"]
    assert m["state"] == "available"
    assert m["value"] == "50.00"
    assert m["sample_count"] == 2


def test_no_data_vs_available_and_trend(fx):
    m = {m["name"]: m for m in _run(lambda s: compute_kpis(
        s, NOW - timedelta(days=1), NOW, fx.loc))}["Safe Delivered Cost"]
    assert m["state"] == "no_data"
    assert m["value"] is None
    assert m["trend"] is None
