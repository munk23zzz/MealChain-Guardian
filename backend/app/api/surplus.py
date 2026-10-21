"""GET /surplus/allocations — rencana alokasi surplus lintas lokasi.

LATAR (terukur 2026-10-20). Panel "Rencana alokasi surplus" di halaman Surplus &
Limbah selalu kosong. Penyebabnya dua aturan yang saling mengunci: halaman itu
hanya dibuka peran SPPG (`SURPLUS_ROLES`), sedangkan `GET /balance/map` untuk
peran SPPG hanya mengirim lokasinya sendiri (Ruling 2026-10-14). Panel memasangkan
surplus -> kekurangan dari daftar itu, jadi dengan satu lokasi hasilnya selalu
"Tidak ada pasangan..." (terukur: Kepala Bandung melihat 0 lokasi surplus).

Endpoint ini menghitung pasangannya di SERVER, lintas lokasi.

Kontrak:
- `commodity` wajib (nama atau id yang ada di tabel `commodities`).
- `limit` 1..20, default 6.
- Hanya sisi TERUKUR yang boleh jadi sumber/tujuan (PLAN-023): lokasi tanpa
  baris permintaan tidak boleh menyumbang surplus, lokasi tanpa baris pasokan
  tidak boleh jadi tujuan — angka 0 hasil pengisian bukan fakta.
- Semua peran terautentikasi boleh membaca: isinya pasangan hasil olahan
  (`from`, `to`, `kg`, `distance_km`), BUKAN angka mentah supply/demand per
  lokasi. Ini sejalan dengan `POST /balance/recommend` yang sudah mengirim
  pasangan lintas wilayah ke `sppg_head`.
- `available: false` + `reason` bila tidak ada pasangan, supaya panel bisa
  mengatakan SEBABNYA, bukan sekadar "kosong".
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.dependencies import get_db
from app.core.allocation import Node, build_allocations
from app.core.gaps import calculate_supply_gap
from app.models import (
    Commodity,
    DemandRecord,
    Location,
    PriceSignal,
    SupplyRecord,
    User,
)
from app.services.recommendation_service import HANDLING_FLAT, TRANSPORT_RATE

router = APIRouter(prefix="", tags=["surplus"])

MAX_LIMIT = 20
DEFAULT_LIMIT = 6
#: Ambang minimum surplus PER LOKASI agar layak masuk rencana (permintaan
#: pemilik 20 Okt 2026: "jangan rencanakan surplus jika di bawah 150 kg").
#: Berlaku pada surplus lokasi sumber, bukan pada tiap baris alokasi: sumber
#: 400 kg tetap boleh mengisi tujuan yang kekurangannya 40 kg.
MIN_SURPLUS_KG = Decimal("150")


async def _resolve_commodity(db: AsyncSession, value: str) -> Commodity:
    com = (
        await db.execute(
            select(Commodity).where(
                (Commodity.name == value) | (Commodity.id.cast(String) == value)
            )
        )
    ).scalar_one_or_none()
    if com is None:
        raise HTTPException(status_code=404, detail="commodity tidak ditemukan")
    return com


@router.get("/surplus/allocations")
async def surplus_allocations(
    commodity: str,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    as_of: datetime | None = Query(
        None, description="Batas atas waktu baris (default: sekarang)"
    ),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pasangan surplus -> kekurangan lintas lokasi untuk satu komoditas.

    Sengaja TIDAK memakai `apply_location_scope`: rencana pengalihan antar-SPPG
    tidak punya arti di dalam satu lokasi. Yang dikirim hanya pasangan (dari, ke,
    kg, jarak) — bukan tabel supply/demand.
    """
    com = await _resolve_commodity(db, commodity)
    batas = as_of.astimezone(UTC) if as_of else datetime.now(UTC)

    locs = (
        (await db.execute(select(Location).order_by(Location.name.asc())))
        .scalars()
        .all()
    )

    async def _latest_by_location(model) -> dict:
        rows = (
            (
                await db.execute(
                    select(model)
                    .where(
                        model.commodity_id == com.id,
                        model.recorded_at <= batas,
                    )
                    .order_by(
                        model.location_id.asc(),
                        model.recorded_at.desc(),
                        model.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        out: dict = {}
        for row in rows:
            out.setdefault(row.location_id, row)
        return out

    sup_by_loc = await _latest_by_location(SupplyRecord)
    dem_by_loc = await _latest_by_location(DemandRecord)

    nodes = []
    for loc in locs:
        s_row, d_row = sup_by_loc.get(loc.id), dem_by_loc.get(loc.id)
        gap = calculate_supply_gap(
            s_row.quantity_kg if s_row is not None else 0,
            d_row.quantity_kg if d_row is not None else 0,
        )
        nodes.append(
            (
                loc,
                gap,
                {
                    "region": loc.region,
                    "latitude": float(loc.latitude) if loc.latitude is not None else None,
                    "longitude": float(loc.longitude) if loc.longitude is not None else None,
                },
                s_row is not None,
                d_row is not None,
            )
        )

    # Pemasok hanya dari lokasi yang permintaannya TERUKUR (sisi cerminnya:
    # tujuan hanya dari lokasi yang pasokannya terukur) — sama dengan klien.
    surpluses = [
        Node(location=loc.name, kg=gap.surplus_kg, **meta)
        for loc, gap, meta, _s_ok, d_ok in nodes
        if gap.surplus_kg > 0 and d_ok
    ]
    shortages = [
        Node(location=loc.name, kg=gap.shortage_kg, **meta)
        for loc, gap, meta, s_ok, _d_ok in nodes
        if gap.shortage_kg > 0 and s_ok
    ]

    sumber_layak = [n for n in surpluses if n.kg >= MIN_SURPLUS_KG]
    surplus_di_bawah_ambang = sum(
        (n.kg for n in surpluses if n.kg < MIN_SURPLUS_KG), start=Decimal("0")
    )
    pairs = build_allocations(
        surpluses,
        shortages,
        limit=limit,
        min_surplus_kg=MIN_SURPLUS_KG,
    )
    # Ambang juga berlaku pada TIAP pengiriman: alokasi 5 kg lintas kota tidak
    # masuk akal karena penanganan tetap Rp150.000 selalu kena. Baris seperti
    # itu dibuang, bukan ditampilkan sebagai "rencana".
    pairs_sebelum_ambang = len(pairs)
    pairs = [p for p in pairs if Decimal(str(p["kg"])) >= MIN_SURPLUS_KG]

    # Kelayakan biaya per pasangan (20 Okt 2026). Panel ini murni neraca: 6 kg
    # ke Makassar tetap muncul karena kekurangannya memang 6 kg. Tapi angka itu
    # tidak boleh dibaca sebagai pengiriman yang wajar, jadi biaya tetapnya
    # ditulis: penanganan Rp150.000 per pengiriman SELALU kena, berapa pun kg-nya
    # (`recommendation_service.HANDLING_FLAT`, tarif angkut `TRANSPORT_RATE`).
    price_row = (
        await db.execute(
            select(PriceSignal)
            .where(PriceSignal.commodity_id == com.id, PriceSignal.recorded_at <= batas)
            .order_by(PriceSignal.recorded_at.desc(), PriceSignal.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    harga = Decimal(str(price_row.price_per_kg)) if price_row is not None else None

    for pair in pairs:
        jarak = pair.get("distance_km")
        if harga is None or jarak is None:
            pair.update(
                {
                    "price_per_kg": None,
                    "value_idr": None,
                    "cost_idr": None,
                    "cost_share_pct": None,
                }
            )
            continue
        kg = Decimal(str(pair["kg"]))
        nilai = kg * harga
        biaya = HANDLING_FLAT + (TRANSPORT_RATE * Decimal(jarak) * kg / Decimal(1000))
        pair.update(
            {
                "price_per_kg": float(harga),
                "value_idr": round(float(nilai), 0),
                "cost_idr": round(float(biaya), 0),
                "cost_share_pct": round(float(biaya / nilai * 100), 1) if nilai > 0 else None,
            }
        )

    surplus_kg = float(sum((n.kg for n in sumber_layak), start=0))
    shortage_kg = float(sum((n.kg for n in shortages), start=0))
    allocatable_kg = float(sum((p["kg"] for p in pairs), start=0))

    reason = None
    if not pairs:
        if not surpluses and not shortages:
            reason = "tidak_ada_sisi_terukur"
        elif not surpluses:
            reason = "tidak_ada_surplus_terukur"
        elif not sumber_layak:
            # Ada surplus terukur, tetapi semuanya di bawah ambang 150 kg.
            reason = "surplus_di_bawah_ambang"
        elif not shortages:
            reason = "tidak_ada_kekurangan_terukur"
        elif pairs_sebelum_ambang:
            # Pasangan terbentuk, tetapi tiap pengirimannya < 150 kg.
            reason = "alokasi_di_bawah_ambang"
        else:
            reason = "tidak_ada_pasangan_terukur"

    return {
        "commodity": com.name,
        "as_of": batas.isoformat(),
        "locations_total": len(locs),
        # Hanya sumber yang lolos ambang; angka ini yang dipakai lencana panel.
        "surplus_locations": len(sumber_layak),
        "shortage_locations": len(shortages),
        "min_surplus_kg": float(MIN_SURPLUS_KG),
        "totals": {
            "surplus_kg": round(surplus_kg, 2),
            "shortage_kg": round(shortage_kg, 2),
            "allocatable_kg": round(allocatable_kg, 2),
            # Bagian yang TIDAK direncanakan karena tiap lokasi < 150 kg —
            # ditulis supaya angka tidak tampak hilang begitu saja.
            "surplus_below_min_kg": round(float(surplus_di_bawah_ambang), 2),
        },
        "available": bool(pairs),
        "reason": reason,
        "pairs": pairs,
    }
