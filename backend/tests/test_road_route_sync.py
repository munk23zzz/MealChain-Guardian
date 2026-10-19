"""Sinkronisasi rute jalan ke cache `road_routes` — TDD RED dulu.

Yang dijaga di sini:
- **Tidak ada panggilan jaringan di suite.** `fetcher` disuntikkan; fixture
  respons OSRM nyata dipakai apa adanya (`tests/fixtures/`).
- **Tidak menyentuh kunci cache asli.** Tes memakai koordinat karangan
  (0.x) yang tidak mungkin bertabrakan dengan pemasok/lokasi demo, dan
  membersihkannya lagi di akhir — kalau tes menulis di kunci asli, geometri
  uji bisa tertinggal dan demo menampilkan jarak palsu.
- **Kegagalan dilaporkan, bukan diganti garis karangan.** OSRM mati atau
  menjawab NoRoute → ada baris gagal + alasan, dan cache TIDAK bertambah.
"""

import asyncio
import json
import urllib.error
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.road_route import (
    ALASAN_LAYANAN_TIDAK_TERJANGKAU,
    ALASAN_RUTE_TIDAK_DITEMUKAN,
)
from app.db import create_engine, create_session_maker
from app.seed.road_routes import batch_route_rows, sync_requests, sync_road_routes

DB_URL = "postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain"
FIXTURE = Path(__file__).parent / "fixtures" / "osrm_cianjur_jakarta.json"

# Koordinat karangan jauh dari data demo (Indonesia) supaya tidak bertabrakan.
FAKE_A = {"origin_lat": 0.1, "origin_lon": 0.1, "destination_lat": 0.9, "destination_lon": 0.9}
FAKE_B = {"origin_lat": 0.2, "origin_lon": 0.2, "destination_lat": 0.9, "destination_lon": 0.9}
KUNCI_UJI_PREFIKS = "driving:0."

# Tanggal uji: harus > usable_until kiriman modern & < usable_until kiriman aktif
NOW_UJI = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)


@asynccontextmanager
async def _sesi():
    engine = create_engine(DB_URL)
    maker = create_session_maker(engine)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _bersihkan(db) -> None:
    await db.execute(
        text("DELETE FROM road_routes WHERE route_key LIKE :p"), {"p": f"{KUNCI_UJI_PREFIKS}%"}
    )
    await db.commit()


def _fetcher_fixture(url: str):
    """Fetcher uji: selalu jawab dengan respons OSRM nyata yang sudah direkam."""
    return json.loads(FIXTURE.read_text())


def _fetcher_gagal(url: str):
    raise urllib.error.URLError("jaringan mati (uji)")


def _fetcher_noroute(url: str):
    return {"code": "NoRoute", "routes": []}


def test_permintaan_unik_dan_koordinat_kosong_dilewati():
    """Baris tanpa koordinat dilewati; baris satu asal→tujuan menghasilkan kunci sama.

    Dedup-nya sendiri bukan tugas fungsi ini — itu `plan_route_sync` (sudah diuji
    di `test_road_route.py`); di sini cukup dibuktikan kuncinya identik.
    """
    rows = [
        {**FAKE_A, "supplier_name": "A", "batch_id": "b1"},
        {**FAKE_A, "supplier_name": "A lagi", "batch_id": "b2"},
        {**FAKE_B, "supplier_name": "B", "batch_id": "b3"},
        {"origin_lat": None, "origin_lon": None, "destination_lat": 0.9, "destination_lon": 0.9},
    ]
    hasil = sync_requests(rows)
    assert len(hasil) == 3
    kunci = [r["key"] for r in hasil]
    assert kunci[0] == kunci[1]
    assert kunci[2] != kunci[0]


def test_sinkronisasi_mengisi_cache_dari_respons_nyata():
    async def _kasus():
        async with _sesi() as db:
            await _bersihkan(db)
            try:
                laporan = await sync_road_routes(
                    db, now=NOW_UJI, fetcher=_fetcher_fixture, rows=[dict(FAKE_A)]
                )
                assert laporan["diambil"] == 1
                assert laporan["gagal"] == 0
                baris = (
                    await db.execute(
                        text(
                            "SELECT distance_m, duration_s, source, geometry "
                            "FROM road_routes WHERE route_key LIKE :p"
                        ),
                        {"p": f"{KUNCI_UJI_PREFIKS}%"},
                    )
                ).all()
                assert len(baris) == 1
                distance_m, duration_s, source, geometry = baris[0]
                assert distance_m == 111230
                assert duration_s == 5126
                assert source == "osrm"
                assert len(geometry["coordinates"]) == 36
            finally:
                await _bersihkan(db)

    asyncio.run(_kasus())


