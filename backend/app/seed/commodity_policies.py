"""Seeder profil komoditas — mengisi `commodity_policies` untuk DB baru.

Kenapa modul ini ada (celah terukur 27 Okt 2026): migrasi `041_commodity_policies`
mengisi tabel profil dengan `INSERT ... SELECT FROM commodities ... WHERE c.name =
:nama`. Pada database yang **dimigrasi lebih dulu daripada diseed**, tabel
`commodities` masih kosong, sehingga migrasi menulis **0 baris profil tanpa satu
pun galat**. Akibatnya:

- `profil_untuk_komoditas` terus jatuh ke bawaan kode (`PROFILES`), sehingga
  perubahan profil di DB tidak berpengaruh dan `profile_source` selalu "bawaan";
- klaim "aturan dibaca dari tabel" pada rencana Fase 3 tidak benar untuk DB baru.

Seeder ini menutupnya: dipanggil SESUDAH komoditas ada, menulis profil yang sama
dengan `PROFILES` (bukan salinan angka terpisah — satu sumber), dan idempoten
lewat **kunci bisnis** (`commodity_id` + `is_active`), bukan primary key acak.

Catatan: modul ini sengaja memakai SQL Core lewat engine sendiri (`SEED_DATABASE_URL`
→ `DATABASE_URL` → DSN compose) mengikuti presedensi seeder repo ini, supaya bisa
dipanggil dari skrip penyemai mana pun tanpa memaksa membuka sesi async.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.commodity_policy import PROFILES, CommodityPolicy

__all__ = ["dsn_async", "seed_commodity_policies", "seed_commodity_policies_sync"]


def dsn_async() -> str:
    """DSN async untuk seeder: `SEED_DATABASE_URL` menang, lalu `DATABASE_URL`.

    Presedensi ini disengaja: penyemai punya target tulis sendiri di beberapa
    jalur, dan menimpanya diam-diam membuat data demo berubah padahal perintah
    dijalankan dengan DSN salinan.
    """
    kandidat = (
        os.environ.get("SEED_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
    )
    if kandidat.startswith("postgresql+psycopg://"):
        kandidat = kandidat.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    elif kandidat.startswith("postgresql://"):
        kandidat = kandidat.replace("postgresql://", "postgresql+asyncpg://", 1)
    return kandidat


def _nilai_profil(policy: CommodityPolicy) -> dict:
    """Baris DB dari satu `CommodityPolicy` — termasuk `simulated_policy`."""
    return {
        "cold": policy.cold_chain_required,
        "tmin": policy.safe_temp_min_c,
        "tmax": policy.safe_temp_max_c,
        "shelf": policy.shelf_life_days,
        "minsamples": policy.min_temperature_samples,
        "maxage": policy.max_observation_age_minutes,
        "maxexc": policy.max_excursion_minutes,
        "versi": policy.policy_version,
        "basis": policy.policy_basis,
        "kind": policy.policy_kind,
    }


async def seed_commodity_policies() -> dict:
    """Tulis profil aktif untuk setiap komoditas yang ada. Idempoten.

    Mengembalikan `{"baru": n, "dilewati": n, "komoditas_tanpa_profil": [...]}`.
    `dilewati` = komoditas yang sudah punya profil AKTIF (tidak ditimpa: profil
    bisa sudah dikalibrasi manusia, dan seeder tidak boleh mengembalikannya ke
    asumsi demo).
    """
    engine = create_async_engine(dsn_async())
    baru = 0
    dilewati = 0
    tanpa_profil: list[str] = []
    try:
        async with engine.begin() as conn:
            ada_tabel = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_name = 'commodity_policies'"
                    )
                )
            ).scalar_one()
            if not ada_tabel:
                raise RuntimeError(
                    "tabel commodity_policies belum ada — jalankan "
                    "`alembic upgrade head` sebelum menyemai profil"
                )
            komoditas = (
                await conn.execute(text("SELECT id, name FROM commodities"))
            ).mappings().all()
            kunci_komoditas = {
                str(row["name"]).strip().lower(): row["id"] for row in komoditas
            }
            aktif = {
                str(row["commodity_id"])
                for row in (
                    await conn.execute(
                        text(
                            "SELECT commodity_id FROM commodity_policies WHERE is_active"
                        )
                    )
                ).mappings()
            }

            for nama, policy in PROFILES.items():
                cid = kunci_komoditas.get(nama)
                if cid is None:
                    # Komoditas belum ada di DB ini: jangan mengarang baris untuk
                    # entitas yang tidak dikenal. Dilaporkan, bukan didiamkan.
                    tanpa_profil.append(nama)
                    continue
                if str(cid) in aktif:
                    dilewati += 1
                    continue
                nilai = _nilai_profil(policy)
                await conn.execute(
                    text(
                        "INSERT INTO commodity_policies ("
                        "commodity_id, cold_chain_required, safe_temp_min_c, "
                        "safe_temp_max_c, shelf_life_days, min_temperature_samples, "
                        "max_observation_age_minutes, max_excursion_minutes, "
                        "policy_version, policy_basis, policy_kind, is_active"
                        ") VALUES (CAST(:cid AS uuid), :cold, :tmin, :tmax, :shelf, "
                        ":minsamples, :maxage, :maxexc, :versi, :basis, :kind, true)"
                    ),
                    {"cid": str(cid), **nilai},
                )
                baru += 1
                aktif.add(str(cid))
    finally:
        await engine.dispose()

    return {
        "baru": baru,
        "dilewati": dilewati,
        "komoditas_tanpa_profil": tanpa_profil,
    }


def seed_commodity_policies_sync() -> dict:
    """Pembungkus sinkron untuk skrip penyemai berbasis `asyncio.run`."""
    return asyncio.run(seed_commodity_policies())


# ── pemakaian sebagai modul: `python -m app.seed.commodity_policies` ─────────
if __name__ == "__main__":  # pragma: no cover - jalur operasional
    hasil = seed_commodity_policies_sync()
    print(
        f"profil komoditas: {hasil['baru']} baru, {hasil['dilewati']} dilewati, "
        f"tanpa_profil={hasil['komoditas_tanpa_profil']}"
    )
