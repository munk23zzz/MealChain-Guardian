"""Fakta audit deterministik untuk Verifier Agent (AUD-9A-03).

Kenapa modul ini ada
--------------------
Verifier agent (agent ke-8) dulu hanya MEWARISI verdict gerbang
(`agent/verify.py`) dan tidak pernah melihat fakta keputusan. Akibatnya
"audit" tidak dapat menangkap klaim yang bertentangan dengan data: SDC yang
tidak sama dengan rinciannya, batch sumber `fail`, bukti yang tidak pernah
tercatat, atau exclusion yang berlaku.

Modul ini adalah **satu-satunya sumber fakta** bagi verifier. Aturannya:

1. **Angka lahir dari kode, bukan dari model.** Semua nilai di sini dihitung
   fungsi domain yang sudah ada (`recommendation_numbers`, `core.freshness`,
   `safety_gate`/`supplier_eligibility`, `supplier_exclusion_service`) lalu
   dibaca apa adanya oleh verifier. Tidak ada kalkulator kedua di sisi agent.
2. **Baca-saja.** Hanya SELECT; tidak ada mutation, tidak ada provider model.
3. **Fail-closed.** Keadaan yang tidak dapat dibuktikan dilaporkan sebagai
   `None` / `dapat_dinilai=false` disertai alasan — bukan `lulus`.

Dikonsumsi lewat `GET /decisions/{decision_id}/audit-facts` (read-only) yang
juga menjadi "toolset" verifier: ia mengambil fakta sendiri, bukan menerima
ringkasan naratif supervisor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.freshness import (
    PASS_THRESHOLD,
    VERIFY_THRESHOLD,
    classify_freshness,
)
from app.core.recommendation_numbers import ringkasan_rincian
from app.core.safety_gate import penghalang_sumber
from app.models import (
    Batch,
    Decision,
    DecisionEvidence,
    LedgerBlock,
)


def _id(value: Any) -> str | None:
    return str(value) if value is not None else None


def _angka(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _teks(value: Any) -> str:
    return str(value or "").strip().lower()


async def _fakta_evidence(db: AsyncSession, decision: Decision) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(DecisionEvidence.id, DecisionEvidence.evidence_type).where(
                    DecisionEvidence.decision_id == decision.id
                )
            )
        )
        .all()
    )
    return {
        "count": len(rows),
        "ids": sorted(str(row[0]) for row in rows),
        "types": sorted({str(row[1]) for row in rows}),
    }


async def _fakta_batch_sumber(db: AsyncSession, decision: Decision) -> dict[str, Any]:
    """Keadaan batch SUMBER — himpunan yang sama dengan yang dipakai execute."""
    from app.services.supplier_eligibility import batch_sumber_transfer

    batches: list[Batch] = await batch_sumber_transfer(db, decision)
    statuses = [_teks(b.safety_status) or "pending" for b in batches]
    skor: list[float] = []
    for b in batches:
        nilai = _angka(b.freshness_score)
        if nilai is not None:
            skor.append(nilai)
    worst_score = min(skor) if skor else None
    return {
        "batch_ids": sorted(str(b.id) for b in batches),
        "count": len(batches),
        "statuses": statuses,
        "worst_status": (
            "fail"
            if "fail" in statuses
            else "pending"
            if "pending" in statuses
            else "pass"
            if statuses
            else None
        ),
        "failed_batch_ids": sorted(
            str(b.id) for b in batches if _teks(b.safety_status) == "fail"
        ),
        "quarantined_batch_ids": sorted(
            str(b.id)
            for b in batches
            if _teks(b.quarantine_status) in {"quarantined", "failed"}
        ),
        # Alasan blokir dipakai bersama guard execute (`penghalang_sumber`).
        "penghalang": penghalang_sumber(batches, sekarang=datetime.now(timezone.utc)),
        "worst_freshness_score": worst_score,
        "freshness_status": (
            classify_freshness(worst_score) if worst_score is not None else None
        ),
        "freshness_ambang": {
            "pass": PASS_THRESHOLD,
            "needs_verification": VERIFY_THRESHOLD,
        },
    }


async def _fakta_exclusion(db: AsyncSession, decision: Decision) -> dict[str, Any]:
    from app.services.supplier_eligibility import resolve_binding
    from app.services.supplier_exclusion_service import exclusion_aktif_untuk

    supplier_id = decision.supplier_id
    alasan = None
    if supplier_id is None:
        try:
            supplier_id, _batches = await resolve_binding(db, decision)
        except HTTPException as exc:
            alasan = str(exc.detail)
    if supplier_id is None or decision.target_location_id is None:
        return {
            "dapat_dinilai": False,
            "aktif": None,
            "ids": [],
            "alasan": alasan or "pemasok atau lokasi tujuan tidak diketahui",
        }
    # Definisi TUNGGAL yang dipakai guard execute (`revalidate_transfer`) dan
    # `can_execute` di approval-summary — bukan query tandingan di sini.
    baris = await exclusion_aktif_untuk(
        db,
        supplier_id=supplier_id,
        target_location_id=decision.target_location_id,
    )
    return {
        "dapat_dinilai": True,
        "aktif": baris is not None,
        "ids": [str(baris[0])] if baris is not None else [],
        "supplier_id": str(supplier_id),
        "alasan": alasan,
    }


async def _fakta_ledger(db: AsyncSession, decision: Decision) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(LedgerBlock.id, LedgerBlock.action).where(
                    LedgerBlock.entity_id == decision.id
                )
            )
        )
        .all()
    )
    return {
        "count": len(rows),
        "block_ids": sorted(str(row[0]) for row in rows),
        "actions": sorted({str(row[1]) for row in rows}),
    }


async def build_audit_facts(db: AsyncSession, decision: Decision) -> dict[str, Any]:
    """Susun fakta audit satu keputusan dari DB kanonik (read-only)."""
    evidence = await _fakta_evidence(db, decision)
    batch = await _fakta_batch_sumber(db, decision)
    exclusion = await _fakta_exclusion(db, decision)
    ledger = await _fakta_ledger(db, decision)

    return {
        "decision_id": str(decision.id),
        "decision_type": decision.decision_type,
        "status": decision.status,
        "iteration": decision.iteration or 1,
        "supersedes_id": _id(decision.supersedes_id),
        "commodity_id": _id(decision.commodity_id),
        "source_location_id": _id(decision.source_location_id),
        "target_location_id": _id(decision.target_location_id),
        "quantity_kg": _angka(decision.quantity_kg),
        "safe_delivered_cost": _angka(decision.safe_delivered_cost),
        # Fakta #1: SDC vs total rincian — aturan dari modul yang sama dengan
        # validasi pembuatan keputusan.
        "sdc_check": ringkasan_rincian(
            decision.safe_delivered_cost, decision.cost_breakdown
        ),
        # Fakta #2: bukti keputusan yang benar-benar tercatat.
        "evidence": evidence,
        # Fakta #3: batch sumber + gerbang kesegaran certified.
        "batch_sumber": batch,
        # Fakta #4: exclusion yang BERLAKU untuk (pemasok, lokasi tujuan).
        "exclusion": exclusion,
        # Fakta #5: blok ledger yang menunjuk keputusan ini.
        "ledger": ledger,
        # Himpunan id yang boleh dipakai verifier sebagai sitasi.
        "citations": {
            "decision_id": str(decision.id),
            "batch_ids": batch["batch_ids"],
            "evidence_ids": evidence["ids"],
            "ledger_block_ids": ledger["block_ids"],
            "exclusion_ids": exclusion["ids"],
        },
    }


__all__ = ["build_audit_facts"]
