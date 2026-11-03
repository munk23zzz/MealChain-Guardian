"""`DecisionEvidencePacket` — SATU read model keputusan (Fase 6 butir 4).

Rencana (`MG/overview.md` §"Bentuk data inti") menetapkan paket bukti
keputusan yang dirakit SERVER dari data yang sama dengan evaluator:

    {decision_id, demo_session_id, batch_evaluations[], supplier, candidate,
     costs: CommercialCost | null, delivery{due_at, needed_by, feasible},
     evidence{source_types[], source_refs[], completeness},
     review{verifier, approvals[], blocking_reasons[]}}

Modul ini pembangkit TUNGGAL-nya. Tampilan biaya, approval, trace, dan Joule
membaca bentuk yang sama; frontend tidak merakit ulang evaluasi batch — kalau
ia merakit sendiri, dua layar bisa menyimpulkan hal berbeda dari data yang sama.

Prinsip yang dijaga:

- **Angka dari sumbernya, bukan hitungan kedua.** `costs` memakai resolver
  `core.commercial_cost` (bukan rumus baru), `batch_evaluations` memakai
  `core.batch_eligibility` (evaluator yang sama dengan dispatch/penerimaan),
  dan `review.blocking_reasons` diambil dari `services.approval_summary`
  (read model yang sama dengan modal approval).
- **`None` bukan nol.** Keputusan administratif tanpa transfer tidak punya
  invoice; biaya yang tidak dapat dibuktikan dikembalikan `null`.
- **Baca-saja.** Tidak ada mutation, tidak ada panggilan model.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.batch_eligibility import batch_policy_from, evaluate_batch
from app.core.commercial_cost import commercial_cost_payload
from app.core.logistics import estimate_logistics
from app.core.policy_store import profil_untuk_komoditas
from app.core.temperature import parse_temperature_log
from app.models import Commodity, Decision, DecisionEvidence, DemandRecord, Location
from app.services import supplier_exclusion_service as exclusions
from app.services.approval_summary import build_approval_summary, syarat_persetujuan
from app.services.batch_eligibility_service import fakta_batch, next_step
from app.services.supplier_eligibility import batch_sumber_transfer

__all__ = ["build_decision_packet"]

#: Bukti yang punya `review_reason` adalah hasil review MANUSIA (Fase 6 butir 3);
#: verdict LLM tidak pernah menulis payload ini.
_REVIEW_KEYS = ("review_reason", "reason")


def _payload(ev: DecisionEvidence) -> dict:
    data = ev.payload or {}
    return data if isinstance(data, dict) else {}


def _review_entries(rows) -> list[dict]:
    hasil = []
    for ev in rows:
        if ev.evidence_type != "human_inspection":
            continue
        data = _payload(ev)
        if not any(kunci in data for kunci in _REVIEW_KEYS):
            continue
        hasil.append(
            {
                "evidence_id": str(ev.id),
                "batch_id": data.get("batch_id"),
                "reviewed_by_user_id": data.get("reviewed_by_user_id"),
                "reviewed_by_role": data.get("reviewed_by_role"),
                "reviewed_at": data.get("reviewed_at") or ev.recorded_at.isoformat(),
                "reason": data.get("review_reason") or data.get("reason"),
                "evidence_refs": list(data.get("evidence_refs") or []),
                "safety_status_before": data.get("safety_status_before"),
                "safety_status_after": data.get("safety_status_after"),
                "policy_version": data.get("policy_version"),
            }
        )
    return hasil


def _source_refs(rows) -> list[dict]:
    """Referensi bukti apa adanya: tipe + rujukan yang tercatat di payload."""
    refs: list[dict] = []
    for ev in rows:
        data = _payload(ev)
        rujukan = (
            data.get("evidence_refs")
            or data.get("batch_ids")
            or ([data["ref"]] if data.get("ref") else [])
        )
        if isinstance(rujukan, str):
            rujukan = [rujukan]
        for item in rujukan or []:
            refs.append({"evidence_type": ev.evidence_type, "ref": str(item)})
    return refs


async def _commodity(db: AsyncSession, decision: Decision) -> Commodity | None:
    if decision.commodity_id is None:
        return None
    return (
        await db.execute(select(Commodity).where(Commodity.id == decision.commodity_id))
    ).scalar_one_or_none()


async def _nama_lokasi(db: AsyncSession, loc_id) -> str | None:
    if loc_id is None:
        return None
    return (
        await db.execute(select(Location.name).where(Location.id == loc_id))
    ).scalar_one_or_none()


async def _batch_evaluations(
    db: AsyncSession, decision: Decision, evaluation_time: datetime
) -> list[dict]:
    """Evaluasi batch terikat memakai evaluator tunggal + profil komoditas."""
    if decision.decision_type in exclusions.ADMIN_TYPES or decision.commodity_id is None:
        return []
    try:
        policy, asal = await profil_untuk_komoditas(db, decision.commodity_id)
    except KeyError:
        policy, asal = None, None
    batches = await batch_sumber_transfer(db, decision)
    kanonik = batch_policy_from(policy)
    hasil: list[dict] = []
    for batch in batches:
        evaluasi = evaluate_batch(
            fakta_batch(batch), kanonik, evaluation_time=evaluation_time
        )
        observasi = None
        if policy is not None:
            observasi = parse_temperature_log(
                batch.temperature_log or [],
                policy=policy,
                evaluation_time=evaluation_time,
            )
        hasil.append(
            {
                "batch_id": str(batch.id),
                "status": evaluasi.status,
                "blocking_reasons": list(evaluasi.blocking_reasons),
                "next_step": next_step(evaluasi),
                "policy_version": evaluasi.policy_version,
                "safety_status": batch.safety_status,
                "usable_until": (
                    batch.usable_until.isoformat() if batch.usable_until else None
                ),
                "temperature_observation": (
                    observasi.observation if observasi is not None else None
                ),
                "evidence_state": (
                    observasi.evidence_state if observasi is not None else None
                ),
                "observed_at": (
                    observasi.last_sample_at.isoformat()
                    if observasi is not None and observasi.last_sample_at
                    else None
                ),
                "profile_source": asal,
            }
        )
    return hasil


async def _delivery(
    db: AsyncSession,
    decision: Decision,
    evaluation_time: datetime,
    *,
    source_name: str | None,
    target_name: str | None,
) -> dict:
    """Tenggat kebutuhan + kelayakan waktu tiba.

    `needed_by` dibaca dari baris permintaan (bukan dikarang dari UI).
    `due_at` = tenggat tiba yang dipakai gerbang: `needed_by` selama belum ada
    jadwal kirim — tidak ada kolom `due_at` di skema, jadi mengarang tanggal
    lain akan menjadi angka baru yang tidak bisa ditelusuri.
    `feasible` dihitung dari `estimate_logistics` dengan jendela waktu nyata,
    bukan memanggil fungsi tanpa batas.
    """
    if decision.target_location_id is None or decision.commodity_id is None:
        return {
            "due_at": None,
            "needed_by": None,
            "feasible": None,
            "reason": "tanpa tujuan/komoditas",
        }
    row = (
        await db.execute(
            select(DemandRecord)
            .where(
                DemandRecord.location_id == decision.target_location_id,
                DemandRecord.commodity_id == decision.commodity_id,
                DemandRecord.recorded_at <= evaluation_time,
            )
            .order_by(DemandRecord.recorded_at.desc(), DemandRecord.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return {
            "due_at": None,
            "needed_by": None,
            "feasible": None,
            "reason": "baris permintaan tidak tercatat",
        }
    needed_by = row.needed_by
    feasible = None
    alasan = None
    if source_name and target_name and decision.quantity_kg is not None:
        jendela = (needed_by - evaluation_time).total_seconds() / 60.0
        try:
            logistik = estimate_logistics(
                source_name,
                target_name,
                float(decision.quantity_kg),
                delivery_window_min=max(0.0, jendela),
            )
            feasible = bool(logistik["feasible"])
            if not feasible:
                alasan = "waktu tiba melewati tenggat kebutuhan"
        except ValueError:
            feasible = None
            alasan = "jarak pasangan lokasi tidak diketahui"
    return {
        "due_at": needed_by.isoformat(),
        "needed_by": needed_by.isoformat(),
        "feasible": feasible,
        "reason": alasan,
    }


async def build_decision_packet(db: AsyncSession, decision: Decision) -> dict:
    """Rakit paket bukti satu keputusan dari DB kanonik (baca-saja)."""
    from app.services.decision_time import decision_now

    evaluation_time = decision_now(decision)
    summary = await build_approval_summary(db, decision)
    commodity = await _commodity(db, decision)
    source_name = summary.get("source_location")
    target_name = summary.get("target_location")

    evidence_rows = (
        (
            await db.execute(
                select(DecisionEvidence)
                .where(DecisionEvidence.decision_id == decision.id)
                .order_by(DecisionEvidence.recorded_at.asc(), DecisionEvidence.id.asc())
            )
        )
        .scalars()
        .all()
    )
    tipe = [ev.evidence_type for ev in evidence_rows]
    tipe_unik = sorted(set(tipe))
    human = _review_entries(evidence_rows)
    binding = [
        _payload(ev)
        for ev in evidence_rows
        if _payload(ev).get("allocation_binding") is True
    ]

    costs = None
    if decision.decision_type not in exclusions.ADMIN_TYPES:
        costs = commercial_cost_payload(decision.quantity_kg, decision.cost_breakdown)

    return {
        "decision_id": str(decision.id),
        "demo_session_id": (
            str(decision.demo_session_id) if decision.demo_session_id else None
        ),
        "decision_type": decision.decision_type,
        "status": decision.status,
        "evaluation_time": evaluation_time.isoformat(),
        "candidate": {
            "source_location": source_name,
            "destination_location": target_name,
            "commodity": commodity.name if commodity else None,
            "quantity_kg": (
                float(decision.quantity_kg)
                if decision.quantity_kg is not None
                else None
            ),
            "supplier_id": (
                str(decision.supplier_id) if decision.supplier_id else None
            ),
            "approval_requirement": syarat_persetujuan(decision),
        },
        "supplier": summary.get("supplier"),
        "batch_evaluations": await _batch_evaluations(db, decision, evaluation_time),
        "costs": costs,
        "delivery": await _delivery(
            db,
            decision,
            evaluation_time,
            source_name=source_name,
            target_name=target_name,
        ),
        "evidence": {
            "source_types": tipe_unik,
            "source_refs": _source_refs(evidence_rows),
            "completeness": {
                "types_recorded": len(tipe_unik),
                "records": len(evidence_rows),
                "has_allocation_binding": bool(binding),
                "has_human_review": bool(human),
                # `is_consistent` hanya bermakna bila sudah dinilai; None dibiarkan
                # None supaya "belum dinilai" tidak terbaca sebagai "konsisten".
                "consistency": [
                    {
                        "evidence_type": ev.evidence_type,
                        "is_consistent": ev.is_consistent,
                    }
                    for ev in evidence_rows
                ],
            },
        },
        "review": {
            "verifier": summary.get("verifier"),
            "approvals": summary.get("approvals", []),
            "approval_state": summary.get("approval_state"),
            "human_reviews": human,
            "blocking_reasons": summary.get("blocking_reasons", []),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
