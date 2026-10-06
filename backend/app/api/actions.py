"""Actions API (S3-01/S3-11) — propose/verify/approve/execute lifecycle.

propose ≠ approve ≠ execute (Rules.md). Eksekusi hanya Mock SAP dengan
penanda MOCK, hanya setelah approval manusia memenuhi approval matrix.
Tidak ada eksekusi otomatis oleh agent.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_roles
from app.api.dependencies import get_db
from app.core.approval_matrix import approval_requirement, evaluate_approvals
from app.core.decision_validity import is_decision_valid
from app.models import Approval, Commodity, Decision, User

router = APIRouter()

VERIFIER_ROLES = ("sppg_head", "sppg_nutritionist")


class ProposeRequest(BaseModel):
    decision_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    material_number: str = Field(min_length=1, max_length=64)


class VerifyRequest(BaseModel):
    decision_id: uuid.UUID
    verdict: str  # CONSISTENT | FLAGGED | UNAVAILABLE


class ApproveRequest(BaseModel):
    decision_id: uuid.UUID
    approved: bool
    comment: str | None = None


class ExecuteRequest(BaseModel):
    decision_id: uuid.UUID


async def _load_decision(db: AsyncSession, decision_id: uuid.UUID) -> Decision:
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    return row


def _requirement_for(row: Decision) -> dict:
    verdict = (row.verifier_note or "unavailable").strip().lower()
    if verdict not in {"consistent", "flagged", "unavailable"}:
        verdict = "unavailable"
    return approval_requirement(verdict)


def _verifier_unverified(row: Decision) -> bool:
    return not row.verified_by


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/actions/propose", status_code=201)
async def propose_action(
    payload: ProposeRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    if decision.status not in {"proposed", "verifier_flagged"}:
        raise HTTPException(
            status_code=409,
            detail=f"decision status {decision.status} tidak dapat dipropose ulang",
        )
    # Kunci nilai snapshot utk PO: commodity/supplier/lokasi.
    commodity = (
        await db.execute(
            select(Commodity).where(Commodity.id == decision.commodity_id)
        )
    ).scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=422, detail="commodity decision tidak valid")

    if is_decision_valid(_now_utc(), decision.expires_at) is False:
        raise HTTPException(status_code=409, detail="decision expired")

    decision.status = "pending_approval"
    await db.commit()
    req = _requirement_for(decision)
    return {
        "decision_id": str(decision.id),
        "status": decision.status,
        "verified": not _verifier_unverified(decision),
        "approval_requirement": req,
        "material_number": payload.material_number,
    }


@router.post("/actions/verify", status_code=200)
async def verify_action(
    payload: VerifyRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Catat verdict verifier (dipanggil supervisor pipeline, bukan LLM).

    Verdict WAJIB tertulis ke decisions.verifier_note — nilai inilah
    yang dibaca approval matrix saat approve/execute. Verdict tidak
    dikenal ditolak 422 SEBELUM mutasi apa pun.
    """
    decision = await _load_decision(db, payload.decision_id)
    verdict = payload.verdict.strip().lower()
    if verdict not in {"consistent", "flagged", "unavailable"}:
        raise HTTPException(
            status_code=422,
            detail="verdict verifier tidak dikenal (CONSISTENT|FLAGGED|UNAVAILABLE)",
        )
    decision.verified_by = "verifier_agent"
    decision.verifier_note = verdict
    if verdict == "flagged":
        decision.status = "verifier_flagged"
    await db.commit()
    req = _requirement_for(decision)
    return {
        "decision_id": str(decision.id),
        "verdict": payload.verdict.strip().upper(),
        "approval_requirement": req,
    }


