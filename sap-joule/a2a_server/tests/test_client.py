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


# --- purchase order: satu panggilan baca, kolom dipetakan apa adanya ---------------------


def test_purchase_orders_membaca_items_dan_memetakan_kolom():
    panggilan: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        panggilan.append(request)
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t"})
        assert request.url.path == "/sap/purchase-orders"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "po_number": "MC-661695B2C685",
                        "status": "confirmed",
                        "created_at": "2026-10-20T02:20:00+00:00",
                        "decision_id": "9f1c0a52-2b6e-4b31-91f5-3c0a1d5e7a11",
                        "decision_status": "executed",
                        "location_name": "SPPG Jakarta Pusat",
                        "supplier_name": "Telur Berkah",
                        "material_number": "MAT-BERA",
                        "commodity_name": "telur",
                        "ordered_quantity_kg": 600.0,
                        "price_per_kg": 18000.0,
                        "total_value": 10800000.0,
                        "origin": "execution",
                    }
                ],
                "count": 1,
            },
        )

    with _client(handler) as client:
        rows = client.purchase_orders()

    assert [r["poNumber"] for r in rows] == ["MC-661695B2C685"]
    assert rows[0]["totalValue"] == 10800000.0, "total dibaca dari backend, bukan dihitung klien"
    assert rows[0]["decisionStatus"] == "executed"
    assert rows[0]["origin"] == "execution"


def test_purchase_orders_meminta_batas_yang_masuk_akal():
    diminta: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t"})
        diminta.update(dict(request.url.params))
        return httpx.Response(200, json={"items": []})

    with _client(handler) as client:
        assert client.purchase_orders() == []          # plafon 200
        client.purchase_orders(limit=5000)             # di atas plafon -> dijepit, bukan ditolak
        assert diminta["limit"] == "200"

        client.purchase_orders(limit=0)                # nol/negatif -> minimal 1
        assert diminta["limit"] == "1"


def test_purchase_orders_menolak_diteruskan_apa_adanya():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t"})
        return httpx.Response(403, json={"detail": "peran ini tidak berhak membaca PO"})

    with _client(handler) as client, pytest.raises(MealchainRejected) as excinfo:
        client.purchase_orders()

    assert "tidak berhak membaca PO" in str(excinfo.value)


def test_suppliers_membaca_items_dan_memetakan_kolom():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/suppliers"
        assert request.url.params["limit"] == "200"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "name": "CV Cipinang Boga Utama",
                        "location": "Jakarta",
                        "commodity": "beras",
                        "reliability_score": 0.92,
                        "capacity_kg_per_week": 4200.0,
                        "certification_status": "haccp",
                        "address": "Jl. Cipinang Besar No. 12",
                        "contact_name": "Budi Santoso",
                        "excluded_at_hub": False,
                        "shipping": {
                            "count": 2,
                            "total_kg": 840.0,
                            "until": "2026-10-22T00:00:00+00:00",
                        },
                    },
                    {
                        "name": "UD Cipanas Telur Sejahtera",
                        "location": "Cianjur",
                        "commodity": "telur",
                        "reliability_score": 0.86,
                        "capacity_kg_per_week": 2100.0,
                        "certification_status": "hygiene",
                        "address": "Jl. Raya Cipanas No. 4",
                        "contact_name": "Asep",
                        "excluded_at_hub": True,
                        "shipping": None,
                    },
                ]
            },
        )

    with _client(handler) as client:
        hasil = client.suppliers()

    assert [row["name"] for row in hasil] == [
        "CV Cipinang Boga Utama",
        "UD Cipanas Telur Sejahtera",
    ]
    assert hasil[0]["reliability"] == 0.92
    assert hasil[0]["shippingCount"] == 2 and hasil[0]["shippingKg"] == 840.0
    assert hasil[1]["shippingCount"] is None and hasil[1]["excludedAtHub"] is True


def test_suppliers_meminta_limit_masuk_akal():
    batas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        batas.append(request.url.params["limit"])
        return httpx.Response(200, json={"items": []})

    with _client(handler) as client:
        client.suppliers(limit=99999)
        client.suppliers(limit=0)

    assert batas == ["200", "1"]


# --- read model baru: batas, path, dan pemetaan kolom -------------------------------------


def test_batches_meminta_plafon_supaya_inventaris_lengkap():
    """Batas 50 di backend dulu membuat 158 batch tampak seperti 50 tanpa galat."""
    diminta: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/batches"
        diminta.append(request.url.params["limit"])
        return httpx.Response(200, json={"batches": [{"id": "b1"}], "total": 158})

    with _client(handler) as client:
        assert client.batches() == [{"id": "b1"}]
        client.batches(limit=99999)  # dijepit ke plafon, bukan ditolak

    assert diminta == [str(500), str(500)]


