"""Batas waktu SATU untuk /balance, /supply, /demand, /demand/forecast.

MASALAH yang dipaku di sini (temuan 28 Okt 2026). Pop-up "Pasokan &
permintaan" menampilkan tiga angka yang tidak bisa dijumlahkan di layar:

- `GET /balance/Jakarta/telur`  → supply 300.0, demand 1080.0, shortage 780.0
  (memakai baris `recorded_at <= sekarang`, lihat `_batas_waktu` di
  `app/api/balance.py`);
- `GET /supply/Jakarta/telur`   → 299.09 kg bertanggal 2026-11-04 (MASA DEPAN);
- `GET /demand/Jakarta/telur`   → 1087.22 kg bertanggal 2026-11-07.

Penyebabnya bukan data, melainkan dua aturan waktu yang berbeda: `/balance`
membatasi baris ke `recorded_at <= sekarang` sejak audit angka 18 Okt,
sedangkan `/supply`, `/demand`, dan `/demand/forecast` mengambil baris terbaru
APA PUN tanggalnya. Deret demo sengaja diperluas sampai 5 Nov (`ACTUAL_REF` di
`app/seed/timeseries.py`), jadi kedua endpoint itu menyajikan pasokan/
permintaan masa depan sebagai kondisi kini — dan selisih di layar (299,09 −
1.087,22 = 788,13) tidak sama dengan kartu Selisih (kurang 780).

ATURAN yang ditegakkan berkas ini:
- ketiga endpoint memakai batas atas waktu YANG SAMA dengan `/balance`
  (baris `recorded_at <= sekarang`);
- `/supply` karena itu mengembalikan baris lampau, bukan baris masa depan;
- `/demand` mengembalikan jumlah lampau;
- `/demand/forecast` hanya memakai catatan yang SUDAH TERJADI — perkiraan
  tidak boleh dibentuk dari catatan bertanggal masa depan;
- angka ketiganya MENUTUP dengan `/balance` untuk pasangan yang sama.

Semua baris sisipan test dibersihkan di `finally`.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.forecasting_fallback import statistical_forecast
from app.main import app
from tests.dsn import DSN_SYNC  # DSN mengikuti DATABASE_URL

DB_URL = DSN_SYNC
COMMODITY = "telur"

#: Nilai baris lampau (2 hari lalu) dan baris masa depan (3 hari ke depan).
LALU_SUPPLY, DEPAN_SUPPLY = 100.0, 999.0
LALU_DEMAND, DEPAN_DEMAND = 200.0, 888.0


@pytest.fixture()
def client(monitor_headers):
    """Klien baca nasional (bgn_monitor) — lokasi uji ini bukan SPPG siapa pun."""
    with TestClient(app) as c:
        c.headers.update(monitor_headers)
        yield c


def _seed_pasangan_berjadwal() -> tuple[str, str]:
    """Lokasi uji baru + 2 baris supply dan 2 baris demand (lampau & masa depan)."""
    nama = f"TEST-{uuid.uuid4().hex[:12]}"
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            loc_id = conn.execute(
                text(
                    "INSERT INTO locations (name, region, latitude, longitude)"
                    " VALUES (:n, 'Test Region', -6.2, 106.8) RETURNING id"
                ),
                {"n": nama},
            ).scalar_one()
            com_id = conn.execute(
                text("SELECT id FROM commodities WHERE name=:n"), {"n": COMMODITY}
            ).scalar_one()
            # Satu baris lampau (2 hari lalu) + satu baris masa depan (3 hari
            # ke depan) untuk masing-masing sisi.
            lampau, depan = "- interval '2 days'", "+ interval '3 days'"
            for qty, geser in ((LALU_SUPPLY, lampau), (DEPAN_SUPPLY, depan)):
                conn.execute(
                    text(
                        "INSERT INTO supply_records (location_id, commodity_id,"
                        " quantity_kg, recorded_at, source)"
                        f" VALUES (:l, :c, :q, now() {geser}, 'manual')"
                    ),
                    {"l": loc_id, "c": com_id, "q": qty},
                )
            for qty, geser in ((LALU_DEMAND, lampau), (DEPAN_DEMAND, depan)):
                conn.execute(
                    text(
                        "INSERT INTO demand_records (location_id, commodity_id,"
                        " quantity_kg, needed_by, recorded_at)"
                        f" VALUES (:l, :c, :q, now() {geser} + interval '3 days',"
                        f" now() {geser})"
                    ),
                    {"l": loc_id, "c": com_id, "q": qty},
                )
    finally:
        engine.dispose()
    return nama, loc_id


def _bersihkan(loc_id) -> None:
    """Hapus residu test FK-safe (baris anak dulu, lokasi terakhir)."""
    engine = create_engine(DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM supply_records WHERE location_id=:l"), {"l": loc_id}
            )
            conn.execute(
                text("DELETE FROM demand_records WHERE location_id=:l"), {"l": loc_id}
            )
            conn.execute(text("DELETE FROM locations WHERE id=:l"), {"l": loc_id})
    finally:
        engine.dispose()


def _parse(waktu: str) -> datetime:
    """ISO-8601 dari respons → datetime UTC yang bisa dibandingkan."""
    nilai = datetime.fromisoformat(waktu)
    return nilai if nilai.tzinfo is not None else nilai.replace(tzinfo=timezone.utc)


def test_supply_memakai_baris_lampau_bukan_baris_masa_depan(client):
    """`/supply` = baris terakhir yang SUDAH TERJADI (100 kg, bukan 999 kg)."""
    nama, loc_id = _seed_pasangan_berjadwal()
    try:
        resp = client.get(f"/supply/{nama}/{COMMODITY}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["quantity_kg"] == pytest.approx(LALU_SUPPLY)
        # Cap waktu yang dikembalikan harus benar-benar masa lalu — angka dan
        # tanggalnya satu baris, bukan angka lampau dengan tanggal masa depan.
        assert _parse(body["recorded_at"]) <= datetime.now(timezone.utc)
    finally:
        _bersihkan(loc_id)


def test_demand_memakai_baris_lampau_bukan_baris_masa_depan(client):
    """`/demand` = baris terakhir yang SUDAH TERJADI (200 kg, bukan 888 kg)."""
    nama, loc_id = _seed_pasangan_berjadwal()
    try:
        resp = client.get(f"/demand/{nama}/{COMMODITY}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["quantity_kg"] == pytest.approx(LALU_DEMAND)
        assert "needed_by" in body
    finally:
        _bersihkan(loc_id)


def test_forecast_hanya_memakai_catatan_masa_lalu(client):
    """Perkiraan dibentuk dari catatan lampau saja (1 observasi: yakin 1/3).

    Kalau baris masa depan (888 kg) ikut terpakai, hasilnya berbeda dan
    `confidence` menjadi 2/3 — dua penanda yang jelas.
    """
    nama, loc_id = _seed_pasangan_berjadwal()
    try:
        resp = client.get(
            f"/demand/forecast/{nama}/{COMMODITY}", params={"horizon_days": 7}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        harapan = statistical_forecast([LALU_DEMAND], horizon_days=7)
        salah = statistical_forecast([LALU_DEMAND, DEPAN_DEMAND], horizon_days=7)
        assert body["forecast_qty_kg"] == pytest.approx(
            harapan["forecast_qty_kg"], rel=1e-9
        )
        assert body["forecast_qty_kg"] != pytest.approx(
            salah["forecast_qty_kg"], rel=1e-9
        ), "perkiraan masih memakai catatan bertanggal masa depan"
        assert body["confidence"] == pytest.approx(1 / 3)
    finally:
        _bersihkan(loc_id)


def test_angka_ketiga_endpoint_menutup_dengan_balance(client):
    """Yang dilihat juri: /supply − /demand = shortage di kartu /balance."""
    nama, loc_id = _seed_pasangan_berjadwal()
    try:
        sup = client.get(f"/supply/{nama}/{COMMODITY}")
        dem = client.get(f"/demand/{nama}/{COMMODITY}")
        bal = client.get(f"/balance/{nama}/{COMMODITY}")
        for r in (sup, dem, bal):
            assert r.status_code == 200, r.text
        supply = sup.json()["quantity_kg"]
        demand = dem.json()["quantity_kg"]
        kartu = bal.json()
        assert supply == pytest.approx(kartu["supply_kg"])
        assert demand == pytest.approx(kartu["demand_kg"])
        # Selisih pop-up harus sama dengan selisih dua angka yang tertera.
        assert round(demand - supply, 2) == pytest.approx(
            round(kartu["shortage_kg"], 2)
        )
    finally:
        _bersihkan(loc_id)
