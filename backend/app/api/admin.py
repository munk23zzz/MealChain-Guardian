"""Endpoint admin (S4-11): kelola pengguna & lokasi SPPG.

RBAC: hanya `bgn_monitor` — alasan lengkap di `app/core/admin_rules.py`.
Tidak ada endpoint DELETE: pengguna & lokasi dipakai keputusan/batch historis,
jadi menghapusnya akan merusak jejak. Perubahan TIDAK menyentuh keputusan lama
(approval merujuk `users.id`, lokasi dirujuk lewat id — bukan salinan nama).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_roles
from app.core.admin_rules import (
    UNSET,
    AdminRuleError,
    resolve_location_update,
    resolve_user_update,
)
from app.db import get_db
from app.models.locations import Location
from app.models.users import User
from app.services.ledger_service import append_block

router = APIRouter(prefix="/admin", tags=["admin"])


class UserUpdate(BaseModel):
    role: str | None = None
    location_id: uuid.UUID | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


def _user_out(user: User, location: Location | None) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "location_id": str(user.location_id) if user.location_id else None,
        "location_name": location.name if location is not None else None,
    }


def _location_out(loc: Location) -> dict:
    return {
        "id": str(loc.id),
        "name": loc.name,
        "region": loc.region,
        "latitude": float(loc.latitude),
        "longitude": float(loc.longitude),
        "role_hint": loc.role_hint,
    }


async def _ambil_user(db: AsyncSession, user_id: str) -> User:
    """Id tak dikenal ATAU bukan UUID → 404 (bukan 500 dari Postgres)."""
    try:
        kunci = uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="pengguna tidak ditemukan") from None
    user = await db.get(User, kunci)
    if user is None:
        raise HTTPException(status_code=404, detail="pengguna tidak ditemukan")
    return user


@router.get("/users")
async def list_users(
    _admin: User = Depends(require_roles("bgn_monitor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    baris = (
        await db.execute(
            select(User, Location)
            .outerjoin(Location, User.location_id == Location.id)
            .order_by(User.email.asc())
        )
    ).all()
    return {"users": [_user_out(u, lokasi) for u, lokasi in baris]}


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    _admin: User = Depends(require_roles("bgn_monitor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await _ambil_user(db, user_id)
    # Pagar tata kelola (keputusan owner 2026-10-17): bgn_monitor memegang
    # pengelolaan pengguna/lokasi, tetapi TIDAK boleh mengubah perannya sendiri
    # (mencegah eskalasi hak akses lewat akunnya sendiri).
    if payload.role is not None and user.id == _admin.id:
        raise HTTPException(status_code=422, detail="tidak boleh mengubah peran sendiri")
    kirim_lokasi = "location_id" in payload.model_fields_set
    lokasi_id = payload.location_id if kirim_lokasi else UNSET

    lokasi_ada: bool | None = None
    if kirim_lokasi and payload.location_id is not None:
        lokasi_ada = await db.get(Location, payload.location_id) is not None

    try:
        role, location_id = resolve_user_update(
            current_role=user.role,
            current_location_id=str(user.location_id) if user.location_id else None,
            role=payload.role,
            location_id=str(lokasi_id) if isinstance(lokasi_id, uuid.UUID) else lokasi_id,
            location_exists=lokasi_ada,
        )
    except AdminRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # AUTH-01 (audit 24 Okt 2026): `bgn_monitor` memegang pengelolaan
    # pengguna/lokasi karena skema tidak punya peran `admin`. Karena itu setiap
    # perubahan WAJIB meninggalkan jejak di ledger — perubahan hak akses tanpa
    # jejak tidak bisa diaudit setelah kejadian.
    role_lama = user.role
    lokasi_lama = user.location_id
    lokasi_baru = uuid.UUID(location_id) if location_id else None
    user.role = role
    user.location_id = lokasi_baru
    if (role, lokasi_baru) != (role_lama, lokasi_lama):
        await append_block(
            db,
            action="admin.user.update",
            entity_id=user.id,
            actor_id=_admin.id,
            payload={
                "user_id": str(user.id),
                "role_sebelum": role_lama,
                "role_sesudah": role,
                "lokasi_sebelum": str(lokasi_lama) if lokasi_lama else None,
                "lokasi_sesudah": str(lokasi_baru) if lokasi_baru else None,
            },
        )
    await db.commit()
    await db.refresh(user)
    lokasi = await db.get(Location, user.location_id) if user.location_id else None
    return {"user": _user_out(user, lokasi)}


@router.get("/locations")
async def list_locations(
    _admin: User = Depends(require_roles("bgn_monitor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    baris = (
        await db.execute(select(Location).order_by(Location.name.asc()))
    ).scalars().all()
    return {"locations": [_location_out(lokasi) for lokasi in baris]}


@router.patch("/locations/{location_id}")
async def update_location(
    location_id: str,
    payload: LocationUpdate,
    _admin: User = Depends(require_roles("bgn_monitor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        kunci = uuid.UUID(location_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="lokasi tidak ditemukan") from None
    lokasi = await db.get(Location, kunci)
    if lokasi is None:
        raise HTTPException(status_code=404, detail="lokasi tidak ditemukan")

    try:
        perubahan = resolve_location_update(
            name=payload.name,
            region=payload.region,
            latitude=payload.latitude,
            longitude=payload.longitude,
        )
    except AdminRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    nilai_lama = {kunci: getattr(lokasi, kunci) for kunci in perubahan}
    for kunci_field, nilai in perubahan.items():
        setattr(lokasi, kunci_field, nilai)
    await append_block(
        db,
        action="admin.location.update",
        entity_id=lokasi.id,
        actor_id=_admin.id,
        payload={
            "location_id": str(lokasi.id),
            "perubahan": {
                kunci: {
                    "sebelum": str(nilai_lama[kunci]),
                    "sesudah": str(nilai),
                }
                for kunci, nilai in perubahan.items()
            },
        },
    )
    try:
        await db.commit()
    except IntegrityError as exc:  # nama lokasi UNIQUE
        await db.rollback()
        raise HTTPException(
            status_code=422, detail="nama lokasi sudah dipakai"
        ) from exc
    await db.refresh(lokasi)
    return {"location": _location_out(lokasi)}
