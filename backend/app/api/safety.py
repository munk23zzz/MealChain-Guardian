"""Router safety (Task 12) — status API uppercase, DB lowercase, tanpa override.

Fase 3 MG (27 Okt 2026): endpoint ini membaca PROFIL KOMODITAS ber-versi
(`commodity_policies`) dan memakai parser bukti yang sama dengan freshness
(`core/temperature.parse_temperature_log`). Komoditas ambient (beras) tidak lagi
diukur terhadap rentang dingin — profilnya memang tidak punya rentang.

Respons membawa bukti yang dipakai (`temperature_observation`, `evidence_state`,
`observed_at`) sehingga verdict bisa ditelusuri, bukan hanya dipercaya.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, require_roles
from app.api.dependencies import get_db
from app.core.policy_store import profil_untuk_komoditas
from app.core.safety import evaluate_safety
from app.models import Batch, Commodity, User

router = APIRouter()


class SafetyRequest(BaseModel):
    # UUID, bukan str: id yang tidak valid harus ditolak 422 oleh Pydantic.
    # Sebelumnya string mentah diteruskan ke asyncpg dan endpoint membalas 500
    # (terukur: batch_id '' -> DataError 'invalid UUID').
    batch_id: UUID
    #: Waktu EVALUASI (bukan jam dinding). Kosong = waktu sampel terakhir di log,
    #: sehingga log historis tidak otomatis disebut "stale" hanya karena hari ini
    #: bukan hari kejadian.
    evaluation_time: datetime | None = None


#: Toleransi jam untuk `evaluation_time` (selisih clock antar layanan).
_SKEW_DETIK = 300


def validasi_waktu_evaluasi(nilai: datetime | None, sekarang: datetime | None = None) -> None:
    """Tolak `evaluation_time` yang tidak bisa dipertanggungjawabkan.

    Audit 2026-10-29 (AUD-008). `None` SENGAJA dipertahankan: ia berarti "nilai
    pada sampel terakhir", sehingga log historis tidak otomatis disebut stale
    (perilaku terdokumentasi di `core/safety.py`). Yang tidak boleh: pemanggil
    menggeser jam ke DEPAN — itu membuat observasi tua tampak segar dan
    melumpuhkan gerbang staleness tanpa mengubah data apa pun.
    """
    if nilai is None:
        return
    if nilai.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="evaluation_time wajib menyertakan offset zona waktu (RFC3339)",
        )
    acuan = sekarang or datetime.now(timezone.utc)
    if nilai > acuan + timedelta(seconds=_SKEW_DETIK):
        raise HTTPException(
            status_code=422,
            detail="evaluation_time di masa depan tidak boleh dipakai menilai keselamatan",
        )


@router.post("/safety/evaluate")
async def evaluate_safety_endpoint(
    payload: SafetyRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    validasi_waktu_evaluasi(payload.evaluation_time)
    baris = (
        await db.execute(
            select(Batch, Commodity.name)
            .join(Commodity, Commodity.id == Batch.commodity_id)
            .where(Batch.id == payload.batch_id)
        )
    ).one_or_none()
    if baris is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")
    batch, _commodity_name = baris

    try:
        policy, asal_profil = await profil_untuk_komoditas(db, batch.commodity_id)
    except KeyError as galat:
        raise HTTPException(status_code=422, detail=str(galat)) from galat

    result = evaluate_safety(
        temperature_log=batch.temperature_log or [],
        policy=policy,
        evaluation_time=payload.evaluation_time,
    )

    # DB lowercase (kontrak Schema.md), API uppercase (kontrak Skill.md §5)
    batch.safety_status = str(result["safety_status"]).lower()
    await db.commit()

    last_sample = result["last_sample_at"]
    alasan = result["reasons"]
    return {
        "safety_status": str(result["safety_status"]).upper(),
        "reasons": [str(r) for r in alasan] if isinstance(alasan, list | tuple) else [],
        "excursion_minutes": float(result["excursion_minutes"]),
        # ── bukti yang dipakai (Fase 3, butir 4 & 5) ──────────────────────
        "commodity_profile": policy.to_dict(),
        "profile_source": asal_profil,
        "temperature_observation": result["temperature_observation"],
        "evidence_state": result["evidence_state"],
        "sample_count": result["sample_count"],
        "observed_at": (
            last_sample.isoformat() if isinstance(last_sample, datetime) else None
        ),
    }