def test_price_quotes_memakai_path_per_pasangan_dan_memetakan_kuotasi():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.raw_path.decode() == "/price/quotes/l-1/beras%20merah"
        return httpx.Response(
            200,
            json={
                "location": "Bandung",
                "commodity": "beras merah",
                "quotes": [
                    {
                        "supplier_name": "UD Rancaekek Beras Sejahtera",
                        "price_per_kg": 12039.42,
                        "recorded_at": "2026-11-03T00:00:00+00:00",
                    },
                    "bukan objek",
                ],
            },
        )

    with _client(handler) as client:
        hasil = client.price_quotes("l-1", "beras merah")

    assert hasil["location"] == "Bandung"
    assert [q["supplier_name"] for q in hasil["quotes"]] == ["UD Rancaekek Beras Sejahtera"]


def test_demand_forecast_meneruskan_metode_dan_keyakinan():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/demand/forecast/l-1/beras"
        return httpx.Response(
            200,
            json={"forecast_qty_kg": 6697.558, "method": "statistical_fallback", "confidence": 1.0},
        )

    with _client(handler) as client:
        hasil = client.demand_forecast("l-1", "beras")

    assert hasil["forecast_qty_kg"] == 6697.558
    assert hasil["method"] == "statistical_fallback"


def test_waste_summary_mengirim_jendela_hari_yang_masuk_akal():
    diminta: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/waste/summary"
        diminta.append(request.url.params["days"])
        return httpx.Response(200, json={"recorded": {"available": True, "kg": 631.46}})

    with _client(handler) as client:
        client.waste_summary(days=30)
        client.waste_summary(days=9999)  # dijepit ke 365
        client.waste_summary(days=0)  # minimal 1

    assert diminta == ["30", "365", "1"]


def test_supplier_routes_membuang_geometri_tapi_mempertahankan_angka_rute():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/supplier-routes"
        return httpx.Response(
            200,
            json={
                "routes": [
                    {
                        "supplier_name": "CV Cipinang Boga Utama",
                        "origin": {"name": "CV Cipinang Boga Utama", "latitude": -6.2},
                        "destination_name": "Jakarta",
                        "commodity": "beras",
                        "quantity_kg": 800.0,
                        "safety_status": "pass",
                        "usable_until": "2027-04-17T15:36:52+00:00",
                        "straight_km": 4.92,
                        "road": {
                            "distance_km": 9.8,
                            "duration_min": 12.2,
                            "ratio_vs_straight": 1.99,
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[106.88, -6.22], [106.87, -6.21]],
                            },
                        },
                        "journey": {
                            "state": "dalam_perjalanan",
                            "state_label": "dalam perjalanan",
                            "eta_at": "2026-10-20T09:00:00+00:00",
                            "remaining_min": 7.5,
                            "arrives_before_usable_until": True,
                        },
                    }
                ],
                "summary": {"routes": 1, "with_road": 1, "without_road": 0, "scope": "nasional"},
            },
        )

    with _client(handler) as client:
        hasil = client.supplier_routes()

    assert hasil["routes"][0]["roadKm"] == 9.8
    assert hasil["routes"][0]["roadMinutes"] == 12.2
    assert hasil["routes"][0]["journeyState"] == "dalam perjalanan"
    assert "geometry" not in str(hasil), "polylines tidak boleh ikut ke teks chat"
    assert hasil["summary"]["with_road"] == 1


def test_bukti_keputusan_memakai_path_yang_benar():
    dipanggil: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        dipanggil.append(request.url.path)
        return httpx.Response(200, json={"decision_id": "d1", "chain": [], "steps": []})

    with _client(handler) as client:
        client.decision_compliance("d1")
        client.decision_chain("d1")
        client.decision_traces("d1")

    assert dipanggil == [
        "/decisions/d1/compliance",
        "/decisions/d1/chain",
        "/decisions/d1/traces",
    ]


def test_status_sistem_membaca_integrasi_ledger_dan_ringkasan_po():
    dipanggil: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        dipanggil.append(request.url.path)
        if request.url.path == "/ledger/verify":
            return httpx.Response(200, json={"valid": True, "blocks": 115, "linked_ratio": 1.0})
        if request.url.path == "/sap/purchase-orders/summary":
            return httpx.Response(200, json={"count": 23, "total_value": 227295034.0})
        return httpx.Response(200, json={"components": [{"id": "mock_sap"}]})

    with _client(handler) as client:
        assert client.ledger_verify()["valid"] is True
        assert client.po_summary()["count"] == 23
        assert client.integrations_status()["components"][0]["id"] == "mock_sap"

    assert dipanggil == ["/ledger/verify", "/sap/purchase-orders/summary", "/integrations/status"]


def test_receipts_mewajibkan_id_batch_dan_membaca_envelope():
    diminta: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/receipts"
        diminta.update(dict(request.url.params))
        return httpx.Response(200, json={"items": [{"checked": {"suhu": True}}]})

    with _client(handler) as client:
        rows = client.receipts("b-1")

    assert rows == [{"checked": {"suhu": True}}]
    assert diminta["batch_id"] == "b-1"


def test_supply_point_memakai_path_per_pasangan():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "t1"})
        assert request.url.path == "/supply/l-1/telur"
        return httpx.Response(
            200, json={"quantity_kg": 1207.32, "recorded_at": "2026-11-04T12:00:00+00:00"}
        )

    with _client(handler) as client:
        assert client.supply_point("l-1", "telur")["quantity_kg"] == 1207.32
