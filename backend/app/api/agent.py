"""Agent supervisor: status + tanya-jawab baca-saja (dokumen `06-agent-log.md`).

Dua endpoint sempit, tanpa mutasi:

- `GET /agent/supervisor/health` — apakah rantai model supervisor terkonfigurasi.
  Ini TIDAK ditempel ke status trace keputusan: satu keputusan bisa punya trace
  lengkap sementara supervisor tidak dikonfigurasi, dan itu dua fakta berbeda.

- `POST /agent/supervisor/ask` — pertanyaan dijawab dengan **tool GET**
  (hitungan keputusan, verifikasi ledger, rantai model). Tidak menulis
  keputusan, trace, atau blok ledger apa pun. Jawaban selalu menyebut tool
  yang dipakai dan `writes: false`, supaya pembaca tidak menyangka ada aksi.

Catatan kejujuran: di build ini belum ada klien model supervisor (hanya
verifier + forecast), jadi jawaban diberi label `mode = "deterministic"`.
Kalau nanti klien supervisor ada, jangan diam-diam mengubah label ini tanpa
menambah tes yang membuktikan provider benar-benar menjawab.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.model_registry import get_agent_chain
from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.scope import apply_location_scope
from app.models import (
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    Location,
    User,
)
from app.services.ledger_service import verify_chain
from app.services.supervisor_answers import ringkas_keputusan_per_status

router = APIRouter(prefix="/agent", tags=["agent"])

# Pertanyaan yang memang bisa dijawab dari data tercatat. Di luar daftar ini,
# supervisor deterministik menjawab "tidak tercatat" — bukan menebak.
CONTOH_PERTANYAAN = [
    "Berapa keputusan yang menunggu persetujuan?",
    "Bagaimana status rantai ledger?",
    "Apa keputusan terbaru?",
    "Model supervisor apa yang terkonfigurasi?",
]


@router.get("/supervisor/health")
async def supervisor_health(user: User = Depends(get_current_user)) -> dict:
    """Status konfigurasi supervisor — tanpa panggilan jaringan ke provider.

    `live` sengaja `null`, bukan `true`: tidak ada probe provider di jalur ini,
    jadi menulis "hidup" akan menjadi klaim tanpa bukti. UI memetakan
    `unconfigured` → peringatan, `configured` → netral.
    """
    chain = get_agent_chain("supervisor")
    slots = [r.model_id or r.agentcore_arn for r in chain if r]
    status = "configured" if slots else "unconfigured"
    return {
        "status": status,
        "live": None,
        "checked": "config_only",
        "slots": len(slots),
        "model": slots[0] if slots else None,
        "detail": (
            "Rantai model supervisor terkonfigurasi, tetapi jalur ini tidak "
            "memanggil provider sehingga belum ada bukti hidup."
            if slots
            else "Belum ada model supervisor di env; jawaban agent memakai tool deterministik."
        ),
    }


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=400)


def _normalisasi(teks: str) -> str:
    return " ".join(teks.lower().split())


@router.post("/supervisor/ask")
async def supervisor_ask(
    body: AskBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Jawab satu pertanyaan dari data yang tercatat. Read-only, selalu."""
    tanya = _normalisasi(body.question)
    if not tanya:
        raise HTTPException(status_code=422, detail="pertanyaan kosong")

    if any(k in tanya for k in ("ledger", "integritas", "rantai", "hash")):
        hasil = await verify_chain(db)
        return {
            "mode": "deterministic",
            "tool": "GET /ledger/verify",
            "writes": False,
            "answer": (
                f"Rantai ledger {'valid' if hasil.get('valid') else 'TIDAK valid'}"
                f" pada {hasil.get('blocks', 0)} blok"
                + (
                    f", putus di blok {hasil.get('broken_at')}."
                    if hasil.get("broken_at")
                    else "."
                )
            ),
            "data": {"valid": hasil.get("valid"), "blocks": hasil.get("blocks")},
        }

    if any(k in tanya for k in ("model", "provider", "supervisor apa")):
        chain = get_agent_chain("supervisor")
        slots = [r.model_id or r.agentcore_arn for r in chain if r]
        return {
            "mode": "deterministic",
            "tool": "model_registry.get_agent_chain('supervisor')",
            "writes": False,
            "answer": (
                f"{len(slots)} slot model supervisor terkonfigurasi"
                + (f": {', '.join(slots[:3])}." if slots else " (belum ada).")
            ),
            "data": {"slots": slots},
        }

    if any(k in tanya for k in ("terbaru", "terakhir", "latest")):
        row = (
            await db.execute(select(Decision).order_by(Decision.created_at.desc()).limit(1))
        ).scalar_one_or_none()
        if row is None:
            return {
                "mode": "deterministic",
                "tool": "GET /decisions?limit=1",
                "writes": False,
                "answer": "Belum ada keputusan tercatat.",
                "data": None,
            }
        return {
            "mode": "deterministic",
            "tool": "GET /decisions?limit=1",
            "writes": False,
            "answer": (
                f"Keputusan terbaru: {row.decision_type} dengan status {row.status} "
                f"(id {str(row.id)[:8]})."
            ),
            "data": {
                "decision_id": str(row.id),
                "decision_type": row.decision_type,
                "status": row.status,
            },
        }

    if any(k in tanya for k in ("menunggu", "pending", "persetujuan", "approval")):
        # Semua status dihitung (audit 29 Okt 2026): versi sebelumnya menyaring
        # empat status saja, sehingga "Keputusan per status" menjumlah ke 43 dari
        # total 49 dan pembaca menyimpulkan sistemnya salah hitung.
        rows = (
            await db.execute(select(Decision.status, func.count()).group_by(Decision.status))
        ).all()
        ringkas = ringkas_keputusan_per_status({status: jumlah for status, jumlah in rows})
        return {
            "mode": "deterministic",
            "tool": "GET /decisions (agregasi status)",
            "writes": False,
            "answer": ringkas["answer"],
            "data": ringkas["data"]["per_status"],
        }

    return {
        "mode": "deterministic",
        "tool": "tidak ada (pertanyaan di luar cakupan tool GET)",
        "writes": False,
        "answer": (
            "Pertanyaan ini tidak bisa dijawab dari data yang tercatat di build ini. "
            "Yang bisa ditanyakan: " + " · ".join(CONTOH_PERTANYAAN)
        ),
        "data": None,
    }


