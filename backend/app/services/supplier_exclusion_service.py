"""Administrative supplier decisions; caller owns transaction/commit."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evidence_consistency import administrative_consistency
from app.core.supplier_exclusion import ExclusionRequest, validate_request
from app.models import Batch, Decision, DecisionEvidence, Supplier, SupplierExclusion, User

ADMIN_TYPES = {"supplier_exclusion", "supplier_exclusion_restoration"}


def require_scope(user: User, location_id: uuid.UUID) -> None:
    if not user.location_id or user.location_id != location_id:
        raise HTTPException(403, "scope SPPG tidak berwenang")


async def lock_supplier(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id).with_for_update())
    ).scalar_one_or_none()
    if supplier is None:
        raise HTTPException(404, "supplier tidak ditemukan")
    return supplier


async def validate_evidence(db: AsyncSession, supplier_id: uuid.UUID, refs: list[dict]) -> None:
    """Incident = persisted temperature DecisionEvidence, not invented incident table."""
    for ref in refs:
        identifier = uuid.UUID(ref["id"])
        if ref["type"] == "batch":
            batch = await db.get(Batch, identifier)
            if batch is None or batch.supplier_id != supplier_id:
                raise HTTPException(422, "evidence batch tidak ada atau supplier tidak cocok")
        else:
            query = select(DecisionEvidence)
            if ref["type"] == "incident":
                query = query.where(
                    DecisionEvidence.id == identifier,
                    DecisionEvidence.evidence_type == "temperature",
                )
            else:
                if await db.get(Decision, identifier) is None:
                    raise HTTPException(422, "evidence decision tidak ditemukan")
                query = query.where(DecisionEvidence.decision_id == identifier)
            rows = (await db.execute(query)).scalars().all()
            linked = set()
            for row in rows:
                data = row.payload or {}
                if data.get("batch_id"):
                    linked.add(data["batch_id"])
                linked.update(data.get("batch_ids", []))
            associated = False
            for raw in linked:
                try:
                    batch = await db.get(Batch, uuid.UUID(str(raw)))
                except ValueError:
                    continue
                if batch is not None and batch.supplier_id == supplier_id:
                    associated = True
            if not associated:
                raise HTTPException(422, "evidence tidak memiliki asosiasi supplier persisten")


async def propose(
    db: AsyncSession, user: User, supplier_id: uuid.UUID, scope_location_id: uuid.UUID,
    reason: str, refs: list[dict], restoration: SupplierExclusion | None = None,
) -> SupplierExclusion:
    require_scope(user, scope_location_id)
    validate_request(ExclusionRequest(supplier_id, scope_location_id, reason, refs))
    supplier_row = await lock_supplier(db, supplier_id)
    await validate_evidence(db, supplier_id, refs)
    active = (
        await db.execute(
            select(SupplierExclusion).where(
                SupplierExclusion.supplier_id == supplier_id,
                SupplierExclusion.scope_location_id == scope_location_id,
                SupplierExclusion.status == "active",
            )
        )
    ).scalar_one_or_none()
    if restoration is not None:
        if active is None or active.id != restoration.id:
            raise HTTPException(409, "restoration membutuhkan exclusion aktif")
        if any(ref in restoration.evidence_refs for ref in refs):
            raise HTTPException(422, "pemulihan membutuhkan evidence baru")
        if restoration.restoration_decision_id:
            prior = await db.get(Decision, restoration.restoration_decision_id)
            if prior.status != "rejected" and prior.expires_at > datetime.now(timezone.utc):
                raise HTTPException(409, "proposal pemulihan masih berjalan")
    elif active is not None:
        raise HTTPException(409, "supplier sudah excluded pada scope ini")
    else:
        pending = (
            (
                await db.execute(
                    select(SupplierExclusion).where(
                        SupplierExclusion.supplier_id == supplier_id,
                        SupplierExclusion.scope_location_id == scope_location_id,
                        SupplierExclusion.status == "proposed",
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in pending:
            prior = await db.get(Decision, row.source_decision_id)
            if prior.status != "rejected" and prior.expires_at > datetime.now(timezone.utc):
                if row.reason == reason.strip() and row.evidence_refs == refs:
                    return row
                raise HTTPException(409, "proposal exclusion masih berjalan")
    decision = Decision(
        decision_type="supplier_exclusion_restoration" if restoration else "supplier_exclusion",
        status="pending_approval",
        proposed_by=str(user.id),
        target_location_id=scope_location_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(decision)
    await db.flush()
    if restoration:
        row = restoration
        row.restoration_decision_id = decision.id
    else:
        row = SupplierExclusion(
            supplier_id=supplier_id,
            scope_location_id=scope_location_id,
            status="proposed",
            reason=reason.strip(),
            evidence_refs=refs,
            source_decision_id=decision.id,
            proposed_by=user.id,
        )
        db.add(row)
    admin_payload = {
        "supplier_id": str(supplier_id),
        "scope_location_id": str(scope_location_id),
        "reason": reason.strip(),
        "evidence_refs": refs,
        "administrative_action": decision.decision_type,
    }
    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="human_inspection",
            payload=admin_payload,
            # `supplier_row` dibaca dengan FOR UPDATE di atas dan `scope` sudah
            # ditegakkan `require_scope`; bukti administratif tanpa alasan
            # tertulis tetap dicatat TIDAK konsisten (eksklusi tanpa alasan
            # tidak bisa ditinjau, lihat core/supplier_exclusion.py).
            is_consistent=administrative_consistency(
                admin_payload,
                supplier_id=supplier_row.id,
                scope_location_id=scope_location_id,
                supplier_exists=supplier_row is not None,
            ),
        )
    )
    await db.flush()
    return row


async def for_decision(db: AsyncSession, decision: Decision) -> SupplierExclusion:
    field = (
        SupplierExclusion.source_decision_id
        if decision.decision_type == "supplier_exclusion"
        else SupplierExclusion.restoration_decision_id
    )
    row = (
        await db.execute(select(SupplierExclusion).where(field == decision.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(409, "administrative decision tidak terhubung ke exclusion")
    return row


async def execute(db: AsyncSession, decision: Decision, user: User) -> SupplierExclusion:
    require_scope(user, decision.target_location_id)
    row = await for_decision(db, decision)
    await lock_supplier(db, row.supplier_id)
    await db.refresh(row)
    evidence = (
        (
            await db.execute(
                select(DecisionEvidence).where(
                    DecisionEvidence.decision_id == decision.id,
                    DecisionEvidence.payload["administrative_action"].astext
                    == decision.decision_type,
                )
            )
        )
        .scalars()
        .one()
    )
    await validate_evidence(db, row.supplier_id, evidence.payload["evidence_refs"])
    now = datetime.now(timezone.utc)
    if decision.decision_type == "supplier_exclusion":
        active = (
            await db.execute(
                select(SupplierExclusion.id).where(
                    SupplierExclusion.supplier_id == row.supplier_id,
                    SupplierExclusion.scope_location_id == row.scope_location_id,
                    SupplierExclusion.status == "active",
                )
            )
        ).scalar_one_or_none()
        if active is not None or row.status != "proposed":
            raise HTTPException(409, "exclusion tidak dapat diaktifkan")
        row.status = "active"
        row.activated_at = now
        row.approved_at = now
    else:
        if row.status != "active":
            raise HTTPException(409, "exclusion tidak aktif")
        row.status = "revoked"
        row.revoked_at = now
        row.revocation_reason = evidence.payload["reason"]
    return row


def serialize(row: SupplierExclusion) -> dict:
    return {
        key: (
            str(value)
            if isinstance(value, uuid.UUID)
            else value.isoformat()
            if isinstance(value, datetime)
            else value
        )
        for key in (
            "id",
            "supplier_id",
            "scope_location_id",
            "status",
            "reason",
            "evidence_refs",
            "source_decision_id",
            "restoration_decision_id",
            "proposed_by",
            "activated_at",
            "revoked_at",
            "revocation_reason",
            "created_at",
        )
        for value in [getattr(row, key)]
    }
