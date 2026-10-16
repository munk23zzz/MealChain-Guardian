"""Generator deret waktu data demo (Fase 4, 2026-10-14).

Mengapa modul ini ada: sebelum Fase 4 dataset demo adalah SATU snapshot
(8 Okt 2026 12:00 UTC) — grafik "Pasokan per Lokasi" kosong dan cerita
"riwayat Sep → hari ini" tidak punya data. Generator ini mengisi riwayat itu
tanpa menyentuh satu pun jangkar kanonik.

Dua aturan yang mengikat (rencana `.hermes/plans/2026-10-14_scope-pemasok-peta-rentang.md`
butir C1/C2) dan cara modul ini memenuhinya:

1. **Nilai record terbaru per lokasi×komoditas tetap kanonik.** Baris AKTUAL
   demo dibuat hanya untuk waktu `< REF - 24 jam` (`actual_timestamps`), jadi
   baris snapshot kanonik di REF selalu tetap yang terbaru — `/supply`,
   `/demand`, `/balance/map`, `/candidate`, dan 12 berkas tes jangkar tidak
   melihat baris demo sama sekali.
2. **Jendela KPI (7 Okt 12:00 → 8 Okt 12:00 UTC) tidak diisi baris baru.**
   Margin 24 jam di atas mengecualikan seluruh jendela itu (batas atasnya
   eksklusif `REF - 24 jam` = 7 Okt 12:00).

Masa depan hanya ditulis ke tabel yang MEMANG merencanakan: `menu_plans`
(`plan_date` s/d akhir rentang). `delivery_events`/`disposal_events` tidak
digenerate — keduanya catatan kejadian (aktual), dan membuat "pengiriman"
bertanggal masa depan sama dengan mengarang aktual masa depan.

Yang SENGAJA tidak digenerate: `demand_records` (riwayatnya sudah 13 titik
per pasangan sejak 20 Agu) — menambah observasi baru menggeser jendela
"3 observasi terbaru" milik `/demand/forecast` dan nilai "kebutuhan terbaru",
yaitu jangkar yang justru harus tetap. Keputusan ini tercatat di laporan fase.

Determinisme: nilai turunan `hashlib.sha256` atas kunci (pasangan + waktu),
BUKAN RNG berjalan — jadi hasil tidak bergantung urutan iterasi dan dua kali
jalan menghasilkan baris identik (dipatok uji).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import create_engine, create_session_maker
from app.models import Decision, Location, MenuPlan, PriceSignal, SupplyRecord

# --------------------------------------------------------------------- batas

#: Waktu referensi kanonik (Ruling REF, Roy 2026-10-09). Semua jangkar angka
#: repo ini dihitung pada waktu ini.
CANONICAL_REF = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)

#: Baris AKTUAL demo berhenti minimal 24 jam sebelum REF deret aktual, sehingga
#: batas atasnya jatuh tepat di `DEFAULT_END` (lihat `ACTUAL_REF`).
ACTUAL_HORIZON_MARGIN = timedelta(days=1)

#: Batas kewarasan rentang permintaan (tolak tanggal ngawur).
GENERATION_FLOOR = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
GENERATION_CEILING = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)

DEFAULT_INTERVAL_HOURS = 12
DEFAULT_START = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
DEFAULT_END = datetime(2026, 11, 5, 0, 0, tzinfo=UTC)

#: REF deret AKTUAL demo. `CANONICAL_REF` tetap jangkar KASUS & snapshot seed — id
#: baris memakai `stable_uuid` yang bergantung REF itu, jadi menggesernya akan
#: menduplikasi baris — sehingga batas deret aktual dipisah ke sini.
#:
#: Dengan REF ini, `actual_cutoff` (REF − 1 hari) jatuh TEPAT di `DEFAULT_END`, jadi
#: baris aktual mengisi penuh 1 Sep → 5 Nov. Sebelumnya batasnya `CANONICAL_REF`
#: (8 Okt): 9 Okt → 5 Nov kosong, kalender menulis "tidak ada catatan", jendela KPI
#: 24 jam / 7 hari kosong, dan grafik berhenti sembilan hari sebelum hari ini.
#: Dilonggarkan 2026-10-17 atas permintaan pemilik. Yang TIDAK berubah: tidak ada
#: baris aktual yang MELEWATI `DEFAULT_END`.
ACTUAL_REF = DEFAULT_END + ACTUAL_HORIZON_MARGIN

#: Sumber baris pasokan demo: feed SAP mock, sama dengan snapshot kanonik.
SUPPLY_SOURCE = "mock_sap"

#: Pola mingguan (narasi demo): akhir pekan lebih rendah — SPPG sekolah.
WEEKEND_FACTOR = Decimal("0.92")
NOISE_SPREAD = Decimal("0.06")
PRICE_NOISE_SPREAD = Decimal("0.03")

#: Kutipan pemasok tidak perlu serapat referensi harga.
QUOTE_INTERVAL_DAYS = 7

#: Tabel yang dibersihkan `purge_demo_rows` (urut FK: anak dulu).
PURGE_MODELS = (SupplyRecord, PriceSignal, MenuPlan)

_TWO_PLACES = Decimal("0.01")


# ------------------------------------------------------------------- bantuan


def _quantize2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _unit(key: str) -> Decimal:
    """Angka tetap di [0,1) dari kunci — pengganti RNG supaya urutan-agnostik."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return Decimal(int.from_bytes(digest[:8], "big")) / Decimal(2**64)


