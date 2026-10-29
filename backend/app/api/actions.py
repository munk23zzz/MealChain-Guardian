"""Actions API (S3-01/S3-11) — propose/verify/approve/execute lifecycle.

propose ≠ approve ≠ execute (Rules.md). Eksekusi hanya Mock SAP dengan
penanda MOCK, hanya setelah approval manusia memenuhi approval matrix.
Tidak ada eksekusi otomatis oleh agent.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

import pydantic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.verifier_client import run_verifier
from app.api.auth import require_roles
from app.api.dependencies import get_db
from app.core.approval_matrix import approval_requirement, evaluate_approvals
from app.core.commercial_cost import commercial_cost, komponen_desimal
from app.core.decision_validity import is_decision_valid
from app.core.po_number import nomor_po
from app.core.safety_gate import (
    batch_blokir_eksekusi,
    penghalang_sumber,
)
from app.core.scope import assert_in_scope
from app.models import (
    AgentTrace,
    Approval,
    Batch,
    Commodity,
    Decision,
    DecisionEvidence,
    DemoSession,
    User,
)
from app.services import settlement
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


async def _dispatch_bound_batches(
    db: AsyncSession, decision: Decision
) -> tuple[list[dict], list[dict]]:
    """Eksekusi keputusan pasokan = barang BERANGKAT.

    Kenapa ada (24 Okt 2026): `POST /actions/execute` dulu hanya mengubah status
    dan menerbitkan PO — tidak ada satu pun penulis `batches.dispatched_at`.
    Akibatnya demo "setujui pengiriman dari pemasok" berakhir di status
    `executed` tanpa truk apa pun di peta Overview.

    Batch yang dikirim = batch di `decision_evidence.payload.batch_ids` (jalur
    yang sama dengan revalidasi safety). Hanya batch yang belum berangkat yang
    disentuh; ETA dihitung dari `travelMin` yang sudah dipakai peta.
    """
    if decision.decision_type in {
        "supplier_exclusion",
        "supplier_exclusion_restoration",
        "price_anomaly",
    }:
        return [], []

    baris = (
        await db.execute(
            select(DecisionEvidence.payload).where(
                DecisionEvidence.decision_id == decision.id
            )
        )
    ).scalars().all()
    id_batch: set[uuid.UUID] = set()
    for payload in baris:
        for nilai in (payload or {}).get("batch_ids") or []:
            try:
                id_batch.add(uuid.UUID(str(nilai)))
            except (ValueError, TypeError):
                continue
    if not id_batch:
        return [], []

    batch = (
        (await db.execute(select(Batch).where(Batch.id.in_(id_batch)))).scalars().all()
    )
    sekarang = _now_utc()
    dikirim: list[dict] = []
    ditahan: list[dict] = []
    for b in batch:
        if b.dispatched_at is not None:
            # Batch yang sudah berangkat = sudah di jalan/tiba. Dulu dilewati
            # diam-diam sehingga eksekusi berakhir "executed" tanpa truk apa pun
            # (terukur 28 Okt 2026: batch template berangkat 8 Okt masih dipilih
            # sebagai kandidat pengadaan). Sekarang dilaporkan sebagai ditahan
            # supaya operator tahu barangnya memang sudah berangkat.
            ditahan.append(
                {
                    "batch_id": str(b.id),
                    "alasan": f"sudah berangkat {b.dispatched_at.isoformat()}",
                }
            )
            continue
        # Dulu `usable_until` yang sudah lewat DITULIS ULANG menjadi
        # `sekarang + 6 jam` sehingga barang kedaluwarsa bisa diberangkatkan
        # (temuan A-01/F-06). Sekarang batch yang tidak lolos gerbang
        # keselamatan tidak diberangkatkan dan tidak diberi tenggat baru.
        alasan = batch_blokir_eksekusi(
            safety_status=b.safety_status,
            quarantine_status=b.quarantine_status,
            usable_until=b.usable_until,
            temperature_log=b.temperature_log,
            sekarang=sekarang,
        )
        if alasan is not None:
            ditahan.append({"batch_id": str(b.id), "alasan": alasan})
            continue
        b.dispatched_at = sekarang
        dikirim.append({"batch_id": str(b.id), "dispatched_at": sekarang.isoformat()})
    return dikirim, ditahan


async def _source_batches_block_reason(db: AsyncSession, decision: Decision) -> str | None:
    """Alasan revalidasi safety saat eksekusi, atau `None` bila semua batch usable.

    Fase 4 MG: aturannya milik `app.core.batch_eligibility` (satu evaluator
    untuk rekomendasi, approval, dispatch, penerimaan). `pending` dan
    `needs_verification` kini DIBLOKIR sebagai `on_hold` — sebelumnya diloloskan,
    dan batch yang belum terbukti aman bisa menjadi stok `usable`.
    """
    if decision.commodity_id is None:
        return "commodity_missing"

    from app.services.supplier_eligibility import batch_sumber_transfer, lokasi_batch_acuan

    # Pengadaan punya batch di SPPG TUJUAN (sisi asal NULL) — definisi lokasi
    # diambil dari satu tempat (`lokasi_batch_acuan`), jadi jenis lain tetap
    # fail-closed.
    if lokasi_batch_acuan(decision) is None:
        return "source_location_missing"

    batches = await batch_sumber_transfer(db, decision)
    # Jam revalidasi mengikuti JANGKAR SESI keputusan, bukan jam dinding.
    # Fase 12 MG (terukur 27 Okt 2026): batch template berjangkar REF 8 Okt
    # dinilai "bukti suhu tidak lengkap" saat jam dinding sudah 19 hari lebih
    # maju, sehingga keputusan `executed` yang sah terbaca gagal revalidasi.
    # Keputusan yang tidak punya sesi (data operasional) tetap memakai jam dinding.
    sekarang = _now_utc()
    sesi_id = getattr(decision, "demo_session_id", None)
    if sesi_id is not None:
        try:
            sesi = await db.get(DemoSession, sesi_id)
            jangkar = getattr(sesi, "evaluation_anchor", None)
        except Exception:  # noqa: BLE001 — jam evaluasi tidak boleh menggagalkan guard
            jangkar = None
        if jangkar is not None:
            sekarang = jangkar
    return penghalang_sumber(batches, sekarang=sekarang)


async def _source_batches_still_safe(db: AsyncSession, decision: Decision) -> bool:
    """True bila SEMUA batch sumber usable (paritas dengan `can_execute`)."""
    return await _source_batches_block_reason(db, decision) is None


async def _sidik_bukti(db: AsyncSession, decision: Decision) -> dict | None:
    """Sidik bukti keputusan SAAT INI (Fase 4 butir 4).

    Approval manusia diberikan atas bukti tertentu: batch mana, pemasok mana,
    kuantitas/biaya berapa, profil komoditas versi apa, dan status evaluasinya
    apa. Sidik yang disimpan saat approve dibandingkan dengan sidik yang
    dihitung ulang saat eksekusi, sehingga pergantian batch atau profil setelah
    persetujuan tidak bisa lolos diam-diam.
    """
    from app.core.commodity_policy import policy_for
    from app.core.decision_fingerprint import dari_decision, hitung_sidik
    from app.core.policy_store import baca_semua_profil
    from app.models import Commodity
    from app.services.supplier_eligibility import batch_sumber_transfer

    if decision.commodity_id is None:
        return None
    nama = (
        await db.execute(
            select(Commodity.name).where(Commodity.id == decision.commodity_id)
        )
    ).scalar_one_or_none()
    profil, _asal = (await baca_semua_profil(db)).get(
        (nama or "").strip().lower(), (policy_for(nama), "bawaan")
    )
    batches = await batch_sumber_transfer(db, decision)
    alasan = await _source_batches_block_reason(db, decision)

    sidik = dari_decision(
        decision,
        batch_ids=[getattr(b, "id", b) for b in batches],
        supplier_id=str(decision.supplier_id) if decision.supplier_id else None,
        policy_version=profil.policy_version,
        evaluation_status="usable" if alasan is None else "on_hold",
        blocking_reasons=() if alasan is None else (alasan,),
    )
    return {
        # `jenis` membedakan sidik approval dari hasil inspeksi manusia biasa;
        # tabel `decision_evidence` punya CHECK tertutup pada `evidence_type`
        # (append-only, migrasi 042), jadi jenis dibedakan di dalam payload —
        # bukan dengan menambah nilai CHECK yang butuh migrasi baru.
        "jenis": "approval_binding",
        "fingerprint": hitung_sidik(sidik),
        "evaluation_status": sidik.evaluation_status,
        "blocking_reasons": list(sidik.blocking_reasons),
        "batch_ids": list(sidik.batch_ids),
        "policy_version": sidik.policy_version,
    }


async def _sidik_berubah(db: AsyncSession, decision: Decision) -> str | None:
    """Sebutkan apa yang berubah sejak approval, atau `None` bila masih sama.

    Keputusan yang disetujui SEBELUM sidik ada (data demo/seed) tidak dihukum:
    `None` berarti "tidak ada sidik tersimpan", dan gate safety tetap berjalan.
    """
    tersimpan = (
        await db.execute(
            select(DecisionEvidence)
            .where(
                DecisionEvidence.decision_id == decision.id,
                DecisionEvidence.evidence_type == "human_inspection",
                DecisionEvidence.payload["jenis"].astext == "approval_binding",
            )
            .order_by(DecisionEvidence.recorded_at.desc())
        )
    ).scalars().first()
    if tersimpan is None:
        return None
    kini = await _sidik_bukti(db, decision)
    if kini is None:
        return "bukti keputusan tidak dapat dihitung ulang"
    lama = tersimpan.payload or {}
    if lama.get("fingerprint") == kini["fingerprint"]:
        return None
    aspek = []
    if set(lama.get("batch_ids") or []) != set(kini["batch_ids"]):
        aspek.append("batch sumber")
    if lama.get("evaluation_status") != kini["evaluation_status"]:
        aspek.append("status bukti")
    if lama.get("policy_version") != kini["policy_version"]:
        aspek.append("profil komoditas")
    return ", ".join(aspek) or "isi keputusan"


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
        # Four-eyes (migrasi 030): satu akun = satu keputusan per usulan. Kunci
        # unik di DB menutup balapan dua request; pesan ini menjelaskan kenapa.
        raise HTTPException(
            409,
            "approval sudah tercatat untuk akun ini — empat mata berarti approver "
            "berbeda, bukan akun yang sama dua kali",
        )
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
    # Persetujuan bersyarat (keputusan produk, 28 Okt 2026): keputusan
    # `verifier_flagged` BOLEH disetujui, tetapi persetujuannya wajib membawa
    # catatan bahwa approver sadar ada temuan verifier. Tanpa catatan, audit
    # hanya melihat "approved" dan temuan verifier hilang dari jejak.
    komentar_final = (payload.comment or "").strip() or None
    if payload.approved and decision.status == "verifier_flagged":
        tanda = "disetujui meski verifier menandai temuan (diketahui approver)"
        komentar_final = f"{komentar_final} | {tanda}" if komentar_final else tanda
    db.add(
        Approval(
            decision_id=decision.id,
            approved_by=user.id,
            approved=payload.approved,
            comment=komentar_final,
        )
    )
    if payload.approved:
        # Fase 4 butir 4: simpan sidik bukti yang DISETUJUI. Tanpa ini,
        # approval hanya mengikat "keputusan dengan id ini" — batch bisa
        # berganti dan approval lama tetap dianggap sah.
        sidik = await _sidik_bukti(db, decision)
        if sidik is not None:
            db.add(
                DecisionEvidence(
                    decision_id=decision.id,
                    evidence_type="human_inspection",
                    payload=sidik,
                    is_consistent=True,
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
    try:
        await db.commit()
    except IntegrityError as exc:  # balapan dua approve bersamaan (unique 030)
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "approval untuk akun ini sudah tercatat; muat ulang lalu periksa kuorum"
            ),
        ) from exc
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


#: PO terakhir milik satu keputusan. Nomor PO deterministik dari id keputusan
#: (`core.po_number`), jadi satu keputusan hanya punya satu PO — tetapi query
#: ini tetap memakai ORDER BY supaya data lama (sebelum audit M8) ikut terbaca.
_PO_KEPUTUSAN = text(
    "SELECT po_number, status, created_at FROM sap_mock_purchase_orders "
    "WHERE decision_id = :d ORDER BY created_at DESC, po_number DESC LIMIT 1"
)


async def _evaluasi_approval(db: AsyncSession, decision: Decision) -> tuple[dict, dict]:
    """Matriks approval untuk satu keputusan: seluruhnya, dan yang scoped.

    Dua hasil karena dua pertanyaan berbeda: `evaluation` menjawab "apakah
    syaratnya terpenuhi", `scoped` menjawab "apakah terpenuhi oleh approver dari
    SPPG TUJUAN" (Ruling 2026-10-14 §3). Satu tempat untuk keduanya supaya
    `/actions/execute` dan review PO tidak bisa menyimpang.
    """
    rows = (
        (await db.execute(select(Approval).where(Approval.decision_id == decision.id)))
        .scalars()
        .all()
    )
    approvers = await _approval_users(db, rows)
    per_user = [
        {"role": u.role, "approved": a.approved} for a, u in zip(rows, approvers)
    ]
    scoped_rows = [
        {"role": u.role, "approved": a.approved}
        for a, u in zip(rows, approvers)
        if u.location_id == decision.target_location_id
    ]
    syarat = _requirement_for(decision)
    return (
        evaluate_approvals(syarat, per_user),
        evaluate_approvals(syarat, scoped_rows),
    )


def _harga_satuan_invoice(decision: Decision, qty: Decimal) -> Decimal:
    """Harga satuan yang ditagihkan pada PO (bahan + transportasi + penanganan).

    Fase 5 butir 2/4: harga PO = harga INVOICE, bukan `sdc / qty`. Sebelum
    perbaikan ini `price` memuat expected_loss + penalti kesegaran + penalti
    keamanan, sehingga dokumen yang dibayar pemasok menagihkan kerugian internal
    yang tidak pernah ia sebabkan (terukur: 37.171,00 vs 29.421,00 pada rincian
    uji Fase 5). Rincian lama `{"purchase": ...}` tetap dipakai apa adanya.
    """
    breakdown = decision.cost_breakdown if isinstance(decision.cost_breakdown, dict) else None
    biaya = commercial_cost(qty, breakdown)
    if biaya is not None:
        return biaya.invoice_unit_price
    purchase = komponen_desimal(breakdown, "purchase")
    if purchase is not None and purchase > 0:
        return (purchase / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal("0")


async def _commit_purchase_order(
    db: AsyncSession,
    decision: Decision,
    po_number: str,
    harga: Decimal,
    supplier_id: uuid.UUID,
    material_number: str,
    user: User,
) -> tuple[list[dict], list[dict]]:
    """Kirim PO ke SAP mock dan tutup keputusannya (gerbang kedua).

    Semua akibat "komitmen" dikumpulkan di satu tempat karena hanya boleh
    terjadi SEKALI, saat Kepala SPPG mereview PO draft: PO menjadi `submitted`,
    keputusan `executed`, trace ACT ditulis (itu definisi "committed" pada KPI
    Decision Time), harga PO dicatat sebagai kutipan, batch terikat
    diberangkatkan, dan satu blok ledger `execute` ditambahkan.
    """
    await db.execute(
        text("UPDATE sap_mock_purchase_orders SET status = 'submitted' WHERE po_number = :po"),
        {"po": po_number},
    )
    decision.status = "executed"
    db.add(
        AgentTrace(
            decision_id=decision.id,
            step_name="ACT",
            tool_called="sap_mock.create_purchase_order",
            input_summary={
                "decision_id": str(decision.id),
                "supplier_id": str(supplier_id),
                "material_number": material_number,
                "quantity_kg": str(decision.quantity_kg),
            },
            output_summary={
                "po_number": po_number,
                "status": "submitted",
                "data_source": "MOCK",
            },
        )
    )
    await settlement.catat_po_terbit(
        db,
        decision=decision,
        po_number=po_number,
        supplier_id=supplier_id,
        harga_per_kg=harga,
        sekarang=_now_utc(),
    )
    dikirim, ditahan = await _dispatch_bound_batches(db, decision)
    await append_block(
        db,
        action="execute",
        entity_id=decision.id,
        actor_id=user.id,
        payload={
            "decision_id": str(decision.id),
            "po_number": po_number,
            "quantity_kg": str(decision.quantity_kg or ""),
            "status": decision.status,
        },
    )
    return dikirim, ditahan


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

    # Matriks approval: satu tempat untuk keduanya (`_evaluasi_approval`), supaya
    # gerbang eksekusi dan gerbang review PO tidak bisa menyimpang.
    # Ruling 2026-10-14 §3: hanya approval dari lokasi TARGET yang dihitung.
    evaluation, scoped = await _evaluasi_approval(db, decision)
    if not evaluation["satisfied"]:
        raise HTTPException(
            status_code=409,
            detail="approval belum memenuhi requirement (missing/rejected)",
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
    # — rekomendasi lama tidak aman selamanya (plan §22). Fase 4: alasan
    # berasal dari evaluator yang sama dengan `can_execute`, jadi pesan 409
    # menyebut SEBAB yang benar (`safety_pending` ≠ `safety_fail`).
    from app.services.supplier_eligibility import PESAN_BLOKIR

    alasan_safety = await _source_batches_block_reason(db, decision)
    if alasan_safety is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"safety revalidation gagal: "
                f"{PESAN_BLOKIR.get(alasan_safety, alasan_safety)}"
                " — decision tidak dapat dieksekusi"
            ),
        )

    # Fase 4 butir 4: approval mengikat BUKTI, bukan hanya id keputusan.
    alasan_sidik = await _sidik_berubah(db, decision)
    if alasan_sidik is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"bukti berubah sejak disetujui ({alasan_sidik}) — "
                "ajukan ulang agar disetujui atas bukti yang sekarang"
            ),
        )

    # ── Gerbang 1: terbitkan PO DRAFT, belum mengirim apa pun ────────────────
    # Dokumen `02-approval-action.md` §6 (keputusan pemilik 28 Okt 2026):
    # "Disetujui" bukan keadaan akhir. Sebelum ini satu klik menyelesaikan
    # approval, penerbitan dokumen, DAN pengiriman ke SAP; akibatnya langkah
    # review PO tidak punya tempat, dan keadaan "menunggu review PO" tidak
    # pernah bisa terjadi. Sekarang eksekusi berhenti di dokumen `draft`;
    # pengiriman terjadi di gerbang 2 (endpoint review di bawah).
    sudah_ada = (await db.execute(_PO_KEPUTUSAN, {"d": decision.id})).mappings().first()
    if sudah_ada is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"purchase order {sudah_ada['po_number']} masih draft — "
                "menunggu review Kepala SPPG"
                if sudah_ada["status"] == "draft"
                else f"purchase order {sudah_ada['po_number']} sudah dikirim ke SAP"
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
    # Fase 5 butir 2/4: harga PO = harga INVOICE (bahan + transportasi +
    # penanganan), bukan `sdc / qty` — lihat `_harga_satuan_invoice`.
    unit_price = _harga_satuan_invoice(decision, qty)
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
            "price, decision_id, status, demo_session_id) "
            "VALUES (:po, :sup, :mat, :qty, :price, :dec, 'draft', :sesi)"
        ),
        {
            "po": po_number,
            "sup": supplier_id,
            "mat": _material_number_for(commodity),
            "qty": qty,
            "price": unit_price.quantize(Decimal("0.01")),
            "dec": decision.id,
            # Fase 2 MG: PO mewarisi sesi dari KEPUTUSANNYA, bukan dari "sesi
            # yang kebetulan aktif". `sap_mock_purchase_orders.decision_id`
            # ber-`ON DELETE SET NULL`, jadi tanpa kolom ini pemilik PO hilang
            # begitu keputusan induknya dihapus — dan reset per sesi tidak bisa
            # lagi membedakan PO milik sesi mana.
            "sesi": decision.demo_session_id,
        },
    )
    # Keputusan tetap `approved`: approval memang sudah cukup, tetapi komitmen
    # (PO terkirim, barang berangkat) belum terjadi. Menulis `executed` di sini
    # akan membuat layar mengklaim pembelian yang belum disetujui siapa pun.
    decision.status = "approved"
    # P1 Merkle ledger: penerbitan dokumen = blok append-only tersendiri.
    await append_block(
        db,
        action="po_draft",
        entity_id=decision.id,
        actor_id=user.id,
        payload={
            "decision_id": str(decision.id),
            "po_number": po_number,
            "quantity_kg": str(qty),
            "status": "draft",
            "awaiting": "po_review",
        },
    )
    await db.commit()
    return {
        "decision_id": str(decision.id),
        "po_number": po_number,
        "data_source": "MOCK",
        # `status` tetap berarti status KEPUTUSAN (kontrak lama), dan kini
        # nilainya `approved` — bukan `executed`.
        "status": decision.status,
        "decision_status": decision.status,
        "po_status": "draft",
        "awaiting": "po_review",
        "issued_by": str(user.id),
        "issued_at": _now_utc().isoformat(),
        # Belum ada barang yang berangkat di gerbang ini.
        "dikirim": [],
        "ditahan": [],
    }


@router.post("/actions/purchase-orders/{po_number}/approve", status_code=200)
async def review_purchase_order(
    po_number: str,
    user: User = Depends(require_roles(*PROPOSER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Gerbang 2 — Kepala SPPG mereview PO draft, lalu PO dikirim ke SAP mock.

    Hanya Kepala SPPG (`PROPOSER_ROLES`), hanya dari SPPG TUJUAN (Ruling
    2026-10-14 §3), hanya untuk PO yang masih `draft`. Semua pagar yang dulu
    diperiksa saat `/actions/execute` diperiksa ULANG di sini, karena di sinilah
    komitmen benar-benar terjadi: verifikasi, kedaluwarsa, kuorum approval,
    binding pemasok, safety batch sumber, dan sidik bukti sejak disetujui.
    """
    row = (
        await db.execute(
            text(
                "SELECT po_number, status, decision_id, price, material_number "
                "FROM sap_mock_purchase_orders WHERE po_number = :po FOR UPDATE"
            ),
            {"po": po_number},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="purchase order tidak ditemukan")
    if row["decision_id"] is None:
        raise HTTPException(
            status_code=409,
            detail="purchase order tanpa keputusan — tidak ada approval yang bisa direview",
        )
    if row["status"] != "draft":
        raise HTTPException(
            status_code=409,
            detail=(
                f"purchase order {po_number} berstatus {row['status']} — "
                "tidak ada review yang tertunda"
            ),
        )

    decision = await _load_decision(db, row["decision_id"])
    _require_decision_scope(user, decision)
    if decision.status == "review_only":
        raise HTTPException(
            status_code=409,
            detail="decision tinjauan (review-only) — tidak untuk dieksekusi",
        )
    if decision.status == "rejected":
        raise HTTPException(status_code=409, detail="decision ditolak")
    if not is_decision_valid(_now_utc(), decision.expires_at):
        raise HTTPException(status_code=409, detail="decision expired")
    if decision.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"status {decision.status} tidak dapat direview",
        )
    if _verifier_unverified(decision):
        raise HTTPException(status_code=409, detail="decision belum terverifikasi")
    evaluation, scoped = await _evaluasi_approval(db, decision)
    if not evaluation["satisfied"]:
        raise HTTPException(
            status_code=409,
            detail="approval belum memenuhi requirement (missing/rejected)",
        )
    if not scoped["satisfied"]:
        raise HTTPException(status_code=409, detail="approval scope tidak memenuhi requirement")

    from app.services.supplier_eligibility import PESAN_BLOKIR, revalidate_transfer

    supplier_id = await revalidate_transfer(db, decision)
    alasan_safety = await _source_batches_block_reason(db, decision)
    if alasan_safety is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "safety revalidation gagal: "
                f"{PESAN_BLOKIR.get(alasan_safety, alasan_safety)}"
                " — decision tidak dapat dieksekusi"
            ),
        )
    alasan_sidik = await _sidik_berubah(db, decision)
    if alasan_sidik is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"bukti berubah sejak disetujui ({alasan_sidik}) — "
                "ajukan ulang agar disetujui atas bukti yang sekarang"
            ),
        )

    harga = Decimal(str(row["price"] or 0))
    dikirim, ditahan = await _commit_purchase_order(
        db,
        decision,
        po_number,
        harga,
        supplier_id,
        str(row["material_number"] or ""),
        user,
    )
    await db.commit()
    return {
        "po_number": po_number,
        "po_status": "submitted",
        "decision_id": str(decision.id),
        "decision_status": decision.status,
        "data_source": "MOCK",
        "reviewed_by": str(user.id),
        "reviewed_at": _now_utc().isoformat(),
        "dikirim": dikirim,
        # Batch terikat yang TIDAK diberangkatkan karena gagal gerbang
        # keselamatan (kedaluwarsa/karantina/status belum pass/bukti suhu
        # kurang). Ditampilkan supaya UI tidak mengaku semua barang jalan.
        "ditahan": ditahan,
    }



