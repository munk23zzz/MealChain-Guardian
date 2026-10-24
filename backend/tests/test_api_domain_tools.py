"""Test API freshness/safety/price/logistics (Task 12, plan Sprint 1)."""

import uuid as uuidlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app
from tests.dsn import DSN_ASYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_ASYNC.replace(
    "+asyncpg", "+psycopg"
)


@pytest.fixture()
def client(auth_headers):
    with TestClient(app) as c:
        c.headers.update(auth_headers)
        yield c


def _db():
    return create_engine(DB_URL)


def _db_latest_reference_price(location: str, commodity: str):
    """Harga acuan TERBARU untuk (lokasi, komoditas) — dibaca langsung dari DB.

    Acuan diambil dari DB, bukan dipaku ke angka kanonik seed: deret aktual
    (pasokan & harga) diperluas sampai 5 Nov lewat ACTUAL_REF, terpisah dari
    CANONICAL_REF 8 Okt yang tetap jangkar kasus. Konsekuensinya 'record
    terbaru' bukan lagi baris 8 Okt, jadi tes yang memaku 26500.0 pecah.
    Query kecil ini meniru kontrak endpoint (source pihps_reference,
    ORDER BY recorded_at DESC LIMIT 1) sehingga tes tetap sahih saat deret
    diperluas lagi.
    """
    with _db().connect() as conn:
        return conn.execute(
            text(
                "SELECT ps.price_per_kg FROM price_signals ps "
                "JOIN locations l ON l.id = ps.location_id "
                "JOIN commodities c ON c.id = ps.commodity_id "
                "WHERE l.name = :loc AND c.name = :com "
                "AND ps.source = 'pihps_reference' "
                "ORDER BY ps.recorded_at DESC LIMIT 1"
            ),
            {"loc": location, "com": commodity},
        ).scalar_one()


def _batch_id_by_quantity(quantity: float) -> str:
    """Batch dengan kuantitas tertentu; jatuh ke batch pertama bila tak ada.

    Kuantitas batch seed dibangkitkan relatif `now` setiap "Segarkan ke hari
    ini", jadi angka pasti (mis. 500 kg) tidak dijamin ada — dan yang diuji di
    sini adalah penolakan `as_of`, bukan angka kuantitasnya.
    """
    with _db().connect() as conn:
        row = conn.execute(
            text(
                "SELECT b.id FROM batches b WHERE b.quantity_kg = :q "
                "ORDER BY b.created_at LIMIT 1"
            ),
            {"q": quantity},
        ).scalar_one_or_none()
        if row is None:
            row = conn.execute(
                text("SELECT b.id FROM batches b ORDER BY b.created_at LIMIT 1")
            ).scalar_one()
        return str(row)


def test_freshness_evaluate_pass_band_persists(client):
    """Pass-band memakai batch milik test sendiri dengan harvested_at relatif
    terhadap now() — time-bomb: batch seed punya harvested_at tetap, decay
    mengikuti jam nyata sehingga lama-lama turun ke bawah 0.85 (terjadi
    2026-10-05: 0.83). Pola perbaikan flaky yang sama dengan ruling
    2026-10-03: seleksi deterministik, bukan bergantung state seed + waktu.
    """
    with _db().begin() as conn:
        batch_id = str(
            conn.execute(
                text(
                    "INSERT INTO batches (commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log) "
                    "SELECT c.id, l.id, (SELECT id FROM suppliers LIMIT 1), "
                    "499.99, now() - interval '30 minutes', '[]'::jsonb "
                    "FROM commodities c, locations l "
                    "WHERE c.name = 'telur' AND l.name = 'Bogor' "
                    "RETURNING id"
                )
            ).scalar_one()
        )
    try:
        resp = client.post("/freshness/evaluate", json={"batch_id": batch_id})
        assert resp.status_code == 200
        body = resp.json()
        assert 0.85 <= body["freshness_score"] <= 1.0
        assert body["status"] == "pass"
        assert "usable_until" in body
        # Persistence (Schema.md batches hanya punya freshness_score + usable_until;
        # status diturunkan ulang deterministik dari score — ruling 2026-10-03)
        with _db().connect() as conn:
            stored = conn.execute(
                text(
                    "SELECT freshness_score, usable_until FROM batches WHERE id = :id"
                ),
                {"id": batch_id},
            ).fetchone()
        assert float(stored[0]) == pytest.approx(body["freshness_score"], abs=1e-9)
        assert stored[1].isoformat() == body["usable_until"]
    finally:
        with _db().begin() as conn:
            conn.execute(
                text("DELETE FROM batches WHERE id = :id"), {"id": batch_id}
            )


