"""Probe Fase 7 butir 6: apa yang DILIHAT operator untuk kasus usable vs on_hold.

Menyemai tiga kasus komoditas ke sesi replay sementara di DB yang ditunjuk
`DATABASE_URL` (klon), lalu mencetak read model approval-summary untuk kasus
`wortel-coldchain-sah` (usable) dan `wortel-coldchain-hold` (on_hold):
status, can_approve, can_execute, safety, dan blocking_reasons.

Sesi uji dihapus lagi di akhir. Skrip ini baca-tulis hanya pada sesinya sendiri.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.demo import _seed_demo_cases
from app.models import Batch, Decision, DemandRecord, DemoSession, Location, PriceSignal
from app.services.approval_summary import build_approval_summary
from tests.dsn import DSN_ASYNC

JANGKAR = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
VERSI = "kanon-2026-10-08T12:00:00Z"


async def main() -> None:
    engine = create_async_engine(DSN_ASYNC)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    sesi_id = uuid.uuid4()
    try:
        async with maker() as db:
            db.add(
                DemoSession(
                    id=sesi_id,
                    status="ended",
                    started_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc),
                    anchor_now=datetime.now(timezone.utc),
                    mode="replay",
                    evaluation_anchor=JANGKAR,
                    dataset_version=VERSI,
                )
            )
            await db.flush()
            target = (
                (await db.execute(select(Location).where(Location.name == "Jakarta")))
                .scalars()
                .one()
            )
            hasil = await _seed_demo_cases(
                db,
                True,
                target,
                demo_session_id=sesi_id,
                mode="replay",
                anchor=JANGKAR,
                dataset_version=VERSI,
            )
            await db.commit()
            print(f"seed: mode={hasil['mode']} anchor={hasil['evaluation_anchor']} "
                  f"kasus={hasil['cases_total']} sumber_suhu={hasil['temperature_source']}")
            for info in hasil["commodity_cases"]:
                if info.get("skipped"):
                    print(f"  {info['case']}: DILEWATI — {info['skipped']}")
            for key in ("wortel-coldchain-sah", "wortel-coldchain-hold", "beras-ambient"):
                info = next(i for i in hasil["commodity_cases"] if i["case"] == key)
                keputusan = await db.get(Decision, uuid.UUID(info["decision_id"]))
                ringkas = await build_approval_summary(db, keputusan)
                print(f"\n[{key}] outcome={info['outcome']} status={ringkas['status']}")
                print(f"  can_approve={ringkas['can_approve']} "
                      f"can_execute={ringkas['can_execute']} "
                      f"valid={ringkas['expiry']['valid']} "
                      f"sisa={ringkas['expiry']['seconds_remaining']}s")
                print(f"  safety={ringkas['safety']}")
                print(f"  blocking={ringkas['blocking_reasons']}")
                print(f"  supplier={(ringkas['supplier'] or {}).get('name')} "
                      f"sdc={ringkas['safe_delivered_cost']}")
    finally:
        async with maker() as db:
            for model in (DemandRecord, PriceSignal, Batch, Decision):
                await db.execute(
                    delete(model).where(model.demo_session_id == sesi_id)
                )
            await db.execute(delete(DemoSession).where(DemoSession.id == sesi_id))
            await db.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
