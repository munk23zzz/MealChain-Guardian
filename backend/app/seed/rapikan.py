"""Rapikan batch yang pemasoknya salah komoditas.

Kenapa ada: beberapa penyemai (kanonik `load_seed`, `jakarta_lengkap`,
`demo_activity`) memilih pemasok dengan cara berbeda. Ketika pemilihan itu
mengabaikan `suppliers.commodity_id`, muncullah baris nyata seperti "batch
beras dipasok CV Barokah Telur Cianjur" — pemasok telur memasok beras. Itu
bukan sekadar tampilan jelek: profil pemasok, kutipan harga, dan baris
pengirim di kartu rekomendasi jadi menyesatkan.

Aturan perbaikan (deterministik, tanpa menghapus baris):
  * batch yang pemasoknya beda komoditas dipindah ke pemasok berkomoditas
    sama di kota batch itu;
  * bila pasangan (lokasi, komoditas) sudah punya pemasok di batch lain,
    pilih yang namanya paling awal — supaya satu pasangan tidak pecah jadi
    dua pemasok (`resolve_binding` menolak menyimpulkan pemasok kalau begitu).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, Supplier


async def rapikan_pemasok_batch(session: AsyncSession) -> int:
    """Perbaiki batch yang pemasoknya tidak menjual komoditas batch itu."""
    salah = (
        await session.execute(
            select(Batch.id, Batch.location_id, Batch.commodity_id)
            .join(Supplier, Supplier.id == Batch.supplier_id)
            .where(
                Supplier.commodity_id.is_not(None),
                Supplier.commodity_id != Batch.commodity_id,
            )
        )
    ).all()
    if not salah:
        return 0

    pemasok = list((await session.execute(select(Supplier))).scalars())
    # Pemasok yang sudah dipakai pasangan (dari batch LAIN yang benar) menang,
    # supaya perbaikan tidak menambah pemasok kedua ke pasangan tunggal.
    dipakai: dict[tuple, set] = {}
    for lok_id, com_id, sup_id, com_sup in (
        await session.execute(
            select(Batch.location_id, Batch.commodity_id, Batch.supplier_id, Supplier.commodity_id)
            .join(Supplier, Supplier.id == Batch.supplier_id)
            .where(Supplier.commodity_id == Batch.commodity_id)
        )
    ).all():
        dipakai.setdefault((lok_id, com_id), set()).add(sup_id)

    diperbaiki = 0
    for batch_id, lok_id, com_id in salah:
        kandidat = sorted(
            (p for p in pemasok if p.commodity_id == com_id),
            key=lambda p: (p.location_id != lok_id, p.name),
        )
        if not kandidat:
            continue
        sudah = dipakai.get((lok_id, com_id)) or set()
        pilih = next((p for p in kandidat if p.id in sudah), kandidat[0])
        batch = await session.get(Batch, batch_id)
        if batch is None:
            continue
        batch.supplier_id = pilih.id
        dipakai.setdefault((lok_id, com_id), set()).add(pilih.id)
        diperbaiki += 1

    if diperbaiki:
        await session.flush()
    return diperbaiki


async def rapikan_batch_ganda(session: AsyncSession) -> int:
    """Hapus batch kembar (pemasok, lokasi, komoditas, waktu panen sama).

    Beberapa penyemai menulis "kiriman pagi" dengan rumus waktu yang sama
    tetapi skema id berbeda (`demo_batch_id` vs `_id("b", …)` vs `batch:<n>`).
    Hasilnya dua baris untuk satu kiriman yang sama: peta menampilkan dua truk
    identik dan penerimaan bisa terhitung dua kali.

    Batch yang DIRUJUK bukti keputusan dipertahankan; kalau tidak ada yang
    dirujuk, yang paling baru dipertahankan. Baris kembar dihapus (penerimaan
    ikut terhapus lewat cascade).
    """
    from sqlalchemy import delete, text

    rujukan: set[str] = set()
    baris = (
        await session.execute(
            text(
                "SELECT jsonb_array_elements_text(payload->'batch_ids') AS b "
                "FROM decision_evidence WHERE payload ? 'batch_ids'"
            )
        )
    ).scalars().all()
    rujukan.update(str(b) for b in baris)

    kembar = (
        await session.execute(
            text(
                "SELECT id FROM ("
                "  SELECT id, row_number() OVER ("
                "    PARTITION BY supplier_id, location_id, commodity_id, harvested_at"
                "    ORDER BY (id::text = ANY(:rujuk)) DESC, created_at DESC"
                "  ) AS rn FROM batches"
                ") d WHERE rn > 1"
            ),
            {"rujuk": list(rujukan) or [""]},
        )
    ).scalars().all()
    if not kembar:
        return 0
    await session.execute(delete(Batch).where(Batch.id.in_(kembar)))
    await session.flush()
    return len(kembar)
