"""Test `mealchain_client.py` memakai `httpx.MockTransport` — tanpa backend hidup.

Kontrak yang diuji = API klon (a) `mealchain-guardian` v0.2.0:
`POST /auth/login {email, password}` → `access_token`; data dibaca dari `/admin/locations`,
`/batches`, `/balance/map`, `/kpi`, `/decisions`, dan `/decisions/{id}/approval-summary`
(bukan lagi `/ui/*` milik v0.1.0).

Janji modul yang tetap diuji: kegagalan TIDAK pernah disamarkan menjadi data kosong/nol,
akun tetap baca-saja, dan login diulang sekali saat 401.
"""

from __future__ import annotations

import json

import httpx
import pytest

from mealchain_client import MealchainClient, MealchainRejected, MealchainUnavailable

API = "http://backend.test"


def _client(handler, **kwargs) -> MealchainClient:
    return MealchainClient(
        base_url=API,
        username="bgn.monitor@demo.local",
        password="Demo#BGN2026",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_login_mengirim_email_dan_membaca_access_token():
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        panggilan.append(request)
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1", "role": "bgn_monitor"})
        if request.url.path == "/batches":
            return httpx.Response(200, json={"batches": [{"id": "b1"}]})
        return httpx.Response(404, json={"detail": "tidak ada"})

    with _client(handler) as client:
        hasil = client.batches()

    assert hasil == [{"id": "b1"}]
    body = json.loads(panggilan[0].content.decode())
    assert body == {"email": "bgn.monitor@demo.local", "password": "Demo#BGN2026"}
    assert "username" not in body  # v0.2.0 menolak field itu (422)
    assert panggilan[1].headers["authorization"] == "Bearer t1"


def test_lokasi_dibaca_dari_admin_locations():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/admin/locations"
        return httpx.Response(
            200,
            json={"locations": [{"id": "l1", "name": "Jakarta", "region": "DKI Jakarta"}]},
        )

    with _client(handler) as client:
        assert client.locations() == [
            {"id": "l1", "name": "Jakarta", "region": "DKI Jakarta"}
        ]


def test_balance_map_per_komoditas():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/balance/map"
        assert request.url.params["commodity"] == "telur"
        return httpx.Response(
            200,
            json={
                "commodity": "telur",
                "locations": [
                    {"location": "Jakarta", "supply_kg": 100.0, "demand_kg": 880.0,
                     "surplus_kg": 0.0, "shortage_kg": 780.0, "status": "shortage"},
                ],
            },
        )

    with _client(handler) as client:
        baris = client.balance_map("telur")["locations"]

    assert baris[0]["shortage_kg"] == 780.0


def test_kpi_memakai_jendela_waktu_yang_diminta():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/kpi"
        assert "start" in request.url.params and "end" in request.url.params
        assert request.url.params["start"] < request.url.params["end"]
        return httpx.Response(
            200,
            json={"metrics": [{"name": "Meal Continuity Rate", "unit": "percent",
                               "state": "available", "value": "74.95", "reason": None}]},
        )

    with _client(handler) as client:
        kpi = client.kpi(days=7)

    assert kpi["metrics"][0]["name"] == "Meal Continuity Rate"


def test_kpi_menolak_jendela_tak_masuk_akal_sebelum_memanggil_backend():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("tidak boleh memanggil backend")

    with _client(handler) as client, pytest.raises(ValueError):
        client.kpi(days=0)


def test_keputusan_pending_dilengkapi_asal_tujuan_dan_komoditas():
    """Feed `/decisions` tidak memuat lokasi/komoditas; itu ada di approval-summary."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        if request.url.path == "/decisions":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"decision_id": "d1", "status": "proposed",
                         "decision_type": "regional_balance", "quantity_kg": 600.0},
                        {"decision_id": "d2", "status": "executed",
                         "decision_type": "price_anomaly", "quantity_kg": 10.0},
                    ]
                },
            )
        if request.url.path == "/decisions/d1/approval-summary":
            return httpx.Response(
                200,
                json={"decision_id": "d1", "source_location": "Cianjur",
                      "target_location": "Jakarta", "commodity": "telur"},
            )
        raise AssertionError(f"tidak diharapkan: {request.url.path}")

    with _client(handler) as client:
        rows = client.pending_decisions()

    assert [r["id"] for r in rows] == ["d1"]
    assert rows[0]["sourceLocation"] == "Cianjur"
    assert rows[0]["targetLocation"] == "Jakarta"
    assert rows[0]["commodity"] == "telur"
    assert rows[0]["quantityKg"] == 600.0
    assert rows[0]["status"] == "proposed"


def test_pending_decisions_menyerap_summary_yang_gagal_tanpa_mengarang_data():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        if request.url.path == "/decisions":
            return httpx.Response(200, json={"items": [
                {"decision_id": "d1", "status": "proposed",
                 "decision_type": "regional_balance", "quantity_kg": 600.0}]})
        return httpx.Response(500, json={"detail": "ringkasan tidak tersedia"})

    with _client(handler) as client:
        rows = client.pending_decisions()

    assert rows[0]["sourceLocation"] is None
    assert rows[0]["targetLocation"] is None
    assert rows[0]["commodity"] is None
    assert rows[0]["quantityKg"] == 600.0  # angka dari feed tetap dipakai


def test_401_diulang_sekali_dengan_login_baru():
    login_count = {"n": 0}
    get_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            login_count["n"] += 1
            return httpx.Response(200, json={"access_token": f"t{login_count['n']}"})
        get_count["n"] += 1
        if get_count["n"] == 1:
            return httpx.Response(401, json={"detail": "Token kedaluwarsa"})
        assert request.headers["authorization"] == "Bearer t2"
        return httpx.Response(200, json={"batches": [{"ok": True}]})

    with _client(handler) as client:
        hasil = client.batches()

    assert hasil == [{"ok": True}]
    assert login_count["n"] == 2
    assert get_count["n"] == 2


def test_kredensial_baca_belum_diisi_melempar_unavailable_bukan_data_kosong(monkeypatch):
    monkeypatch.delenv("MEALCHAIN_READ_USERNAME", raising=False)
    monkeypatch.delenv("MEALCHAIN_READ_PASSWORD", raising=False)
    client = MealchainClient(base_url=API, username=None, password=None,
                             transport=httpx.MockTransport(lambda r: httpx.Response(500)))

    with pytest.raises(MealchainUnavailable) as excinfo:
        client.batches()

    assert "MEALCHAIN_READ_USERNAME" in str(excinfo.value)


def test_backend_menolak_diteruskan_apa_adanya():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        return httpx.Response(500, json={"detail": "database sedang mati"})

    with _client(handler) as client, pytest.raises(MealchainRejected) as excinfo:
        client.decisions()

    assert "HTTP 500" in str(excinfo.value)
    assert "database sedang mati" in str(excinfo.value)


def test_login_ditolak_disebut_jenis_penolakannya():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "email atau password salah"})

    with _client(handler) as client, pytest.raises(MealchainRejected) as excinfo:
        client.batches()

    assert "email atau password salah" in str(excinfo.value)


def test_backend_mati_jadi_unavailable_bukan_galat_httpx_mentah():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _client(handler) as client, pytest.raises(MealchainUnavailable) as excinfo:
        client.batches()

    assert "tidak bisa dihubungi" in str(excinfo.value)


def test_health_tanpa_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"status": "ok", "sap": {"data_source": "MOCK"}})

    with _client(handler) as client:
        assert client.health()["sap"]["data_source"] == "MOCK"
