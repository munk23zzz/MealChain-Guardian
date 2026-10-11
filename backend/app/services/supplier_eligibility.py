"""Binding batch/supplier untuk keputusan transfer dan revalidasi terkunci."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, Decision, DecisionEvidence, SupplierExclusion
from app.services.supplier_exclusion_service import lock_supplier


async def persist_binding(db: AsyncSession, decision: Decision, candidate: dict) -> None:
    """Validasi FK batch asli, bukan supplier tebakan dari lokasi/quote."""
    batch_ids = candidate.get("batch_ids") or []
    supplier_id = candidate.get("supplier_id")
    if not batch_ids and not supplier_id:
        return  # keputusan legacy direvalidasi konservatif saat execute
    if batch_ids and not supplier_id:
        # Fixture/legacy Event 3 may carry only explicit batch IDs; derive
        # supplier from that batch FK, never from its location.
        batches = (await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))).scalars().all()
        suppliers = {b.supplier_id for b in batches}
        if len(suppliers) != 1 or None in suppliers:
            return
        supplier_id = next(iter(suppliers))
    try:
        supplier_id = uuid.UUID(str(supplier_id))
        batch_ids = [uuid.UUID(str(value)) for value in batch_ids]
    except ValueError as exc:
        raise HTTPException(422, "binding batch/supplier tidak valid") from exc
    if not batch_ids:
        raise HTTPException(422, "binding batch wajib")
    batches = (await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))).scalars().all()
    if len(batches) != len(set(batch_ids)) or any(
        b.supplier_id != supplier_id
        or b.location_id != decision.source_location_id
        or b.commodity_id != decision.commodity_id
        for b in batches
    ):
        raise HTTPException(422, "binding batch/supplier tidak cocok")
    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="human_inspection",
            payload={
                "allocation_binding": True,
                "supplier_id": str(supplier_id),
                "batch_ids": sorted(str(value) for value in set(batch_ids)),
            },
        )
    )


async def resolve_binding(db: AsyncSession, decision: Decision) -> tuple[uuid.UUID, list[Batch]]:
    """Legacy tanpa snapshot: hanya FK batch dengan satu supplier tidak ambigu."""
    evidence = (
        (
            await db.execute(
                select(DecisionEvidence).where(DecisionEvidence.decision_id == decision.id)
            )
        )
        .scalars()
        .all()
    )
    bindings = [e.payload for e in evidence if e.payload.get("allocation_binding") is True]
    query = select(Batch)
    if bindings:
        if len(bindings) != 1:
            raise HTTPException(409, "binding ambigu; ajukan keputusan baru")
        binding = bindings[0]
        try:
            ids = {uuid.UUID(str(v)) for v in binding["batch_ids"]}
            supplier_id = uuid.UUID(binding["supplier_id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, "binding tidak valid") from exc
        batches = (await db.execute(query.where(Batch.id.in_(ids)))).scalars().all()
        if (
            len(batches) != len(ids)
            or not ids
            or any(
                b.supplier_id != supplier_id
                or b.location_id != decision.source_location_id
                or b.commodity_id != decision.commodity_id
                for b in batches
            )
        ):
            raise HTTPException(409, "binding batch/supplier berubah")
    else:
        batches = (
            (await db.execute(query.where(
                Batch.location_id == decision.source_location_id,
                Batch.commodity_id == decision.commodity_id,
            ))).scalars().all()
        )
        suppliers = {b.supplier_id for b in batches}
        if len(suppliers) != 1 or None in suppliers:
            raise HTTPException(
                409, "supplier_unknown: keputusan lama perlu binding batch eksplisit"
            )
        supplier_id = suppliers.pop()
    return supplier_id, batches


def source_batch_safety_blocked(batches) -> bool:
    """True bila transfer TIDAK boleh dieksekusi karena keadaan batch sumber.

    Definisi TUNGGAL untuk blokir safety batch sumber: tidak ada batch sumber,
    atau ADA batch sumber ber-status FAIL. Dipakai bersama oleh
    `revalidate_transfer` (guard execute) dan `_safety_view` pada
    approval-summary, supaya readiness `can_execute` tidak pernah menjanjikan
    eksekusi yang pasti ditolak 409.

    Sebelum audit 2026-10-11, approval-summary memakai `all(... == "fail")`
    sehingga dua batch sumber (satu FAIL, satu aman) dilaporkan `blocked=False`.
    """
    if not batches:
        return True
    return any((b.safety_status or "pending") == "fail" for b in batches)


async def batch_sumber_transfer(db: AsyncSession, decision: Decision) -> list:
    """Batch sumber yang DIPAKAI execute: batch terikat bila ada binding,
    kalau tidak seluruh batch lokasi+komoditas sumber.

    Sama dengan set yang dihitung `resolve_binding`, tetapi TIDAK melempar:
    keadaan yang tidak dapat dipastikan (binding ganda / id rusak) dikembalikan
    sebagai daftar kosong — oleh `source_batch_safety_blocked` itu terbaca
    "diblokir", sikap konservatif untuk read model.
    """
    evidence = (
        (
            await db.execute(
                select(DecisionEvidence).where(
                    DecisionEvidence.decision_id == decision.id
                )
            )
        )
        .scalars()
        .all()
    )
    bindings = [
        (e.payload or {})
        for e in evidence
        if (e.payload or {}).get("allocation_binding") is True
    ]
    if len(bindings) > 1:
        return []
    if len(bindings) == 1:
        try:
            ids = {uuid.UUID(str(v)) for v in bindings[0]["batch_ids"]}
        except (ValueError, KeyError, TypeError):
            return []
        if not ids:
            return []
        return list(
            (await db.execute(select(Batch).where(Batch.id.in_(ids)))).scalars().all()
        )
    return list(
        (
            await db.execute(
                select(Batch).where(
                    Batch.location_id == decision.source_location_id,
                    Batch.commodity_id == decision.commodity_id,
                )
            )
        )
        .scalars()
        .all()
    )


async def revalidate_transfer(db: AsyncSession, decision: Decision) -> uuid.UUID:
    """Supplier row stabil diserialisasi dengan activation, termasuk tanpa exclusion row."""
    supplier_id, batches = await resolve_binding(db, decision)
    await lock_supplier(db, supplier_id)
    # Baca ulang sesudah lock: state exclusion/safety mungkin berubah saat menunggu.
    supplier_id, batches = await resolve_binding(db, decision)
    for batch in batches:
        await db.refresh(batch, with_for_update=True)
    active = (
        await db.execute(
            select(SupplierExclusion.id).where(
                SupplierExclusion.supplier_id == supplier_id,
                SupplierExclusion.scope_location_id == decision.target_location_id,
                SupplierExclusion.status == "active",
            )
        )
    ).first()
    reasons = []
    if active:
        reasons.append("supplier excluded pada SPPG penerima")
    if not batches:
        reasons.append("safety revalidation gagal: tidak ada batch sumber")
    elif source_batch_safety_blocked(batches):
        reasons.append("safety revalidation gagal: batch sumber kini FAIL")

    if reasons:
        raise HTTPException(409, "; ".join(reasons))
    return supplier_id
