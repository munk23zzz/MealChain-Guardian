"""Endpoint data & rentang waktu (Fase 4): `/demo/preview`, `/demo/timeseries`,
`/demo/timeseries/purge`.

Yang dibuktikan lewat HTTP, bukan cuma lewat modul:

1. Pratinjau tidak menulis apa pun.
2. Membangun deret waktu **tidak menggeser jangkar**: setelah generate,
   `/balance/map` tetap mencerminkan baris TERBARU tiap lokasi di DB (deret
   aktual berlanjut sampai 4 Nov 12:00), dan baris `origin='seed'` tidak tersentuh.
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
from app.seed.timeseries import (
    CANONICAL_REF,
    DEFAULT_END,
    DEFAULT_START,
    generate_timeseries,
    purge_demo_rows,
)
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC
TABLES = ("supply_records", "demand_records", "price_signals", "menu_plans")


def _kanonik_pada_stempel() -> int:
    """Baris seed yang MENEMPATI stempel deret (00:00/12:00 UTC di dalam rentang).

    Kenapa tidak dipaku ke 8 Okt 12:00: "Segarkan ke hari ini" dan reset template
    memindahkan snapshot kanonik ke REF baru, sehingga stempel lama kosong dan
    generator menulis baris demo di sana — `added` jadi `planned`, bukan
    `planned - 40`. Yang benar-benar diuji adalah "baris yang sudah ada tidak
    dihitung sebagai added", dan itu harus dibaca dari DB.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM supply_records"
                        " WHERE origin = 'seed'"
                        "   AND recorded_at >= :mulai AND recorded_at < :akhir"
                        "   AND date_part('hour', recorded_at AT TIME ZONE 'UTC')"
                        "       IN (0, 12)"
                        "   AND date_part('minute', recorded_at AT TIME ZONE 'UTC') = 0"
                        "   AND date_part('second', recorded_at AT TIME ZONE 'UTC') = 0"
                    ),
                    {"mulai": DEFAULT_START, "akhir": DEFAULT_END},
                ).scalar()
                or 0
            )
    finally:
        engine.dispose()


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


def _teardown_counts(before: dict[str, int]) -> None:
    """Kembalikan DB: ada baris demo sebelumnya → bangun ulang; kalau tidak → bersihkan.

    Pemulihan memakai fungsi modul LANGSUNG, bukan HTTP. Sebelumnya ia mem-POST
    `/demo/timeseries` memakai token dari fixture `auth_headers`; saat teardown
    token itu bisa sudah tidak sah (401) sehingga pemulihan tak jalan — dan
    justru kegagalan teardown inilah yang membiarkan deret kanonik terhapus lalu
    menyeret puluhan tes lain (kejadian 2026-10-16 malam).
    """
    if any(v for k, v in before.items() if k.endswith(":demo")):
        asyncio.run(
            generate_timeseries(DEFAULT_START, DEFAULT_END, interval_hours=12)
        )
    else:
        asyncio.run(purge_demo_rows())


