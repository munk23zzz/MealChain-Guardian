"""Seeder mengisi profil komoditas — DB baru tidak boleh kehabisan profil (Fase 3).

Migrasi 041 mengisi `commodity_policies` dengan `INSERT ... SELECT FROM commodities`
lalu `WHERE c.name = :nama`. Pada database yang di-migrasi lebih dulu daripada
diseed, tabel `commodities` masih KOSONG, sehingga nol baris profil ditulis dan
tidak ada galat apa pun. Gejalanya baru muncul jauh kemudian: `profil_untuk_komoditas`
jatuh ke bawaan kode (`core.commodity_policy.PROFILES`) sehingga perubahan profil
di DB tidak berpengaruh, dan `profile_source` terus berbunyi "bawaan".

Kontrak yang dikunci berkas ini:

1. Setelah seed pada DB yang komoditasnya belum ada, SETIAP komoditas punya tepat
   satu baris profil AKTIF.
2. Menjalankan seed dua kali tidak menambah baris profil (idempoten lewat kunci
   bisnis `commodity_id` + `is_active`, bukan lewat primary key acak).
3. Profil yang ditulis seeder lolos validasi yang sama dengan pembaca API
   (`validate_policy_row`), jadi dua pintu tidak berbeda aturan.
4. Komoditas ambient (beras) tersimpan tanpa rentang dingin — bukan 0-8 °C.

Berkas ini bekerja di DB-nya sendiri (skema dibangun dari `Base.metadata`) supaya
tidak menyentuh data sesi lain.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text

from app.core.commodity_policy import PROFILES, validate_policy_row
from tests.dsn import DSN_SYNC

KOMODITAS = ("telur", "ayam", "wortel", "beras")


def _db():
    return create_engine(DSN_SYNC)


def _exec(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            res = conn.execute(text(sql), params or {})
            try:
                return res.fetchall()
            except Exception:  # noqa: BLE001 - statement tanpa resultset (DELETE/INSERT)
                return []
    finally:
        engine.dispose()


def _scalar(sql: str, params: dict | None = None):
    engine = _db()
    try:
        with engine.begin() as conn:
            return conn.execute(text(sql), params or {}).scalar_one_or_none()
    finally:
        engine.dispose()


def _tabel_profil_ada() -> bool:
    return bool(
        _scalar(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = 'commodity_policies'"
        )
    )


pytestmark = pytest.mark.skipif(
    not _tabel_profil_ada(), reason="butuh migrasi 041 (tabel commodity_policies)"
)


def _id_komoditas(nama: str) -> str | None:
    nilai = _scalar("SELECT id FROM commodities WHERE name = :n", {"n": nama})
    return str(nilai) if nilai else None


def _profil_aktif(nama: str) -> dict | None:
    baris = _exec(
        "SELECT p.cold_chain_required, p.safe_temp_min_c, p.safe_temp_max_c, "
        "p.shelf_life_days, p.min_temperature_samples, "
        "p.max_observation_age_minutes, p.max_excursion_minutes, "
        "p.policy_version, p.policy_basis, p.policy_kind "
        "FROM commodity_policies p JOIN commodities c ON c.id = p.commodity_id "
        "WHERE lower(c.name) = :n AND p.is_active",
        {"n": nama.lower()},
    )
    if not baris:
        return None
    baris = baris[0]
    return {
        "commodity": nama,
        "cold_chain_required": baris[0],
        "safe_temp_min_c": None if baris[1] is None else float(baris[1]),
        "safe_temp_max_c": None if baris[2] is None else float(baris[2]),
        "shelf_life_days": float(baris[3]),
        "min_temperature_samples": int(baris[4]),
        "max_observation_age_minutes": baris[5],
        "max_excursion_minutes": float(baris[6]),
        "policy_version": baris[7],
        "policy_basis": baris[8],
        "policy_kind": baris[9],
    }


def _pastikan_komoditas() -> None:
    """Komoditas dasar ada; baris profil SENGAJA tidak dibuat di sini.

    Kalau fixture ini juga menulis profil, tes tidak membuktikan apa pun tentang
    seeder.
    """
    for nama in KOMODITAS:
        if _id_komoditas(nama) is None:
            _exec(
                "INSERT INTO commodities (id, name, unit) VALUES "
                "(CAST(:i AS uuid), :n, 'kg')",
                {"i": str(uuid.uuid4()), "n": nama},
            )


def test_seed_mengisi_profil_untuk_semua_komoditas():
    """DB yang dimigrasi sebelum diseed tidak boleh punya nol profil."""
    from app.seed.commodity_policies import seed_commodity_policies_sync

    _pastikan_komoditas()
    for nama in KOMODITAS:
        _exec(
            "DELETE FROM commodity_policies WHERE commodity_id = CAST(:i AS uuid)",
            {"i": _id_komoditas(nama)},
        )
        assert _profil_aktif(nama) is None, "prasyarat: profil sengaja dikosongkan"

    hasil = seed_commodity_policies_sync()

    for nama in KOMODITAS:
        profil = _profil_aktif(nama)
        assert profil is not None, f"{nama} tidak mendapat profil dari seeder"
        # Validasi yang sama dengan pembaca API/DB: dua pintu, satu aturan.
        validate_policy_row(profil)
    assert hasil["baru"] >= len(KOMODITAS), hasil


def test_seed_dua_kali_tidak_menggandakan_profil():
    """Idempoten lewat kunci bisnis, bukan primary key acak."""
    from app.seed.commodity_policies import seed_commodity_policies_sync

    _pastikan_komoditas()
    seed_commodity_policies_sync()
    sebelum = int(_scalar("SELECT count(*) FROM commodity_policies WHERE is_active"))

    seed_commodity_policies_sync()
    sesudah = int(_scalar("SELECT count(*) FROM commodity_policies WHERE is_active"))

    assert sesudah == sebelum, (
        "seed kedua menambah baris profil — kunci idempotensinya salah "
        f"({sebelum} → {sesudah})"
    )
    for nama in KOMODITAS:
        jumlah = int(
            _scalar(
                "SELECT count(*) FROM commodity_policies p JOIN commodities c "
                "ON c.id = p.commodity_id WHERE lower(c.name) = :n AND p.is_active",
                {"n": nama},
            )
        )
        assert jumlah == 1, f"{nama} punya {jumlah} profil aktif, harus tepat 1"


def test_profil_ambient_tidak_mendapat_rentang_dingin():
    from app.seed.commodity_policies import seed_commodity_policies_sync

    _pastikan_komoditas()
    seed_commodity_policies_sync()

    beras = _profil_aktif("beras")
    assert beras is not None
    assert beras["cold_chain_required"] is False
    assert beras["safe_temp_min_c"] is None and beras["safe_temp_max_c"] is None


def test_profil_rantai_dingin_lengkap():
    """Profil rantai dingin tanpa rentang/usia sampel ditolak constraint DB."""
    from app.seed.commodity_policies import seed_commodity_policies_sync

    _pastikan_komoditas()
    seed_commodity_policies_sync()

    for nama in ("telur", "ayam", "wortel"):
        profil = _profil_aktif(nama)
        assert profil is not None, nama
        assert profil["cold_chain_required"] is True
        assert profil["safe_temp_min_c"] is not None
        assert profil["safe_temp_max_c"] is not None
        assert profil["safe_temp_min_c"] < profil["safe_temp_max_c"]
        assert profil["min_temperature_samples"] >= 2
        assert profil["max_observation_age_minutes"] is not None


def test_profil_seeder_sama_dengan_bawaan_kode():
    """Nilai seeder tidak boleh berbeda diam-diam dari `PROFILES` di kode.

    Kalau keduanya berbeda, DB yang diseed dan DB yang belum diseed menjawab
    pertanyaan yang sama dengan aturan berbeda — persis yang Fase 3 tutup.
    """
    from app.seed.commodity_policies import seed_commodity_policies_sync

    _pastikan_komoditas()
    seed_commodity_policies_sync()

    for nama, bawaan in PROFILES.items():
        profil = _profil_aktif(nama)
        assert profil is not None, nama
        assert profil["cold_chain_required"] == bawaan.cold_chain_required
        assert profil["shelf_life_days"] == pytest.approx(
            float(bawaan.shelf_life_days), abs=0.01
        )
        assert profil["min_temperature_samples"] == bawaan.min_temperature_samples
        if bawaan.safe_temp_min_c is not None:
            assert profil["safe_temp_min_c"] == pytest.approx(
                float(bawaan.safe_temp_min_c), abs=0.01
            )
        if bawaan.max_observation_age_minutes is not None:
            assert profil["max_observation_age_minutes"] == bawaan.max_observation_age_minutes
        assert profil["policy_kind"] == bawaan.policy_kind
