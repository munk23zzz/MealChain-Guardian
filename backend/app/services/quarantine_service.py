"""Karantina batch — aksi manusia atas batch yang ditahan dari alokasi.

Kewenangan: peran SPPG pemilik lokasi batch (`sppg_head`/`sppg_nutritionist`).
`bgn_monitor` read-only secara desain, jadi tidak boleh menahan/melepas. Agent
tidak pernah memanggil modul ini — ia hanya mengusulkan lewat temuannya.

Setiap transisi menulis satu blok evidence ledger supaya pertanyaan "siapa
menahan batch ini dan kapan" punya jawaban yang bisa diverifikasi.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.quarantine import (
    AKSI_GAGAL,
    AKSI_TAHAN,
    QUARANTINED,
    boleh_ditahan,
    status_setelah,
)
from app.models import Batch
from app.models.users import User
from app.services.ledger_service import append_block

SPPG_ROLES = frozenset({"sppg_head", "sppg_nutritionist"})
_AKSI_LEDGER = {
    AKSI_TAHAN: "batch_quarantine",
    "lepas": "batch_quarantine_release",
    AKSI_GAGAL: "batch_quarantine_fail",
}


def _pastikan_berwenang(user: User, batch: Batch) -> None:
    if user.role not in SPPG_ROLES:
        raise HTTPException(
            403,
            "hanya SPPG pemilik lokasi batch yang boleh menahan atau melepas batch",
        )
    if not user.location_id or user.location_id != batch.location_id:
        raise HTTPException(403, "cakupan lokasi di luar SPPG Anda")


async def ubah_karantina(
    db: AsyncSession,
    user: User,
    batch_id: uuid.UUID,
    aksi: str,
    alasan: str,
) -> dict:
    """Terapkan satu transisi karantina; ValueError → 409, bukan tebakan."""
    batch = (
        await db.execute(select(Batch).where(Batch.id == batch_id).with_for_update())
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(404, "batch tidak ditemukan")

    _pastikan_berwenang(user, batch)

    if aksi == AKSI_TAHAN:
        boleh, sebab = boleh_ditahan(batch.safety_status)
        if not boleh:
            raise HTTPException(409, sebab)

    try:
        status_baru = status_setelah(batch.quarantine_status, aksi)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    sekarang = datetime.now(timezone.utc)
    sebelumnya = batch.quarantine_status
    batch.quarantine_status = status_baru
    batch.quarantine_reason = alasan.strip()
    batch.quarantine_updated_at = sekarang
    batch.quarantine_actor_id = user.id
    if status_baru == QUARANTINED:
        batch.quarantined_at = sekarang
    else:
        # `quarantined_at` hanya berarti "sedang ditahan sejak kapan". Riwayat
        # kapan batch pernah ditahan tetap ada di blok ledger, bukan di baris
        # batch yang statusnya sudah berubah.
        batch.quarantined_at = None

    blok = await append_block(
        db,
        action=_AKSI_LEDGER[aksi],
        entity_id=batch.id,
        actor_id=user.id,
        payload={
            "batch_id": str(batch.id),
            "aksi": aksi,
            "status_sebelum": sebelumnya,
            "status_sesudah": status_baru,
            "alasan": batch.quarantine_reason,
            "safety_status": batch.safety_status,
            "oleh": user.email,
            "waktu": sekarang.isoformat(),
        },
    )
    await db.commit()

    return {
        "batch_id": str(batch.id),
        "quarantine_status": batch.quarantine_status,
        "quarantine_reason": batch.quarantine_reason,
        "quarantined_at": (
            batch.quarantined_at.isoformat() if batch.quarantined_at else None
        ),
        "quarantine_updated_at": sekarang.isoformat(),
        "safety_status": batch.safety_status,
        "ledger_height": blok["height"],
        "ledger_hash": blok["payload_hash"],
    }