def _peta_acuan() -> dict[str, tuple[float, float]]:
    """(lokasi → pasokan terbaru, demand terbaru) dari DB — acuan peta.

    Peta `/balance/map` menyajikan baris TERBARU tiap lokasi YANG SUDAH TERJADI
    (`recorded_at <= now()`, parameter `as_of`; audit angka 18 Okt 2026 — baris
    masa depan tidak boleh tampil sebagai kondisi kini). Angka snapshot lama
    (4.900 kg, 3 surplus : 7 shortage) adalah keadaan 8 Okt; setelah deret aktual
    diperluas sampai 4 Nov 12:00, angka itu bukan lagi sifat yang harus kekal.
    Yang benar-benar harus berlaku: angka peta = baris terbaru di DB yang sudah
    terjadi.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            baris = conn.execute(
                text(
                    "SELECT l.name, "
                    " (SELECT s.quantity_kg FROM supply_records s "
                    "   WHERE s.location_id = l.id AND s.commodity_id = c.id "
                    "   AND s.recorded_at <= now() "
                    "   ORDER BY s.recorded_at DESC, s.id DESC LIMIT 1), "
                    " (SELECT d.quantity_kg FROM demand_records d "
                    "   WHERE d.location_id = l.id AND d.commodity_id = c.id "
                    "   AND d.recorded_at <= now() "
                    "   ORDER BY d.recorded_at DESC, d.id DESC LIMIT 1) "
                    "FROM locations l, commodities c "
                    "WHERE c.name = 'telur'"
                )
            ).all()
            return {
                str(nama): (float(sup or 0.0), float(dem or 0.0))
                for nama, sup, dem in baris
            }
    finally:
        engine.dispose()


@pytest.fixture()
def demo_state(auth_headers):
    """Snapshot baris demo sebelum tes + pengembalian keadaan setelahnya."""
    from fastapi.testclient import TestClient

    from app.main import app

    before = _counts()
    with TestClient(app) as client:
        yield client
        _teardown_counts(before)


def _menu_coverage() -> tuple[int, int, int, int]:
    """(baris rencana, tanggal unik, baris ganda, hari tanpa rencana).

    `baris ganda` = lebih dari satu rencana untuk (lokasi, tanggal) yang sama —
    dulu tidak diperiksa, padahal justru itu yang membuat angka total bergeser
    tanpa cakupan bertambah.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            total = int(conn.execute(text("SELECT count(*) FROM menu_plans")).scalar() or 0)
            tanggal = int(
                conn.execute(text("SELECT count(DISTINCT plan_date) FROM menu_plans")).scalar()
                or 0
            )
            kembar = int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM ("
                        "  SELECT location_id, plan_date FROM menu_plans"
                        "  GROUP BY 1, 2 HAVING count(*) > 1) d"
                    )
                ).scalar()
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
    return total, tanggal, kembar, kosong


def _jumlah_lokasi() -> int:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(conn.execute(text("SELECT count(*) FROM locations")).scalar() or 0)
    finally:
        engine.dispose()


def _jumlah_hari_rentang() -> int:
    """Jumlah tanggal dalam rentang default (inklusif)."""
    return (DEFAULT_END.date() - DEFAULT_START.date()).days + 1


def _jumlah_pasokan() -> int:
    """Pasangan lokasi×komoditas pada snapshot kanonik (dulu dipaku 40)."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(DISTINCT (location_id, commodity_id)) "
                        "FROM supply_records WHERE origin = 'seed'"
                    )
                ).scalar()
                or 0
            )
    finally:
        engine.dispose()


def _jumlah_stempel_demo() -> int:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(DISTINCT recorded_at) FROM supply_records "
                        "WHERE origin = 'demo'"
                    )
                ).scalar()
                or 0
            )
    finally:
        engine.dispose()


def _stempel_demo_terakhir() -> str:
    """Stempel terakhir deret demo, format ISO tanpa zona (untuk startswith)."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT max(recorded_at) FROM supply_records WHERE origin = 'demo'"
                )
            ).scalar()
    finally:
        engine.dispose()
    assert row is not None, "deret demo belum dibangun"
    return row.strftime("%Y-%m-%dT%H:%M:%S")


def _stempel_seed_pertama() -> str:
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT min(recorded_at) FROM supply_records WHERE origin = 'seed'"
                )
            ).scalar()
    finally:
        engine.dispose()
    assert row is not None, "snapshot kanonik tidak ditemukan"
    return row.isoformat()


