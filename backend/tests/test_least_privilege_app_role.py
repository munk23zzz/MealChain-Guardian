"""Role aplikasi minimum: boleh bekerja, tidak boleh mengubah riwayat/DDL (Fase 11 butir 3).

Kontrak:
1. Akun login yang mewarisi `mealchain_app` dapat MEMBACA tabel (mis. `decisions`)
   dan MENULIS di tabel kerja (mis. `users`), serta menambah blok ledger lewat
   `append_block`.
2. Akun itu TIDAK dapat `UPDATE`/`DELETE`/`TRUNCATE` pada `ledger_blocks`, dan
   tidak dapat menjalankan DDL (`CREATE TABLE`) — jadi "append-only" dan
   "migrasi hanya oleh role migrasi" ditegakkan hak, bukan janji.
3. Migrasi dijalankan role pemilik (`mealchain`), yang juga anggota
   `mealchain_migrator`; aplikasi tidak pernah menjadi anggota role itu.

Akun login uji dibuat dan dihapus di dalam tes; kata sandinya acak dan tidak
pernah dicetak. Semua mutasi dijalankan di transaksi yang di-rollback.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.ledger_service import append_block
from tests.dsn import DSN_ASYNC, DSN_SYNC

ROLE_GRUP = "mealchain_app"
GUC = "mealchain.ledger_maintenance"


def _dsn_sebagai(user: str, password: str, *, asink: bool) -> str:
    dsn = DSN_SYNC
    if asink:
        dsn = DSN_ASYNC
    kepala, sisa = dsn.split("://", 1)
    _, ekor = sisa.split("@", 1)
    return f"{kepala}://{user}:{password}@{ekor}"


@contextmanager
def _tx(dsn: str):
    engine = create_engine(dsn)
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _exec(stmt: str, params: dict | None = None):
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            res = conn.execute(text(stmt), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        engine.dispose()


def _superuser() -> bool:
    return bool(_exec("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")[0][0])


@pytest.fixture()
def akun_app():
    """Akun login sementara yang mewarisi `mealchain_app` (bukan migrator)."""
    if not _superuser():
        pytest.skip("butuh role superuser untuk membuat akun login uji")
    nama = f"app_uji_{uuid.uuid4().hex[:8]}"
    sandi = f"Uji#{uuid.uuid4().hex[:12]}"
    dsn = _dsn_sebagai(nama, sandi, asink=False)
    try:
        _exec(
            f'CREATE ROLE "{nama}" LOGIN PASSWORD \'{sandi}\' '
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
        )
        _exec(f'GRANT {ROLE_GRUP} TO "{nama}"')
        yield {"nama": nama, "dsn": dsn, "dsn_async": _dsn_sebagai(nama, sandi, asink=True)}
    finally:
        _exec(f'DROP OWNED BY "{nama}"')
        _exec(f'DROP ROLE IF EXISTS "{nama}"')


def test_akun_aplikasi_bukan_superuser_dan_bukan_migrator(akun_app):
    baris = _exec(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles "
        "WHERE rolname = :r",
        {"r": akun_app["nama"]},
    )[0]
    assert tuple(bool(v) for v in baris) == (False, False, False, False), baris

    anggota_migrator = _exec(
        "SELECT pg_has_role(:r, 'mealchain_migrator', 'member')", {"r": akun_app["nama"]}
    )[0][0]
    assert anggota_migrator is False, "aplikasi tidak boleh berperan migrator"


def test_akun_aplikasi_bisa_membaca_dan_menulis_tabel_kerja(akun_app):
    with _tx(akun_app["dsn"]) as conn:
        jumlah = conn.execute(text("SELECT count(*) FROM decisions")).scalar_one()
        assert int(jumlah) >= 0
        # Menulis di tabel kerja (bukan riwayat) harus boleh.
        conn.execute(
            text("UPDATE users SET name = name WHERE id = (SELECT id FROM users LIMIT 1)")
        )


def test_akun_aplikasi_tidak_bisa_mengubah_riwayat(akun_app):
    puncak = int(
        _exec("SELECT coalesce(max(height), 0) FROM ledger_blocks")[0][0]
    )
    assert puncak > 0

    for stmt, params in (
        ("UPDATE ledger_blocks SET payload_hash = repeat('9', 64) WHERE height = :h",
         {"h": puncak}),
        ("DELETE FROM ledger_blocks WHERE height = :h", {"h": puncak}),
    ):
        with pytest.raises(DBAPIError):
            with _tx(akun_app["dsn"]) as conn:
                conn.execute(text(stmt), params)
    with pytest.raises(DBAPIError):
        with _tx(akun_app["dsn"]) as conn:
            conn.execute(text("TRUNCATE ledger_blocks"))


def test_akun_aplikasi_tidak_bisa_ddl(akun_app):
    with pytest.raises(DBAPIError):
        with _tx(akun_app["dsn"]) as conn:
            conn.execute(text(f"CREATE TABLE uji_ddl_{uuid.uuid4().hex[:6]} (id int)"))


def test_akun_aplikasi_bisa_menambah_blok_lewat_service(akun_app):
    """`append_block` jalan dengan hak minimum: SELECT+INSERT, tanpa UPDATE."""

    async def _main():
        engine = create_async_engine(akun_app["dsn_async"], pool_pre_ping=True)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                hasil = await append_block(
                    db,
                    action="uji.least_privilege",
                    entity_id=None,
                    actor_id=None,
                    payload={"uji": "append-oleh-akun-aplikasi"},
                )
                await db.rollback()
                return hasil
        finally:
            await engine.dispose()

    hasil = asyncio.run(_main())
    assert hasil["height"] > 0, hasil
    assert len(hasil["payload_hash"]) == 64, hasil


def test_akun_aplikasi_tidak_bisa_memakai_pintu_pemeliharaan(akun_app):
    """GUC saja tidak cukup: pintu pemeliharaan butuh peran migrator."""

    async def _main():
        engine = create_async_engine(akun_app["dsn_async"], pool_pre_ping=True)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                await db.execute(text(f"SET LOCAL {GUC} = 'on'"))
                try:
                    await db.execute(
                        text("UPDATE ledger_blocks SET payload = payload WHERE height = 1")
                    )
                finally:
                    await db.rollback()
        finally:
            await engine.dispose()

    with pytest.raises(DBAPIError):
        asyncio.run(_main())
