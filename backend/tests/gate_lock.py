"""Kunci gerbang: satu suite pytest pada satu waktu, per database.

Kenapa ada: seluruh tes memakai database kerja yang SAMA dengan aplikasi demo
(DSN ditulis eksplisit di `conftest.py`). Dua suite yang berjalan bersamaan —
mis. sesi kerja lain menjalankan gerbangnya sendiri — saling menghapus baris
dan saling mencabut token, sehingga hasilnya merah di berkas yang tidak
disentuh siapa pun. Gejala khasnya `401 "token tidak valid"`, `DeadlockDetected`
dan kegagalan yang hilang saat berkasnya dijalankan sendiri.

Kunci ini memakai `pg_try_advisory_lock` (non-blocking) supaya suite kedua
BERHENTI dengan pesan jelas alih-alih menunggu atau, lebih buruk, mencampur
state. Kunci dilepas otomatis oleh Postgres bila prosesnya mati.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

# Kunci global untuk semua suite repo ini; angka apa pun asal tetap.
KUNCI_GERBANG = 771_204_518


def dsn_psycopg(dsn_asyncpg: str) -> str:
    """Ubah DSN asyncpg aplikasi menjadi DSN psycopg sinkron."""
    return (
        dsn_asyncpg.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        .replace("postgres://", "postgresql+psycopg://")
    )


def ambil_kunci(dsn: str, kunci: int = KUNCI_GERBANG) -> tuple[Engine, Connection] | None:
    """Coba pegang kunci gerbang.

    Kembalian `None` berarti ada suite lain yang sedang berjalan (atau DB tidak
    terjangkau). Pemanggil memutuskan: pada DB tak terjangkau, lanjutkan saja
    (test host tanpa Postgres); pada kunci terpegang suite lain, berhenti.
    """
    engine = create_engine(dsn, pool_pre_ping=True)
    try:
        koneksi = engine.connect()
    except Exception:
        engine.dispose()
        raise
    hasil = koneksi.execute(
        text("SELECT pg_try_advisory_lock(:k)"), {"k": kunci}
    ).scalar()
    if not hasil:
        koneksi.close()
        engine.dispose()
        return None
    return engine, koneksi


def lepas_kunci(pegangan: tuple[Engine, Connection], kunci: int = KUNCI_GERBANG) -> None:
    engine, koneksi = pegangan
    try:
        koneksi.execute(
            text("SELECT pg_advisory_unlock(:k)"), {"k": kunci}
        )
        koneksi.close()
    finally:
        engine.dispose()
