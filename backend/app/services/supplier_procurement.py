"""Penilaian pemasok → SPPG untuk Demo Control (keputusan pemilik 2026-10-19).

Kenapa modul terpisah dari `recommendation_service`: pipeline
`regional_balance` menilai PEMINDAHAN antar SPPG (surplus satu kota →
kekurangan kota lain) dan mengikat batch di kota ASAL. Demo Control menilai
hal lain: PEMASOK yang sudah memasok SPPG itu sendiri.

Definisi "memasok SPPG ini" memakai data yang memang ada, tanpa tabel baru:

- pemasok terdaftar pada lokasi SPPG (`suppliers.location_id`);
- stoknya tercatat di lokasi itu (`batches.location_id`, komoditas sama);
- penawaran harganya dicatat untuk lokasi itu (`price_signals`
  `source='supplier_quote'`, `supplier_id` terisi);
- jarak angkut diukur dari KOORDINAT PEMASOK ke KOORDINAT SPPG
  (`core.supplier_leg.supplier_leg_km`), bukan dari pusat kota.

Tidak ada angka karangan: pemasok tanpa stok, tanpa penawaran, atau
dikecualikan di SPPG tersebut tetap tampil sebagai kandidat BESERTA alasannya —
bukan dibuang diam-diam dan bukan diberi angka tebakan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.freshness import classify_freshness, evaluate_freshness
from app.core.policy_store import profil_untuk_komoditas
from app.core.price import price_deviation
from app.core.safe_delivered_cost import (
    SafeDeliveredCostInputs,
    calculate_safe_delivered_cost,
)
from app.core.scoring import CandidateScoreFactors, calculate_candidate_score
from app.core.supplier_leg import supplier_leg_km
from app.core.trip_cost import biaya_angkut_trip
from app.models import (
    Batch,
    BatchReceipt,
    Commodity,
    Decision,
    DecisionEvidence,
    DemandRecord,
    Location,
    PriceSignal,
    Supplier,
    SupplierExclusion,
    SupplyRecord,
)

__all__ = [
    "SupplierCandidate",
    "evaluate_suppliers",
    "persist_supplier_binding",
]

#: Tarif per ton-km DIHENTIKAN 2026-10-29b: angkut per trip di core/trip_cost.py.
#: Biaya handling tetap yang sama dengan pipeline rekomendasi.
HANDLING_FLAT = Decimal("150000")

_SAFETY_RANK = {"pass": 0, "pending": 1, "needs_verification": 2, "fail": 3}
_SHELF_LIFE = {
    "telur": settings.shelf_life_days_telur,
    "ayam": settings.shelf_life_days_ayam,
    "wortel": settings.shelf_life_days_wortel,
    "beras": settings.shelf_life_days_beras,
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


@dataclass(frozen=True)
class SupplierCandidate:
    """Satu pemasok yang memasok SPPG target, dinilai apa adanya."""

    supplier_id: str
    supplier_name: str
    reliability: Decimal
    capacity_kg_per_week: Decimal | None
    quote_price: Decimal | None
    reference_price: Decimal | None
    available_kg: Decimal
    quantity_kg: Decimal
    leg_km: Decimal | None
    freshness_score: Decimal
    freshness_status: str
    safety_status: str
    excluded: bool
    exclusion_reason: str | None
    eligible: bool
    reasons: tuple[str, ...] = ()
    score: Decimal | None = None
    safe_delivered_cost: Decimal | None = None
    cost_breakdown: dict = field(default_factory=dict)
    batch_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        # Deviasi & klasifikasi harga lahir dari fungsi domain yang sama dengan
        # endpoint `/price/deviation`; `None` bila salah satu harga tidak ada.
        price_deviation_pct: str | None = None
        klasifikasi_harga: str | None = None
        if self.quote_price is not None and self.reference_price is not None:
            try:
                hasil = price_deviation(self.quote_price, self.reference_price)
            except (ValueError, ZeroDivisionError):
                hasil = None
            if isinstance(hasil, dict):
                nilai = hasil.get("deviation_pct")
                price_deviation_pct = str(nilai) if nilai is not None else None
                klasifikasi_harga = str(hasil.get("status") or "") or None
        return {
            "supplier_id": self.supplier_id,
            "supplier": self.supplier_name,
            "reliability": str(self.reliability),
            "capacity_kg_per_week": _str_or_none(self.capacity_kg_per_week),
            "quote_price_per_kg": _str_or_none(self.quote_price),
            "reference_price_per_kg": _str_or_none(self.reference_price),
            # Deviasi harga dihitung DI SINI oleh kode, bukan oleh model, dan
            # ikut tersimpan di jejak OPTIMIZE. Tanpa ini angka deviasi hanya
            # ada di fakta worker Price (teks model) sehingga verifier menandai
            # narasi supervisor "harga deviasi -1,92%" sebagai angka tanpa
            # sumber dan verdict jatuh ke `flagged` (29 Okt 2026).
            "price_deviation_pct": price_deviation_pct,
            "price_classification": klasifikasi_harga,
            "available_kg": str(self.available_kg),
            "quantity_kg": str(self.quantity_kg),
            "leg_km": _str_or_none(self.leg_km),
            "leg_reference": (
                "supplier_coordinates" if self.leg_km is not None
                else "supplier_coordinates_missing"
            ),
            "freshness_score": str(self.freshness_score),
            "freshness_status": self.freshness_status,
            "safety_status": self.safety_status,
            "excluded": self.excluded,
            "exclusion_reason": self.exclusion_reason,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "score": _str_or_none(self.score),
            "safe_delivered_cost": _str_or_none(self.safe_delivered_cost),
            "cost_breakdown": dict(self.cost_breakdown),
            "batch_ids": list(self.batch_ids),
        }


def _str_or_none(value) -> str | None:
    return None if value is None else str(value)


def _worst_safety(statuses: set[str]) -> str:
    if not statuses:
        return "pending"
    return max(statuses, key=lambda s: _SAFETY_RANK.get(s, 3))


async def _latest_row(db, model, *conditions, as_of):
    return (
        await db.execute(
            select(model)
            .where(*conditions, model.recorded_at <= as_of)
            .order_by(model.recorded_at.desc(), model.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def evaluate_suppliers(
    db: AsyncSession,
    *,
    target: Location,
    commodity: str,
    as_of: datetime | None = None,
) -> dict:
    """Nilai semua pemasok yang memasok `target` untuk `commodity`.

    Hasil selalu memuat SELURUH pemasok terdaftar di lokasi itu (dengan alasan
    bila tidak layak) supaya angka "berapa pemasok dinilai" bisa dibuktikan.
    """
    as_of = as_of or datetime.now(timezone.utc)

    komoditas = (
        await db.execute(select(Commodity).where(Commodity.name == commodity))
    ).scalar_one_or_none()
    if komoditas is None:
        raise ValueError(f"komoditas {commodity!r} tidak ada di database")

    supply_row = await _latest_row(
        db,
        SupplyRecord,
        SupplyRecord.location_id == target.id,
        SupplyRecord.commodity_id == komoditas.id,
        as_of=as_of,
    )
    demand_row = await _latest_row(
        db,
        DemandRecord,
        DemandRecord.location_id == target.id,
        DemandRecord.commodity_id == komoditas.id,
        as_of=as_of,
    )
    supply_kg = _dec(supply_row.quantity_kg) if supply_row else None
    demand_kg = _dec(demand_row.quantity_kg) if demand_row else None
    gap_kg = (
        max(demand_kg - supply_kg, Decimal("0"))
        if demand_kg is not None and supply_kg is not None
        else Decimal("0")
    )

    reference_row = (
        await db.execute(
            select(PriceSignal)
            .where(
                PriceSignal.location_id == target.id,
                PriceSignal.commodity_id == komoditas.id,
                PriceSignal.source == "pihps_reference",
                PriceSignal.recorded_at <= as_of,
            )
            .order_by(PriceSignal.recorded_at.desc(), PriceSignal.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    reference_price = _dec(reference_row.price_per_kg) if reference_row else None

    pemasok = (
        (
            await db.execute(
                select(Supplier)
                .where(
                    Supplier.location_id == target.id,
                    Supplier.commodity_id == komoditas.id,
                )
                .order_by(Supplier.name.asc())
            )
        )
        .scalars()
        .all()
    )

    exclusions = {
        e.supplier_id: e
        for e in (
            await db.execute(
                select(SupplierExclusion).where(
                    SupplierExclusion.scope_location_id == target.id,
                    SupplierExclusion.status == "active",
                )
            )
        )
        .scalars()
        .all()
    }

    kandidat: list[SupplierCandidate] = []
    # Batch yang sudah punya penerimaan DISETUJUI bukan stok yang bisa dibeli
    # lagi: barangnya sudah masuk dapur, dan DB hanya mengizinkan satu
    # penerimaan disetujui per batch (`uq_batch_receipts_satu_disetujui`).
    # Tanpa gerbang ini kasus demo bisa menunjuk batch yang riwayatnya sudah
    # "diterima", sehingga layar menampilkan barang tiba sendiri padahal tidak
    # ada manusia yang menyetujui penerimaan untuk kasus itu (terukur
    # 30 Okt 2026: keputusan wortel `pending_approval` sudah berstatus terima).
    sudah_diterima = set(
        (
            await db.execute(
                select(BatchReceipt.batch_id)
                .join(Batch, Batch.id == BatchReceipt.batch_id)
                .where(
                    BatchReceipt.status == "disetujui",
                    Batch.location_id == target.id,
                    Batch.commodity_id == komoditas.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for sup in pemasok:
        batch_rows = (
            (
                await db.execute(
                    select(Batch).where(
                        Batch.supplier_id == sup.id,
                        Batch.location_id == target.id,
                        Batch.commodity_id == komoditas.id,
                        Batch.harvested_at <= as_of,
                    )
                )
            )
            .scalars()
            .all()
        )
        stok_reasons: list[str] = []
        tersedia = Decimal("0")
        dipakai: list[str] = []
        freshness: list[Decimal] = []
        safety: set[str] = set()
        # Kesegaran WAJIB dinilai dengan profil komoditas (pita suhu + umur
        # simpan per komoditas), bukan `settings` global. Dulu beras (ambient)
        # dinilai terhadap 0-8 C dan ayam memakai jalur yang sama dengan ambang
        # pass 0,60 hardcoded, berbeda dari PASS_THRESHOLD 0,85 di
        # `core/freshness.py`. Akibatnya dua mesin memberi angka berbeda untuk
        # batch yang sama dan keputusan lahir `verifier_flagged` (28 Okt 2026).
        profil, _asal_profil = await profil_untuk_komoditas(db, komoditas.id)
        for b in batch_rows:
            if b.quarantine_status and b.quarantine_status != "none":
                stok_reasons.append(f"batch {str(b.id)[:8]} dikarantina")
                continue
            if b.dispatched_at is not None:
                # Stok yang sudah berangkat bukan stok yang bisa dibeli: batch
                # itu sudah di jalan/tiba di SPPG. Tanpa gerbang ini, kandidat
                # pengadaan bisa menunjuk batch yang berangkat 20 hari lalu dan
                # `POST /actions/execute` berakhir tanpa truk (terukur 28 Okt 2026).
                stok_reasons.append(f"batch {str(b.id)[:8]} sudah berangkat")
                continue
            # Batch `fail` tidak boleh jadi kandidat. `needs_verification`
            # TETAP boleh: kasus demo `*-coldchain-hold` justru dibangun dari
            # batch yang menunggu verifikasi, dan gerbang eksekusi
            # (`core/safety_gate.py`) yang menahan keputusannya — bukan pemilihan
            # kandidat. Menolak di sini membuat kasus itu tidak punya binding
            # sama sekali (terukur 28 Okt 2026: "safety gate memblokir karena
            # batch acuan tidak layak" pada wortel-coldchain-hold).
            if b.id in sudah_diterima:
                stok_reasons.append(f"batch {str(b.id)[:8]} sudah diterima")
                continue
            if b.safety_status == "fail":
                stok_reasons.append(
                    f"batch {str(b.id)[:8]} gagal uji keamanan"
                )
                continue
            segar = evaluate_freshness(
                harvested_at=b.harvested_at,
                as_of=as_of,
                policy=profil,
                temperature_log=b.temperature_log or [],
            )
            skor = segar.score
            status = segar.status
            # Hanya batch yang benar-benar `pass` yang boleh jadi kandidat,
            # sejalan dengan `core/safety_gate.py` (fail-closed). Sebelumnya
            # `needs_verification` ikut dipilih, lalu verifier menandai
            # keputusannya sendiri dan eksekusi berisiko 409.
            if status != "pass":
                stok_reasons.append(
                    f"batch {str(b.id)[:8]} kesegaran {status}"
                )
                continue
            tersedia += Decimal(str(b.quantity_kg))
            dipakai.append(str(b.id))
            freshness.append(_score(Decimal(str(skor))))
            safety.add(b.safety_status)

        quote_row = (
            await db.execute(
                select(PriceSignal)
                .where(
                    PriceSignal.location_id == target.id,
                    PriceSignal.commodity_id == komoditas.id,
                    PriceSignal.supplier_id == sup.id,
                    PriceSignal.source == "supplier_quote",
                    PriceSignal.recorded_at <= as_of,
                )
                .order_by(PriceSignal.recorded_at.desc(), PriceSignal.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        quote = _dec(quote_row.price_per_kg) if quote_row else None

        leg = supplier_leg_km(
            (sup.latitude, sup.longitude), (target.latitude, target.longitude)
        )
        reliability = Decimal(str(sup.reliability_score))
        freshness_score = min(freshness) if freshness else Decimal("0")
        # Ambang dari `core/freshness.py` (PASS 0,85 / VERIFY 0,60), bukan
        # literal 0,60: satu sumber ambang untuk kandidat, KPI, dan verifier.
        freshness_status = (
            classify_freshness(float(min(freshness))) if freshness else "fail"
        )
        safety_status = _worst_safety(safety) if safety else "pending"

        quantity = min(gap_kg, tersedia) if gap_kg > 0 else Decimal("0")
        alasan: list[str] = list(dict.fromkeys(stok_reasons))
        dikecualikan = sup.id in exclusions
        if dikecualikan:
            alasan.append(
                "dikecualikan di SPPG ini: "
                f"{exclusions[sup.id].reason or 'tanpa alasan tercatat'}"
            )
        if quote is None:
            alasan.append("penawaran harga untuk SPPG ini tidak tercatat")
        if tersedia <= 0:
            alasan.append("tidak ada stok batch yang bisa dikirim di SPPG ini")
        if gap_kg <= 0:
            alasan.append("SPPG ini tidak kekurangan komoditas tersebut")
        if leg is None:
            alasan.append("koordinat pemasok belum lengkap; jarak tidak dihitung")

        layak = not dikecualikan and quote is not None and tersedia > 0 and gap_kg > 0
        skor = None
        sdc_total = None
        breakdown: dict = {}
        if layak:
            hasil = calculate_candidate_score(
                CandidateScoreFactors(
                    demand_fit=quantity / gap_kg,
                    supply_availability=min(Decimal("1"), quantity / tersedia),
                    freshness_score=freshness_score,
                    safety_status=safety_status,
                    supplier_reliability=reliability,
                    logistics_feasible=leg is not None,
                )
            )
            skor = _score(hasil.score)
            layak = hasil.eligible
            if not layak:
                alasan.append("skor kandidat menandai perlu eliminasi keras")
            # Angkut PER TRIP (revisi 2026-10-29b): jalur pengadaan hanya punya
            # satu kaki (pemasok → SPPG), jadi jarak kaki itu = jarak total.
            if leg is not None:
                angkut, trip_info = biaya_angkut_trip(leg, quantity)
            else:
                # Jarak tidak diketahui → jangan mengarang tarif berangkat.
                angkut = Decimal("0.00")
                trip_info = {"basis": "jarak_tidak_diketahui", "trips": None}
            sdc = calculate_safe_delivered_cost(
                SafeDeliveredCostInputs(
                    purchase_cost=_money(quantity * Decimal(str(quote))),
                    transport_cost=angkut,
                    handling_cost=HANDLING_FLAT,
                    freshness_score=freshness_score,
                    safety_status=safety_status,
                    # Susut = fungsi waktu. Jalur pengadaan tidak membawa
                    # tanggal kebutuhan, jadi mesin memakai asumsi siklus
                    # harian dan basisnya ikut dilaporkan.
                    commodity=commodity,
                )
            )
            sdc_total = sdc.total
            breakdown = {
                "purchase": str(sdc.purchase_cost),
                "transport": str(sdc.transport_cost),
                "transport_supplier_leg": str(angkut),
                "transport_total_km": _str_or_none(leg),
                "transport_trips": trip_info["trips"],
                "transport_basis": trip_info["basis"],
                "supplier_leg_km": _str_or_none(leg),
                "handling": str(sdc.handling_cost),
                "expected_loss": str(sdc.expected_loss),
                # Jejak susut gudang (konsep Performance & Audit, 29 Okt 2026).
                "loss_in_storage": str(sdc.loss_in_storage),
                "storage_days": str(sdc.storage_days),
                "shelf_life_days": str(sdc.shelf_life_days),
                "storage_basis": sdc.storage_basis,
                "shrinkage_rate": str(sdc.shrinkage_rate),
                "shrinkage_rate_source": sdc.shrinkage_rate_source,
                "formula_version": sdc.formula_version,
                "freshness_risk": str(sdc.freshness_risk_penalty),
                "safety_penalty": str(sdc.safety_risk_penalty),
            }

        kandidat.append(
            SupplierCandidate(
                supplier_id=str(sup.id),
                supplier_name=sup.name,
                reliability=reliability,
                capacity_kg_per_week=_dec(sup.capacity_kg_per_week),
                quote_price=quote,
                reference_price=reference_price,
                available_kg=tersedia,
                quantity_kg=quantity,
                leg_km=leg,
                freshness_score=freshness_score,
                freshness_status=freshness_status,
                safety_status=safety_status,
                excluded=dikecualikan,
                exclusion_reason=(
                    exclusions[sup.id].reason if dikecualikan else None
                ),
                eligible=layak,
                reasons=tuple(alasan),
                score=skor,
                safe_delivered_cost=sdc_total,
                cost_breakdown=breakdown,
                batch_ids=tuple(sorted(dipakai)),
            )
        )

    layak_semua = [k for k in kandidat if k.eligible]
    layak_semua.sort(
        key=lambda k: (
            -(k.score or Decimal("0")),
            k.safe_delivered_cost or Decimal("0"),
            k.supplier_name,
        )
    )
    berperingkat = []
    for posisi, k in enumerate(layak_semua, start=1):
        baris = k.to_dict()
        baris["rank"] = posisi
        berperingkat.append(baris)

    return {
        "target_location": target.name,
        "commodity": commodity,
        "as_of": as_of.isoformat(),
        "supply_kg": _str_or_none(supply_kg),
        "demand_kg": _str_or_none(demand_kg),
        "gap_kg": str(gap_kg),
        "reference_price_per_kg": _str_or_none(reference_price),
        "suppliers_total": len(kandidat),
        "candidates": [k.to_dict() for k in kandidat],
        "ranked": berperingkat,
        "chosen": berperingkat[0] if berperingkat else None,
    }


async def persist_supplier_binding(
    db: AsyncSession,
    decision: Decision,
    *,
    supplier_id: str,
    batch_ids,
) -> None:
    """Bukti pengadaan: batch milik pemasok itu, di SPPG TUJUAN.

    Beda dari `persist_binding` (pemindahan): batch dicek terhadap
    `target_location_id`, karena barang datang KE SPPG ini dari pemasok yang
    memasoknya — bukan dari stok SPPG lain.
    """
    try:
        supplier_uuid = uuid.UUID(str(supplier_id))
        batch_uuid = [uuid.UUID(str(value)) for value in batch_ids]
    except ValueError as exc:
        raise HTTPException(422, "binding batch/supplier tidak valid") from exc
    if not batch_uuid:
        raise HTTPException(422, "binding batch wajib")
    batches = (
        (await db.execute(select(Batch).where(Batch.id.in_(batch_uuid))))
        .scalars()
        .all()
    )
    if len(batches) != len(set(batch_uuid)) or any(
        b.supplier_id != supplier_uuid
        or b.commodity_id != decision.commodity_id
        or b.location_id != decision.target_location_id
        for b in batches
    ):
        raise HTTPException(422, "binding batch/supplier tidak cocok")
    db.add(
        DecisionEvidence(
            decision_id=decision.id,
            evidence_type="human_inspection",
            payload={
                "allocation_binding": True,
                "procurement": True,
                "supplier_id": str(supplier_uuid),
                "target_location_id": str(decision.target_location_id),
                "batch_ids": sorted(str(value) for value in set(batch_uuid)),
            },
            is_consistent=True,
        )
    )
