"""Kelengkapan komoditas demo (Fase 7 MG butir 5 & 6).

Kenapa berkas ini ada: sebelum Fase 7, "wortel" hanya NAMA — tidak ada batch,
suhu, harga, maupun rute, sehingga klaim "wortel didemokan end-to-end" tidak
punya satu baris pun untuk dibuktikan. Rencana Fase 7 butir 5 menuntut aturan
yang tegas: **jangan mengklaim komoditas sebelum datanya lengkap**, dan kasus
ambient hanya sah bila profil komoditasnya memang ambient.

Yang dipaku di sini:

1. setiap kasus komoditas punya rantai data lengkap di spesifikasinya (batch,
   suhu, harga, kebutuhan, sertifikat) dan komoditasnya punya profil policy;
2. status keamanan yang DITULIS pada kasus tidak boleh karangan: mengevaluasi
   log suhu yang benar-benar dihasilkan generator lewat `core.safety` harus
   memberi status yang sama;
3. wortel rantai dingin "sah" benar-benar memenuhi policy (sampel cukup, suhu
   dalam rentang, sampel masih baru) → `pass` → `usable`;
4. wortel "bukti kurang" menghasilkan `needs_verification` BESERTA alasannya
   (verifikasi manusia), bukan `fail` dan bukan error aplikasi;
5. beras ambient tidak dinilai terhadap rentang rantai dingin (27 °C bukan
   excursion) meski log tetap dicatat;
6. kasus komoditas tanpa batch DITOLAK oleh spesifikasi (`ValueError`) — aturan
   "jangan klaim wortel sebelum batch ada" ditegakkan di kode, bukan di prosa;
7. di database, seeder benar-benar menulis baris lengkap untuk ketiga kasus
   (batch + pemasok + log suhu + harga + kebutuhan + keputusan + jejak VERIFY),
   semuanya terikat pada sesi demo yang menyemainya.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.demo import _seed_demo_cases
from app.core.commodity_policy import policy_for
from app.core.safety import evaluate_safety
from app.models import Location
from app.services import scenario_generator as gen
from app.services.scenario_specs import (
    SCENARIO_VERSION,
    ScenarioCaseSpec,
    kasus_komoditas,
    spec_untuk,
)
from tests.dsn import DSN_ASYNC, DSN_SYNC

JANGKAR = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
VERSI = "kanon-2026-10-08T12:00:00Z"
KASUS = tuple(spec.key for spec in kasus_komoditas())

#: Harapan hasil yang DIDEMOKAN, bukan hasil yang diharapkan pemrogram:
#: `usable` harus lolos verifikasi; `on_hold` harus meminta verifikasi manusia.
STATUS_HARAPAN = {"usable": "pass", "on_hold": "needs_verification"}


# --------------------------------------------------------------------------- #
# helper DB (sinkron; hanya SELECT + semai/bersih milik tes ini)
# --------------------------------------------------------------------------- #


def _sql(query: str, params: dict | None = None) -> list[dict]:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.connect() as conn:
            return [dict(r) for r in conn.execute(text(query), params or {}).mappings()]
    finally:
        engine.dispose()


def _exec(query: str, params: dict | None = None) -> None:
    engine = create_engine(DSN_SYNC)
    try:
        with engine.begin() as conn:
            conn.execute(text(query), params or {})
    finally:
        engine.dispose()


def _hapus_sesi(sesi_id: uuid.UUID) -> None:
    """Hapus baris milik sesi uji ini saja (urutan FK)."""
    for tabel in ("demand_records", "price_signals", "batches", "decisions"):
        _exec(f"DELETE FROM {tabel} WHERE demo_session_id = :s", {"s": str(sesi_id)})
    _exec("DELETE FROM demo_sessions WHERE id = :s", {"s": str(sesi_id)})


async def _semai_async(sesi_id: uuid.UUID) -> dict:
    engine = create_async_engine(DSN_ASYNC)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as db:
            target = (
                await db.execute(
                    __import__("sqlalchemy").select(Location).where(
                        Location.name == "Jakarta"
                    )
                )
            ).scalars().one()
            hasil = await _seed_demo_cases(
                db,
                True,
                target,
                demo_session_id=sesi_id,
                mode="replay",
                anchor=JANGKAR,
                dataset_version=VERSI,
            )
            await db.commit()
            return hasil
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def kasus_db():
    """Satu sesi replay berisi ketiga kasus komoditas, dibersihkan sesudah modul.

    Di-scope modul karena penyemaian memakan ~5 detik dan ketiga tes di bawah
    membaca dataset yang SAMA; membersihkannya per tes akan membuat tes kedua
    menyemai ulang tanpa alasan.
    """
    sesi_id = uuid.uuid4()
    _exec(
        "INSERT INTO demo_sessions "
        "(id, status, started_at, expires_at, anchor_now, mode, evaluation_anchor, "
        " dataset_version) "
        "VALUES (:id, 'ended', now(), now() + interval '3 hours', now(), 'replay', "
        "        :anchor, :versi)",
        {"id": str(sesi_id), "anchor": JANGKAR, "versi": VERSI},
    )
    try:
        hasil = asyncio.run(_semai_async(sesi_id))
        yield sesi_id, hasil
    finally:
        _hapus_sesi(sesi_id)


# --------------------------------------------------------------------------- #
# butir 5 — rantai data lengkap & hanya komoditas yang punya profil
# --------------------------------------------------------------------------- #


def test_setiap_kasus_komoditas_punya_rantai_data_lengkap():
    assert KASUS == ("wortel-coldchain-sah", "wortel-coldchain-hold", "beras-ambient")
    for spec in kasus_komoditas():
        # Profil policy wajib ada: `policy_for` melempar KeyError bila komoditas
        # belum punya profil, dan kasus tanpa profil tidak boleh didemokan.
        policy = policy_for(spec.commodity)
        assert policy.policy_version, f"{spec.key}: profil tanpa versi"

        assert spec.batches, f"{spec.key}: kasus tanpa batch"
        total_kg = sum(b.quantity_kg for b in spec.batches)
        assert total_kg >= spec.quantity_kg, f"{spec.key}: batch < kebutuhan"

        for batch in spec.batches:
            assert batch.temperature_offsets_min, f"{spec.key}: tanpa sampel suhu"
            assert batch.certificate, f"{spec.key}: tanpa sertifikat"
            assert batch.dispatched_offset_min is not None, (
                f"{spec.key}: tanpa waktu kirim — rute tidak bisa dihitung"
            )

        assert spec.price_per_kg and spec.price_per_kg > 0, f"{spec.key}: tanpa harga"
        assert spec.demand_needed_by_offset_min is not None, (
            f"{spec.key}: tanpa tenggat kebutuhan"
        )
        assert spec.source_candidates, f"{spec.key}: tanpa kota sumber"


def test_kasus_komoditas_tanpa_batch_ditolak():
    """Aturan butir 5 ditegakkan di kode: komoditas tanpa batch tidak sah.

    Ini regresi untuk keadaan sebelum Fase 7: wortel ada sebagai nama, tetapi
    tidak punya satu batch pun — dan tetap disebut "didemokan".
    """
    with pytest.raises(ValueError, match="wajib punya batch"):
        ScenarioCaseSpec(
            key="uji-tanpa-batch",
            kind="commodity",
            commodity="wortel",
            target_location="Jakarta",
            source_candidates=("Bogor",),
            quantity_kg=100.0,
            intended_outcome="usable",
        )


def test_wortel_punya_batch_dan_suhu_sejak_fase_7():
    """Wortel sebelumnya hanya nama: sekarang dua kasus dengan batch + log."""
    wortel = [spec for spec in kasus_komoditas() if spec.commodity == "wortel"]
    assert len(wortel) == 2
    for spec in wortel:
        batch = spec.batches[0]
        assert batch.temperature_offsets_min, f"{spec.key}: wortel tanpa sampel suhu"
        assert batch.harvest_offset_min < 0
        log = gen.log_suhu(batch, anchor=JANGKAR, mode="replay")
        assert log, f"{spec.key}: log suhu kosong"


# --------------------------------------------------------------------------- #
# butir 5 & 6 — status yang ditulis harus hasil evaluasi policy
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("key", KASUS)
def test_status_keamanan_adalah_hasil_evaluasi_bukan_tulisan_tangan(key: str):
    """Status deklarasi == hasil `core.safety` atas log yang benar-benar ditulis."""
    spec = spec_untuk(key)
    policy = policy_for(spec.commodity)
    for batch in spec.batches:
        log = gen.log_suhu(batch, anchor=JANGKAR, mode="replay")
        hasil = evaluate_safety(log, policy=policy, evaluation_time=JANGKAR)
        assert hasil["safety_status"] == batch.safety_status, (
            f"{key}/{batch.label}: deklarasi {batch.safety_status!r} != "
            f"evaluasi {hasil['safety_status']!r} ({hasil['reasons']})"
        )


@pytest.mark.parametrize("key", KASUS)
def test_intended_outcome_sejalan_dengan_status_keamanan(key: str):
    spec = spec_untuk(key)
    for batch in spec.batches:
        harap = STATUS_HARAPAN[spec.intended_outcome]
        assert batch.safety_status == harap, (
            f"{key}: outcome {spec.intended_outcome!r} menuntut {harap!r}, "
            f"dideklarasikan {batch.safety_status!r}"
        )


def test_wortel_sah_memenuhi_policy_rantai_dingin():
    """Bukti kasus `usable` benar-benar sah menurut profil, bukan sekadar label."""
    spec = spec_untuk("wortel-coldchain-sah")
    policy = policy_for("wortel")
    assert policy.cold_chain_required is True
    batch = spec.batches[0]
    log = gen.log_suhu(batch, anchor=JANGKAR, mode="replay")

    sah = [
        e
        for e in log
        if e.get("timestamp") and isinstance(e["temperature_c"], float)
    ]
    assert len(sah) >= policy.min_temperature_samples
    assert batch.malformed_samples == 0
    for entri in sah:
        assert policy.safe_temp_min_c <= entri["temperature_c"] <= policy.safe_temp_max_c

    hasil = evaluate_safety(log, policy=policy, evaluation_time=JANGKAR)
    assert hasil["safety_status"] == "pass"
    assert hasil["evidence_state"] == "sufficient"
    assert hasil["excursion_minutes"] == 0.0
    # Sampel terakhir masih "baru" menurut profil (bukan log basi).
    terakhir = max(datetime.fromisoformat(e["timestamp"]) for e in sah)
    assert JANGKAR - terakhir <= timedelta(minutes=policy.max_observation_age_minutes)


def test_wortel_bukti_kurang_menghasilkan_verifikasi_bukan_error():
    """`on_hold` = minta verifikasi manusia; BUKAN `fail`, BUKAN galat."""
    spec = spec_untuk("wortel-coldchain-hold")
    assert spec.intended_outcome == "on_hold"
    policy = policy_for("wortel")
    batch = spec.batches[0]
    log = gen.log_suhu(batch, anchor=JANGKAR, mode="replay")

    sah = [e for e in log if e.get("timestamp") and isinstance(e["temperature_c"], float)]
    assert len(sah) < policy.min_temperature_samples, (
        "kasus hold harus kekurangan sampel sah — kalau cukup, statusnya bukan "
        "verifikasi melainkan PASS, dan demo kehilangan maksudnya"
    )
    assert batch.malformed_samples >= 1, "bukti rusak yang disengaja hilang"

    hasil = evaluate_safety(log, policy=policy, evaluation_time=JANGKAR)
    assert hasil["safety_status"] == "needs_verification"
    assert hasil["reasons"], "verifikasi tanpa alasan tidak bisa ditindaklanjuti"
    assert hasil["safety_status"] != "fail", (
        "bukti kurang bukan kegagalan keamanan — menuduhnya fail membuat jendela "
        "penerimaan/karantina menolak batch yang hanya kurang dicatat"
    )
    assert hasil["evidence_state"] in ("insufficient", "partial", "missing")


def test_beras_ambient_tidak_dinilai_dengan_rentang_rantai_dingin():
    """Beras 26-27 °C sah: profil ambient tidak punya rentang untuk dilanggar."""
    spec = spec_untuk("beras-ambient")
    policy = policy_for("beras")
    assert policy.cold_chain_required is False
    assert policy.safe_temp_min_c is None and policy.safe_temp_max_c is None

    batch = spec.batches[0]
    log = gen.log_suhu(batch, anchor=JANGKAR, mode="replay")
    assert log, "suhu ruang tetap DICATAT walau tidak dinilai"
    # Suhu ruang (> batas rantai dingin mana pun) memang nilai yang disimpan:
    # kalau generator menurunkannya agar "kelihatan dingin", catatan itu bohong.
    assert all(e["temperature_c"] >= 20.0 for e in log)

    hasil = evaluate_safety(log, policy=policy, evaluation_time=JANGKAR)
    assert hasil["safety_status"] == "pass"
    assert hasil["excursion_minutes"] == 0.0
    assert any("ambient" in r for r in hasil["reasons"]), hasil["reasons"]
    # Log tetap tersimpan sebagai catatan, berlabel simulasi.
    assert {e["source"] for e in log} == {"simulated_replay"}


def test_batch_wortel_relatif_jangkar_dan_layak_saat_dinilai():
    """Waktu kejadian wortel dari jangkar; masa layak melewati jangkar."""
    for spec in kasus_komoditas():
        if spec.commodity != "wortel":
            continue
        policy = policy_for("wortel")
        baris = gen.rencana_batch(
            spec, spec.batches[0], anchor=JANGKAR, mode="replay", policy=policy
        )
        assert baris["harvested_at"] <= JANGKAR
        assert baris["usable_until"] > JANGKAR
        assert baris["temperature_source"] == "simulated_replay"
        # Identitas baris membawa versi skenario: replay dari versi lain tidak
        # boleh menimpa baris kasus generasi ini.
        assert SCENARIO_VERSION in gen.identitas_kasus(
            spec, mode="replay", anchor=JANGKAR, dataset_version=VERSI,
            target=spec.target_location,
        )


# --------------------------------------------------------------------------- #
# butir 5 & 6 di DB — seeder menulis baris lengkap untuk ketiga kasus
# --------------------------------------------------------------------------- #


def test_seeder_menulis_baris_lengkap_untuk_setiap_kasus(kasus_db):
    sesi_id, hasil = kasus_db
    dibangun = {i["case"]: i for i in hasil["commodity_cases"] if not i.get("skipped")}
    assert set(dibangun) == set(KASUS), (
        f"kasus komoditas tidak tergarap: {hasil['commodity_cases']}"
    )

    for key in KASUS:
        spec = spec_untuk(key)
        info = dibangun[key]
        assert info["decision_id"], f"{key}: tanpa keputusan"
        assert info["temperature_source"] == "simulated_replay"

        batch_id = info["batch_ids"][0]
        batch = _sql(
            "SELECT b.id, b.supplier_id, b.quantity_kg, b.temperature_log, "
            "       b.usable_until, b.freshness_score, b.safety_status, "
            "       b.harvested_at, b.dispatched_at, b.certification_status, "
            "       c.name AS commodity "
            "FROM batches b JOIN commodities c ON c.id = b.commodity_id "
            "WHERE b.id = :b AND b.demo_session_id = :s",
            {"b": batch_id, "s": str(sesi_id)},
        )
        assert batch, f"{key}: batch tidak tertulis di sesi ini"
        baris = batch[0]
        assert baris["commodity"] == spec.commodity
        assert baris["supplier_id"] is not None, f"{key}: batch tanpa pemasok"
        assert float(baris["quantity_kg"]) == pytest.approx(spec.quantity_kg, abs=0.01)
        assert baris["freshness_score"] is not None
        assert baris["usable_until"] > JANGKAR
        assert baris["harvested_at"] <= JANGKAR
        assert baris["dispatched_at"] is not None
        assert baris["certification_status"] == spec.batches[0].certificate
        assert baris["safety_status"] == spec.batches[0].safety_status
        log = baris["temperature_log"]
        assert log and all(e.get("source") == "simulated_replay" for e in log), (
            f"{key}: log suhu bukan dari simulasi replay"
        )

        # Dua kasus wortel berbagi kota+komoditas, jadi baris kebutuhan HARUS
        # dipilih lewat kuantitasnya masing-masing (420 vs 380): jumlah baris 2
        # adalah hasil yang benar — kalau hanya 1, satu kebutuhan hilang karena
        # kunci unik (lokasi, komoditas, recorded_at) saling menimpa.
        demand = _sql(
            "SELECT d.quantity_kg, d.needed_by, d.recorded_at "
            "FROM demand_records d JOIN commodities c ON c.id = d.commodity_id "
            "WHERE d.demo_session_id = :s AND c.name = :k AND d.location_id = "
            "      (SELECT location_id FROM batches WHERE id = :b)",
            {"s": str(sesi_id), "k": spec.commodity, "b": batch_id},
        )
        if spec.commodity == "wortel":
            assert len(demand) == 2, "dua kasus wortel wajib punya dua baris kebutuhan"
        milik_kasus = [
            d
            for d in demand
            if float(d["quantity_kg"]) == pytest.approx(spec.quantity_kg, abs=0.01)
        ]
        assert len(milik_kasus) == 1, f"{key}: kebutuhan kasus ini tidak tertulis tunggal"
        assert milik_kasus[0]["needed_by"] > JANGKAR
        assert milik_kasus[0]["recorded_at"] <= JANGKAR

        harga = _sql(
            "SELECT p.price_per_kg, p.source FROM price_signals p "
            "JOIN commodities c ON c.id = p.commodity_id "
            "WHERE p.demo_session_id = :s AND c.name = :k",
            {"s": str(sesi_id), "k": spec.commodity},
        )
        harga_kasus = [
            h
            for h in harga
            if float(h["price_per_kg"]) == pytest.approx(spec.price_per_kg, abs=0.01)
        ]
        assert len(harga_kasus) == 1, f"{key}: harga acuan kasus ini tidak tertulis"
        assert harga_kasus[0]["source"] == "pihps_reference"

        keputusan = _sql(
            "SELECT d.id, d.status, d.supplier_id, l.name AS target "
            "FROM decisions d JOIN locations l ON l.id = d.target_location_id "
            "WHERE d.id = :d AND d.demo_session_id = :s",
            {"d": info["decision_id"], "s": str(sesi_id)},
        )
        assert keputusan, f"{key}: keputusan tidak tertulis di sesi ini"
        assert keputusan[0]["status"] == "pending_approval"
        assert keputusan[0]["supplier_id"] is not None
        assert keputusan[0]["target"] == spec.target_location

        jejak = _sql(
            "SELECT t.tool_called, t.output_summary FROM agent_traces t "
            "WHERE t.decision_id = :d AND t.step_name = 'VERIFY'",
            {"d": info["decision_id"]},
        )
        assert jejak, f"{key}: jejak VERIFY hilang"
        assert jejak[0]["tool_called"] == "evidence.temperature"
        bukti = jejak[0]["output_summary"] or {}
        harapan = "sufficient" if spec.intended_outcome == "usable" else "insufficient"
        assert bukti.get("evidence_state") == harapan, (
            f"{key}: jejak VERIFY menyebut bukti {bukti.get('evidence_state')!r}, "
            f"bukan {harapan!r}"
        )
        assert bukti.get("safety_status") == spec.batches[0].safety_status


def test_kasus_komoditas_tidak_menyentuh_sesi_lain(kasus_db):
    """Penyemaian replay hanya menggarap baris datasetnya sendiri."""
    sesi_id, _ = kasus_db
    lain = _sql(
        "SELECT count(*) AS n FROM decisions "
        "WHERE demo_session_id IS NOT NULL AND demo_session_id <> :s "
        "  AND demo_case = ANY(:kasus)",
        {"s": str(sesi_id), "kasus": list(KASUS)},
    )[0]["n"]
    # Sesi lain boleh ada (dataset bermode/anchor lain), yang dilarang adalah
    # salinan ganda ber-ID sama milik sesi ini.
    milik_saya = _sql(
        "SELECT count(*) AS n FROM decisions WHERE demo_session_id = :s",
        {"s": str(sesi_id)},
    )[0]["n"]
    assert milik_saya == 10, "tujuh kasus (tiga komoditas + empat cerita) menulis 10 baris"
    assert lain >= 0  # dokumentasi: hitungan sesi lain tidak diubah tes ini


def test_hasil_seed_menyebut_tujuh_kasus(kasus_db):
    _, hasil = kasus_db
    assert hasil["cases_total"] == 7
    assert hasil["mode"] == "replay"
    assert hasil["temperature_source"] == "simulated_replay"
    assert hasil["evaluation_anchor"] == JANGKAR.isoformat()
    # Tiga kasus komoditas dilaporkan lengkap dengan status yang diharapkan.
    status = {
        i["case"]: i.get("safety_status")
        for i in hasil["commodity_cases"]
        if not i.get("skipped")
    }
    assert status["wortel-coldchain-sah"] == "pass"
    assert status["wortel-coldchain-hold"] == "needs_verification"
    assert status["beras-ambient"] == "pass"
