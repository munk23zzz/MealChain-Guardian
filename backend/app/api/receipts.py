"""Router catatan penerimaan barang (migrasi 016).

Perannya jelas: petugas dapur mencatat apa yang benar-benar ia periksa saat
barang datang — termasuk keadaan yang tidak ada di daftar periksa ("Lainnya").
Yang disimpan apa adanya, tanpa ditafsirkan: backend tidak mengubah status
keamanan/kesegaran dari catatan ini (itu tugas `/safety/evaluate` dan
`/freshness/evaluate` yang membaca data terukur).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MUTATING_ROLES, get_current_user, require_roles
from app.api.dependencies import get_db
from app.core.scope import assert_in_scope
from app.models import Batch, BatchReceipt, User

router = APIRouter()

#: Batas kewarasan untuk snapshot yang dikirim klien (id titik periksa hidup di
#: lapisan UI; backend menyimpannya apa adanya tetapi tidak mau menerima apa pun
#: tanpa batas).
MAX_CHECKED_KEYS = 20
MAX_KEY_LENGTH = 40
NOTE_MAX = 500


class ReceiptRequest(BaseModel):
    batch_id: uuid.UUID
    #: Snapshot titik periksa: {"kemasan": true, "suhu": false, ...}.
    checked: dict[str, bool] = Field(default_factory=dict)
    #: Isian "Lainnya" — keadaan yang tidak ada di daftar periksa.
    other_note: str | None = Field(default=None, max_length=NOTE_MAX)

    @field_validator("checked")
    @classmethod
    def _batas_kewarasan(cls, nilai: dict[str, bool]) -> dict[str, bool]:
        if len(nilai) > MAX_CHECKED_KEYS:
            raise ValueError(f"terlalu banyak titik periksa (maks {MAX_CHECKED_KEYS})")
        if any(len(kunci) > MAX_KEY_LENGTH for kunci in nilai):
            raise ValueError(f"nama titik periksa terlalu panjang (maks {MAX_KEY_LENGTH})")
        if any(not kunci.strip() for kunci in nilai):
            raise ValueError("nama titik periksa tidak boleh kosong")
        return nilai


def _row(receipt: BatchReceipt, nama: str | None = None) -> dict:
    """Bentuk balasan yang stabil untuk UI (jumlah titik dihitung SERVER)."""
    dicek = receipt.checked or {}
    return {
        "id": str(receipt.id),
        "batch_id": str(receipt.batch_id),
        "checked": {str(k): bool(v) for k, v in dicek.items()},
        "checked_count": sum(1 for nilai in dicek.values() if nilai is True),
        "other_note": receipt.other_note,
        "recorded_by": str(receipt.recorded_by),
        "recorded_by_name": nama,
        "recorded_at": receipt.recorded_at.isoformat(),
    }


@router.post("/receipts", status_code=201)
async def create_receipt(
    payload: ReceiptRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    """Catat satu penerimaan barang. 201 = tersimpan; 404 = batch tidak ada.

    Scope: barang hanya bisa diterima di dapur sendiri (ruling 2026-10-14) —
    peran SPPG yang mencoba mencatat batch milik lokasi lain dibalas 403.
    """
    batch = (
        await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    ).scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="batch tidak ditemukan")

    assert_in_scope(user, batch.location_id, what="lokasi batch")

    # Catatan kosong/spasi = tidak ada catatan (NULL), bukan string kosong —
    # UI harus bisa membedakan "tidak menulis apa-apa" dari "menulis spasi".
    catatan = (payload.other_note or "").strip()

    receipt = BatchReceipt(
        batch_id=batch.id,
        checked=dict(payload.checked),
        other_note=catatan or None,
        recorded_by=user.id,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return _row(receipt, nama=user.name)


@router.get("/receipts")
async def list_receipts(
    batch_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Riwayat catatan penerimaan sebuah batch, terbaru dulu.

    Tidak dibatasi lokasi (pengawas nasional perlu bisa membacanya), tetapi
    hanya untuk batch yang diminta — bukan papan catatan seluruh jaringan.
    """
    baris = (
        await db.execute(
            select(BatchReceipt, User.name)
            .join(User, User.id == BatchReceipt.recorded_by)
            .where(BatchReceipt.batch_id == batch_id)
            .order_by(BatchReceipt.recorded_at.desc(), BatchReceipt.id.desc())
            .limit(limit)
        )
    ).all()
    return {"items": [_row(receipt, nama=nama) for receipt, nama in baris]}
