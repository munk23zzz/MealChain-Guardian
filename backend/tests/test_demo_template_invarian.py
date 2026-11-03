"""Kontrak template demo: keputusan contoh harus patuh aturan domain yang sama.

Audit 21 Okt 2026 menemukan tiga pelanggaran pada data contoh yang dibangun
"Siapkan data demo":

1. Dua keputusan `supplier_exclusion` (satu `executed`, satu `pending_approval`)
   tidak punya satu pun baris `agent_traces` → Agent Log/Decision & Evidence kosong.
2. Keputusan `executed` itu juga tidak punya baris `approvals` yang `approved`,
   padahal aturan keras proyek (Rules.md §1.2) mewajibkan approval manusia sebelum
   aksi berisiko tinggi dieksekusi — dan alur tulis nyata memaksa dua approval
   (409 bila baru satu, terbukti di `verify/decisions.spec.json`).

Tes ini memanggil penyemai eksklusi langsung (cepat, ±1 detik), bukan seluruh
template (±60 detik), lalu memeriksa invariannya — termasuk untuk baris yang
SUDAH ada dari seed lama, karena fungsi itu idempoten dan harus menambal.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.seed.demo_template import _semai_eksklusi
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DSN = os.environ.get(
    "TEST_DATABASE_URL",
    DSN_ASYNC,
)


@asynccontextmanager
async def _db():
    engine = create_async_engine(DSN)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


def test_eksklusi_punya_jejak_dan_persetujuan():
    async def skenario():
        async with _db() as db:
            hasil = await _semai_eksklusi(db, datetime.now(UTC))
            await db.commit()

            # `aktif`/`menunggu` adalah id BARIS EKSKLUSI; yang diuji jejaknya
            # adalah id KEPUTUSAN (`putusan_*`) — dua entitas berbeda.
            id_aktif = hasil.get("putusan_aktif")
            id_menunggu = hasil.get("putusan_menunggu")
            if not id_aktif or not id_menunggu:
                # Prasyarat seed (Jakarta, akun kepala, ≥2 pemasok non-HACCP)
                # tidak ada di DB ini: lewati dengan alasan jelas, bukan lolos diam.
                import pytest

                pytest.skip(f"prasyarat seed tidak ada: {hasil}")

            def skalar(sql: str, **p):
                return db.execute(text(sql), p)

            # 1. Setiap keputusan eksklusi punya jejak langkah.
            for label, did in (("aktif", id_aktif), ("menunggu", id_menunggu)):
                n = (
                    await skalar(
                        "SELECT count(*) FROM agent_traces WHERE decision_id = :d", d=did
                    )
                ).scalar_one()
                assert n >= 2, f"keputusan eksklusi {label} hanya punya {n} jejak langkah"
                langkah = (
                    await skalar(
                        "SELECT array_agg(step_name ORDER BY step_at) FROM agent_traces"
                        " WHERE decision_id = :d",
                        d=did,
                    )
                ).scalar_one()
                assert "DETECT" in langkah, f"jejak {label} tanpa DETECT: {langkah}"
                assert "DECIDE" in langkah, f"jejak {label} tanpa DECIDE: {langkah}"

            # 2. Keputusan yang SUDAH dieksekusi wajib punya approval manusia.
            n_appr = (
                await skalar(
                    "SELECT count(*) FROM approvals WHERE decision_id = :d AND approved",
                    d=id_aktif,
                )
            ).scalar_one()
            assert n_appr >= 2, f"keputusan executed hanya punya {n_appr} approval (butuh 2)"

            # 3. Jejak & approval harus menunjuk keputusan yang benar-benar ada.
            yatim = (
                await skalar(
                    "SELECT count(*) FROM agent_traces t LEFT JOIN decisions d"
                    " ON d.id = t.decision_id WHERE d.id IS NULL"
                )
            ).scalar_one()
            assert yatim == 0

    asyncio.run(skenario())


def test_eksklusi_idempoten_tidak_menggandakan_jejak():
    async def skenario():
        async with _db() as db:
            hasil = await _semai_eksklusi(db, datetime.now(UTC))
            await db.commit()
            id_aktif = hasil.get("putusan_aktif")
            if not id_aktif:
                import pytest

                pytest.skip(f"prasyarat seed tidak ada: {hasil}")

            def hitung():
                return db.execute(
                    text("SELECT count(*) FROM agent_traces WHERE decision_id = :d"),
                    {"d": id_aktif},
                )

            sebelum = (await hitung()).scalar_one()
            await _semai_eksklusi(db, datetime.now(UTC))
            await db.commit()
            sesudah = (await hitung()).scalar_one()
            assert sesudah == sebelum, f"jejak bertambah {sebelum} → {sesudah} pada run kedua"

    asyncio.run(skenario())
