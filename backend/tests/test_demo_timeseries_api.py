"""Endpoint data & rentang waktu (Fase 4): `/demo/preview`, `/demo/timeseries`,
`/demo/timeseries/purge`.

Yang dibuktikan lewat HTTP, bukan cuma lewat modul:

1. Pratinjau tidak menulis apa pun.
2. Membangun deret waktu **tidak menggeser jangkar**: setelah generate,
   `/balance/map` masih 4.900 kg dengan 3 surplus : 7 shortage dan
   `/supply/Cianjur/telur` masih 1.400 kg.
3. Idempoten: panggilan kedua menambah 0 baris.
4. Purge hanya menghapus `origin='demo'`.
5. Rentang ngawur ditolak 422; peran pemantau (bgn_monitor) ditolak 403.
"""

import asyncio
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.seed.seed_data import load_seed
from app.seed.timeseries import CANONICAL_REF, DEFAULT_END, DEFAULT_START, purge_demo_rows

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
TABLES = ("supply_records", "price_signals", "menu_plans")


def _counts() -> dict[str, int]:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return {
                f"{t}:{o}": int(
                    conn.execute(
                        text(f"SELECT count(*) FROM {t} WHERE origin = :o"), {"o": o}
                    ).scalar()
                    or 0
                )
                for t in TABLES
                for o in ("seed", "demo")
            }
    finally:
        engine.dispose()


def _teardown_counts(before: dict[str, int], client, headers: dict) -> None:
    """Kembalikan DB: ada baris demo sebelumnya → bangun ulang; kalau tidak → bersihkan."""
    if any(v for k, v in before.items() if k.endswith(":demo")):
        r = client.post("/demo/timeseries", json={"force": False}, headers=headers)
        assert r.status_code == 200, r.text
    else:
        asyncio.run(purge_demo_rows())


@pytest.fixture()
def demo_state(auth_headers):
    """Snapshot baris demo sebelum tes + pengembalian keadaan setelahnya."""
    from fastapi.testclient import TestClient

    from app.main import app

    before = _counts()
    with TestClient(app) as client:
        yield client
        _teardown_counts(before, client, auth_headers)


