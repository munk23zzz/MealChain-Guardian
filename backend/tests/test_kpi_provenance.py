"""Fase 8 MG — KPI: cakupan sesi, porsi/disposal yang benar, dan provenance.

Empat cacat yang ditutup berkas ini (rencana `phase-08-kpi-provenance.md`):

1. **Kontaminasi demo.** Fakta milik sesi demo ikut terhitung sebagai hasil
   operasional. Akibatnya kartu KPI "hari ini" berisi angka simulasi, dan
   sebaliknya angka operasional bisa tersaring keluar. Kontrak sekarang:
   cakupan operasional = `demo_session_id IS NULL`; cakupan demo = SATU
   `demo_session_id` yang disebut eksplisit (tidak ada "sesi terbaru").
2. **Porsi tersaji dari bahan diterima.** `catat_penerimaan` dulu menulis
   `delivery_events.delivered_portions` dari kg yang diterima — bahan di gudang
   bukan makanan yang tersaji. Sekarang penerimaan hanya menghasilkan PROYEKSI
   berlabel, bukan fakta tersaji.
3. **Disposal dari freshness.** Skor kesegaran tidak boleh menjadi limbah
   aktual; ia hanya boleh menjadi estimasi susut berlabel.
4. **Angka tanpa asal.** Setiap metrik wajib membawa `source`, `period`,
   `sample_count`, `coverage`, `definition`, `formula`, `method_version`,
   `evidence_kind`, dan baseline/no-baseline.

Jendela uji sengaja jauh di masa depan (2031) supaya tidak bertabrakan dengan
data kanon/demo: yang terhitung hanya baris yang dibuat tes ini. Semua baris
dibersihkan di `finally`, jadi DB gate tetap bisa dipakai ulang.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services import settlement
from app.services.kpi_service import METRIC_NAMES, compute_kpis
from tests.dsn import DSN_ASYNC

#: Jendela uji terisolasi: tidak ada data kanon/demo di sini.
AWAL = datetime(2031, 6, 1, tzinfo=timezone.utc)
AKHIR = datetime(2031, 6, 30, tzinfo=timezone.utc)
TANGGAL_RENCANA = date(2031, 6, 10)
TANGGAL_KEDUA = date(2031, 6, 11)


def _jalankan(fn):
    async def _main():
        eng = create_async_engine(DSN_ASYNC)
        maker = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with maker() as db:
                return await fn(db)
        finally:
            await eng.dispose()

    return asyncio.run(_main())


def _metrik(db_result) -> dict[str, dict]:
    return {m["name"]: m for m in db_result}


async def _kpi(
    db, *, awal: datetime = AWAL, akhir: datetime = AKHIR, **kwargs
) -> dict[str, dict]:
    return _metrik(await compute_kpis(db, awal, akhir, None, **kwargs))


async def _lokasi_komoditas(db) -> tuple[uuid.UUID, uuid.UUID]:
    lokasi = (await db.execute(text("SELECT id FROM locations LIMIT 1"))).scalar()
    komoditas = (await db.execute(text("SELECT id FROM commodities LIMIT 1"))).scalar()
    assert lokasi is not None and komoditas is not None, "DB uji butuh lokasi + komoditas"
    return lokasi, komoditas


async def _sesi_demo(db, *, dibuat: str) -> uuid.UUID:
    """Sesi demo 'expired' (bukan aktif) — cukup sebagai pemilik fakta."""
    sesi = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO demo_sessions (id, status, started_at, expires_at, anchor_now, "
            "mode, evaluation_anchor) VALUES (:id, 'expired', :d, :d, :d, 'replay', :d)"
        ),
        {"id": sesi, "d": datetime(2031, 6, 1, tzinfo=timezone.utc)},
    )
    return sesi


async def _rencana_dan_kiriman(
    db,
    sesi: uuid.UUID | None,
    *,
    porsi: int,
    terkirim: int,
    tanggal: date = TANGGAL_RENCANA,
):
    lokasi, _ = await _lokasi_komoditas(db)
    rencana = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO menu_plans (id, location_id, plan_date, planned_portions, origin, "
            "demo_session_id) VALUES (:id, :l, CAST(:t AS date), :p, :o, :s)"
        ),
        {
            "id": rencana,
            "l": lokasi,
            "t": tanggal,
            "p": porsi,
            "o": "demo" if sesi else "seed",
            "s": sesi,
        },
    )
    await db.execute(
        text(
            "INSERT INTO delivery_events (id, menu_plan_id, delivered_portions, status, "
            "delivered_at, origin, demo_session_id) "
            "VALUES (:id, :m, :p, 'delivered', :d, :o, :s)"
        ),
        {
            "id": uuid.uuid4(),
            "m": rencana,
            "p": terkirim,
            "d": datetime(2031, 6, 10, 4, tzinfo=timezone.utc),
            "o": "demo" if sesi else "seed",
            "s": sesi,
        },
    )
    return rencana


async def _bersihkan(db) -> None:
    """Hapus semua baris uji (jendela 2031) tanpa menyentuh data kanon/demo."""
    for tanggal in (TANGGAL_RENCANA, TANGGAL_KEDUA):
        await db.execute(
            text(
                "DELETE FROM delivery_events WHERE menu_plan_id IN "
                "(SELECT id FROM menu_plans WHERE plan_date = CAST(:t AS date))"
            ),
            {"t": tanggal},
        )
        await db.execute(
            text("DELETE FROM menu_plans WHERE plan_date = CAST(:t AS date)"),
            {"t": tanggal},
        )
    await db.execute(
        text(
            "DELETE FROM disposal_events WHERE disposed_at >= :a AND disposed_at < :b"
        ),
        {"a": AWAL, "b": AKHIR},
    )
    await db.execute(
        text("DELETE FROM demo_sessions WHERE anchor_now = :d"),
        {"d": datetime(2031, 6, 1, tzinfo=timezone.utc)},
    )
    await db.commit()


# --------------------------------------------------------------- 1. cakupan


def test_fakta_sesi_demo_tidak_masuk_operasional():
    """`include_demo=False` = `demo_session_id IS NULL`, dan hasilnya `no_data` — bukan 0%."""

    async def _skenario(db):
        sesi = await _sesi_demo(db, dibuat="2031-06-01")
        await _rencana_dan_kiriman(db, sesi, porsi=1000, terkirim=900)
        await db.commit()
        try:
            operasional = await _kpi(db, include_demo=False)
            demo = await _kpi(db, include_demo=True, demo_session_id=sesi)
            return operasional, demo
        finally:
            await _bersihkan(db)

    operasional, demo = _jalankan(_skenario)
    mc_ops = operasional["Meal Continuity Rate"]
    assert mc_ops["state"] == "no_data", mc_ops
    # Bukan angka palsu: 0% akan berarti "rencana ada, tidak ada yang terkirim".
    assert mc_ops["value"] is None, mc_ops
    assert mc_ops["reason"], "alasan no_data wajib ada"
    assert mc_ops["sample_count"] == 0

    mc_demo = demo["Meal Continuity Rate"]
    assert mc_demo["state"] == "available", mc_demo
    assert float(mc_demo["value"]) == pytest.approx(90.0)
    assert mc_demo["sample_count"] == 1


def test_sesi_demo_dipilih_eksplisit_bukan_terbaru():
    """Dua sesi: yang diminta harus yang dipakai, bukan yang terakhir dibuat."""

    async def _skenario(db):
        sesi_a = await _sesi_demo(db, dibuat="2031-06-01")
        await _rencana_dan_kiriman(db, sesi_a, porsi=1000, terkirim=900)
        sesi_b = await _sesi_demo(db, dibuat="2031-06-02")  # lebih baru
        await _rencana_dan_kiriman(
            db, sesi_b, porsi=1000, terkirim=200, tanggal=TANGGAL_KEDUA
        )
        await db.commit()
        try:
            a = await _kpi(db, include_demo=True, demo_session_id=sesi_a)
            b = await _kpi(db, include_demo=True, demo_session_id=sesi_b)
            return a, b
        finally:
            await _bersihkan(db)

    a, b = _jalankan(_skenario)
    assert float(a["Meal Continuity Rate"]["value"]) == pytest.approx(90.0)
    assert float(b["Meal Continuity Rate"]["value"]) == pytest.approx(20.0)


def test_cakupan_demo_tanpa_sesi_ditolak():
    """Tidak ada jalur 'sesi terbaru': cakupan demo wajib menyebut sesinya."""

    async def _db_kosong(db):
        return await compute_kpis(db, AWAL, AKHIR, None, include_demo=True)

    with pytest.raises(ValueError):
        _jalankan(_db_kosong)


# ------------------------------------------------- 2. porsi & disposal aktual


def test_penerimaan_bahan_tidak_menulis_porsi_tersaji():
    """Bahan diterima ≠ makanan tersaji: penerimaan hanya memberi proyeksi."""

    async def _skenario(db):
        lokasi, komoditas = await _lokasi_komoditas(db)
        rencana = await db.execute(
            text(
                "SELECT id, planned_portions FROM menu_plans WHERE planned_portions > 0 LIMIT 1"
            )
        )
        baris = rencana.first()
        if baris is None:
            pytest.skip("DB uji tanpa menu plan berisi porsi")
        batch = SimpleNamespace(
            location_id=lokasi, commodity_id=komoditas, quantity_kg=Decimal("30.00")
        )
        receipt = SimpleNamespace(id=uuid.uuid4())
        hasil = await settlement.catat_penerimaan(
            db, batch=batch, receipt=receipt, sekarang=datetime.now(timezone.utc)
        )
        await db.flush()
        jumlah = (
            await db.execute(
                text(
                    "SELECT count(*) FROM delivery_events WHERE source_ref = :r"
                ),
                {"r": f"receipt:{receipt.id}"},
            )
        ).scalar()
        await db.rollback()
        return hasil, int(jumlah or 0)

    hasil, jumlah_delivery = _jalankan(_skenario)
    assert jumlah_delivery == 0, "penerimaan tidak boleh menulis baris porsi tersaji"
    assert hasil["ditulis"] is False
    assert "proyeksi" in str(hasil.get("alasan", "")).lower(), hasil
    # Proyeksi tetap dihitung (bukan dibuang), hanya TIDAK disimpan sebagai fakta.
    if hasil.get("proyeksi_porsi") is not None:
        assert hasil["proyeksi_porsi"] > 0


def test_freshness_tidak_menjadi_disposal_aktual():
    """Skor kesegaran hanya boleh muncul sebagai estimasi berlabel, tidak sebagai disposal."""
    sekarang = datetime.now(timezone.utc)
    awal = sekarang - timedelta(days=30)
    hasil = _jalankan(
        lambda db: _kpi(db, awal=awal, akhir=sekarang, include_demo=False)
    )
    loss = hasil["Avoidable Food Loss"]

    est = loss.get("estimate")
    assert est is not None, "kehilangan pangan wajib memisahkan estimasi dari fakta"
    assert est["evidence_kind"] == "simulated_estimate"
    assert "freshness" in str(est["source"]).lower(), est

    # Nilai metrik tidak boleh berasal dari freshness: sumbernya hanya kejadian
    # tercatat (disposal + pasokan yang diterima).
    sumber_nilai = str(loss["provenance"]["source"]).lower()
    assert "disposal_events" in sumber_nilai
    assert "freshness" not in sumber_nilai

    if loss["state"] == "available":
        assert loss["value"] is not None
    else:
        assert loss["value"] is None, "metrik tanpa kejadian disposal tidak boleh 0"


# ------------------------------------------------------------- 3. provenance


Wajib = (
    "source",
    "period",
    "sample_count",
    "coverage",
    "definition",
    "formula",
    "method_version",
    "evidence_kind",
    "baseline",
)


def test_setiap_metrik_membawa_provenance_lengkap():
    hasil = _jalankan(lambda db: _kpi(db, include_demo=False))
    assert list(hasil) == list(METRIC_NAMES)

    for nama, m in hasil.items():
        prov = m.get("provenance")
        assert isinstance(prov, dict), f"{nama}: provenance hilang"
        for kunci in Wajib:
            assert kunci in prov, f"{nama}: provenance tanpa {kunci}"
        # `source` harus menunjuk tabel.kolom, bukan kalimat pemasaran.
        assert "." in prov["source"], f"{nama}: source bukan tabel.kolom: {prov['source']}"
        assert prov["method_version"], f"{nama}: method_version kosong"
        assert prov["evidence_kind"] in {
            "recorded_fact",
            "derived",
            "simulated_estimate",
        }, f"{nama}: evidence_kind tak dikenal {prov['evidence_kind']!r}"
        assert prov["definition"] and prov["formula"], f"{nama}: definisi/rumus kosong"
        periode = prov["period"]
        assert periode.get("start") and periode.get("end") and periode.get("basis"), (
            nama,
            periode,
        )
        assert isinstance(m["sample_count"], int)
        assert "coverage" in m and "sample_count" in m

        baseline = prov["baseline"]
        assert baseline["kind"] in {"value", "no_baseline"}, (nama, baseline)
        if baseline["kind"] == "no_baseline":
            assert baseline["value"] is None, f"{nama}: baseline kosong tapi bernilai"
            assert baseline["reason"], f"{nama}: tanpa baseline harus ada alasannya"


def test_tidak_ada_metrik_estimasi_tanpa_label():
    """Metrik yang nilainya proyeksi wajib bertanda estimasi — tidak diam-diam."""
    hasil = _jalankan(lambda db: _kpi(db, include_demo=False))
    for nama, m in hasil.items():
        if m["provenance"]["evidence_kind"] == "simulated_estimate":
            assert m.get("estimate"), f"{nama}: estimasi tanpa blok estimate"
            assert m["estimate"]["evidence_kind"] == "simulated_estimate"
            assert m["estimate"].get("definition"), f"{nama}: estimasi tanpa definisi"


def test_baseline_tidak_dikarang_nol():
    hasil = _jalankan(lambda db: _kpi(db, include_demo=False))
    for nama, m in hasil.items():
        b = m["provenance"]["baseline"]
        if b["kind"] == "no_baseline":
            assert b["value"] is None, f"{nama}: baseline 'tidak ada' tidak boleh diisi angka"
            assert "0" not in str(b["value"] or ""), nama


# ------------------------------------- 5. klasifikasi asal baris (baris 23 fase)
#
# Spesifikasi: baris lama harus DIKLASIFIKASIKAN `historical_seed`, dan query
# operasional tidak boleh memperlakukannya sebagai fakta baru. Tanpa ini angka
# operasional terbaca seolah catatan lapangan hari ini, padahal seluruh faktanya
# berasal dari data seed (di DB demo: 100% baris 30 hari terakhir).


def test_basis_asal_empat_kemungkinan():
    from app.services.kpi_service import _basis_asal

    assert _basis_asal(0, 0) == "tidak_ada_data"
    assert _basis_asal(3, 0) == "historical_seed"
    assert _basis_asal(0, 3) == "live"
    assert _basis_asal(2, 1) == "campuran"


def test_metrik_operasional_menyebut_barisnya_historical_seed():
    async def _skenario(db):
        await _bersihkan(db)
        await _rencana_dan_kiriman(db, None, porsi=1000, terkirim=1000)
        await db.commit()
        try:
            prov = (await _kpi(db))["Meal Continuity Rate"]["provenance"]
            assert prov["data_basis"] == "historical_seed", prov.get("data_basis")
            kl = prov["classification"]
            # menu_plans + delivery_events yang baru dibuat = dua baris seed.
            assert kl["historical_seed"] == 2, kl
            assert kl["live"] == 0, kl
        finally:
            await _bersihkan(db)

    _jalankan(_skenario)


def test_metrik_sesi_demo_tidak_disebut_live_maupun_seed():
    async def _skenario(db):
        await _bersihkan(db)
        sesi = await _sesi_demo(db, dibuat="2031-06-01")
        await _rencana_dan_kiriman(db, sesi, porsi=800, terkirim=800)
        await db.commit()
        try:
            prov = (
                await _kpi(db, include_demo=True, demo_session_id=sesi)
            )["Meal Continuity Rate"]["provenance"]
            assert prov["data_basis"] == "sesi_demo", prov.get("data_basis")
            assert "classification" not in prov or prov["classification"].get(
                "historical_seed"
            ) in (0, None)
        finally:
            await _bersihkan(db)

    _jalankan(_skenario)


def test_klasifikasi_menghitung_baris_bukan_metrik():
    """`classification` menghitung baris sumber; `sample_count` menghitung unit
    analisis. Dua angka berbeda tidak boleh disamakan: pembaca perlu tahu berapa
    baris historis yang menyusun angka, bukan hanya berapa sampel yang dinilai."""

    async def _skenario(db):
        await _bersihkan(db)
        await _rencana_dan_kiriman(db, None, porsi=1000, terkirim=900)
        await _rencana_dan_kiriman(
            db, None, porsi=1000, terkirim=950, tanggal=TANGGAL_KEDUA
        )
        await db.commit()
        try:
            m = (await _kpi(db))["Meal Continuity Rate"]
            prov = m["provenance"]
            assert prov["classification"]["historical_seed"] == 4, prov["classification"]
            assert prov["sample_count"] >= 2, prov["sample_count"]
        finally:
            await _bersihkan(db)

    _jalankan(_skenario)
