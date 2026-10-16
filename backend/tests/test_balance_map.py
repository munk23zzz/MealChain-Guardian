"""S4-06 polish (arah Roy 2026-10-08): dashboard map Indonesia + grafik.

TDD RED dulu — endpoint read-only `GET /balance/map?commodity=telur`:
- Satu panggilan memberi kondisi REAL semua lokasi (supply/demand terbaru
  per lokasi, formula `calculate_supply_gap` yang sama dengan panel
  snapshot — TIDAK ada rumus kedua).
- Read-only: get_current_user (JWT) — semua role boleh baca; 401 unauth.
- 404 komoditas tak dikenal; lokasi tanpa data → zeros (bukan 404) agar
  map tetap lengkap.
- (Ruling 2026-10-14) peta ikut tercakup: peran SPPG hanya menerima lokasinya
  sendiri, bgn_monitor tetap menerima seluruh lokasi nasional.
- Response menyertakan lat/long dari DB (bukan koordinat karangan FE).
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import app

DB_URL = (
    "postgresql+psycopg://mealchain:mealchain_local@postgres:5432/mealchain"
)
COMMODITY = "telur"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _seed_location(com_name: str, supply_kg: float, demand_kg: float):
    """Buat lokasi test terisolasi dengan data supply/demand sendiri."""
    key = f"map-{uuid.uuid4()}"
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            loc_id = conn.execute(
                text(
                    "INSERT INTO locations (name, region, latitude, longitude)"
                    " VALUES (:n, :r, :la, :lo) RETURNING id"
                ),
                {
                    "n": f"TEST-{key[:12]}",
                    "r": "Test Region",
                    "la": -6.2,
                    "lo": 106.8,
                },
            ).scalar_one()
            com_id = conn.execute(
                text("SELECT id FROM commodities WHERE name=:n"),
                {"n": com_name},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO supply_records (location_id, commodity_id,"
                    " quantity_kg, recorded_at, source)"
                    " VALUES (:l, :c, :q, now(), 'manual')"
                ),
                {"l": loc_id, "c": com_id, "q": supply_kg},
            )
            conn.execute(
                text(
                    "INSERT INTO demand_records (location_id, commodity_id,"
                    " quantity_kg, needed_by, recorded_at, seed_key)"
                    " VALUES (:l, :c, :q, now(), now(), :k)"
                ),
                {"l": loc_id, "c": com_id, "q": demand_kg, "k": key},
            )
    finally:
        engine.dispose()
    return key, loc_id


def _cleanup(loc_id) -> None:
    """Hapus residu test FK-safe."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM supply_records WHERE location_id=:l"),
                {"l": loc_id},
            )
            conn.execute(
                text("DELETE FROM demand_records WHERE location_id=:l"),
                {"l": loc_id},
            )
            conn.execute(
                text("DELETE FROM locations WHERE id=:l"), {"l": loc_id}
            )
    finally:
        engine.dispose()


def _latest_quantity_kg(table: str, location: str, commodity: str) -> float:
    """Nilai baris TERBARU per lokasi×komoditas, dibaca dari DB yang sama.

    Dipakai sebagai ACUAN (bukan angka kanonik yang dipaku): sejak deret aktual
    demo diperluas sampai 5 Nov (`ACTUAL_REF` di app/seed/timeseries.py), baris
    terbaru Jakarta/telur bukan lagi snapshot kanonik 8 Okt. Urutan pilih baris
    sama persis dengan endpoint (`recorded_at DESC, id DESC`).
    """
    engine = create_engine(DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT r.quantity_kg FROM {table} r"
                    " JOIN locations l ON l.id = r.location_id"
                    " JOIN commodities c ON c.id = r.commodity_id"
                    " WHERE l.name = :loc AND c.name = :com"
                    " ORDER BY r.recorded_at DESC, r.id DESC LIMIT 1"
                ),
                {"loc": location, "com": commodity},
            ).scalar_one_or_none()
    finally:
        engine.dispose()
    return float(row) if row is not None else 0.0


