"""Ledger append-only ditegakkan DATABASE — bukan konvensi (Fase 11 MG).

Kontrak yang dikunci tes ini:

1. Role aplikasi (`mealchain_app`) hanya boleh `SELECT` dan `INSERT` pada
   `ledger_blocks`; `UPDATE`, `DELETE`, `TRUNCATE` ditolak.
2. Trigger `prevent_ledger_mutation()` menolak `UPDATE`/`DELETE`/`TRUNCATE`
   bahkan bagi pemilik tabel — jadi "append-only" tidak bergantung pada
   kesopanan kode aplikasi.
3. Rantai lama tetap valid sesudah migrasi (blok baru tidak mengubah hash).
4. Pintu pemeliharaan (`SET LOCAL mealchain.ledger_maintenance = 'on'` DAN
   keanggotaan `mealchain_migrator`) adalah satu-satunya jalan memotong ujung
   rantai untuk keperluan uji/rebuild.
5. Koreksi luar biasa dilayani dengan MENAMBAH blok `ledger.correction`,
   bukan menulis ulang blok lama, dan hanya oleh role migrasi.

Tes menulis ke DB yang ditunjuk `DATABASE_URL` (klon sekali pakai menurut
`MG/prompts-fase.md`), memakai blok di ujung rantai sendiri lalu memangkasnya
kembali lewat pintu pemeliharaan.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.ledger_service import append_block, verify_chain
from tests.dsn import DSN_ASYNC, DSN_SYNC

ROLE_APP = "mealchain_app"
ROLE_MIGRATOR = "mealchain_migrator"
GUC = "mealchain.ledger_maintenance"


def _exec(stmt: str, params: dict | None = None, *, maintenance: bool = False):
    """Jalankan satu pernyataan; `maintenance=True` membuka pintu pemeliharaan."""
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            if maintenance:
                conn.execute(text(f"SET LOCAL {GUC} = 'on'"))
            res = conn.execute(text(stmt), params or {})
            try:
                return res.fetchall()
            except Exception:
                return []
    finally:
        engine.dispose()


def _puncak() -> int:
    return int(_exec("SELECT coalesce(max(height), 0) FROM ledger_blocks")[0][0])


def _kepala() -> tuple[int, str]:
    baris = _exec(
        "SELECT height, payload_hash FROM ledger_blocks ORDER BY height DESC LIMIT 1"
    )
    return (int(baris[0][0]), str(baris[0][1])) if baris else (0, "0" * 64)


@contextmanager
def _tx(maintenance: bool = False, dsn: str = DSN_SYNC):
    """Transaksi yang SELALU di-rollback — tidak ada mutasi yang bertahan.

    Tanpa ini, run RED (trigger belum ada) akan benar-benar mengosongkan
    `ledger_blocks` lewat TRUNCATE di tes; DB uji jadi rusak sebelum migrasi
    diterapkan.
    """
    engine = create_engine(dsn)
    conn = engine.connect()
    trans = conn.begin()
    try:
        if maintenance:
            conn.execute(text(f"SET LOCAL {GUC} = 'on'"))
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _blok_uji(conn, tinggi: int, prev: str, action: str, payload: dict,
              generation: int = 1) -> str:
    """Tulis satu blok sah (hash benar) lewat koneksi yang diberikan."""
    teks = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256((prev + teks).encode()).hexdigest()
    conn.execute(
        text(
            "INSERT INTO ledger_blocks "
            "(height, prev_hash, payload_hash, action, payload, generation) "
            "VALUES (:h, :p, :ph, :a, :pl, :g)"
        ),
        {"h": tinggi, "p": prev, "ph": digest, "a": action, "pl": teks, "g": generation},
    )
    return digest


def _dsn_sebagai(user: str, password: str) -> str:
    """DSN yang sama dengan DB uji, tetapi login sebagai role lain."""
    return re.sub(r"://[^/@]+@", f"://{user}:{password}@", DSN_SYNC, count=1)


def _verifikasi() -> dict:
    async def _main():
        engine = create_async_engine(DSN_ASYNC, pool_pre_ping=True)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                return await verify_chain(db)
        finally:
            await engine.dispose()

    return asyncio.run(_main())


def _superuser() -> bool:
    return bool(_exec("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")[0][0])


# ---------------------------------------------------------------------------
# Butir 1 — hak SQL dan trigger
# ---------------------------------------------------------------------------
def test_role_aplikasi_hanya_insert_dan_select():
    hak = {}
    for aksi in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
        hak[aksi] = bool(
            _exec(
                "SELECT has_table_privilege(:r, 'ledger_blocks', :a)",
                {"r": ROLE_APP, "a": aksi},
            )[0][0]
        )
    assert hak["SELECT"] is True, hak
    assert hak["INSERT"] is True, hak
    assert hak["UPDATE"] is False, hak
    assert hak["DELETE"] is False, hak
    assert hak["TRUNCATE"] is False, hak


def test_role_migrasi_ada_dan_terpisah_dari_role_aplikasi():
    baris = _exec(
        "SELECT rolname, rolsuper, rolcanlogin FROM pg_roles "
        "WHERE rolname IN (:a, :m)",
        {"a": ROLE_APP, "m": ROLE_MIGRATOR},
    )
    nama = {r[0]: r for r in baris}
    assert set(nama) == {ROLE_APP, ROLE_MIGRATOR}
    for role in (ROLE_APP, ROLE_MIGRATOR):
        assert nama[role][1] is False, f"{role} tidak boleh superuser"
        assert nama[role][2] is False, f"{role} adalah wadah hak, bukan akun login"


def test_trigger_menolak_update_blok():
    puncak = _puncak()
    assert puncak > 0, "ledger kosong — tidak ada blok untuk diuji"
    asli = _exec(
        "SELECT payload_hash FROM ledger_blocks WHERE height = :h", {"h": puncak}
    )[0][0]
    with pytest.raises(DBAPIError) as galat:
        with _tx() as conn:
            conn.execute(
                text(
                    "UPDATE ledger_blocks SET payload_hash = repeat('f', 64) "
                    "WHERE height = :h"
                ),
                {"h": puncak},
            )
    assert "ledger_append_only" in str(galat.value)
    assert _kepala()[1] == asli


def test_trigger_menolak_delete_blok():
    puncak = _puncak()
    with pytest.raises(DBAPIError) as galat:
        with _tx() as conn:
            conn.execute(text("DELETE FROM ledger_blocks WHERE height = :h"),
                         {"h": puncak})
    assert "ledger_append_only" in str(galat.value)
    assert _puncak() == puncak


def test_trigger_menolak_truncate():
    puncak = _puncak()
    with pytest.raises(DBAPIError) as galat:
        with _tx() as conn:
            conn.execute(text("TRUNCATE ledger_blocks"))
    assert "ledger_append_only" in str(galat.value)
    assert _puncak() == puncak


def test_role_aplikasi_insert_select_tapi_update_delete_ditolak():
    """Role login dengan hak minimum: INSERT jalan, mutasi ditolak database."""
    if not _superuser():
        pytest.skip("butuh role superuser untuk membuat role uji sekali pakai")

    role = f"probe_f11_{uuid.uuid4().hex[:8]}"
    sandi = f"Probe#{uuid.uuid4().hex[:10]}"
    dsn_probe = _dsn_sebagai(role, sandi)
    puncak, prev = _kepala()
    try:
        _exec(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{sandi}\' NOSUPERUSER')
        _exec(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        _exec(f'GRANT SELECT, INSERT ON ledger_blocks TO "{role}"')

        # INSERT oleh role aplikasi harus BERHASIL (jalur kerja normal).
        with _tx(dsn=dsn_probe) as conn:
            _blok_uji(conn, puncak + 1, prev, "probe.fase11", {"uji": "role-aplikasi"})

        for stmt, params in (
            ("UPDATE ledger_blocks SET payload_hash = repeat('e', 64) WHERE height = :h",
             {"h": puncak}),
            ("DELETE FROM ledger_blocks WHERE height = :h", {"h": puncak}),
        ):
            with pytest.raises(DBAPIError):
                with _tx(dsn=dsn_probe) as conn:
                    conn.execute(text(stmt), params)
        with pytest.raises(DBAPIError):
            with _tx(dsn=dsn_probe) as conn:
                conn.execute(text("TRUNCATE ledger_blocks"))
        assert _puncak() == puncak, "tidak satu pun mutasi boleh bertahan"
    finally:
        _exec(f'DROP OWNED BY "{role}"')
        _exec(f'DROP ROLE IF EXISTS "{role}"')


def test_rantai_lama_tetap_valid_setelah_migrasi():
    hasil = _verifikasi()
    jumlah = int(_exec("SELECT count(*) FROM ledger_blocks")[0][0])
    kepala = _exec("SELECT payload_hash FROM ledger_blocks ORDER BY height DESC LIMIT 1")[0][0]
    assert hasil["valid"] is True, hasil
    assert hasil["blocks"] == jumlah, hasil
    assert hasil["head"] == kepala, hasil


# ---------------------------------------------------------------------------
# Butir 1 (lanjutan) — pintu pemeliharaan + prosedur koreksi yang disetujui
# ---------------------------------------------------------------------------
def test_pintu_pemeliharaan_hanya_dengan_guc_dan_role_migrasi():
    """Tanpa GUC mutasi ditolak; dengan GUC + role migrasi, pemangkasan diizinkan."""
    puncak, prev = _kepala()

    with pytest.raises(DBAPIError) as galat:
        with _tx() as conn:
            _blok_uji(conn, puncak + 1, prev, "probe.pemeliharaan", {"uji": "tanpa-guc"})
            conn.execute(
                text("UPDATE ledger_blocks SET entity_id = :e WHERE height = :h"),
                {"e": str(uuid.uuid4()), "h": puncak + 1},
            )
    assert "ledger_append_only" in str(galat.value)

    with _tx(maintenance=True) as conn:
        digest = _blok_uji(
            conn, puncak + 1, prev, "probe.pemeliharaan", {"uji": "dengan-guc"}
        )
        conn.execute(
            text("UPDATE ledger_blocks SET entity_id = :e WHERE height = :h"),
            {"e": str(uuid.uuid4()), "h": puncak + 1},
        )
        baris = conn.execute(
            text("SELECT payload_hash, entity_id FROM ledger_blocks WHERE height = :h"),
            {"h": puncak + 1},
        ).one()
        assert baris[0] == digest
        assert baris[1] is not None

    assert _puncak() == puncak, "semua mutasi uji harus dibatalkan"


def test_koreksi_menambah_blok_bukan_menulis_ulang():
    puncak = _puncak()
    target = max(1, puncak)
    try:
        with pytest.raises(DBAPIError) as galat:
            _exec("SELECT ledger_append_correction(:t, :r)", {"t": target, "r": "uji pintu"})
        assert "ledger_append_only" in str(galat.value), "koreksi wajib lewat pintu pemeliharaan"

        baris = _exec(
            "SELECT ledger_append_correction(:t, :r)",
            {"t": target, "r": "koreksi uji otomatis Fase 11"},
            maintenance=True,
        )
        tinggi_baru = int(baris[0][0])
        assert tinggi_baru == puncak + 1

        aksi, payload = _exec(
            "SELECT action, payload FROM ledger_blocks WHERE height = :h", {"h": tinggi_baru}
        )[0]
        assert aksi == "ledger.correction"
        assert f'"target_height": {target}' in payload, payload

        hasil = _verifikasi()
        assert hasil["valid"] is True, hasil
        assert hasil["blocks"] == tinggi_baru, hasil
    finally:
        _exec("DELETE FROM ledger_blocks WHERE height > :h", {"h": puncak},
              maintenance=True)


def test_role_aplikasi_tidak_bisa_menjalankan_koreksi():
    """Dua syarat koreksi: hak EXECUTE (role migrasi) DAN pintu pemeliharaan."""
    if not _superuser():
        pytest.skip("butuh role superuser untuk membuat role uji sekali pakai")

    role = f"probe_kor_{uuid.uuid4().hex[:8]}"
    sandi = f"Probe#{uuid.uuid4().hex[:10]}"
    dsn_probe = _dsn_sebagai(role, sandi)
    try:
        _exec(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{sandi}\' NOSUPERUSER')
        _exec(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        _exec(f'GRANT SELECT ON ledger_blocks TO "{role}"')
        with pytest.raises(DBAPIError):
            with _tx(dsn=dsn_probe) as conn:
                conn.execute(text(f"SET LOCAL {GUC} = 'on'"))
                conn.execute(text("SELECT ledger_append_correction(1, 'coba aplikasi')"))
    finally:
        _exec(f'DROP OWNED BY "{role}"')
        _exec(f'DROP ROLE IF EXISTS "{role}"')


def test_append_block_bekerja_untuk_role_minimum():
    """`append_block` tidak boleh menuntut hak UPDATE (FOR UPDATE akan gagal)."""
    if not _superuser():
        pytest.skip("butuh role superuser untuk membuat role uji sekali pakai")

    role = f"probe_ins_{uuid.uuid4().hex[:8]}"
    sandi = f"Probe#{uuid.uuid4().hex[:10]}"
    dsn_probe = _dsn_sebagai(role, sandi).replace("+psycopg", "+asyncpg")
    try:
        _exec(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{sandi}\' NOSUPERUSER')
        _exec(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        _exec(f'GRANT SELECT, INSERT ON ledger_blocks TO "{role}"')
        _exec(f'GRANT SELECT ON ledger_meta TO "{role}"')

        async def _main():
            engine = create_async_engine(dsn_probe, pool_pre_ping=True)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with maker() as db:
                    hasil = await append_block(
                        db,
                        action="probe.fase11",
                        entity_id=None,
                        actor_id=None,
                        payload={"uji": "append-role-minimum"},
                    )
                    await db.rollback()
                    return hasil
            finally:
                await engine.dispose()

        hasil = asyncio.run(_main())
        assert hasil["height"] > 0, hasil
        assert len(hasil["payload_hash"]) == 64, hasil
    finally:
        _exec(f'DROP OWNED BY "{role}"')
        _exec(f'DROP ROLE IF EXISTS "{role}"')
