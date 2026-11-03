"""Acceptance test Sprint 1 (Task 13) — bukti hard constraint + endpoint.

Semua assertion dijalankan terhadap PostgreSQL hasil migration + seed dan
FastAPI app nyata. Ini bukti automated untuk docs/verification/sprint-1.md.
"""

import uuid as uuidlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.constraints import check_capacity, check_delivery_window
from app.core.forecasting_fallback import statistical_forecast
from app.core.freshness import classify_freshness
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


@pytest.fixture()
def national_client(monitor_headers):
    """Klien baca NAsional untuk nilai lintas lokasi.

    Ruling 2026-10-14: kepala SPPG Jakarta hanya boleh membaca lokasinya
    sendiri, jadi nilai Cianjur/Bogor (jangkar docs/verification/sprint-1.md)
    dibaca sebagai bgn_monitor — peran yang memang berhak lintas lokasi.
    Endpoint yang mengubah data tetap memakai `client` (peran approver).
    """
    with TestClient(app) as c:
        c.headers.update(monitor_headers)
        yield c


def test_acceptance_1_freshness_boundaries():
    """Freshness 0.85 PASS; 0.60 NEEDS_VERIFICATION; 0.599999 FAIL."""
    assert classify_freshness(0.85) == "pass"
    assert classify_freshness(0.849999) == "needs_verification"
    assert classify_freshness(0.60) == "needs_verification"
    assert classify_freshness(0.599999) == "fail"


def test_acceptance_2_safety_fail_not_overridable_via_api(client):
    """Safety FAIL tidak bisa diubah lewat API input lain — batch excursion
    tetap FAIL setelah evaluasi ulang dengan payload berbeda-beda."""
    with create_engine(DB_URL).connect() as conn:
        batch_id = str(
            conn.execute(
                text(
                    # Pilih batch KANONIK secara eksplisit: `LIMIT 1` tanpa
                    # filter dulu mengambil batch hasil penyemai demo (tanpa
                    # excursion) begitu sesi lain menambah baris, sehingga tes
                    # merah walau aturan safety-nya benar.
                    # Batch yang PROFILNYA memang gagal safety: pasangan
                    # (Surabaya, telur) ber-`safety_fail` di generator dan lot
                    # 1-nya ber-`safety_status='fail'`. Memilih batch Surabaya
                    # pertama (ORDER BY id) kini bisa lot sehat → evaluasi
                    # menjawab PASS dan tes gagal walau aturannya benar.
                    "SELECT b.id FROM batches b "
                    "JOIN locations l ON l.id=b.location_id "
                    "JOIN commodities c ON c.id=b.commodity_id "
                    "WHERE l.name='Surabaya' AND c.name='telur' "
                    "AND b.origin='seed' AND b.safety_status='fail' "
                    "ORDER BY b.harvested_at, b.id LIMIT 1"
                )
            ).scalar_one()
        )
    r1 = client.post("/safety/evaluate", json={"batch_id": batch_id})
    r2 = client.post("/safety/evaluate", json={"batch_id": batch_id, "extra": "junk"})
    assert r1.json()["safety_status"] == "FAIL"
    assert r2.status_code in (200, 422)
    if r2.status_code == 200:
        assert r2.json()["safety_status"] == "FAIL"


def test_acceptance_3a_capacity_constraint():
    result = check_capacity(available_kg=500, required_kg=500)
    assert result["sufficient"] is True
    assert check_capacity(available_kg=400, required_kg=500)["sufficient"] is False


def test_acceptance_3b_delivery_window_constraint():
    assert check_delivery_window(150.0, 150.0) is True
    assert check_delivery_window(151.0, 150.0) is False


