#!/usr/bin/env python3
"""Tandatangani keadaan rantai ledger ke checkpoint di LUAR database.

Fase 11 MG, butir 2. `GET /ledger/verify` bisa menyatakan `valid=true` untuk
database yang ditulis ulang rapi: siapa pun yang memegang hak tulis tabel dapat
menghitung ulang seluruh `payload_hash`. Karena itu bukti integritas harus
dibandingkan dengan salinan yang disimpan di tempat aplikasi tidak bisa menulis.

Skrip ini adalah penulis salinan tersebut:
- membaca kepala rantai (`height` tertinggi + `payload_hash`-nya),
- menulis `data/anchors/ledger-checkpoint.json` secara atomik,
- hanya SELECT ke database (tidak menulis apa pun ke DB).

Jalankan sebagai role migrasi/pemilik dari HOST, dengan `./data` di-mount
TULIS (backend hanya mendapat `:ro`, jadi aplikasi tidak bisa memalsukan hasil
skrip ini):

  docker run --rm --network mealchain-guardian_mealchain-network \\
    --env-file .env \\
    -e DATABASE_URL=postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain \\
    -v "E:/hackathon/HackathonAWS/mealchain-guardian/backend:/app" \\
    -v "E:/hackathon/HackathonAWS/mealchain-guardian/data:/data" \\
    -w /app mealchain-guardian-backend python scripts/ledger_anchor.py

Sesudah itu panel Integritas menampilkan `anchor.match=true`. Bila checkpoint
hilang, panel menyatakan "belum ada checkpoint" — bukan "cocok".

Argumen:
  --output PATH   lokasi checkpoint (default: /data/anchors/ledger-checkpoint.json)
  --database-url  DSN asyncpg (default: env DATABASE_URL)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.ledger_service import tulis_checkpoint


async def _main(database_url: str, output: str) -> int:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as db:
            data = await tulis_checkpoint(db, output)
    finally:
        await engine.dispose()

    # Ringkasan tanpa rahasia: tidak ada DSN, tidak ada token.
    print(f"checkpoint  : {output}")
    print(f"height      : {data['height']}")
    print(f"blocks      : {data['blocks']}")
    print(f"generation  : {data['generation']}")
    print(f"payload_hash: {data['payload_hash']}")
    print(f"created_at  : {data['created_at']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default=None, help="lokasi berkas checkpoint")
    p.add_argument("--database-url", default=None, help="DSN asyncpg (default env)")
    args = p.parse_args(argv)

    dsn = args.database_url or os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL kosong — tidak ada database untuk dibaca", file=sys.stderr)
        return 2
    output = args.output or "/data/anchors/ledger-checkpoint.json"
    try:
        return asyncio.run(_main(dsn, output))
    except ValueError as exc:
        print(f"gagal menulis checkpoint: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
