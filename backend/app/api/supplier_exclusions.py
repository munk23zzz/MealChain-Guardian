"""Scope-local supplier governance. Approval/verify/execute reuse actions API."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.core.scope import assert_in_scope, is_national_scope
from app.models import SupplierExclusion
from app.services import supplier_exclusion_service as service

router = APIRouter()


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["batch", "incident", "decision"]
    id: uuid.UUID


class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=50)


class ProposalRequest(ReasonRequest):
    supplier_id: uuid.UUID
    scope_location_id: uuid.UUID


@router.post("/supplier-exclusions/proposals", status_code=201)
async def propose(
    payload: ProposalRequest, user=Depends(require_roles(*MUTATING_ROLES)), db=Depends(get_db)
):
    try:
        row = await service.propose(
            db,
            user,
            payload.supplier_id,
            payload.scope_location_id,
            payload.reason,
            [ref.model_dump(mode="json") for ref in payload.evidence_refs],
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return service.serialize(row)


@router.post("/supplier-exclusions/{exclusion_id}/restore", status_code=201)
async def restore(
    exclusion_id: uuid.UUID,
    payload: ReasonRequest,
    user=Depends(require_roles(*MUTATING_ROLES)),
    db=Depends(get_db),
):
    row = await db.get(SupplierExclusion, exclusion_id)
    if row is None:
        raise HTTPException(404, "exclusion tidak ditemukan")
    try:
        row = await service.propose(
            db,
            user,
            row.supplier_id,
            row.scope_location_id,
            payload.reason,
            [ref.model_dump(mode="json") for ref in payload.evidence_refs],
            restoration=row,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await db.commit()
    return service.serialize(row)


@router.get("/supplier-exclusions")
async def listing(
    supplier_id: uuid.UUID | None = None,
    scope_location_id: uuid.UUID | None = None,
    status: Literal["proposed", "active", "rejected", "revoked"] | None = None,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Register eksklusi. Ruling 2026-10-14: peran SPPG hanya melihat eksklusi
    ber-scope lokasinya (parameter `scope_location_id` asing → 403, bukan
    diabaikan diam-diam); bgn_monitor melihat semua."""
    query = select(SupplierExclusion)
    # Parameter cakupan asing = 403 (bukan diabaikan diam-diam). Tanpa
    # parameter, peran SPPG tetap hanya melihat eksklusi lokasinya sendiri.
    if scope_location_id is not None:
        assert_in_scope(user, scope_location_id, what="lokasi eksklusi")
    if not is_national_scope(user):
        query = query.where(SupplierExclusion.scope_location_id == user.location_id)
    for field, value in (
        (SupplierExclusion.supplier_id, supplier_id),
        (SupplierExclusion.scope_location_id, scope_location_id),
        (SupplierExclusion.status, status),
    ):
        if value is not None:
            query = query.where(field == value)
    rows = (
        (
            await db.execute(
                query.order_by(SupplierExclusion.created_at.desc(), SupplierExclusion.id)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [service.serialize(row) for row in rows], "count": len(rows)}