def _material_number_for(commodity: Commodity) -> str:
    return f"MAT-{commodity.name.upper()}"


class ReproposeRequest(BaseModel):
    decision_id: uuid.UUID
    ttl_minutes: int = Field(default=30, ge=1, le=1440)


async def _salin_binding_induk(db: AsyncSession, parent: Decision, child: Decision) -> None:
    """Salin bukti `allocation_binding` induk ke iterasi baru, lewat validator.

    Penolakan manusia tidak mengubah batch/pemasok yang dipakai; tanpa salinan
    ini iterasi pengadaan kehilangan identitas alokasinya (temuan F6 audit
    27 Okt 2026). Bukti induk yang sudah tidak sah → tidak disalin, bukan
    dipaksakan: `persist_binding` yang memutuskan, dan kegagalan validasinya
    dibiarkan lewat supaya re-propose tidak mati hanya karena data lama busuk.
    """
    from app.services.supplier_eligibility import persist_binding

    evidence = (
        (
            await db.execute(
                select(DecisionEvidence).where(
                    DecisionEvidence.decision_id == parent.id,
                    DecisionEvidence.payload["allocation_binding"].astext == "true",
                )
            )
        )
        .scalars()
        .all()
    )
    if len(evidence) != 1:
        return
    payload = evidence[0].payload or {}
    try:
        await persist_binding(
            db,
            child,
            {
                "batch_ids": payload.get("batch_ids") or [],
                "supplier_id": payload.get("supplier_id"),
            },
        )
    except HTTPException:
        return


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
        # Pengadaan: pemasok adalah identitas keputusan (`supplier_id`), bukan
        # turunan lokasi. Dulu kolom ini tidak disalin, sehingga iterasi baru
        # dari pengadaan yang ditolak kehilangan pemasoknya dan eksekusinya
        # ditolak `409 supplier_unknown` (audit 27 Okt 2026, F6).
        supplier_id=parent.supplier_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.ttl_minutes),
        iteration=(parent.iteration or 1) + 1,
        supersedes_id=parent.id,
        demo_case=parent.demo_case,
    )
    db.add(child)
    await db.flush()
    # Binding induk disalin lewat validator yang sama dengan penulis produksi.
    # Kalau bukti induk sudah tidak sah (batch hilang/berpindah), binding TIDAK
    # ditulis: anak tetap bisa dieksekusi lewat jalur `supplier_id` + batch
    # pemasok di SPPG tujuan, dan layar menampilkan alasan sebenarnya.
    await _salin_binding_induk(db, parent, child)
    # Bahan LEARN (29 Okt 2026): langkah ini tidak hanya menyalin alasan induk,
    # tetapi MEMBACA riwayat penolakan lain di kota+komoditas yang sama. Tanpa
    # ini, "belajar dari penolakan" berarti agent hanya melihat satu penolakan
    # yang kebetulan sedang diproses — data penolakan lain ada di DB tapi tidak
    # pernah dibaca.
    from app.services.rejection_feedback import riwayat_penolakan

    riwayat = await riwayat_penolakan(
        db,
        target_location_id=parent.target_location_id,
        commodity_id=parent.commodity_id,
        kecuali_decision_id=parent.id,
    )
    db.add(
        AgentTrace(
            decision_id=child.id,
            step_name="LEARN",
            tool_called="rejection_loop.repropose",
            input_summary={
                "parent_decision_id": str(parent.id),
                "parent_iteration": parent.iteration or 1,
                "parent_status": parent.status,
                "riwayat_penolakan_dibaca": riwayat["jumlah"],
            },
            output_summary={
                "parent_rejection_reason": parent.rejection_reason,
                "learning_note": (
                    "Iterasi baru menyertakan penyesuaian atas penolakan: "
                    + (parent.rejection_reason or "")
                ),
                "riwayat_penolakan": riwayat,
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


# ---------------------------------------------------------------------------
# Fase 6 butir 3 & 5 — penerimaan manusia atas bukti batch
# ---------------------------------------------------------------------------


class TemperatureSampleIn(BaseModel):
    """Satu sampel suhu yang dibawa reviewer (bukan dihitung ulang di sini)."""

    model_config = pydantic.ConfigDict(extra="forbid")

    timestamp: datetime
    temperature_c: float


class ReviewRequest(BaseModel):
    """Review manusia: alasan + bukti wajib; identitas & waktu TIDAK dari klien.

    `extra="forbid"` bukan gaya penulisan: tanpa itu klien bisa mengirim
    `reviewed_by`/`reviewed_at` dan payload akan tampak seperti review orang
    lain pada waktu lain. Yang mencatat keduanya hanya server.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    batch_id: uuid.UUID
    #: Alasan wajib dan cukup panjang: "aman" bukan alasan yang dapat ditinjau.
    reason: str = Field(min_length=10, max_length=2000)
    #: Rujukan bukti (nomor berita acara, id inspeksi, dsb.) — minimal satu.
    evidence_refs: list[str] = Field(min_length=1, max_length=20)
    #: Sampel suhu yang ditambahkan reviewer; kosong = tidak ada bukti baru.
    temperature_samples: list[TemperatureSampleIn] = Field(default_factory=list)

    @pydantic.field_validator("evidence_refs")
    @classmethod
    def _refs_tidak_kosong(cls, nilai: list[str]) -> list[str]:
        bersih = [str(v).strip() for v in nilai]
        if any(not v for v in bersih):
            raise ValueError("evidence_refs tidak boleh berisi teks kosong")
        return bersih


@router.post("/decisions/{decision_id}/review", status_code=200)
async def review_decision(
    decision_id: uuid.UUID,
    payload: ReviewRequest,
    user: User = Depends(require_roles(*VERIFIER_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Tinjau bukti batch terikat; status hanya berubah bila bukti mencukupi.

    Endpoint ini TIDAK menerima verdict. Ia menambahkan bukti (sampel suhu),
    lalu `core.safety.evaluate_safety` menghitung ulang status terhadap profil
    komoditas. `fail` tidak dapat dibalik, `pass` tidak perlu ditinjau, dan
    review tanpa bukti baru menghasilkan `status_changed=false` beserta alasan.
    """
    from app.services.human_review import review_batch

    decision = await _load_decision(db, decision_id)
    _require_decision_scope(user, decision)
    return await review_batch(db, decision, payload, user)
