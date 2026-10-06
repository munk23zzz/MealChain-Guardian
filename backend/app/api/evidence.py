"""Router evidence (S3-02) — /evidence/fuse (carry-over Sprint 2).

Perakitan evidence deterministik dari snapshot rekomendasi: pass-through
tanpa kalkulasi baru (anti-LLM, anti-formula-duplikat). Struktur keluaran
dipakai Supervisor/verifier sebagai bukti audit.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class FuseRequest(BaseModel):
    recommendation: dict


@router.post("/evidence/fuse")
async def fuse_evidence(payload: FuseRequest) -> dict:
    rec = payload.recommendation or {}
    candidate = rec.get("candidate") or {}
    evidence = rec.get("evidence") or {}
    if not candidate or not evidence:
        raise HTTPException(
            status_code=422,
            detail="recommendation wajib berisi candidate + evidence",
        )
    batch_ids = sorted({str(b) for b in evidence.get("batch_ids", []) if b})
    price_sources = list(evidence.get("price_sources", []))
    if not batch_ids and not price_sources:
        raise HTTPException(
            status_code=422, detail="evidence kosong: tidak ada batch/price source"
        )
    return {
        "candidate": {
            "source_location": candidate.get("source_location"),
            "destination_location": candidate.get("destination_location"),
            "commodity": candidate.get("commodity"),
            "quantity_kg": candidate.get("quantity_kg"),
        },
        "batch_ids": batch_ids,
        "price_sources": price_sources,
        "price_anomaly": rec.get("price_anomaly"),
        "cost_breakdown": rec.get("cost_breakdown"),
        "safe_delivered_cost": rec.get("safe_delivered_cost"),
        "source_count": len(batch_ids) + len(price_sources),
    }