@router.get("/feedback/rejections")
async def feedback_rejections(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Jumlah baris terbaru per jenis (keputusan, penerimaan).",
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Riwayat PENOLAKAN yang boleh dibaca langkah LEARN agent (baca-saja).

    Kenapa ada (29 Okt 2026): data demo memuat kasus ditolak — penerimaan ayam
    300 kg yang ditolak saat serah terima dan 10 keputusan `rejected` di tiga
    kota — tetapi tidak ada satu pun jalan baca untuk agent. Gateway tool agent
    hanya punya tool pasokan/harga/rute/pengajuan, jadi LEARN hanya bisa
    mencatat penolakan yang kebetulan sedang diproses, bukan membaca pola yang
    sudah ada.

    Endpoint ini TIDAK menulis apa pun (`writes: false`) dan memakai cakupan
    lokasi yang sama dengan feed keputusan: peran SPPG melihat kotanya sendiri,
    `bgn_monitor` melihat nasional. `sumber` disebut apa adanya supaya pembaca
    bisa memeriksa sendiri tabel yang dibaca.
    """
    komoditas: dict = {}
    for cid, nama in (await db.execute(select(Commodity.id, Commodity.name))).all():
        komoditas[cid] = nama
    lokasi: dict = {}
    for lid, nama in (await db.execute(select(Location.id, Location.name))).all():
        lokasi[lid] = nama

    stmt_keputusan = (
        select(Decision)
        .where(Decision.status == "rejected")
        .order_by(Decision.created_at.desc(), Decision.id.desc())
        .limit(limit)
    )
    stmt_keputusan = apply_location_scope(
        stmt_keputusan, Decision.target_location_id, user
    )
    keputusan = [
        {
            "decision_id": str(row.id),
            "decision_type": row.decision_type,
            "status": row.status,
            "iteration": row.iteration or 1,
            "rejection_reason": row.rejection_reason,
            "komoditas": komoditas.get(row.commodity_id),
            "lokasi_tujuan": lokasi.get(row.target_location_id),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
        for row in (await db.scalars(stmt_keputusan)).all()
    ]

    stmt_penerimaan = (
        select(BatchReceipt, Batch)
        .join(Batch, Batch.id == BatchReceipt.batch_id)
        .where(BatchReceipt.status == "ditolak")
        .order_by(
            BatchReceipt.reviewed_at.desc().nullslast(), BatchReceipt.id.desc()
        )
        .limit(limit)
    )
    stmt_penerimaan = apply_location_scope(stmt_penerimaan, Batch.location_id, user)
    penerimaan = []
    for catatan, batch in (await db.execute(stmt_penerimaan)).all():
        penerimaan.append(
            {
                "receipt_id": str(catatan.id),
                "batch_id": str(batch.id),
                "status": catatan.status,
                "komoditas": komoditas.get(batch.commodity_id),
                "lokasi": lokasi.get(batch.location_id),
                "ordered_kg": (
                    float(catatan.ordered_kg) if catatan.ordered_kg is not None else None
                ),
                "accepted_kg": (
                    float(catatan.accepted_kg) if catatan.accepted_kg is not None else None
                ),
                # Ditolak = tidak masuk stok: kolom "diterima" sengaja kosong.
                "received_kg": None,
                "review_note": catatan.review_note,
                "reviewed_at": (
                    catatan.reviewed_at.isoformat() if catatan.reviewed_at else None
                ),
            }
        )

    cakupan_lokasi = getattr(user, "location_id", None)
    return {
        "writes": False,
        "sumber": ["decisions(status='rejected')", "batch_receipts(status='ditolak')"],
        "cakupan": lokasi.get(cakupan_lokasi) or "nasional",
        "dihitung_pada": datetime.now(timezone.utc).isoformat(),
        "jumlah": {"keputusan": len(keputusan), "penerimaan": len(penerimaan)},
        "keputusan": keputusan,
        "penerimaan": penerimaan,
    }
