"""Data referensi minimum — isi mode DEFAULT.

Mode DEFAULT harus menjalankan aplikasi tanpa satu pun data bisnis tiruan:
hanya enum/lookup (komoditas, lokasi/SPPG) dan akun awal (peran RBAC) yang
ditanam. Semua tabel bisnis dibiarkan kosong supaya *empty state* frontend
benar-benar teruji, bukan tertutup data contoh.

Dipakai oleh `python -m app.seed.db_mode init-default`. Idempoten: semua baris
memakai `stable_uuid` dari nama/email, jadi dijalankan berulang tidak
menggandakan apa pun.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db import create_session_maker
from app.models import Commodity, Location, User
from app.seed.seed_data import DEMO_USERS, build_seed_rows, stable_uuid


async def seed_reference(session) -> dict[str, int]:
    """Tanam komoditas + lokasi + akun awal. Kembalikan jumlah baris per tabel."""
    rows = build_seed_rows(datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc))

    jumlah = {"commodities": 0, "locations": 0, "users": 0}

    for com in rows["commodities"]:
        ada = await session.get(Commodity, com["id"])
        if ada is None:
            session.add(Commodity(**com))
            jumlah["commodities"] += 1
        else:
            ada.name = com["name"]
            ada.unit = com["unit"]

    for loc in rows["locations"]:
        ada = await session.get(Location, loc["id"])
        if ada is None:
            session.add(Location(**loc))
            jumlah["locations"] += 1
        else:
            ada.name = loc["name"]
            ada.region = loc["region"]
            ada.latitude = loc["latitude"]
            ada.longitude = loc["longitude"]
            ada.role_hint = loc.get("role_hint")

    await session.flush()

    # Akun awal: peran-peran yang dipakai RBAC UI (kepala SPPG, ahli gizi,
    # pemantau BGN). Password-nya password demo yang sama dengan seed kanonik;
    # di produksi akun ini wajib diganti (lihat docs/db-mode.md).
    import bcrypt

    lokasi_menurut_nama = {
        name: uid
        for name, uid in (
            await session.execute(select(Location.name, Location.id))
        ).all()
    }
    for u in DEMO_USERS:
        uid = stable_uuid("user", u["email"])
        ada = await session.get(User, uid)
        if ada is None:
            session.add(
                User(
                    id=uid,
                    name=u["name"],
                    email=u["email"],
                    password_hash=bcrypt.hashpw(
                        u["password"].encode(), bcrypt.gensalt()
                    ).decode(),
                    role=u["role"],
                    location_id=lokasi_menurut_nama.get(u["location"]),
                )
            )
            jumlah["users"] += 1

    await session.commit()
    return jumlah


async def _main() -> dict[str, int]:
    engine = create_async_engine(settings.database_url)
    try:
        maker = create_session_maker(engine)
        async with maker() as session:
            return await seed_reference(session)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print(asyncio.run(_main()))
