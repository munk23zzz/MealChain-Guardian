"""A4 — AWS for SAP MCP Server: provider yang benar-benar bicara MCP, bukan stub.

Seam yang diuji (tanpa tenant SAP hidup): transport HTTP di-inject lewat
``httpx.MockTransport``, jadi yang diuji adalah *bentuk protokol* yang dikirim
ke server MCP dan *pemetaan* hasil tool kembali ke kontrak SAP-shaped repo.

Aturan yang dijaga:
- tanpa endpoint/token pemilihan provider DITOLAK (fail closed, bukan fallback);
- ``initialize`` dikirim sebelum ``tools/call`` pertama;
- hasil tool yang ``isError`` atau transport mati melempar galat eksplisit —
  TIDAK pernah diterjemahkan menjadi daftar kosong;
- semua baris hasil berlabel ``DataSource="SAP"``.
"""

import json

import httpx
import pytest

from app.sap_integration.aws_mcp_provider import (
    AwsMcpSapProvider,
    SAPConfigurationError,
    SAPToolError,
    SAPTransportError,
)


def _rpc_ok(payload, *, request_id=None):
    """Balasan JSON-RPC 2.0 sukses dengan isi tool berupa teks JSON."""
    return httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
        },
    )


def _provider(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    return AwsMcpSapProvider(
        endpoint="https://mcp.sap.example/mcp", token="rahasia", transport=transport, **kwargs
    )


def test_endpoint_kosong_ditolak_sebelum_jaringan_dipanggil():
    with pytest.raises(SAPConfigurationError, match="endpoint"):
        AwsMcpSapProvider(endpoint="")


def test_initialize_dikirim_sebelum_tools_call():
    terlihat = []

    def handler(request):
        body = json.loads(request.content)
        terlihat.append(body["method"])
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "serverInfo": {"name": "aws-for-sap", "version": "1.0"},
                    },
                },
            )
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return _rpc_ok(
            [
                {
                    "MaterialNumber": "M-1",
                    "Plant": "1000",
                    "StorageLocation": "SL01",
                    "Batch": "B-9",
                    "MatlStkQty": 12,
                    "BaseUnit": "KG",
                }
            ],
            request_id=body["id"],
        )

    provider = _provider(handler)
    rows = provider.get_material_stock("1000")

    assert terlihat[0] == "initialize"
    assert terlihat[1] == "notifications/initialized"
    assert terlihat[2] == "tools/call"
    assert rows == [
        {
            "MaterialNumber": "M-1",
            "Plant": "1000",
            "StorageLocation": "SL01",
            "Batch": "B-9",
            "MatlStkQty": 12,
            "BaseUnit": "KG",
            "DataSource": "SAP",
        }
    ]


def test_purchase_order_dipetakan_dan_data_source_sap():
    def handler(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return _rpc_ok(
            [
                {
                    "PurchaseOrder": "4500000123",
                    "Supplier": "V-77",
                    "Material": "TELUR-1",
                    "Quantity": 250,
                    "Status": "OPEN",
                }
            ],
            request_id=body["id"],
        )

    rows = _provider(handler).get_purchase_orders("1000")
    assert rows == [
        {
            "PurchaseOrder": "4500000123",
            "Supplier": "V-77",
            "Material": "TELUR-1",
            "Quantity": 250,
            "Status": "OPEN",
            "DataSource": "SAP",
        }
    ]


def test_transport_mati_melempar_galat_bukan_daftar_kosong():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    provider = _provider(handler)
    with pytest.raises(SAPTransportError):
        provider.get_material_stock("1000")


def test_http_401_melempar_galat_transport():
    def handler(request):
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(SAPTransportError, match="401"):
        _provider(handler).get_material_stock("1000")


def test_tool_iserror_melempar_galat_tool():
    def handler(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "plant 1000 tidak ada"}],
                },
            },
        )

    with pytest.raises(SAPToolError, match="tidak ada"):
        _provider(handler).get_material_stock("1000")


def test_jsonrpc_error_melempar_galat_tool():
    def handler(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {"code": -32602, "message": "invalid params"},
            },
        )

    with pytest.raises(SAPToolError, match="invalid params"):
        _provider(handler).get_material_stock("1000")


def test_token_dikirim_sebagai_bearer_dan_session_id_dipertahankan():
    terlihat = []

    def handler(request):
        body = json.loads(request.content)
        terlihat.append((body["method"], request.headers.get("authorization"),
                        request.headers.get("mcp-session-id")))
        if body["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "sesi-123"},
                json={"jsonrpc": "2.0", "id": body["id"], "result": {}},
            )
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return _rpc_ok([], request_id=body["id"])

    _provider(handler).get_material_stock("1000")
    assert terlihat[0][1] == "Bearer rahasia"
    assert terlihat[2][2] == "sesi-123"


def test_business_partner_dan_product_master_dipetakan():
    def handler(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        nama = body["params"]["name"]
        if nama.endswith("business_partner"):
            return _rpc_ok(
                {"BusinessPartner": "V-77", "SupplierName": "CV Sumber Telur"},
                request_id=body["id"],
            )
        return _rpc_ok(
            {"Product": "TELUR-1", "ProductType": "FERT", "BaseUnit": "KG",
             "ShelfLifeDays": 28},
            request_id=body["id"],
        )

    provider = _provider(handler)
    assert provider.get_business_partner("V-77") == {
        "BusinessPartner": "V-77",
        "SupplierName": "CV Sumber Telur",
        "DataSource": "SAP",
    }
    assert provider.get_product_master("TELUR-1") == {
        "Product": "TELUR-1",
        "ProductType": "FERT",
        "BaseUnit": "KG",
        "ShelfLifeDays": 28,
        "DataSource": "SAP",
    }


def test_create_purchase_order_ditolak_tanpa_izin_tulis():
    def handler(request):
        raise AssertionError("tidak boleh ada panggilan jaringan tanpa izin tulis")

    with pytest.raises(PermissionError):
        _provider(handler).create_purchase_order({"Material": "TELUR-1"})


def test_create_purchase_order_mengirim_tool_dan_mengembalikan_nomor_po():
    terlihat = {}

    def handler(request):
        body = json.loads(request.content)
        if body["method"] == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}})
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        terlihat["params"] = body["params"]
        return _rpc_ok({"PurchaseOrder": "4500000999"}, request_id=body["id"])

    provider = _provider(handler, allow_write=True)
    hasil = provider.create_purchase_order({"Material": "TELUR-1", "Quantity": 100})
    assert terlihat["params"]["name"] == "sap_create_purchase_order"
    assert terlihat["params"]["arguments"] == {"Material": "TELUR-1", "Quantity": 100}
    assert hasil == {"PurchaseOrder": "4500000999", "DataSource": "SAP"}
