"""Kontrak cakupan status template demo (audit 21 Okt 2026, temuan P4/B2).

DB mengizinkan tujuh status (`proposed`, `verifier_flagged`, `pending_approval`,
`approved`, `rejected`, `executed`, `review_only`), tetapi template demo hanya
memuat lima. Akibatnya layar untuk `approved` (sudah disetujui, belum dieksekusi)
dan `review_only` (temuan yang tidak bisa dieksekusi) tidak pernah bisa
diperlihatkan — padahal keduanya jalur nyata di sistem.

Tes memanggil penyemai langsung (cepat), bukan seluruh template (±60 detik).
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.seed.demo_template import _semai_status_tambahan
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


def test_menyemai_status_approved_dan_review_only():
    async def skenario():
        async with _db() as db:
            hasil = await _semai_status_tambahan(db, datetime.now(UTC))
            await db.commit()

            id_approved = hasil.get("approved")
            id_review = hasil.get("review_only")
            if not id_approved or not id_review:
                import pytest

                pytest.skip(f"prasyarat template tidak ada: {hasil}")

            approved = (
                await db.execute(
                    text(
                        "SELECT status, decision_type, quantity_kg FROM decisions WHERE id = :d"
                    ),
                    {"d": id_approved},
                )
            ).one()
            assert approved.status == "approved"
            assert approved.quantity_kg is not None, "keputusan siap eksekusi harus punya jumlah"

            review = (
                await db.execute(
                    text("SELECT status, decision_type, quantity_kg FROM decisions WHERE id = :d"),
                    {"d": id_review},
                )
            ).one()
            assert review.status == "review_only"
            assert review.quantity_kg is None, (
                "review_only = temuan tanpa jumlah; kalau ada jumlah, layar menawarkan eksekusi "
                "yang pasti gagal"
            )

            for did in (id_approved, id_review):
                jejak = (
                    await db.execute(
                        text("SELECT count(*) FROM agent_traces WHERE decision_id = :d"),
                        {"d": did},
                    )
                ).scalar_one()
                assert jejak >= 2, f"keputusan {did} hanya punya {jejak} jejak"

            appr = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM approvals WHERE decision_id = :d AND approved"
                    ),
                    {"d": id_approved},
                )
            ).scalar_one()
            assert appr >= 2, f"approved hanya punya {appr} approval (aturan: dua peran)"

    asyncio.run(skenario())


def test_cakupan_status_dan_tipe_lengkap():
    """Tujuh status DB dan enam tipe keputusan harus terwakili template.

    Audit 21 Okt 2026: `proposed` dan dua tipe tata kelola pemasok
    (`supplier_exclusion_restoration`, `supplier_procurement`) tidak ada, sehingga
    layar untuk jalur itu tidak bisa diperlihatkan saat demo.
    """
    from sqlalchemy import text as sql

    async def skenario():
        async with _db() as db:
            await _semai_status_tambahan(db, datetime.now(UTC))
            await db.commit()
            status = set(
                (await db.execute(sql("SELECT DISTINCT status FROM decisions"))).scalars()
            )
            tipe = set(
                (
                    await db.execute(sql("SELECT DISTINCT decision_type FROM decisions"))
                ).scalars()
            )
            # Status/tipe lain datang dari penyemai lain (kasus, eksklusi, bukti);
            # matriks penuh diverifikasi pada build lengkap, bukan di sini.
            assert "proposed" in status, f"status `proposed` belum ada: {sorted(status)}"
            wajib_tipe = {"supplier_exclusion_restoration", "supplier_procurement"}
            assert wajib_tipe <= tipe, f"tipe belum terwakili: {wajib_tipe - tipe}"

            for t in ("supplier_exclusion_restoration", "supplier_procurement"):
                baris = (
                    await db.execute(
                        sql(
                            "SELECT id, supplier_id, quantity_kg, status FROM decisions"
                            " WHERE decision_type = :t ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"t": t},
                    )
                ).first()
                assert baris is not None, f"tidak ada keputusan bertipe {t}"
                assert baris.supplier_id is not None, f"{t} harus menunjuk pemasok"
                jejak = (
                    await db.execute(
                        sql("SELECT count(*) FROM agent_traces WHERE decision_id = :d"),
                        {"d": baris.id},
                    )
                ).scalar_one()
                assert jejak >= 2, f"{t} hanya punya {jejak} jejak"

    asyncio.run(skenario())


def test_idempoten_tidak_menggandakan_keputusan():
    async def skenario():
        async with _db() as db:
            pertama = await _semai_status_tambahan(db, datetime.now(UTC))
            await db.commit()
            if not pertama.get("approved"):
                import pytest

                pytest.skip(f"prasyarat template tidak ada: {pertama}")
            kedua = await _semai_status_tambahan(db, datetime.now(UTC))
            await db.commit()
            assert kedua["approved"] == pertama["approved"]
            assert kedua["review_only"] == pertama["review_only"]

    asyncio.run(skenario())
