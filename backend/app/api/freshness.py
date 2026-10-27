"""Router freshness (Task 12) — tipis: validasi, ambil batch, panggil core, persist.

Fase 3 MG (27 Okt 2026): endpoint ini berhenti memakai peta Python sendiri
(`_SHELF_LIFE_BY_COMMODITY` dari `settings`) dan membaca PROFIL KOMODITAS
berversi (`commodity_policies`) lewat `core/policy_store.py`. Responsnya kini
membawa bukti suhu yang dipakai — `temperature_observation`, `evidence_state`,
`source`, `observed_at` — supaya pemanggil bisa melihat MENGAPA statusnya
begitu, bukan hanya angkanya.

Dua hal yang TIDAK berubah: `as_of` tetap hanya boleh di-override dalam
`DEMO_MODE`, dan skor tetap disimpan ke `batches.freshness_score`.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, require_roles
from app.api.dependencies import get_db
from app.core.config import settings
from app.core.freshness import classify_freshness, evaluate_freshness
from app.core.policy_store import profil_untuk_komoditas
from app.models import Batch, User

router = APIRouter()


class FreshnessRequest(BaseModel):
    # UUID, bukan str: id yang tidak valid harus ditolak 422 oleh Pydantic.
    # Sebelumnya string mentah diteruskan ke asyncpg dan endpoint membalas 500
    # (terukur: batch_id '' -> DataError 'invalid UUID').
    batch_id: UUID
    as_of: datetime | None = None


@router.post("/freshness/evaluate")
async def evaluate_freshness_endpoint(
    payload: FreshnessRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    batch = (
        await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")

    # as_of hanya boleh di-override dalam DEMO_MODE (plan Task 12)
    if payload.as_of is not None and not settings.demo_mode:
        raise HTTPException(
            status_code=403,
            detail="as_of hanya boleh di-override dalam DEMO_MODE",
        )
    as_of = payload.as_of or datetime.now(batch.harvested_at.tzinfo)

    # Profil komoditas dibaca dari `commodity_policies` (fallback bawaan kode
    # bila DB pra-migrasi 041 — lihat `policy_store`).
    try:
        policy, asal_profil = await profil_untuk_komoditas(db, batch.commodity_id)
    except KeyError as galat:
        # Komoditas tanpa profil TIDAK dinilai dengan rentang karangan: itulah
        # bug yang Fase 3 tutup (bawaan 0-8 °C untuk semua komoditas).
        raise HTTPException(status_code=422, detail=str(galat)) from galat

    hasil = evaluate_freshness(
        harvested_at=batch.harvested_at,
        as_of=as_of,
        policy=policy,
        temperature_log=batch.temperature_log or [],
    )

    batch.freshness_score = Decimal(str(round(hasil.score, 2)))
    batch.usable_until = hasil.usable_until
    await db.commit()

    return {
        "freshness_score": float(round(hasil.score, 2)),
        "status": hasil.status,
        "usable_until": hasil.usable_until.isoformat(),
        # ── bukti yang dipakai (Fase 3, butir 4 & 5) ──────────────────────
        "commodity_profile": policy.to_dict(),
        "profile_source": asal_profil,
        "temperature_observation": hasil.temperature_observation,
        "evidence_state": hasil.evidence_state,
        "sample_count": hasil.observation.sample_count,
        "observed_at": (
            hasil.observation.last_sample_at.isoformat()
            if hasil.observation.last_sample_at
            else None
        ),
        "evidence_reasons": list(hasil.observation.issues),
        # Klasifikasi murni atas skor tetap dikirim untuk konsumen lama, tetapi
        # `status` di atas sudah memperhitungkan kecukupan bukti.
        "status_skor_saja": classify_freshness(hasil.score),
    }
