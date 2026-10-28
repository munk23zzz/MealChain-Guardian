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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.model_registry import get_agent_chain
from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models import Decision, User
from app.services.ledger_service import verify_chain

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
        rows = (
            await db.execute(
                select(Decision.status, func.count())
                .where(
                    Decision.status.in_(
                        ["pending_approval", "approved", "executed", "rejected"]
                    )
                )
                .group_by(Decision.status)
            )
        ).all()
        hitung = {status: jumlah for status, jumlah in rows}
        return {
            "mode": "deterministic",
            "tool": "GET /decisions (agregasi status)",
            "writes": False,
            "answer": (
                "Keputusan per status: "
                + ", ".join(f"{k} {v}" for k, v in sorted(hitung.items()))
                + "."
                if hitung
                else "Belum ada keputusan tercatat."
            ),
            "data": hitung,
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
