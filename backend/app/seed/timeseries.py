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

Yang SENGAJA tidak digenerate: baris kanonik apa pun. Sejak audit angka 18 Okt
2026 permintaan (`demand_records`) ikut diperluas: baris kanonik berhenti di
8 Okt sehingga dashboard berlabel "Hari Ini" membandingkan pasokan 18 Okt
dengan permintaan 8 Okt. Generator kini menulis SATU observasi per hari (jam
00:00 UTC) mulai 9 Okt untuk pasangan yang MEMANG punya permintaan kanonik;
baris kanonik tidak ditimpa (kunci unik lokasi×komoditas×waktu, `DO UPDATE`
hanya berlaku untuk `origin='demo'`). Pasangan tanpa permintaan kanonik
(Bandung & Cianjur untuk telur) sengaja tetap kosong — "belum ada catatan"
adalah fakta yang ditampilkan apa adanya, bukan lubang yang ditambal.

Determinisme: nilai turunan `hashlib.sha256` atas kunci (pasangan + waktu),
BUKAN RNG berjalan — jadi hasil tidak bergantung urutan iterasi dan dua kali
jalan menghasilkan baris identik (dipatok uji).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import create_engine, create_session_maker
from app.models import (
    Batch,
    Decision,
    DeliveryEvent,
    DemandRecord,
    DisposalEvent,
    Location,
    MenuPlan,
    PriceSignal,
    SupplyRecord,
)

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

#: Permintaan demo (audit angka 18 Okt 2026). Cadence-nya BUKAN 12 jam seperti
#: pasokan: permintaan adalah rencana menu, dicatat sekali sehari. Derau lebih
#: kecil daripada pasokan (rencana tidak bergerak secepat panen) dan pola
#: akhir-pekan tetap dipakai supaya seri tidak terlihat rata/karangan.
DEMAND_NOISE_SPREAD = Decimal("0.02")
#: `needed_by` = `recorded_at` + 3 hari, sama dengan baris kanonik (8 -> 11 Okt).
DEMAND_LEAD_DAYS = 3
#: Hari pertama permintaan demo: sehari setelah baris kanonik terakhir (8 Okt).
#: Baris kanonik tidak pernah ditimpa — kunci unik lokasi×komoditas×waktu dipakai.
DEMAND_DEMO_START = datetime(2026, 10, 9, tzinfo=UTC)

#: Kutipan pemasok tidak perlu serapat referensi harga.
QUOTE_INTERVAL_DAYS = 7

#: Tabel yang dibersihkan `purge_demo_rows()`. Urutannya penting: baris anak
#: (kiriman) dibuang sebelum induknya (`menu_plans`) supaya tidak bergantung CASCADE.
#: `Batch` ikut di-purge sejak kegiatan demo (2026-10-17): tombol "Bersihkan
#: data demo" yang meninggalkan 40 kiriman demo akan membuat peta tetap ramai
#: padahal operator sudah meminta data demo dibuang. Anak FK-nya
#: (`batch_receipts`) memakai ON DELETE CASCADE.
PURGE_MODELS = (
    DeliveryEvent,
    DisposalEvent,
    SupplyRecord,
    DemandRecord,
    PriceSignal,
    MenuPlan,
    Batch,
)

#: Hari rencana pertama yang BELUM punya kiriman/limbah kanonik. Kanonik:
#: `delivery_events` 1–7 Okt, `disposal_events` 4–7 Okt. Mulai 8 Okt generator
#: boleh menulis baris demo — dengan begitu jangkar agenda 2 Okt (1.200 porsi
#: terkirim) tidak pernah tersentuh, sementara jendela KPI 7 hari tetap terisi.
EVENT_DEMO_START = datetime(2026, 10, 8, tzinfo=UTC)

#: Alasan limbah yang dipakai data kanonik — demo tidak mengarang alasan baru.
DISPOSAL_REASONS = ("spoilage_cold_chain", "expired_transport")

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