def test_preview_tidak_menulis(demo_state, auth_headers):
    before = _counts()
    r = demo_state.get("/demo/preview", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["writes"] is False
    assert body["counts"]["supply"]["planned"] > 0
    assert body["range"]["actual_end"] == "2026-11-05T00:00:00+00:00"
    assert _counts() == before


def test_membangun_deret_tidak_menggeser_jangkar(demo_state, auth_headers, monitor_headers):
    r = demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # "added" = planned − baris kanonik yang sudah menempati stempel 8 Okt 12:00
    # (10 lokasi × 4 komoditas = 40 baris). Angka 3.870 yang dulu dipaku di sini
    # pecah saat beras masuk, padahal yang diuji adalah "kanonik tidak dihitung
    # sebagai added" — jadi hitung dari kontraknya, bukan dari angka tetap.
    planned = body["counts"]["supply"]["planned"]
    kanonik = _kanonik_pada_stempel()
    pasokan = _jumlah_pasokan()
    assert pasokan > 0, "snapshot kanonik tidak ditemukan"
    assert planned % pasokan == 0, "planned harus kelipatan pasokan lokasi×komoditas"
    assert body["counts"]["supply"]["added"] == planned - kanonik, body["counts"]["supply"]
    # Rencana menu harus menutup SELURUH rentang tanpa lubang. Angka "520"
    # sempat dipaku di sini dan pecah begitu jumlah hari kanonik berubah —
    # yang benar adalah cakupan, bukan selisih yang bergantung susunan lama.
    lokasi_menu, hari, kembar, kosong = _menu_coverage()
    assert kosong == 0, "ada hari tanpa rencana di dalam rentang"
    assert kembar == 0, "ada lebih dari satu rencana untuk satu lokasi+tanggal"
    assert hari == _jumlah_hari_rentang()
    assert lokasi_menu == hari * _jumlah_lokasi()
    assert body["purged"]["total"] >= 0
    assert set(body["purged"]["deleted"]) == {
        "supply_records",
        "price_signals",
        "menu_plans",
        "delivery_events",
        # `batches` masuk daftar PURGE_MODELS saat peta mulai membaca tabel
        # batches (commit 3f24ae3); tanpa baris ini tes menolak kontrak yang
        # memang benar.
        "batches",
        "disposal_events",
        # `demand_records` masuk daftar PURGE_MODELS saat deret permintaan demo
        # diperluas (audit angka 18 Okt 2026); tanpa baris ini tes menolak
        # kontrak yang memang benar.
        "demand_records",
    }

    # Jangkar sisi SUMBER: baris KANONIK Cianjur telur tetap 1.400 kg. Record TERBARU
    # keseluruhan kini berasal dari deret demo (ujung rencana 4 Nov 12:00).
    sup = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers)
    assert sup.status_code == 200, sup.text
    assert sup.json()["recorded_at"].startswith(_stempel_demo_terakhir())
    assert _seed_supply_terbaru()[1] == 1400.0

    # Jangkar peta: angka peta = baris TERBARU tiap lokasi yang SUDAH TERJADI
    # (`recorded_at <= now()`, audit angka 18 Okt 2026). Total dan sebaran
    # surplus/shortage karena itu bergerak mengikuti waktu, bukan dipaku.
    # Yang diuji: peta setia pada baris terbaru + rumus gap (surplus bila
    # supply > demand).
    peta = demo_state.get("/balance/map?commodity=telur", headers=monitor_headers)
    assert peta.status_code == 200, peta.text
    lokasi = peta.json()["locations"]
    acuan = _peta_acuan()
    assert {loc["location"] for loc in lokasi} == set(acuan)
    for loc in lokasi:
        sup, dem = acuan[loc["location"]]
        assert loc["supply_kg"] == pytest.approx(sup), loc["location"]
        assert loc["demand_kg"] == pytest.approx(dem), loc["location"]
        if sup > dem:
            assert loc["status"] == "surplus", loc["location"]
        elif sup < dem:
            assert loc["status"] == "shortage", loc["location"]
        else:
            assert loc["status"] == "balanced", loc["location"]
    assert sum(loc["supply_kg"] for loc in lokasi) == pytest.approx(
        sum(sup for sup, _ in acuan.values())
    )


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
    for nama in ("supply", "demand", "prices", "menu_plans"):
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
    assert (
        r.json()["counts"]["supply"]["added"]
        == r.json()["counts"]["supply"]["planned"] - _kanonik_pada_stempel()
    )
    assert durasi < 30, f"generate 66 hari butuh {durasi:.1f}s (batas 30s)"


def test_baris_aktual_berhenti_di_batas_rencana(demo_state, auth_headers):
    """Deret AKTUAL demo mengisi sampai ujung rencana, dan TIDAK melewatinya.

    Tes ini dulu bernama `..._tidak_ada_di_masa_depan_kecuali_rencana` dan memaku
    "tidak ada baris aktual >= REF 8 Okt". Aturan itu DIGANTI 2026-10-17 atas
    permintaan pemilik: justru rentang 9 Okt → 5 Nov yang wajib ada isinya (kalender
    dan jendela KPI 24 jam / 7 hari bergantung padanya). Yang dijaga sekarang: batas
    atas baris aktual = `DEFAULT_END` — tidak ada yang melampauinya — sementara baris
    rencana tetap menutup sampai `DEFAULT_END`.
    """
    demo_state.post(
        "/demo/timeseries",
        json={"start": DEFAULT_START.isoformat(), "end": DEFAULT_END.isoformat(), "force": True},
        headers=auth_headers,
    )
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            aktual_lewat_batas = conn.execute(
                text(
                    "SELECT count(*) FROM supply_records WHERE origin = 'demo' "
                    "AND recorded_at >= :batas"
                ),
                {"batas": DEFAULT_END},
            ).scalar()
            aktual_isi_ujung_rencana = conn.execute(
                text(
                    "SELECT count(*) FROM supply_records WHERE origin = 'demo' "
                    "AND recorded_at >= :awal"
                ),
                {"awal": datetime(2026, 10, 9, 0, 0, tzinfo=UTC)},
            ).scalar()
            rencana_sampai_ujung = conn.execute(
                text(
                    "SELECT count(*) FROM menu_plans WHERE origin = 'demo' "
                    "AND plan_date = :batas"
                ),
                {"batas": DEFAULT_END.date()},
            ).scalar()
    finally:
        engine.dispose()
    assert int(aktual_lewat_batas or 0) == 0
    assert int(aktual_isi_ujung_rencana or 0) > 0
    assert int(rencana_sampai_ujung or 0) > 0


