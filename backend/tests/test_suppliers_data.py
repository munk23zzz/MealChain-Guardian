"""Mutu data pemasok Fase 2 — aturan yang mengikat data demo ke kanonik.

Dua hal yang dijaga di sini:

1. **Data demo tidak boleh merusak kanonik.** 14 pemasok `sprint1_seed.json`
   harus tetap ada dengan skor keandalan yang sama seperti berkas itu. Id
   kanonik diketahui BUKAN UUID5 natural key (baris warisan, lihat
   `test_canonical_supplier_ids_are_legacy_random_uuids`).
   Kalau generator/seed demo kelak menimpa mereka, tes ini yang menangkapnya.
2. **Berkas demo tidak boleh berbohong.** Koordinat wajib ada untuk SETIAP
   pemasok (tanpa itu peta akan menaruhnya di laut), tersebar di Indonesia, dan
   titik pemasok demo harus ada di sekitar hub-nya: baris ber-`offset_index`
   memakai geseran kecil dari titik hub, sedangkan klaster Jakarta memakai
   koordinat absolut yang **wajib ≤150 km** dari SPPG Jakarta (Fase 7).

Baca `data/seed/suppliers_demo.json` lewat `load_demo_rows()` (modul yang sama
dipakai seeder) supaya validasi tidak terduplikasi.
"""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.seed.suppliers_demo import (
    OFFSETS,
    REACH_KM_MAX,
    haversine_km,
    load_demo_rows,
)
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC

# Indonesia (batas longgar) — cukup untuk menangkap koordinat yang tertukar
# lat/long atau salah benua.
LAT_RANGE = (-11.5, 6.5)
LON_RANGE = (94.5, 141.5)