def _login(client, email: str, password: str) -> dict:
    resp = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_balance_map_unauth_401(client):
    resp = client.get(f"/balance/map?commodity={COMMODITY}")
    assert resp.status_code == 401


def test_balance_map_unknown_commodity_404(client):
    headers = _login(
        client, "sppg.head@demo.local", "Demo#SPPG2026"
    )
    resp = client.get(
        f"/balance/map?commodity=xyz-{uuid.uuid4().hex[:8]}",
        headers=headers,
    )
    assert resp.status_code == 404


def test_balance_map_monitor_returns_all_demo_locations(client):
    """10 lokasi demo → 10 titik + koordinat DB + formula selaras panel.

    Memakai bgn_monitor karena cakupan nasional memang milik peran itu
    (Ruling 2026-10-14); kepala SPPG hanya menerima lokasinya sendiri —
    lihat test_balance_map_kepala_hanya_sppg_sendiri.
    """
    headers = _login(client, "bgn.monitor@demo.local", "Demo#BGN2026")
    resp = client.get(f"/balance/map?commodity={COMMODITY}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["commodity"] == COMMODITY
    assert len(body["locations"]) == 10
    jkt = next(x for x in body["locations"] if x["location"] == "Jakarta")
    # Koordinat dari DB (bukan karangan FE):
    assert abs(jkt["latitude"] - (-6.2088)) < 0.001
    assert abs(jkt["longitude"] - 106.8456) < 0.001
    # Formula selaras panel snapshot, tapi angkanya TIDAK dipaku: acuan dihitung
    # dari DB (baris terbaru supply & demand Jakarta/telur). Sejak deret aktual
    # demo diperluas sampai 5 Nov, baris terbaru Jakarta/telur adalah baris demo
    # (bukan kanonik 8 Okt: supply 300 / demand 1080 / shortage 780).
    supply = _latest_quantity_kg("supply_records", "Jakarta", COMMODITY)
    demand = _latest_quantity_kg("demand_records", "Jakarta", COMMODITY)
    surplus = max(supply - demand, 0.0)
    shortage = max(demand - supply, 0.0)
    status = "surplus" if surplus > 0 else ("shortage" if shortage > 0 else "balanced")
    assert jkt["supply_kg"] == pytest.approx(supply, abs=1e-6)
    assert jkt["demand_kg"] == pytest.approx(demand, abs=1e-6)
    assert jkt["surplus_kg"] == pytest.approx(surplus, abs=1e-6)
    assert jkt["shortage_kg"] == pytest.approx(shortage, abs=1e-6)
    assert jkt["status"] == status


def test_balance_map_seed_test_data_visible(client):
    """Lokasi test dengan data sendiri ikut tampil (map tidak hardcode)."""
    key, loc_id = _seed_location(COMMODITY, 500.0, 300.0)
    try:
        headers = _login(client, "bgn.monitor@demo.local", "Demo#BGN2026")
        resp = client.get(
            f"/balance/map?commodity={COMMODITY}", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["locations"]) == 11
        mine = next(
            x
            for x in body["locations"]
            if x["location"] == f"TEST-{key[:12]}"
        )
        assert mine["supply_kg"] == 500.0
        assert mine["demand_kg"] == 300.0
        assert mine["surplus_kg"] == 200.0
        assert mine["status"] == "surplus"
    finally:
        _cleanup(loc_id)


def test_balance_map_kepala_hanya_sppg_sendiri(client):
    """Kepala SPPG melihat satu titik saja — SPPG-nya sendiri."""
    headers = _login(client, "sppg.head@demo.local", "Demo#SPPG2026")
    resp = client.get(f"/balance/map?commodity={COMMODITY}", headers=headers)
    assert resp.status_code == 200, resp.text
    locations = resp.json()["locations"]
    assert [x["location"] for x in locations] == ["Jakarta"], locations


def test_balance_map_monitor_can_read(client):
    """bgn_monitor read-only tetap boleh membaca map."""
    headers = _login(
        client, "bgn.monitor@demo.local", "Demo#BGN2026"
    )
    resp = client.get(f"/balance/map?commodity={COMMODITY}", headers=headers)
    assert resp.status_code == 200
