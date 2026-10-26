"""S2: rebuild template wajib berada di dalam sesi demo aktif."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api import demo_session as router
from app.core.config import settings


class _DbPalsu:
    pass


class _UserPalsu:
    id = None


def test_rebuild_ditolak_tanpa_sesi_saat_enforcement_aktif(monkeypatch):
    """Operasi destruktif tidak boleh berjalan tanpa jendela sesi aktif."""
    monkeypatch.setattr(settings, "demo_session_enforce", True, raising=False)

    async def tidak_ada_sesi(_db):
        return None

    dipanggil = False

    async def reset_tidak_boleh_dipanggil(_db):
        nonlocal dipanggil
        dipanggil = True
        return {"hitung": {}}

    monkeypatch.setattr(router.sesi, "aktif", tidak_ada_sesi)
    monkeypatch.setattr(
        "app.services.demo_template_reset.bangun_ulang",
        reset_tidak_boleh_dipanggil,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(router.butuh_sesi_aktif(db=_DbPalsu()))

    assert exc.value.status_code == 409
    assert "sesi demo" in str(exc.value.detail)
    assert dipanggil is False


def test_route_rebuild_memasang_dependency_sesi():
    """Kontrak wiring: FastAPI harus menjalankan guard sebelum handler."""
    from app.main import app

    route = next(
        r for r in app.routes if getattr(r, "path", None) == "/demo/template/rebuild"
    )
    dependency_calls = {d.call for d in route.dependant.dependencies}
    assert router.butuh_sesi_aktif in dependency_calls