# --------------------------------------------------------------------------
# Status data & tombol "Segarkan ke hari ini" (Fase 5)
# --------------------------------------------------------------------------


def _snapshot_ids_kanonik() -> dict[str, set[str]]:
    """Id baris KANONIK (origin='seed' / bukan demo) per tabel deret waktu."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return {
                t: {
                    str(r[0])
                    for r in conn.execute(
                        text(
                            f"SELECT id::text FROM {t} WHERE "
                            + ("origin<>'demo'" if t == "batches" else "origin='seed'")
                        )
                    )
                }
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


def _jumlah_kasus_demo() -> int:
    """Jumlah kasus skrip yang terpasang sekarang (`demo_case` terisi)."""
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(DISTINCT demo_case) FROM decisions "
                        "WHERE demo_case IS NOT NULL"
                    )
                ).scalar()
                or 0
            )
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
    assert body["canonical_ref"] == CANONICAL_REF.isoformat()
    supply = body["tables"]["supply_records"]
    # Angka `seed` TIDAK dipaku 40: setiap generasi kanonik memang 40 baris
    # (10 lokasi × 4 komoditas), tetapi jumlah generasi bergantung pada berapa
    # kali "snapshot kanonik" digeser (template/sesi demo dan "Segarkan ke hari
    # ini" menulis generasi ber-REF sendiri). Yang diuji: angkanya SAMA dengan
    # DB (endpoint membaca DB, bukan konstanta) dan setiap generasi tetap utuh
    # satu baris per pasangan lokasi×komoditas.
    with create_engine(DB_URL).connect() as conn:
        seed_supply = int(
            conn.execute(
                text("SELECT count(*) FROM supply_records WHERE origin='seed'")
            ).scalar()
        )
        generasi = conn.execute(
            text(
                "SELECT count(*) FROM (SELECT recorded_at FROM supply_records "
                "WHERE origin='seed' GROUP BY recorded_at) g"
            )
        ).scalar()
        pasangan_ganda = int(
            conn.execute(
                text(
                    "SELECT count(*) FROM ("
                    "  SELECT recorded_at, location_id, commodity_id FROM supply_records"
                    "  WHERE origin='seed' GROUP BY 1,2,3 HAVING count(*) > 1) d"
                )
            ).scalar()
        )
    assert supply["seed"] == seed_supply
    assert pasangan_ganda == 0, "satu generasi kanonik = satu baris per pasangan"
    pasokan = _jumlah_pasokan()
    assert seed_supply == pasokan * int(generasi or 0), "satu generasi = satu baris per pasangan"
    # Deret demo = satu baris per pasangan per stempel yang ditulis generator.
    # Jumlah stempelnya bergantung state (snapshot kanonik bisa digeser), jadi
    # dihitung dari DB — bukan dipaku 130 stempel / 5160 baris.
    assert supply["demo"] == pasokan * _jumlah_stempel_demo()
    assert supply["demo_to"].startswith(_stempel_demo_terakhir())
    assert supply["seed_from"] == _stempel_seed_pertama()
    assert supply["generated_at"] is not None
    # Permintaan ikut dilaporkan: tanpa ini panel hanya melihat 3 tabel dan
    # menyembunyikan 864 baris permintaan demo.
    demand = body["tables"]["demand_records"]
    # Angka seed TURUN dari DB (40 pasangan × 7 observasi), bukan konstanta:
    # deret permintaan bertambah saat dataset diperluas.
    with create_engine(DB_URL).connect() as conn:
        seed_demand = int(
            conn.execute(
                text("SELECT count(*) FROM demand_records WHERE origin='seed'")
            ).scalar()
        )
        demo_demand = int(
            conn.execute(
                text("SELECT count(*) FROM demand_records WHERE origin='demo'")
            ).scalar()
        )
    assert demand["seed"] == seed_demand
    assert demand["demo"] == demo_demand
    assert demand["demo_from"].startswith("2026-10-09T00:00:00")
    menu = body["tables"]["menu_plans"]
    assert menu["demo_to"].startswith("2026-11-05")
    assert body["totals"]["demo"] == (
        supply["demo"]
        + demand["demo"]
        + body["tables"]["price_signals"]["demo"]
        + menu["demo"]
    )


def test_status_butuh_peran_kepala(demo_state, monitor_headers):
    assert demo_state.get("/demo/data-status", headers=monitor_headers).status_code == 403
    assert demo_state.post("/demo/refresh", headers=monitor_headers).status_code == 403


def _seed_supply_terbaru(
    lokasi: str = "Cianjur", komoditas: str = "telur"
) -> tuple[str, float]:
    """Baris KANONIK (`origin='seed'`) terbaru satu pasangan: (recorded_at ISO, kg).

    Sejak deret aktual berjalan sampai 5 Nov, record terbaru keseluruhan berasal dari
    deret demo — jadi jangkar kanonik harus dibaca eksplisit lewat `origin='seed'`.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT s.recorded_at, s.quantity_kg FROM supply_records s "
                    "JOIN locations l ON l.id = s.location_id "
                    "JOIN commodities c ON c.id = s.commodity_id "
                    "WHERE l.name = :lok AND c.name = :kom AND s.origin = 'seed' "
                    "ORDER BY s.recorded_at DESC LIMIT 1"
                ),
                {"lok": lokasi, "kom": komoditas},
            ).fetchone()
    finally:
        engine.dispose()
    assert row is not None, "baris kanonik tidak ditemukan"
    return row[0].isoformat(), float(row[1])


