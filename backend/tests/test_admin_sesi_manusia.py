"""Token layanan agen tidak boleh mengelola pengguna (audit 2026-10-29, AUD-006).

Token layanan (`MEALCHAIN_API_TOKEN`) adalah JWT milik akun berperan
`bgn_monitor`; dari sisi RBAC ia identik dengan operator manusia. Guard
`require_sesi_manusia` menuntut klaim `typ="user"` yang hanya diterbitkan login.
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.api.auth import _algorithm, _issue_token, _secret
from app.main import app
from app.models import User
from tests.dsn import DSN_SYNC


def _admin_db() -> User:
    engine = create_engine(DSN_SYNC)
    with engine.begin() as conn:
        baris = (
            conn.execute(
                text(
                    "SELECT id, name, email, password_hash, role, location_id "
                    "FROM users WHERE role = 'bgn_monitor' LIMIT 1"
                )
            )
            .mappings()
            .first()
        )
    if baris is None:
        pytest.skip("tidak ada akun bgn_monitor pada database uji")
    return User(**dict(baris))


def _token_layanan(user: User) -> str:
    """JWT gaya token layanan: sah, berperan admin, TANPA klaim `typ`."""
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "loc": str(user.location_id) if user.location_id else None,
            "iat": now,
            "exp": now + 3600,
        },
        _secret(),
        algorithm=_algorithm(),
    )


def _get(path: str, token: str):
    with TestClient(app) as client:
        return client.get(path, headers={"Authorization": f"Bearer {token}"})


def test_token_layanan_tanpa_klaim_typ_ditolak_403():
    user = _admin_db()

    respons = _get("/admin/users", _token_layanan(user))

    assert respons.status_code == 403, respons.text
    assert "token layanan" in respons.json()["detail"]


def test_sesi_login_boleh_mengakses_admin():
    user = _admin_db()

    respons = _get("/admin/users", _issue_token(user))

    assert respons.status_code == 200, respons.text
