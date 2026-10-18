"""Buat token JWT untuk agent (worker) tanpa lewat endpoint login.

Dipakai saat menyiapkan `MEALCHAIN_API_TOKEN` untuk runtime AgentCore: token ini
hanya perlu kemampuan BACA (role `bgn_monitor` = cakupan nasional, read-only),
berumur panjang (default 30 hari), dan tidak bergantung pada password demo.

Token memakai klaim yang sama dengan `backend/app/api/auth.py::_issue_token`
(`sub`, `role`, `loc`, `iat`, `exp`), jadi diterima `get_current_user` apa adanya.

Contoh:
    python backend/scripts/buat_token_agen.py --email bgn.monitor@demo.local --hari 30
    python backend/scripts/buat_token_agen.py --email bgn.monitor@demo.local --tulis-env

`--tulis-env` menambahkan/mengganti baris `MEALCHAIN_API_TOKEN=` di berkas `.env`
di root repo (nilai token tidak dicetak ke layar).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import jwt as pyjwt

ROOT = Path(__file__).resolve().parents[2]
KUNCI_TOKEN = "MEALCHAIN_API_TOKEN"


def cari_root(mulai: Path) -> Path:
    """Cari akar repo (folder berisi docker-compose.yml) tanpa bergantung kedalaman."""
    for kandidat in (mulai, *mulai.parents):
        if (kandidat / "docker-compose.yml").exists():
            return kandidat
    return mulai


def muat_env(path: Path) -> dict[str, str]:
    hasil: dict[str, str] = {}
    if not path.exists():
        return hasil
    for baris in path.read_text(encoding="utf-8").splitlines():
        baris = baris.strip()
        if baris and not baris.startswith("#") and "=" in baris:
            kunci, nilai = baris.split("=", 1)
            hasil[kunci.strip()] = nilai.strip()
    return hasil


def url_psycopg(url: str) -> str:
    """`postgresql+psycopg://…` → `postgresql://…` untuk koneksi langsung."""
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def cari_user(url: str, email: str) -> tuple[str, str, str | None]:
    import psycopg

    with psycopg.connect(url) as koneksi, koneksi.cursor() as kursor:
        kursor.execute(
            "select id::text, role, location_id::text from users where email = %s",
            (email,),
        )
        baris = kursor.fetchone()
    if baris is None:
        raise SystemExit(f"user dengan email {email!r} tidak ditemukan")
    return baris[0], baris[1], baris[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat token JWT untuk agent MealChain.")
    parser.add_argument("--email", default="bgn.monitor@demo.local")
    parser.add_argument("--hari", type=int, default=30, help="umur token dalam hari")
    parser.add_argument(
        "--tulis-env", action="store_true", help="tulis ke .env (tanpa mencetak token)"
    )
    parser.add_argument("--database-url", default="", help="override DATABASE_URL")
    args = parser.parse_args()

    root = cari_root(Path(__file__).resolve())
    env = {**muat_env(root / ".env"), **muat_env(root / "secrets" / "aws-app.env"), **os.environ}
    secret = env.get("JWT_SECRET", "")
    if not secret:
        raise SystemExit("JWT_SECRET belum diset (cek .env atau environment)")
    database_url = args.database_url or env.get("DATABASE_URL", "")
    if not database_url:
        raise SystemExit("DATABASE_URL belum diset (cek .env atau pakai --database-url)")

    user_id, role, lokasi = cari_user(url_psycopg(database_url), args.email)
    sekarang = int(time.time())
    token = pyjwt.encode(
        {
            "sub": user_id,
            "role": role,
            "loc": lokasi,
            "iat": sekarang,
            "exp": sekarang + args.hari * 24 * 3600,
        },
        secret,
        algorithm=env.get("JWT_ALGORITHM", "HS256"),
    )

    if args.tulis_env:
        path = root / ".env"
        baris_baru = [
            b
            for b in path.read_text(encoding="utf-8").splitlines()
            if not b.startswith(f"{KUNCI_TOKEN}=")
        ]
        baris_baru.append(f"{KUNCI_TOKEN}={token}")
        path.write_text("\n".join(baris_baru) + "\n", encoding="utf-8")
        print(f"token untuk {args.email} (role {role}) ditulis ke .env; panjang {len(token)}")
    else:
        print(token)
    print(
        f"umur {args.hari} hari · role {role} · lokasi {lokasi or 'semua (nasional)'}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
