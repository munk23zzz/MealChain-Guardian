"""Penulis data KPI dari aksi nyata (settlement demo).

Latar: tiga sumber KPI hanya diisi oleh seeder — `delivery_events`,
`price_signals`, dan `disposal_events`. Akibatnya kartu KPI tidak bergerak saat
operator menerima barang, saat keputusan dieksekusi, atau saat limbah dicatat;
angkanya hanya berubah kalau seed dijalankan ulang. Modul ini menutup celah itu
tanpa mengubah satu rumus KPI pun.

Aturan yang dipegang:

- **Tidak mengarang angka.** Porsi tersampaikan dihitung dari kg yang benar-benar
  diterima dibagi gram/porsi komoditas (`settings.menu_grams_*`), lalu dibatasi
  sisa rencana hari itu. Kalau gramasi komoditas belum diatur, penulisan
  dilewati dengan alasan yang bisa dibaca — bukan ditebak.
- **Idempoten.** Setiap baris membawa `source_ref` unik (`receipt:<uuid>`,
  `po:<nomor>`, `disposal:<kunci>`), jadi klik/retry kedua tidak menggandakan
  angka KPI.
- **Bisa dimatikan.** `settings.demo_kpi_writeback` (default aktif untuk demo)
  mematikan seluruh penulisan tanpa menyentuh pemanggilnya.

Semua fungsi menerima `AsyncSession` milik pemanggil dan TIDAK melakukan commit:
transaksi aksi (approve penerimaan / eksekusi keputusan) yang menentukan.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Batch,
    BatchReceipt,
    Commodity,
    DeliveryEvent,
    DisposalEvent,
    MenuPlan,
    PriceSignal,
)
from app.services.demo_session import sesi_sekarang

WIB = ZoneInfo("Asia/Jakarta")

#: Gram per porsi per komoditas. Nilainya dari config, bukan dari modul ini.
GRAM_PER_PORSI = {
    "telur": "menu_grams_telur",
    "ayam": "menu_grams_ayam",
    "wortel": "menu_grams_wortel",
    "beras": "menu_grams_beras",
}


def _aktif() -> bool:
    return bool(getattr(settings, "demo_kpi_writeback", True))


def _asal() -> str:
    """`demo` bila sesi demo berjalan, selain itu `seed` (pola tabel deret waktu)."""
    return "demo" if sesi_sekarang() is not None else "seed"


def _gram_per_porsi(nama_komoditas: str | None) -> float | None:
    atribut = GRAM_PER_PORSI.get((nama_komoditas or "").strip().lower())
    if atribut is None:
        return None
    nilai = getattr(settings, atribut, None)
    return float(nilai) if nilai else None


async def _sudah_ada(db: AsyncSession, model, ref: str) -> bool:
    hasil = await db.execute(select(model.id).where(model.source_ref == ref).limit(1))
    return hasil.scalar_one_or_none() is not None


async def catat_penerimaan(
    db: AsyncSession,
    *,
    batch: Batch,
    receipt: BatchReceipt,
    sekarang: datetime,
) -> dict:
    """Hitung PROYEKSI porsi dari bahan yang diterima — tanpa menulis fakta tersaji.

    Fase 8 (27 Okt 2026): fungsi ini dulu menulis `delivery_events` dengan
    `delivered_portions` hasil konversi kg ÷ gram. Itu salah secara konsep:
    bahan yang sampai di gudang bukan makanan yang tersaji ke penerima manfaat,
    dan `delivery_events` adalah catatan pengiriman yang dibuat petugas. Selama
    keduanya dicampur, kartu Meal Continuity menampilkan "porsi tersaji" yang
    sebenarnya hanya proyeksi dari berat terima.

    Kontrak sekarang: TIDAK ADA baris yang ditulis. Nilai kembali hanya
    proyeksi berlabel (`proyeksi_porsi`, `gram_per_porsi`) yang dipakai UI
    sebagai estimasi; metrik operasional tetap `no_data` sampai ada catatan
    kiriman yang sebenarnya.
    """
    if not _aktif():
        return {"ditulis": False, "alasan": "penulis KPI dimatikan (demo_kpi_writeback=false)"}

    komoditas = (
        await db.execute(select(Commodity).where(Commodity.id == batch.commodity_id))
    ).scalar_one_or_none()
    gram = _gram_per_porsi(komoditas.name if komoditas else None)
    if not gram:
        return {
            "ditulis": False,
            "alasan": (
                "gram per porsi komoditas ini belum diatur "
                f"({komoditas.name if komoditas else 'komoditas tidak dikenal'}) — "
                "porsi tidak ditebak"
            ),
        }

    plan_date: date = sekarang.astimezone(WIB).date()
    plan = (
        await db.execute(
            select(MenuPlan)
            .where(MenuPlan.location_id == batch.location_id, MenuPlan.plan_date == plan_date)
            .limit(1)
        )
    ).scalar_one_or_none()
    if plan is None:
        return {
            "ditulis": False,
            "alasan": f"tidak ada rencana menu {plan_date.isoformat()} untuk lokasi batch",
        }

    terkirim = (
        await db.execute(
            select(func.coalesce(func.sum(DeliveryEvent.delivered_portions), 0)).where(
                DeliveryEvent.menu_plan_id == plan.id
            )
        )
    ).scalar_one()
    sisa = int(plan.planned_portions or 0) - int(terkirim or 0)

    porsi = int(Decimal(str(batch.quantity_kg)) * 1000 / Decimal(str(gram)))
    porsi_proyeksi = max(0, min(porsi, sisa)) if sisa > 0 else 0
    return {
        "ditulis": False,
        "alasan": (
            "penerimaan bahan hanya menghasilkan proyeksi porsi — bukan porsi "
            "tersaji; tidak ada fakta pengiriman yang ditulis"
        ),
        "proyeksi_porsi": porsi_proyeksi,
        "porsi_dari_berat": porsi,
        "menu_plan_id": str(plan.id),
        "gram_per_porsi": gram,
        "sisa_rencana": max(0, sisa),
    }


async def catat_po_terbit(
    db: AsyncSession,
    *,
    decision,
    po_number: str,
    supplier_id: uuid.UUID,
    harga_per_kg: Decimal,
    sekarang: datetime,
) -> dict:
    """Tulis `price_signals` (supplier_quote) saat PO benar-benar terbit.

    Harga yang dipakai adalah harga PO apa adanya; pembandingnya (acuan PIHPS)
    sudah ada di tabel yang sama, jadi metrik deviasi bisa memasangkan keduanya.
    """
    if not _aktif():
        return {"ditulis": False, "alasan": "penulis KPI dimatikan (demo_kpi_writeback=false)"}

    ref = f"po:{po_number}"
    if await _sudah_ada(db, PriceSignal, ref):
        return {"ditulis": False, "alasan": "sudah tercatat", "source_ref": ref}

    if Decimal(str(harga_per_kg)) <= 0:
        return {"ditulis": False, "alasan": "harga per kg tidak valid"}

    db.add(
        PriceSignal(
            location_id=decision.target_location_id,
            commodity_id=decision.commodity_id,
            supplier_id=supplier_id,
            price_per_kg=Decimal(str(harga_per_kg)).quantize(Decimal("0.01")),
            source="supplier_quote",
            origin=_asal(),
            # Fase 2 MG: fakta mewarisi sesi dari KEPUTUSAN INDUKNYA. Memakai
            # `sesi_sekarang()` (sesi aktif) berarti menstempel fakta dengan
            # sesi yang kebetulan sedang berjalan — begitu ada dua sesi, angka
            # satu sesi masuk ke sesi lain dan reset per sesi salah sasaran.
            demo_session_id=decision.demo_session_id,
            generated_at=sekarang,
            recorded_at=sekarang,
            source_ref=ref,
        )
    )
    return {"ditulis": True, "source_ref": ref, "harga_per_kg": str(harga_per_kg)}


async def catat_pembuangan(
    db: AsyncSession,
    *,
    location_id: uuid.UUID,
    commodity_id: uuid.UUID,
    quantity_kg: Decimal,
    reason: str,
    partner_name: str | None,
    sekarang: datetime,
    kunci: str | None = None,
) -> dict:
    """Catat satu kejadian limbah — satu-satunya jalan agar food loss bergerak.

    `kunci` membuat penulisan idempoten (mis. id keputusan atau UUID aksi);
    tanpa kunci, dipakai UUID acak sehingga dua permintaan = dua kejadian nyata.
    """
    if not _aktif():
        return {"ditulis": False, "alasan": "penulis KPI dimatikan (demo_kpi_writeback=false)"}

    ref = f"disposal:{kunci or uuid.uuid4()}"
    if await _sudah_ada(db, DisposalEvent, ref):
        return {"ditulis": False, "alasan": "sudah tercatat", "source_ref": ref}

    jumlah = Decimal(str(quantity_kg))
    if jumlah <= 0:
        return {"ditulis": False, "alasan": "jumlah kg harus lebih dari nol"}

    db.add(
        DisposalEvent(
            location_id=location_id,
            commodity_id=commodity_id,
            quantity_kg=jumlah,
            reason=(reason or "").strip() or "tidak disebutkan",
            partner_name=(partner_name or "").strip() or None,
            origin=_asal(),
            generated_at=sekarang,
            disposed_at=sekarang,
            source_ref=ref,
        )
    )
    return {"ditulis": True, "source_ref": ref, "quantity_kg": str(jumlah)}


async def bersihkan_kutipan_tanpa_po(db: AsyncSession) -> int:
    """Hapus kutipan `po:<nomor>` yang PO-nya sudah tidak ada.

    Kutipan yang lahir dari PO (`source_ref='po:<nomor>'`) hanya bermakna selama
    PO-nya ada. Tes integrasi membuat PO lalu menghapusnya lagi di pembersihan,
    dan `reset-demo` menghapus PO demo — dalam kedua kasus kutipannya akan
    tertinggal dan menggeser metrik Price Deviation dengan angka yang tidak
    bisa ditelusuri ke dokumen mana pun. Dipanggil di awal `reset-demo`.
    """
    hasil = await db.execute(
        text(
            "DELETE FROM price_signals ps "
            "WHERE ps.source_ref LIKE 'po:%' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM sap_mock_purchase_orders po "
            "  WHERE 'po:' || po.po_number = ps.source_ref)"
        )
    )
    return int(hasil.rowcount or 0)
