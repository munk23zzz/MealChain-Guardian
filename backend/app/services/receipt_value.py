"""Nilai rupiah penerimaan barang (Fase 5 butir 4b).

Definisi: `accepted_value_idr` = kg yang DITERIMA × `sap_mock_purchase_orders.price`
untuk PO yang mendanai batch itu. Sejak Fase 5 `price` adalah harga satuan
INVOICE (bahan + transportasi + penanganan), jadi angka inilah yang boleh masuk
pembukuan; penalti risiko internal tetap tinggal di `safe_delivered_cost` dan
tidak pernah ditagihkan.

Jalur atribusi batch → PO cuma satu, dan otoritatif: `persist_supplier_binding`
menulis bukti `allocation_binding` berisi `batch_ids`. Batch yang tidak muncul
di bukti itu menghasilkan `None` ("tidak tercatat") — bukan 0, bukan harga
pasar, dan bukan tebakan dari pasangan (pemasok, komoditas, lokasi). Alasannya
terukur: 110 dari 120 batch demo tidak punya ikatan, sehingga menebak akan
mengarang nilai untuk hampir seluruh baris.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decisions import Decision, DecisionEvidence
from app.models.sap_mock import SapMockPurchaseOrder

_SEN = Decimal("0.01")


async def po_dan_harga(
    db: AsyncSession, batch_id: uuid.UUID
) -> tuple[str | None, Decimal | None]:
    """Nomor PO + harga satuan invoice yang mendanai `batch_id`.

    Dipisah dari `harga_invoice_po` supaya layar penerimaan bisa MENJELASKAN
    asal nilai ("130 kg × Rp 26.200 per kg dari PO …") tanpa membagi nilai
    dengan jumlah kg di peramban. Aturan atribusinya sama persis — satu jalur,
    bukti `human_inspection` terbaru — jadi harga yang tampil tidak bisa
    berbeda dari harga yang dipakai menghitung nilai.
    """
    baris = (
        await db.execute(
            select(SapMockPurchaseOrder.po_number, SapMockPurchaseOrder.price)
            .join(Decision, Decision.id == SapMockPurchaseOrder.decision_id)
            .join(DecisionEvidence, DecisionEvidence.decision_id == Decision.id)
            .where(
                DecisionEvidence.evidence_type == "human_inspection",
                func.jsonb_exists(
                    DecisionEvidence.payload["batch_ids"], str(batch_id)
                ),
            )
            .order_by(Decision.created_at.desc(), SapMockPurchaseOrder.created_at.desc())
            .limit(1)
        )
    ).first()
    if baris is None:
        return None, None
    return baris[0], baris[1]


async def harga_invoice_po(db: AsyncSession, batch_id: uuid.UUID) -> Decimal | None:
    """Harga satuan invoice PO yang mendanai `batch_id`, atau None.

    Bila satu batch muncul di beberapa bukti (keputusan lama dan penggantinya),
    yang dipakai bukti TERBARU — itu alokasi yang masih berlaku.
    """
    _nomor, harga = await po_dan_harga(db, batch_id)
    return harga


def nilai_dari(kg: float | None, harga: Decimal | None) -> float | None:
    """Nilai rupiah dari kg × harga satuan — satu tempat, tanpa duplikasi."""
    if kg is None or harga is None:
        return None
    return float((Decimal(str(kg)) * Decimal(harga)).quantize(_SEN, rounding=ROUND_HALF_UP))


async def nilai_diterima(
    db: AsyncSession, batch_id: uuid.UUID, kg: float | None
) -> float | None:
    """Nilai rupiah barang yang diterima, dibulatkan ke sen."""
    if kg is None:
        return None
    return nilai_dari(kg, await harga_invoice_po(db, batch_id))
