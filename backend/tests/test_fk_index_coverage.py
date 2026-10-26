"""FK tanpa indeks pendukung — temuan audit lineage F-07.

Kenapa dijaga tes: Postgres TIDAK membuat indeks untuk kolom FK. Tanpa indeks,
`DELETE`/`UPDATE` pada tabel induk memicu sequential scan pada tabel anak, dan join
lewat FK jadi lambat tanpa gejala sampai data tumbuh. Audit menemukan 22 kolom FK
tanpa indeks pendukung; migrasi `033_indeks_fk_hilang` menambahkannya.

Tes membaca katalog, bukan daftar nama di kode. "Didukung" berarti kolom FK menjadi
kolom PERTAMA sebuah indeks — indeks gabungan yang menaruh kolom FK di posisi kedua
tidak dipakai Postgres untuk join FK.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings

QUERY_FK_TANPA_INDEKS = text(
    """
    SELECT c.conrelid::regclass::text AS tabel, a.attname AS kolom
    FROM pg_constraint c
    JOIN LATERAL unnest(c.conkey) AS k(attnum) ON true
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f'
      AND NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid AND i.indkey[0] = k.attnum
      )
    ORDER BY 1, 2
    """
)


def test_setiap_kolom_fk_punya_indeks_pendukung() -> None:
    engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg"))
    try:
        with engine.connect() as koneksi:
            baris = koneksi.execute(QUERY_FK_TANPA_INDEKS).all()
    except OperationalError as exc:  # DB tidak terjangkau: jangan menuduh skema
        pytest.skip(f"basis data tidak terjangkau: {type(exc).__name__}")
    except SQLAlchemyError as exc:  # pragma: no cover - katalog tak terbaca
        pytest.skip(f"katalog tidak terbaca: {type(exc).__name__}")
    finally:
        engine.dispose()

    belum = [f"{r[0]}.{r[1]}" for r in baris]
    assert belum == [], (
        "kolom FK tanpa indeks pendukung (tambahkan lewat migrasi, jangan manual):\n"
        + "\n".join(f"- {k}" for k in belum)
    )
