"""Batas 2 jam sesi demo, satu sesi aktif, dan penolakan setelah kedaluwarsa.

Tiga kontrak yang dikunci di sini (permintaan produk, 25 Okt 2026):

1. **Batas absolut 2 jam.** `expires_at` tidak pernah melewati
   `started_at + DEMO_SESSION_MAX_MINUTES`, walau `/demo/session/extend`
   meminta lebih. Perpanjangan hanya boleh menambal sampai plafon.
2. **Satu sesi aktif.** Dijamin DATABASE (unique partial index), bukan hanya
   `asyncio.Lock` satu proses: dua worker tidak bisa membuka dua sesi aktif.
3. **Penolakan setelah kedaluwarsa.** Dengan `DEMO_SESSION_ENFORCE=true`,
   request MUTASI tanpa sesi aktif dijawab 409 dengan kalimat yang menyuruh
   menyiapkan sesi — bukan diteruskan, dan bukan 500.

Berkas ini menyentuh `demo_sessions` dan (pada tes enforcement) memicu sapuan
`origin='demo'`. Jalankan dengan `TEST_DATABASE_URL` menunjuk DB sekali-pakai;
pada DB kerja, tes enforcement akan menghapus baris demo tanpa stempel.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.main import app
from app.services import demo_session as sesi
from tests.dsn import DSN_SYNC

WIB = timezone(timedelta(hours=7))


# ----------------------------------------------------------- batas 2 jam


def test_batas_akhir_selalu_dua_jam(monkeypatch):
    monkeypatch.setattr(settings, "demo_session_max_minutes", 120)
    mulai = datetime(2026, 10, 25, 10, 0, tzinfo=WIB)
    assert sesi._batas_akhir(mulai) == mulai + timedelta(minutes=120)


def test_menit_valid_tidak_bisa_melewati_plafon(monkeypatch):
    monkeypatch.setattr(settings, "demo_session_max_minutes", 120)
    assert sesi._menit_valid(999, 120) == 120
    assert sesi._menit_valid(None, 500) == 120


def test_perpanjang_berhenti_di_plafon_dua_jam(monkeypatch):
    """Sesi 110 menit + minta 240 menit → berhenti di 120 menit, bukan 350."""
    monkeypatch.setattr(settings, "demo_session_max_minutes", 120)

    async def _skenario():
        async with _db() as db:
            await _pastikan_tanpa_sesi(db)
            awal = await sesi.mulai(db, menit=110)
            try:
                sesudah = await sesi.perpanjang(db, menit=240)
                assert sesudah is not None
                assert sesudah.id == awal.id
                assert sesudah.expires_at == awal.started_at + timedelta(minutes=120)
            finally:
                await _hapus_sesi(db, awal.id)

    _jalankan(_skenario)


# --------------------------------------------------- satu sesi aktif (DB)


def _ada_sesi_aktif(conn) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM demo_sessions WHERE status='active' LIMIT 1")
        ).scalar()
    )


def test_database_menolak_dua_sesi_aktif():
    """Unique partial index: baris `active` kedua ditolak DB, bukan oleh kode."""
    eng = create_engine(DSN_SYNC)
    sid1, sid2 = uuid.uuid4(), uuid.uuid4()
    sekarang = datetime.now(timezone.utc)
    sql = text(
        "INSERT INTO demo_sessions (id, status, started_at, expires_at, anchor_now) "
        "VALUES (:i, 'active', :s, :e, :s)"
    )
    try:
        with eng.connect() as conn:
            # Sesi aktif milik orang lain TIDAK boleh ditutup tes ini: di DB demo
            # itu sesi yang sedang dipakai layar. Bila ada, tes ini tidak bisa
            # menyiapkan prasyaratnya (tepat satu baris aktif buatan sendiri).
            if _ada_sesi_aktif(conn):
                pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
        with eng.begin() as conn:
            conn.execute(
                sql,
                {"i": str(sid1), "s": sekarang, "e": sekarang + timedelta(hours=2)},
            )
        with pytest.raises(IntegrityError):
            with eng.begin() as conn:
                conn.execute(
                    sql,
                    {"i": str(sid2), "s": sekarang, "e": sekarang + timedelta(hours=2)},
                )
    finally:
        with eng.begin() as conn:
            conn.execute(
                text("DELETE FROM demo_sessions WHERE id IN (:a, :b)"),
                {"a": str(sid1), "b": str(sid2)},
            )
        eng.dispose()


# ------------------------------------------ enforcement setelah kedaluwarsa


def _mk_token(uid, role="sppg_head", loc=None) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(uid),
        "role": role,
        "loc": str(loc) if loc else None,
        "iat": now,
        "exp": now + 900,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest.fixture
def akun_sppg():
    eng = create_engine(DSN_SYNC)
    with eng.begin() as conn:
        loc = conn.execute(
            text("SELECT id FROM locations WHERE name='Jakarta' LIMIT 1")
        ).scalar()
    if loc is None:
        pytest.skip("lokasi Jakarta tidak ada di DB uji")
    uid = uuid.uuid4()
    digest = bcrypt.hashpw(b"uji-sesi-pw", bcrypt.gensalt()).decode()
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id,email,name,role,location_id,password_hash) "
                "VALUES (:i,:e,'Uji Sesi','sppg_head',:l,:p)"
            ),
            {"i": str(uid), "e": f"uji-sesi-{uid.hex[:10]}@test.local", "l": str(loc), "p": digest},
        )
    try:
        yield {"uid": uid, "loc": loc, "token": _mk_token(uid, loc=loc)}
    finally:
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id=:i"), {"i": str(uid)})
        eng.dispose()


def test_mutasi_ditolak_saat_tidak_ada_sesi(akun_sppg, monkeypatch):
    """Tanpa sesi aktif + enforce menyala → 409, bukan diproses."""
    monkeypatch.setattr(settings, "demo_session_enforce", True)
    h = {"Authorization": f"Bearer {akun_sppg['token']}"}
    with TestClient(app) as client:
        # pastikan tidak ada sesi aktif (endpoint ini juga memicu sapuan demo)
        r0 = client.get("/demo/session", headers=h)
        assert r0.status_code == 200
        if r0.json()["active"]:
            # DB demo yang sedang dipakai layar punya sesi aktif; tes ini tidak
            # menutup sesi orang lain, jadi prasyaratnya tidak bisa dibuat.
            pytest.skip("ada sesi demo aktif — tes tidak menutupnya")
        r = client.post(
            "/actions/approve",
            json={"decision_id": str(uuid.uuid4()), "approved": True},
            headers=h,
        )
    assert r.status_code == 409, r.text
    assert "sesi demo" in r.text.lower()


def test_baca_tetap_boleh_tanpa_sesi(akun_sppg, monkeypatch):
    """Pembacaan tidak diblokir: KPI tetap bisa dilihat walau sesi kosong."""
    monkeypatch.setattr(settings, "demo_session_enforce", True)
    h = {"Authorization": f"Bearer {akun_sppg['token']}"}
    with TestClient(app) as client:
        client.get("/demo/session", headers=h)
        r = client.get("/kpi?periode=today", headers=h)
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ util


def _jalankan(coro_fn):
    import asyncio

    return asyncio.run(coro_fn())


from contextlib import asynccontextmanager  # noqa: E402

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from tests.dsn import DSN_ASYNC  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL", DSN_ASYNC)


@asynccontextmanager
async def _db():
    engine = create_async_engine(DSN)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _pastikan_tanpa_sesi(db):
    from sqlalchemy import select

    from app.models import DemoSession

    ada = (
        await db.execute(
            select(DemoSession.id)
            .where(DemoSession.status == "active")
            .execution_options(demo_session_bypass=True)
        )
    ).scalar_one_or_none()
    if ada is not None:
        pytest.skip("ada sesi demo aktif — tes tidak menutupnya")


async def _hapus_sesi(db, *ids):
    from sqlalchemy import delete

    from app.models import DemoSession

    for sid in ids:
        if sid is None:
            continue
        await db.execute(
            delete(DemoSession)
            .where(DemoSession.id == sid)
            .execution_options(demo_session_bypass=True)
        )
    await db.commit()
