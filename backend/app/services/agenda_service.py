"""Agenda harian untuk tab "Hari Ini" (GET /agenda) — permintaan pemilik 2026-10-16.

Kenapa modul ini ada: "Hari Ini" adalah satu-satunya halaman yang NAMANYA harian,
tetapi seluruh isinya dihitung dari "sekarang" sehingga pertanyaan "bagaimana kalau
saya lihat tanggal lain?" tidak bisa dijawab sama sekali. Sementara itu
`menu_plans` menyimpan rencana 10 SPPG untuk SETIAP hari 1 Sep–5 Nov dan hanya
dipakai satu angka KPI (Meal Continuity) — datanya ada, tapi tak pernah terlihat.

Tiga aturan yang dijaga modul ini:

1. **Batas hari = WIB (UTC+7)**, bukan UTC. `plan_date` bertipe DATE (tanpa zona),
   kolom waktu lain `timestamptz`. Konversi memakai `timezone('Asia/Jakarta', ts)`
   supaya kiriman pukul 00:30 WIB jatuh di hari WIB-nya, seperti yang dibaca
   operator di layar ("23.38 WIB").
2. **Hari tanpa baris menulis `available: false`**, bukan nol yang tampak
   terukur. Aturan repo: indikator yang belum bisa dihitung ditulis alasannya,
   bukan diganti nol.
3. **Cakupan mengikuti `app/core/scope.py`**: rencana menu, kiriman, limbah,
   pasokan, harga, dan keputusan ikut scope user (endpoint `/supply`, `/price`,
   `/decisions` memakai aturan yang sama). Sebaliknya **batch** tetap lintas
   lokasi seperti GET /batches — batch adalah barang sisi SUMBER (pemasok), bukan
   target SPPG.

Modul ini murni baca: satu kueri agregat per tabel (GROUP BY hari), jadi 62 hari
pun hanya tujuh kueri — bukan 62×7.
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scope import scope_location_id
from app.models import (
    Batch,
    Decision,
    DeliveryEvent,
    DisposalEvent,
    MenuPlan,
    PriceSignal,
    SupplyRecord,
    User,
)

WIB = timezone(timedelta(hours=7))
TZ_NAME = "Asia/Jakarta"
MAX_DAYS = 62

# Bagian yang ikut scope SPPG (sisi TUJUAN) vs bagian lintas lokasi (sisi SUMBER).
_TARGET_SECTIONS = ("menu", "delivery", "disposal", "supply", "price", "decisions")
SOURCE_SECTIONS = ("batches_expiring",)


def day_bounds(d: date) -> tuple[datetime, datetime]:
    """Rentang UTC yang mewakili satu hari WIB [00:00 WIB, 24:00 WIB)."""
    start = datetime.combine(d, time.min, tzinfo=WIB)
    return start, start + timedelta(days=1)


def _wib_day(column):
    """Ekspresi SQL: kolom timestamptz → tanggal menurut zona WIB.

    Zona ditulis sebagai LITERAL, bukan parameter terikat: PostgreSQL
    membandingkan ekspresi di SELECT dan GROUP BY secara struktural, sementara
    setiap bind parameter adalah simpul berbeda — with a bind param, `GROUP BY
    timezone($6, ts)` tak dianggap sama dengan `timezone($1, ts)` di SELECT dan
    kueri ditolak ("must appear in the GROUP BY clause"). Literal menghilangkan
    kelas masalah itu.
    """
    return func.cast(
        func.timezone(literal_column("'Asia/Jakarta'"), column), Date
    )


def _bagian(available: bool, **angka) -> dict:
    return {"available": available, **angka}


def _menu_kosong() -> dict:
    return _bagian(False, rows=0, planned_portions=0)


def _kiriman_kosong() -> dict:
    return _bagian(False, rows=0, delivered_portions=0)


def _limbah_kosong() -> dict:
    return _bagian(False, rows=0, quantity_kg=0.0)


def _hitung_kosong() -> dict:
    return _bagian(False, rows=0)


def _keputusan_kosong() -> dict:
    return _bagian(False, rows=0, by_status={})


async def _agregat_harian(db: AsyncSession, statement) -> dict[date, tuple]:
    """Jalankan statement ber-GROUP BY hari → {tanggal: tuple nilai}."""
    hasil: dict[date, tuple] = {}
    for row in (await db.execute(statement)).all():
        hasil[row[0]] = tuple(row[1:])
    return hasil


async def compute_agenda(
    db: AsyncSession, user: User, start: date, end: date
) -> dict:
    """Agenda harian [start, end] inklusif; setiap hari selalu muncul.

    Dipanggil setelah validasi rentang di lapisan API (start <= end, <= MAX_DAYS).
    """
    scope = scope_location_id(user)
    awal, _ = day_bounds(start)
    _, akhir = day_bounds(end)

    # ---------------------------------------------------------- rencana menu
    stmt = (
        select(
            MenuPlan.plan_date,
            func.count(),
            func.coalesce(func.sum(MenuPlan.planned_portions), 0),
        )
        .where(MenuPlan.plan_date >= start, MenuPlan.plan_date <= end)
        .group_by(MenuPlan.plan_date)
    )
    if scope is not None:
        stmt = stmt.where(MenuPlan.location_id == scope)
    menu = await _agregat_harian(db, stmt)

    # -------------------------------------------------------------- kiriman
    stmt = (
        select(
            _wib_day(DeliveryEvent.delivered_at).label("hari"),
            func.count(),
            func.coalesce(func.sum(DeliveryEvent.delivered_portions), 0),
        )
        .join(MenuPlan, MenuPlan.id == DeliveryEvent.menu_plan_id)
        .where(DeliveryEvent.delivered_at >= awal, DeliveryEvent.delivered_at < akhir)
        .group_by(_wib_day(DeliveryEvent.delivered_at))
    )
    if scope is not None:
        stmt = stmt.where(MenuPlan.location_id == scope)
    kiriman = await _agregat_harian(db, stmt)

    # --------------------------------------------------------------- limbah
    stmt = (
        select(
            _wib_day(DisposalEvent.disposed_at).label("hari"),
            func.count(),
            func.coalesce(func.sum(DisposalEvent.quantity_kg), 0),
        )
        .where(
            DisposalEvent.disposed_at >= awal, DisposalEvent.disposed_at < akhir
        )
        .group_by(_wib_day(DisposalEvent.disposed_at))
    )
    if scope is not None:
        stmt = stmt.where(DisposalEvent.location_id == scope)
    limbah = await _agregat_harian(db, stmt)

    # -------------------------------------------------------------- pasokan
    stmt = (
        select(_wib_day(SupplyRecord.recorded_at).label("hari"), func.count())
        .where(SupplyRecord.recorded_at >= awal, SupplyRecord.recorded_at < akhir)
        .group_by(_wib_day(SupplyRecord.recorded_at))
    )
    if scope is not None:
        stmt = stmt.where(SupplyRecord.location_id == scope)
    pasokan = await _agregat_harian(db, stmt)

    # ---------------------------------------------------------------- harga
    stmt = (
        select(_wib_day(PriceSignal.recorded_at).label("hari"), func.count())
        .where(PriceSignal.recorded_at >= awal, PriceSignal.recorded_at < akhir)
        .group_by(_wib_day(PriceSignal.recorded_at))
    )
    if scope is not None:
        stmt = stmt.where(PriceSignal.location_id == scope)
    harga = await _agregat_harian(db, stmt)

    # -------------------------------------------------- batch kedaluwarsa
    # Sisi SUMBER: lintas lokasi, sama seperti GET /batches (panel chaos).
    stmt = (
        select(_wib_day(Batch.usable_until).label("hari"), func.count())
        .where(
            Batch.usable_until.is_not(None),
            Batch.usable_until >= awal,
            Batch.usable_until < akhir,
        )
        .group_by(_wib_day(Batch.usable_until))
    )
    batch = await _agregat_harian(db, stmt)

    # ------------------------------------------------------------ keputusan
    stmt = (
        select(
            _wib_day(Decision.created_at).label("hari"),
            func.count(),
        )
        .where(Decision.created_at >= awal, Decision.created_at < akhir)
        .group_by(_wib_day(Decision.created_at))
    )
    if scope is not None:
        stmt = stmt.where(Decision.target_location_id == scope)
    keputusan = await _agregat_harian(db, stmt)

    # status per hari (untuk agenda; satu kueri terpisah supaya agregat di atas
    # tetap satu baris per hari).
    stmt = (
        select(
            _wib_day(Decision.created_at).label("hari"),
            Decision.status,
            func.count(),
        )
        .where(Decision.created_at >= awal, Decision.created_at < akhir)
        .group_by(_wib_day(Decision.created_at), Decision.status)
    )
    if scope is not None:
        stmt = stmt.where(Decision.target_location_id == scope)
    status_per_hari: dict[date, dict[str, int]] = {}
    for hari, status, jumlah in (await db.execute(stmt)).all():
        status_per_hari.setdefault(hari, {})[status] = jumlah

    # ---------------------------------------------------------------- susun
    days = []
    hari_ini = start
    while hari_ini <= end:
        m = menu.get(hari_ini)
        k = kiriman.get(hari_ini)
        lb = limbah.get(hari_ini)
        p = pasokan.get(hari_ini)
        h = harga.get(hari_ini)
        b = batch.get(hari_ini)
        c = keputusan.get(hari_ini)

        hari = {
            "date": hari_ini.isoformat(),
            "menu": (
                _bagian(True, rows=m[0], planned_portions=int(m[1]))
                if m
                else _menu_kosong()
            ),
            "delivery": (
                _bagian(True, rows=k[0], delivered_portions=int(k[1]))
                if k
                else _kiriman_kosong()
            ),
            "disposal": (
                _bagian(True, rows=lb[0], quantity_kg=float(lb[1]))
                if lb
                else _limbah_kosong()
            ),
            "supply": _bagian(True, rows=p[0]) if p else _hitung_kosong(),
            "price": _bagian(True, rows=h[0]) if h else _hitung_kosong(),
            "batches_expiring": (
                _bagian(True, rows=b[0]) if b else _hitung_kosong()
            ),
            "decisions": (
                _bagian(True, rows=c[0], by_status=status_per_hari.get(hari_ini, {}))
                if c
                else _keputusan_kosong()
            ),
        }
        # Titik penanda di kalender: berapa bagian yang benar-benar ada isinya.
        hari["activity"] = sum(
            1
            for nama in (*_TARGET_SECTIONS, *SOURCE_SECTIONS)
            if hari[nama]["available"]
        )
        days.append(hari)
        hari_ini += timedelta(days=1)

    return {
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timezone": TZ_NAME,
        },
        "scope": {
            "location_id": str(scope) if scope else None,
            "national": scope is None,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
    }
