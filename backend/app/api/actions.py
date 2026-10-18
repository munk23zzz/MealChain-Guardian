"""Actions API (S3-01/S3-11) — propose/verify/approve/execute lifecycle.

propose ≠ approve ≠ execute (Rules.md). Eksekusi hanya Mock SAP dengan
penanda MOCK, hanya setelah approval manusia memenuhi approval matrix.
Tidak ada eksekusi otomatis oleh agent.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

import pydantic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.verifier_client import run_verifier
from app.api.auth import require_roles
from app.api.dependencies import get_db
from app.core.approval_matrix import approval_requirement, evaluate_approvals
from app.core.decision_validity import is_decision_valid
from app.core.po_number import nomor_po
from app.core.scope import assert_in_scope
from app.models import AgentTrace, Approval, Batch, Commodity, Decision, User
from app.services import supplier_exclusion_service as exclusions
from app.services.ledger_service import append_block

router = APIRouter()

VERIFIER_ROLES = ("sppg_head", "sppg_nutritionist")
# PLAN.md §13.1/§13.3 (keputusan owner): hanya Head yang boleh mengusulkan,
# menentukan purpose operasional, dan mengeksekusi transfer. Nutritionist
# tetap boleh verify dan memberi approval kedua (lihat VERIFIER_ROLES).
PROPOSER_ROLES = ("sppg_head",)


class ProposeRequest(BaseModel):
    decision_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    #: Opsional sejak 18 Okt 2026: UI tidak tahu kode material, jadi server
    #: menurunkannya dari komoditas (`MAT-<KOMODITAS>`). Nilai eksplisit
    #: (Demo Control) tetap dipakai apa adanya.
    material_number: str | None = Field(default=None, min_length=1, max_length=64)


class VerifyRequest(BaseModel):
    decision_id: uuid.UUID

    model_config = pydantic.ConfigDict(extra="forbid")


class ApproveRequest(BaseModel):
    decision_id: uuid.UUID
    approved: bool
    comment: str | None = None


class ExecuteRequest(BaseModel):
    decision_id: uuid.UUID


async def _load_decision(db: AsyncSession, decision_id: uuid.UUID) -> Decision:
    row = (
        await db.execute(select(Decision).where(Decision.id == decision_id).with_for_update())
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="decision tidak ditemukan")
    return row


def _require_decision_scope(user: User, decision: Decision) -> None:
    """Cakupan lokasi pada JALUR TULIS keputusan (Ruling 2026-10-14 §3).

    "Keputusan yang menyasar SPPG X hanya bisa disetujui oleh approver dari
    SPPG X (kepala + ahli gizi X). Verifier kedua tidak lagi boleh berasal dari
    SPPG lain."

    Sebelum 2026-10-17 penjaga ini hanya dipasang di cabang `ADMIN_TYPES`
    (supplier_exclusion*), sehingga propose/verify/approve/execute keputusan
    operasional (`regional_balance`, `safety_disruption`, `price_anomaly`)
    masih bisa dijalankan peran SPPG dari lokasi lain. Aturan ditegakkan lewat
    helper kanonik `app/core/scope.assert_in_scope` — satu sumber pesan/aturan
    dengan endpoint baca (mis. `/decisions/{id}`), bukan salinan aturan baru.
    """
    assert_in_scope(user, decision.target_location_id, what="keputusan")


def _requirement_for(row: Decision) -> dict:
    verdict = (row.verifier_note or "unavailable").strip().lower()
    if verdict not in {"consistent", "flagged", "unavailable"}:
        verdict = "unavailable"
    # Keputusan operasional (transfer) wajib dua approval dari dua role —
    # Head lalu Nutritionist — apa pun verdict verifier-nya (PLAN.md §13.3).
    # Tipe administrasi (supplier exclusion/restoration) tetap ikut verdict.
    operasional = row.decision_type not in exclusions.ADMIN_TYPES
    return approval_requirement(verdict, dua_role_wajib=operasional)


def _verifier_unverified(row: Decision) -> bool:
    """Belum ADA verdict hasil audit (audit M1, 18 Okt 2026).

    Dulu cukup `verified_by` — padahal endpoint verify menulisnya bahkan ketika
    provider menjawab UNAVAILABLE. Sekarang verdict harus CONSISTENT/FLAGGED;
    "unavailable" berarti belum dinilai, bukan lulus.
    """
    return not (
        row.verified_by
        and (row.verifier_note or "").lower() in {"consistent", "flagged"}
    )


async def _verifier_ctx(
    db: AsyncSession, decision: Decision, commodity: Commodity | None
) -> dict:
    """Susun ctx verifier DARI data kanonik (audit M1).

    Sebelum ini safety/freshness/kandidat/logistik dikirim `null`, sehingga
    model hanya bisa menjawab UNAVAILABLE — dan verdict itu tetap dicatat
    sebagai "terverifikasi". Sekarang:
    - safety & freshness: batch terbaru di lokasi sumber untuk komoditas yang
      sama; trace DETECT (bila ada) menang karena ia peristiwa pemicunya;
    - kandidat: hasil OPTIMIZE trace (eligible_count + recommended_candidate),
      jatuh ke `candidate_score` snapshot bila trace tidak ada;
    - logistik: komponen jarak/transport dari cost breakdown keputusan.
    """
    safety_status = None
    freshness_score = None
    if decision.source_location_id and decision.commodity_id:
        batch = (
            await db.execute(
                text(
                    "SELECT safety_status, freshness_score FROM batches "
                    "WHERE location_id = :src AND commodity_id = :com "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"src": decision.source_location_id, "com": decision.commodity_id},
            )
        ).mappings().first()
        if batch:
            safety_status = batch["safety_status"]
            freshness_score = (
                float(batch["freshness_score"])
                if batch["freshness_score"] is not None
                else None
            )

    traces = (
        await db.execute(
            text(
                "SELECT step_name, output_summary FROM agent_traces "
                "WHERE decision_id = :d ORDER BY step_at"
            ),
            {"d": decision.id},
        )
    ).mappings().all()
    detect = next((t for t in traces if t["step_name"] == "DETECT"), None)
    if detect and isinstance(detect["output_summary"], dict):
        safety_status = detect["output_summary"].get("safety_status") or safety_status

    opt = next((t for t in traces if t["step_name"] == "OPTIMIZE"), None)
    opt_out = (opt["output_summary"] if opt else None) or {}
    candidates: list[dict] = []
    if detect and isinstance(detect["output_summary"], dict):
        daftar = detect["output_summary"].get("candidates")
        if isinstance(daftar, list) and daftar:
            candidates = daftar
    if not candidates and isinstance(opt_out, dict) and opt_out.get("chosen_candidate_id"):
        candidates = [
            {
                "candidate_id": opt_out.get("chosen_candidate_id"),
                "score": opt_out.get("score"),
                "rank": opt_out.get("rank"),
                "source_location": None,
                "destination_location": None,
                "commodity": commodity.name if commodity else None,
            }
        ]

    breakdown = decision.cost_breakdown if isinstance(decision.cost_breakdown, dict) else {}
    if not candidates and breakdown.get("candidate_score") is not None:
        source_name = None
        if decision.source_location_id:
            source_name = (
                await db.execute(
                    text("SELECT name FROM locations WHERE id = :l"),
                    {"l": decision.source_location_id},
                )
            ).scalar_one_or_none()
        candidates = [
            {
                "source_location": source_name,
                "score": str(breakdown.get("candidate_score")),
                "commodity": commodity.name if commodity else None,
            }
        ]

    logistics = None
    if breakdown.get("supplier_leg_km") or breakdown.get("transport_supplier_leg"):
        logistics = {
            "supplier_leg_km": breakdown.get("supplier_leg_km"),
            "transport_supplier_leg": breakdown.get("transport_supplier_leg"),
            "reference": breakdown.get("supplier_leg_reference"),
        }
    if logistics is None and decision.source_location_id and decision.target_location_id:
        # Fallback jujur: rute cache OSRM untuk pasangan lokasi ini (bila ada).
        # Tanpa rute, `logistics` tetap None — jangan mengarang jarak.
        from app.core.road_route import route_key

        koord = (
            await db.execute(
                text(
                    "SELECT id, latitude, longitude FROM locations "
                    "WHERE id IN (:src, :tgt)"
                ),
                {"src": decision.source_location_id, "tgt": decision.target_location_id},
            )
        ).mappings().all()
        peta = {str(r["id"]): r for r in koord}
        asal = peta.get(str(decision.source_location_id))
        tujuan = peta.get(str(decision.target_location_id))
        if asal and tujuan:
            key = route_key(
                float(asal["latitude"]),
                float(asal["longitude"]),
                float(tujuan["latitude"]),
                float(tujuan["longitude"]),
            )
            rute = (
                await db.execute(
                    text(
                        "SELECT distance_m, duration_s, source FROM road_routes "
                        "WHERE route_key = :k"
                    ),
                    {"k": key},
                )
            ).mappings().first()
            if rute:
                logistics = {
                    "distance_km": round(rute["distance_m"] / 1000, 1),
                    "duration_minutes": round(rute["duration_s"] / 60),
                    "reference": f"road_routes:{rute['source']}",
                }

    sdc = str(decision.safe_delivered_cost) if decision.safe_delivered_cost is not None else None
    return {
        "decision_id": str(decision.id),
        "commodity": commodity.name if commodity else None,
        "quantity_kg": (
            float(decision.quantity_kg) if decision.quantity_kg is not None else None
        ),
        "safety_status": safety_status,
        "freshness_score": freshness_score,
        "candidates": candidates,
        "eligible_count": opt_out.get("eligible_count") if isinstance(opt_out, dict) else None,
        "evidence": {"safe_delivered_cost": sdc, "cost_breakdown": breakdown},
        "logistics": logistics,
        "cost": {"safe_delivered_cost": sdc, "breakdown": breakdown},
        "rationale": (
            f"Audit independen decision {decision.decision_type} " f"iterasi {decision.iteration}"
        ),
    }


async def _source_batches_still_safe(db: AsyncSession, decision: Decision) -> bool:
    """O-EVENT-2 (plan §22): revalidasi safety saat eksekusi.

    Batch sumber = batch di lokasi sumber decision dengan komoditas yang
    sama. Bila SEMUA batch sumber kini FAIL → decision tidak boleh
    dieksekusi walau approval matrix sudah satisfied (safety hard stop;
    tanpa FK baru, tanpa migration). Decision tanpa lokasi/komoditas
    sumber (mis. price_anomaly) tidak direvalidasi → True.
    """
    if decision.source_location_id is None or decision.commodity_id is None:
        return True
    batches = (
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
    if not batches:
        return True
    # Cukup satu batch aman → eksekusi tetap mungkin; semua FAIL → blokir.
    return any((b.safety_status or "pending") != "fail" for b in batches)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/actions/propose", status_code=201)
async def propose_action(
    payload: ProposeRequest,
    user: User = Depends(require_roles(*PROPOSER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    if decision.status not in {"proposed", "verifier_flagged"}:
        raise HTTPException(
            status_code=409,
            detail=f"decision status {decision.status} tidak dapat diajukan untuk persetujuan",
        )
    if decision.decision_type in exclusions.ADMIN_TYPES:
        raise HTTPException(409, "gunakan endpoint proposal supplier-exclusions")
    # Ruling 2026-10-14 §3: proposal keputusan operasional ikut terkunci lokasi.
    _require_decision_scope(user, decision)
    # Kunci nilai snapshot utk PO: commodity/supplier/lokasi.
    commodity = (
        await db.execute(select(Commodity).where(Commodity.id == decision.commodity_id))
    ).scalar_one_or_none()
    if commodity is None:
        raise HTTPException(status_code=422, detail="commodity decision tidak valid")

    if is_decision_valid(_now_utc(), decision.expires_at) is False:
        raise HTTPException(status_code=409, detail="decision expired")

    decision.status = "pending_approval"
    await db.commit()
    req = _requirement_for(decision)
    material_number = payload.material_number or _material_number_for(commodity)
    return {
        "decision_id": str(decision.id),
        "status": decision.status,
        "verified": not _verifier_unverified(decision),
        "approval_requirement": req,
        "material_number": material_number,
    }


def get_verifier_chain() -> list[tuple[str, Callable, str]]:
    """Dependency chain verifier — overridable oleh test.

    Default: chain dari env (SAP AI Core → Bedrock sesuai konfigurasi).
    Provider tidak dikonfigurasi → chain kosong → run_verifier UNAVAILABLE.
    """
    from app.ai_providers.verifier_client import _default_env_chain

    return _default_env_chain()


@router.post("/actions/verify", status_code=200)
async def verify_action(
    payload: VerifyRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
    chain: list = Depends(get_verifier_chain),
):
    """Verifikasi independen SERVER-SIDE (O-SEC-3, plan §10).

    Browser TIDAK mengirim verdict — request hanya decision_id. Server
    menyusun ctx kanonik dari DB lalu menjalankan verifier via chain
    provider; tanpa provider → UNAVAILABLE (fail-closed, konservatif).
    Verify di luar fase pra-approval ditolak 409 (integritas matrix §22).
    """
    decision = await _load_decision(db, payload.decision_id)
    if decision.status not in {"proposed", "verifier_flagged", "pending_approval"}:
        raise HTTPException(
            status_code=409,
            detail=("verify hanya untuk decision pra-approval " f"(status kini {decision.status})"),
        )
    # Ruling 2026-10-14 §3: verifikasi pun terkunci lokasi. Sebelum ini penjaga
    # itu hanya berlaku untuk tipe administrasi, sehingga verifier dari SPPG
    # lain masih bisa memverifikasi keputusan operasional.
    _require_decision_scope(user, decision)
    existing_approvals = (
        (await db.execute(select(Approval).where(Approval.decision_id == decision.id)))
        .scalars()
        .all()
    )
    if existing_approvals:
        raise HTTPException(
            status_code=409,
            detail=(
                "verify tidak dapat diulang setelah ada approval tercatat "
                "(integritas audit trail)"
            ),
        )
    # Ruling Owner 2026-10-16 (keputusan 2b): endpoint ini DULU tidak memeriksa
    # kedaluwarsa sama sekali — hanya status pra-approval — sehingga verifikasi
    # pada keputusan yang sudah lewat tenggat diterima, berbeda dari
    # /actions/propose yang menolaknya tanpa syarat. Penjaganya disamakan.
    # Diletakkan SETELAH penjaga status/approval supaya urutan galat yang sudah
    # ada tidak berubah — yang berubah hanya panggilan yang dulu lolos.
    if not is_decision_valid(_now_utc(), decision.expires_at):
        raise HTTPException(status_code=409, detail="decision expired")
    # Audit M2 (18 Okt 2026): verdict yang SUDAH tercatat bersifat final.
    # Sebelum ini endpoint boleh dipanggil berulang selama belum ada approval,
    # dan setiap panggilan menimpa `verifier_note` — hasil audit bisa "diulang
    # sampai menyenangkan" (FLAGGED → CONSISTENT menurunkan syarat approval).
    # Retry tetap diizinkan bila percobaan sebelumnya TIDAK menghasilkan verdict
    # (unavailable): provider boleh pulih, dan belum ada hasil untuk ditimpa.
    if not _verifier_unverified(decision):
        raise HTTPException(
            status_code=409,
            detail=(
                "verdict sudah tercatat — hasil audit tidak bisa ditimpa; "
                "tarik/ajukan keputusan baru bila perlu penilaian ulang"
            ),
        )
    commodity = (
        await db.execute(select(Commodity).where(Commodity.id == decision.commodity_id))
    ).scalar_one_or_none()
    ctx = await _verifier_ctx(db, decision, commodity)
    if decision.decision_type in exclusions.ADMIN_TYPES:
        from app.models import DecisionEvidence

        evidence = (
            (
                await db.execute(
                    select(DecisionEvidence).where(DecisionEvidence.decision_id == decision.id)
                )
            )
            .scalars()
            .all()
        )
        ctx["evidence"] = {"administrative_evidence": [e.payload for e in evidence]}
    result = run_verifier(ctx, default_chain=chain)
    verdict = result.verdict  # CONSISTENT | FLAGGED | UNAVAILABLE (server)
    # Audit M1 (18 Okt 2026): `verified_by` hanya ditulis bila ADA hasil audit.
    # Dulu baris ini tanpa syarat, sehingga UNAVAILABLE pun tercatat sebagai
    # "terverifikasi" — dan pagar approve ikut terbuka.
    recorded = verdict in {"CONSISTENT", "FLAGGED"}
    if recorded:
        decision.verified_by = "verifier_agent"
    decision.verifier_note = verdict.lower()
    if verdict == "FLAGGED":
        decision.status = "verifier_flagged"
    # Audit M2: setiap percobaan meninggalkan jejak, dan verdict yang TERCATAT
    # menambah blok ledger. Tanpa ini riwayat "siapa memverifikasi, kapan, dengan
    # hasil apa" hanya hidup sebagai satu kolom yang bisa ditimpa.
    db.add(
        AgentTrace(
            decision_id=decision.id,
            step_name="VERIFY",
            tool_called="verifier",
            input_summary={"source": "db_canonical", "decision_status": decision.status},
            output_summary={
                "verdict": verdict,
                "recorded": recorded,
                "provider": result.provider,
                "fallback_used": result.fallback_used,
                "reason": (result.reason or "")[:500],
            },
            step_at=datetime.now(timezone.utc),
        )
    )
    if recorded:
        await append_block(
            db,
            action="verify",
            entity_id=decision.id,
            actor_id=user.id,
            payload={
                "decision_id": str(decision.id),
                "verdict": verdict,
                "provider": result.provider,
                "verifier_note": verdict.lower(),
            },
        )
    await db.commit()
    req = _requirement_for(decision)
    return {
        "decision_id": str(decision.id),
        "verdict": verdict,
        "recorded": recorded,
        "reason": result.reason,
        "verifier_note": verdict.lower(),
        "provider": result.provider,
        "fallback_used": result.fallback_used,
        "approval_requirement": req,
    }


@router.post("/actions/approve", status_code=200)
async def approve_action(
    payload: ApproveRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    # Ruling 2026-10-14 §3 + integritas jejak approval. Kedua penjaga ini DULU
    # berada di dalam cabang `ADMIN_TYPES`, sehingga keputusan operasional bisa
    # di-approve oleh peran SPPG dari lokasi lain dan di-approve dua kali oleh
    # satu orang.
    _require_decision_scope(user, decision)
    if decision.decision_type in exclusions.ADMIN_TYPES and not is_decision_valid(
        _now_utc(), decision.expires_at
    ):
        # Kedaluwarsa pada APPROVE sengaja hanya dijaga untuk keputusan
        # administratif — Keputusan owner 1b, dipaku
        # `test_approve_expired_ordinary_decision_accepted`: keputusan biasa
        # yang lewat tenggat masih boleh disetujui, tetapi tetap tidak bisa
        # dieksekusi karena /actions/execute memeriksa kedaluwarsa tanpa syarat.
        raise HTTPException(409, "decision expired")
    existing = (
        await db.execute(
            select(Approval.id).where(
                Approval.decision_id == decision.id, Approval.approved_by == user.id
            )
        )
    ).first()
    if existing:
        raise HTTPException(409, "approval sudah tercatat")
    # Status gate sengaja SETELAH pemeriksaan duplikat: user yang sudah
    # menyetujui keputusan berstatus `approved` harus membaca "approval sudah
    # tercatat", bukan "status approved tidak dapat di-approve" — pesan kedua
    # membuat orang mencari tombol yang sebenarnya sudah ia tekan.
    if decision.status not in {"pending_approval", "verifier_flagged"}:
        raise HTTPException(
            status_code=409, detail=f"decision status {decision.status} tidak dapat di-approve"
        )
    # Fase 0 butir 2 (18 Okt 2026): persetujuan SEBELUM verifikasi = jalan
    # buntu permanen. Begitu kuorum penuh, status menjadi `approved`, dan
    # status itu tidak menerima `/actions/verify` lagi — `/actions/execute`
    # lalu menolak selamanya dengan "belum diverifikasi". Menolak keputusan
    # tetap boleh: penolakan menghentikan laju, tidak butuh verdict.
    if payload.approved and _verifier_unverified(decision):
        raise HTTPException(
            status_code=409,
            detail=(
                "keputusan belum diverifikasi — catat hasil verifier dulu "
                "sebelum meminta persetujuan"
            ),
        )
    # Penolakan WAJIB beralasan — alasan inilah bahan learning agent
    # (rejection loop, permintaan Roy 2026-10-07). Tanpa alasan = 422.
    if not payload.approved and not (payload.comment or "").strip():
        raise HTTPException(
            status_code=422,
            detail="penolakan wajib menyertakan alasan (comment)",
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
        decision.rejection_reason = payload.comment.strip()
        if decision.decision_type == "supplier_exclusion":
            exclusion = await exclusions.for_decision(db, decision)
            exclusion.status = "rejected"
    # Ruling produk 2A (18 Okt 2026): kuorum penuh = status `approved`.
    #
    # Sebelum ini approve TIDAK PERNAH menyentuh status, sehingga keputusan
    # dengan dua approval tetap `pending_approval` sampai dieksekusi. Dampaknya:
    # auditor tidak bisa membedakan kuorum 1 dari kuorum 2, dan blok ledger
    # approval kedua menyimpan status yang salah. Evaluasi dilakukan SEBELUM
    # commit karena baris approval baru harus ikut dihitung (flush), dan status
    # hasilnya harus masuk ke payload ledger di bawah.
    await db.flush()
    rows = (
        (await db.execute(select(Approval).where(Approval.decision_id == decision.id)))
        .scalars()
        .all()
    )
    evaluation = evaluate_approvals(
        _requirement_for(decision),
        [
            {"role": u.role, "approved": a.approved}
            for a, u in zip(rows, await _approval_users(db, rows))
        ],
    )
    if payload.approved and evaluation["satisfied"]:
        decision.status = "approved"
    # P1 Merkle ledger: setiap approve/reject = block append-only.
    await append_block(
        db,
        action="approve" if payload.approved else "reject",
        entity_id=decision.id,
        actor_id=user.id,
        payload={
            "decision_id": str(decision.id),
            "approved": payload.approved,
            "comment": payload.comment,
            "status": decision.status,
        },
    )
    await db.commit()
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
    users = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    by_id = {u.id: u for u in users}
    return [by_id[a.approved_by] for a in approvals]


@router.post("/actions/execute", status_code=200)
async def execute_action(
    payload: ExecuteRequest,
    user: User = Depends(require_roles(*PROPOSER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    decision = await _load_decision(db, payload.decision_id)
    # Ruling 2026-10-14 §3: eksekusi terkunci ke lokasi target (semua tipe).
    _require_decision_scope(user, decision)
    # Audit M6 (18 Okt 2026): temuan review-only tidak pernah bisa dieksekusi.
    # Pesannya didahulukan supaya tidak terbaca "belum terverifikasi" — temuan
    # ini memang tidak menuntut verifikasi maupun approval.
    if decision.status == "review_only":
        raise HTTPException(
            status_code=409,
            detail="decision tinjauan (review-only) — tidak untuk dieksekusi",
        )
    if decision.status == "executed":
        if decision.decision_type in exclusions.ADMIN_TYPES:
            return {
                "decision_id": str(decision.id),
                "status": "executed",
                "data_source": "LOCAL",
                "exclusion": exclusions.serialize(await exclusions.for_decision(db, decision)),
            }
        raise HTTPException(status_code=409, detail="decision sudah dieksekusi")
    if _verifier_unverified(decision):
        raise HTTPException(status_code=409, detail="decision belum terverifikasi")
    if decision.status == "rejected":
        raise HTTPException(status_code=409, detail="decision ditolak")
    if not is_decision_valid(_now_utc(), decision.expires_at):
        raise HTTPException(status_code=409, detail="decision expired")
    if decision.status not in {"pending_approval", "verifier_flagged", "approved"}:
        raise HTTPException(
            status_code=409,
            detail=f"status {decision.status} tidak dapat dieksekusi",
        )

    rows = (
        (await db.execute(select(Approval).where(Approval.decision_id == decision.id)))
        .scalars()
        .all()
    )
    approvers = await _approval_users(db, rows)
    evaluation = evaluate_approvals(
        _requirement_for(decision),
        [
            {"role": u.role, "approved": a.approved}
            for a, u in zip(rows, approvers)
        ],
    )
    if not evaluation["satisfied"]:
        raise HTTPException(
            status_code=409,
            detail="approval belum memenuhi requirement (missing/rejected)",
        )
    # Ruling 2026-10-14 §3: hanya approval dari lokasi TARGET yang dihitung.
    # Filter ini dulu hanya dipakai untuk tipe administrasi, sehingga approval
    # approver SPPG lain (mis. baris lama sebelum ruling) ikut memenuhi matriks
    # keputusan operasional.
    scoped = evaluate_approvals(
        _requirement_for(decision),
        [
            {"role": u.role, "approved": a.approved}
            for a, u in zip(rows, approvers)
            if u.location_id == decision.target_location_id
        ],
    )
    if not scoped["satisfied"]:
        raise HTTPException(409, "approval scope tidak memenuhi requirement")

    if decision.decision_type in exclusions.ADMIN_TYPES:
        exclusion = await exclusions.execute(db, decision, user)
        decision.status = "executed"
        await append_block(
            db,
            action="execute",
            entity_id=decision.id,
            actor_id=user.id,
            payload={
                "decision_id": str(decision.id),
                "exclusion_id": str(exclusion.id),
                "administrative_action": decision.decision_type,
                "status": exclusion.status,
            },
        )
        await db.commit()
        return {
            "decision_id": str(decision.id),
            "status": "executed",
            "data_source": "LOCAL",
            "exclusion": exclusions.serialize(exclusion),
        }

    from app.services.supplier_eligibility import revalidate_transfer

    supplier_id = await revalidate_transfer(db, decision)

    # O-EVENT-2 revalidation: safety batch sumber dicek ULANG saat eksekusi
    # — rekomendasi lama tidak aman selamanya (plan §22).
    if not await _source_batches_still_safe(db, decision):
        raise HTTPException(
            status_code=409,
            detail=(
                "safety revalidation gagal: batch sumber kini FAIL "
                "(temperature excursion) — decision tidak dapat dieksekusi"
            ),
        )

    # Snapshot utk PO
    commodity = (
        await db.execute(select(Commodity).where(Commodity.id == decision.commodity_id))
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

    # Audit M8 (18 Okt 2026): satu pembentuk nomor PO untuk semua jalur.
    po_number = nomor_po(decision.id)
    if supplier_id is None:
        raise HTTPException(status_code=422, detail="supplier untuk lokasi target tidak ditemukan")
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
    # Trace langkah ACT (rantai PRD DETECT→…→DECIDE→ACT→LEARN). Sebelum
    # 16 Okt 2026 TIDAK ADA penulis ACT di repo ini — whitelist trace, CHECK
    # `agent_traces_step_name_check`, Schema.md, PRD, dan prompt supervisor
    # semuanya memuat ACT, tetapi satu-satunya penyebutannya di kode adalah
    # PEMBACA di `services/kpi_service.py` (metrik Decision Time) sehingga
    # kartu KPI itu `no_data` permanen. Eksekusi = saat PO benar-benar terbit,
    # dan itulah definisi "committed" yang dipakai metriknya: ACT ditulis di
    # sini, bukan saat approval (approval belum berarti komitmen ke SAP).
    # Jalur administratif (eksklusi pemasok) tidak menerbitkan PO → sengaja
    # tidak menulis ACT.
    db.add(
        AgentTrace(
            decision_id=decision.id,
            step_name="ACT",
            tool_called="sap_mock.create_purchase_order",
            input_summary={
                "decision_id": str(decision.id),
                "supplier_id": str(supplier_id),
                "material_number": _material_number_for(commodity),
                "quantity_kg": str(qty),
            },
            output_summary={
                "po_number": po_number,
                "status": "submitted",
                "data_source": "MOCK",
            },
        )
    )
    # P1 Merkle ledger: eksekusi = block append-only (bukti PO terbit).
    await append_block(
        db,
        action="execute",
        entity_id=decision.id,
        actor_id=user.id,
        payload={
            "decision_id": str(decision.id),
            "po_number": po_number,
            "quantity_kg": str(qty),
            "status": decision.status,
        },
    )
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


class ReproposeRequest(BaseModel):
    decision_id: uuid.UUID
    ttl_minutes: int = Field(default=30, ge=1, le=1440)


@router.post("/actions/repropose", status_code=201)
async def repropose_action(
    payload: ReproposeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*PROPOSER_ROLES)),
):
    """Agent merespons penolakan: iterasi baru + langkah LEARN.

    Iterasi mewarisi substansi keputusan (lokasi, komoditas, jumlah,
    SDC) dan terhubung ke keputusan lama via supersedes_id — alasan
    penolakan manusia menjadi bahan learning agent (rejection loop,
    permintaan Roy 2026-10-07). Iterasi baru TETAP butuh approve manusia.
    """
    parent = await _load_decision(db, payload.decision_id)
    # Audit M3 (18 Okt 2026): cakupan diperiksa untuk SEMUA tipe, bukan hanya
    # cabang ADMIN_TYPES. Sebelum ini Kepala SPPG lain bisa me-repropose
    # keputusan operasional yang ditolak; anaknya menyalin target parent,
    # sehingga ia menciptakan keputusan untuk SPPG yang bukan wilayahnya.
    _require_decision_scope(user, parent)
    if parent.decision_type in exclusions.ADMIN_TYPES:
        exclusions.require_scope(user, parent.target_location_id)
        raise HTTPException(
            409, "ajukan evidence baru melalui supplier-exclusions/proposals atau restore"
        )
    if parent.status != "rejected":
        raise HTTPException(
            status_code=409,
            detail=(f"re-propose hanya untuk decision rejected " f"(status kini {parent.status})"),
        )
    if not (parent.rejection_reason or "").strip():
        raise HTTPException(
            status_code=409,
            detail="decision rejected tanpa alasan — tidak ada bahan re-propose",
        )
    child = Decision(
        decision_type=parent.decision_type,
        status="proposed",
        proposed_by="supervisor_agent",
        source_location_id=parent.source_location_id,
        target_location_id=parent.target_location_id,
        commodity_id=parent.commodity_id,
        quantity_kg=parent.quantity_kg,
        safe_delivered_cost=parent.safe_delivered_cost,
        cost_breakdown=parent.cost_breakdown,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.ttl_minutes),
        iteration=(parent.iteration or 1) + 1,
        supersedes_id=parent.id,
        demo_case=parent.demo_case,
    )
    db.add(child)
    await db.flush()
    db.add(
        AgentTrace(
            decision_id=child.id,
            step_name="LEARN",
            tool_called="rejection_loop.repropose",
            input_summary={
                "parent_decision_id": str(parent.id),
                "parent_iteration": parent.iteration or 1,
                "parent_status": parent.status,
            },
            output_summary={
                "parent_rejection_reason": parent.rejection_reason,
                "learning_note": (
                    "Iterasi baru menyertakan penyesuaian atas penolakan: "
                    + (parent.rejection_reason or "")
                ),
            },
        )
    )
    await db.commit()
    return {
        "decision_id": str(child.id),
        "status": child.status,
        "iteration": child.iteration,
        "supersedes_id": str(parent.id),
        "parent_rejection_reason": parent.rejection_reason,
        "expires_at": child.expires_at.isoformat(),
    }


async def _resolve_supplier_id(db: AsyncSession, target_location_id, commodity: Commodity):
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