def _factor(key: str, spread: Decimal, day: date | None) -> Decimal:
    """Faktor pengali deterministik: pola mingguan + derau simetris terkendali."""
    factor = Decimal(1)
    if day is not None and day.weekday() >= 5:
        factor *= WEEKEND_FACTOR
    return factor * (Decimal(1) + spread * (Decimal(2) * _unit(key) - Decimal(1)))


def _pair_key(location_id, commodity_id) -> str:
    return f"{location_id}|{commodity_id}"


# ----------------------------------------------------------------- validasi


def validate_range(start: datetime, end: datetime) -> None:
    """Tolak rentang yang tidak masuk akal — pesan galat siap dipakai API."""
    for label, value in (("start", start), ("end", end)):
        if value is None:
            raise ValueError(f"{label} wajib diisi")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} wajib punya offset zona waktu")
    if start >= end:
        raise ValueError("start harus lebih awal dari end")
    if start < GENERATION_FLOOR or end > GENERATION_CEILING:
        raise ValueError(
            f"rentang di luar batas yang didukung "
            f"({GENERATION_FLOOR.date()} .. {GENERATION_CEILING.date()})"
        )


def actual_cutoff(ref: datetime = ACTUAL_REF) -> datetime:
    """Batas ATAS eksklusif untuk baris aktual demo (= `DEFAULT_END` secara bawaan)."""
    return ref - ACTUAL_HORIZON_MARGIN


def actual_timestamps(
    start: datetime,
    end: datetime,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ref: datetime = ACTUAL_REF,
) -> list[datetime]:
    """Waktu baris AKTUAL: dari `start` melangkah sampai `actual_cutoff(ref)`."""
    if interval_hours < 1:
        raise ValueError("interval_hours minimal 1")
    limit = min(end, actual_cutoff(ref))
    step = timedelta(hours=interval_hours)
    stamps: list[datetime] = []
    current = start
    while current < limit:
        stamps.append(current)
        current = current + step
    return stamps


# -------------------------------------------------------------- nilai deret


def supply_value(baseline: Decimal, pair: str, at: datetime) -> Decimal:
    """Nilai pasokan demo di sekitar baseline kanonik pasangan itu."""
    factor = _factor(f"supply|{pair}|{at.isoformat()}", NOISE_SPREAD, at.date())
    value = _quantize2(Decimal(baseline) * factor)
    return max(value, Decimal("0"))


def reference_price_value(baseline: Decimal, pair: str, at: datetime) -> Decimal:
    """Harga referensi PIHPS demo di sekitar harga referensi kanonik."""
    factor = _factor(f"price|{pair}|{at.isoformat()}", PRICE_NOISE_SPREAD, None)
    return max(_quantize2(Decimal(baseline) * factor), Decimal("0.01"))