def test_acceptance_4_seed_dataset_10x4_and_locked_values(national_client):
    """Seed 10×4 dan angka kanonik Cianjur/Jakarta/Bogor tetap terkunci.

    Komoditas keempat (beras) masuk di commit "Beras: komoditas keempat", jadi
    yang dikunci di sini adalah 10 lokasi × 4 komoditas — angka kanonik telur
    tidak berubah.
    """
    with create_engine(DB_URL).connect() as conn:
        n_loc = conn.execute(text("SELECT COUNT(*) FROM locations")).scalar()
        n_com = conn.execute(text("SELECT COUNT(*) FROM commodities")).scalar()
        assert n_loc == 10
        assert n_com == 4
        # Nilai kanonik DIKUNCI pada baris seed (`origin='seed'`) dan dibaca
        # langsung dari DB — bukan lewat endpoint: `/supply/*` mengembalikan
        # baris TERBARU, dan sejak deret aktual demo diperluas sampai 5 Nov
        # (`ACTUAL_REF` di app/seed/timeseries.py) baris terbaru tiap lokasi
        # adalah baris demo 4 Nov, bukan snapshot kanonik 8 Okt.
        locked = {
            name: float(qty)
            for name, qty in conn.execute(
                text(
                    "SELECT l.name, s.quantity_kg FROM supply_records s"
                    " JOIN locations l ON l.id = s.location_id"
                    " JOIN commodities c ON c.id = s.commodity_id"
                    " WHERE c.name = 'telur' AND s.origin = 'seed'"
                )
            )
        }
    # Satu baris kanonik per lokasi (tanpa duplikat yang tertelan dict):
    assert len(locked) == 10
    assert locked["Cianjur"] == 1400.0
    assert locked["Jakarta"] == 300.0
    assert locked["Bogor"] == 800.0
    # Endpoint tetap hidup — ia menyajikan baris terbaru, bukan angka kanonik:
    assert national_client.get("/supply/Cianjur/telur").status_code == 200


def test_acceptance_5_all_sprint1_endpoints_live(client, monitor_headers):
    """Seluruh endpoint Sprint 1 dipanggil terhadap PostgreSQL migration+seed."""
    paths = [
        ("GET", "/supply/Cianjur/telur", None),
        ("GET", "/demand/Jakarta/telur", None),
        ("GET", "/demand/forecast/Jakarta/telur", None),
        ("GET", "/price/Cianjur/telur", None),
    ]
    for method, path, _ in paths:
        # Rute lintas lokasi dibaca sebagai bgn_monitor (Ruling 2026-10-14).
        # Header ditimpa per-permintaan: dua TestClient dalam satu test
        # menabrak loop asyncpg yang berbeda.
        resp = client.get(path, headers=monitor_headers)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code}"
    posts = [
        ("/freshness/evaluate", {"batch_id": _any_batch_id()}),
        ("/safety/evaluate", {"batch_id": _any_batch_id()}),
        (
            "/price/deviation",
            {"location": "Cianjur", "commodity": "telur", "supplier_price": 32000},
        ),
        (
            "/logistics/estimate",
            {"source": "Cianjur", "target": "Jakarta", "quantity_kg": 500,
             "delivery_window_min": 150},
        ),
    ]
    for path, payload in posts:
        resp = client.post(path, json=payload)
        assert resp.status_code == 200, f"POST {path} → {resp.status_code}: {resp.text}"


def _any_batch_id() -> str:
    with create_engine(DB_URL).connect() as conn:
        return str(
            conn.execute(text("SELECT id FROM batches ORDER BY created_at LIMIT 1")).scalar_one()
        )


def test_acceptance_6_mock_sap_header(national_client):
    resp = national_client.get("/supply/Cianjur/telur")
    assert resp.headers.get("X-Data-Source") == "MOCK"


def test_acceptance_7_forecast_fallback_label(client):
    resp = client.get("/demand/forecast/Jakarta/telur")
    assert resp.json()["method"] == "statistical_fallback"


def test_acceptance_missing_batch_404(client):
    resp = client.post("/freshness/evaluate", json={"batch_id": str(uuidlib.uuid4())})
    assert resp.status_code == 404


def test_acceptance_price_anomaly_supplier_c(client):
    resp = client.post(
        "/price/deviation",
        json={"location": "Cianjur", "commodity": "telur", "supplier_price": 32000},
    )
    assert resp.json()["classification"] == "anomalous"
    assert resp.json()["flagged"] is True


def test_acceptance_logistics_boundary(client):
    resp = client.post(
        "/logistics/estimate",
        json={
            "source": "Cianjur",
            "target": "Jakarta",
            "quantity_kg": 500,
            "delivery_window_min": 150,
        },
    )
    assert resp.json()["feasible"] is True


def test_acceptance_forecast_flat_math():
    result = statistical_forecast([100.0, 100.0, 100.0], horizon_days=7)
    assert result["forecast_qty_kg"] == pytest.approx(700.0)
