"""Anchor ledger di luar database (Fase 11 MG, butir 2).

Kontrak yang dikunci:

1. Tanpa checkpoint, laporan WAJIB menyatakan "belum ada anchor"
   (`anchor.match = null`), bukan "cocok".
2. Dengan checkpoint yang dibuat dari keadaan sekarang, `anchor.match = true`.
3. Riwayat yang DITULIS ULANG rapi — hash dihitung ulang dari blok yang diubah
   sampai kepala, sehingga `verify_chain` tetap `valid = true` — tetap
   terdeteksi lewat `anchor.match = false`. Inilah bukti bahwa `valid=true` dari
   database yang sama BUKAN bukti tidak dapat diubah.
4. Checkpoint yang menunjuk tinggi melebihi rantai (riwayat dipangkas / DB
   dipulihkan dari salinan lebih lama) juga dilaporkan sebagai tidak cocok.

Semua mutasi dijalankan di dalam satu transaksi yang di-rollback, jadi tes tidak
meninggalkan perubahan pada ledger klon.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.ledger_service import tulis_checkpoint, verify_chain
from tests.dsn import DSN_ASYNC
from tests.ledger_pemeliharaan import buka_pintu_async


def _jalankan(fn):
    async def _main():
        engine = create_async_engine(DSN_ASYNC, pool_pre_ping=True)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await engine.dispose()

    return asyncio.run(_main())


def _berkas_sementara() -> Path:
    direktori = tempfile.mkdtemp(prefix="anchor-f11-")
    return Path(direktori) / "ledger-checkpoint.json"


def test_tanpa_checkpoint_dilaporkan_belum_ada():
    jalur = str(_berkas_sementara())  # sengaja tidak dibuat

    async def _t(db):
        return await verify_chain(db, anchor_path=jalur)

    hasil = _jalankan(_t)
    anchor = hasil["anchor"]
    assert anchor["configured"] is True, anchor
    assert anchor["match"] is None, anchor
    assert "belum dibuat" in (anchor["reason"] or ""), anchor
    # Integritas rantai tetap dilaporkan apa adanya.
    assert hasil["valid"] is True, hasil


def test_path_kosong_berarti_anchor_dimatikan():
    async def _t(db):
        return await verify_chain(db, anchor_path="")

    hasil = _jalankan(_t)
    anchor = hasil["anchor"]
    assert anchor["configured"] is False, anchor
    assert anchor["match"] is None, anchor
    assert "dimatikan" in (anchor["reason"] or ""), anchor


def test_checkpoint_cocok_dengan_rantai():
    jalur = str(_berkas_sementara())

    async def _t(db):
        data = await tulis_checkpoint(db, jalur)
        laporan = await verify_chain(db, anchor_path=jalur)
        return data, laporan

    data, laporan = _jalankan(_t)
    assert Path(jalur).exists()

    # Berkas memuat kepala rantai yang SEBENARNYA, bukan angka karangan.
    assert data["height"] > 0
    assert data["blocks"] >= data["height"]
    assert laporan["anchor"]["configured"] is True, laporan
    assert laporan["anchor"]["match"] is True, laporan
    assert laporan["anchor"]["height"] == data["height"]
    assert laporan["anchor"]["payload_hash"] == laporan["head"]


def test_riwayat_ditulis_ulang_tetap_terdeteksi():
    """Hash dihitung ulang rapi sampai kepala: `valid` tetap true, anchor tidak."""
    jalur = str(_berkas_sementara())

    async def _t(db):
        await tulis_checkpoint(db, jalur)
        kepala, puncak = await _kepala(db)
        target = max(1, puncak // 2)

        await buka_pintu_async(db)
        baris = (
            await db.execute(
                text(
                    "SELECT height, prev_hash, payload FROM ledger_blocks "
                    "WHERE height >= :t ORDER BY height"
                ),
                {"t": target},
            )
        ).fetchall()
        assert baris, "ledger klon kosong — tidak ada blok untuk diuji"

        prev = None
        for tinggi, prev_hash, payload in baris:
            if prev is None:
                prev = prev_hash
                # Blok target diubah, blok sesudahnya hanya di-hash ulang.
                isi = payload + " " if tinggi == target else payload
            else:
                isi = payload
            baru = hashlib.sha256((prev + isi).encode()).hexdigest()
            # Penulisan ulang yang rapi harus menyambung: `prev_hash` blok
            # sesudahnya ikut diperbarui, kalau tidak rantainya justru putus.
            await db.execute(
                text(
                    "UPDATE ledger_blocks SET prev_hash = :p, payload = :pl, "
                    "payload_hash = :ph WHERE height = :h"
                ),
                {"p": prev, "pl": isi, "ph": baru, "h": tinggi},
            )
            prev = baru

        # Tanpa anchor, manipulasi ini LOLOS: hash-nya konsisten.
        utuh = await verify_chain(db, anchor_path="")
        assert utuh["valid"] is True, utuh

        # Dengan anchor, manipulasi tertangkap.
        dengan_anchor = await verify_chain(db, anchor_path=jalur)
        assert dengan_anchor["valid"] is True, dengan_anchor
        assert dengan_anchor["anchor"]["match"] is False, dengan_anchor
        assert "ditulis ulang" in (dengan_anchor["anchor"]["reason"] or ""), dengan_anchor
        await db.rollback()
        return puncak, kepala, target

    puncak, kepala, target = _jalankan(_t)

    # Rollback mengembalikan rantai: kepala sama seperti sebelum manipulasi.
    async def _cek(db):
        return await _kepala(db)

    kepala_sesudah, puncak_sesudah = _jalankan(_cek)
    assert (puncak_sesudah, kepala_sesudah) == (puncak, kepala)
    assert target <= puncak


def test_checkpoint_lebih_tinggi_dari_rantai_tidak_cocok():
    jalur = _berkas_sementara()

    async def _t(db):
        puncak = int(
            (await db.execute(text("SELECT max(height) FROM ledger_blocks"))).scalar_one()
        )
        jalur.write_text(
            json.dumps(
                {
                    "height": puncak + 10,
                    "payload_hash": "a" * 64,
                    "created_at": "2026-10-27T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        return await verify_chain(db, anchor_path=str(jalur))

    hasil = _jalankan(_t)
    assert hasil["anchor"]["match"] is False, hasil
    assert "tidak ada di database" in (hasil["anchor"]["reason"] or ""), hasil


async def _kepala(db) -> tuple[str, int]:
    baris = (
        await db.execute(
            text(
                "SELECT height, payload_hash FROM ledger_blocks "
                "ORDER BY height DESC LIMIT 1"
            )
        )
    ).fetchone()
    if baris is None:
        pytest.fail("ledger klon kosong")
    return str(baris[1]), int(baris[0])
