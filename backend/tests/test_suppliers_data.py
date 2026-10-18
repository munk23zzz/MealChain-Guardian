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
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.seed.seed_data import stable_uuid
from app.seed.suppliers_demo import (
    OFFSETS,
    REACH_KM_MAX,
    demo_supplier_id,
    haversine_km,
    load_demo_rows,
)

DB_URL = "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"

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
    """21 baris = 12 klaster Jakarta + 9 hub lain (satu per hub) — Fase 7.

    Angka dulu (Fase 2): 30 baris = 3 per hub × 10 kota. Yang berubah SADAR di
    Fase 7 (permintaan pemilik 2026-10-15): klaster Jakarta diperbesar dan
    dijadikan berjenjang, hub lain cukup satu pemasok lokal.

    Komoditas ke-4 (beras) menambah 3 baris (1 klaster Jakarta + 2 hub) yang
    sekaligus menjadi overlay koordinat bagi pemasok kanonik bernama sama.
    """
    rows = load_demo_rows()
    assert len(rows) == 24, "13 pemasok klaster Jakarta + 11 baris hub lain"

    per_hub: dict[str, int] = {}
    per_commodity: dict[str, int] = {}
    for row in rows:
        per_hub[row["location"]] = per_hub.get(row["location"], 0) + 1
        per_commodity[row["commodity"]] = per_commodity.get(row["commodity"], 0) + 1

    assert len(per_hub) == 10, "semua 10 lokasi harus punya pemasok"
    assert per_hub["Jakarta"] == 13, f"klaster Jakarta harus 13 baris: {per_hub}"
    assert min(per_hub.values()) >= 1, f"ada hub tanpa pemasok: {per_hub}"
    assert per_commodity == {"ayam": 5, "beras": 3, "telur": 6, "wortel": 10}

    # Klaster Jakarta WAJIB berkoordinat absolut: jaraknya ke SPPG Jakarta yang
    # diperiksa (aturan "terjangkau"), bukan geseran kecil dari titik hub.
    jakarta = [r for r in rows if r["location"] == "Jakarta"]
    assert all("latitude" in r and "longitude" in r for r in jakarta)
    lainnya = [r for r in rows if r["location"] != "Jakarta"]
    assert all("latitude" not in r and "offset_index" in r for r in lainnya)

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
    # Tetangga terdekat sekarang "Beras Makmur Jakarta" (0,6 km dari titik SPPG).
    assert min(distances, key=lambda n: distances[n]) == "Beras Makmur Jakarta"
    assert max(distances, key=lambda n: distances[n]) == "Wortel Lestari Subang"


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
    assert len(low) == 4, f"harus ada 4 pemasok berisiko, ada {len(low)}"
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
    assert total == 14 + len(load_demo_rows())
    assert with_coords == total


def test_coordinates_land_in_indonesia(conn):
    rows = conn.execute(
        text("SELECT name, latitude, longitude FROM suppliers")
    ).all()
    for name, lat, lon in rows:
        assert LAT_RANGE[0] <= float(lat) <= LAT_RANGE[1], f"{name} lat di luar Indonesia"
        assert LON_RANGE[0] <= float(lon) <= LON_RANGE[1], f"{name} lon di luar Indonesia"