@router.post("/actions/approve", status_code=200)
async def approve_action(
    payload: ApproveRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    if decision.status not in {"pending_approval", "verifier_flagged"}:
        raise HTTPException(
            status_code=409, detail=f"decision status {decision.status} tidak dapat di-approve"
        )
    db.add(
        Approval(
            decision_id=decision.id,
            approved_by=user.id,
            approved=payload.approved,
            comment=payload.comment,
        )
    )
    if not payload.approved:
        decision.status = "rejected"
    await db.commit()
    rows = (
        await db.execute(select(Approval).where(Approval.decision_id == decision.id))
    ).scalars().all()
    evaluation = evaluate_approvals(
        _requirement_for(decision),
        [
            {"role": u.role, "approved": a.approved}
            for a, u in zip(rows, await _approval_users(db, rows))
        ],
    )
    return {
        "decision_id": str(decision.id),
        "approved_by": str(user.id),
        "decision_status": decision.status,
        "approval_state": evaluation,
    }


async def _approval_users(db: AsyncSession, approvals):
    ids = [a.approved_by for a in approvals]
    if not ids:
        return []
    users = (
        await db.execute(select(User).where(User.id.in_(ids)))
    ).scalars().all()
    by_id = {u.id: u for u in users}
    return [by_id[a.approved_by] for a in approvals]


@router.post("/actions/execute", status_code=200)
async def execute_action(
    payload: ExecuteRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    if decision.status == "executed":
        raise HTTPException(status_code=409, detail="decision sudah dieksekusi")
    if _verifier_unverified(decision):
        raise HTTPException(status_code=409, detail="decision belum terverifikasi")
    if decision.status == "rejected":
        raise HTTPException(status_code=409, detail="decision ditolak")
    if not is_decision_valid(_now_utc(), decision.expires_at):
        raise HTTPException(status_code=409, detail="decision expired")
    if decision.status not in {"pending_approval", "verifier_flagged"}:
        raise HTTPException(
            status_code=409,
            detail=f"status {decision.status} tidak dapat dieksekusi",
        )

    rows = (
        await db.execute(select(Approval).where(Approval.decision_id == decision.id))
    ).scalars().all()
    evaluation = evaluate_approvals(
        _requirement_for(decision),
        [
            {"role": u.role, "approved": a.approved}
            for a, u in zip(rows, await _approval_users(db, rows))
        ],
    )
    if not evaluation["satisfied"]:
        raise HTTPException(
            status_code=409,
            detail="approval belum memenuhi requirement (missing/rejected)",
        )

    # Snapshot utk PO
    commodity = (
        await db.execute(
            select(Commodity).where(Commodity.id == decision.commodity_id)
        )
    ).scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=422, detail="commodity decision tidak valid")
    qty = decision.quantity_kg or Decimal("0")
    if qty <= 0:
        raise HTTPException(status_code=422, detail="quantity decision tidak valid")
    sdc = decision.safe_delivered_cost
    unit_price = (sdc / qty) if (sdc and qty > 0) else Decimal("0")
    if unit_price <= 0:
        raise HTTPException(status_code=422, detail="unit price decision tidak valid")

    po_number = f"MC-{decision.id.hex[:12].upper()}"
    supplier_id = await _resolve_supplier_id(db, decision.target_location_id, commodity)
    if supplier_id is None:
        raise HTTPException(
            status_code=422, detail="supplier untuk lokasi target tidak ditemukan"
        )
    await db.execute(
        text(
            "INSERT INTO sap_mock_purchase_orders "
            "(po_number, supplier_id, material_number, ordered_quantity, "
            "price, decision_id, status) "
            "VALUES (:po, :sup, :mat, :qty, :price, :dec, 'submitted')"
        ),
        {
            "po": po_number,
            "sup": supplier_id,
            "mat": _material_number_for(commodity),
            "qty": qty,
            "price": unit_price.quantize(Decimal("0.01")),
            "dec": decision.id,
        },
    )
    decision.status = "executed"
    await db.commit()
    return {
        "decision_id": str(decision.id),
        "po_number": po_number,
        "data_source": "MOCK",
        "status": "executed",
        "executed_by": str(user.id),
        "executed_at": _now_utc().isoformat(),
    }


def _material_number_for(commodity: Commodity) -> str:
    return f"MAT-{commodity.name.upper()}"


async def _resolve_supplier_id(
    db: AsyncSession, target_location_id, commodity: Commodity
):
    """Supplier lokal utk lokasi target (suppliers.location_id)."""
    if target_location_id is None:
        return None
    result = await db.execute(
        text(
            "SELECT id FROM suppliers "
            "WHERE location_id = :loc ORDER BY reliability_score DESC, id LIMIT 1"
        ),
        {"loc": target_location_id},
    )
    return result.scalar_one_or_none()
