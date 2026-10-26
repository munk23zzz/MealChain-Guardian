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

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.journey import dispatch_time, validate_dispatch
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
from app.seed.demo_credentials import AkunDemo, DemoCredentialError, resolve_demo_password
from app.seed.supplier_profile import derive_supplier_profiles

SEED_PATH = Path(os.environ.get("SEED_PATH", "/data/seed/sprint1_seed.json"))


def _seed_database_url() -> str:
    """URL DB untuk seed (sinkron psycopg) — target penulisan = target baca.

    Audit 21 Okt 2026 (keselamatan data): fungsi ini dulu hanya membaca
    `SEED_DATABASE_URL` lalu jatuh ke DSN compose, MENGABAIKAN `DATABASE_URL`.
    Skrip/uji yang menunjuk salinan (`DATABASE_URL=…/mealchain_audit`) tetap
    menulis akun & data demo ke DB demo utama — terbukti saat verifikasi template
    di DB salinan: `users` salinan tetap kosong, DB utama menerima merge-nya.

    Urutan: `SEED_DATABASE_URL` (eksplisit) → `DATABASE_URL` (asyncpg→psycopg)
    → DSN compose.
    """
    eksplisit = os.environ.get("SEED_DATABASE_URL")
    if eksplisit:
        return eksplisit
    utama = os.environ.get("DATABASE_URL")
    if utama:
        return utama.replace("+asyncpg", "+psycopg")
    return "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

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
    # Profil pemasok kanonik DITURUNKAN dari batch kiriman (keputusan pemilik
    # 2026-10-16): `commodity` + `certification_status` saja, dan hanya bila
    # datanya memang ada. `capacity_kg_per_week` TIDAK diturunkan - tidak ada
    # sumbernya. Aturan lengkap + tes: app/seed/supplier_profile.py.
    profiles = derive_supplier_profiles(
        data["batches"], [sup["name"] for sup in data["suppliers"]]
    )
    suppliers = [
        {
            "id": stable_uuid("supplier", sup["name"]),
            "name": sup["name"],
            "location": sup["location"],
            "reliability_score": Decimal(str(sup["reliability_score"])),
            "commodity": profiles[sup["name"]]["commodity"],
            "certification_status": profiles[sup["name"]]["certification_status"],
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
        # Revisi kedua Roy 2026-10-03: source generik dua nilai
        # ('pihps_reference' | 'supplier_quote'); identitas supplier pada kolom
        # supplier_id (FK), TIDAK dienkode ke dalam string source.
        supplier_name = p.get("supplier")
        if source == "supplier_quote" and not supplier_name:
            raise ValueError(
                f"quote {p['location']}/{p['commodity']} wajib punya field 'supplier'"
            )
        price_signals.append(
            {
                "id": stable_uuid(
                    "price",
                    p["location"],
                    p["commodity"],
                    source,
                    supplier_name or "",
                    ref.isoformat(),
                ),
                "location": p["location"],
                "commodity": p["commodity"],
                "supplier": supplier_name,
                "price_per_kg": Decimal(str(p["price_per_kg"])),
                "recorded_at": ref,
                "source": source,
            }
        )

    batches = []
    for b in data["batches"]:
        harvested_at = ref + timedelta(hours=float(b["harvested_at_offset_hours"]))
        score = float(b["freshness_score"])
        # Jam berangkat kiriman: `null` di berkas seed = barang belum berangkat
        # (NULL di DB), bukan jam nol. Urutannya divalidasi di sini supaya berkas
        # seed yang salah tidak pernah sampai ke DB.
        dispatched_at = dispatch_time(ref, b.get("dispatch_offset_hours"))
        validate_dispatch(harvested_at, dispatched_at)
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
                "dispatched_at": dispatched_at,
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

    # ---- P6 (keputusan Roy 2026-10-09): facts KPI Meal Continuity & Food
    # Loss. Deterministik & idempoten (stable_uuid): 7 hari terakhir berisi
    # plan porsi per lokasi, delivery, dan disposal event. Rasio continuity
    # ~97-99% (1 hari shortfall kecil di Bogor) — angka live nyata dari DB,
    # bukan angka PRD.
    menu_plans = []
    delivery_events = []
    disposal_events = []
    for loc in data["locations"]:
        base = 1200 if loc["region"] != "Sumatera" else 900
        for day in range(1, 8):
            plan_date = (ref - timedelta(days=day)).date()
            menu_plans.append({
                "id": stable_uuid("menu_plan", loc["name"], plan_date.isoformat()),
                "location": loc["name"],
                "plan_date": plan_date,
                "planned_portions": base,
            })
            delivered = base - (24 if (loc["name"] == "Bogor" and day == 3) else 0)
            delivery_events.append({
                "id": stable_uuid("delivery", loc["name"], plan_date.isoformat()),
                "menu_plan": stable_uuid("menu_plan", loc["name"], plan_date.isoformat()),
                "delivered_portions": delivered,
                "status": "delivered",
                "delivered_at": ref - timedelta(days=day, hours=-2),
            })
            if day in (2, 5):
                disposal_events.append({
                    "id": stable_uuid("disposal", loc["name"], str(day)),
                    "location": loc["name"],
                    "commodity": "telur",
                    "quantity_kg": Decimal("6") if day == 2 else Decimal("4"),
                    "reason": "expired_transport" if day == 2 else "spoilage_cold_chain",
                    "disposed_at": ref - timedelta(days=day),
                })

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
        "menu_plans": menu_plans,
        "delivery_events": delivery_events,
        "disposal_events": disposal_events,
    }


async def sync_routes_after_seed(reference_time: datetime) -> dict:
    """Sinkronkan rute JALAN (OSRM) sesudah batch ada di DB.

    Dipanggil di akhir seeding (keputusan pemilik 2026-10-16: rute diambil saat
    seeding/sync, bukan saat peta dibuka). Jaringan mati TIDAK menggagalkan
    seeding: laporan gagal dicetak, dan peta akan menulis "belum disinkronkan".
    """
    from app.seed.road_routes import sync_road_routes

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain",
    )
    engine = create_engine(database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            return await sync_road_routes(session, now=reference_time)
    finally:
        await engine.dispose()


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
            # Peta nama→objek dibangun SEBELUM baris baru ditambahkan, sehingga
            # pada DB kosong (CI / gerbang terisolasi) pemasok pertama yang
            # menunjuk lokasi/komoditas baru gagal `KeyError` (mis. 'Cianjur').
            # Setelah flush, id baris baru sudah ada → bangun ulang petanya.
            await session.flush()
            loc_by_name = {
                r.name: r for r in (await session.execute(select(Location))).scalars()
            }
            com_by_name = {
                r.name: r for r in (await session.execute(select(Commodity))).scalars()
            }

            for item in rows["suppliers"]:
                existing = sup_by_name.get(item["name"])
                if existing is None:
                    session.add(
                        Supplier(
                            name=item["name"],
                            location_id=loc_by_name[item["location"]].id,
                            reliability_score=item["reliability_score"],
                            commodity_id=(
                                com_by_name[item["commodity"]].id
                                if item["commodity"] in com_by_name
                                else None
                            ),
                            certification_status=item["certification_status"],
                        )
                    )
                    counts["suppliers"] = counts.get("suppliers", 0) + 1
                else:
                    if existing.reliability_score != item["reliability_score"]:
                        # Baris kanonik warisan (dibuat sebelum skor JSON terpasang,
                        # jadi mewarisi DEFAULT 0.80 kolom) DIKOREKSI ke nilai berkas
                        # kanonik. Tanpa ini, skor pemasok yang dipakai mesin
                        # rekomendasi (`services/recommendation_service.py`) diam-diam
                        # bukan skor yang tertulis di `data/seed/sprint1_seed.json`.
                        # Hanya skor: id lokasi/komoditas/sertifikasi tidak disentuh
                        # supaya seeder tetap tidak merombak identitas baris.
                        existing.reliability_score = item["reliability_score"]
                        counts["suppliers_corrected"] = (
                            counts.get("suppliers_corrected", 0) + 1
                        )
                    # Profil kanonik: ISI HANYA CELAH KOSONG (keputusan pemilik
                    # 2026-10-16). Nilai yang sudah terisi - mis. pemasok demo
                    # Jabodetabek - tidak pernah ditimpa, dan kapasitas mingguan
                    # tidak disentuh sama sekali karena tidak ada sumbernya.
                    if existing.commodity_id is None and item["commodity"] in com_by_name:
                        existing.commodity_id = com_by_name[item["commodity"]].id
                        counts["suppliers_commodity_filled"] = (
                            counts.get("suppliers_commodity_filled", 0) + 1
                        )
                    if (
                        existing.certification_status is None
                        and item["certification_status"]
                    ):
                        existing.certification_status = item["certification_status"]
                        counts["suppliers_certification_filled"] = (
                            counts.get("suppliers_certification_filled", 0) + 1
                        )
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
                        supplier_id=(
                            sup_by_name[item["supplier"]].id
                            if item.get("supplier")
                            else None
                        ),
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
                        dispatched_at=item["dispatched_at"],
                        temperature_log=item["temperature_log"],
                        certification_status=item["certification_status"],
                        freshness_score=item["freshness_score"],
                        safety_status=item["safety_status"],
                        usable_until=item["usable_until"],
                    )
                )
            # Batch dari data acuan bisa memakai pemasok yang komoditasnya beda
            # (mis. beras dipasok pemasok telur). Rapikan sebelum dipakai.
            from app.seed.rapikan import rapikan_pemasok_batch

            await rapikan_pemasok_batch(session)

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
                    counts["sap_mock_material_stock"] = (
                        counts.get("sap_mock_material_stock", 0) + 1
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
                    counts["sap_mock_purchase_orders"] = (
                        counts.get("sap_mock_purchase_orders", 0) + 1
                    )
            await _load_p6_facts(session, rows, loc_by_name, com_by_name, counts)
            # Laporkan baris deret yang DITULIS, bukan hanya entitas baru.
            # Sebelumnya `rows` kosong walau 242 baris masuk, sehingga pemanggil
            # (mis. tombol refresh di panel) tidak bisa membedakan "tidak ada
            # yang perlu ditulis" dari "berhasil menulis".
            counts["supply_records"] = len(rows["supply"])
            counts["demand_records"] = len(rows["demand"])
            counts["price_signals"] = len(rows["price_signals"])
            counts["menu_plans"] = len(rows["menu_plans"])
            counts["delivery_events"] = len(rows["delivery_events"])
            counts["disposal_events"] = len(rows["disposal_events"])
            # Migrasi 012 mem-backfill koordinat pemasok yang SUDAH ADA saat
            # migrasi berjalan. Di DB baru pemasok lahir SESUDAH migrasi, jadi
            # sebagian tertinggal tanpa pin peta. Backfill idempoten (hanya
            # menyentuh baris NULL) supaya bootstrap dari nol setara demo.
            await session.execute(
                text(
                    """
                    WITH ranked AS (
                        SELECT s.id,
                               l.latitude  AS base_lat,
                               l.longitude AS base_lon,
                               row_number() OVER (
                                   PARTITION BY s.location_id ORDER BY s.name
                               ) - 1 AS rn
                        FROM suppliers s
                        JOIN locations l ON l.id = s.location_id
                        WHERE s.latitude IS NULL AND l.latitude IS NOT NULL
                    )
                    UPDATE suppliers s
                    SET latitude  = r.base_lat  + (0.012 * ((r.rn % 3) - 1)),
                        longitude = r.base_lon + (0.012 * (((r.rn / 3) % 3) - 1)),
                        updated_at = now()
                    FROM ranked r
                    WHERE s.id = r.id
                    """
                )
            )
            await session.commit()
    finally:
        await engine.dispose()
    return counts


async def _load_p6_facts(session, rows: dict, loc_by_name, com_by_name,
                         counts: dict) -> None:
    """P6: muat facts KPI (menu plan / delivery / disposal) — idempoten merge."""
    from sqlalchemy import select as _select

    from app.models import DeliveryEvent, DisposalEvent, MenuPlan

    plan_by_key = {
        (r.location_id, r.plan_date): r
        for r in (await session.execute(_select(MenuPlan))).scalars()
    }
    delivery_ids = {
        r.id for r in (await session.execute(_select(DeliveryEvent))).scalars()
    }
    disposal_ids = {
        r.id for r in (await session.execute(_select(DisposalEvent))).scalars()
    }
    for item in rows["menu_plans"]:
        loc_id = loc_by_name[item["location"]].id
        key = (loc_id, item["plan_date"])
        plan_by_key.setdefault(key, None)

    # Upsert pada kunci unik (location_id, plan_date) — bukan `merge` per PK.
    #
    # Sebabnya nyata (Fase 5, 2026-10-15): generator deret waktu demo mengisi
    # `plan_date` sampai 5 Nov, jadi tanggal di sekitar "hari ini" bisa SUDAH
    # terisi baris `origin='demo'`. `merge` memakai PK, sehingga baris demo itu
    # tidak terlihat dan INSERT menabrak `uq_menu_plans_loc_date` →
    # UniqueViolationError, dan baris kanonik tidak pernah ada di tanggal itu.
    #
    # Prioritas: isi KANONIK menang atas baris demo — baris demo di tanggal itu
    # diadopsi (planned_portions + origin jadi kanonik) dan id-nya DIPERTAHANKAN,
    # karena mengganti PK induk yang masih dirujuk `delivery_events` memutus FK.
    # Baris kanonik yang sudah ada TIDAK disentuh (`WHERE origin='demo'`).
    # Id baris yang SUDAH menempati tiap (lokasi, tanggal) — apa pun asalnya.
    # Anak-anak (delivery_events) harus menunjuk id AKTUAL ini, bukan id kanonik
    # hasil hitung: kalau baris demo yang menempati tanggal itu, id-nya lain.
    id_aktual = {
        (r.location_id, r.plan_date): r.id
        for r in (await session.execute(_select(MenuPlan))).scalars()
    }

    if rows["menu_plans"]:
        plan_stmt = pg_insert(MenuPlan).values(
            [
                {
                    "id": item["id"],
                    "location_id": loc_by_name[item["location"]].id,
                    "plan_date": item["plan_date"],
                    "planned_portions": item["planned_portions"],
                    "origin": "seed",
                }
                for item in rows["menu_plans"]
            ]
        )
        plan_stmt = plan_stmt.on_conflict_do_update(
            constraint="uq_menu_plans_loc_date",
            # `id` SENGAJA tidak di-update: mengganti PK induk yang masih
            # dirujuk delivery_events = ForeignKeyViolationError, dan dulu itu
            # menggagalkan seluruh refresh (500). Baris demo di tanggal itu
            # "diadopsi" apa adanya (isi + origin jadi kanonik, id tetap).
            set_={
                "planned_portions": plan_stmt.excluded.planned_portions,
                "origin": "seed",
            },
            where=MenuPlan.origin == "demo",
        )
        await session.execute(plan_stmt)
    await session.flush()  # pastikan menu_plan tersimpan sebelum delivery FK
    peta_plan = {
        item["id"]: id_aktual.get((loc_by_name[item["location"]].id, item["plan_date"]), item["id"])
        for item in rows["menu_plans"]
    }
    for item in rows["delivery_events"]:
        if item["id"] in delivery_ids:
            continue
        session.add(DeliveryEvent(
            id=item["id"],
            menu_plan_id=peta_plan.get(item["menu_plan"], item["menu_plan"]),
            delivered_portions=item["delivered_portions"],
            status=item["status"],
            delivered_at=item["delivered_at"],
        ))
        counts["delivery_events"] = counts.get("delivery_events", 0) + 1
    for item in rows["disposal_events"]:
        if item["id"] in disposal_ids:
            continue
        session.add(DisposalEvent(
            id=item["id"],
            location_id=loc_by_name[item["location"]].id,
            commodity_id=com_by_name[item["commodity"]].id,
            quantity_kg=item["quantity_kg"],
            reason=item["reason"],
            disposed_at=item["disposed_at"],
        ))
        counts["disposal_events"] = counts.get("disposal_events", 0) + 1


# ---------------------------------------------------------------------------
# Demo users (S3-01) — 3 role final, idempoten.
# Password demo statis (bukan secret produksi); dipakai untuk demo juri.
#
# Ruling 2026-10-14: KEDUA approver demo sengaja di SPPG yang sama (Jakarta).
# Matriks AND dua verifier kini berlaku di dalam satu SPPG (approve/execute
# memakai `require_scope(user, decision.target_location_id)`), jadi ahli gizi
# di lokasi lain hanya akan mendapat 403 dan feed kosong — kasus FLAGGED/
# UNAVAILABLE tidak bisa didemokan. bgn_monitor tetap nasional (tanpa lokasi).
# ---------------------------------------------------------------------------

_AKUN_DEMO_MENTAH = [
    {
        "email": "sppg.head@demo.local",
        "name": "SPPG Head Demo",
        "role": "sppg_head",
        "location": "Jakarta",
    },
    {
        "email": "sppg.nutritionist@demo.local",
        "name": "SPPG Nutritionist Demo",
        "role": "sppg_nutritionist",
        "location": "Jakarta",  # satu SPPG dengan kepala demo (Ruling 2026-10-14)
    },
    {
        "email": "bgn.monitor@demo.local",
        "name": "BGN Monitor Demo",
        "role": "bgn_monitor",
        "location": None,
    },
    # Keputusan produk 3A (18 Okt 2026): setiap kota yang menyimpan riwayat demo
    # punya approver SENDIRI. Tanpa ini, keputusan bertarget Bandung/Surabaya
    # mustahil di-approve (scope menolak 403) dan riwayat `executed`-nya hanya
    # bisa dibuat dengan approval dari SPPG lain — bukti yang tidak sah.
    {
        "email": "sppg.head.bandung@demo.local",
        "name": "SPPG Head Bandung Demo",
        "role": "sppg_head",
        "location": "Bandung",
    },
    {
        "email": "sppg.nutritionist.bandung@demo.local",
        "name": "SPPG Nutritionist Bandung Demo",
        "role": "sppg_nutritionist",
        "location": "Bandung",
    },
    {
        "email": "sppg.head.surabaya@demo.local",
        "name": "SPPG Head Surabaya Demo",
        "role": "sppg_head",
        "location": "Surabaya",
    },
    {
        "email": "sppg.nutritionist.surabaya@demo.local",
        "name": "SPPG Nutritionist Surabaya Demo",
        "role": "sppg_nutritionist",
        "location": "Surabaya",
    },
]

# Satu pintu: pembacaan `akun["password"]` diselesaikan lewat
# `resolve_demo_password` (guard DEMO_MODE), bukan literal di dalam dict.
DEMO_USERS: list[AkunDemo] = [AkunDemo(akun) for akun in _AKUN_DEMO_MENTAH]


def ensure_demo_users() -> None:
    """Idempoten: merge 3 user demo (stable uuid dari email)."""
    asyncio.run(_ensure_demo_users_async())


async def _ensure_demo_users_async() -> None:
    import bcrypt

    from app.models import User

    # Fail-fast SEBELUM menyentuh database: bila kredensial demo tidak
    # diizinkan (DEMO_MODE mati dan DEMO_PASSWORD_<ROLE> tidak disuplai),
    # seed berhenti tanpa menulis apa pun (temuan D-01).
    sandi_demo = {u["email"]: resolve_demo_password(u["role"]) for u in DEMO_USERS}

    engine = create_engine(_seed_database_url())
    try:
        session_maker = create_session_maker(engine)
        async with session_maker() as session:
            locs = {
                loc.name: loc.id
                for loc in (await session.execute(select(Location))).scalars()
            }
            for u in DEMO_USERS:
                uid = stable_uuid("user", u["email"])
                # Password datang dari `resolve_demo_password` — bukan literal
                # di daftar ini. Seed menolak berjalan bila DEMO_MODE tidak
                # aktif dan operator tidak menyuplai DEMO_PASSWORD_<ROLE>
                # (temuan D-01, 25 Okt 2026).
                digest = bcrypt.hashpw(
                    sandi_demo[u["email"]].encode(), bcrypt.gensalt()
                ).decode()
                await session.merge(
                    User(
                        id=uid,
                        name=u["name"],
                        email=u["email"],
                        password_hash=digest,
                        role=u["role"],
                        location_id=(
                            locs.get(u["location"]) if u["location"] else None
                        ),
                    )
                )
            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Sprint 1 deterministik")
    parser.add_argument("--reference-time", required=True, help="ISO 8601 tz-aware")
    parser.add_argument(
        "--with-demo-users",
        action="store_true",
        help="Juga pastikan 3 akun demo role ada (S3-01)",
    )
    parser.add_argument(
        "--with-demo-suppliers",
        action="store_true",
        help="Juga pastikan 30 pemasok demo ada (Fase 2: pemasok tampil di peta)",
    )
    parser.add_argument(
        "--skip-routes",
        action="store_true",
        help=(
            "Jangan sinkronkan rute jalan (OSRM) sesudah seeding. Tanpa flag ini, "
            "rute kiriman aktif diambil dari OSRM dan disimpan di tabel road_routes "
            "supaya peta tidak butuh internet (keputusan pemilik 2026-10-16)."
        ),
    )
    args = parser.parse_args()
    ref = datetime.fromisoformat(args.reference_time)
    if ref.tzinfo is None:
        raise SystemExit(
            "reference-time wajib timezone-aware. Ruling REF seed canonical "
            "(Roy 2026-10-09): 2026-10-08T12:00:00+00:00 — REF lain "
            "menduplikasi baris (id stable_uuid bergantung REF)."
        )
    if args.with_demo_users:
        # Fail-fast paling awal: bila kredensial demo tidak diizinkan, jangan
        # menulis data apa pun lebih dulu (temuan D-01).
        try:
            for _u in DEMO_USERS:
                resolve_demo_password(_u["role"])
        except DemoCredentialError as exc:
            raise SystemExit(f"[seed] {exc}") from exc

    counts = asyncio.run(load_seed(ref))
    if args.with_demo_users:
        try:
            ensure_demo_users()
        except DemoCredentialError as exc:
            # Pesan untuk operator, bukan traceback: seed berhenti sebelum
            # menulis apa pun (temuan D-01).
            raise SystemExit(f"[seed] {exc}") from exc
        print("Demo users siap (3 role, idempoten).")
    if args.with_demo_suppliers:
        from app.seed.suppliers_demo import seed_demo_suppliers

        added = asyncio.run(seed_demo_suppliers())
        print(
            f"Pemasok demo siap (60 baris, idempoten): baru {added['created']}, "
            f"diperbarui {added['updated']}."
        )
    if not args.skip_routes:
        try:
            laporan = asyncio.run(sync_routes_after_seed(ref))
            print(
                "Rute jalan (OSRM): "
                f"{laporan['diambil']} diambil, {laporan['sudah_ada']} sudah ada, "
                f"{laporan['gagal']} gagal — hanya kiriman aktif."
            )
            for alasan, jumlah in sorted(laporan["alasan_gagal"].items()):
                print(f"  gagal ({alasan}): {jumlah} — peta akan menulis 'belum disinkronkan'")
        except Exception as exc:  # jaringan/DB di luar dugaan tidak membatalkan seed
            print(f"Rute jalan: GAGAL disinkronkan ({type(exc).__name__}: {exc}).")
            print("  Peta akan menulis 'belum disinkronkan'; seeding tetap selesai.")
    print(f"Seed selesai (idempoten). Row baru: {counts or '{}'}")


if __name__ == "__main__":
    main()
