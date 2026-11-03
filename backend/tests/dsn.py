"""DSN sinkron untuk tes — mengikuti `DATABASE_URL` bila di-set.

Kenapa ada berkas ini (temuan 21 Okt 2026): puluhan tes memaku DSN
`postgresql+psycopg://.../mealchain`. Akibatnya suite hanya bisa berjalan di DB
demo: fixture menulis (mis. user untuk login) ke `mealchain`, sementara aplikasi
di bawah test membaca DB lain bila `DATABASE_URL` dialihkan — hasilnya 401
"email atau password salah" dan puluhan error yang tampak seperti cacat produk.

Dengan satu konstanta ini, `DATABASE_URL=...mealchain_gate` membuat fixture dan
aplikasi menunjuk DB yang sama, sehingga gate bisa dijalankan pada DB terpisah
tanpa menyentuh DB demo.
"""

from __future__ import annotations

import os

_DSN_ASYNC_DEFAULT = (
    "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
)


def dsn_sync(dsn_asyncpg: str | None = None) -> str:
    """DSN psycopg (sinkron) dari DSN asyncpg aplikasi."""
    dasar = dsn_asyncpg or os.environ.get("DATABASE_URL") or _DSN_ASYNC_DEFAULT
    return (
        dasar.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        .replace("postgres://", "postgresql+psycopg://")
    )


#: DSN asyncpg (untuk engine async di fixture).
DSN_ASYNC = os.environ.get("DATABASE_URL") or _DSN_ASYNC_DEFAULT

#: Dipakai tes sebagai `ENGINE_URL` / `DB_URL` / DSN langsung.
DSN_SYNC = dsn_sync()
