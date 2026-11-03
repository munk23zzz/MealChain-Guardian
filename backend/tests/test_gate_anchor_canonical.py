"""Gerbang hanya sah di DB yang snapshot kanoniknya berada di JANGKAR.

Kenapa ada berkas ini (26 Okt 2026): setelah tombol "Segarkan ke hari ini" ditekan,
snapshot kanonik pindah ke rentang hari ini. Banyak tes memaku hal-hal yang hanya
benar pada jangkar (8 Okt 12:00): stempel deret, angka 4.900 kg, "3 surplus : 7
shortage". Pada DB yang sudah digeser, hasilnya 7 kegagalan yang tampak seperti bug
produk padahal hanya jangkar yang berbeda — dan lebih buruk lagi, generator deret
demo tidak bisa menulis baris apa pun karena stempel yang sama sudah ditempati
baris kanonik (bentrok kunci bisnis, `ON CONFLICT ... WHERE origin='demo'`).

Tes ini mengubah kebingungan itu menjadi satu pesan yang jelas: DB ini bukan DB
gerbang. Perbaikannya: jalankan gerbang pada DB yang disemai ulang pada `CANONICAL_REF`
(`load_seed(CANONICAL_REF)`), atau kembalikan snapshot seperti prosedur rollback.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.seed.timeseries import CANONICAL_REF

QUERY_PASANGAN = text(
    """
    WITH pasangan AS (
        SELECT l.id AS location_id, c.id AS commodity_id
        FROM locations l CROSS JOIN commodities c
    )
    SELECT count(*) FROM pasangan p
    WHERE NOT EXISTS (
        SELECT 1 FROM supply_records s
        WHERE s.location_id = p.location_id
          AND s.commodity_id = p.commodity_id
          AND s.origin = 'seed'
          AND s.recorded_at = :ref
    )
    """
)


def test_snapshot_kanonik_berada_di_jangkar() -> None:
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg"))
    try:
        with engine.connect() as koneksi:
            pasangan_tanpa_jangkar = int(
                koneksi.execute(QUERY_PASANGAN, {"ref": CANONICAL_REF}).scalar() or 0
            )
            total = int(
                koneksi.execute(
                    text(
                        "SELECT count(*) FROM locations l CROSS JOIN commodities c"
                    )
                ).scalar()
                or 0
            )
    except OperationalError as exc:
        pytest.skip(f"basis data tidak terjangkau: {type(exc).__name__}")
    except SQLAlchemyError as exc:  # pragma: no cover
        pytest.skip(f"katalog tidak terbaca: {type(exc).__name__}")
    finally:
        engine.dispose()

    if total == 0:
        pytest.skip("DB belum punya master data (lokasi/komoditas)")

    assert pasangan_tanpa_jangkar == 0, (
        f"{pasangan_tanpa_jangkar} dari {total} pasangan lokasi×komoditas tidak punya "
        f"baris kanonik pada jangkar {CANONICAL_REF.isoformat()}.\n"
        "DB ini sudah digeser (mis. tombol 'Segarkan ke hari ini'), jadi BUKAN DB "
        "gerbang: tes yang memaku jangkar akan gagal dan deret demo tidak bisa ditulis.\n"
        "Pakai DB yang disemai ulang pada CANONICAL_REF sebelum menjalankan gate."
    )
