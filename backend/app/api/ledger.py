"""Endpoint Merkle ledger (P1) — read-only, semua role terautentikasi."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db import get_db
from app.models.users import User
from app.services.ledger_service import verify_chain

router = APIRouter(prefix="", tags=["ledger"])


@router.get("/ledger/verify")
async def ledger_verify(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Verifikasi rantai Merkle dari genesis (jujur: valid/broken_at)."""
    return await verify_chain(db)