def _menu_coverage() -> tuple[int, int, int]:
    """(jumlah baris rencana, jumlah tanggal unik, hari tanpa rencana)."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            total = int(conn.execute(text("SELECT count(*) FROM menu_plans")).scalar() or 0)
            tanggal = int(
                conn.execute(text("SELECT count(DISTINCT plan_date) FROM menu_plans")).scalar()
                or 0
            )
            kosong = int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM ("
                        "  SELECT l.id, d::date FROM locations l"
                        f"  CROSS JOIN generate_series(DATE '{DEFAULT_START.date().isoformat()}',"
                        f" DATE '{DEFAULT_END.date().isoformat()}', INTERVAL '1 day') d"
                        "  WHERE NOT EXISTS ("
                        "    SELECT 1 FROM menu_plans m"
                        "    WHERE m.location_id = l.id AND m.plan_date = d::date)"
                        ") x"
                    )
                ).scalar()
                or 0
            )
    finally:
        engine.dispose()
    return total, tanggal, kosong


def test_preview_tidak_menulis(demo_state, auth_headers):
    before = _counts()
    r = demo_state.get("/demo/preview", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["writes"] is False
    assert body["counts"]["supply"]["planned"] > 0
    assert body["range"]["actual_end"] == "2026-10-07T12:00:00+00:00"
    assert _counts() == before


def test_membangun_deret_tidak_menggeser_jangkar(demo_state, auth_headers, monitor_headers):
    r = demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["supply"]["added"] == 2190
    # Rencana menu harus menutup SELURUH rentang tanpa lubang. Angka "520"
    # sempat dipaku di sini dan pecah begitu jumlah hari kanonik berubah —
    # yang benar adalah cakupan, bukan selisih yang bergantung susunan lama.
    assert _menu_coverage() == (660, 66, 0)
    assert body["purged"]["total"] >= 0
    assert set(body["purged"]["deleted"]) == {
        "supply_records",
        "price_signals",
        "menu_plans",
    }

    # Jangkar sisi SUMBER: record terbaru Cianjur telur tetap 1.400 kg.
    sup = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers)
    assert sup.status_code == 200, sup.text
    assert sup.json()["quantity_kg"] == 1400.0
    assert sup.json()["recorded_at"].startswith("2026-10-08T12:00:00")

    # Jangkar peta: total 4.900 kg, 3 surplus : 7 shortage.
    peta = demo_state.get("/balance/map?commodity=telur", headers=monitor_headers)
    assert peta.status_code == 200, peta.text
    lokasi = peta.json()["locations"]
    assert sum(loc["supply_kg"] for loc in lokasi) == 4900.0
    status_count: dict[str, int] = {}
    for loc in lokasi:
        status_count[loc["status"]] = status_count.get(loc["status"], 0) + 1
    assert status_count == {"surplus": 3, "shortage": 7}


def test_idempoten_lewat_http(demo_state, auth_headers):
    demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    kedua = demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat()},
        headers=auth_headers,
    )
    assert kedua.status_code == 200, kedua.text
    for nama in ("supply", "prices", "menu_plans"):
        assert kedua.json()["counts"][nama]["added"] == 0


def test_purge_lewat_http_hanya_demo(demo_state, auth_headers):
    demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    sebelum = _counts()
    r = demo_state.post("/demo/timeseries/purge", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] > 0
    sesudah = _counts()
    for t in TABLES:
        assert sesudah[f"{t}:demo"] == 0
        assert sesudah[f"{t}:seed"] == sebelum[f"{t}:seed"]


def test_rentang_ngawur_ditolak_422(demo_state, auth_headers):
    terbalik = demo_state.post(
        "/demo/timeseries",
        json={
            "start": DEFAULT_END.isoformat(),
            "end": DEFAULT_START.isoformat(),
        },
        headers=auth_headers,
    )
    assert terbalik.status_code == 422
    assert "lebih awal" in terbalik.text

    zaman_batu = demo_state.post(
        "/demo/timeseries",
        json={"start": "2019-01-01T00:00:00+00:00", "end": "2019-02-01T00:00:00+00:00"},
        headers=auth_headers,
    )
    assert zaman_batu.status_code == 422
    assert "di luar batas" in zaman_batu.text

    tanpa_zona = demo_state.get(
        "/demo/preview",
        params={"start": "2026-09-01T00:00:00", "end": "2026-10-01T00:00:00"},
        headers=auth_headers,
    )
    assert tanpa_zona.status_code == 422
    assert "zona waktu" in tanpa_zona.text

    interval_nol = demo_state.get(
        "/demo/preview", params={"interval_hours": 0}, headers=auth_headers
    )
    assert interval_nol.status_code == 422


def test_peran_pemantau_ditolak_403(demo_state, monitor_headers):
    assert demo_state.get("/demo/preview", headers=monitor_headers).status_code == 403
    assert (
        demo_state.post(
            "/demo/timeseries", json={}, headers=monitor_headers
        ).status_code
        == 403
    )
    assert (
        demo_state.post("/demo/timeseries/purge", headers=monitor_headers).status_code
        == 403
    )


def test_performa_66_hari_di_bawah_30_detik(demo_state, auth_headers):
    """Sasaran rencana Fase 4: membangun 66 hari data < 30 detik."""
    mulai = time.perf_counter()
    r = demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    durasi = time.perf_counter() - mulai
    assert r.status_code == 200, r.text
    assert r.json()["counts"]["supply"]["added"] == 2190
    assert durasi < 30, f"generate 66 hari butuh {durasi:.1f}s (batas 30s)"


def test_baris_demo_tidak_ada_di_masa_depan_kecuali_rencana(demo_state, auth_headers):
    demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            aktual_masa_depan = conn.execute(
                text(
                    "SELECT count(*) FROM supply_records WHERE origin = 'demo' "
                    "AND recorded_at >= :ref"
                ),
                {"ref": datetime(2026, 10, 8, 12, 0, tzinfo=UTC)},
            ).scalar()
            rencana_masa_depan = conn.execute(
                text(
                    "SELECT count(*) FROM menu_plans WHERE origin = 'demo' "
                    "AND plan_date > :ref"
                ),
                {"ref": datetime(2026, 10, 8, 12, 0, tzinfo=UTC)},
            ).scalar()
    finally:
        engine.dispose()
    assert int(aktual_masa_depan or 0) == 0
    assert int(rencana_masa_depan or 0) > 0


# --------------------------------------------------------------------------
# Status data & tombol "Segarkan ke hari ini" (Fase 5)
# --------------------------------------------------------------------------


def _snapshot_ids() -> dict[str, set[str]]:
    """Id baris kanonik per tabel — dipakai untuk membuktikan refresh bisa dibalik."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return {
                t: {str(r[0]) for r in conn.execute(text(f"SELECT id::text FROM {t}"))}
                for t in (
                    "supply_records",
                    "demand_records",
                    "price_signals",
                    "batches",
                    "menu_plans",
                )
            }
    finally:
        engine.dispose()


