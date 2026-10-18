"""Endpoint karantina batch (POST /batches/{id}/quarantine).

Kewenangan manusia, bukan agent: menahan batch mengeluarkannya dari kandidat
alokasi sampai seseorang melepas atau menyatakannya gagal. Peran yang sah
adalah SPPG pemilik lokasi batch; `bgn_monitor` read-only.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.models.users import User
from app.services.quarantine_service import ubah_karantina

router = APIRouter(prefix="", tags=["quarantine"])


class KarantinaRequest(BaseModel):
    aksi: Literal["tahan", "lepas", "gagal"]
    alasan: str

    @field_validator("alasan")
    @classmethod
    def _alasan_berisi(cls, nilai: str) -> str:
        if not nilai.strip():
            raise ValueError("alasan wajib diisi")
        return nilai.strip()


@router.post("/batches/{batch_id}/quarantine")
async def ubah_status_karantina(
    batch_id: uuid.UUID,
    payload: KarantinaRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """201 saat batch baru ditahan, 200 saat dilepas/dinyatakan gagal."""
    hasil = await ubah_karantina(
        db, user, batch_id, payload.aksi, payload.alasan
    )
    response.status_code = 201 if payload.aksi == "tahan" else 200
    return hasil
