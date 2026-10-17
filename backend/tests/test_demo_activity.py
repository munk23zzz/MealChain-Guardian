"""Kegiatan demo (kiriman di seluruh lokasi) harus benar & idempoten.

Kenapa ada: pemilik ingin aplikasi "terlihat aktif" di semua peran. Seed kanonik
hanya punya 9 batch Jakarta. Modul `app.seed.demo_activity` menambah kiriman
`origin='demo'` di 10 lokasi. Tes ini mengunci janji yang membuatnya AMAN:

1. idempoten — menyegarkan dua kali tidak menggandakan kiriman;
2. tiga keadaan perjalanan benar-benar ada (belum berangkat / di jalan / tiba);
3. semua baris ber-origin 'demo' + `generated_at` terisi (bisa dibedakan dari
   kanonik dan bisa dibersihkan tombol "Bersihkan data demo");
4. kolom bermakna (kuantitas > 0, masa layak sesudah panen, jam berangkat
   sesudah panen);
5. pembersih benar-benar membuang kiriman demo (tanpa menyentuh kanonik).

Tes membersihkan kiriman yang ia buat sendiri, supaya DB kerja tidak
tertinggal ramai oleh 40 baris setelah suite selesai.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.db import create_engine, create_session_maker
from app.models import Batch
from app.seed.demo_activity import seed_demo_activity

NOW = datetime(2026, 10, 17, 5, 0, tzinfo=UTC)


async def _jalankan(now: datetime = NOW) -> tuple[dict, list[Batch]]:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            hasil = await seed_demo_activity(s, now)
            await s.commit()
        async with maker() as s:
            baris = list(
                (await s.execute(select(Batch).where(Batch.origin == "demo"))).scalars()
            )
        return hasil, baris
    finally:
        await engine.dispose()


async def _bersihkan() -> None:
    engine = create_engine(settings.database_url)
    maker = create_session_maker(engine)
    try:
        async with maker() as s:
            await s.execute(delete(Batch).where(Batch.origin == "demo"))
            await s.commit()
    finally:
        await engine.dispose()


def test_idempoten_dan_tiga_keadaan() -> None:
    import asyncio

    async def skenario() -> None:
        try:
            await _bersihkan()
            hasil1, baris1 = await _jalankan()
            assert hasil1["batch_demo"] > 0
            ids1 = {b.id for b in baris1}

            hasil2, baris2 = await _jalankan(NOW + timedelta(minutes=5))
            ids2 = {b.id for b in baris2}
            assert hasil2["batch_demo"] == 0, "jalur kedua harus memperbarui, bukan menambah"
            assert ids1 == ids2, "id deterministik: tidak boleh ada duplikat"
            assert len(baris2) == len(baris1)

            # Tiga keadaan perjalanan nyata (bukan hanya satu jenis data).
            belum = [b for b in baris2 if b.dispatched_at is None]
            jalan = [
                b
                for b in baris2
                if b.dispatched_at and b.dispatched_at > NOW - timedelta(hours=2)
            ]
            tiba = [
                b
                for b in baris2
                if b.dispatched_at and b.dispatched_at <= NOW - timedelta(hours=3)
            ]
            assert belum and jalan and tiba, (len(belum), len(jalan), len(tiba))

            # Kolom bermakna + penanda demo.
            for b in baris2:
                assert b.origin == "demo"
                assert b.generated_at is not None
                assert b.quantity_kg > 0
                assert b.usable_until > b.harvested_at
                if b.dispatched_at is not None:
                    assert b.dispatched_at >= b.harvested_at

            # Sebaran lokasi: bukan hanya satu kota.
            assert len({b.location_id for b in baris2}) >= 5

            # Pembersih membuang kiriman demo saja.
            await _bersihkan()
            _, sisa = await _jalankan()
            assert len(sisa) == len(baris1), "pembersih lalu seed ulang harus kembali penuh"
            await _bersihkan()
        finally:
            await _bersihkan()

    asyncio.run(skenario())


def test_keputusan_selesai_memenuhi_empat_metrik_kpi() -> None:
    """Empat metrik KPI "hari ini" hanya bisa terisi kalau barisnya memenuhi syarat.

    Bukan uji tampilan: tes ini menegaskan syarat yang DIBACA `kpi_service`,
    supaya data demo tidak sekadar "ada" tetapi benar-benar counted:
    - Safe Delivered Cost : PO mock hari ini + decisions.safe_delivered_cost
    - Decision Time       : trace DETECT & ACT hari ini, ACT sesudah approval
    - Evidence Completeness: >= 2 jenis bukti konsisten SEBELUM approval
    - Avoidable Food Loss : disposal_events hari ini
    """
    import asyncio

    from sqlalchemy import delete, select

    from app.models import (
        AgentTrace,
        Approval,
        Decision,
        DecisionEvidence,
        DisposalEvent,
        SapMockPurchaseOrder,
    )
    from app.seed.demo_activity import (
        demo_decision_id,
        seed_demo_completed_decisions,
    )

    async def skenario() -> None:
        engine = create_engine(settings.database_url)
        maker = create_session_maker(engine)
        kandidat = [
            demo_decision_id(kota, komoditas)
            for kota in ("Bandung", "Jakarta", "Surabaya")
            for komoditas in ("telur", "ayam", "wortel")
        ]
        try:
            # Mulai dari keadaan bersih: kalau tidak, jalur pertama hanya
            # "memperbarui" baris yang ditinggalkan refresh demo sebelumnya.
            async with maker() as s:
                await s.execute(
                    delete(SapMockPurchaseOrder).where(
                        SapMockPurchaseOrder.decision_id.in_(kandidat)
                    )
                )
                await s.execute(delete(Decision).where(Decision.id.in_(kandidat)))
                # HANYA dua baris limbah milik modul ini — jangan menyapu
                # seluruh `origin='demo'`: deret waktu demo memakai alasan yang
                # sama dan akan ikut terhapus.
                import uuid as _uuid

                await s.execute(
                    delete(DisposalEvent).where(
                        DisposalEvent.id.in_([
                            _uuid.uuid5(
                                _uuid.NAMESPACE_URL,
                                f"mcg:demo-aktivitas:limbah:jakarta:{n}",
                            )
                            for n in (0, 1)
                        ])
                    )
                )
                await s.commit()

            async with maker() as s:
                pertama = await seed_demo_completed_decisions(s, NOW)
                await s.commit()
            assert pertama["keputusan_demo"] > 0
            assert pertama["limbah_demo"] > 0

            async with maker() as s:
                kedua = await seed_demo_completed_decisions(s, NOW + timedelta(minutes=5))
                await s.commit()
            assert kedua["keputusan_demo"] == 0, "jalur kedua harus idempoten"
            assert kedua["limbah_demo"] == 0

            async with maker() as s:
                jakarta = (
                    await s.execute(select(Decision.id).where(Decision.origin == "demo"))
                ).scalars().all()
                kandidat = [
                    demo_decision_id(kota, komoditas)
                    for kota in ("Bandung", "Jakarta", "Surabaya")
                    for komoditas in ("telur", "ayam", "wortel")
                ]
                dipakai = [d for d in jakarta if d in kandidat]
                assert dipakai, "tidak ada keputusan demo yang terbuat"

                for did in dipakai:
                    d = await s.get(Decision, did)
                    assert d.created_at >= NOW - timedelta(hours=2)
                    assert d.safe_delivered_cost is not None
                    assert d.demo_case is None  # ikut dihitung KPI (bukan kasus skrip)

                    acc = (
                        await s.execute(
                            select(Approval).where(
                                Approval.decision_id == did, Approval.approved.is_(True)
                            )
                        )
                    ).scalars().first()
                    assert acc is not None
                    bukti = list(
                        (await s.execute(
                            select(DecisionEvidence).where(
                                DecisionEvidence.decision_id == did,
                                DecisionEvidence.is_consistent.is_(True),
                                DecisionEvidence.recorded_at < acc.approved_at,
                            )
                        )).scalars()
                    )
                    assert len({b.evidence_type for b in bukti}) >= 2

                    traces = {
                        t.step_name: t.step_at
                        for t in (await s.execute(
                            select(AgentTrace).where(AgentTrace.decision_id == did)
                        )).scalars()
                    }
                    assert "DETECT" in traces and "ACT" in traces
                    assert traces["ACT"] > acc.approved_at
                    assert traces["DETECT"] >= NOW - timedelta(hours=2)

                    po = (
                        await s.execute(
                            select(SapMockPurchaseOrder).where(
                                SapMockPurchaseOrder.decision_id == did
                            )
                        )
                    ).scalars().first()
                    assert po is not None and po.price > 0

                limbah = list(
                    (await s.execute(
                        select(DisposalEvent).where(DisposalEvent.origin == "demo")
                    )).scalars()
                )
                assert any(e.disposed_at >= NOW - timedelta(hours=4) for e in limbah)

                # Bersihkan hanya baris yang tes ini buat. PO tidak punya FK ke
                # decisions, jadi ia harus dihapus eksplisit (kalau tidak, tes
                # meninggalkan PO yatim yang mengotori metrik SDC berikutnya).
                await s.execute(
                    delete(SapMockPurchaseOrder).where(
                        SapMockPurchaseOrder.decision_id.in_(dipakai)
                    )
                )
                await s.execute(delete(Decision).where(Decision.id.in_(dipakai)))
                await s.commit()

            # Kembalikan keadaan demo sesudah membersihkan: suite ini berbagi DB
            # dengan aplikasi. Keputusan selesai + PO `DEMO-PO-*` dipakai tab KPI
            # dan panel PO; menghapusnya tanpa memulihkan membuat berkas tes LAIN
            # gagal hanya karena urutan (mis. `test_sap_orders_api` memaku
            # "seed punya PO Jakarta") dan membuka aplikasi sesudah pytest
            # memperlihatkan panel kosong.
            async with maker() as s:
                await seed_demo_completed_decisions(s, datetime.now(UTC))
                await s.commit()
        finally:
            await engine.dispose()

    asyncio.run(skenario())
