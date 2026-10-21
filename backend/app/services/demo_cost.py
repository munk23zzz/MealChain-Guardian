"""Biaya keputusan demo dihitung dari baris nyata, bukan angka tulisan tangan.

Masalah yang diperbaiki (audit 19 Okt 2026): `api/demo.py` menulis
`cost_breakdown` yang sama untuk SEMUA kasus — purchase 15.720.000 + logistics
486.000 — sementara `safe_delivered_cost` tiap kasus berbeda. Akibatnya
`shortage-darurat` (SDC 14.787.096) dan `supplier-janggal` (SDC 9.200.000)
punya komponen beli yang LEBIH BESAR dari totalnya: mustahil secara aritmetika,
dan hanya 2 dari 6 komponen yang terisi.

Modul ini menyusun ulang biaya dengan input yang benar-benar ada di database:
batch terikat (pemasok, kesegaran, status keamanan), kutipan harga pemasok,
jarak antar-SPPG dari tabel logistik, dan jarak pemasok → SPPG. Rumusnya
`core.safe_delivered_cost` — mesin yang sama yang dipakai rekomendasi nyata,
sehingga rincian selalu menjumlah persis ke total.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import haversine_km
from app.core.logistics import estimate_logistics
from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)
from app.models.batches import Batch
from app.models.decisions import Decision
from app.models.locations import Location
from app.models.price_signals import PriceSignal
from app.models.suppliers import Supplier

__all__ = ["hitung_biaya_demo"]

# Sama dengan recommendation_service — satu angka untuk seluruh aplikasi.
TRANSPORT_RATE = Decimal("300")  # Rp per km per ton
HANDLING_FLAT = Decimal("150000")

_TWO_DP = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_TWO_DP)


async def _batch_terikat(
    db: AsyncSession, decision: Decision, sekarang: datetime
) -> Batch | None:
    """Batch yang sama dengan yang dipakai `_ikat_sumber` (aturan identik)."""
    return (
        await db.execute(
            select(Batch)
            .where(
                Batch.location_id == decision.source_location_id,
                Batch.commodity_id == decision.commodity_id,
                Batch.usable_until.is_not(None),
                Batch.usable_until >= sekarang,
                # Safety FAIL = hard exclusion terkunci (`core/scoring.py`).
                # Tanpa filter ini batch gagal uji bisa terpilih sebagai batch
                # terikat, lalu `calculate_safe_delivered_cost` melempar
                # ValueError dan seluruh perhitungan biaya (termasuk tombol
                # "Hitung ulang biaya") mati karena data yang sah.
                Batch.safety_status != "fail",
            )
            .order_by(Batch.quantity_kg.desc(), Batch.id.asc())
            .limit(1)
        )
    ).scalars().first()


async def _harga_satuan(
    db: AsyncSession, decision: Decision, supplier_id, lokasi_id=None
) -> tuple[Decimal | None, str | None]:
    """Harga per kg: kutipan pemasok dulu, lalu harga acuan lokasi asal.

    Mengembalikan (harga, sumber). `None` bila tidak ada baris harga sama sekali
    — pemanggil wajib melewati perhitungan, bukan memakai 0.
    """
    titik = lokasi_id if lokasi_id is not None else decision.source_location_id
    dasar = (
        select(PriceSignal)
        .where(
            PriceSignal.location_id == titik,
            PriceSignal.commodity_id == decision.commodity_id,
        )
        .order_by(PriceSignal.recorded_at.desc())
        .limit(1)
    )
    if supplier_id is not None:
        kutipan = (
            await db.execute(
                dasar.where(
                    PriceSignal.supplier_id == supplier_id,
                    PriceSignal.source == "supplier_quote",
                )
            )
        ).scalars().first()
        if kutipan is not None and kutipan.price_per_kg is not None:
            return Decimal(str(kutipan.price_per_kg)), "kutipan pemasok"
    acuan = (
        await db.execute(
            dasar.where(PriceSignal.source == "pihps_reference")
        )
    ).scalars().first()
    if acuan is None:
        acuan = (await db.execute(dasar)).scalars().first()
    if acuan is None or acuan.price_per_kg is None:
        return None, None
    return Decimal(str(acuan.price_per_kg)), "harga acuan PIHPS lokasi asal"


async def hitung_biaya_demo(
    db: AsyncSession, decision: Decision, sekarang: datetime
) -> bool:
    """Isi `safe_delivered_cost`, `cost_breakdown`, dan `supplier_id` dari data.

    Kembalikan True bila biaya berhasil dihitung. False berarti bahan tidak
    cukup (mis. tidak ada harga atau lokasi tidak dikenal) — keputusan
    dibiarkan tanpa rincian dan UI menampilkan alasannya, bukan angka karangan.
    """
    if decision.quantity_kg is None or float(decision.quantity_kg) <= 0:
        return False

    lokasi = {
        l.id: l
        for l in (
            await db.execute(
                select(Location).where(
                    Location.id.in_(
                        [decision.source_location_id, decision.target_location_id]
                    )
                )
            )
        ).scalars().all()
    }
    asal = lokasi.get(decision.source_location_id)
    tujuan = lokasi.get(decision.target_location_id)
    if tujuan is None:
        return False

    # Pengadaan (`supplier_procurement`) tidak punya lokasi asal: barang datang
    # dari pemasok langsung ke SPPG tujuan, jadi tidak ada angkut antar-SPPG.
    pengadaan = asal is None
    if asal is None:
        asal = tujuan

    batch = None if pengadaan else await _batch_terikat(db, decision, sekarang)
    # Pemasok: batch yang terikat, atau identitas yang sudah tercatat. Jangan
    # pernah menimpanya dengan None — pengadaan tidak punya batch.
    supplier_id = batch.supplier_id if batch is not None else decision.supplier_id

    harga, sumber_harga = await _harga_satuan(db, decision, supplier_id, asal.id)
    if harga is None or harga <= 0:
        return False

    if pengadaan:
        linehaul_km = Decimal("0")
    else:
        try:
            jalur = estimate_logistics(asal.name, tujuan.name, float(decision.quantity_kg))
        except ValueError:
            return False
        linehaul_km = Decimal(str(jalur["distance_km"]))
    leg_km: Decimal | None = None
    leg_reference = "tidak_ada_pemasok"
    if supplier_id is not None:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        ).scalars().first()
        if (
            supplier is not None
            and supplier.latitude is not None
            and supplier.longitude is not None
            and asal.latitude is not None
            and asal.longitude is not None
        ):
            leg_km = Decimal(
                str(
                    round(
                        haversine_km(
                            float(supplier.latitude),
                            float(supplier.longitude),
                            float(asal.latitude),
                            float(asal.longitude),
                        ),
                        3,
                    )
                )
            )
            leg_reference = "supplier_coordinates"

    qty = Decimal(str(decision.quantity_kg))
    purchase = _money(qty * harga)
    linehaul_cost = _money(TRANSPORT_RATE * linehaul_km * qty / 1000)
    leg_cost = _money(TRANSPORT_RATE * leg_km * qty / 1000) if leg_km is not None else _money(Decimal("0"))
    transport = linehaul_cost + leg_cost

    # Kesegaran & keamanan datang dari batch yang benar-benar terikat. Tanpa
    # batch, keduanya tidak diketahui — mesin memperlakukan safety "pending"
    # (tanpa penalti) dan kesegaran harus diberikan; kita pakai 1.0 hanya bila
    # memang tidak ada batch, dan menandainya di catatan.
    freshness = Decimal("1")
    safety_status = "pending"
    if batch is not None:
        if batch.freshness_score is not None:
            freshness = Decimal(str(batch.freshness_score))
        safety_status = batch.safety_status or "pending"

    hasil = calculate_safe_delivered_cost(
        SafeDeliveredCostInputs(
            purchase_cost=purchase,
            transport_cost=transport,
            handling_cost=HANDLING_FLAT,
            freshness_score=freshness,
            safety_status=safety_status,
        )
    )

    komponen = {
        "purchase": str(hasil.purchase_cost),
        "transport": str(hasil.transport_cost),
        "logistics": str(hasil.transport_cost),
        "transport_linehaul": str(linehaul_cost),
        "transport_supplier_leg": str(leg_cost),
        "supplier_leg_km": str(leg_km) if leg_km is not None else None,
        "supplier_leg_reference": leg_reference,
        "handling": str(hasil.handling_cost),
        "expected_loss": str(hasil.expected_loss),
        "freshness_risk": str(hasil.freshness_risk_penalty),
        "safety_penalty": str(hasil.safety_risk_penalty),
        "basis": (
            f"dihitung: {sumber_harga} Rp{harga}/kg, linehaul {linehaul_km} km"
            + (f", pemasok {leg_km} km" if leg_km is not None else "")
            + (f", batch {str(batch.id)[:8]}" if batch is not None else ", tanpa batch terikat")
        ),
    }

    decision.safe_delivered_cost = hasil.total
    decision.cost_breakdown = komponen
    # `supplier_id` SENGAJA tidak ditulis di sini. Batch hanya dipakai sebagai
    # DASAR HITUNG (harga, jarak, kesegaran) dan id-nya tercatat di `basis`.
    # Menyalin pemasok batch ke keputusan berarti mengarang identitas: satu
    # lokasi bisa punya beberapa pemasok, dan keputusan lama tidak pernah
    # mencatat yang mana. Kolom kosong + "tanpa identitas pemasok" lebih jujur
    # daripada atribusi yang tidak pernah diputuskan (arahan 19 Okt 2026).
    return True
