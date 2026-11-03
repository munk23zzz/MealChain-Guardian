"""Kontrak kasus "bukti lengkap" yang tinggal di jendela 24 jam.

Latar (23 Okt 2026): setelah rehearsal penuh, Kelengkapan Bukti berhenti di
0,00% karena keputusan pengadaan hanya membawa satu jenis bukti konsisten
sebelum approval, sedangkan metriknya menuntut >= 2 jenis. Perbaikannya DATA
DEMO saja: satu kasus menunggu persetujuan dengan dua jenis bukti. Berkas ini
mengunci janji-janji yang membuatnya aman:

1. kasus lahir DI DALAM jendela 24 jam dan masih menunggu persetujuan;
2. belum ada approval dan belum ada purchase order — jadi tiga metrik aksi
   lain (Imbalance, Safe Delivered Cost, Decision Time) tetap kosong;
3. ada DUA jenis bukti konsisten berbeda yang direkam sebelum approval;
4. baris ditandai `demo_case`, sehingga Imbalance/Decision Time mengabaikannya;
5. menjalankan penyemai dua kali tidak menggandakan apa pun, dan menghapus
   approval/PO lama supaya cerita demo kembali ke awal.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.seed.demo_kasus_bukti import DEMO_CASE, semai_kasus_bukti_hari_ini
from tests.dsn import DSN_SYNC


def _jalankan(now: datetime) -> dict:
    async def _isi() -> dict:
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                hasil = await semai_kasus_bukti_hari_ini(session, now)
                await session.commit()
                return hasil
        finally:
            await engine.dispose()

    return asyncio.run(_isi())


def _baca() -> dict:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            baris = conn.execute(
                text(
                    "SELECT d.id, d.status, d.demo_case, d.created_at, "
                    "d.verified_by, d.verifier_note, "
                    "(SELECT count(*) FROM approvals a WHERE a.decision_id = d.id), "
                    "(SELECT count(*) FROM sap_mock_purchase_orders p "
                    " WHERE p.decision_id = d.id), "
                    "(SELECT count(DISTINCT e.evidence_type) FROM decision_evidence e "
                    " WHERE e.decision_id = d.id AND e.is_consistent), "
                    "(SELECT count(*) FROM agent_traces t WHERE t.decision_id = d.id) "
                    "FROM decisions d WHERE d.demo_case = :c "
                    "ORDER BY d.created_at DESC LIMIT 1"
                ),
                {"c": DEMO_CASE},
            ).one()
            bukti = [
                (r[0], r[1])
                for r in conn.execute(
                    text(
                        "SELECT e.evidence_type, e.recorded_at FROM decision_evidence e "
                        "WHERE e.decision_id = :d ORDER BY e.recorded_at"
                    ),
                    {"d": baris[0]},
                )
            ]
    finally:
        engine.dispose()
    return {
        "id": str(baris[0]),
        "status": baris[1],
        "demo_case": baris[2],
        "created_at": baris[3],
        "verified_by": baris[4],
        "verifier_note": baris[5],
        "approvals": baris[6],
        "pos": baris[7],
        "jenis_bukti": baris[8],
        "traces": baris[9],
        "bukti": bukti,
    }


def _hapus() -> None:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            ids = [
                r[0]
                for r in conn.execute(
                    text("SELECT id FROM decisions WHERE demo_case = :c"),
                    {"c": DEMO_CASE},
                )
            ]
            for did in ids:
                for tabel in (
                    "sap_mock_purchase_orders",
                    "approvals",
                    "decision_evidence",
                    "agent_traces",
                ):
                    conn.execute(
                        text(f"DELETE FROM {tabel} WHERE decision_id = :d"), {"d": did}
                    )
                conn.execute(text("DELETE FROM decisions WHERE id = :d"), {"d": did})
    finally:
        engine.dispose()


def test_kasus_menunggu_persetujuan_di_dalam_jendela_24_jam():
    now = datetime.now(timezone.utc)
    try:
        hasil = _jalankan(now)
        kasus = _baca()

        assert hasil["decisions"] == 1
        assert kasus["status"] == "pending_approval"
        assert kasus["demo_case"] == DEMO_CASE
        assert kasus["created_at"] >= now - timedelta(hours=24)
        assert kasus["created_at"] <= now
        # Siap disetujui: verifier sudah mencatat hasil konsisten.
        assert kasus["verified_by"]
        assert kasus["verifier_note"] == "consistent"
        # Tiga metrik aksi lain harus tetap kosong karenanya.
        assert kasus["approvals"] == 0
        assert kasus["pos"] == 0
    finally:
        _hapus()


def test_dua_jenis_bukti_konsisten_sebelum_approval():
    now = datetime.now(timezone.utc)
    try:
        _jalankan(now)
        kasus = _baca()

        assert kasus["jenis_bukti"] >= 2, "metrik menuntut >= 2 jenis bukti berbeda"
        jenis = [j for j, _ in kasus["bukti"]]
        assert len(set(jenis)) == len(jenis), "jenis bukti harus berbeda"
        for _, direkam in kasus["bukti"]:
            assert direkam <= now, "bukti harus lahir sebelum approval demo"
        assert kasus["traces"] >= 1
    finally:
        _hapus()


def test_penyemai_ulang_tidak_menggandakan_dan_mereset_persetujuan():
    now = datetime.now(timezone.utc)
    try:
        _jalankan(now)
        kasus = _baca()
        # Tiru demo yang sudah berjalan: satu approval + satu PO buatan tes.
        engine = create_engine(DSN_SYNC)
        try:
            with engine.begin() as conn:
                pengguna = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
                pemasok = conn.execute(
                    text("SELECT id FROM suppliers LIMIT 1")
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO approvals (id, decision_id, approved_by, approved, "
                        "approved_at) VALUES (:i, :d, :u, true, now())"
                    ),
                    {"i": str(uuid.uuid4()), "d": kasus["id"], "u": pengguna},
                )
                conn.execute(
                    text(
                        "INSERT INTO sap_mock_purchase_orders (id, po_number, supplier_id, "
                        "material_number, ordered_quantity, price, decision_id, status, origin) "
                        "VALUES (:i, :po, :s, 'MAT-UJI', 1, 1000, :d, 'draft', 'demo')"
                    ),
                    {
                        "i": str(uuid.uuid4()),
                        "po": f"UJI-{uuid.uuid4().hex[:8]}",
                        "s": pemasok,
                        "d": kasus["id"],
                    },
                )
        finally:
            engine.dispose()

        _jalankan(now + timedelta(minutes=5))
        ulang = _baca()

        assert ulang["id"] == kasus["id"], "penyemai harus idempoten (id sama)"
        assert ulang["approvals"] == 0, "approval lama harus dibersihkan"
        assert ulang["pos"] == 0, "PO lama harus dibersihkan"
        assert ulang["jenis_bukti"] >= 2
        assert ulang["status"] == "pending_approval"
    finally:
        _hapus()