def test_demo_supplier_sits_near_its_hub(conn):
    """Baris demo ber-offset = titik hub + geseran kecil (≤0.05°).

    Sejak Fase 7 klaster Jakarta memakai koordinat ABSOLUT (kota penyangga),
    jadi aturan "dekat hub" hanya berlaku untuk baris yang memakai
    `offset_index` — sisanya diperiksa oleh tes jarak di atas/di bawah.
    """
    offset_names = [r["name"] for r in load_demo_rows() if "offset_index" in r]
    assert offset_names
    rows = conn.execute(
        text(
            "SELECT s.name, s.latitude, s.longitude, l.latitude, l.longitude "
            "FROM suppliers s JOIN locations l ON l.id = s.location_id "
            "WHERE s.name = ANY(:names)"
        ),
        {"names": offset_names},
    ).all()
    assert len(rows) == len(offset_names)
    for name, lat, lon, hub_lat, hub_lon in rows:
        assert abs(float(lat) - float(hub_lat)) <= 0.05, f"{name} terlalu jauh dari hub-nya"
        assert abs(float(lon) - float(hub_lon)) <= 0.05, f"{name} terlalu jauh dari hub-nya"


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
    """17 nama pemasok kanonik harus tetap ada; tabrakan nama harus identik.

    Berkas demo juga dipakai sebagai OVERLAY KOORDINAT: seeder mencocokkan
    lewat nama, jadi tiga pemasok beras kanonik (Jakarta/Bogor/Cianjur) memang
    muncul di kedua berkas. Yang dilarang bukan tabrakan nama, melainkan
    tabrakan yang menyembunyikan entitas berbeda — jadi profilnya wajib sama.
    """
    canonical = _canonical_suppliers()
    assert len(canonical) == 17
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


def test_canonical_supplier_ids_are_legacy_random_uuids(conn):
    """Keadaan yang DIKETAHUI, bukan yang diinginkan: 14 id kanonik bukan UUID5.

    `build_seed_rows` menghitung `stable_uuid("supplier", nama)`, tetapi baris
    kanonik di DB demo sudah ada lebih dulu dengan UUID v4 acak, dan loader tidak
    menimpa id (mengganti primary key berarti menulis ulang seluruh FK yang
    menunjuknya: `batches`, `price_signals`, `supply_records`).

    Jadi id kanonik = "opaque tapi stabil", bukan natural key. Tes ini memaku
    keadaannya supaya perubahan id (mis. kelak dirapikan lewat migrasi khusus)
    terjadi sadar, bukan menyelinap.
    """
    canonical = _canonical_suppliers()
    rows = {
        name: uuid.UUID(str(sid))
        for name, sid in conn.execute(
            text("SELECT name, id FROM suppliers")
        ).all()
    }
    natural = {item["name"]: stable_uuid("supplier", item["name"]) for item in canonical}
    mismatched = {name for name, want in natural.items() if rows.get(name) != want}
    assert mismatched == set(natural), (
        "sebagian id kanonik ternyata sudah natural key — perbarui tes ini "
        f"(yang cocok: {sorted(set(natural) - mismatched)})"
    )


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
    try:
        asyncio.run(seed_demo_suppliers())
        with engine.connect() as c:
            before = c.execute(snapshot_sql, {"names": list(demo_names)}).all()
        assert len(before) == 14
        asyncio.run(seed_demo_suppliers())
        with engine.connect() as c:
            after = c.execute(snapshot_sql, {"names": list(demo_names)}).all()
        assert [tuple(r) for r in before] == [tuple(r) for r in after]
    finally:
        engine.dispose()


def test_demo_rows_use_their_natural_key_ids(conn):
    """Pemasok demo (24 baris): id = UUID5 `demo_supplier::<nama>`, tanpa tabrakan."""
    rows = conn.execute(text("SELECT id, name FROM suppliers")).all()
    stored = {str(r.id): r.name for r in rows}
    overlay = {item["name"] for item in _canonical_suppliers()}
    demo_ids = {}
    for row in load_demo_rows():
        if row["name"] in overlay:
            # Baris overlay (3 pemasok beras) menempati id KANONIK — seeder
            # mencocokkan lewat nama. Yang penting barisnya ada, bukan id demo.
            assert row["name"] in stored.values(), row["name"]
            continue
        expected = str(demo_supplier_id(row["name"]))
        assert stored.get(expected) == row["name"], f"id demo tidak sesuai: {row['name']}"
        demo_ids[expected] = row["name"]
    others = {i for i in stored if i not in demo_ids}
    assert not (set(demo_ids) & others), "id demo bertabrakan dengan baris non-demo"
    assert len(others) == len(_canonical_suppliers())


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
    assert total == 14 + len(load_demo_rows())


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
    assert "TIDAK diubah" in meta["canonical_untouched"]
