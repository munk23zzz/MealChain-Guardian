"""Bahan belajar agent dari data yang DITOLAK (permintaan pemilik 29 Okt 2026).

Kenapa modul sendiri: dua jalur LEARN butuh bahan yang sama —
`POST /actions/repropose` (rejection loop) dan langkah LEARN di
`event1_orchestrator` — dan keduanya tidak boleh menebak alasan penolakan.
Satu fungsi membaca, dua pemakai; tidak ada angka yang dikarang di sini.

Isi yang dikembalikan hanya FAKTA tercatat: tipe keputusan, komoditas, alasan
penolakan manusia, dan kapan ditolak. Penerimaan yang ditolak ikut dibaca
karena penolakan saat serah terima (Dok 05 §5, Dok 08) juga alasan nyata yang
bukan hiasan: "kemasan bocor", "suhu di atas batas".
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, BatchReceipt, Commodity, Decision, Location


async def riwayat_penolakan(
    db: AsyncSession,
    *,
    target_location_id: uuid.UUID | None = None,
    commodity_id: uuid.UUID | None = None,
    limit: int = 5,
    kecuali_decision_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Penolakan terakhir yang relevan untuk satu kota/komoditas.

    `kecuali_decision_id` dipakai saat keputusan yang sedang diproses memang
    keputusan yang ditolak itu sendiri (repropose): ia tidak boleh muncul
    sebagai "pelajaran sebelumnya".
    """
    komoditas: dict = {}
    for cid, nama in (await db.execute(select(Commodity.id, Commodity.name))).all():
        komoditas[cid] = nama
    lokasi: dict = {}
    for lid, nama in (await db.execute(select(Location.id, Location.name))).all():
        lokasi[lid] = nama

    stmt = select(Decision).where(Decision.status == "rejected")
    if target_location_id is not None:
        stmt = stmt.where(Decision.target_location_id == target_location_id)
    if commodity_id is not None:
        stmt = stmt.where(Decision.commodity_id == commodity_id)
    if kecuali_decision_id is not None:
        stmt = stmt.where(Decision.id != kecuali_decision_id)
    stmt = stmt.order_by(Decision.created_at.desc(), Decision.id.desc()).limit(limit)

    keputusan = [
        {
            "decision_id": str(row.id),
            "decision_type": row.decision_type,
            "komoditas": komoditas.get(row.commodity_id),
            "lokasi_tujuan": lokasi.get(row.target_location_id),
            "alasan": row.rejection_reason,
            "iteration": row.iteration or 1,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in (await db.scalars(stmt)).all()
    ]

    stmt_p = (
        select(BatchReceipt, Batch)
        .join(Batch, Batch.id == BatchReceipt.batch_id)
        .where(BatchReceipt.status == "ditolak")
    )
    if target_location_id is not None:
        stmt_p = stmt_p.where(Batch.location_id == target_location_id)
    if commodity_id is not None:
        stmt_p = stmt_p.where(Batch.commodity_id == commodity_id)
    stmt_p = stmt_p.order_by(BatchReceipt.reviewed_at.desc().nullslast()).limit(limit)

    penerimaan = [
        {
            "receipt_id": str(catatan.id),
            "komoditas": komoditas.get(batch.commodity_id),
            "lokasi": lokasi.get(batch.location_id),
            "alasan": catatan.review_note,
            "ordered_kg": float(catatan.ordered_kg) if catatan.ordered_kg is not None else None,
            "reviewed_at": catatan.reviewed_at.isoformat() if catatan.reviewed_at else None,
        }
        for catatan, batch in (await db.execute(stmt_p)).all()
    ]

    return {
        "jumlah": {"keputusan": len(keputusan), "penerimaan": len(penerimaan)},
        "keputusan": keputusan,
        "penerimaan": penerimaan,
        "sumber": ["decisions(status='rejected')", "batch_receipts(status='ditolak')"],
    }
