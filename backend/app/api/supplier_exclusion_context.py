"""Konteks tindakan administratif dari bukti keputusan yang tersimpan."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.decisions import _assert_decision_readable
from app.api.dependencies import get_db
from app.models import Batch, Decision, DecisionEvidence, Supplier, SupplierExclusion, User
from app.services.supplier_exclusion_service import serialize

router = APIRouter()


def present_context(rows: list, exclusions: list[dict], scope: UUID | None, allowed: bool) -> dict:
    suppliers = {}
    for batch, supplier in rows:
        item = suppliers.setdefault(str(supplier.id), {
            "id": str(supplier.id), "name": supplier.name, "batch_ids": [],
            "evidence_refs": [], "batches": [],
        })
        if str(batch.id) not in item["batch_ids"]:
            item["batch_ids"].append(str(batch.id))
            item["evidence_refs"].append({"type": "batch", "id": str(batch.id)})
            item["batches"].append({"id": str(batch.id), "safety_status": batch.safety_status})
    can_propose = bool(suppliers and scope and allowed)
    reason = None
    if not suppliers:
        reason = "Relasi supplier pada bukti batch belum tersedia; usulan tidak dapat dibuat."
    elif not allowed or not scope:
        reason = "Hanya approver pada SPPG tujuan yang dapat mengusulkan."
    return {"suppliers": list(suppliers.values()), "exclusions": exclusions,
            "scope_location_id": str(scope) if scope else None,
            "can_propose": can_propose, "reason_unavailable": reason}


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


@router.get("/supplier-exclusions/context/{decision_id}")
async def exclusion_context(
    decision_id: UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    decision = await db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "decision tidak ditemukan")
    await _assert_decision_readable(db, user, decision)
    evidence = (await db.execute(select(DecisionEvidence).where(
        DecisionEvidence.decision_id == decision_id,
    ))).scalars().all()
    batch_ids = set()
    refs = []
    for row in evidence:
        payload = row.payload or {}
        batch_ids.update(filter(None, [_uuid(payload.get("batch_id"))]))
        batch_ids.update(filter(None, map(_uuid, payload.get("batch_ids", []))))
        refs.extend(payload.get("evidence_refs", []))
    for ref in refs:
        if not isinstance(ref, dict) or not (identifier := _uuid(ref.get("id"))):
            continue
        if ref.get("type") == "batch":
            batch_ids.add(identifier)
        elif ref.get("type") in {"incident", "decision"}:
            query = select(DecisionEvidence)
            if ref["type"] == "incident":
                query = query.where(DecisionEvidence.id == identifier)
            else:
                query = query.where(DecisionEvidence.decision_id == identifier)
            for linked in (await db.execute(query)).scalars():
                batch_ids.update(filter(None, [_uuid(linked.payload.get("batch_id"))]))
                batch_ids.update(filter(None, map(_uuid, linked.payload.get("batch_ids", []))))
    rows = (await db.execute(select(Batch, Supplier).join(
        Supplier, Batch.supplier_id == Supplier.id,
    ).where(Batch.id.in_(batch_ids)))).all() if batch_ids else []
    supplier_ids = {supplier.id for _, supplier in rows}
    exclusions = (await db.execute(select(SupplierExclusion).where(
        SupplierExclusion.supplier_id.in_(supplier_ids),
        SupplierExclusion.scope_location_id == decision.target_location_id,
    ).order_by(SupplierExclusion.created_at.desc()))).scalars().all() if supplier_ids else []
    allowed = (
        user.role in {"sppg_head", "sppg_nutritionist"}
        and user.location_id == decision.target_location_id
    )
    return present_context(
        rows, [serialize(row) for row in exclusions], decision.target_location_id, allowed,
    )
