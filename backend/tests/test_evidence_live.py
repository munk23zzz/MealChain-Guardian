"""Task 16 follow-up: evidence.batch_ids wajib terisi di jalur live.

Temuan reviewer terpisah (deleg_586e9481): API evidence.batch_ids = []
pada jalur DB. Cacat evidence-audit: kandidat harus menunjuk batch
sumbernya (traceability). Reproduksi end-to-end: service live (DB seed
riil) wajib memancarkan batch_ids non-kosong pada kandidat
Cianjur→Jakarta telur.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import recommendation_service as rs

_AURL = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"


def test_live_evidence_batch_ids_nonempty():
    engine = create_async_engine(_AURL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _run():
        async with session_maker() as db:
            out = await rs.build_recommendations(
                lambda: rs.fetch_operational_facts(db, None)
            )
        await engine.dispose()
        return out

    out = asyncio.run(_run())
    recs = out["recommendations"]
    assert recs, "service live wajib menghasilkan kandidat"

    def _find(src, dst, com):
        return next(
            r
            for r in recs
            if r["candidate"]["source_location"] == src
            and r["candidate"]["destination_location"] == dst
            and r["candidate"]["commodity"] == com
        )

    top = _find("Cianjur", "Jakarta", "telur")
    assert top["candidate"]["source_location"] == "Cianjur"
    assert top["candidate"]["destination_location"] == "Jakarta"
    ids = top["evidence"]["batch_ids"]
    assert isinstance(ids, list) and len(ids) > 0
    assert all(isinstance(x, str) and len(x) == 36 for x in ids)
