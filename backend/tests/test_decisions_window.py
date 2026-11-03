"""Jendela waktu `GET /decisions` (permintaan pemilik 24 Okt 2026).

Aturan yang diuji:
- `24h`/`7d` = jendela bergulir; `30d` = bulan berjalan menurut WIB.
- Kunci tak dikenal → None (tanpa saringan), bukan diam-diam 24 jam.
- `total` ikut jendela: angka di layar dan jumlah baris yang bisa dicapai
  tidak boleh bertentangan.

Tes API memakai dependency override (bukan login sungguhan) dan SENGAJA
baca-saja: tidak membuat/mengubah keputusan di DB demo yang dipakai juri.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.core.window import window_start
from app.main import app
from app.models import User

PENONTON = User(
    id=uuid.uuid4(),
    email="audit-jendela@demo.local",
    name="Audit Jendela",
    role="bgn_monitor",
    password_hash="tidak-dipakai",
)


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: PENONTON
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


# ── fungsi murni ────────────────────────────────────────────────────────────


def test_tanpa_jendela_tanpa_saringan():
    assert window_start(None) is None
    assert window_start("") is None
    assert window_start("mingguan") is None


def test_dua_puluh_empat_jam_dan_tujuh_hari_bergulir():
    sekarang = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)
    assert window_start("24h", sekarang) == sekarang - timedelta(hours=24)
    assert window_start("7d", sekarang) == sekarang - timedelta(days=7)


def test_satu_bulan_mulai_awal_bulan_wib():
    # 24 Okt 06.00 WIB → awal bulan = 1 Okt 00.00 WIB = 30 Sep 17.00 UTC.
    sekarang = datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    awal = window_start("30d", sekarang)
    assert awal is not None
    assert awal == datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)


def test_kunci_case_insensitive():
    sekarang = datetime(2026, 10, 24, 9, 0, tzinfo=timezone.utc)
    assert window_start("7D", sekarang) == window_start("7d", sekarang)


# ── API ─────────────────────────────────────────────────────────────────────


def test_jendela_mempersempit_dan_total_ikut(client):
    penuh = client.get("/decisions").json()
    hari = client.get("/decisions?window=24h").json()
    minggu = client.get("/decisions?window=7d").json()
    assert hari["total"] <= minggu["total"] <= penuh["total"]
    assert hari["count"] == len(hari["items"])
    assert hari["total"] == len(hari["items"]), "tanpa limit, total = seluruh baris"


def test_hari_ini_bagian_dari_tujuh_hari(client):
    hari = {row["decision_id"] for row in client.get("/decisions?window=24h").json()["items"]}
    minggu = {row["decision_id"] for row in client.get("/decisions?window=7d").json()["items"]}
    assert hari.issubset(minggu), "jendela lebih sempit tidak boleh memuat baris di luar"


def test_jendela_tidak_dikenal_ditolak_422(client):
    assert client.get("/decisions?window=2h").status_code == 422


def test_jendela_bisa_digabung_dengan_limit(client):
    body = client.get("/decisions?window=7d&limit=1").json()
    assert len(body["items"]) <= 1
    assert body["count"] == len(body["items"])
