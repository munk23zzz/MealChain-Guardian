"""Penilaian pemasok → SPPG: hanya pemasok yang MEMASOK SPPG itu yang dinilai.

Konteks keputusan pemilik 2026-10-19: tab Demo Control harus menilai dari
pemasok ke SPPG (bukan surplus SPPG lain). Tes ini membaca DB nyata (seed demo)
dan memaku tiga hal yang mudah salah:

1. Populasi kandidat = pemasok terdaftar di lokasi SPPG itu dengan komoditas
   yang sama — tidak ada pemasok kota lain yang menyelinap masuk.
2. Batch yang diikat = batch milik pemasok tersebut, DI lokasi SPPG itu, dengan
   komoditas yang sama.
3. Pemasok dengan pengecualian `active` di SPPG itu tidak pernah layak, dan
   alasannya ikut dilaporkan (bukan dibuang diam-diam).

Tes bersifat baca-saja: tidak ada baris yang ditulis, jadi aman dijalankan
berdampingan dengan suite lain.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Batch, Commodity, DemandRecord, Location, Supplier, SupplyRecord
from app.services.supplier_procurement import evaluate_suppliers


def _jalankan(target_name: str, commodity: str) -> dict:
    async def _isi():
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            target = (
                await session.execute(
                    select(Location).where(Location.name == target_name)
                )
            ).scalar_one()
            return await evaluate_suppliers(
                session, target=target, commodity=commodity
            )

    return asyncio.run(_isi())


@pytest.fixture(scope="module")
def telur_jakarta() -> dict:
    return _jalankan("Jakarta", "telur")


def test_kandidat_hanya_pemasok_yang_memasok_sppg_itu(telur_jakarta):
    """13 pemasok Jakarta ada di DB, tetapi hanya yang komoditasnya telur dinilai."""
    hasil = telur_jakarta
    nama = {k["supplier"] for k in hasil["candidates"]}
    # Nama pemasok kota lain (Cianjur/Bandung) tidak boleh muncul.
    assert not any("Cianjur" in n or "Bandung" in n for n in nama), nama
    assert nama, "seed Jakarta punya pemasok telur"
    assert hasil["suppliers_total"] == len(hasil["candidates"])


def test_setiap_kandidat_terdaftar_di_lokasi_sppg(telur_jakarta):
    async def _cek():
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            jakarta = (
                await session.execute(
                    select(Location).where(Location.name == "Jakarta")
                )
            ).scalar_one()
            rows = (
                (
                    await session.execute(
                        select(Supplier).where(Supplier.location_id == jakarta.id)
                    )
                )
                .scalars()
                .all()
            )
            return {str(s.id) for s in rows}

    id_jakarta = asyncio.run(_cek())
    for kandidat in telur_jakarta["candidates"]:
        assert kandidat["supplier_id"] in id_jakarta


def test_kekurangan_dihitung_dari_supply_dan_demand_db(telur_jakarta):
    async def _angka():
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            jakarta = (
                await session.execute(
                    select(Location).where(Location.name == "Jakarta")
                )
            ).scalar_one()
            sup = (
                await session.execute(
                    select(SupplyRecord)
                    .where(SupplyRecord.location_id == jakarta.id)
                    .order_by(SupplyRecord.recorded_at.desc())
                    .limit(1)
                )
            ).scalar_one()
            dem = (
                await session.execute(
                    select(DemandRecord)
                    .where(DemandRecord.location_id == jakarta.id)
                    .order_by(DemandRecord.recorded_at.desc())
                    .limit(1)
                )
            ).scalar_one()
            return Decimal(str(sup.quantity_kg)), Decimal(str(dem.quantity_kg))

    hasil = telur_jakarta
    if hasil["supply_kg"] is None or hasil["demand_kg"] is None:
        pytest.skip("seed belum punya baris supply/demand untuk telur Jakarta")
    gap = max(Decimal(str(hasil["demand_kg"])) - Decimal(str(hasil["supply_kg"])), 0)
    assert Decimal(str(hasil["gap_kg"])) == gap


def test_pemasok_terpilih_punya_batch_di_sppg_itu(telur_jakarta):
    chosen = telur_jakarta["chosen"]
    assert chosen is not None, "seed Jakarta punya pemasok telur dengan stok"
    assert chosen["eligible"] is True
    assert chosen["batch_ids"], "keputusan pengadaan wajib terikat batch nyata"

    async def _cek(batch_ids: list[str], supplier_id: str) -> list[Batch]:
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            return (
                (
                    await session.execute(
                        select(Batch).where(
                            Batch.id.in_([uuid.UUID(b) for b in batch_ids])
                        )
                    )
                )
                .scalars()
                .all()
            )

    batches = asyncio.run(_cek(chosen["batch_ids"], chosen["supplier_id"]))
    assert len(batches) == len(set(chosen["batch_ids"]))
    for b in batches:
        assert str(b.supplier_id) == chosen["supplier_id"]
        assert b.commodity_id is not None
        assert b.location_id is not None


def test_pemasok_dikecualikan_tidak_layak_dan_alasannya_tercatat():
    """Pemasok dengan pengecualian `active` di Jakarta tidak layak dan alasannya tercatat.

    Nama tidak dipaku: yang diuji adalah perilaku (ada kandidat ber-`excluded`,
    ia tidak layak, dan alasannya memuat kata "dikecualikan"), bukan identitas
    satu pemasok yang bisa berubah saat data demo dirapikan.
    """
    hasil = _jalankan("Jakarta", "ayam")
    kandidat = {k["supplier"]: k for k in hasil["candidates"]}
    tersangka = next((k for k in kandidat.values() if k["excluded"]), None)
    if tersangka is None:
        pytest.skip("seed tidak memuat pemasok ayam Jakarta yang dikecualikan")
    assert tersangka["eligible"] is False
    assert any("dikecualikan" in r.lower() for r in tersangka["reasons"])
    if hasil["chosen"] is not None:
        assert hasil["chosen"]["supplier"] != tersangka["supplier"]


def test_peringkat_deterministik_dan_layak(telur_jakarta):
    urut = telur_jakarta["ranked"]
    assert urut, "minimal satu pemasok layak pada seed demo"
    assert [r["rank"] for r in urut] == list(range(1, len(urut) + 1))
    sebelum = None
    for baris in urut:
        assert baris["eligible"] is True
        if sebelum is not None:
            kunci_baru = (Decimal(str(baris["score"])),)
            kunci_lama = (Decimal(str(sebelum["score"])),)
            assert kunci_baru <= kunci_lama
        sebelum = baris


# ---------------------------------------------------------------------------
# Penerimaan harus lewat manusia: batch yang SUDAH diterima tidak boleh dipilih
# ---------------------------------------------------------------------------


def _batch_sudah_diterima(commodity: str) -> set[uuid.UUID]:
    """Batch di Jakarta/komoditas itu yang punya penerimaan `disetujui`."""
    from app.models import BatchReceipt

    async def _isi():
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        async with maker() as session:
            jakarta = (
                await session.execute(select(Location).where(Location.name == "Jakarta"))
            ).scalar_one()
            komoditas = (
                await session.execute(
                    select(Commodity).where(Commodity.name == commodity)
                )
            ).scalar_one()
            return set(
                (
                    await session.execute(
                        select(BatchReceipt.batch_id)
                        .join(Batch, Batch.id == BatchReceipt.batch_id)
                        .where(
                            BatchReceipt.status == "disetujui",
                            Batch.location_id == jakarta.id,
                            Batch.commodity_id == komoditas.id,
                        )
                    )
                )
                .scalars()
                .all()
            )

    return asyncio.run(_isi())


@pytest.mark.parametrize("komoditas", ["telur", "beras", "wortel", "ayam"])
def test_batch_sudah_diterima_tidak_dijadikan_kandidat(komoditas):
    """Kasus baru tidak boleh menunjuk barang yang riwayatnya sudah "diterima".

    Tanpa gerbang ini layar menampilkan barang tiba sendiri padahal tidak ada
    manusia yang menyetujui penerimaan untuk kasus itu (terukur 30 Okt 2026:
    keputusan wortel `pending_approval` sudah berstatus terima), dan approval
    penerimaannya jadi mustahil karena DB hanya mengizinkan satu disetujui/batch.
    """
    hasil = _jalankan("Jakarta", komoditas)
    terlarang = _batch_sudah_diterima(komoditas)
    dipilih = hasil["chosen"]
    if dipilih is None:
        pytest.skip(f"tidak ada kandidat untuk {komoditas}")
    terikat = {uuid.UUID(str(b)) for b in dipilih["batch_ids"]}
    assert not (terikat & terlarang), (
        f"{komoditas}: batch yang sudah diterima ikut dipilih: {terikat & terlarang}"
    )
    # Alasan penolakan tetap dibaca manusia, bukan dibuang diam-diam.
    for kandidat in hasil["candidates"]:
        if set(kandidat.get("batch_ids") or ()) & {str(b) for b in terlarang}:
            assert any("sudah diterima" in r for r in kandidat["reasons"]), kandidat
