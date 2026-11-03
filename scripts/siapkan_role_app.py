#!/usr/bin/env python3
"""Buat akun login aplikasi yang mewarisi `mealchain_app` (Fase 11 MG, butir 3).

Kenapa terpisah dari migrasi: kata sandi tidak boleh masuk berkas migrasi yang
dilacak git. Migrasi hanya membuat WADAH HAK (`mealchain_app`, NOLOGIN);
akun login dibuat di sini, dengan sandi dibaca dari `APP_DB_PASSWORD`.

Yang dilakukan:
- `CREATE ROLE <APP_DB_USER> LOGIN PASSWORD ... NOSUPERUSER NOCREATEDB
  NOCREATEROLE NOBYPASSRLS` (atau `ALTER ROLE ... PASSWORD` bila sudah ada),
- `GRANT mealchain_app TO <APP_DB_USER>` — hak kerja dari migrasi 043,
- memastikan akun itu BUKAN anggota `mealchain_migrator`.

Keluaran TIDAK memuat sandi: hanya nama akun, keanggotaan, dan DSN dengan
penanda `<APP_DB_PASSWORD>`.

Jalankan sebagai role pemilik/migrasi dari host:

  APP_DB_PASSWORD='...' docker run --rm \\
    --network mealchain-guardian_mealchain-network --env-file .env \\
    -e APP_DB_PASSWORD -e DATABASE_URL=postgresql+asyncpg://mealchain:***@postgres:5432/mealchain \\
    -v "E:/hackathon/HackathonAWS/mealchain-guardian:/repo:ro" -w /repo \\
    -e PYTHONPATH=/repo/backend mealchain-guardian-backend \\
    python scripts/siapkan_role_app.py

Sesudah itu `DATABASE_URL` aplikasi boleh diarahkan ke akun ini; `alembic` dan
`pg_dump` tetap memakai DSN pemilik (butir 3: migrasi/backup oleh role berwenang).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROLE_GRUP = "mealchain_app"
ROLE_MIGRATOR = "mealchain_migrator"
POLA_NAMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _escape(petik: str) -> str:
    """Literal string SQL aman (standard_conforming_strings = on)."""
    return petik.replace("'", "''")


async def _siapkan(database_url: str, user: str, sandi: str) -> dict:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as db:
            ada = (
                await db.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": user}
                )
            ).fetchone()
            if ada:
                await db.execute(
                    text(f'ALTER ROLE "{user}" WITH LOGIN PASSWORD \'{_escape(sandi)}\'')
                )
                tindakan = "diperbarui"
            else:
                await db.execute(
                    text(
                        f'CREATE ROLE "{user}" LOGIN PASSWORD \'{_escape(sandi)}\' '
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                    )
                )
                tindakan = "dibuat"

            await db.execute(text(f'GRANT {ROLE_GRUP} TO "{user}"'))
            # Jangan pernah memberi peran migrator ke akun aplikasi.
            await db.execute(text(f'REVOKE {ROLE_MIGRATOR} FROM "{user}"'))

            anggota_grup = (
                await db.execute(
                    text(f"SELECT pg_has_role(:r, '{ROLE_GRUP}', 'member')"),
                    {"r": user},
                )
            ).scalar_one()
            anggota_migrator = (
                await db.execute(
                    text(f"SELECT pg_has_role(:r, '{ROLE_MIGRATOR}', 'member')"),
                    {"r": user},
                )
            ).scalar_one()
            sifat = (
                await db.execute(
                    text(
                        "SELECT rolsuper, rolcanlogin, rolcreatedb, rolcreaterole "
                        "FROM pg_roles WHERE rolname = :r"
                    ),
                    {"r": user},
                )
            ).one()
            await db.commit()
    finally:
        await engine.dispose()

    return {
        "tindakan": tindakan,
        "anggota_app": bool(anggota_grup),
        "anggota_migrator": bool(anggota_migrator),
        "superuser": bool(sifat[0]),
        "canlogin": bool(sifat[1]),
        "createdb": bool(sifat[2]),
        "createrole": bool(sifat[3]),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user", default=os.environ.get("APP_DB_USER", "mealchain_app_login"))
    p.add_argument("--database-url", default=None)
    args = p.parse_args(argv)

    user = args.user
    if not POLA_NAMA.match(user):
        print(f"nama akun tidak sah: {user!r}", file=sys.stderr)
        return 2

    sandi = os.environ.get("APP_DB_PASSWORD", "")
    if not sandi:
        print(
            "APP_DB_PASSWORD kosong — sandi tidak dibuat di repo; set lewat env",
            file=sys.stderr,
        )
        return 2
    if len(sandi) < 12:
        print("APP_DB_PASSWORD terlalu pendek (minimal 12 karakter)", file=sys.stderr)
        return 2

    dsn = args.database_url or os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL kosong — butuh DSN role pemilik", file=sys.stderr)
        return 2

    hasil = asyncio.run(_siapkan(dsn, user, sandi))

    print(f"akun aplikasi : {user} ({hasil['tindakan']})")
    print(f"anggota       : {ROLE_GRUP}={hasil['anggota_app']} "
          f"{ROLE_MIGRATOR}={hasil['anggota_migrator']}")
    print(
        "sifat         : "
        f"superuser={hasil['superuser']} login={hasil['canlogin']} "
        f"createdb={hasil['createdb']} createrole={hasil['createrole']}"
    )
    # DSN contoh TANPA sandi asli — pembaca mengambilnya dari env.
    contoh = re.sub(r"://[^/@]+@", f"://{user}:<APP_DB_PASSWORD>@", dsn)
    print(f"DSN aplikasi  : {contoh}")

    if not hasil["anggota_app"] or hasil["anggota_migrator"] or hasil["superuser"]:
        print("GAGAL: keanggotaan/sifat akun tidak sesuai kontrak", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