def _delete_ids(ids_by_table: dict[str, set[str]]) -> None:
    """Hapus HANYA id yang diberikan, urut aman-FK (anak dulu)."""
    urutan = ("price_signals", "batches", "supply_records", "demand_records", "menu_plans")
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            for table in urutan:
                ids = list(ids_by_table.get(table, ()))
                if ids:
                    conn.execute(
                        text(f"DELETE FROM {table} WHERE id::text = ANY(:ids)"),
                        {"ids": ids},
                    )
    finally:
        engine.dispose()


def _origin_counts() -> dict[str, dict[str, int]]:
    """Jumlah baris per tabel × origin — pembanding keadaan sebelum/sesudah."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return {
                t: {
                    o: int(
                        conn.execute(
                            text(f"SELECT count(*) FROM {t} WHERE origin = :o"),
                            {"o": o},
                        ).scalar()
                        or 0
                    )
                    for o in ("seed", "demo")
                }
                for t in (
                    "supply_records",
                    "demand_records",
                    "price_signals",
                    "batches",
                    "menu_plans",
                    "decisions",
                )
            }
    finally:
        engine.dispose()


def test_data_status_membaca_db(demo_state, auth_headers):
    demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    r = demo_state.get("/demo/data-status", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canonical_ref"] == "2026-10-08T12:00:00+00:00"
    supply = body["tables"]["supply_records"]
    assert supply["seed"] == 30
    assert supply["demo"] == 2190
    assert supply["demo_to"].startswith("2026-10-07T00:00:00")
    assert supply["seed_from"] == "2026-10-08T12:00:00+00:00"
    assert supply["generated_at"] is not None
    menu = body["tables"]["menu_plans"]
    assert menu["demo_to"].startswith("2026-11-05")
    assert body["totals"]["demo"] == (
        supply["demo"] + body["tables"]["price_signals"]["demo"] + menu["demo"]
    )


def test_status_butuh_peran_kepala(demo_state, monitor_headers):
    assert demo_state.get("/demo/data-status", headers=monitor_headers).status_code == 403
    assert demo_state.post("/demo/refresh", headers=monitor_headers).status_code == 403


def test_refresh_hari_ini_bergeser_dan_bisa_dikembalikan(
    demo_state, auth_headers, monitor_headers
):
    """Tombol hari demo: snapshot kanonik pindah ke hari ini, lalu dikembalikan.

    Yang dibuktikan: (1) baris kanonik BARU benar-benar dibuat dan record
    terbaru Cianjur ikut pindah ke hari ini, (2) NILAI jangkar tidak berubah
    (angkanya dari berkas seed yang sama), (3) peringatannya dibawa di respons,
    (4) keadaan sebelum bisa dipulihkan — jumlah per `origin` kembali persis dan
    id baris kanonik lama tidak hilang. Jadi tes ini tidak merusak DB demo.
    """
    before_ids = _snapshot_ids()
    before_counts = _origin_counts()
    awal = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers).json()
    assert awal["recorded_at"].startswith("2026-10-08T12:00:00")

    r = demo_state.post("/demo/refresh", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"], "seeder relatif harus melaporkan baris yang dimuat"
    assert body["cases"]["seeded"] is True
    assert "TANGGALNYA" in body["warning"]

    added = {t: _snapshot_ids()[t] - before_ids[t] for t in before_ids}
    assert len(added["supply_records"]) == 30, "snapshot REF baru = 30 baris pasokan"
    assert len(added["menu_plans"]) > 0
    sesudah_counts = _origin_counts()
    # Batch memakai id yang TIDAK bergantung waktu referensi → ia di-UPDATE di
    # tempat (tanggal panen ikut pindah), bukan ditambah. Menambah baris di sini
    # akan berarti dua snapshot batch sekaligus.
    assert sesudah_counts["batches"]["seed"] == before_counts["batches"]["seed"]

    # Record terbaru ikut pindah ke HARI INI, tapi nilainya tetap angka kanonik.
    sesudah = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers).json()
    assert sesudah["quantity_kg"] == 1400.0
    assert sesudah["recorded_at"] != awal["recorded_at"]
    assert sesudah["recorded_at"].startswith(str(datetime.now(UTC).year))

    # ---- rollback: (a) buang baris yang ditambahkan refresh, (b) kembalikan
    # baris yang di-update di tempat lewat seed pada REF kanonik, (c) isi ulang
    # baris deret waktu demo yang tanggalnya diambil alih.
    _delete_ids(added)
    asyncio.run(load_seed(CANONICAL_REF))
    demo_state.post("/demo/timeseries", json={"force": False}, headers=auth_headers)
    assert _origin_counts() == before_counts
    kembali = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers).json()
    assert kembali["recorded_at"] == awal["recorded_at"]
    assert kembali["quantity_kg"] == 1400.0
