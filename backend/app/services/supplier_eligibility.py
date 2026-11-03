"""Binding batch/supplier untuk keputusan transfer dan revalidasi terkunci."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evidence_consistency import binding_consistency
from app.core.safety_gate import (
    BLOKIR_EKSEKUSI_KARANTINA,
    BLOKIR_EKSEKUSI_KEDALUWARSA,
    BLOKIR_SAFETY_FAIL_SUMBER,
    penghalang_sumber,
)
from app.models import Batch, Decision, DecisionEvidence
from app.services.supplier_exclusion_service import lock_supplier

#: Pesan manusiawi untuk kode blokir batch sumber. Kode → kalimat, bukan
#: sebaliknya, supaya "dikarantina" tidak pernah dilaporkan sebagai "FAIL".
#: Sejak Fase 4 kode berasal dari evaluator tunggal (`batch_eligibility`), jadi
#: `pending`/`needs_verification` punya kalimat sendiri — bukan disamakan
#: dengan FAIL seperti sebelumnya.
PESAN_BLOKIR = {
    BLOKIR_SAFETY_FAIL_SUMBER: "batch sumber kini FAIL (temperature excursion)",
    "safety_fail": "batch sumber kini FAIL (temperature excursion)",
    "safety_pending": "batch sumber belum diuji (safety pending) — perlu verifikasi",
    "safety_needs_verification": (
        "batch sumber menunggu verifikasi keamanan pangan"
    ),
    "safety_status_unknown": "status keamanan batch sumber tidak dikenal",
    BLOKIR_EKSEKUSI_KARANTINA: "batch sumber dikarantina/gagal",
    "quarantined": "batch sumber dikarantina/gagal",
    BLOKIR_EKSEKUSI_KEDALUWARSA: "batch sumber kedaluwarsa",
    "batch_expired": "batch sumber kedaluwarsa",
    "expiry_unknown": "masa layak batch sumber tidak tercatat",
    "temperature_evidence_incomplete": "bukti suhu batch sumber tidak lengkap",
    "evidence_missing": "bukti batch sumber tidak lengkap",
    "freshness_fail": "batch sumber tidak lagi segar",
    "expired_before_arrival": "batch sumber kedaluwarsa sebelum tiba",
    "delivery_window_exceeded": "jadwal kirim tidak lagi terpenuhi",
}


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
    # Pengadaan: pemasok binding WAJIB sama dengan pemasok keputusan. Tanpa ini
    # PO bisa diterbitkan ke pemasok yang berbeda dari yang tampil di layar
    # (temuan F5 audit 27 Okt 2026: `9d27bcfc` menampilkan "UD Blitar" tetapi
    # PO-nya ke "CV Ambarawa").
    if (
        decision.decision_type == "supplier_procurement"
        and decision.supplier_id is not None
        and decision.supplier_id != supplier_id
    ):
        raise HTTPException(422, "binding supplier tidak sama dengan pemasok keputusan")
    acuan = lokasi_batch_acuan(decision)
    batches = (await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))).scalars().all()
    if len(batches) != len(set(batch_ids)) or any(
        b.supplier_id != supplier_id
        or b.location_id != acuan
        or b.commodity_id != decision.commodity_id
        for b in batches
    ):
        raise HTTPException(422, "binding batch/supplier tidak cocok")
    binding_payload = {
        "allocation_binding": True,
        "supplier_id": str(supplier_id),
        "batch_ids": sorted(str(value) for value in set(batch_ids)),
    }
    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="human_inspection",
            payload=binding_payload,
            # Dinilai dari baris `batches` yang baru dibaca di atas (bukan dari
            # badan request): bukti yang tidak lagi cocok dengan DB tercatat
            # False, dan fakta yang tidak lengkap tetap None.
            is_consistent=binding_consistency(
                binding_payload,
                batch_ids=[b.id for b in batches],
                batch_suppliers=[b.supplier_id for b in batches],
                batch_locations=[b.location_id for b in batches],
                batch_commodities=[b.commodity_id for b in batches],
                supplier_id=supplier_id,
                source_location_id=acuan,
                commodity_id=decision.commodity_id,
            ),
        )
    )


def lokasi_batch_acuan(decision: Decision) -> uuid.UUID | None:
    """Lokasi tempat batch keputusan ini HARUS berada.

    Satu definisi, dipakai `resolve_binding`, `batch_sumber_transfer` dan guard
    safety (`actions._source_batches_still_safe`, `approval_summary._safety_view`).

    Pengadaan (`supplier_procurement`) tidak memindahkan stok SPPG lain: batch
    milik pemasok ada di SPPG TUJUAN, dan `decisions.source_location_id` memang
    NULL (`demo_procurement_orchestrator`: "sisi asal = NULL"). Dulu guard
    eksekusi membandingkan batch dengan lokasi SUMBER untuk semua jenis,
    sehingga pengadaan yang datanya sehat selalu ditolak
    `409 binding batch/supplier berubah` (terukur 27 Okt 2026, keputusan
    `943e662c…`) sementara `approval-summary` menyatakan `can_execute=True`.
    """
    if getattr(decision, "decision_type", None) == "supplier_procurement":
        return decision.target_location_id
    return decision.source_location_id


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
    acuan = lokasi_batch_acuan(decision)
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
                or b.location_id != acuan
                or b.commodity_id != decision.commodity_id
                for b in batches
            )
        ):
            raise HTTPException(409, "binding batch/supplier berubah")
    elif decision.decision_type == "supplier_procurement":
        # Pengadaan tanpa snapshot binding: pemasok datang dari kolom keputusan,
        # batch-nya di SPPG TUJUAN (lihat `lokasi_batch_acuan`).
        if decision.supplier_id is None or acuan is None:
            raise HTTPException(
                409, "supplier_unknown: keputusan pengadaan tanpa pemasok/batch tujuan"
            )
        supplier_id = decision.supplier_id
        batches = list(
            (await db.execute(query.where(
                Batch.location_id == acuan,
                Batch.supplier_id == supplier_id,
                Batch.commodity_id == decision.commodity_id,
            ))).scalars().all()
        )
        if not batches:
            raise HTTPException(409, "supplier_unknown: tidak ada batch pemasok di SPPG tujuan")
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
    return supplier_id, list(batches)


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
    # Delegasi ke definisi tunggal di `app.core.safety_gate`: blokir bila tidak
    # ada batch sumber, ada batch `fail`, dikarantina, atau kedaluwarsa.
    # `pending`/`needs_verification` TIDAK memblokir (keadaan normal sebelum
    # pengujian) — guard execute memakai fungsi yang sama, jadi `can_execute`
    # tidak bisa lagi menjanjikan eksekusi yang akan ditolak 409.
    return penghalang_sumber(batches, sekarang=datetime.now(UTC)) is not None


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
    # Binding GANDA berisi identik = satu alokasi yang ditulis dua kali, bukan
    # dua alokasi berbeda. Dulu semuanya ditolak, sehingga batch sumber terbaca
    # kosong, cek safety kehilangan bahan, verdict jatuh `unavailable`, dan
    # keputusan berhenti di `proposed` (terukur 28 Okt 2026). Konflik sungguhan
    # (fingerprint/batch berbeda) tetap fail-closed.
    if len(bindings) > 1:
        sidik = {
            (
                str(b.get("fingerprint") or ""),
                tuple(sorted(str(v) for v in b.get("batch_ids") or [])),
            )
            for b in bindings
        }
        if len(sidik) > 1:
            return []
        bindings = bindings[:1]
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
    acuan = lokasi_batch_acuan(decision)
    if decision.decision_type == "supplier_procurement":
        # Tanpa binding: batch milik pemasok keputusan, di SPPG TUJUAN.
        if decision.supplier_id is None or acuan is None:
            return []
        return list(
            (
                await db.execute(
                    select(Batch).where(
                        Batch.location_id == acuan,
                        Batch.supplier_id == decision.supplier_id,
                        Batch.commodity_id == decision.commodity_id,
                    )
                )
            )
            .scalars()
            .all()
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
    from app.services.supplier_exclusion_service import exclusion_aktif_untuk

    active = await exclusion_aktif_untuk(
        db,
        supplier_id=supplier_id,
        target_location_id=decision.target_location_id,
    )
    reasons = []
    if active:
        reasons.append("supplier excluded pada SPPG penerima")
    if not batches:
        reasons.append("safety revalidation gagal: tidak ada batch sumber")
    else:
        # Satu definisi dengan guard `_source_batches_still_safe` dan
        # `can_execute`; kode blokirnya disebut apa adanya supaya pesan tidak
        # menyamakan "kedaluwarsa"/"dikarantina" dengan "FAIL".
        blokir = penghalang_sumber(batches, sekarang=datetime.now(UTC))
        if blokir is not None:
            reasons.append(f"safety revalidation gagal: {PESAN_BLOKIR.get(blokir, blokir)}")

    if reasons:
        raise HTTPException(409, "; ".join(reasons))
    return supplier_id
