"""`persist_binding` harus memakai lokasi acuan yang sama dengan guard eksekusi.

Temuan gate fullstack 27 Okt 2026 (spec `verify/decision-evidence-write.spec.json`):
`POST /decisions` TIDAK bisa menulis binding pengadaan — hasil ukur
`candidate{batch_ids,supplier_id}` → `422 binding batch/supplier tidak cocok`,
karena `persist_binding` membandingkan `batch.location_id` dengan
`decision.source_location_id` (NULL untuk pengadaan) alih-alih lokasi TUJUAN.

Akibatnya satu-satunya jalan membuat pengadaan yang bisa dieksekusi adalah
orkestrator demo; jalur API biasa selalu gagal di 422 sebelum keputusan lahir.

Berkas ini mengunci: pengadaan divalidasi terhadap SPPG tujuan, pemasok binding
harus sama dengan pemasok keputusan (kalau tidak, PO bisa ke pihak yang berbeda
dari yang tampil di layar), dan jalur pemindahan tidak berubah.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import HTTPException
from sqlalchemy import select, text

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.models import Decision, DecisionEvidence

PW = "TestPass#2026"


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


def _batch_pemasok_di_sppg() -> dict:
    async def _ambil(db):
        row = (
            await db.execute(
                text(
                    "SELECT b.id, b.supplier_id, b.location_id, b.commodity_id "
                    "FROM batches b JOIN suppliers s ON s.id = b.supplier_id "
                    "WHERE b.location_id = s.location_id AND b.safety_status = 'pass' "
                    "ORDER BY b.created_at DESC LIMIT 1"
                )
            )
        ).first()
        assert row, "butuh batch pemasok-di-SPPG untuk fixture"
        return {
            "batch_id": row[0],
            "supplier_id": row[1],
            "location_id": row[2],
            "commodity_id": row[3],
        }

    return _jalankan(_ambil)


def _buat_keputusan(
    *, jenis: str, source, target, commodity, supplier=None
) -> uuid.UUID:
    async def _buat(db):
        did = uuid.uuid4()
        await db.execute(
            text(
                "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                "source_location_id, target_location_id, commodity_id, quantity_kg, "
                "safe_delivered_cost, expires_at, cost_breakdown, iteration, "
                "supplier_id) VALUES (:id, :jenis, 'proposed', 'supervisor_agent', "
                ":src, :tgt, :kom, 120, 3000000, now() + interval '45 minutes', "
                "'{}'::jsonb, 1, :sup)"
            ),
            {
                "id": did,
                "jenis": jenis,
                "src": source,
                "tgt": target,
                "kom": commodity,
                "sup": supplier,
            },
        )
        await db.commit()
        return did

    return _jalankan(_buat)


def _persist(decision_id: uuid.UUID, candidate: dict):
    async def _isi(db):
        from app.services.supplier_eligibility import persist_binding

        d = await db.get(Decision, decision_id)
        try:
            await persist_binding(db, d, candidate)
            await db.commit()
        except HTTPException as exc:
            await db.rollback()
            return {"status": exc.status_code, "detail": exc.detail}

        async def _bukti():
            rows = (
                await db.execute(
                    select(DecisionEvidence).where(
                        DecisionEvidence.decision_id == decision_id,
                        DecisionEvidence.payload["allocation_binding"].astext == "true",
                    )
                )
            ).scalars().all()
            return [
                {"payload": e.payload, "is_consistent": e.is_consistent} for e in rows
            ]

        return {"status": 200, "bukti": await _bukti()}

    return _jalankan(_isi)


def _hapus(decision_id: uuid.UUID) -> None:
    async def _del(db):
        await db.execute(
            text("DELETE FROM decision_evidence WHERE decision_id = :d"), {"d": decision_id}
        )
        await db.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": decision_id})
        await db.commit()

    _jalankan(_del)


def test_pengadaan_binding_ditulis_terhadap_sppg_tujuan():
    """Batch milik pemasok keputusan, di lokasi TUJUAN → binding konsisten."""
    b = _batch_pemasok_di_sppg()
    did = _buat_keputusan(
        jenis="supplier_procurement",
        source=None,
        target=b["location_id"],
        commodity=b["commodity_id"],
        supplier=b["supplier_id"],
    )
    try:
        hasil = _persist(
            did, {"batch_ids": [str(b["batch_id"])], "supplier_id": str(b["supplier_id"])}
        )
        assert hasil["status"] == 200, hasil
        assert hasil["bukti"], "binding tidak tertulis"
        bukti = hasil["bukti"][0]
        assert bukti["is_consistent"] is True
        assert bukti["payload"]["supplier_id"] == str(b["supplier_id"])
        assert bukti["payload"]["batch_ids"] == [str(b["batch_id"])]
    finally:
        _hapus(did)


def test_pengadaan_binding_pemasok_berbeda_ditolak():
    """Binding tidak boleh menunjuk pemasok lain daripada pemasok keputusan."""
    b = _batch_pemasok_di_sppg()

    async def _pemasok_lain(db):
        row = (
            await db.execute(
                text("SELECT id FROM suppliers WHERE id <> :s LIMIT 1"),
                {"s": b["supplier_id"]},
            )
        ).first()
        return row[0]

    lain = _jalankan(_pemasok_lain)
    did = _buat_keputusan(
        jenis="supplier_procurement",
        source=None,
        target=b["location_id"],
        commodity=b["commodity_id"],
        supplier=b["supplier_id"],
    )
    try:
        hasil = _persist(
            did, {"batch_ids": [str(b["batch_id"])], "supplier_id": str(lain)}
        )
        assert hasil["status"] == 422, hasil
        assert "binding supplier tidak sama dengan pemasok keputusan" in hasil["detail"]
        assert _persist_ulang_tanpa_bukti(did)
    finally:
        _hapus(did)


def _persist_ulang_tanpa_bukti(decision_id: uuid.UUID) -> bool:
    """Penolakan tidak boleh menyisakan baris bukti setengah jadi."""

    async def _cek(db):
        rows = (
            await db.execute(
                select(DecisionEvidence).where(
                    DecisionEvidence.decision_id == decision_id,
                    DecisionEvidence.payload["allocation_binding"].astext == "true",
                )
            )
        ).scalars().all()
        return len(rows) == 0

    return _jalankan(_cek)


def test_pemindahan_tetap_divalidasi_terhadap_lokasi_sumber():
    """Regresi: jalur transfer (non-pengadaan) tidak boleh ikut berubah."""
    b = _batch_pemasok_di_sppg()

    async def _lokasi_lain(db):
        row = (
            await db.execute(
                text(
                    "SELECT l.id FROM locations l WHERE l.id <> :l AND l.name = 'Bandung'"
                ),
                {"l": b["location_id"]},
            )
        ).first()
        if row:
            return row[0]
        row = (
            await db.execute(
                text("SELECT id FROM locations WHERE id <> :l LIMIT 1"),
                {"l": b["location_id"]},
            )
        ).first()
        return row[0]

    sumber_lain = _jalankan(_lokasi_lain)
    did = _buat_keputusan(
        jenis="regional_balance",
        source=sumber_lain,
        target=b["location_id"],
        commodity=b["commodity_id"],
    )
    try:
        hasil = _persist(
            did, {"batch_ids": [str(b["batch_id"])], "supplier_id": str(b["supplier_id"])}
        )
        assert hasil["status"] == 422, hasil
        assert "binding batch/supplier tidak cocok" in hasil["detail"]
    finally:
        _hapus(did)