def demand_value(baseline: Decimal, pair: str, at: datetime) -> Decimal:
    """Nilai permintaan demo di sekitar baseline kanonik pasangan itu."""
    factor = _factor(
        f"demand|{pair}|{at.isoformat()}", DEMAND_NOISE_SPREAD, at.date()
    )
    return max(_quantize2(Decimal(baseline) * factor), Decimal("0"))


def plan_demand_rows(
    pairs: list[tuple[str, Any, Any, Decimal]],
    timestamps: list[datetime],
) -> list[dict]:
    """Baris `demand_records` demo: SATU observasi per hari (jam 00:00).

    Stempel 12:00 sengaja dilewati: itu kadens telemetri pasokan, bukan rencana
    menu. Baris kanonik (8 Okt 12:00) tidak pernah ditimpa — `_upsert_demand`
    memakai kunci unik lokasi×komoditas×waktu dan tidak meng-update baris non-demo.
    Pasangan yang TIDAK punya permintaan kanonik (Bandung, Cianjur) tidak ikut:
    "belum ada catatan" adalah fakta, bukan lubang yang ditambal.
    """
    rows: list[dict] = []
    for pair, location_id, commodity_id, baseline in pairs:
        for at in timestamps:
            if at.hour != 0 or at < DEMAND_DEMO_START:
                continue
            rows.append(
                {
                    "location_id": location_id,
                    "commodity_id": commodity_id,
                    "quantity_kg": demand_value(baseline, pair, at),
                    "needed_by": at + timedelta(days=DEMAND_LEAD_DAYS),
                    "recorded_at": at,
                    "origin": "demo",
                }
            )
    return rows


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
    bases: list[tuple[Any, int]],
    start: datetime,
    end: datetime,
    menu_start: datetime | None = None,
) -> list[dict]:
    """Rencana menu harian (tabel PERENCANAAN: tanggal masa depan sah).

    `menu_start` memisahkan awal rencana dari awal deret fakta. Dipakai sesi
    demo: pasokan/harga disemai 30 hari agar pemilih periode KPI punya pembeda,
    sementara rencana menu + kiriman + limbah tetap mulai `EVENT_DEMO_START`
    supaya continuity tidak jatuh hanya karena hari lama belum punya kiriman.
    """
    rows: list[dict] = []
    day = (menu_start or start).date()
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


def _event_id(kind: str, location_id, day: date) -> uuid.UUID:
    """Id deterministik untuk baris kiriman/limbah demo.

    Dipakai supaya generator idempoten tanpa perlu SELECT dulu: id yang sama
    muncul lagi pada panggilan berikutnya, lalu `ON CONFLICT (id) DO NOTHING`
    membuangnya. Tanpa ini, "dua kali jalan tidak menggandakan" hanya bisa
    dicapai lewat kueri-cek yang balapan.
    """
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mealchain:{kind}:{location_id}:{day}")


