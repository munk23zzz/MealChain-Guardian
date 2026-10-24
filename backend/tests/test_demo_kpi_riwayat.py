"""KPI 24 jam dimulai dari "belum ada aksi hari ini" — kontrak penyemai demo.

Permintaan pemilik (23 Okt 2026): saat demo dimulai, kartu KPI 24 jam belum
berisi angka aksi. Angka itu baru muncul ketika operator benar-benar
menjalankan alurnya (Event 1 -> approve -> execute -> Event 3). Sebabnya
sederhana: empat dari tujuh metrik hanya bisa lahir dari aksi
(Imbalance, Safe Delivered Cost, Decision Time, Evidence Completeness),
sementara tiga lainnya (Meal Continuity, Avoidable Food Loss, Price Deviation)
hanya punya penulis di penyemai.

Karena itu penyemai demo menggeser baris AKSI lokasi demo (Jakarta) ke luar
jendela 24 jam, sementara baris FAKTA hari ini (menu plan, kiriman, limbah,
kutipan harga, supply) tidak disentuh. Jakarta dipilih karena itulah akun yang
dipakai mendemokan; kota lain dan pandangan global BGN Monitor tetap seperti
disemai. Yang dikunci berkas ini:

1. lima tabel aksi (`decisions`, `agent_traces`, `approvals`,
   `decision_evidence`, `sap_mock_purchase_orders`) milik Jakarta yang lahir di
   jendela 24 jam digeser ke belakang — urutan relatifnya tetap;
2. `decisions.expires_at` TIDAK ikut bergeser: keputusan yang menunggu
   tindakan tetap punya tenggat berjalan;
3. baris lokasi lain (uji: Bandung) tidak tersentuh, dan baris yang sudah di
   luar jendela juga tidak, jadi menjalankan fungsi dua kali tidak menggeser
   apa pun lagi (idempoten).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db import create_engine as create_async_engine
from app.db import create_session_maker
from app.seed.demo_kpi_riwayat import geser_aksi_ke_riwayat
from tests.dsn import DSN_SYNC

PENANDA = "uji-kpi-riwayat"


def _tanam_aksi(now: datetime, lokasi: str = "Jakarta", geser_detik: int = 0) -> dict:
    """Tanam satu rantai aksi lengkap di dalam jendela 24 jam milik tes ini."""
    now = now + timedelta(seconds=geser_detik)
    ids = {
        "decision": str(uuid.uuid4()),
        "trace": str(uuid.uuid4()),
        "evidence": str(uuid.uuid4()),
        "approval": str(uuid.uuid4()),
        "po": str(uuid.uuid4()),
    }
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            user_id = conn.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
            supplier_id = conn.execute(text("SELECT id FROM suppliers LIMIT 1")).scalar_one()
            lokasi_id = conn.execute(
                text("SELECT id FROM locations WHERE name = :n"), {"n": lokasi}
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO decisions (id, decision_type, status, proposed_by, "
                    "expires_at, created_at, iteration, origin, generated_at, "
                    "source_location_id) VALUES "
                    "(:id, 'regional_balance', 'proposed', :proposed, :expires, :created, "
                    "0, 'demo', :created, :loc)"
                ),
                {
                    "id": ids["decision"],
                    "proposed": PENANDA,
                    "expires": now + timedelta(hours=2),
                    "created": now - timedelta(hours=1),
                    "loc": lokasi_id,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO agent_traces (id, decision_id, step_name, step_at) "
                    "VALUES (:id, :d, 'DETECT', :at)"
                ),
                {
                    "id": ids["trace"],
                    "d": ids["decision"],
                    "at": now - timedelta(minutes=55),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO decision_evidence (id, decision_id, evidence_type, "
                    "payload, is_consistent, recorded_at) VALUES "
                    "(:id, :d, 'human_inspection', '{}'::jsonb, true, :at)"
                ),
                {
                    "id": ids["evidence"],
                    "d": ids["decision"],
                    "at": now - timedelta(minutes=50),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO approvals (id, decision_id, approved_by, approved, "
                    "approved_at) VALUES (:id, :d, :u, true, :at)"
                ),
                {
                    "id": ids["approval"],
                    "d": ids["decision"],
                    "u": user_id,
                    "at": now - timedelta(minutes=40),
                },
            )
            conn.execute(
                text(
                    "INSERT INTO sap_mock_purchase_orders (id, po_number, supplier_id, "
                    "material_number, ordered_quantity, price, decision_id, status, "
                    "created_at, origin) VALUES (:id, :po, :s, 'MAT-UJI', 1, 1000, "
                    ":d, 'draft', :at, 'demo')"
                ),
                {
                    "id": ids["po"],
                    "po": f"{PENANDA}-{uuid.uuid4().hex[:8]}",
                    "s": supplier_id,
                    "d": ids["decision"],
                    "at": now - timedelta(minutes=30),
                },
            )
    finally:
        engine.dispose()
    return ids


def _baca(ids: dict) -> dict:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            baris = conn.execute(
                text(
                    "SELECT d.created_at, d.generated_at, d.expires_at, "
                    "(SELECT step_at FROM agent_traces WHERE id = :t), "
                    "(SELECT recorded_at FROM decision_evidence WHERE id = :e), "
                    "(SELECT approved_at FROM approvals WHERE id = :a), "
                    "(SELECT created_at FROM sap_mock_purchase_orders WHERE id = :p) "
                    "FROM decisions d WHERE d.id = :d"
                ),
                {
                    "d": ids["decision"],
                    "t": ids.get("trace"),
                    "e": ids.get("evidence"),
                    "a": ids.get("approval"),
                    "p": ids.get("po"),
                },
            ).one()
    finally:
        engine.dispose()
    return {
        "created_at": baris[0],
        "generated_at": baris[1],
        "expires_at": baris[2],
        "trace": baris[3],
        "evidence": baris[4],
        "approval": baris[5],
        "po": baris[6],
    }


def _hapus(ids: dict) -> None:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            for tabel in (
                "sap_mock_purchase_orders",
                "approvals",
                "decision_evidence",
                "agent_traces",
            ):
                conn.execute(
                    text(f"DELETE FROM {tabel} WHERE decision_id = :d"),
                    {"d": ids["decision"]},
                )
            conn.execute(
                text("DELETE FROM decisions WHERE id = :d"), {"d": ids["decision"]}
            )
    finally:
        engine.dispose()


def _jalankan(now: datetime) -> dict:
    import asyncio

    async def _isi() -> dict:
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                hasil = await geser_aksi_ke_riwayat(session, now)
                await session.commit()
                return hasil
        finally:
            await engine.dispose()

    return asyncio.run(_isi())


def test_aksi_bergeser_keluar_jendela_24_jam_urutan_tetap():
    now = datetime.now(timezone.utc)
    ids = _tanam_aksi(now)
    try:
        sebelum = _baca(ids)
        hasil = _jalankan(now)
        sesudah = _baca(ids)

        assert hasil["aktif"] is True
        assert hasil["digeser"], "tidak ada baris yang digeser"
        batas = now - timedelta(hours=24)
        for kunci in ("created_at", "generated_at", "trace", "evidence", "approval", "po"):
            assert sesudah[kunci] < batas, f"{kunci} masih di dalam jendela 24 jam"

        # Urutan rantai bukti tidak boleh berubah oleh pergeseran.
        assert (
            sesudah["created_at"]
            < sesudah["evidence"]
            < sesudah["approval"]
            < sesudah["po"]
        )
        assert sesudah["trace"] < sesudah["approval"]

        # Tenggat keputusan TIDAK ikut bergeser.
        assert sesudah["expires_at"] == sebelum["expires_at"]
    finally:
        _hapus(ids)


def test_lokasi_lain_tidak_digeser():
    now = datetime.now(timezone.utc)
    ids = _tanam_aksi(now, lokasi="Bandung")
    try:
        sebelum = _baca(ids)
        _jalankan(now)
        sesudah = _baca(ids)

        assert sesudah == sebelum, "baris lokasi non-demo ikut tergeser"
    finally:
        _hapus(ids)


def test_baris_orm_belum_diflush_ikut_digeser():
    """Penyemai menambah baris lewat ORM; UPDATE raw SQL butuh flush dulu.

    Tanpa `await db.flush()`, keputusan yang baru di-`add` tidak terlihat oleh
    UPDATE dan ter-commit dengan tanggal aslinya (terukur 23 Okt 2026: 7
    keputusan Jakarta tetap berada di jendela 24 jam).
    """
    import asyncio

    from sqlalchemy import select

    from app.db import create_engine as create_async_engine
    from app.db import create_session_maker
    from app.models import AgentTrace, Decision, Location

    now = datetime.now(timezone.utc)
    decision_id = uuid.uuid4()
    trace_id = uuid.uuid4()

    async def _isi() -> None:
        engine = create_async_engine(settings.database_url)
        maker = create_session_maker(engine)
        try:
            async with maker() as session:
                lokasi = (
                    await session.execute(select(Location).where(Location.name == "Jakarta"))
                ).scalar_one()
                session.add(
                    Decision(
                        id=decision_id,
                        decision_type="regional_balance",
                        status="proposed",
                        proposed_by=PENANDA,
                        expires_at=now + timedelta(hours=2),
                        created_at=now - timedelta(minutes=30),
                        iteration=0,
                        origin="demo",
                        source_location_id=lokasi.id,
                    )
                )
                # Keputusan di-flush supaya FK trace punya induk; trace DIBIARKAN
                # tertahan di unit-of-work — itulah yang harus terlihat oleh
                # flush di dalam `geser_aksi_ke_riwayat`.
                await session.flush()
                session.add(
                    AgentTrace(
                        id=trace_id,
                        decision_id=decision_id,
                        step_name="DETECT",
                        step_at=now - timedelta(minutes=25),
                    )
                )
                # SENGAJA tanpa flush: inilah keadaan penyemai yang sebenarnya.
                await geser_aksi_ke_riwayat(session, now)
                await session.commit()
        finally:
            await engine.dispose()

    ids = {"decision": str(decision_id), "trace": str(trace_id)}
    try:
        asyncio.run(_isi())
        sesudah = _baca(ids)
        assert sesudah["created_at"] < now - timedelta(hours=24)
        assert sesudah["trace"] < now - timedelta(hours=24)
    finally:
        _hapus(ids)


def test_baris_yang_lahir_sesudah_now_ikut_digeser():
    """Build yang berjalan lama mencatat `now` di awal; baris bisa lahir sesudahnya.

    Terukur 23 Okt 2026: 4 kasus skrip Jakarta punya created_at 57 detik setelah
    `now`, sehingga lolos dari saringan `<= now` dan tetap tinggal di jendela.
    """
    now = datetime.now(timezone.utc)
    ids = _tanam_aksi(now, geser_detik=45)
    try:
        _jalankan(now)
        sesudah = _baca(ids)
        batas = datetime.now(timezone.utc) - timedelta(hours=24)
        for kunci in ("created_at", "trace", "approval", "po"):
            assert sesudah[kunci] < batas, f"{kunci} masih di dalam jendela 24 jam"
    finally:
        _hapus(ids)


def test_jalan_dua_kali_tidak_menggeser_lagi():
    now = datetime.now(timezone.utc)
    ids = _tanam_aksi(now)
    try:
        _jalankan(now)
        sekali = _baca(ids)
        hasil_kedua = _jalankan(now)
        dua_kali = _baca(ids)

        assert hasil_kedua["digeser"] == {}
        assert dua_kali == sekali
    finally:
        _hapus(ids)
