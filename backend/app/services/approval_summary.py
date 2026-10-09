"""Approval summary read model (S4-04) — murni read, tanpa mutation.

Satu sumber kebenaran untuk modal approval: decision + konteks material +
safety/freshness batch sumber + verifier + expiry + approval matrix +
approvals tercatat + readiness aksi (can_approve/can_execute) +
blocking_reasons. Semua dihitung server-side dari DB kanonik (plan §S4-04,
prompt Owner §21) — UI tidak pernah menghitung requirement sendiri.

Parity dengan execute (O-PO): supplier/material yang dijanjikan summary
dihitung dengan logika yang sama dengan execute_action
(`_resolve_supplier_id` + `_material_number_for`), sehingga PO hasil
eksekusi selalu cocok dengan ringkasan yang disetujui manusia.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.approval_matrix import APPROVER_ROLES, evaluate_approvals
from app.core.decision_validity import is_decision_valid
from app.models import (
    Approval,
    Batch,
    Commodity,
    Decision,
    Location,
    Supplier,
    User,
)


def _verdict_of(decision: Decision) -> str:
    """Verdict tersimpan server-side; tanpa verdict → unavailable."""
    verdict = (decision.verifier_note or "").strip().lower()
    if verdict not in {"consistent", "flagged", "unavailable"}:
        verdict = "unavailable"
    return verdict


def _requirement_for(decision: Decision) -> dict:
    from app.core.approval_matrix import approval_requirement

    return approval_requirement(_verdict_of(decision))


async def _supplier_for(
    db: AsyncSession, decision: Decision, commodity: Commodity | None
) -> Supplier | None:
    """Supplier yang akan dipakai execute (logika sama, hasil parity)."""
    if decision.target_location_id is None or commodity is None:
        return None
    result = await db.execute(
        select(Supplier)
        .where(Supplier.location_id == decision.target_location_id)
        .order_by(Supplier.reliability_score.desc(), Supplier.id)
        .limit(1)
    )
    return result.scalars().first()


def _material_number(commodity: Commodity | None) -> str | None:
    return f"MAT-{commodity.name.upper()}" if commodity else None


async def _safety_view(
    db: AsyncSession, decision: Decision
) -> dict:
    """Safety batch sumber (lokasi+komoditas sama) — sejajar revalidation
    execute (O-EVENT-2). Tanpa lokasi/komoditas → unavailable, bukan fail."""
    if decision.source_location_id is None or decision.commodity_id is None:
        return {"worst_status": None, "blocked": False, "batches_checked": 0}
    batches = (
        await db.execute(
            select(Batch).where(
                Batch.location_id == decision.source_location_id,
                Batch.commodity_id == decision.commodity_id,
            )
        )
    ).scalars().all()
    if not batches:
        return {"worst_status": None, "blocked": False, "batches_checked": 0}
    statuses = [(b.safety_status or "pending") for b in batches]
    blocked = all(s == "fail" for s in statuses)
    worst = "fail" if blocked else (
        "needs_verification" if "needs_verification" in statuses else
        "pending" if "pending" in statuses else "pass"
    )
    return {
        "worst_status": worst,
        "blocked": blocked,
        "batches_checked": len(batches),
    }


async def build_approval_summary(db: AsyncSession, decision: Decision) -> dict:
    """Susun read model kanonik dari DB — tanpa call provider, tanpa write."""
    # Konteks lokasi/komoditas (nama manusiawi untuk UI).
    async def _loc_name(loc_id):
        if loc_id is None:
            return None
        row = await db.execute(
            select(Location.name).where(Location.id == loc_id)
        )
        return row.scalar_one_or_none()

    commodity = None
    if decision.commodity_id is not None:
        commodity = (
            await db.execute(
                select(Commodity).where(Commodity.id == decision.commodity_id)
            )
        ).scalar_one_or_none()

    supplier = await _supplier_for(db, decision, commodity)

    # Verifier + matrix + approvals (server-side, tidak dari client).
    req = _requirement_for(decision)
    approval_rows = (
        await db.execute(
            select(Approval)
            .where(Approval.decision_id == decision.id)
            .order_by(Approval.approved_at.asc(), Approval.id.asc())
        )
    ).scalars().all()
    role_by_id = {}
    if approval_rows:
        users = (
            await db.execute(
                select(User).where(
                    User.id.in_([a.approved_by for a in approval_rows])
                )
            )
        ).scalars().all()
        role_by_id = {u.id: u.role for u in users}
    approvals_payload = [
        {
            "role": role_by_id.get(a.approved_by),
            "approved": a.approved,
            "comment": a.comment,
            "approved_at": a.approved_at.isoformat(),
        }
        for a in approval_rows
    ]
    approval_state = evaluate_approvals(
        req,
        [{"role": a["role"], "approved": a["approved"]} for a in approvals_payload],
    )

    # Expiry + safety revalidation view.
    now = datetime.now(timezone.utc)
    valid = is_decision_valid(now, decision.expires_at)
    seconds_remaining = max(
        0, int((decision.expires_at - now).total_seconds())
    )
    safety = await _safety_view(db, decision)

    # Readiness aksi (kesimpulan server, bukan UI).
    unverified = not decision.verified_by
    # can_approve: approve tambahan masih sah selama status actionable,
    # tidak expired, belum rejected/executed (approve_action mengizinkan
    # approval ekstra — satisfaction hanya syarat execute).
    can_approve = (
        decision.status in {"pending_approval", "verifier_flagged"}
        and valid
        and approval_state["rejected"] is False
    )
    blocking: list[str] = []
    if not valid:
        blocking.append("decision expired")
    if unverified:
        blocking.append("decision belum terverifikasi")
    if decision.status == "rejected":
        blocking.append("decision ditolak")
    if decision.status == "executed":
        blocking.append("decision sudah dieksekusi")
    if decision.status not in {"pending_approval", "verifier_flagged"} and (
        decision.status not in {"executed", "rejected"}
    ):
        blocking.append(f"status {decision.status} tidak dapat dieksekusi")
    if not approval_state["satisfied"]:
        blocking.append("approval belum memenuhi requirement (missing/rejected)")
    if safety["blocked"]:
        blocking.append(
            "safety revalidation gagal: batch sumber kini FAIL"
        )
    can_execute = not blocking
    # Decision yang sudah executed tetap tampil executed tanpa tombol baru.
    if decision.status == "executed":
        can_execute = False

    return {
        "decision_id": str(decision.id),
        "decision_type": decision.decision_type,
        "status": decision.status,
        "iteration": decision.iteration or 1,
        "supersedes_id": (
            str(decision.supersedes_id) if decision.supersedes_id else None
        ),
        "proposed_by": decision.proposed_by,
        "source_location": await _loc_name(decision.source_location_id),
        "target_location": await _loc_name(decision.target_location_id),
        "commodity": commodity.name if commodity else None,
        "quantity_kg": (
            float(decision.quantity_kg)
            if decision.quantity_kg is not None
            else None
        ),
        "safe_delivered_cost": (
            float(decision.safe_delivered_cost)
            if decision.safe_delivered_cost is not None
            else None
        ),
        "cost_breakdown": decision.cost_breakdown,
        "material_number": _material_number(commodity),
        "supplier": (
            {
                "id": str(supplier.id),
                "name": supplier.name,
                "reliability_score": float(supplier.reliability_score),
            }
            if supplier
            else None
        ),
        "execution_target": "MOCK" if decision.target_location_id else None,
        "verifier": {
            "verdict": _verdict_of(decision),
            "verified_by": decision.verified_by,
        },
        "safety": safety,
        "expiry": {
            "expires_at": decision.expires_at.isoformat(),
            "valid": valid,
            "seconds_remaining": seconds_remaining,
        },
        "approval_requirement": req,
        "approval_state": approval_state,
        "approvals": approvals_payload,
        "can_approve": can_approve,
        "can_execute": can_execute,
        "blocking_reasons": blocking,
        # Disiplin approver untuk UI (read-only, bukan logika).
        "approver_roles": sorted(APPROVER_ROLES),
    }
