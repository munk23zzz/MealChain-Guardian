"""Approval summary read model (S4-04) — murni read, tanpa mutation.

Satu sumber kebenaran untuk modal approval: decision + konteks material +
safety/freshness batch sumber + verifier + expiry + approval matrix +
approvals tercatat + readiness aksi (can_approve/can_execute) +
blocking_reasons. Semua dihitung server-side dari DB kanonik (plan §S4-04,
prompt Owner §21) — UI tidak pernah menghitung requirement sendiri.

Parity dengan execute (O-PO): supplier berasal dari resolve_binding yang
sama dengan revalidasi transfer. Binding tidak valid memblokir readiness;
supplier tidak pernah ditebak dari lokasi atau quote.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.approval_matrix import APPROVER_ROLES, evaluate_approvals
from app.core.decision_validity import is_decision_valid
from app.models import (
    Approval,
    Commodity,
    Decision,
    Location,
    Supplier,
    User,
)

# Kelompok jenis keputusan administratif (eksklusi supplier). Diimpor, bukan
# disalin: sebelumnya modul ini menulis ulang himpunannya sebagai literal di
# dalam badan fungsi, dan salinan seperti itu bisa menyimpang dari yang dipakai
# penjaga endpoint (app/api/actions.py memakai konstanta yang sama).
from app.services import supplier_exclusion_service as exclusions


def _verdict_of(decision: Decision) -> str:
    """Verdict tersimpan server-side; tanpa verdict → unavailable."""
    verdict = (decision.verifier_note or "").strip().lower()
    if verdict not in {"consistent", "flagged", "unavailable"}:
        verdict = "unavailable"
    return verdict


def _requirement_for(decision: Decision) -> dict:
    from app.core.approval_matrix import approval_requirement

    # Harus parity dengan api/actions.py: transfer operasional wajib dua role
    # (PLAN.md §13.3); tipe administrasi (supplier exclusion) ikut verdict.
    operasional = decision.decision_type not in exclusions.ADMIN_TYPES
    return approval_requirement(_verdict_of(decision), dua_role_wajib=operasional)


async def _supplier_for(db: AsyncSession, decision: Decision) -> Supplier | None:
    """Supplier yang akan dipakai execute (logika sama, hasil parity)."""
    if decision.decision_type in exclusions.ADMIN_TYPES:
        from app.models import SupplierExclusion

        field = (
            SupplierExclusion.source_decision_id
            if decision.decision_type == "supplier_exclusion"
            else SupplierExclusion.restoration_decision_id
        )
        exclusion = (
            await db.execute(select(SupplierExclusion).where(field == decision.id))
        ).scalar_one_or_none()
        if exclusion is None:
            return None
        return (
            await db.execute(select(Supplier).where(Supplier.id == exclusion.supplier_id))
        ).scalar_one_or_none()
    from app.services.supplier_eligibility import resolve_binding

    supplier_id, _ = await resolve_binding(db, decision)
    return (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()


def _material_number(commodity: Commodity | None) -> str | None:
    return f"MAT-{commodity.name.upper()}" if commodity else None


async def _safety_view(db: AsyncSession, decision: Decision) -> dict:
    """Safety batch sumber yang AKAN dipakai execute — sejajar revalidation
    execute (O-EVENT-2). Tanpa lokasi/komoditas → unavailable, bukan fail.

    Set batch & definisi blokir diambil dari `supplier_eligibility`
    (`batch_sumber_transfer` + `source_batch_safety_blocked`) supaya
    `can_execute` tidak pernah menjanjikan eksekusi yang pasti 409.
    """
    from app.services.supplier_eligibility import (
        batch_sumber_transfer,
        source_batch_safety_blocked,
    )

    tak_terdefinisi = {
        "worst_status": None,
        "blocked": False,
        "batches_checked": 0,
        "reason": None,
    }
    if decision.source_location_id is None or decision.commodity_id is None:
        return tak_terdefinisi
    batches = await batch_sumber_transfer(db, decision)
    if not batches:
        # Tidak ada batch sumber terjangkau: execute menolak (revalidate_transfer),
        # tetapi tidak ada status yang bisa dilaporkan — jangan mengarang "fail".
        return {
            "worst_status": None,
            "blocked": True,
            "batches_checked": 0,
            "reason": "safety revalidation gagal: tidak ada batch sumber",
        }
    statuses = [(b.safety_status or "pending") for b in batches]
    blocked = source_batch_safety_blocked(batches)
    worst = (
        "fail"
        if blocked
        else (
            "needs_verification"
            if "needs_verification" in statuses
            else "pending"
            if "pending" in statuses
            else "pass"
        )
    )
    return {
        "worst_status": worst,
        "blocked": blocked,
        "batches_checked": len(batches),
        "reason": "safety revalidation gagal: batch sumber kini FAIL" if blocked else None,
    }


async def build_approval_summary(
    db: AsyncSession, decision: Decision, viewer_id: uuid.UUID | None = None
) -> dict:
    """Susun read model kanonik dari DB — tanpa call provider, tanpa write.

    `viewer_id` (opsional) dipakai untuk `approved_by_me`: apakah user yang
    MEMBACA sudah punya baris approval. UI memakainya supaya tidak menawarkan
    "Setuju" kepada orang yang approval-nya sudah tercatat — klik seperti itu
    selalu berakhir 409 "approval sudah tercatat" (laporan owner 17 Okt).
    """

    # Konteks lokasi/komoditas (nama manusiawi untuk UI).
    async def _loc_name(loc_id):
        if loc_id is None:
            return None
        row = await db.execute(select(Location.name).where(Location.id == loc_id))
        return row.scalar_one_or_none()

    commodity = None
    if decision.commodity_id is not None:
        commodity = (
            await db.execute(select(Commodity).where(Commodity.id == decision.commodity_id))
        ).scalar_one_or_none()

    binding_error = None
    try:
        supplier = await _supplier_for(db, decision)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        supplier = None
        binding_error = exc.detail

    # Verifier + matrix + approvals (server-side, tidak dari client).
    req = _requirement_for(decision)
    approval_rows = (
        (
            await db.execute(
                select(Approval)
                .where(Approval.decision_id == decision.id)
                .order_by(Approval.approved_at.asc(), Approval.id.asc())
            )
        )
        .scalars()
        .all()
    )
    role_by_id = {}
    if approval_rows:
        users = (
            (
                await db.execute(
                    select(User).where(User.id.in_([a.approved_by for a in approval_rows]))
                )
            )
            .scalars()
            .all()
        )
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
    # Apakah PEMBACA sudah menyetujui? Dihitung dari baris approval user itu
    # sendiri (bukan dari role), karena "approval sudah tercatat" diperiksa per
    # user di /actions/approve.
    approved_by_me = bool(
        viewer_id is not None
        and any(a.approved_by == viewer_id and a.approved for a in approval_rows)
    )

    # Expiry + safety revalidation view.
    now = datetime.now(timezone.utc)
    valid = is_decision_valid(now, decision.expires_at)
    seconds_remaining = max(0, int((decision.expires_at - now).total_seconds()))
    safety = await _safety_view(db, decision)
    supplier_governance = None
    execution_target = "MOCK" if decision.target_location_id else None
    if decision.decision_type in exclusions.ADMIN_TYPES:
        from app.models import DecisionEvidence, SupplierExclusion

        field = (
            SupplierExclusion.source_decision_id
            if decision.decision_type == "supplier_exclusion"
            else SupplierExclusion.restoration_decision_id
        )
        exclusion = (
            await db.execute(select(SupplierExclusion).where(field == decision.id))
        ).scalar_one_or_none()
        ev = (
            (
                await db.execute(
                    select(DecisionEvidence).where(DecisionEvidence.decision_id == decision.id)
                )
            )
            .scalars()
            .first()
        )
        data = (ev.payload if ev else {}) or {}
        supplier_governance = {
            "action": decision.decision_type,
            "reason": data.get("reason") or (exclusion.reason if exclusion else None),
            "scope_location_id": str(decision.target_location_id)
            if decision.target_location_id
            else None,
            "evidence_refs": data.get("evidence_refs", []),
            "supplier_id": str(exclusion.supplier_id) if exclusion else None,
            "exclusion_status": exclusion.status if exclusion else None,
        }
        execution_target = "LOCAL"

    # Readiness aksi (kesimpulan server, bukan UI).
    verified_note = (decision.verifier_note or "").lower()
    # Audit M1 (18 Okt 2026): "terverifikasi" = ada verdict hasil audit, bukan
    # sekadar baris verify. `verified_by` dulu ditulis walau UNAVAILABLE.
    unverified = not (decision.verified_by and verified_note in {"consistent", "flagged"})
    # Ruling Owner 2026-10-16 (keputusan 1b + 3b): gerbang approve/reject.
    #
    # SATU endpoint (`approve_action`) menangani "setuju" DAN "tolak" — bedanya
    # hanya payload (penolakan wajib beralasan). Jadi satu predikat, dua nama;
    # menghitungnya dua kali hanya membuat keduanya bisa menyimpang.
    #
    # Sebelumnya blok ini menuntut `valid` untuk SEMUA jenis keputusan, padahal
    # penjaga kedaluwarsa di /actions/approve BERSARANG di dalam blok
    # ADMIN_TYPES. Dua lapisan menyatakan aturan berbeda: UI mematikan "Setuju"
    # untuk keputusan kedaluwarsa jenis biasa, sementara endpoint tetap menerima
    # approval itu. Yang dipilih owner: perilaku ENDPOINT yang benar, read model
    # mengikuti — jenis administratif tetap dijaga, jenis biasa tidak.
    #
    # Catatan: /actions/execute memeriksa kedaluwarsa TANPA syarat, jadi
    # `can_execute` dan `blocking_reasons` di bawah tidak ikut dilonggarkan.
    approval_accepted = (
        decision.status in {"pending_approval", "verifier_flagged"}
        and (valid or decision.decision_type not in exclusions.ADMIN_TYPES)
        and approval_state["rejected"] is False
    )
    # Fase 0 butir 2 (18 Okt 2026): Setuju hanya ditawarkan bila verifikasi
    # sudah tercatat. Tanpa syarat ini alur bisa masuk jalan buntu: approve
    # dua kali → status `approved` (tidak menerima verify lagi) → execute
    # menolak selamanya. Penolakan tidak kami kunci.
    can_approve = approval_accepted and not unverified
    can_reject = approval_accepted
    blocking: list[str] = []
    if binding_error is not None:
        blocking.append(binding_error)
    if not valid:
        blocking.append("decision expired")
    if unverified:
        blocking.append(
            "decision belum terverifikasi"
            if not decision.verified_by
            else "verdict verifier tidak tersedia — bukan hasil audit"
        )
    if decision.status == "rejected":
        blocking.append("decision ditolak")
    if decision.status == "executed":
        blocking.append("decision sudah dieksekusi")
    if decision.status not in {"pending_approval", "verifier_flagged", "approved"} and (
        decision.status not in {"executed", "rejected"}
    ):
        blocking.append(f"status {decision.status} tidak dapat dieksekusi")
    if not approval_state["satisfied"]:
        blocking.append("approval belum memenuhi requirement (missing/rejected)")
    if safety["blocked"]:
        # Alasan diambil dari _safety_view (bisa "batch sumber FAIL" atau
        # "tidak ada batch sumber") — jangan menuliskan sebab yang belum tentu.
        blocking.append(safety.get("reason") or "safety revalidation gagal")
    can_execute = not blocking
    # Decision yang sudah executed tetap tampil executed tanpa tombol baru.
    if decision.status == "executed":
        can_execute = False

    return {
        "decision_id": str(decision.id),
        "decision_type": decision.decision_type,
        "status": decision.status,
        "iteration": decision.iteration or 1,
        "supersedes_id": (str(decision.supersedes_id) if decision.supersedes_id else None),
        "proposed_by": decision.proposed_by,
        "source_location": await _loc_name(decision.source_location_id),
        "target_location": await _loc_name(decision.target_location_id),
        "commodity": commodity.name if commodity else None,
        "quantity_kg": (float(decision.quantity_kg) if decision.quantity_kg is not None else None),
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
        "execution_target": execution_target,
        "supplier_governance": supplier_governance,
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
        "approved_by_me": approved_by_me,
        "approvals": approvals_payload,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_execute": can_execute,
        "blocking_reasons": blocking,
        # Disiplin approver untuk UI (read-only, bukan logika).
        "approver_roles": sorted(APPROVER_ROLES),
    }
