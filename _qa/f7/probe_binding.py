"""Diagnosa binding kasus komoditas: mengapa summary menjawab 409.

Menyemai sesi replay sementara, lalu mencetak untuk tiap kasus komoditas:
tipe keputusan, lokasi sumber/tujuan, pemasok keputusan, payload binding, dan
pemasok/lokasi/komoditas batch yang terikat. Sesi dihapus di akhir.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.demo import _seed_demo_cases
from app.models import (
    Batch,
    Decision,
    DecisionEvidence,
    DemandRecord,
    DemoSession,
    Location,
    PriceSignal,
)
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
            for info in hasil["commodity_cases"]:
                if info.get("skipped"):
                    continue
                d = await db.get(Decision, uuid.UUID(info["decision_id"]))
                bukti = (
                    (
                        await db.execute(
                            select(DecisionEvidence).where(
                                DecisionEvidence.decision_id == d.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                ikat = [
                    b.payload
                    for b in bukti
                    if (b.payload or {}).get("allocation_binding") is True
                ]
                print(f"\n[{info['case']}] decision_type={d.decision_type}")
                print(
                    f"  src={d.source_location_id} tgt={d.target_location_id} "
                    f"supplier={d.supplier_id} commodity={d.commodity_id}"
                )
                print(f"  binding={ikat}")
                for bid in ikat[0]["batch_ids"] if ikat else []:
                    b = await db.get(Batch, uuid.UUID(bid))
                    print(
                        f"  batch {bid[:8]} supplier={b.supplier_id} "
                        f"loc={b.location_id} commodity={b.commodity_id} "
                        f"safety={b.safety_status} qty={b.quantity_kg} "
                        f"usable_until={b.usable_until.isoformat()}"
                    )
                print(f"  sekarang={datetime.now(timezone.utc).isoformat()}")
    finally:
        async with maker() as db:
            for model in (DemandRecord, PriceSignal, Batch, Decision):
                await db.execute(delete(model).where(model.demo_session_id == sesi_id))
            await db.execute(delete(DemoSession).where(DemoSession.id == sesi_id))
            await db.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