def _terbaru_semua(lokasi: str = "Cianjur", komoditas: str = "telur") -> str:
    """`recorded_at` terbaru satu pasangan dari SEMUA origin (ISO).

    Dipakai untuk menguji kontrak endpoint `/supply/<lokasi>/<komoditas>`
    ("kembalikan yang terbaru") tanpa memaku tanggal. Tanggal terbaru bisa
    berpindah karena fitur "Segarkan ke hari ini" — yang tidak boleh berubah
    hanyalah: endpoint selalu mengembalikan baris paling baru yang ada.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT max(s.recorded_at) FROM supply_records s "
                    "JOIN locations l ON l.id = s.location_id "
                    "JOIN commodities c ON c.id = s.commodity_id "
                    "WHERE l.name = :lok AND c.name = :kom"
                ),
                {"lok": lokasi, "kom": komoditas},
            ).scalar_one()
    finally:
        engine.dispose()
    assert row is not None, "tidak ada baris supply untuk pasangan itu"
    return row.isoformat()


def _batch_duplikat() -> int:
    """Jumlah (pemasok, lokasi, komoditas, panen) dengan lebih dari satu batch.

    Invariant setelah "Segarkan ke hari ini": batch di-UPDATE di tempat (id tidak
    bergantung waktu referensi), jadi menyegarkan tidak boleh MELIPATKAN batch
    yang sama. Jumlah baris boleh bertambah hanya karena pasangan yang tadinya
    satu lot kini punya lot kedua di berkas seed.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT coalesce(sum(n - 1), 0) FROM ("
                        "SELECT count(*) AS n FROM batches "
                        "GROUP BY supplier_id, location_id, commodity_id, harvested_at "
                        "HAVING count(*) > 1) d"
                    )
                ).scalar()
            )
    finally:
        engine.dispose()