def quote_price_value(
    baseline: Decimal, supplier_key: str, at: datetime
) -> Decimal:
    """Kutipan pemasok demo di sekitar kutipan kanonik pemasok itu."""
    factor = _factor(
        f"quote|{supplier_key}|{at.isoformat()}", PRICE_NOISE_SPREAD, None
    )
    return max(_quantize2(Decimal(baseline) * factor), Decimal("0.01"))


def planned_portions(base: int, location_id, day: date) -> int:
    """Porsi rencana harian: pola mingguan (akhir pekan lebih sedikit)."""
    factor = _factor(f"portions|{location_id}|{day.isoformat()}", Decimal("0.02"), day)
    return int((Decimal(base) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def plan_supply_rows(
    pairs: list[tuple[str, Any, Any, Decimal]],
    timestamps: list[datetime],
) -> list[dict]:
    """Baris `supply_records` demo (list murni — tidak menyentuh DB)."""
    return [
        {
            "location_id": location_id,
            "commodity_id": commodity_id,
            "quantity_kg": supply_value(baseline, pair, at),
            "recorded_at": at,
            "source": SUPPLY_SOURCE,
            "origin": "demo",
        }
        for pair, location_id, commodity_id, baseline in pairs
        for at in timestamps
    ]


def plan_reference_price_rows(
    pairs: list[tuple[str, Any, Any, Decimal]],
    timestamps: list[datetime],
) -> list[dict]:
    return [
        {
            "location_id": location_id,
            "commodity_id": commodity_id,
            "price_per_kg": reference_price_value(baseline, pair, at),
            "supplier_id": None,
            "recorded_at": at,
            "source": "pihps_reference",
            "origin": "demo",
        }
        for pair, location_id, commodity_id, baseline in pairs
        for at in timestamps
    ]


def plan_quote_price_rows(
    quotes: list[tuple[str, Any, Any, Any, Decimal]],
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Kutipan pemasok demo, satu per pekan (bukan tiap 12 jam)."""
    rows: list[dict] = []
    step = timedelta(days=QUOTE_INTERVAL_DAYS)
    for supplier_key, location_id, commodity_id, supplier_id, baseline in quotes:
        at = start
        while at < end:
            rows.append(
                {
                    "location_id": location_id,
                    "commodity_id": commodity_id,
                    "price_per_kg": quote_price_value(baseline, supplier_key, at),
                    "supplier_id": supplier_id,
                    "recorded_at": at,
                    "source": "supplier_quote",
                    "origin": "demo",
                }
            )
            at = at + step
    return rows


def plan_menu_plan_rows(
    bases: list[tuple[Any, int]], start: datetime, end: datetime
) -> list[dict]:
    """Rencana menu harian (tabel PERENCANAAN: tanggal masa depan sah)."""
    rows: list[dict] = []
    day = start.date()
    last = end.date()
    while day <= last:
        for location_id, base in bases:
            rows.append(
                {
                    "location_id": location_id,
                    "plan_date": day,
                    "planned_portions": planned_portions(base, location_id, day),
                    "origin": "demo",
                }
            )
        day = day + timedelta(days=1)
    return rows


def plan_all(
    *,
    supply_pairs: list[tuple[str, Any, Any, Decimal]],
    reference_pairs: list[tuple[str, Any, Any, Decimal]],
    quotes: list[tuple[str, Any, Any, Any, Decimal]],
    menu_bases: list[tuple[Any, int]],
    start: datetime,
    end: datetime,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ref: datetime = ACTUAL_REF,
) -> dict:
    """Seluruh rencana baris demo (murni) — dipakai API untuk pratinjau & tulis."""
    validate_range(start, end)
    stamps = actual_timestamps(start, end, interval_hours, ref)
    actual_end = min(end, actual_cutoff(ref))
    return {
        "supply": plan_supply_rows(supply_pairs, stamps),
        "prices": plan_reference_price_rows(reference_pairs, stamps)
        + plan_quote_price_rows(quotes, start, actual_end),
        "menu_plans": plan_menu_plan_rows(menu_bases, start, end),
        "actual_timestamps": len(stamps),
        "range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "actual_start": stamps[0].isoformat() if stamps else None,
            "actual_end": actual_end.isoformat(),
            "plan_end": end.date().isoformat(),
        },
    }


# ---------------------------------------------------------------------- DB

_DB_URL_DEFAULT = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"


def _database_url() -> str:
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    from app.core.config import settings

    return settings.database_url


async def _collect_baselines(session) -> dict:
    """Baca jangkar dari DB: nilai kanonik (origin='seed') per pasangan."""
    supply_rows = (
        await session.execute(
            select(
                SupplyRecord.location_id,
                SupplyRecord.commodity_id,
                SupplyRecord.quantity_kg,
            )
            .where(SupplyRecord.origin == "seed")
            .distinct(SupplyRecord.location_id, SupplyRecord.commodity_id)
            .order_by(
                SupplyRecord.location_id,
                SupplyRecord.commodity_id,
                SupplyRecord.recorded_at.desc(),
            )
        )
    ).all()
    reference_rows = (
        await session.execute(
            select(
                PriceSignal.location_id,
                PriceSignal.commodity_id,
                PriceSignal.price_per_kg,
            )
            .where(
                PriceSignal.origin == "seed",
                PriceSignal.source == "pihps_reference",
            )
            .distinct(PriceSignal.location_id, PriceSignal.commodity_id)
            .order_by(
                PriceSignal.location_id,
                PriceSignal.commodity_id,
                PriceSignal.recorded_at.desc(),
            )
        )
    ).all()
    quote_rows = (
        await session.execute(
            select(
                PriceSignal.supplier_id,
                PriceSignal.location_id,
                PriceSignal.commodity_id,
                PriceSignal.price_per_kg,
            )
            .where(
                PriceSignal.origin == "seed",
                PriceSignal.source == "supplier_quote",
            )
            .order_by(
                PriceSignal.supplier_id,
                PriceSignal.commodity_id,
                PriceSignal.recorded_at.desc(),
            )
        )
    ).all()
    portion_rows = (
        await session.execute(
            select(MenuPlan.location_id, func.max(MenuPlan.planned_portions))
            .where(MenuPlan.origin == "seed")
            .group_by(MenuPlan.location_id)
        )
    ).all()
    portion_fallback = int(
        (
            await session.execute(
                select(func.avg(MenuPlan.planned_portions)).where(
                    MenuPlan.origin == "seed"
                )
            )
        ).scalar()
        or 1200
    )
    seen_quotes: set[tuple[object, object]] = set()
    quotes: list[tuple[str, Any, Any, Any, Decimal]] = []
    for supplier_id, location_id, commodity_id, price in quote_rows:
        key = (supplier_id, commodity_id)
        if key in seen_quotes:
            continue
        seen_quotes.add(key)
        quotes.append(
            (
                f"{supplier_id}|{commodity_id}",
                location_id,
                commodity_id,
                supplier_id,
                Decimal(price),
            )
        )
    bases = {location_id: int(base or portion_fallback) for location_id, base in portion_rows}
    locations = (await session.execute(select(Location))).scalars().all()
    menu_bases = [(loc.id, bases.get(loc.id, portion_fallback)) for loc in locations]
    return {
        "supply_pairs": [
            (
                _pair_key(loc, com),
                loc,
                com,
                Decimal(quantity),
            )
            for loc, com, quantity in supply_rows
        ],
        "reference_pairs": [
            (_pair_key(loc, com), loc, com, Decimal(price))
            for loc, com, price in reference_rows
        ],
        "quotes": quotes,
        "menu_bases": menu_bases,
    }


async def _upsert_supply(session, rows: list[dict], now: datetime) -> None:
    if not rows:
        return
    stmt = pg_insert(SupplyRecord).values(
        [{**row, "generated_at": now} for row in rows]
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_supply_records_loc_com_time_source",
        set_={"quantity_kg": stmt.excluded.quantity_kg, "generated_at": stmt.excluded.generated_at},
        where=SupplyRecord.origin == "demo",
    )
    await session.execute(stmt)


async def _upsert_prices(session, rows: list[dict], now: datetime) -> None:
    """Dua index parsial, jadi dua jalur upsert (referensi vs kutipan)."""
    for source, index_name in (
        ("pihps_reference", "uq_price_signals_reference"),
        ("supplier_quote", "uq_price_signals_quote"),
    ):
        subset = [row for row in rows if row["source"] == source]
        if not subset:
            continue
        stmt = pg_insert(PriceSignal).values(
            [{**row, "generated_at": now} for row in subset]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=(
                ["location_id", "commodity_id", "recorded_at"]
                if source == "pihps_reference"
                else ["location_id", "commodity_id", "supplier_id", "recorded_at"]
            ),
            index_where=PriceSignal.source == source,
            set_={
                "price_per_kg": stmt.excluded.price_per_kg,
                "generated_at": stmt.excluded.generated_at,
            },
            where=PriceSignal.origin == "demo",
        )
        await session.execute(stmt)


async def _insert_menu_plans(session, rows: list[dict], now: datetime) -> None:
    """Rencana menu: hari yang SUDAH ada (kanonik) tidak disentuh.

    `DO NOTHING` dipilih sadar: `menu_plans` punya kunci unik
    (location_id, plan_date) yang TIDAK memuat `origin`, jadi `DO UPDATE` akan
    menimpa 14 hari kanonik dengan angka demo. Hari kanonik harus menang.
    """
    if not rows:
        return
    stmt = pg_insert(MenuPlan).values([{**row, "generated_at": now} for row in rows])
    stmt = stmt.on_conflict_do_nothing(constraint="uq_menu_plans_loc_date")
    await session.execute(stmt)


async def _count_origin(session, model, origin: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(model).where(model.origin == origin)
            )
        ).scalar()
        or 0
    )


async def generate_timeseries(
    start: datetime = DEFAULT_START,
    end: datetime = DEFAULT_END,
    *,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ref: datetime = ACTUAL_REF,
    database_url: str | None = None,
) -> dict:
    """Tulis baris demo untuk rentang `[start, end]`. Idempoten.

    Kembalian: ringkasan siap dipakai API (`range`, `counts`, `skipped`).
    """
    plan = None
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            baselines = await _collect_baselines(session)
            plan = plan_all(
                start=start, end=end, interval_hours=interval_hours, ref=ref, **baselines
            )
            before = {
                "supply": await _count_origin(session, SupplyRecord, "demo"),
                "prices": await _count_origin(session, PriceSignal, "demo"),
                "menu_plans": await _count_origin(session, MenuPlan, "demo"),
            }
            now = datetime.now(UTC)
            await _upsert_supply(session, plan["supply"], now)
            await _upsert_prices(session, plan["prices"], now)
            await _insert_menu_plans(session, plan["menu_plans"], now)
            await session.commit()
            after = {
                "supply": await _count_origin(session, SupplyRecord, "demo"),
                "prices": await _count_origin(session, PriceSignal, "demo"),
                "menu_plans": await _count_origin(session, MenuPlan, "demo"),
            }
    finally:
        await engine.dispose()

    counts = {
        name: {
            "planned": len(plan[name]),
            "added": after[name] - before[name],
            "in_db": after[name],
        }
        for name in ("supply", "prices", "menu_plans")
    }
    return {
        "range": plan["range"],
        "counts": counts,
        "actual_timestamps": plan["actual_timestamps"],
        "interval_hours": interval_hours,
        "skipped": {
            "menu_plans_kept": len(plan["menu_plans"]) - counts["menu_plans"]["added"],
        },
    }


async def preview_timeseries(
    start: datetime = DEFAULT_START,
    end: datetime = DEFAULT_END,
    *,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ref: datetime = ACTUAL_REF,
    database_url: str | None = None,
) -> dict:
    """Sama seperti `generate_timeseries`, TANPA menulis apa pun."""
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            baselines = await _collect_baselines(session)
            plan = plan_all(
                start=start, end=end, interval_hours=interval_hours, ref=ref, **baselines
            )
            existing_menu = int(
                (
                    await session.execute(
                        select(func.count()).select_from(MenuPlan)
                    )
                ).scalar()
                or 0
            )
    finally:
        await engine.dispose()
    return {
        "range": plan["range"],
        "counts": {
            "supply": {"planned": len(plan["supply"])},
            "prices": {"planned": len(plan["prices"])},
            "menu_plans": {
                "planned": len(plan["menu_plans"]),
                "existing_rows": existing_menu,
            },
        },
        "actual_timestamps": plan["actual_timestamps"],
        "interval_hours": interval_hours,
        "writes": False,
    }


async def purge_demo_rows(database_url: str | None = None) -> dict:
    """Hapus HANYA baris `origin='demo'`. Baris kanonik tidak tersentuh."""
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)
    deleted: dict[str, int] = {}
    try:
        async with maker() as session:
            for model in PURGE_MODELS:
                result = await session.execute(
                    delete(model).where(model.origin == "demo")
                )
                deleted[model.__tablename__] = int(result.rowcount or 0)
            await session.commit()
    finally:
        await engine.dispose()
    return {"deleted": deleted, "total": sum(deleted.values())}


async def pastikan_deret_demo(
    database_url: str | None = None,
    *,
    start: datetime = DEFAULT_START,
    end: datetime = DEFAULT_END,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
) -> dict:
    """Pulihkan deret demo kanonik bila ADA baris yang hilang (jaring keamanan).

    Kenapa ada: `purge_demo_rows()` menghapus SELURUH baris `origin='demo'`.
    Bila pemanggilnya (mis. sebuah tes) gagal sebelum memulihkan, DB kerja
    tertinggal ter-purge — dan puluhan tes lain gagal berantai, padahal kode
    aplikasinya tidak apa-apa. Fungsi ini memulihkannya lewat generator resmi
    yang sama (`generate_timeseries`), bukan INSERT karangan.

    Kontrak:
    - idempoten: bila deret sudah lengkap, TIDAK ada baris ditambah;
    - hanya baris `origin='demo'` yang disentuh, `origin='seed'` tetap utuh;
    - kelengkapan diukur **agnostik-origin**: jumlah baris di dalam rentang yang
      direncanakan (SEMUA origin) minimal sebanyak yang direncanakan generator.
      Alasannya: sebagian stamp — mis. 8 Okt 12:00 — kuncinya sudah dipegang baris
      kanonik `origin='seed'`, dan generator sengaja TIDAK menimpanya. Menuntut
      "baris demo == rencana" membuat deret yang lengkap selalu tampak kurang 30
      baris, lalu fungsi ini "memulihkan" selamanya;
    - ringkasan memuat `sebelum`, `sesudah`, `harapan`, `kurang`, `dipulihkan`
      supaya bisa diperiksa manusia — bukan "sudah beres" tanpa angka.
    """
    pratinjau = await preview_timeseries(
        start, end, interval_hours=interval_hours, database_url=database_url
    )
    harapan = {
        "supply_records": int(pratinjau["counts"]["supply"]["planned"]),
        "price_signals": int(pratinjau["counts"]["prices"]["planned"]),
        "menu_plans": int(pratinjau["counts"]["menu_plans"]["planned"]),
    }

    batas_aktual = min(end, actual_cutoff())
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)

    async def _nyata(session) -> dict[str, int]:
        """Baris nyata di dalam rentang rencana, dihitung dari SEMUA origin."""
        return {
            "supply_records": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(SupplyRecord)
                        .where(
                            SupplyRecord.recorded_at >= start,
                            SupplyRecord.recorded_at < batas_aktual,
                        )
                    )
                ).scalar()
                or 0
            ),
            "price_signals": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(PriceSignal)
                        .where(
                            PriceSignal.recorded_at >= start,
                            PriceSignal.recorded_at < batas_aktual,
                        )
                    )
                ).scalar()
                or 0
            ),
            "menu_plans": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(MenuPlan)
                        .where(
                            MenuPlan.plan_date >= start.date(),
                            MenuPlan.plan_date <= end.date(),
                        )
                    )
                ).scalar()
                or 0
            ),
        }

    try:
        async with maker() as session:
            sebelum = await _nyata(session)
    finally:
        await engine.dispose()

    kurang = {t: harapan[t] - sebelum[t] for t in harapan if sebelum[t] < harapan[t]}

    if not kurang:
        return {
            "dipulihkan": False,
            "sebelum": sebelum,
            "sesudah": sebelum,
            "harapan": harapan,
            "kurang": {},
        }

    ringkasan = await generate_timeseries(
        start, end, interval_hours=interval_hours, database_url=database_url
    )
    engine2 = create_engine(database_url or _database_url())
    maker2 = create_session_maker(engine2)
    try:
        async with maker2() as session:
            sesudah = await _nyata(session)
    finally:
        await engine2.dispose()
    return {
        "dipulihkan": True,
        "sebelum": sebelum,
        "sesudah": sesudah,
        "harapan": harapan,
        "kurang": kurang,
        "ringkasan": ringkasan,
    }


async def demo_data_status(database_url: str | None = None) -> dict:
    """Keadaan data demo SEKARANG (baca saja) — untuk panel Demo Control.

    Tanpa ini, panel hanya bisa menebak "sekian baris demo" dari hasil operasi
    terakhir; kalau operator membuka tab baru atau kontainer di-restart, UI akan
    berbohong. Jadi status dibaca dari DB, bukan dari ingatan klien.
    """
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            tables: dict[str, dict] = {}
            for model in (SupplyRecord, PriceSignal, MenuPlan):
                seed_count = await _count_origin(session, model, "seed")
                demo_count = await _count_origin(session, model, "demo")
                entry: dict = {"seed": seed_count, "demo": demo_count}
                if model is MenuPlan:
                    for label, origin in (("seed", "seed"), ("demo", "demo")):
                        rows = (
                            await session.execute(
                                select(
                                    func.min(MenuPlan.plan_date),
                                    func.max(MenuPlan.plan_date),
                                ).where(MenuPlan.origin == origin)
                            )
                        ).one()
                        entry[f"{label}_from"] = rows[0].isoformat() if rows[0] else None
                        entry[f"{label}_to"] = rows[1].isoformat() if rows[1] else None
                else:
                    for label, origin in (("seed", "seed"), ("demo", "demo")):
                        rows = (
                            await session.execute(
                                select(
                                    func.min(model.recorded_at),
                                    func.max(model.recorded_at),
                                ).where(model.origin == origin)
                            )
                        ).one()
                        entry[f"{label}_from"] = rows[0].isoformat() if rows[0] else None
                        entry[f"{label}_to"] = rows[1].isoformat() if rows[1] else None
                if model is not MenuPlan:
                    last_generated = (
                        await session.execute(
                            select(func.max(model.generated_at)).where(
                                model.origin == "demo"
                            )
                        )
                    ).scalar()
                    entry["generated_at"] = (
                        last_generated.isoformat() if last_generated else None
                    )
                tables[model.__tablename__] = entry
            canonical_decisions = (
                await session.execute(
                    select(func.count())
                    .select_from(Decision)
                    .where(Decision.origin == "seed")
                )
            ).scalar()
            demo_decisions = (
                await session.execute(
                    select(func.count())
                    .select_from(Decision)
                    .where(Decision.origin == "demo")
                )
            ).scalar()
    finally:
        await engine.dispose()
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "canonical_ref": CANONICAL_REF.isoformat(),
        "actual_cutoff": actual_cutoff().isoformat(),
        "tables": tables,
        "decisions": {
            "seed": int(canonical_decisions or 0),
            "demo": int(demo_decisions or 0),
        },
        "totals": {
            "seed": sum(entry["seed"] for entry in tables.values()),
            "demo": sum(entry["demo"] for entry in tables.values()),
        },
    }


def main() -> None:
    """CLI: `python -m app.seed.timeseries [--start ...] [--end ...]`."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate deret waktu demo")
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--interval-hours", type=int, default=DEFAULT_INTERVAL_HOURS)
    parser.add_argument("--preview", action="store_true", help="Hitung saja, tanpa menulis")
    parser.add_argument("--purge", action="store_true", help="Hapus baris origin=demo")
    args = parser.parse_args()

    if args.purge:
        print(f"Purge: {asyncio.run(purge_demo_rows())}")
        return
    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)
    if args.preview:
        hasil = asyncio.run(
            preview_timeseries(start, end, interval_hours=args.interval_hours)
        )
        print(f"Pratinjau: {hasil}")
        return
    summary = asyncio.run(
        generate_timeseries(start, end, interval_hours=args.interval_hours)
    )
    print(f"Selesai: {summary}")


if __name__ == "__main__":
    main()