def test_freshness_evaluate_fail_band(client):
    """Batch yang JELAS basi → status `fail`.

    Dulu tes ini memilih batch seed ber-`freshness_score < 0.60` dari DB. Itu
    time-bomb: skornya adalah nilai SIMPANAN dari penyemaian lama, sedangkan
    `/freshness/evaluate` MENGHITUNG ULANG dari `harvested_at` relatif sekarang.
    Begitu data demo dibangun ulang ke tanggal hari ini (24 Okt 2026), batch itu
    jadi segar dan hasilnya `needs_verification` — tes merah padahal endpoint benar.
    Batch sekarang dibuat tes sendiri dengan umur 30 hari, jadi hasilnya tidak
    bergantung pada state seed maupun jam pemakaian.
    """
    with _db().begin() as conn:
        batch_id = str(
            conn.execute(
                text(
                    "INSERT INTO batches (commodity_id, location_id, supplier_id, "
                    "quantity_kg, harvested_at, temperature_log) "
                    "SELECT c.id, l.id, (SELECT id FROM suppliers LIMIT 1), "
                    "498.77, now() - interval '30 days', '[]'::jsonb "
                    "FROM commodities c, locations l "
                    "WHERE c.name = 'ayam' AND l.name = 'Semarang' "
                    "RETURNING id"
                )
            ).scalar_one()
        )
    try:
        resp = client.post("/freshness/evaluate", json={"batch_id": batch_id})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["freshness_score"] < 0.60, body
        assert body["status"] == "fail", body
    finally:
        with _db().begin() as conn:
            conn.execute(text("DELETE FROM batches WHERE id = :id"), {"id": batch_id})


def test_freshness_as_of_rejected_when_not_demo(client):
    batch_id = _batch_id_by_quantity(500)
    resp = client.post(
        "/freshness/evaluate",
        json={"batch_id": batch_id, "as_of": "2026-10-01T12:00:00+00:00"},
    )
    assert resp.status_code == 403


def test_freshness_missing_batch_404(client):
    random_id = str(uuidlib.uuid4())
    resp = client.post("/freshness/evaluate", json={"batch_id": random_id})
    assert resp.status_code == 404


def test_safety_evaluate_fail_persists_uppercase(client):
    # Batch Surabaya kanonik (seed) dengan riwayat suhu buruk. `origin='seed'`
    # memisahkan dari batch demo/tes lain yang bisa lebih dulu terbaca.
    with _db().connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    # Batch yang MEMANG punya penyimpangan suhu: pasangan
                    # (Surabaya, telur) profil `safety_fail` di generator, dan
                    # lot 1-nya ber-`safety_status='fail'`. Dulu tes memilih
                    # batch Surabaya PERTAMA, yang kini bisa lot sehat sehingga
                    # evaluasi menjawab PASS.
                    "SELECT b.id FROM batches b "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "JOIN locations l ON l.id = b.location_id "
                    "WHERE l.name = 'Surabaya' AND c.name = 'telur' "
                    "AND b.origin = 'seed' AND b.safety_status = 'fail' "
                    "ORDER BY b.harvested_at LIMIT 1"
                )
            ).scalar_one()
        )
    resp = client.post("/safety/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_status"] == "FAIL"
    assert body["excursion_minutes"] >= 30
    assert isinstance(body["reasons"], list)
    # DB lowercase
    with _db().connect() as conn:
        stored = conn.execute(
            text("SELECT safety_status FROM batches WHERE id = :id"),
            {"id": batch_id},
        ).scalar_one()
    assert stored == "fail"


