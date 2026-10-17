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

    Peta `/balance/map` menyajikan baris TERBARU tiap lokasi. Angka snapshot lama
    (4.900 kg, 3 surplus : 7 shortage) adalah keadaan 8 Okt; setelah deret aktual
    diperluas sampai 4 Nov 12:00, angka itu bukan lagi sifat yang harus kekal.
    Yang benar-benar harus berlaku: angka peta = baris terbaru di DB.
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            baris = conn.execute(
                text(
                    "SELECT l.name, "
                    " (SELECT s.quantity_kg FROM supply_records s "
                    "   WHERE s.location_id = l.id AND s.commodity_id = c.id "
                    "   ORDER BY s.recorded_at DESC, s.id DESC LIMIT 1), "
                    " (SELECT d.quantity_kg FROM demand_records d "
                    "   WHERE d.location_id = l.id AND d.commodity_id = c.id "
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
    # 3.870, bukan 3.900: 130 cap waktu × 30 pasangan = 3.900 baris yang direncanakan,
    # tetapi 30 di antaranya jatuh tepat di (lokasi, komoditas, 8 Okt 12:00) — stamp
    # yang sudah dipegang baris kanonik seed, jadi baris itu DIPERTAHANKAN dan tidak
    # dihitung sebagai "added".
    assert body["counts"]["supply"]["added"] == 3870
    # Rencana menu harus menutup SELURUH rentang tanpa lubang. Angka "520"
    # sempat dipaku di sini dan pecah begitu jumlah hari kanonik berubah —
    # yang benar adalah cakupan, bukan selisih yang bergantung susunan lama.
    assert _menu_coverage() == (660, 66, 0)
    assert body["purged"]["total"] >= 0
    assert set(body["purged"]["deleted"]) == {
        "supply_records",
        "price_signals",
        "menu_plans",
        "delivery_events",
        "disposal_events",
    }

    # Jangkar sisi SUMBER: baris KANONIK Cianjur telur tetap 1.400 kg. Record TERBARU
    # keseluruhan kini berasal dari deret demo (ujung rencana 4 Nov 12:00).
    sup = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers)
    assert sup.status_code == 200, sup.text
    assert sup.json()["recorded_at"].startswith("2026-11-04T12:00:00")
    assert _seed_supply_terbaru()[1] == 1400.0

    # Jangkar peta: angka peta = baris TERBARU tiap lokasi di DB. Total 4.900 kg
    # dan sebaran 3 surplus : 7 shortage adalah keadaan 8 Okt — dipaku di sini dulu
    # dan pecah begitu deret aktual diperluas sampai 4 Nov. Yang diuji sekarang:
    # peta setia pada baris terbaru + rumus gap (surplus bila supply > demand).
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
    assert r.json()["counts"]["supply"]["added"] == 3870
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
    assert supply["demo"] == 3870
    assert supply["demo_to"].startswith("2026-11-04T12:00:00")
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
    # Kontrak endpoint, bukan tanggal: kembalikan baris TERBARU dari origin mana pun.
    # Tanggalnya tidak dipaku karena "Segarkan ke hari ini" memang memindahkan baris
    # kanonik ke hari ini — memakunya membuat tes merah hanya karena fitur itu dipakai.
    assert awal["recorded_at"] == _terbaru_semua()

    # Record kanonik terbaru ikut pindah ke HARI INI, nilai kanonik tidak berubah.
    # (Record terbaru keseluruhan berasal dari deret demo — 4 Nov 12:00 — karena itu
    # jangkar dibaca lewat `origin='seed'`.)
    awal_seed, kg_awal = _seed_supply_terbaru()
    assert kg_awal == 1400.0

    try:
        r = demo_state.post("/demo/refresh", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["rows"], "seeder relatif harus melaporkan baris yang dimuat"
        assert body["cases"]["seeded"] is True
        assert "TANGGALNYA" in body["warning"]

        added = {t: _snapshot_ids()[t] - before_ids[t] for t in before_ids}
        assert len(added["supply_records"]) == 30, "snapshot REF baru = 30 baris pasokan"
        # Rencana menu TIDAK digandakan: untuk tanggal yang sudah punya rencana
        # (deret demo menutup 8 Okt–5 Nov), seeder memakai rencana yang ada. Menu
        # boleh 0 baris baru — yang wajib bertambah adalah snapshot pasokan.
        assert _menu_duplikat() == 0, "refresh menggandakan rencana menu (lokasi, tanggal)"
        sesudah_counts = _origin_counts()
        # Batch memakai id yang TIDAK bergantung waktu referensi → ia di-UPDATE di
        # tempat (tanggal panen ikut pindah), bukan ditambah. Menambah baris di sini
        # akan berarti dua snapshot batch sekaligus.
        assert sesudah_counts["batches"]["seed"] == before_counts["batches"]["seed"]

        # Snapshot kanonik terbaru kini bertanggal HARI INI, nilainya tetap kanonik.
        recorded_seed, kg_sesudah = _seed_supply_terbaru()
        assert recorded_seed != awal_seed
        assert recorded_seed.startswith(str(datetime.now(UTC).year))
        assert kg_sesudah == 1400.0
    finally:
        # ---- rollback SELALU jalan: (a) buang baris yang ditambahkan refresh,
        # (b) kembalikan baris yang di-update di tempat lewat seed pada REF kanonik,
        # (c) isi ulang baris deret waktu demo yang tanggalnya diambil alih.
        #
        # Dulu ketiga langkah ini berada SESUDAH asersi tanpa `try/finally`, jadi
        # satu kegagalan di tengah (mis. asersi cap waktu) meninggalkan baris
        # ber-REF jam di DB kerja. Residunya nyata: 120 baris `demand_records`
        # ber-`needed_by` 2026-10-19 tertinggal dan menyusup ke jendela "3
        # observasi terbaru", sehingga `/demand/forecast/Jakarta/telur` meleset
        # (2.140 alih-alih 2.120).
        added = {t: _snapshot_ids()[t] - before_ids[t] for t in before_ids}
        _delete_ids(added)
        _kembalikan_baseline()

    assert _origin_counts() == before_counts
    kembali = demo_state.get("/supply/Cianjur/telur", headers=monitor_headers).json()
    assert kembali["recorded_at"] == awal["recorded_at"]
    assert _seed_supply_terbaru()[1] == 1400.0


# ---------------------------------------------------------------------------
# "Segarkan ke hari ini" juga menyinkronkan rute jalan.
#
# Alasannya nyata (temuan 17 Okt 2026): seeder memindahkan tanggal kiriman ke
# hari ini, tetapi pasangan pemasok→tujuan yang BELUM ada di cache `road_routes`
# hanya punya geometri kalau disinkronkan. Sebelum perbaikan ini, kiriman baru
# punya data tetapi tidak punya garis — peta menulis "belum disinkronkan"
# padahal jalannya bisa diambil. Dua tes di bawah mengunci kontraknya tanpa
# menyentuh jaringan: sinkronisasi dipalsukan.
# ---------------------------------------------------------------------------


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
