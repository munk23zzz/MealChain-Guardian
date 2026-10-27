"""Alur demo replay vs realtime (Fase 7 MG butir 1, 2, 3).

Sebelum Fase 7, kasus demo ditulis dengan `datetime.now()` dan `gen_random_uuid`:
dua pembuatan dataset yang sama menghasilkan baris berbeda, jangkar sesi hanya
label di layar, dan dua sesi realtime tidak bisa dibedakan dari datanya.

Berkas ini menguji janji yang sekarang dijaga `services.scenario_generator`
lewat jalur NYATA `api.demo._seed_demo_cases` (bukan fungsi generator saja):

1. replay identik: dua pembuatan pada sesi replay menghasilkan ID, jumlah, dan
   waktu evaluasi yang sama, tanpa duplikasi;
2. realtime berbeda dari replay, dan semua waktu KEJADIAN simulasi berada pada
   offset dari jangkar sesi (tidak di masa depan relatif jangkar);
3. dua sesi realtime tidak saling menghapus: reset sesi pertama tidak mengubah
   keputusan/batch/fakta sesi kedua;
4. waktu AKSI operator (jendela persetujuan) tetap jam dinding — kartu replay
   tidak lahir dalam keadaan kedaluwarsa.

DB: mengikuti `DATABASE_URL` proses tes (jalur gerbang memakai klon). Baris yang
dibuat berkas ini dibersihkan di `finally` per sesi uji.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.demo import DEMO_CASES, _seed_demo_cases
from app.models import Location
from tests.dsn import DSN_ASYNC, DSN_SYNC

JANGKAR_REPLAY = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
JANGKAR_REALTIME_A = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
JANGKAR_REALTIME_B = datetime(2026, 10, 27, 4, 30, tzinfo=timezone.utc)
KASUS_KOMODITAS = ("wortel-coldchain-sah", "wortel-coldchain-hold", "beras-ambient")
SEMUA_KASUS = DEMO_CASES + KASUS_KOMODITAS


# --------------------------------------------------------------------------- #
# helper
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


def _buat_sesi(*, mode: str, anchor: datetime, status: str = "ended") -> uuid.UUID:
    """Sesi demo dengan jangkar tertentu (tanpa membangun seluruh template)."""
    sesi_id = uuid.uuid4()
    versi = (
        f"realtime-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%S}Z"
        if mode == "realtime"
        else "kanon-2026-10-08T12:00:00Z"
    )
    _exec(
        "INSERT INTO demo_sessions "
        "(id, status, started_at, expires_at, anchor_now, mode, evaluation_anchor, "
        " dataset_version) "
        "VALUES (:id, :status, now(), now() + interval '3 hours', now(), :mode, "
        "        :anchor, :versi)",
        {
            "id": str(sesi_id),
            "status": status,
            "mode": mode,
            "anchor": anchor,
            "versi": versi,
        },
    )
    return sesi_id


def _hapus_sesi(sesi_id: uuid.UUID) -> None:
    """Hapus baris sesi + semua baris miliknya (urutan FK)."""
    _exec(
        "DELETE FROM demand_records WHERE demo_session_id = :s", {"s": str(sesi_id)}
    )
    _exec(
        "DELETE FROM price_signals WHERE demo_session_id = :s", {"s": str(sesi_id)}
    )
    _exec("DELETE FROM batches WHERE demo_session_id = :s", {"s": str(sesi_id)})
    _exec("DELETE FROM decisions WHERE demo_session_id = :s", {"s": str(sesi_id)})
    _exec("DELETE FROM demo_sessions WHERE id = :s", {"s": str(sesi_id)})


def _semai(sesi_id: uuid.UUID, *, mode: str, anchor: datetime) -> dict:
    """Jalankan `_seed_demo_cases` untuk sesi itu, seperti `/demo/seed`.

    Tes lain di repo ini sinkron (TestClient + engine sinkron), jadi jalur async
    dijalankan lewat `asyncio.run` di sini — bukan `pytest.mark.asyncio`, yang
    akan menuntut seluruh berkas pindah ke gaya async.
    """
    return asyncio.run(_semai_async(sesi_id, mode=mode, anchor=anchor))


async def _semai_async(sesi_id: uuid.UUID, *, mode: str, anchor: datetime) -> dict:
    """Jalankan `_seed_demo_cases` untuk sesi itu, seperti `/demo/seed`."""
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
            versi = (
                f"realtime-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%S}Z"
                if mode == "realtime"
                else "kanon-2026-10-08T12:00:00Z"
            )
            hasil = await _seed_demo_cases(
                db,
                True,
                target,
                demo_session_id=sesi_id,
                mode=mode,
                anchor=anchor,
                dataset_version=versi,
            )
            await db.commit()
            return hasil
    finally:
        await engine.dispose()


def _keputusan(sesi_id: uuid.UUID) -> list[dict]:
    return _sql(
        "SELECT id, demo_case, iteration, status, generated_at, created_at, expires_at "
        "FROM decisions WHERE demo_session_id = :s AND demo_case = ANY(:kasus) "
        "ORDER BY demo_case, iteration",
        {"s": str(sesi_id), "kasus": list(SEMUA_KASUS)},
    )


def _jejak(sesi_id: uuid.UUID) -> list[dict]:
    return _sql(
        "SELECT t.id, t.step_name, t.step_at FROM agent_traces t "
        "JOIN decisions d ON d.id = t.decision_id "
        "WHERE d.demo_session_id = :s AND d.demo_case = ANY(:kasus) "
        "ORDER BY t.step_at",
        {"s": str(sesi_id), "kasus": list(SEMUA_KASUS)},
    )


def _batch(sesi_id: uuid.UUID) -> list[dict]:
    return _sql(
        "SELECT id, commodity_id, safety_status, harvested_at, usable_until, "
        "temperature_log, freshness_score FROM batches WHERE demo_session_id = :s "
        "ORDER BY id",
        {"s": str(sesi_id)},
    )


@pytest.fixture()
def sesi_ids():
    dibuat: list[uuid.UUID] = []
    yield dibuat
    for sesi_id in dibuat:
        _hapus_sesi(sesi_id)


# --------------------------------------------------------------------------- #
# butir 1 — replay identik
# --------------------------------------------------------------------------- #


def test_replay_dua_kali_menghasilkan_baris_sama_tanpa_duplikasi(sesi_ids):
    sesi = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    sesi_ids.append(sesi)

    pertama = _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)
    baris1 = _keputusan(sesi)
    jejak1 = _jejak(sesi)
    batch1 = _batch(sesi)

    kedua = _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)
    baris2 = _keputusan(sesi)
    jejak2 = _jejak(sesi)
    batch2 = _batch(sesi)

    assert pertama["mode"] == kedua["mode"] == "replay"
    assert pertama["evaluation_anchor"] == JANGKAR_REPLAY.isoformat()
    assert pertama["cases_total"] == kedua["cases_total"] == 7

    # ID sama: baris ditimpa, bukan digandakan.
    assert [b["id"] for b in baris1] == [b["id"] for b in baris2]
    # Tujuh KASUS, sepuluh BARIS keputusan: tiga kasus cerita memang berulang
    # (rejection-loop 3 iterasi, gangguan-logistik 2) — jumlah baris bukan
    # jumlah kasus, dan tes ini tidak boleh menyamakan keduanya.
    assert {b["demo_case"] for b in baris1} == set(SEMUA_KASUS)
    assert len(baris1) == len(baris2) == 10
    # Waktu kejadian sama (ini inti "replay dapat diulang").
    assert [b["generated_at"] for b in baris1] == [b["generated_at"] for b in baris2]
    # Jumlah jejak dan batch tidak bertambah antar-run.
    assert len(jejak1) == len(jejak2)
    assert len(batch1) == len(batch2) == 3
    assert len({b["id"] for b in batch1}) == 3


def test_replay_tidak_menyentuh_jumlah_baris_kanonik(sesi_ids):
    """Seed replay hanya menambah/menimpa baris MILIK sesi itu."""
    sebelum = _sql(
        "SELECT count(*) AS n FROM decisions WHERE demo_session_id IS NULL"
    )[0]["n"]
    sesi = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    sesi_ids.append(sesi)
    _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)
    sesudah = _sql(
        "SELECT count(*) AS n FROM decisions WHERE demo_session_id IS NULL"
    )[0]["n"]
    assert sebelum == sesudah


# --------------------------------------------------------------------------- #
# butir 2 — realtime berbeda dari replay, waktu dari jangkar
# --------------------------------------------------------------------------- #


def test_realtime_berbeda_dari_replay(sesi_ids):
    replay = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    realtime = _buat_sesi(mode="realtime", anchor=JANGKAR_REALTIME_A)
    sesi_ids.extend([replay, realtime])

    hasil_replay = _semai(replay, mode="replay", anchor=JANGKAR_REPLAY)
    hasil_realtime = _semai(realtime, mode="realtime", anchor=JANGKAR_REALTIME_A)

    assert hasil_realtime["evaluation_anchor"] != hasil_replay["evaluation_anchor"]
    assert hasil_realtime["evaluation_anchor"] == JANGKAR_REALTIME_A.isoformat()
    assert hasil_realtime["temperature_source"] == "simulated_realtime"

    id_replay = {b["id"] for b in _keputusan(replay)}
    id_realtime = {b["id"] for b in _keputusan(realtime)}
    assert id_replay.isdisjoint(id_realtime)


def test_waktu_kejadian_simulasi_relatif_jangkar_dan_tidak_di_masa_depan(sesi_ids):
    sesi = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    sesi_ids.append(sesi)
    _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)

    for baris in _keputusan(sesi):
        assert baris["generated_at"] <= JANGKAR_REPLAY, (
            f"{baris['demo_case']} v{baris['iteration']} lahir di masa depan relatif jangkar"
        )
        assert JANGKAR_REPLAY - baris["generated_at"] <= timedelta(days=1)

    for jejak in _jejak(sesi):
        assert jejak["step_at"] <= JANGKAR_REPLAY
        assert JANGKAR_REPLAY - jejak["step_at"] <= timedelta(days=1)

    for batch in _batch(sesi):
        assert batch["harvested_at"] <= JANGKAR_REPLAY
        assert batch["usable_until"] > JANGKAR_REPLAY
        for entri in batch["temperature_log"]:
            assert entri["source"] in ("simulated_replay", "simulated_realtime")
            if entri.get("timestamp"):
                stempel = datetime.fromisoformat(entri["timestamp"])
                assert stempel <= JANGKAR_REPLAY


def test_tenggat_kebutuhan_setelah_jangkar_dan_sebelum_masa_layak(sesi_ids):
    sesi = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    sesi_ids.append(sesi)
    _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)

    baris = _sql(
        "SELECT needed_by, recorded_at, quantity_kg FROM demand_records "
        "WHERE demo_session_id = :s",
        {"s": str(sesi)},
    )
    assert len(baris) == 3, "tiga kasus komoditas masing-masing punya satu kebutuhan"
    # Kedua kasus wortel harus PUNYA barisnya sendiri: kalau recorded_at-nya
    # sama, unik (lokasi, komoditas, recorded_at) menimpa yang pertama dan
    # kebutuhan 420 kg hilang tanpa galat apa pun.
    assert sorted(float(d["quantity_kg"]) for d in baris) == [380.0, 420.0, 600.0]
    for demand in baris:
        assert demand["needed_by"] > JANGKAR_REPLAY
        assert demand["recorded_at"] <= JANGKAR_REPLAY


def test_jendela_aksi_operator_tetap_jam_dinding(sesi_ids):
    """Kartu replay boleh bertanggal 8 Okt, tetapi TIDAK lahir kedaluwarsa."""
    sesi = _buat_sesi(mode="replay", anchor=JANGKAR_REPLAY)
    sesi_ids.append(sesi)
    _semai(sesi, mode="replay", anchor=JANGKAR_REPLAY)

    sekarang = datetime.now(timezone.utc)
    pending = [b for b in _keputusan(sesi) if b["status"] == "pending_approval"]
    assert pending, "seed harus menyisakan kartu untuk disetujui"
    for baris in pending:
        assert baris["expires_at"] > sekarang, (
            f"{baris['demo_case']} kedaluwarsa sejak lahir — jendela aksi harus jam dinding"
        )
        assert baris["created_at"] >= sekarang - timedelta(minutes=5)


# --------------------------------------------------------------------------- #
# butir 3 — dua sesi realtime
# --------------------------------------------------------------------------- #


def test_reset_satu_sesi_tidak_mengubah_sesi_lain(sesi_ids):
    sesi_a = _buat_sesi(mode="realtime", anchor=JANGKAR_REALTIME_A)
    sesi_b = _buat_sesi(mode="realtime", anchor=JANGKAR_REALTIME_B)
    sesi_ids.extend([sesi_a, sesi_b])

    _semai(sesi_a, mode="realtime", anchor=JANGKAR_REALTIME_A)
    _semai(sesi_b, mode="realtime", anchor=JANGKAR_REALTIME_B)

    id_b = {b["id"] for b in _keputusan(sesi_b)}
    batch_b = {b["id"] for b in _batch(sesi_b)}
    demand_b = {
        r["id"]
        for r in _sql(
            "SELECT id FROM demand_records WHERE demo_session_id = :s",
            {"s": str(sesi_b)},
        )
    }
    assert id_b and batch_b and demand_b

    # Reset sesi A (force=True) — persis yang dilakukan tombol "Muat Demo".
    _semai(sesi_a, mode="realtime", anchor=JANGKAR_REALTIME_A)

    assert {b["id"] for b in _keputusan(sesi_b)} == id_b
    assert {b["id"] for b in _batch(sesi_b)} == batch_b
    assert {
        r["id"]
        for r in _sql(
            "SELECT id FROM demand_records WHERE demo_session_id = :s",
            {"s": str(sesi_b)},
        )
    } == demand_b

    # Dan fakta sesi B tetap konsisten dengan jangkarnya sendiri.
    for baris in _keputusan(sesi_b):
        assert baris["generated_at"] <= JANGKAR_REALTIME_B
