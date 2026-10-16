"""KPI service (S4-03) — agregasi deterministik dari records aplikasi.

Ruling O-KPI (plan addendum §23): state available/no_data/unavailable +
reason eksplisit; TANPA fake 0/proxy. Definisi per worksheet §10:
- Meal Continuity Rate: butuh facts menu/fulfilment yang tidak ada di
  schema → `unavailable` (bukan 0, bukan proxy PO).
- Avoidable Food Loss: butuh disposal event (discarded_at/reason) yang
  tidak ada → `unavailable`.
- Regional Imbalance Resolution Rate: root lineage (supersedes chain)
  dedupe; denominator DETECT root cases; numerator root dengan status
  executed di window.
- Safe Delivered Cost: mean SDC decision yang PO-nya committed pada
  window (anchor eksekusi = PO.created_at, bukan decision.created_at).
- Procurement Price Deviation: magnitudo absolut mean, pairing quote →
  referensi PIHPS terakhir pada lokasi+komoditas sama sebelum quote
  (O-NUM: absolut di aggregate, tanpa mengubah signed contract core).
- Decision Time: mean (first DETECT → last ACT) per decision; ACT hanya
  dihitung bila committed (PO ada); coverage = sample/eligible.
- Evidence Completeness: % decision dengan ≥2 distinct evidence type
  is_consistent SEBELUM approval-complete cutoff; bukti sesudah cutoff
  tidak dihitung; dua salinan tipe sama bukan dua sumber. Penyebutnya =
  keputusan yang PUNYA cutoff approval (16 Okt 2026): keputusan yang belum
  disetujui siapa pun tidak bisa dinilai lengkap/tidak, jadi ia keluar dari
  penyebut dan bagiannya dilaporkan `coverage`; tanpa satu pun approval
  metriknya `no_data`, bukan 0%.

Semua query period `[start, end)`. Omit location untuk SPPG difilter di
API layer (service menerima location_id=None = global).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.kpi import quantize2, resolve_root

METRIC_NAMES = (
    "Meal Continuity Rate",
    "Avoidable Food Loss",
    "Regional Imbalance Resolution Rate",
    "Safe Delivered Cost",
    "Procurement Price Deviation",
    "Decision Time",
    "Evidence Completeness",
)


def _metric(name, unit, state, value=None, reason=None, sample_count=0,
            coverage=None, previous_value=None, trend=None):
    return {
        "name": name,
        "unit": unit,
        "state": state,
        "value": None if value is None else str(quantize2(value)),
        "reason": reason,
        "sample_count": sample_count,
        "coverage": None if coverage is None else str(quantize2(coverage)),
        "previous_value": (
            None if previous_value is None else str(quantize2(previous_value))
        ),
        "trend": trend,
    }


def _no_data(name, unit, sample_count=0, reason=None):
    return _metric(
        name, unit, "no_data", reason=reason or "tidak ada record pada periode ini",
        sample_count=sample_count,
    )


async def _rows(db: AsyncSession, stmt: str, params: dict | None = None):
    result = await db.execute(text(stmt), params or {})
    return result.fetchall()


async def compute_kpis(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    location_id: uuid.UUID | None,
) -> dict:
    """Hitung tujuh KPI pada [start, end). Read-only."""
    loc_filter_dec = (
        "AND (d.source_location_id = :loc OR d.target_location_id = :loc)"
        if location_id else ""
    )
    loc_param = {"loc": location_id} if location_id else {}

    metrics: list[dict] = []

    # ---- 1. Meal Continuity Rate (P6, 009: facts menu/fulfilment kini ada)
    # = SUM(delivered_portions) / SUM(planned_portions) pada window.
    # delivered_at = anchor; delivery tanpa menu plan tidak mungkin (FK).
    # delivered_portions > planned → tetap dibatasi planned per plan (over-
    # delivery bukan continuity >100%, dibatasi 100% per plan-day).
    mc_rows = await _rows(
        db,
        "SELECT SUM(mp.planned_portions), "
        "SUM(LEAST(COALESCE(de.delivered, 0), mp.planned_portions)) "
        "FROM menu_plans mp LEFT JOIN ("
        "SELECT menu_plan_id, SUM(delivered_portions) AS delivered "
        "FROM delivery_events WHERE delivered_at >= :start "
        "AND delivered_at < :end GROUP BY menu_plan_id"
        ") de ON de.menu_plan_id = mp.id "
        # plan_date (bukan created_at): window continuity = tanggal rencana,
        # bukan kapan row dibuat (seed idempoten bisa dibuat ulang kapan pun).
        "WHERE mp.plan_date >= CAST(:start AS date) AND mp.plan_date < CAST(:end AS date) "
        + ("AND mp.location_id = :loc" if location_id else ""),
        {"start": start, "end": end, **loc_param},
    )
    planned_total = mc_rows[0][0] if mc_rows else None
    delivered_total = mc_rows[0][1] if mc_rows else None
    if planned_total and int(planned_total) > 0:
        mc_rate = Decimal(delivered_total) * 100 / Decimal(planned_total)
        plan_days = await _rows(
            db,
            "SELECT COUNT(*) FROM menu_plans WHERE plan_date >= CAST(:start AS date) "
            "AND plan_date < CAST(:end AS date)"
            + (" AND location_id = :loc" if location_id else ""),
            {"start": start, "end": end, **loc_param},
        )
        mc_metric = _metric(
            "Meal Continuity Rate", "percent", "available",
            value=mc_rate,
            sample_count=int(plan_days[0][0]) if plan_days else 0,
            coverage=Decimal(1),
        )
    else:
        mc_metric = _no_data(
            "Meal Continuity Rate", "percent",
            reason=(
                "tidak ada menu plan pada periode ini — "
                "unavailable bila tabel facts belum dimigrasi (009)"
            ),
        )
    metrics.append(mc_metric)

    # ---- 2. Avoidable Food Loss (P6, 009: disposal event kini ada)
    # = SUM(disposal kg) / (SUM disposal + SUM supply batch tercatat)
    # * 100 pada window — loss atas total input makanan nyata.
    fl_rows = await _rows(
        db,
        "SELECT (SELECT COALESCE(SUM(quantity_kg),0) FROM disposal_events "
        "WHERE disposed_at >= :start AND disposed_at < :end"
        + (" AND location_id = :loc" if location_id else "") +
        ") AS disposed_kg, "
        "(SELECT COALESCE(SUM(quantity_kg),0) FROM supply_records "
        "WHERE recorded_at >= :start AND recorded_at < :end"
        + (" AND location_id = :loc" if location_id else "") +
        ") AS supply_kg, "
        # sample_count = jumlah event disposal yang benar-benar dipakai di window
        # ini (dulu di-hardcode 2 sehingga angka sampel tidak mencerminkan data).
        "(SELECT COUNT(*) FROM disposal_events "
        "WHERE disposed_at >= :start AND disposed_at < :end"
        + (" AND location_id = :loc" if location_id else "") +
        ") AS disposal_events",
        {"start": start, "end": end, **loc_param},
    )
    disposed_kg = Decimal(str(fl_rows[0][0] or 0)) if fl_rows else Decimal(0)
    supply_kg = Decimal(str(fl_rows[0][1] or 0)) if fl_rows else Decimal(0)
    disposal_count = int(fl_rows[0][2] or 0) if fl_rows else 0
    if disposed_kg > 0:
        denom = disposed_kg + supply_kg
        fl_rate = disposed_kg * 100 / denom if denom > 0 else None
        fl_metric = _metric(
            "Avoidable Food Loss", "percent", "available",
            value=fl_rate,
            sample_count=disposal_count,
            coverage=Decimal(1),
        )
    elif disposed_kg == 0 and supply_kg > 0:
        fl_metric = _no_data(
            "Avoidable Food Loss", "percent",
            reason="tidak ada disposal event pada periode ini",
        )
    else:
        fl_metric = _no_data("Avoidable Food Loss", "percent")
    metrics.append(fl_metric)

    # ---- 3. Regional Imbalance Resolution Rate (dedupe root lineage) ----
    det_rows = await _rows(
        db,
        "SELECT d.id, d.supersedes_id, d.status FROM decisions d "
        "JOIN agent_traces t ON t.decision_id = d.id AND t.step_name = 'DETECT' "
        "WHERE t.step_at >= :start AND t.step_at < :end "
        "AND d.demo_case IS NULL " + loc_filter_dec,
        {"start": start, "end": end, **loc_param},
    )
    imbalance_rate = None
    imbalance_count = 0
    if det_rows:
        parent_map = {str(r[0]): str(r[1]) for r in det_rows if r[1]}
        root_status: dict[str, str] = {}
        for did, _sup, status in det_rows:
            root_status[str(did)] = status
        roots: dict[str, bool] = {}
        for did, status in root_status.items():
            root = resolve_root(parent_map, did)
            roots[root] = roots.get(root, False) or (status == "executed")
        imbalance_count = len(roots)
        executed = sum(1 for ok in roots.values() if ok)
        imbalance_rate = Decimal(executed) * 100 / Decimal(imbalance_count)
    metrics.append(
        _metric(
            "Regional Imbalance Resolution Rate", "percent",
            "available" if imbalance_rate is not None else "no_data",
            value=imbalance_rate,
            sample_count=imbalance_count,
            coverage=Decimal(1),
            reason=None if imbalance_rate is not None
            else "tidak ada DETECT pada periode ini",
        )
    )

    # ---- 4. Safe Delivered Cost: mean SDC executed (PO committed anchor) --
    sdc_rows = await _rows(
        db,
        "SELECT d.safe_delivered_cost FROM decisions d "
        "JOIN sap_mock_purchase_orders po ON po.decision_id = d.id "
        f"WHERE po.created_at >= :start AND po.created_at < :end "
        f"AND d.safe_delivered_cost IS NOT NULL {loc_filter_dec}",
        {"start": start, "end": end, **loc_param},
    )
    sdc_values = [Decimal(str(r[0])) for r in sdc_rows]
    if sdc_values:
        sdc_mean = sum(sdc_values) / Decimal(len(sdc_values))
        sdc_metric = _metric(
            "Safe Delivered Cost", "IDR", "available",
            value=sdc_mean, sample_count=len(sdc_values),
            coverage=Decimal(1),
        )
    else:
        sdc_metric = _no_data("Safe Delivered Cost", "IDR")
    metrics.append(sdc_metric)

    # ---- 5. Procurement Price Deviation (absolut, pairing per lokasi) ----
    ps_rows = await _rows(
        db,
        "SELECT ps.location_id, ps.commodity_id, ps.price_per_kg, ps.recorded_at "
        "FROM price_signals ps WHERE ps.source = 'supplier_quote' "
        "AND ps.recorded_at >= :start AND ps.recorded_at < :end "
        + ("AND ps.location_id = :loc" if location_id else ""),
        {"start": start, "end": end, **loc_param},
    )
    deviations: list[Decimal] = []
    for loc, com, quote, recorded_at in ps_rows:
        ref = await _rows(
            db,
            "SELECT price_per_kg FROM price_signals "
            "WHERE source='pihps_reference' AND location_id=:loc "
            "AND commodity_id=:com AND recorded_at <= :t "
            "ORDER BY recorded_at DESC LIMIT 1",
            {"loc": loc, "com": com, "t": recorded_at},
        )
        if not ref:
            continue  # unpaired → excluded, bukan dianggap 0%
        reference = Decimal(str(ref[0][0]))
        if reference == 0:
            continue
        q = Decimal(str(quote))
        deviations.append(abs(q - reference) / reference * Decimal("100"))
    if deviations:
        price_mean = sum(deviations) / Decimal(len(deviations))
        price_metric = _metric(
            "Procurement Price Deviation", "percent", "available",
            value=price_mean, sample_count=len(deviations),
            coverage=Decimal(1),
        )
    else:
        price_metric = _no_data("Procurement Price Deviation", "percent")
    metrics.append(price_metric)

    # ---- 6. Decision Time: mean first DETECT → last ACT (ACT committed) ---
    dt_rows = await _rows(
        db,
        "SELECT d.id, "
        "MIN(t.step_at) FILTER (WHERE t.step_name='DETECT') AS detect_at, "
        "MAX(t.step_at) FILTER (WHERE t.step_name='ACT') AS act_at "
        "FROM decisions d JOIN agent_traces t ON t.decision_id = d.id "
        "WHERE t.step_at >= :start AND t.step_at < :end "
        "AND d.demo_case IS NULL " + loc_filter_dec + " GROUP BY d.id",
        {"start": start, "end": end, **loc_param},
    )
    durations: list[Decimal] = []
    committed = await _rows(
        db,
        "SELECT decision_id FROM sap_mock_purchase_orders "
        "WHERE created_at >= :start AND created_at < :end",
        {"start": start, "end": end},
    )
    committed_ids = {str(r[0]) for r in committed}
    eligible = 0
    for did, detect_at, act_at in dt_rows:
        if detect_at is None:
            continue
        eligible += 1
        if act_at is None or str(did) not in committed_ids:
            continue  # ACT belum committed → exclusion, bukan proxy
        durations.append(
            Decimal(str((act_at - detect_at).total_seconds())) / Decimal("60")
        )
    if durations:
        dt_mean = sum(durations) / Decimal(len(durations))
        dt_metric = _metric(
            "Decision Time", "minutes", "available",
            value=dt_mean,
            sample_count=len(durations),
            coverage=(Decimal(len(durations)) / Decimal(eligible))
            if eligible else None,
        )
    else:
        dt_metric = _no_data("Decision Time", "minutes")
    metrics.append(dt_metric)

    # ---- 7. Evidence Completeness: ≥2 distinct consistent sebelum cutoff --
    ev_rows = await _rows(
        db,
        "SELECT d.id, d.status, "
        "MIN(a.approved_at) FILTER (WHERE a.approved IS TRUE) AS first_approve "
        "FROM decisions d "
        "LEFT JOIN approvals a ON a.decision_id = d.id "
        f"WHERE d.created_at >= :start AND d.created_at < :end {loc_filter_dec} "
        "GROUP BY d.id",
        {"start": start, "end": end, **loc_param},
    )
    ev_details = await _rows(
        db,
        "SELECT e.decision_id, e.evidence_type, e.is_consistent, e.recorded_at "
        "FROM decision_evidence e JOIN decisions d ON d.id = e.decision_id "
        f"WHERE d.created_at >= :start AND d.created_at < :end {loc_filter_dec}",
        {"start": start, "end": end, **loc_param},
    )
    ev_by_decision: dict[str, list[tuple]] = {}
    for did, etype, consistent, recorded_at in ev_details:
        ev_by_decision.setdefault(str(did), []).append(
            (etype, consistent, recorded_at)
        )
    complete = 0
    judged = 0
    # Penyebut = keputusan yang PUNYA cutoff approval, yaitu yang bisa dinilai
    # "bukti lengkap sebelum disetujui". Sebelum 2026-10-16 semua keputusan di
    # jendela dihitung, sehingga keputusan yang belum disetujui siapa pun
    # terhitung sebagai TIDAK lengkap dan kartu menampilkan 0,00% berlabel
    # "tersedia" padahal belum ada satu pun bukti yang dinilai. Keputusan tanpa
    # approval tidak bisa dinilai lengkap/tidak → keluar dari penyebut, dan
    # bagiannya dilaporkan lewat `coverage`, bukan disembunyikan.
    for did, _status, first_approve in ev_rows:
        if first_approve is None:
            continue  # belum ada approval → belum ada cutoff untuk dibandingkan
        judged += 1
        cutoff = first_approve  # approval-complete cutoff (konservatif: pertama)
        cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=start.tzinfo)
        distinct = set()
        for etype, consistent, recorded_at in ev_by_decision.get(str(did), []):
            if consistent is not True or recorded_at is None:
                continue
            rec = (
                recorded_at
                if recorded_at.tzinfo
                else recorded_at.replace(tzinfo=start.tzinfo)
            )
            if rec < cutoff:
                distinct.add(etype)
        if len(distinct) >= 2:
            complete += 1
    if judged:
        ev_rate = Decimal(complete) * 100 / Decimal(judged)
        ev_metric = _metric(
            "Evidence Completeness", "percent", "available",
            value=ev_rate,
            sample_count=judged,
            coverage=(
                Decimal(judged) / Decimal(len(ev_rows)) if ev_rows else None
            ),
        )
    else:
        ev_metric = _no_data(
            "Evidence Completeness", "percent",
            sample_count=0,
            reason=(
                "belum ada keputusan yang disetujui pada periode ini — "
                "tanpa approval tidak ada cutoff untuk menilai bukti"
            ),
        )
    metrics.append(ev_metric)

    assert [m["name"] for m in metrics] == list(METRIC_NAMES)
    return metrics