def _at(day: date, hour: int) -> datetime:
    """Pukul `hour` UTC pada tanggal rencana (14:00 = 21:00 WIB hari yang sama)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


#: Zona WIB dipakai untuk memutuskan "hari ini" pada penyemaian kiriman.
_WIB = timezone(timedelta(hours=7))


def kiriman_sudah_terjadi(plan_date: date, now: datetime) -> bool:
    """True bila kiriman untuk `plan_date` memang sudah berlangsung.

    Aturan tunggal yang dipakai generator DAN penghitung harapan: rencana
    setelah hari ini (WIB) belum terjadi, dan rencana hari ini baru terjadi
    setelah pukul kirim 14:00 UTC (21:00 WIB). Tanpa satu sumber aturan,
    jaring `pastikan_deret_demo` menganggap deret selalu kurang.
    """
    hari_ini = now.astimezone(_WIB).date()
    if plan_date > hari_ini:
        return False
    return _at(plan_date, 14) <= now


def plan_delivery_rows(
    menu_rows: list[dict], now: datetime | None = None
) -> list[dict]:
    """Rencana kiriman demo: satu kiriman per rencana pada/ setelah 8 Okt.

    Porsi terkirim 80–100% dari rencana (85% hari penuh, 10% kurang sedikit, 5%
    kurang lebih banyak). Kalau semuanya 100%, "Meal Continuity Rate" hanya bisa
    100% dan deretnya tidak informatif — padahal justru angka itulah yang dibaca
    juri di panel KPI.

    Kiriman hanya ditulis untuk kejadian yang SUDAH berlangsung: rencana setelah
    hari ini (WIB) dilewati, dan rencana hari ini baru dapat kiriman bila pukul
    21:00 WIB (14:00 UTC) sudah lewat. Tanpa aturan ini, kartu Meal Continuity
    menampilkan 100% untuk barang yang belum berangkat — angka palsu yang persis
    dilarang prinsip proyek (audit ulang 24 Okt 2026, temuan N1).
    """
    batas = EVENT_DEMO_START.date()
    acuan = now or datetime.now(UTC)
    rows: list[dict] = []
    for item in menu_rows:
        if item["plan_date"] < batas:
            continue
        # Belum terjadi (besok/lusa, atau hari ini sebelum jam kirim) -> lewati.
        if not kiriman_sudah_terjadi(item["plan_date"], acuan):
            continue
        dikirim_pada = _at(item["plan_date"], 14)
        kunci = f"kirim|{item['location_id']}|{item['plan_date']}"
        u = _unit(kunci)
        if u < Decimal("0.85"):
            faktor = Decimal("1.00")
        elif u < Decimal("0.95"):
            faktor = Decimal("0.92")
        else:
            faktor = Decimal("0.80")
        porsi = int(
            (Decimal(item["planned_portions"]) * faktor).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
        rows.append(
            {
                "id": _event_id("kirim", item["location_id"], item["plan_date"]),
                "menu_plan_id": item["menu_plan_id"],
                "delivered_portions": max(1, porsi),
                "status": "delivered",
                "delivered_at": dikirim_pada,
                "origin": "demo",
            }
        )
    return rows


def plan_disposal_rows(
    menu_rows: list[dict], commodities_by_location: dict
) -> list[dict]:
    """Dua catatan limbah per hari rencana (8 Okt ke atas), 3–13 kg.

    Lokasi bergilir tiap hari (posisi `n` dan `n+3` dari daftar terurut), jadi
    seluruh lokasi kebagian tanpa RNG yang bergantung urutan pemrosesan.
    Komoditas diambil dari pasokan lokasi itu — limbah selalu punya material.
    """
    batas = EVENT_DEMO_START.date()
    per_hari: dict[date, list[dict]] = {}
    for item in menu_rows:
        if item["plan_date"] < batas:
            continue
        per_hari.setdefault(item["plan_date"], []).append(item)

    rows: list[dict] = []
    for urutan, hari in enumerate(sorted(per_hari)):
        rencana = sorted(per_hari[hari], key=lambda r: str(r["location_id"]))
        jumlah = len(rencana)
        if jumlah == 0:
            continue
        for posisi in sorted({urutan % jumlah, (urutan + 3) % jumlah}):
            item = rencana[posisi]
            komoditas = commodities_by_location.get(item["location_id"]) or []
            if not komoditas:
                continue
            u = _unit(f"limbah|{item['location_id']}|{hari}")
            kg = (Decimal(3) + u * Decimal(10)).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_UP
            )
            rows.append(
                {
                    "id": _event_id("limbah", item["location_id"], hari),
                    "location_id": item["location_id"],
                    "commodity_id": sorted(komoditas, key=str)[0],
                    "quantity_kg": kg,
                    "reason": DISPOSAL_REASONS[0]
                    if u < Decimal("0.5")
                    else DISPOSAL_REASONS[1],
                    "disposed_at": _at(hari, 12),
                    "origin": "demo",
                }
            )
    return rows


def plan_all(
    *,
    supply_pairs: list[tuple[str, Any, Any, Decimal]],
    reference_pairs: list[tuple[str, Any, Any, Decimal]],
    quotes: list[tuple[str, Any, Any, Any, Decimal]],
    menu_bases: list[tuple[Any, int]],
    demand_pairs: list[tuple[str, Any, Any, Decimal]] | None = None,
    start: datetime,
    end: datetime,
    interval_hours: int = DEFAULT_INTERVAL_HOURS,
    ref: datetime = ACTUAL_REF,
    menu_start: datetime | None = None,
) -> dict:
    """Seluruh rencana baris demo (murni) — dipakai API untuk pratinjau & tulis."""
    validate_range(start, end)
    stamps = actual_timestamps(start, end, interval_hours, ref)
    actual_end = min(end, actual_cutoff(ref))
    menu_rows = plan_menu_plan_rows(menu_bases, start, end, menu_start)
    demand_rows = plan_demand_rows(demand_pairs or [], stamps)
    #: Berapa baris kiriman/limbah yang SEHARUSNYA ada: satu kiriman per rencana
    #: sejak 8 Okt, dua catatan limbah per hari rencana. Angka inilah yang dipakai
    #: laporan pratinjau dan jaring `pastikan_deret_demo` — bukan tebakan selisih.
    hari_berevent = {
        r["plan_date"] for r in menu_rows if r["plan_date"] >= EVENT_DEMO_START.date()
    }
    # Harapan kiriman DITURUNKAN dari generatornya sendiri (satu sumber aturan):
    # `plan_delivery_rows` hanya mengirim hari yang sudah berjalan, jadi hitungan
    # "setiap rencana dapat kiriman" akan salah bila dihitung manual di sini
    # (jaring `pastikan_deret_demo` lalu menganggap deret selalu kurang dan
    # memulihkannya terus-menerus).
    event_plan = {
        "deliveries": sum(
            1
            for r in menu_rows
            if r["plan_date"] >= EVENT_DEMO_START.date()
            and kiriman_sudah_terjadi(r["plan_date"], datetime.now(UTC))
        ),
        "disposals": len(hari_berevent) * 2,
        "demand": len(demand_rows),
    }
    return {
        "supply": plan_supply_rows(supply_pairs, stamps),
        "demand": demand_rows,
        "prices": plan_reference_price_rows(reference_pairs, stamps)
        + plan_quote_price_rows(quotes, start, actual_end),
        "menu_plans": menu_rows,
        "event_plan": event_plan,
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
    # Baseline permintaan: baris kanonik TERBARU per pasangan (8 Okt, origin
    # 'seed'). Hanya pasangan yang memang punya permintaan yang ikut — pasangan
    # tanpa baris (Bandung, Cianjur untuk telur) harus tetap "belum ada catatan".
    demand_rows = (
        await session.execute(
            select(
                DemandRecord.location_id,
                DemandRecord.commodity_id,
                DemandRecord.quantity_kg,
            )
            .where(DemandRecord.origin == "seed")
            .distinct(DemandRecord.location_id, DemandRecord.commodity_id)
            .order_by(
                DemandRecord.location_id,
                DemandRecord.commodity_id,
                DemandRecord.recorded_at.desc(),
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
        "demand_pairs": [
            (
                _pair_key(loc, com),
                loc,
                com,
                Decimal(quantity),
            )
            for loc, com, quantity in demand_rows
        ],
        "reference_pairs": [
            (_pair_key(loc, com), loc, com, Decimal(price))
            for loc, com, price in reference_rows
        ],
        "quotes": quotes,
        "menu_bases": menu_bases,
    }


def _potong(rows: list[dict], per: int = 1000):
    """Pecah baris jadi beberapa INSERT.

    asyncpg menolak satu statement dengan lebih dari 32767 argumen bind
    (`the number of query arguments cannot exceed 32767`). Satu baris
    supply_records memakai 7 argumen, jadi regenerasi besar (banyak hari x
    lokasi x komoditas) akan menabrak batas itu kalau dijadikan satu INSERT.
    1000 baris per potong = ~7000 argumen, jauh di bawah batas.
    """
    for i in range(0, len(rows), per):
        yield rows[i : i + per]


async def _upsert_supply(session, rows: list[dict], now: datetime) -> None:
    if not rows:
        return
    for bagian in _potong(rows):
        stmt = pg_insert(SupplyRecord).values(
            [{**row, "generated_at": now} for row in bagian]
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_supply_records_loc_com_time_source",
            set_={
                "quantity_kg": stmt.excluded.quantity_kg,
                "generated_at": stmt.excluded.generated_at,
            },
            where=SupplyRecord.origin == "demo",
        )
        await session.execute(stmt)


async def _upsert_demand(session, rows: list[dict], now: datetime) -> None:
    """Idempoten pada (lokasi, komoditas, recorded_at); kanonik tidak ditimpa.

    `DO UPDATE ... WHERE origin='demo'` berarti bentrokan dengan baris kanonik
    (seed) tidak mengubah apa pun — baris 8 Okt 12:00 tetap milik seed.
    """
    if not rows:
        return
    for bagian in _potong(rows):
        stmt = pg_insert(DemandRecord).values(
            [{**row, "generated_at": now} for row in bagian]
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_demand_records_loc_com_time",
            set_={
                "quantity_kg": stmt.excluded.quantity_kg,
                "needed_by": stmt.excluded.needed_by,
                "generated_at": stmt.excluded.generated_at,
            },
            where=DemandRecord.origin == "demo",
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
        for bagian in _potong(subset):
            stmt = pg_insert(PriceSignal).values(
                [{**row, "generated_at": now} for row in bagian]
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
    for bagian in _potong(rows):
        stmt = pg_insert(MenuPlan).values([{**row, "generated_at": now} for row in bagian])
        stmt = stmt.on_conflict_do_nothing(constraint="uq_menu_plans_loc_date")
        await session.execute(stmt)


def _komoditas_per_lokasi(baselines: dict) -> dict:
    """Peta lokasi → komoditas yang dipasoknya (dasar komoditas catatan limbah).

    Limbah selalu punya material; komoditasnya diambil dari pasokan lokasi itu
    supaya `commodity_id` bukan karangan.
    """
    peta: dict = {}
    for _key, location_id, commodity_id, _base in baselines["supply_pairs"]:
        daftar = peta.setdefault(location_id, [])
        if commodity_id not in daftar:
            daftar.append(commodity_id)
    return peta


async def _insert_events(
    session,
    end: datetime,
    now: datetime,
    commodities_by_location: dict,
) -> None:
    """Tulis kiriman + limbah demo untuk rencana 8 Okt..ujung rencana.

    Idempoten lewat id deterministik (`_event_id`) + `ON CONFLICT (id) DO NOTHING`.
    Kiriman hanya dibuat untuk rencana yang BELUM punya kiriman APA PUN, sehingga:

    - hari kanonik (1–7 Okt) yang sudah punya kiriman tidak pernah tertimpa;
    - panggilan kedua tidak menambah baris.

    `menu_plan_id` baru diketahui setelah menu ditulis, karena itu fungsi ini
    membaca ulang rencana dari DB (bukan dari `plan_menu_plan_rows`, yang belum
    punya id).
    """
    batas = EVENT_DEMO_START.date()
    baris = (
        await session.execute(
            select(
                MenuPlan.id,
                MenuPlan.location_id,
                MenuPlan.plan_date,
                MenuPlan.planned_portions,
            ).where(
                MenuPlan.plan_date >= batas,
                MenuPlan.plan_date <= end.date(),
            )
        )
    ).all()
    if not baris:
        return

    rencana = [
        {
            "menu_plan_id": r[0],
            "location_id": r[1],
            "plan_date": r[2],
            "planned_portions": int(r[3]),
        }
        for r in baris
    ]
    # 22 Okt 2026: rencana dibaca dari DB, tetapi baris menu bisa GAGAL masuk
    # karena `ON CONFLICT (location_id, plan_date) DO NOTHING` kalah oleh menu
    # kanonik (kunci unik tidak memuat `origin`). Kalau id hasil rencana dipakai
    # apa adanya, INSERT kiriman menabrak FK `delivery_events_menu_plan_id_fkey`
    # dan seluruh init-demo berhenti. Saring dulu ke id yang benar-benar ada.
    ada = set(
        (
            await session.execute(
                select(MenuPlan.id).where(
                    MenuPlan.id.in_([r["menu_plan_id"] for r in rencana])
                )
            )
        )
        .scalars()
        .all()
    )
    rencana = [r for r in rencana if r["menu_plan_id"] in ada]
    if not rencana:
        return

    sudah_punya = set(
        (
            await session.execute(
                select(DeliveryEvent.menu_plan_id).where(
                    DeliveryEvent.menu_plan_id.in_(
                        [r["menu_plan_id"] for r in rencana]
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    kiriman = [
        r
        for r in plan_delivery_rows(rencana, now=now)
        if r["menu_plan_id"] not in sudah_punya
    ]
    limbah = plan_disposal_rows(rencana, commodities_by_location)

    if kiriman:
        await session.execute(
            pg_insert(DeliveryEvent)
            .values([{**row, "generated_at": now} for row in kiriman])
            .on_conflict_do_nothing(index_elements=["id"])
        )
    if limbah:
        await session.execute(
            pg_insert(DisposalEvent)
            .values([{**row, "generated_at": now} for row in limbah])
            .on_conflict_do_nothing(index_elements=["id"])
        )


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
    menu_start: datetime | None = None,
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
                start=start, end=end, interval_hours=interval_hours, ref=ref,
                menu_start=menu_start, **baselines
            )
            before = {
                "supply": await _count_origin(session, SupplyRecord, "demo"),
                "demand": await _count_origin(session, DemandRecord, "demo"),
                "prices": await _count_origin(session, PriceSignal, "demo"),
                "menu_plans": await _count_origin(session, MenuPlan, "demo"),
                "deliveries": await _count_origin(session, DeliveryEvent, "demo"),
                "disposals": await _count_origin(session, DisposalEvent, "demo"),
            }
            now = datetime.now(UTC)
            # Ditulis per tahap dengan commit masing-masing. Satu transaksi raksasa
            # (3.870 pasokan + 648 permintaan + 520 menu + 290 limbah) menahan
            # ratusan kunci FK sekaligus; bila proses lain (sesi lain, atau
            # permintaan HTTP di proses yang sama) menulis tabel yang sama,
            # Postgres bisa memilih korban deadlock. Commit per tahap mempersingkat
            # jendela kunci; generator tetap idempoten sehingga aman diulang.
            await _upsert_supply(session, plan["supply"], now)
            await session.commit()
            await _upsert_demand(session, plan["demand"], now)
            await session.commit()
            await _upsert_prices(session, plan["prices"], now)
            await session.commit()
            await _insert_menu_plans(session, plan["menu_plans"], now)
            await session.commit()
            # Kiriman & limbah menunjuk `menu_plan_id` → ditulis SETELAH menu ada.
            await _insert_events(session, end, now, _komoditas_per_lokasi(baselines))
            await session.commit()
            after = {
                "supply": await _count_origin(session, SupplyRecord, "demo"),
                "demand": await _count_origin(session, DemandRecord, "demo"),
                "prices": await _count_origin(session, PriceSignal, "demo"),
                "menu_plans": await _count_origin(session, MenuPlan, "demo"),
                "deliveries": await _count_origin(session, DeliveryEvent, "demo"),
                "disposals": await _count_origin(session, DisposalEvent, "demo"),
            }
    finally:
        await engine.dispose()

    counts = {
        name: {
            "planned": len(plan[name]),
            "added": after[name] - before[name],
            "in_db": after[name],
        }
        for name in ("supply", "demand", "prices", "menu_plans")
    }
    # Kiriman/limbah: `planned` datang dari `event_plan` (dihitung per hari rencana
    # sejak 8 Okt), bukan `len(plan[...])` — rencananya memang bukan daftar baris.
    for name in ("deliveries", "disposals"):
        counts[name] = {
            "planned": plan["event_plan"][name],
            "added": after[name] - before[name],
            "in_db": after[name],
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
    menu_start: datetime | None = None,
) -> dict:
    """Sama seperti `generate_timeseries`, TANPA menulis apa pun."""
    engine = create_engine(database_url or _database_url())
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            baselines = await _collect_baselines(session)
            plan = plan_all(
                start=start, end=end, interval_hours=interval_hours, ref=ref,
                menu_start=menu_start, **baselines
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
            "demand": {"planned": len(plan["demand"])},
            "prices": {"planned": len(plan["prices"])},
            "menu_plans": {
                "planned": len(plan["menu_plans"]),
                "existing_rows": existing_menu,
            },
            "deliveries": {"planned": plan["event_plan"]["deliveries"]},
            "disposals": {"planned": plan["event_plan"]["disposals"]},
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
            if any(deleted.values()):
                # Reset data demo = generasi ledger baru. Blok lama jadi arsip,
                # bukan dihapus, supaya rantai hash tetap utuh (audit N3).
                from app.services.ledger_service import bump_generation

                await bump_generation(session)
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
        "demand_records": int(pratinjau["counts"]["demand"]["planned"]),
        "price_signals": int(pratinjau["counts"]["prices"]["planned"]),
        "menu_plans": int(pratinjau["counts"]["menu_plans"]["planned"]),
        # Kiriman & limbah ikut dijaga: keduanya kini punya `origin` (migrasi 017),
        # jadi bisa hilang tanpa jejak bila purge dijalankan lalu run-nya mati.
        "deliveries": int(pratinjau["counts"]["deliveries"]["planned"]),
        "disposals": int(pratinjau["counts"]["disposals"]["planned"]),
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
            # Permintaan demo juga dijaga: rentangnya sama dengan pasokan (baris
            # kanonik 8 Okt berada di luar rentang ini, jadi tidak ikut dihitung).
            "demand_records": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(DemandRecord)
                        .where(
                            DemandRecord.recorded_at >= start,
                            DemandRecord.recorded_at < batas_aktual,
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
            # Kiriman dihitung lewat tanggal RENCANA (bukan delivered_at), sebab
            # kiriman hari terakhir jatuh 14:00 — di luar `end` yang pukul 00:00.
            "deliveries": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(DeliveryEvent)
                        .join(MenuPlan, MenuPlan.id == DeliveryEvent.menu_plan_id)
                        .where(
                            MenuPlan.plan_date >= EVENT_DEMO_START.date(),
                            MenuPlan.plan_date <= end.date(),
                        )
                    )
                ).scalar()
                or 0
            ),
            # Limbah: seluruh hari rencana terakhir ikut (disposed_at 12:00), jadi
            # batas atasnya `end + 1 hari`, bukan `end`.
            "disposals": int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(DisposalEvent)
                        .where(
                            DisposalEvent.disposed_at >= EVENT_DEMO_START,
                            DisposalEvent.disposed_at < end + timedelta(days=1),
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
            for model in (SupplyRecord, DemandRecord, PriceSignal, MenuPlan):
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
