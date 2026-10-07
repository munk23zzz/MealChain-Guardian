"""Auth JWT (S3-01) — login DB-backed + proteksi endpoint.

Tiga role final (Schema.md): sppg_head | sppg_nutritionist | bgn_monitor.
bgn_monitor read-only. JWT HS256 dari .env (JWT_SECRET, JWT_ALGORITHM,
JWT_EXPIRE_MINUTES).
"""

import os
import time
from uuid import UUID

import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models import Location, User

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)

# Hash bcrypt dummy untuk timing konsisten saat email tidak dikenal.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode()


class LoginRequest(BaseModel):
    email: str
    password: str


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET belum diset")
    return secret


def _algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", "HS256")


def _expire_minutes() -> int:
    return int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))


def _issue_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "loc": str(user.location_id) if user.location_id else None,
        "iat": now,
        "exp": now + _expire_minutes() * 60,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_algorithm())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependensi auth: validasi Bearer token + user DB-backed."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="butuh Bearer token")
    try:
        claims = pyjwt.decode(
            credentials.credentials,
            _secret(),
            algorithms=[_algorithm()],
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="token tidak valid") from exc
    raw_sub = claims.get("sub")
    try:
        user_id = UUID(str(raw_sub))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail="token tidak valid") from exc
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="token tidak valid")
    return user


def require_roles(*allowed: str):
    """Guard RBAC: user harus punya salah satu role yang diizinkan."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="role tidak diizinkan")
        return user

    return _guard


# Role yang boleh melakukan mutasi/komputasi endpoint (bgn_monitor read-only
# per PRD §77). Dipakai guard endpoint legacy Sprint 1/2 (residual debt).
MUTATING_ROLES = ("sppg_head", "sppg_nutritionist")


@router.post("/auth/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(
            select(User).where(User.email == payload.email.lower().strip())
        )
    ).scalar_one_or_none()
    if user is None:
        # Timing konsisten untuk email tak dikenal.
        bcrypt.checkpw(payload.password.encode(), _DUMMY_HASH.encode())
        raise HTTPException(status_code=401, detail="email atau password salah")
    if not bcrypt.checkpw(payload.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="email atau password salah")
    return {
        "access_token": _issue_token(user),
        "token_type": "bearer",
        "role": user.role,
        "user_id": str(user.id),
        "expires_in": _expire_minutes() * 60,
    }


@router.get("/auth/me")
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    loc_name = None
    if user.location_id:
        loc = (
            await db.execute(
                select(Location).where(Location.id == user.location_id)
            )
        ).scalar_one_or_none()
        loc_name = loc.name if loc else None
    return {
        "user_id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "location_id": str(user.location_id) if user.location_id else None,
        "location_name": loc_name,
    }
