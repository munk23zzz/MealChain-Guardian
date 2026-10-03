"""Seed sintetis deterministik Sprint 1 (Task 10).

- `build_seed_rows(reference_time)` membangun seluruh row dari
  /data/seed/sprint1_seed.json + waktu referensi eksplisit — tanpa random.
- Idempotensi: setiap row memakai UUID5 (namespace proyek + natural key),
  sehingga dua load dengan reference time sama menghasilkan isi & jumlah sama.
"""

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db import create_engine, create_session_maker
from app.models import (
    Batch,
    Commodity,
    DemandRecord,
    Location,
    PriceSignal,
    SapMockMaterialStock,
    SapMockPurchaseOrder,
    Supplier,
    SupplyRecord,
)

SEED_PATH = Path(os.environ.get("SEED_PATH", "/data/seed/sprint1_seed.json"))

# Namespace tetap proyek — jangan pernah diubah (mengubah semua id seed)
SEED_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def stable_uuid(*parts: object) -> uuid.UUID:
    """UUID5 deterministik dari natural key."""
    return uuid.uuid5(SEED_NAMESPACE, "::".join(str(p) for p in parts))


def canonical_hash(payload: object) -> str:
    """Hash payload kanonik untuk bukti idempotensi."""
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path | None = None) -> dict:
    with open(path or SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_seed_rows(reference_time: datetime, seed_path: Path | None = None) -> dict:
    """Bangun semua row seed dari JSON + reference_time (wajib tz-aware)."""
    if reference_time.tzinfo is None:
        raise ValueError("reference_time wajib timezone-aware")

    data = _load_json(seed_path)
    ref = reference_time

    locations = [
        {
            "id": stable_uuid("location", loc["name"]),
            "name": loc["name"],
            "region": loc["region"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "role_hint": loc.get("role_hint"),
        }
        for loc in data["locations"]
    ]
    commodities = [
        {
            "id": stable_uuid("commodity", com["name"]),
            "name": com["name"],
            "unit": com.get("unit", "kg"),
        }
        for com in data["commodities"]
    ]
    suppliers = [
        {
            "id": stable_uuid("supplier", sup["name"]),
            "name": sup["name"],
            "location": sup["location"],
            "reliability_score": Decimal(str(sup["reliability_score"])),
        }
        for sup in data["suppliers"]
    ]

    supply = [
        {
            "id": stable_uuid("supply", s["location"], s["commodity"], ref.isoformat()),
            "location": s["location"],
            "commodity": s["commodity"],
            "quantity_kg": Decimal(str(s["quantity_kg"])),
            "recorded_at": ref,
            "source": s.get("source", "mock_sap"),
        }
        for s in data["supply"]
    ]

    demand = []
    for d in data["demand"]:
        obs = d["observations_kg"]
        interval = int(d["interval_days"])
        needed_by = ref + timedelta(days=int(d["needed_by_offset_days"]))
        for i, qty in enumerate(obs):
            recorded_at = ref - timedelta(days=interval * (len(obs) - 1 - i))
            demand.append(
                {
                    "id": stable_uuid(
                        "demand", d["location"], d["commodity"], recorded_at.isoformat()
                    ),
                    "location": d["location"],
                    "commodity": d["commodity"],
                    "quantity_kg": Decimal(str(qty)),
                    "needed_by": needed_by,
                    "recorded_at": recorded_at,
                }
            )

    price_signals = []
    for p in data["prices"]:
        source = p["source"]
        price_signals.append(
            {
                # Ruling Roy 2026-10-03: source memakai kontrak Schema.md
                # ('pihps_reference' | 'supplier_quote'); quote A/B/C dibedakan
                # oleh nilai harga — masuk natural key agar tetap deterministik unik.
                "id": stable_uuid(
                    "price",
                    p["location"],
                    p["commodity"],
                    source,
                    str(p["price_per_kg"]),
                    ref.isoformat(),
                ),
                "location": p["location"],
                "commodity": p["commodity"],
                "price_per_kg": Decimal(str(p["price_per_kg"])),
                "recorded_at": ref,
                "source": source,
            }
        )

    batches = []
    for b in data["batches"]:
        harvested_at = ref + timedelta(hours=float(b["harvested_at_offset_hours"]))
        score = float(b["freshness_score"])
        # Konversi temperature_log relatif → timestamp absolut (deterministik)
        temperature_log = [
            {
                "timestamp": (
                    ref + timedelta(hours=float(e["timestamp_offset_hours"]))
                ).isoformat(),
                "temperature_c": e["temperature_c"],
            }
            for e in b["temperature_log"]
        ]
        batches.append(
            {
                "id": stable_uuid("batch", b["code"]),
                "code": b["code"],
                "location": b["location"],
                "commodity": b["commodity"],
                "supplier": b["supplier"],
                "quantity_kg": Decimal(str(b["quantity_kg"])),
                "harvested_at": harvested_at,
                "shelf_life_days": float(b["shelf_life_days"]),
                "freshness_score": Decimal(str(b["freshness_score"])),
                "freshness_status": b["freshness_status"],
                "safety_status": b["safety_status"],
                "usable_until": harvested_at + timedelta(
                    days=float(b["shelf_life_days"]) * score
                ),
                "temperature_log": temperature_log,
                "certification_status": b.get("certification_status", "none"),
            }
        )

    material_stock = [
        {
            "id": stable_uuid("sap_stock", m["material_number"], m["plant"], m["batch"]),
            "material_number": m["material_number"],
            "plant": m["plant"],
            "storage_location": m.get("storage_location"),
            "batch": m.get("batch"),
            "quantity": Decimal(str(m["quantity"])),
            "unit": m["unit"],
        }
        for m in data["mock_sap"]["material_stock"]
    ]
    purchase_orders = [
        {
            "id": stable_uuid("sap_po", po["po_number"]),
            "po_number": po["po_number"],
            "supplier": po["supplier"],
            "material_number": po["material_number"],
            "ordered_quantity": Decimal(str(po["ordered_quantity"])),
            "price": Decimal(str(po["price"])),
            "status": po["status"],
        }
        for po in data["mock_sap"]["purchase_orders"]
    ]

    return {
        "locations": locations,
        "commodities": commodities,
        "suppliers": suppliers,
        "supply": supply,
        "demand": demand,
        "price_signals": price_signals,
        "batches": batches,
        "material_stock": material_stock,
        "purchase_orders": purchase_orders,
    }


async def load_seed(reference_time: datetime, seed_path: Path | None = None) -> dict:
    """Muat seed ke PostgreSQL secara idempoten (upsert by deterministic PK)."""
    rows = build_seed_rows(reference_time, seed_path)
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
    )
    engine = create_engine(database_url)
    maker = create_session_maker(engine)
    counts: dict[str, int] = {}
    try:
        async with maker() as session:
            loc_by_name = {
                r.name: r
                for r in (
                    await session.execute(select(Location))
                ).scalars()
            }
            com_by_name = {
                r.name: r
                for r in (
                    await session.execute(select(Commodity))
                ).scalars()
            }
            sup_by_name = {
                r.name: r
                for r in (
                    await session.execute(select(Supplier))
                ).scalars()
            }

            for item in rows["locations"]:
                existing = loc_by_name.get(item["name"])
                if existing is None:
                    session.add(Location(**item))
                    counts["locations"] = counts.get("locations", 0) + 1
            for item in rows["commodities"]:
                if item["name"] not in com_by_name:
                    session.add(Commodity(name=item["name"], unit=item["unit"]))
                    counts["commodities"] = counts.get("commodities", 0) + 1
            for item in rows["suppliers"]:
                if item["name"] not in sup_by_name:
                    session.add(
                        Supplier(
                            name=item["name"],
                            location_id=loc_by_name[item["location"]].id,
                            reliability_score=item["reliability_score"],
                        )
                    )
                    counts["suppliers"] = counts.get("suppliers", 0) + 1
            await session.flush()

            loc_by_name = {
                r.name: r for r in (await session.execute(select(Location))).scalars()
            }
            com_by_name = {
                r.name: r for r in (await session.execute(select(Commodity))).scalars()
            }
            sup_by_name = {
                r.name: r for r in (await session.execute(select(Supplier))).scalars()
            }
            stock_map = {
                (r.material_number, r.plant, r.batch): r
                for r in (
                    await session.execute(select(SapMockMaterialStock))
                ).scalars()
            }
            po_map = {
                r.po_number: r
                for r in (
                    await session.execute(select(SapMockPurchaseOrder))
                ).scalars()
            }

            for item in rows["supply"]:
                await session.merge(
                    SupplyRecord(
                        id=item["id"],
                        location_id=loc_by_name[item["location"]].id,
                        commodity_id=com_by_name[item["commodity"]].id,
                        quantity_kg=item["quantity_kg"],
                        recorded_at=item["recorded_at"],
                        source=item["source"],
                    )
                )
            for item in rows["demand"]:
                await session.merge(
                    DemandRecord(
                        id=item["id"],
                        location_id=loc_by_name[item["location"]].id,
                        commodity_id=com_by_name[item["commodity"]].id,
                        quantity_kg=item["quantity_kg"],
                        needed_by=item["needed_by"],
                        recorded_at=item["recorded_at"],
                    )
                )
            for item in rows["price_signals"]:
                await session.merge(
                    PriceSignal(
                        id=item["id"],
                        location_id=loc_by_name[item["location"]].id,
                        commodity_id=com_by_name[item["commodity"]].id,
                        price_per_kg=item["price_per_kg"],
                        recorded_at=item["recorded_at"],
                        source=item["source"],
                    )
                )
            for item in rows["batches"]:
                await session.merge(
                    Batch(
                        id=item["id"],
                        location_id=loc_by_name[item["location"]].id,
                        commodity_id=com_by_name[item["commodity"]].id,
                        supplier_id=sup_by_name[item["supplier"]].id,
                        quantity_kg=item["quantity_kg"],
                        harvested_at=item["harvested_at"],
                        temperature_log=item["temperature_log"],
                        certification_status=item["certification_status"],
                        freshness_score=item["freshness_score"],
                        safety_status=item["safety_status"],
                        usable_until=item["usable_until"],
                        seed_key=item["code"],
                    )
                )
            for item in rows["material_stock"]:
                existing_stock = stock_map.get(
                    (item["material_number"], item["plant"], item["batch"])
                )
                if existing_stock is not None:
                    existing_stock.storage_location = item["storage_location"]
                    existing_stock.quantity = item["quantity"]
                    existing_stock.unit = item["unit"]
                else:
                    session.add(
                        SapMockMaterialStock(
                            id=item["id"],
                            material_number=item["material_number"],
                            plant=item["plant"],
                            storage_location=item["storage_location"],
                            batch=item["batch"],
                            quantity=item["quantity"],
                            unit=item["unit"],
                        )
                    )
            for item in rows["purchase_orders"]:
                existing_po = po_map.get(item["po_number"])
                if existing_po is not None:
                    existing_po.supplier_id = sup_by_name[item["supplier"]].id
                    existing_po.material_number = item["material_number"]
                    existing_po.ordered_quantity = item["ordered_quantity"]
                    existing_po.price = item["price"]
                    existing_po.status = item["status"]
                else:
                    session.add(
                        SapMockPurchaseOrder(
                            id=item["id"],
                            po_number=item["po_number"],
                            supplier_id=sup_by_name[item["supplier"]].id,
                            material_number=item["material_number"],
                            ordered_quantity=item["ordered_quantity"],
                            price=item["price"],
                            status=item["status"],
                        )
                    )
            await session.commit()
    finally:
        await engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Sprint 1 deterministik")
    parser.add_argument("--reference-time", required=True, help="ISO 8601 tz-aware")
    args = parser.parse_args()
    ref = datetime.fromisoformat(args.reference_time)
    if ref.tzinfo is None:
        raise SystemExit("reference-time wajib timezone-aware, mis. 2026-10-01T12:00:00+00:00")
    counts = asyncio.run(load_seed(ref))
    print(f"Seed selesai (idempoten). Row baru: {counts or '{}'}")


if __name__ == "__main__":
    main()
