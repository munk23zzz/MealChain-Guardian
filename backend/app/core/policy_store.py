"""Profil komoditas dari DB — satu pembaca untuk freshness, safety, API, Joule.

Tabel `commodity_policies` adalah sumber kebenaran profil (rencana Fase 3:
"aturan harus dapat dibaca oleh core, API, seed, dan Joule tanpa mengulang
mapping Python"). Modul ini:

- membaca profil AKTIF dari DB;
- memvalidasi barisnya lewat `validate_policy_row` (bukan mempercayai DB
  buta-buta: constraint DB menjaga nilai cacat, tetapi validasi yang sama
  dipakai juga saat seed supaya dua pintu tidak berbeda aturan);
- jatuh ke `PROFILES` (profil bawaan kode) HANYA bila tabelnya belum ada/baris
  hilang — dengan penanda `sumber` supaya API bisa menyebut asal angkanya,
  bukan menyembunyikan bahwa DB belum berisi.

Kenapa ada fallback: test/DB lama bisa berjalan sebelum migrasi 041. Tanpa
fallback, setiap evaluasi batch gagal 500 hanya karena migrasi belum jalan.
Dengan fallback + `sumber`, ketahuan mana yang dibaca.
"""

from __future__ import annotations

from app.core.commodity_policy import PROFILES, CommodityPolicy, validate_policy_row

__all__ = ["ASAL_DB", "ASAL_BAWAAN", "baca_profil", "baca_semua_profil", "profil_untuk_komoditas"]

ASAL_DB = "commodity_policies"
ASAL_BAWAAN = "core.commodity_policy.PROFILES"


async def _baris_aktif(db, commodity: str | None = None) -> list[dict]:
    """Baca baris aktif dari `commodity_policies` (kosong bila tabel belum ada)."""
    from sqlalchemy import text

    nama = (commodity or "").strip().lower()
    sql = (
        "SELECT c.name AS commodity, p.cold_chain_required, "
        "p.safe_temp_min_c, p.safe_temp_max_c, p.shelf_life_days, "
        "p.min_temperature_samples, p.max_observation_age_minutes, "
        "p.max_excursion_minutes, p.policy_version, p.policy_basis, p.policy_kind "
        "FROM commodity_policies p JOIN commodities c ON c.id = p.commodity_id "
        "WHERE p.is_active"
    )
    if nama:
        sql += " AND lower(c.name) = :nama"
    try:
        rows = (await db.execute(text(sql), {"nama": nama})).mappings().all()
    except Exception:  # tabel belum ada (DB pra-migrasi 041) / DB tak terjangkau
        return []
    return [dict(row) for row in rows]


async def baca_profil(db, commodity: str | None) -> tuple[CommodityPolicy, str]:
    """Profil satu komoditas + asal pembacaannya (`commodity_policies`/bawaan).

    `KeyError` bila komoditas tidak dikenal sama sekali: menebak profil adalah
    bug yang Fase 3 tutup.
    """
    baris = await _baris_aktif(db, commodity)
    if baris:
        return validate_policy_row(baris[0]), ASAL_DB
    kunci = (commodity or "").strip().lower()
    if kunci in PROFILES:
        return PROFILES[kunci], ASAL_BAWAAN
    raise KeyError(
        f"komoditas {commodity!r} belum punya profil; "
        f"tersedia: {', '.join(sorted(PROFILES))}"
    )


async def baca_semua_profil(db) -> dict[str, tuple[CommodityPolicy, str]]:
    """Semua profil aktif, dikunci nama komoditas — untuk daftar/agregasi."""
    hasil: dict[str, tuple[CommodityPolicy, str]] = {
        nama: (policy, ASAL_BAWAAN) for nama, policy in PROFILES.items()
    }
    for row in await _baris_aktif(db):
        kunci = str(row["commodity"]).strip().lower()
        hasil[kunci] = (validate_policy_row(row), ASAL_DB)
    return hasil


async def profil_untuk_komoditas(db, commodity_id) -> tuple[CommodityPolicy, str]:
    """Profil dari `commodity_id` (jalur batch) — nama dibaca dari tabel komoditas."""
    from sqlalchemy import text

    nama = (
        await db.execute(
            text("SELECT name FROM commodities WHERE id = :i"), {"i": str(commodity_id)}
        )
    ).scalar_one_or_none()
    if nama is None:
        raise KeyError(f"komoditas id {commodity_id} tidak ada di tabel commodities")
    return await baca_profil(db, nama)