def _menu_duplikat() -> int:
    """Jumlah (lokasi, tanggal) yang punya lebih dari satu rencana menu.

    Invariant setelah "Segarkan ke hari ini": rencana untuk tanggal yang sudah
    ada dipakai ulang, bukan digandakan.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM ("
                        "  SELECT location_id, plan_date FROM menu_plans"
                        "  GROUP BY 1, 2 HAVING count(*) > 1"
                        ") dup"
                    )
                ).scalar()
                or 0
            )
    finally:
        engine.dispose()


def _kembalikan_baseline() -> None:
    """Pulihkan DB kerja ke baseline kanonik setelah menguji "Segarkan ke hari ini".

    Refresh mengubah data lewat tiga jalur yang tidak bisa dibalik dengan
    menghapus "id baru" saja:
      1. menulis generasi seed baru (id baru) untuk tanggal HARI INI,
      2. MENGADOPSI rencana menu demo (origin `demo` → `seed`, id tetap),
      3. memperbarui baris yang id-nya tidak bergantung ref — limbah per
         "hari ke-N" — sehingga tanggalnya ikut pindah.
    Karena itu rollback memakai jalur resmi yang terbukti menghasilkan baseline
    kanonik: purge demo → buang generasi seed di luar kanonik → seeder kanonik →
    generator deret (3870/4010/590 baris demo, 30/44/70 kanonik, 70 kiriman +
    20 limbah kanonik).
    """
    from app.seed.seed_data import build_seed_rows

    kanonik = build_seed_rows(CANONICAL_REF)
    asyncio.run(purge_demo_rows())
    tanggal = {
        "delivery_events": sorted(
            {row["delivered_at"].date().isoformat() for row in kanonik["delivery_events"]}
        ),
        "disposal_events": sorted(
            {row["disposed_at"].date().isoformat() for row in kanonik["disposal_events"]}
        ),
    }
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            # Peristiwa kanonik di-*update di tempat* oleh refresh (id tidak
            # mengandung ref), jadi tanggalnya bisa pindah ke hari ini. Buang
            # baris seed yang tanggalnya di luar jendela kanonik, lalu seeder
            # menulis ulang 70 kiriman (1–7 Okt) + 20 limbah (4–7 Okt).
            conn.execute(
                text(
                    "DELETE FROM delivery_events WHERE origin='seed' "
                    "AND NOT (delivered_at::date = ANY(CAST(:t AS date[])))"
                ),
                {"t": tanggal["delivery_events"]},
            )
            conn.execute(
                text(
                    "DELETE FROM disposal_events WHERE origin='seed' "
                    "AND NOT (disposed_at::date = ANY(CAST(:t AS date[])))"
                ),
                {"t": tanggal["disposal_events"]},
            )
            for tabel, kunci in (
                ("delivery_events", "delivery_events"),
                ("disposal_events", "disposal_events"),
                ("menu_plans", "menu_plans"),
                ("supply_records", "supply"),
                ("demand_records", "demand"),
                ("price_signals", "price_signals"),
            ):
                ids = [str(row["id"]) for row in kanonik[kunci]]
                conn.execute(
                    text(
                        f"DELETE FROM {tabel} WHERE origin='seed' "
                        "AND NOT (id = ANY(CAST(:ids AS uuid[])))"
                    ),
                    {"ids": ids},
                )
    finally:
        engine.dispose()
    asyncio.run(load_seed(CANONICAL_REF))
    asyncio.run(generate_timeseries(DEFAULT_START, DEFAULT_END))
    # `/demo/refresh` mem-purge SELURUH baris demo, termasuk batch & keputusan
    # demo. Tanpa langkah ini rollback hanya mengembalikan deret waktu, sehingga
    # tes berikutnya dalam suite yang sama melihat "riwayat demo tidak ada" dan
    # `batches.seed` bertambah satu (refresh membuat batch untuk pasangan yang
    # batch demo-nya sudah dihapus). Penyemai memakai id stabil → aman diulang.
    async def _pulihkan_kegiatan_demo() -> None:
        from app.core.config import settings as _settings
        from app.db import create_engine as _async_engine
        from app.db import create_session_maker
        from app.seed.demo_activity import (
            seed_demo_activity,
            seed_demo_completed_decisions,
        )

        eng = _async_engine(_settings.database_url)
        maker = create_session_maker(eng)
        try:
            async with maker() as sesi:
                await seed_demo_activity(sesi, datetime.now(UTC))
                await seed_demo_completed_decisions(sesi, datetime.now(UTC))
                await sesi.commit()
        finally:
            await eng.dispose()

    asyncio.run(_pulihkan_kegiatan_demo())


def test_refresh_hari_ini_tidak_menggandakan_snapshot_kanonik(
    demo_state, auth_headers, monitor_headers
):
    """Tombol hari demo TIDAK memanggal tanggal snapshot kanonik.

    Kontrak lama ("snapshot kanonik pindah ke hari ini") menghasilkan baris
    yatim: id baris kanonik diturunkan dari tanggal acuan, jadi memuat ulang
    pada tanggal hari ini membuat generasi baru sementara generasi lama tetap
    ada — 100 `price_signals` duplikat dan 40 `pihps_reference` ganda, dan
    akhirnya empat tes invarian merah SETELAH tombol ditekan.

    Kontrak yang berlaku: snapshot kanonik dipertahankan (dilewati bila sudah
    ada), sedangkan baris DEMO yang bergerak ke hari ini — kiriman, kasus
    skrip, keputusan selesai, harga harian, dan seed hari-ini.
    """
    # Hanya baris KANONIK yang dipakai sebagai pembanding: refresh memang
    # menambah baris demo hari ini (itu tugasnya).
    sebelum_kanonik = _snapshot_ids_kanonik()
    awal_seed, kg_awal = _seed_supply_terbaru()
    # Dulu 1400,0 kg (baris kanonik semata). Sejak `build_into` juga
    # menjalankan `generate_timeseries`, baris pasokan "terbaru" untuk Jakarta
    # datang dari deret sintesis sehingga angkanya tidak lagi bulat. Yang
    # diuji di sini bukan angka mutlaknya, melainkan bahwa refresh TIDAK
    # menggandakan baris kanonik — jadi cukup pastikan nilainya ada.
    assert kg_awal > 0

    r = demo_state.post("/demo/refresh", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"]["dilewati"] == "snapshot kanonik sudah ada"
    assert body["cases"]["seeded"] is True
    assert body["hari_ini"]["keputusan"] == 9
    assert "TANGGALNYA" in body["warning"]

    # Kanonik: baris seed TIDAK bertambah/berubah tanggal (tidak ada generasi
    # kedua). Baris demo boleh bertambah — itu justru tugas refresh.
    # Set id kanonik dibandingkan lewat potongan yang sama: baris seed saja.
    dengan_kanonik = _snapshot_ids_kanonik()
    for tabel, ids in sebelum_kanonik.items():
        assert dengan_kanonik[tabel] == ids, f"{tabel}: refresh membuat generasi kanonik baru"
    recorded_seed, kg_sesudah = _seed_supply_terbaru()
    assert recorded_seed == awal_seed
    assert kg_sesudah == 1400.0

    # Demo: kiriman dan deret hari ini ada, tanpa baris ganda.
    assert _batch_duplikat() == 0, "refresh meninggalkan batch kembar"
    assert _origin_counts()["price_signals"]["demo"] > 0
    assert _menu_duplikat() == 0

def test_refresh_menyinkronkan_rute_kiriman(
    demo_state, auth_headers, monkeypatch
) -> None:
    import app.seed.seed_data as seed_data

    dipanggil: dict = {}

    async def palsu(reference_time):
        dipanggil["ref"] = reference_time
        return {"diambil": 2, "sudah_ada": 3, "gagal": 0, "alasan_gagal": {}}

    monkeypatch.setattr(seed_data, "sync_routes_after_seed", palsu)

    try:
        r = demo_state.post("/demo/refresh", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["routes"]["diambil"] == 2, "laporan sinkronisasi rute harus dibawa"
        assert body["route_error"] is None
        assert dipanggil["ref"].tzinfo is not None, "waktu referensi wajib tz-aware"
    finally:
        # Tombol demo MENULIS generasi snapshot baru untuk hari ini dan mengadopsi
        # rencana menu demo. Tanpa rollback, generasi ini tertinggal (supply seed
        # 60 vs 30, menu 140 vs 70) dan meracuni tes berikutnya dalam satu run.
        _kembalikan_baseline()


def test_refresh_tetap_berhasil_bila_osrm_tidak_terjangkau(
    demo_state, auth_headers, monkeypatch
) -> None:
    """Jaringan mati TIDAK boleh menggagalkan tombol demo — dilaporkan, bukan disembunyikan."""
    import app.seed.seed_data as seed_data

    async def meledak(reference_time):
        raise RuntimeError("OSRM tidak terjangkau")

    monkeypatch.setattr(seed_data, "sync_routes_after_seed", meledak)

    try:
        r = demo_state.post("/demo/refresh", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["routes"] == {}
        assert "OSRM tidak terjangkau" in body["route_error"]
    finally:
        # Sama seperti tes rute di atas: refresh menulis snapshot hari ini.
        _kembalikan_baseline()
