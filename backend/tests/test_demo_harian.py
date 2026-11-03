"""Kegiatan demo harus IKUT BERGESER saat hari berganti.

Latar (18 Okt 2026): KPI "hari ini" kembali kosong sehari setelah data demo
disemai. Penyejakannya bukan angka yang salah, melainkan TANGGAL: keputusan demo
sudah diperbarui (`created_at = now`), tetapi anak-anaknya (bukti, approval,
jejak agen, PO) hanya ditulis SEKALI saat pertama dibuat. Setelah tanggal
berganti, semuanya berada di luar jendela 24 jam → "tidak ada record pada
periode ini", padahal datanya ada di layar lain.

Tes ini mengunci dua janji:

1. menyemai ulang dengan `now` baru memindahkan SELURUH riwayat (keputusan,
   bukti, approval, jejak, PO, limbah, harga harian) ke hari itu;
2. beras punya keputusan selesai sendiri (bukan hanya komoditas di peta),
   lengkap dengan jejak, bukti, dan dua approval — supaya panel Decision &
   Evidence berisi untuk komoditas itu.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import (
    AgentTrace,
    Approval,
    Commodity,
    Decision,
    DecisionEvidence,
    DisposalEvent,
    PriceSignal,
    SapMockPurchaseOrder,
)
from app.seed.demo_activity import (
    demo_decision_id,
    seed_demo_completed_decisions,
    seed_demo_daily_prices,
)

HARI_1 = datetime(2026, 10, 17, 5, 0, tzinfo=UTC)
HARI_3 = HARI_1 + timedelta(days=2)
#: Jendela KPI "hari ini" = [00:00, 24:00) UTC. Itu batas yang benar: limbah
#: demo memang sengaja 2,5 jam lalu, jadi ambang 90 menit akan menolak data
#: yang justru sah.
AWAL_HARI = HARI_3.replace(hour=0, minute=0, second=0, microsecond=0)


async def _semai(now: datetime) -> dict:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            hasil = await seed_demo_completed_decisions(s, now)
            await seed_demo_daily_prices(s, now)
            await s.commit()
            return hasil
    finally:
        await engine.dispose()


async def _baca(now: datetime) -> dict:
    """Ambil anak-anak demo untuk keputusan yang DIKELOLA seeder ini.

    DB kerja dipakai bersama sesi lain, yang juga menyemai keputusan demo. Tes
    harus menilai baris miliknya sendiri (id deterministik per kota×komoditas),
    bukan seluruh tabel — kalau tidak, baris sesi lain membuat tes gagal karena
    alasan yang tidak ada hubungannya dengan perubahan ini.
    """
    dikelola = {
        demo_decision_id(kota, komoditas)
        for kota in ("Jakarta", "Bandung", "Surabaya")
        for komoditas in ("telur", "ayam", "wortel", "beras")
    }
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            keputusan = list(
                (
                    await s.execute(
                        select(Decision).where(Decision.id.in_(dikelola))
                    )
                ).scalars()
            )
            ids = [k.id for k in keputusan]
            bukti = list(
                (
                    await s.execute(
                        select(DecisionEvidence).where(
                            DecisionEvidence.decision_id.in_(ids)
                        )
                    )
                ).scalars()
            )
            approval = list(
                (
                    await s.execute(
                        select(Approval).where(Approval.decision_id.in_(ids))
                    )
                ).scalars()
            )
            jejak = list(
                (
                    await s.execute(
                        select(AgentTrace).where(AgentTrace.decision_id.in_(ids))
                    )
                ).scalars()
            )
            po = list(
                (
                    await s.execute(
                        select(SapMockPurchaseOrder).where(
                            SapMockPurchaseOrder.decision_id.in_(ids)
                        )
                    )
                ).scalars()
            )
            # Dua kejadian yang MEMANG dikelola seeder ini. Generator deret waktu
            # juga menulis limbah demo (bertanggal 8 Okt) — bukan milik tes ini.
            limbah_ids = {
                uuid.uuid5(
                    uuid.NAMESPACE_URL, f"mcg:demo-aktivitas:limbah:jakarta:{n}"
                )
                for n in (0, 1)
            }
            limbah = list(
                (
                    await s.execute(
                        select(DisposalEvent).where(DisposalEvent.id.in_(limbah_ids))
                    )
                ).scalars()
            )
            return {
                "keputusan": keputusan,
                "bukti": bukti,
                "approval": approval,
                "jejak": jejak,
                "po": po,
                "limbah": limbah,
            }
    finally:
        await engine.dispose()


def test_menyemai_ulang_memindahkan_seluruh_riwayat_ke_hari_ini() -> None:
    import asyncio

    async def skenario() -> None:
        await _semai(HARI_1)
        await _semai(HARI_3)
        data = await _baca(HARI_3)
        awal = AWAL_HARI

        for kolom, nilai in (
            ("created_at", [k.created_at for k in data["keputusan"]]),
            ("recorded_at bukti", [b.recorded_at for b in data["bukti"]]),
            ("approved_at", [a.approved_at for a in data["approval"]]),
            ("step_at jejak", [t.step_at for t in data["jejak"]]),
            ("created_at PO", [p.created_at for p in data["po"]]),
            ("disposed_at", [d.disposed_at for d in data["limbah"]]),
        ):
            assert nilai, f"{kolom}: tidak ada baris demo sama sekali"
            paling_lama = min(nilai)
            assert paling_lama >= awal, (
                f"{kolom} masih di masa lalu ({paling_lama.isoformat()}); "
                f"harus >= {awal.isoformat()} (awal hari) agar masuk jendela KPI"
            )

    asyncio.run(skenario())


def test_beras_punya_keputusan_selesai_lengkap() -> None:
    import asyncio

    async def skenario() -> None:
        await _semai(HARI_3)
        data = await _baca(HARI_3)
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as s:
                beras_id = (
                    await s.execute(
                        select(Commodity.id).where(Commodity.name == "beras")
                    )
                ).scalar_one()
        finally:
            await engine.dispose()

        beras = [k for k in data["keputusan"] if k.commodity_id == beras_id]
        assert len(beras) == 1, f"harus tepat satu keputusan beras, dapat {len(beras)}"
        kid = beras[0].id

        jenis_bukti = {b.evidence_type for b in data["bukti"] if b.decision_id == kid}
        assert len(jenis_bukti) >= 2, jenis_bukti
        langkah = {t.step_name for t in data["jejak"] if t.decision_id == kid}
        assert {"DETECT", "VERIFY", "DECIDE", "ACT"} <= langkah, langkah
        approver = {a.approved_by for a in data["approval"] if a.decision_id == kid}
        assert len(approver) == 2, "regional_balance wajib dua role berbeda"
        assert any(p.decision_id == kid for p in data["po"]), "PO demo beras belum ada"

    asyncio.run(skenario())


def test_harga_harian_demo_tersedia_untuk_hari_ini() -> None:
    """Procurement Price Deviation butuh quote yang punya acuan LEBIH DULU."""
    import asyncio

    async def skenario() -> None:
        await _semai(HARI_3)
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as s:
                baris = list(
                    (
                        await s.execute(
                            select(PriceSignal).where(PriceSignal.origin == "demo")
                        )
                    ).scalars()
                )
        finally:
            await engine.dispose()

        mulai = HARI_3 - timedelta(days=1)
        hari_ini = [p for p in baris if p.recorded_at >= mulai]
        acuan = [p for p in hari_ini if p.source == "pihps_reference"]
        kutipan = [p for p in hari_ini if p.source == "supplier_quote"]
        assert acuan and kutipan, "acuan & kutipan demo hari ini harus ada berpasangan"
        for q in kutipan:
            lebih_dulu = [
                r
                for r in acuan
                if r.location_id == q.location_id
                and r.commodity_id == q.commodity_id
                and r.recorded_at < q.recorded_at
            ]
            assert lebih_dulu, (
                f"kutipan {q.supplier_id} tidak punya acuan PIHPS lebih dulu — "
                "metrik deviasi harga akan kosong"
            )
        assert all(p.price_per_kg > Decimal(0) for p in hari_ini)

    asyncio.run(skenario())
