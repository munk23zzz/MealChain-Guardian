"""Router cost (S3-02) — SDC standalone endpoint (carry-over Sprint 2).

Tipis: validasi + delegasi penuh ke core.safe_delivered_cost (Opsi A
terkunci). FAIL ditolak sebelum perhitungan (422), tanpa eksepsi bocor.

Sejak konsep Performance & Audit (29 Okt 2026) permintaan boleh membawa
`commodity`, `shelf_life_days`, dan `storage_days` — susut gudang dihitung dari
LAMA SIMPAN, bukan dari kesegaran. Ketiganya opsional supaya kontrak lama tetap
sah: tanpa `storage_days`, mesin memakai asumsi siklus harian dan MENGATAKANNYA
di `storage_basis` (tidak pernah diam-diam nol).
"""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import MUTATING_ROLES, require_roles
from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)
from app.models import User

router = APIRouter()

_DUA_DESIMAL = Decimal("0.01")


def _dua_desimal(nilai: Decimal) -> Decimal:
    """Hari simpan/umur simpan dilaporkan 2 desimal (HALF_UP), seperti rupiah."""
    return Decimal(nilai).quantize(_DUA_DESIMAL, rounding=ROUND_HALF_UP)


class SafeDeliveredRequest(BaseModel):
    purchase_cost: Decimal
    transport_cost: Decimal = Decimal("0")
    handling_cost: Decimal = Decimal("0")
    freshness_score: Decimal = Field(ge=0, le=1)
    safety_status: str
    #: Nama komoditas (telur/ayam/wortel/beras) — sumber umur simpan.
    commodity: str | None = None
    #: Umur simpan komoditas (hari). Kosong → dari tabel profil komoditas.
    shelf_life_days: Decimal | None = Field(default=None, gt=0)
    #: Lama simpan di gudang SPPG (hari). Kosong → asumsi siklus harian.
    storage_days: Decimal | None = Field(default=None, ge=0)


@router.post("/cost/safe-delivered")
async def post_safe_delivered(
    payload: SafeDeliveredRequest,
    _user: User = Depends(require_roles(*MUTATING_ROLES)),
) -> dict:
    try:
        result = calculate_safe_delivered_cost(
            SafeDeliveredCostInputs(
                purchase_cost=payload.purchase_cost,
                transport_cost=payload.transport_cost,
                handling_cost=payload.handling_cost,
                freshness_score=payload.freshness_score,
                safety_status=payload.safety_status,
                commodity=payload.commodity,
                shelf_life_days=payload.shelf_life_days,
                storage_days=payload.storage_days,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "purchase_cost": str(result.purchase_cost),
        "transport_cost": str(result.transport_cost),
        "handling_cost": str(result.handling_cost),
        #: Susut gudang (fungsi waktu). `expected_loss` dipertahankan sebagai
        #: alias kontrak lama — angka yang sama, bukan rumus kedua.
        "loss_in_storage": str(result.loss_in_storage),
        "expected_loss": str(result.expected_loss),
        "freshness_risk_penalty": str(result.freshness_risk_penalty),
        "safety_risk_penalty": str(result.safety_risk_penalty),
        "total": str(result.total),
        #: Jejak hitung: umur simpan, hari simpan, asalnya, versi rumus.
        #: Dua desimal supaya klien bisa membandingkan sebagai teks tanpa
        #: kejutan bentuk ("7" vs "7.00") — sama seperti komponen rupiah.
        "shelf_life_days": str(_dua_desimal(result.shelf_life_days)),
        "storage_days": str(_dua_desimal(result.storage_days)),
        "storage_basis": result.storage_basis,
        #: Laju yang dipakai + asalnya: tabel komoditas atau cadangan 20%.
        "shrinkage_rate": str(result.shrinkage_rate),
        "shrinkage_rate_source": result.shrinkage_rate_source,
        "daily_shrinkage_rate": str(
            result.daily_shrinkage_rate.quantize(Decimal("0.000001"))
        ),
        "formula_version": result.formula_version,
    }