def _canonical_suppliers() -> list[dict]:
    candidates = [
        Path("/data/seed/sprint1_seed.json"),
        Path(__file__).resolve().parents[2] / "data" / "seed" / "sprint1_seed.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)["suppliers"]
    raise AssertionError("sprint1_seed.json tidak ditemukan (container maupun repo)")


# --------------------------------------------------------------------------
# Bagian murni — berkas data
# --------------------------------------------------------------------------


def test_demo_file_shape_and_distribution():
    """Berkas demo = MASTER pemasok, bukan overlay di atas 14 baris kanonik.

    Sejak dataset 19 Okt 2026 nama usaha nyata (CV/UD/PT/PD/Koperasi + nama
    pasar induk) menggantikan pola "Supplier <Kota>-N", jadi `suppliers_demo.json`
    memuat SEMUA pemasok dan `sprint1_seed.json` memuat daftar yang SAMA.
    Angka lama (24 baris demo + 14 kanonik) tidak berlaku lagi.

    Yang dijaga di sini: setiap hub punya pemasok, klaster Jakarta paling besar,
    semua komoditas terwakili, dan SEMUA baris berkoordinat absolut (tidak ada
    lagi `offset_index` — jarak pemasok-SPPG harus bisa dihitung apa adanya).
    """
    rows = load_demo_rows()
    canonical = _canonical_suppliers()
    assert len(rows) == len(canonical) == 60, "60 pemasok lokal di 10 hub"

    per_hub: dict[str, int] = {}
    per_commodity: dict[str, int] = {}
    for row in rows:
        per_hub[row["location"]] = per_hub.get(row["location"], 0) + 1
        per_commodity[row["commodity"]] = per_commodity.get(row["commodity"], 0) + 1

    assert len(per_hub) == 10, "semua 10 lokasi harus punya pemasok"
    assert per_hub["Jakarta"] == 13, f"klaster Jakarta harus 13 baris: {per_hub}"
    assert min(per_hub.values()) >= 4, f"ada hub yang terlalu tipis: {per_hub}"
    assert set(per_commodity) == {"ayam", "beras", "telur", "wortel"}, per_commodity
    assert min(per_commodity.values()) >= 10, per_commodity

    assert all(
        "latitude" in r and "longitude" in r and "offset_index" not in r for r in rows
    ), "semua baris memakai koordinat absolut"

    names = [r["name"] for r in rows]
    assert len(set(names)) == len(names)


def test_jakarta_cluster_is_stratified_in_distance(conn):
    """Jarak bertingkat (0–25 / 25–60 / 60–150 km) — bukan semua di dalam kota.

    Dibuktikan dari koordinat di berkas, bukan dari klaim: haversine ke titik
    SPPG Jakarta yang dibaca dari tabel `locations`.
    """
    hub = conn.execute(
        text("SELECT latitude, longitude FROM locations WHERE name = 'Jakarta'")
    ).one()
    hub_coords = {"Jakarta": (float(hub[0]), float(hub[1]))}
    rows = load_demo_rows(hub_coords=hub_coords)  # menegakkan aturan ≤ 150 km
    jakarta = [r for r in rows if r["location"] == "Jakarta"]

    distances = {
        r["name"]: haversine_km(
            float(r["latitude"]), float(r["longitude"]), hub_coords["Jakarta"][0],
            hub_coords["Jakarta"][1],
        )
        for r in jakarta
    }
    assert max(distances.values()) <= REACH_KM_MAX, distances
    dekat = [n for n, d in distances.items() if d <= 25]
    menengah = [n for n, d in distances.items() if 25 < d <= 60]
    jauh = [n for n, d in distances.items() if 60 < d <= REACH_KM_MAX]
    assert len(dekat) >= 4, dekat
    assert len(menengah) >= 2, menengah
    assert len(jauh) >= 1, jauh
    # Urutan ujung-ujungnya dipaku supaya perubahan besar terlihat sadar.
    # Tetangga terdekat sekarang "CV Cipinang Boga Utama" (0,6 km dari titik SPPG).
    assert min(distances, key=lambda n: distances[n]) == "CV Cipinang Boga Utama"
    assert max(distances, key=lambda n: distances[n]) == "CV Hortikultura Subang Lestari"


def test_jakarta_cluster_rejects_unreachable_or_relative_rows(tmp_path):
    """Aturan 150 km dan kewajiban koordinat absolut ditegakkan saat memuat."""
    hub_coords = {"Jakarta": (-6.2088, 106.8456)}
    example = next(r for r in load_demo_rows() if r["location"] == "Jakarta")

    jauh = dict(example, latitude=3.5952, longitude=98.6722)  # Medan, ~1.400 km
    path = tmp_path / "jauh.json"
    path.write_text(json.dumps({"suppliers": [jauh]}), encoding="utf-8")
    with pytest.raises(ValueError, match="jangkauan"):
        load_demo_rows(path, hub_coords=hub_coords)

    relatif = {
        key: value
        for key, value in example.items()
        if key not in ("latitude", "longitude")
    }
    relatif["offset_index"] = 0
    path2 = tmp_path / "relatif.json"
    path2.write_text(json.dumps({"suppliers": [relatif]}), encoding="utf-8")
    with pytest.raises(ValueError, match="absolut"):
        load_demo_rows(path2, hub_coords=hub_coords)  # tanpa hub_coords baris ini sah


def test_demo_file_has_material_for_exclusion_story():
    """Empat pemasok skor rendah tanpa sertifikasi = bahan kasus 'pemasok janggal'."""
    rows = load_demo_rows()
    low = [r for r in rows if float(r["reliability_score"]) <= 0.45]
    # Dua (dulu empat): dataset 19 Okt 2026 memakai skor yang lebih realistis,
    # dan cerita "pemasok janggal" tetap punya bahan selama ada >1 kandidat.
    assert len(low) >= 2, f"harus ada >=2 pemasok berisiko, ada {len(low)}"
    assert all(r["certification_status"] == "none" for r in low)
    assert all(r["capacity_kg_per_week"] > 0 for r in rows)


def test_load_demo_rows_rejects_bad_data(tmp_path):
    """Validator menolak data rusak (nama ganda, sertifikasi, skor, offset, koordinat)."""
    good = load_demo_rows()[0]
    tanpa_koordinat = {
        key: value for key, value in good.items() if key not in ("latitude", "longitude")
    }
    cases = {
        "ganda": [good, dict(good)],
        "sertifikasi": [{**good, "certification_status": "wishful"}],
        "skor": [{**good, "reliability_score": 1.4}],
        "offset": [{**good, "latitude": None, "longitude": None, "offset_index": 9}],
        "koordinat_separuh": [
            {key: value for key, value in good.items() if key != "longitude"}
        ],
        "koordinat_luar_indonesia": [{**good, "latitude": -30.0, "longitude": 106.8}],
        "tanpa_koordinat_maupun_offset": [tanpa_koordinat],
    }
    for label, rows in cases.items():
        path = tmp_path / f"bad_{label}.json"
        path.write_text(json.dumps({"suppliers": rows}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_demo_rows(path)


def test_offsets_stay_within_a_few_km():
    assert all(abs(dlat) <= 0.03 and abs(dlon) <= 0.03 for dlat, dlon in OFFSETS)


# --------------------------------------------------------------------------
# Bagian DB
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def conn():
    engine = create_engine(DB_URL)
    with engine.connect() as connection:
        yield connection
    engine.dispose()


def test_every_supplier_has_map_coordinates(conn):
    """Tanpa koordinat, pemasok tidak bisa tampil di peta — jadi ini wajib."""
    total, with_coords = conn.execute(
        text(
            "SELECT count(*), count(*) FILTER (WHERE latitude IS NOT NULL "
            "AND longitude IS NOT NULL) FROM suppliers"
        )
    ).one()
    # Tidak ada lagi 14 baris kanonik legacy: berkas demo = master, jadi jumlah
    # baris tabel = jumlah baris berkas.
    assert total == len(load_demo_rows())
    assert with_coords == total


def test_coordinates_land_in_indonesia(conn):
    rows = conn.execute(
        text("SELECT name, latitude, longitude FROM suppliers")
    ).all()
    for name, lat, lon in rows:
        assert LAT_RANGE[0] <= float(lat) <= LAT_RANGE[1], f"{name} lat di luar Indonesia"
        assert LON_RANGE[0] <= float(lon) <= LON_RANGE[1], f"{name} lon di luar Indonesia"


def test_every_supplier_sits_near_its_own_hub(conn):
    """Setiap pemasok berjarak wajar dari hub-nya — bukti dari DB, bukan klaim.

    Dulu tes ini hanya memeriksa baris ber-`offset_index` (≤0.05° dari hub).
    Dataset 19 Okt 2026 memakai koordinat ABSOLUT untuk semua baris, jadi yang
    diuji sekarang jarak haversine ke hub sendiri: pemasok "di sekitar daerah
    mereka" adalah janji berkas, bukan hiasan. Batasnya 60 km — cukup untuk
    penyangga (Subang, Serang, Cileunyi) tetapi menolak salah pulau.
    """
    rows = conn.execute(
        text(
            "SELECT s.name, s.latitude, s.longitude, l.latitude, l.longitude, l.name "
            "FROM suppliers s JOIN locations l ON l.id = s.location_id"
        )
    ).all()
    assert len(rows) == len(load_demo_rows())
    for name, lat, lon, hub_lat, hub_lon, hub in rows:
        jarak = haversine_km(
            float(lat), float(lon), float(hub_lat), float(hub_lon)
        )
        # 150 km = REACH_KM_MAX, aturan yang juga dipakai pemuat untuk klaster
        # rujukan. Serang 77,7 km dan Subang 108,6 km memang penyangga sah;
        # batas ini masih menolak salah pulau/provinsi.
        assert jarak <= 150.0, f"{name} berjarak {jarak:.1f} km dari hub {hub}"


def test_jakarta_suppliers_in_db_are_within_reach(conn):
    """Bukti di database, bukan hanya di berkas: semua pemasok hub Jakarta ≤150 km.

    Termasuk pemasok kanonik yang koordinatnya di-backfill migrasi 012 (geseran
    kecil dari titik hub) — dua jalur penulisan koordinat, satu aturan jarak.
    """
    rows = conn.execute(
        text(
            "SELECT s.name, s.latitude, s.longitude, l.latitude, l.longitude "
            "FROM suppliers s JOIN locations l ON l.id = s.location_id "
            "WHERE l.name = 'Jakarta'"
        )
    ).all()
    assert len(rows) >= 12, f"klaster Jakarta harus terisi: {len(rows)}"
    for name, lat, lon, hub_lat, hub_lon in rows:
        distance = haversine_km(
            float(lat), float(lon), float(hub_lat), float(hub_lon)
        )
        assert distance <= REACH_KM_MAX, f"{name} berjarak {distance:.1f} km dari Jakarta"

    # Dan tidak ada pemasok hub lain yang menyelinap ke klaster Jakarta.
    demo_jakarta = [r["name"] for r in load_demo_rows() if r["location"] == "Jakarta"]
    stored_jakarta = {r[0] for r in rows}
    assert set(demo_jakarta) <= stored_jakarta


def test_every_supplier_has_its_own_pin(conn):
    """Tidak ada dua pemasok yang bertumpuk di satu titik — pin harus bisa diklik.

    Pemasok kanonik di-backfill migrasi 012 dengan 9 posisi bergeser per hub, dan
    pemasok demo memakai tiga geseran tetap; jadi kedua jalur harus menghasilkan
    koordinat yang berbeda-beda.
    """
    rows = conn.execute(
        text("SELECT name, latitude, longitude FROM suppliers ORDER BY name")
    ).all()
    pins: dict[tuple[str, str], list[str]] = {}
    for name, lat, lon in rows:
        pins.setdefault((str(lat), str(lon)), []).append(name)
    overlapping = {k: v for k, v in pins.items() if len(v) > 1}
    assert not overlapping, f"pin bertumpuk: {overlapping}"
    assert len(pins) == len(rows)


def test_canonical_supplier_names_all_present(conn):
    """Nama di kedua berkas harus SAMA, dan profilnya identik.

    Berkas demo dipakai sebagai master + sumber profil; seeder mencocokkan lewat
    NAMA. Jadi yang dilarang adalah dua entitas berbeda yang menyamar dengan nama
    sama — bukan tabrakan namanya sendiri (sekarang memang seluruh 60 baris
    muncul di kedua berkas).
    """
    canonical = _canonical_suppliers()
    assert len(canonical) == 60
    canonical_names = {item["name"] for item in canonical}
    stored = {
        name
        for name in conn.execute(text("SELECT name FROM suppliers")).scalars()
    }
    assert canonical_names <= stored, f"pemasok kanonik hilang: {canonical_names - stored}"

    by_name = {item["name"]: item for item in canonical}
    for row in load_demo_rows():
        canon = by_name.get(row["name"])
        if canon is None:
            continue
        assert row["location"] == canon["location"], row["name"]
        assert float(row["reliability_score"]) == float(canon["reliability_score"]), row["name"]


def test_canonical_supplier_scores_match_seed_json(conn):
    """Skor pemasok kanonik = nilai di `sprint1_seed.json` (tidak ada drift).

    Temuan Fase 2 (2026-10-14): tiga pemasok Cianjur di DB demo memakai nilai
    default kolom (0.80), bukan skor JSON (0.92/0.88/0.81). Sebabnya loader seed
    hanya MENAMBAH bila nama belum ada (`if item["name"] not in sup_by_name`).

    DIPERBAIKI di loader (baris warisan dikoreksi ke skor berkas kanonik) dan
    dipaku di sini: penyimpangan sekecil apa pun langsung merah, karena skor ini
    bukan hiasan — ia masuk ke pemilihan pemasok mesin rekomendasi.
    """
    canonical = _canonical_suppliers()
    json_scores = {item["name"]: float(item["reliability_score"]) for item in canonical}
    stored = {
        name: float(score)
        for name, score in conn.execute(
            text("SELECT name, reliability_score FROM suppliers")
        ).all()
        if name in json_scores
    }
    assert stored == json_scores


def test_supplier_ids_are_unique_and_stable(conn):
    """Id pemasok unik dan TIDAK berubah saat berkas demo dimuat ulang.

    Koreksi penting: di checkout ini pemuat membuat baris `suppliers` dengan
    UUID v4 dari DB (bukan UUID5 dari nama), jadi "natural key" bukan invariant
    yang berlaku. Yang benar-benar dijaga: tidak ada id kembar, dan menjalankan
    seeder lagi tidak mengganti id mana pun — id itu dirujuk `batches`,
    `price_signals`, dan PO mock.
    """
    import asyncio

    from app.seed.suppliers_demo import seed_demo_suppliers

    sebelum = {
        name: str(sid)
        for name, sid in conn.execute(text("SELECT name, id FROM suppliers")).all()
    }
    assert len(sebelum) == len(set(sebelum.values())), "ada id pemasok kembar"
    assert len(sebelum) == len(load_demo_rows())

    asyncio.run(seed_demo_suppliers())
    conn.rollback()
    sesudah = {
        name: str(sid)
        for name, sid in conn.execute(text("SELECT name, id FROM suppliers")).all()
    }
    assert sesudah == sebelum


def test_demo_seeding_is_purely_additive():
    """Menjalankan seeder pemasok demo TIDAK mengubah satu pun baris non-demo.

    Inilah jaminan yang penting untuk data kanonik (rencana Fase 2 butir C3):
    data demo aditif. Dibandingkan potret SEBELUM vs SESUDAH, bukan dugaan —
    urutannya: seed → potret → seed lagi → potret.
    """
    import asyncio

    from app.seed.suppliers_demo import seed_demo_suppliers

    demo_names = tuple(row["name"] for row in load_demo_rows())
    engine = create_engine(DB_URL)
    snapshot_sql = text(
        "SELECT id, name, location_id, reliability_score, commodity_id, latitude, "
        "longitude, capacity_kg_per_week, certification_status, address, contact_name "
        "FROM suppliers WHERE name <> ALL(:names) ORDER BY name"
    )
    semua_sql = text(
        "SELECT id, name, location_id, reliability_score, commodity_id, latitude, "
        "longitude, capacity_kg_per_week, certification_status, address, contact_name "
        "FROM suppliers ORDER BY name"
    )
    try:
        asyncio.run(seed_demo_suppliers())
        with engine.connect() as c:
            # Sejak berkas demo = master, TIDAK ada baris non-demo yang perlu
            # dijaga — invariant lama "14 baris non-demo tetap utuh" menjadi
            # vacuous. Yang tetap bermakna: seeder tidak mengubah ISI tabel.
            sisa = c.execute(snapshot_sql, {"names": list(demo_names)}).all()
            assert len(sisa) == 0, f"ada baris pemasok di luar berkas demo: {len(sisa)}"
            before = c.execute(semua_sql).all()
        asyncio.run(seed_demo_suppliers())
        with engine.connect() as c:
            after = c.execute(semua_sql).all()
        assert [tuple(r) for r in before] == [tuple(r) for r in after]
    finally:
        engine.dispose()


def test_every_demo_row_exists_in_db(conn):
    """Setiap baris berkas demo punya baris DB bernama SAMA (tanpa duplikat).

    Seeder mencocokkan lewat NAMA, jadi nama adalah kunci alami yang berlaku —
    bukan id. Dua baris dengan nama sama akan saling menimpa profil, dan baris
    berkas yang tidak ada di DB berarti profil (koordinat/kapasitas) hilang.
    """
    rows = conn.execute(text("SELECT name FROM suppliers")).all()
    nama_db = [r[0] for r in rows]
    assert len(nama_db) == len(set(nama_db)), "ada nama pemasok ganda"
    assert set(nama_db) == {r["name"] for r in load_demo_rows()}


def test_seeding_is_idempotent_against_live_db():
    """Menjalankan seeder dua kali: tidak ada baris baru, isi tetap 38."""
    import asyncio

    from app.seed.suppliers_demo import seed_demo_suppliers

    first = asyncio.run(seed_demo_suppliers())
    second = asyncio.run(seed_demo_suppliers())
    assert first["created"] == 0 and first["updated"] == len(load_demo_rows())
    assert second["created"] == 0 and second["updated"] == len(load_demo_rows())

    engine = create_engine(DB_URL)
    try:
        with engine.connect() as c:
            total = c.execute(text("SELECT count(*) FROM suppliers")).scalar_one()
    finally:
        engine.dispose()
    # Tidak ada lagi 14 baris kanonik legacy: berkas demo = master, jadi jumlah
    # baris tabel = jumlah baris berkas.
    assert total == len(load_demo_rows())


def test_demo_suppliers_are_flagged_synthetic():
    """Berkas data harus menyatakan dirinya sintetis — jangan sampai dikira data nyata."""
    path = Path(os.environ.get("DEMO_SUPPLIERS_PATH", "")) if os.environ.get(
        "DEMO_SUPPLIERS_PATH"
    ) else None
    candidates = [path] if path else []
    candidates += [
        Path("/data/seed/suppliers_demo.json"),
        Path(__file__).resolve().parents[2] / "data" / "seed" / "suppliers_demo.json",
    ]
    target = next(p for p in candidates if p and p.exists())
    with open(target, encoding="utf-8") as f:
        meta = json.load(f)["_meta"]
    assert "SINTETIS" in meta["provenance"]
    # Berkas demo kini MASTER (bukan overlay koordinat di atas 14 kanonik), jadi
    # yang diperiksa adalah pernyataan itu — bukan kalimat lama
    # "canonical_untouched" yang sudah tidak menggambarkan datanya.
    assert "SAMA" in meta["canonical_overlap"]
    assert "ABSOLUT" in meta["coordinates"]