def test_safety_evaluate_pass_clean_batch(client):
    with _db().connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    # Batch BARANG DINGIN yang sehat: beras (26-28 C) tidak
                    # punya gerbang rantai dingin sehingga evaluasinya
                    # NEEDS_VERIFICATION, dan lot kedua bisa berprofil lain.
                    "SELECT b.id FROM batches b "
                    "JOIN locations l ON l.id = b.location_id "
                    "JOIN commodities c ON c.id = b.commodity_id "
                    "WHERE l.name = 'Bogor' AND c.name IN ('telur','ayam','wortel') "
                    "AND b.origin = 'seed' AND b.safety_status = 'pass' "
                    "ORDER BY b.harvested_at, b.id LIMIT 1"
                )
            ).scalar_one()
        )
    resp = client.post("/safety/evaluate", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_status"] == "PASS"
    assert body["excursion_minutes"] == 0.0


def test_safety_missing_batch_404(client):
    resp = client.post("/safety/evaluate", json={"batch_id": str(uuidlib.uuid4())})
    assert resp.status_code == 404


def test_price_latest_reference(client, monitor_headers):
    # Cianjur = lokasi lain; dibaca sebagai bgn_monitor (Ruling 2026-10-14).
    # Maksud tes: endpoint mengembalikan baris referensi TERBARU. Acuan
    # diturunkan dari DB (baris terbaru) supaya tidak pecah saat deret aktual
    # diperluas sampai 5 Nov — sumber baris demo tetap 'pihps_reference'.
    expected_price = _db_latest_reference_price("Cianjur", "telur")
    resp = client.get("/price/Cianjur/telur", headers=monitor_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["price_per_kg"] == float(expected_price)
    assert body["source"] == "pihps_reference"


def test_price_unknown_404(client):
    assert client.get("/price/Atlantis/telur").status_code == 404


def test_price_deviation_supplier_c_flagged(client):
    # reference_price = baris harga terbaru di DB (bukan 26500.0 kanonik 8 Okt).
    expected_reference = _db_latest_reference_price("Cianjur", "telur")
    resp = client.post(
        "/price/deviation",
        json={"location": "Cianjur", "commodity": "telur", "supplier_price": 32000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reference_price"] == float(expected_reference)
    # supplier 32000 vs acuan terbaru ≈ 26951.37 → deviasi ≈ +18.7% (≥ 15%)
    # sehingga tetap anomalous/flagged.
    assert body["classification"] == "anomalous"
    assert body["flagged"] is True


def test_price_deviation_normal(client):
    resp = client.post(
        "/price/deviation",
        json={"location": "Cianjur", "commodity": "telur", "supplier_price": 26200},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification"] == "normal"
    assert body["flagged"] is False


def test_logistics_estimate_cianjur_jakarta(client):
    resp = client.post(
        "/logistics/estimate",
        json={
            "source": "Cianjur",
            "target": "Jakarta",
            "quantity_kg": 500,
            "delivery_window_min": 150,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["distance_km"] == 120
    assert body["estimated_time_min"] == 150
    assert body["feasible"] is True


def test_logistics_boundary_over_window_infeasible(client):
    resp = client.post(
        "/logistics/estimate",
        json={
            "source": "Cianjur",
            "target": "Jakarta",
            "quantity_kg": 500,
            "delivery_window_min": 149,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["feasible"] is False


def test_logistics_unknown_location_422_or_404(client):
    resp = client.post(
        "/logistics/estimate",
        json={"source": "Atlantis", "target": "Jakarta", "quantity_kg": 100},
    )
    assert resp.status_code in (404, 422)


def test_malformed_payload_422(client):
    assert client.post("/freshness/evaluate", json={}).status_code == 422
    assert client.post("/safety/evaluate", json={}).status_code == 422
    assert client.post("/logistics/estimate", json={"source": "Cianjur"}).status_code == 422
    assert client.post("/price/deviation", json={"location": "Cianjur"}).status_code == 422


def test_batch_id_tidak_sah_422_bukan_500(client):
    """batch_id kosong/bukan UUID harus ditolak skema, bukan meledak jadi 500.

    Dulu tipenya `str` dan diteruskan apa adanya ke asyncpg: pengguna yang salah
    kirim id mendapat 500 "invalid UUID". Terukur di audit 2026-10-22.
    """
    for batch_id in ("", "bukan-uuid", "12345"):
        for jalur in ("/freshness/evaluate", "/safety/evaluate"):
            resp = client.post(jalur, json={"batch_id": batch_id})
            assert resp.status_code == 422, f"{jalur} batch_id={batch_id!r} -> {resp.status_code}"


def test_router_no_domain_duplication():
    """Router tidak memuat rumus domain — semua lewat core."""
    import inspect

    import app.api.freshness as fmod
    import app.api.logistics as lmod
    import app.api.price as pmod
    import app.api.safety as smod

    for mod in (fmod, smod, pmod, lmod):
        src = inspect.getsource(mod)
        assert "0.85" not in src.replace("#", ""), f"{mod.__name__} hardcode threshold"
        assert "* 60" not in src, f"{mod.__name__} duplikasi rumus waktu"