def test_sinkronisasi_idempoten_tidak_menggandakan():
    async def _kasus():
        async with _sesi() as db:
            await _bersihkan(db)
            try:
                pertama = await sync_road_routes(
                    db, now=NOW_UJI, fetcher=_fetcher_fixture, rows=[dict(FAKE_A)]
                )
                kedua = await sync_road_routes(
                    db, now=NOW_UJI, fetcher=_fetcher_fixture, rows=[dict(FAKE_A)]
                )
                assert pertama["diambil"] == 1
                assert kedua["diambil"] == 0
                assert kedua["sudah_ada"] == 1
                jumlah = (
                    await db.execute(
                        text("SELECT count(*) FROM road_routes WHERE route_key LIKE :p"),
                        {"p": f"{KUNCI_UJI_PREFIKS}%"},
                    )
                ).scalar_one()
                assert jumlah == 1
            finally:
                await _bersihkan(db)

    asyncio.run(_kasus())


def test_dedup_dua_batch_satu_rute_hanya_satu_panggilan():
    dipanggil: list[str] = []

    def _fetcher_catat(url: str):
        dipanggil.append(url)
        return json.loads(FIXTURE.read_text())

    async def _kasus():
        async with _sesi() as db:
            await _bersihkan(db)
            try:
                laporan = await sync_road_routes(
                    db,
                    now=NOW_UJI,
                    fetcher=_fetcher_catat,
                    rows=[dict(FAKE_A, batch_id="b1"), dict(FAKE_A, batch_id="b2")],
                )
                assert len(dipanggil) == 1  # satu panggilan untuk dua batch
                assert laporan["diperiksa"] == 2
                assert laporan["duplikat"] == 1
                assert laporan["diambil"] == 1
            finally:
                await _bersihkan(db)

    asyncio.run(_kasus())


def test_jaringan_mati_dilaporkan_dan_cache_tidak_diisi():
    async def _kasus():
        async with _sesi() as db:
            await _bersihkan(db)
            try:
                laporan = await sync_road_routes(
                    db, now=NOW_UJI, fetcher=_fetcher_gagal, rows=[dict(FAKE_A)]
                )
                assert laporan["diambil"] == 0
                assert laporan["gagal"] == 1
                assert laporan["alasan_gagal"] == {ALASAN_LAYANAN_TIDAK_TERJANGKAU: 1}
                assert laporan["rincian_gagal"][0]["alasan"] == ALASAN_LAYANAN_TIDAK_TERJANGKAU
                jumlah = (
                    await db.execute(
                        text("SELECT count(*) FROM road_routes WHERE route_key LIKE :p"),
                        {"p": f"{KUNCI_UJI_PREFIKS}%"},
                    )
                ).scalar_one()
                assert jumlah == 0  # TIDAK ada geometri karangan
            finally:
                await _bersihkan(db)

    asyncio.run(_kasus())


def test_respons_noroute_dilaporkan_bukan_digambar():
    async def _kasus():
        async with _sesi() as db:
            await _bersihkan(db)
            try:
                laporan = await sync_road_routes(
                    db, now=NOW_UJI, fetcher=_fetcher_noroute, rows=[dict(FAKE_A)]
                )
                assert laporan["diambil"] == 0
                assert laporan["alasan_gagal"] == {ALASAN_RUTE_TIDAK_DITEMUKAN: 1}
            finally:
                await _bersihkan(db)

    asyncio.run(_kasus())


def test_baris_batch_aktif_hanya_yang_masih_layak():
    async def _kasus():
        async with _sesi() as db:
            rows = await batch_route_rows(db, NOW_UJI)
        assert rows, "harus ada kiriman aktif pada 2026-10-16"
        assert all(r["usable_until"] is not None for r in rows)
        assert all(r["usable_until"] >= NOW_UJI for r in rows)
        # kiriman kanonik ke Jakarta (ditambahkan Fase 10 atas keputusan pemilik)
        tujuan = {r["destination_name"] for r in rows}
        assert "Jakarta" in tujuan
        # Kedaluwarsa tidak ikut — diuji PER BATCH, bukan per kota. Sejak beras
        # (umur simpan 180 hari) ada di semua hub, tidak ada lagi kota yang
        # seluruh batch-nya basi, jadi "kota X tidak muncul" bukan invarian.
        semua = await batch_route_rows(db, NOW_UJI, semua_batch=True)
        aktif = {r["batch_id"] for r in rows}
        gugur = [r for r in semua if r["batch_id"] not in aktif]
        assert gugur, "prasyarat: ada batch yang sudah lewat masa layak"
        assert all(r["usable_until"] < NOW_UJI for r in gugur)

    asyncio.run(_kasus())


@pytest.mark.parametrize("semua", [True, False])
def test_baris_batch_memuat_koordinat_dua_ujung(semua: bool):
    async def _kasus():
        async with _sesi() as db:
            rows = await batch_route_rows(db, NOW_UJI, semua_batch=semua)
        for r in rows:
            assert r["origin_lat"] is not None and r["origin_lon"] is not None
            assert r["destination_lat"] is not None and r["destination_lon"] is not None

    asyncio.run(_kasus())
