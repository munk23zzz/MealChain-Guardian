"""Kasus demo PENGADAAN harus membawa binding yang bisa dieksekusi.

Konteks (audit 27 Okt 2026): `_ikat_sumber` memilih batch di lokasi ASAL untuk
SEMUA jenis keputusan, padahal penulis produksi pengadaan
(`persist_supplier_binding`) memilih batch di SPPG TUJUAN milik
`decisions.supplier_id`. Akibatnya empat keputusan `rejection-loop-kuota`
(pending_approval, pengadaan Cianjur→Jakarta dkk.) membawa binding transfer:
pemasok di binding berbeda dari pemasok di kolom keputusan.

Sebelum guard diperbaiki, eksekusi keputusan itu menghasilkan PO ke pemasok
yang BERBEDA dari yang tampil di layar. Sesudah guard memakai lokasi acuan
`target_location_id`, binding yang salah itu ditolak
`409 binding batch/supplier berubah` — jadi kasus demo unggulan tidak bisa
diekskusi sama sekali sampai penyemainya ikut benar.

Berkas ini mengunci kontraknya: setiap keputusan pengadaan hasil penyemai demo
punya binding yang (a) menunjuk batch di lokasi TUJUAN, (b) milik pemasok
keputusan, dan (c) lolos `resolve_binding` + safety gate tanpa blokir.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.models import Batch, Decision, Location


def _jalankan(fn):
    async def _bungkus():
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(_bungkus())


def _semai_kasus() -> None:
    from app.api.demo import _seed_demo_cases

    async def _isi(db) -> None:
        # Kasus demo adalah per-KOTA (`force=True` hanya mengganti kasus kota
        # yang diminta), jadi fixture harus menyemai SEMUA kota demo. Dulu di
        # sini hanya Jakarta; keputusan Bandung/Surabaya yang tersisa dari
        # penyemaian lama tetap memakai binding versi lama dan membuat tes
        # gagal karena data usang, bukan karena penyemainya salah.
        kota = (
            await db.execute(
                select(Location).where(
                    Location.name.in_(["Jakarta", "Bandung", "Surabaya", "Medan"])
                )
            )
        ).scalars().all()
        for loc in kota:
            await _seed_demo_cases(db, True, loc)
        await db.commit()

    _jalankan(_isi)


def _kasus_pengadaan() -> list[dict]:
    """Keputusan pengadaan demo yang masih bisa ditindaklanjuti."""

    async def _ambil(db):
        from app.models import DecisionEvidence

        rows = (
            await db.execute(
                select(Decision).where(
                    Decision.decision_type == "supplier_procurement",
                    Decision.demo_case.is_not(None),
                    Decision.status.in_(["proposed", "pending_approval", "approved"]),
                )
            )
        ).scalars().all()
        hasil = []
        for d in rows:
            bukti = (
                await db.execute(
                    select(DecisionEvidence).where(
                        DecisionEvidence.decision_id == d.id,
                        DecisionEvidence.payload["allocation_binding"].astext == "true",
                    )
                )
            ).scalars().all()
            batches = (
                await db.execute(select(Batch).where(Batch.id.in_(
                    [b for e in bukti for b in _ids(e.payload)]
                )))
            ).scalars().all() if bukti else []
            hasil.append(
                {
                    "id": d.id,
                    "status": d.status,
                    "demo_case": d.demo_case,
                    "target": d.target_location_id,
                    "supplier": d.supplier_id,
                    "binding_supplier": (
                        str(bukti[0].payload.get("supplier_id")) if bukti else None
                    ),
                    "batches": [(b.id, b.location_id, b.supplier_id) for b in batches],
                }
            )
        return hasil

    return _jalankan(_ambil)


def _ids(payload: dict):
    import uuid as _u

    return [_u.UUID(str(v)) for v in payload.get("batch_ids", [])]


def _resolve(decision_id: uuid.UUID, supplier_id):
    """`resolve_binding` + `batch_sumber_transfer` nyata untuk satu keputusan."""

    async def _cek(db):
        from app.services.supplier_eligibility import (
            batch_sumber_transfer,
            resolve_binding,
            source_batch_safety_blocked,
        )

        d = await db.get(Decision, decision_id)
        supplier, batches = await resolve_binding(db, d)
        return {
            "supplier": supplier,
            "batches": [(b.id, b.location_id, b.supplier_id) for b in batches],
            "blocked": source_batch_safety_blocked(await batch_sumber_transfer(db, d)),
        }

    return _jalankan(_cek)


@pytest.fixture(scope="module")
def kasus() -> list[dict]:
    _semai_kasus()
    rows = _kasus_pengadaan()
    assert rows, "penyemai demo tidak menghasilkan keputusan pengadaan yang tertunda"
    return rows


def test_binding_pengadaan_menunjuk_batch_di_sppg_tujuan(kasus):
    """Batch acuan harus di lokasi TUJUAN, bukan lokasi asal (semantik pengadaan)."""
    for k in kasus:
        assert k["batches"], (
            f"{k['demo_case']} {str(k['id'])[:8]}: pengadaan tanpa binding batch — "
            "layar akan menampilkan 'pemasok tidak dikenal'"
        )
        for _bid, lokasi, _sup in k["batches"]:
            assert lokasi == k["target"], (
                f"{k['demo_case']} {str(k['id'])[:8]}: batch binding ada di lokasi "
                f"{lokasi}, bukan SPPG tujuan {k['target']}"
            )


def test_binding_pengadaan_memakai_pemasok_keputusan(kasus):
    """Pemasok di binding = `decisions.supplier_id`, jadi PO = pemasok di layar."""
    for k in kasus:
        assert k["binding_supplier"] == str(k["supplier"]), (
            f"{k['demo_case']} {str(k['id'])[:8]}: binding menunjuk pemasok "
            f"{k['binding_supplier']}, kolom keputusan {k['supplier']}"
        )


def test_kasus_pengadaan_lolos_resolve_binding_dan_safety(kasus):
    """Tidak boleh ada kasus demo pengadaan yang pasti ditolak guard eksekusi."""
    for k in kasus:
        try:
            hasil = _resolve(k["id"], k["supplier"])
        except HTTPException as exc:  # pragma: no cover - pesan kegagalan
            raise AssertionError(
                f"{k['demo_case']} {str(k['id'])[:8]} ditolak guard: "
                f"{exc.status_code} {exc.detail}"
            ) from exc
        assert hasil["batches"], f"{str(k['id'])[:8]}: resolve tanpa batch"
        assert hasil["blocked"] is False, (
            f"{k['demo_case']} {str(k['id'])[:8]}: safety gate memblokir karena "
            "batch acuan tidak layak — kasus demo tidak bisa dieksekusi"
        )
