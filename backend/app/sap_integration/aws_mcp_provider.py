"""A4 — adapter SAP lewat *AWS for SAP MCP Server* (MCP JSON-RPC 2.0 di atas HTTP).

Kenapa berbentuk begini:

- Protokol MCP memakai JSON-RPC 2.0 dengan urutan wajib ``initialize`` →
  ``notifications/initialized`` → ``tools/call``. Server AWS for SAP mengekspos
  operasi SAP sebagai *tool*; adapter ini yang menerjemahkan kontrak SAP-shaped
  repo (``MaterialStockRecord`` dkk.) ke nama tool + argumen, lalu memetakan
  hasilnya kembali.
- **Fail closed**: endpoint kosong ditolak di konstruktor, transport mati atau
  ``isError`` melempar galat eksplisit. Tidak pernah diterjemahkan menjadi daftar
  kosong — "tidak ada data" dan "tidak bisa bertanya" harus berbeda di jejak audit.
- Operasi tulis (``create_purchase_order``) butuh izin eksplisit ``allow_write``
  dan tetap hanya dipanggil dari alur approval manusia.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from app.sap_integration.provider_interface import (
    BusinessPartnerRecord,
    MaterialStockRecord,
    ProductMasterRecord,
    PurchaseOrderRecord,
    PurchaseOrderResult,
    SAPCapability,
    SAPDataProvider,
)

MCP_PROTOCOL_VERSION = "2025-06-18"

# Nama tool default. Tenant AWS for SAP boleh memberi nama lain — karena itu bisa
# ditimpa lewat ``tool_names`` (dipetakan dari settings di factory).
NAMA_TOOL_DEFAULT: dict[str, str] = {
    "material_stock": "sap_material_stock",
    "purchase_orders": "sap_purchase_orders",
    "create_purchase_order": "sap_create_purchase_order",
    "business_partner": "sap_business_partner",
    "product_master": "sap_product_master",
}


class SAPConfigurationError(ValueError):
    """Konfigurasi integrasi tidak lengkap — jangan menebak, tolak."""


class SAPTransportError(RuntimeError):
    """Server MCP tidak bisa dihubungi / membalas non-2xx."""


class SAPToolError(RuntimeError):
    """Server MCP menjawab, tetapi tool-nya gagal (``error`` atau ``isError``)."""


class AwsMcpSapProvider(SAPDataProvider):
    """Adapter MCP nyata; default aplikasi tetap ``MockSAPProvider``."""

    capabilities = frozenset(
        {
            SAPCapability.MATERIAL_STOCK,
            SAPCapability.PURCHASE_ORDERS,
            SAPCapability.CREATE_PURCHASE_ORDER,
            SAPCapability.BUSINESS_PARTNERS,
            SAPCapability.PRODUCT_MASTER,
        }
    )

    def __init__(
        self,
        *,
        endpoint: str,
        token: str = "",
        timeout_seconds: float = 10.0,
        allow_write: bool = False,
        transport: httpx.BaseTransport | None = None,
        tool_names: dict[str, str] | None = None,
    ) -> None:
        if not endpoint or not endpoint.strip():
            raise SAPConfigurationError(
                "aws_mcp butuh endpoint MCP yang eksplisit "
                "(SAP_MCP_ENDPOINT); tanpa itu pemilihan provider ditolak"
            )
        self._endpoint = endpoint.strip()
        self._token = token.strip()
        self._allow_write = allow_write
        self._tools = {**NAMA_TOOL_DEFAULT, **(tool_names or {})}
        self._client = httpx.Client(
            timeout=timeout_seconds,
            transport=transport,
            headers={"accept": "application/json, text/event-stream"},
        )
        self._session_id: str | None = None
        self._initialized = False
        self._next_id = 0

    # ------------------------------------------------------------------ transport

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AwsMcpSapProvider":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        headers = {"content-type": "application/json"}
        if self._token:
            headers["authorization"] = f"Bearer {self._token}"
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        try:
            response = self._client.post(self._endpoint, json=body, headers=headers)
        except httpx.HTTPError as exc:  # jaringan mati, DNS, timeout, TLS
            raise SAPTransportError(f"server MCP tidak bisa dihubungi: {exc}") from exc
        if response.status_code >= 400:
            raise SAPTransportError(
                f"server MCP membalas HTTP {response.status_code}: {response.text[:200]}"
            )
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        return response

    @staticmethod
    def _payload_dari_response(response: httpx.Response) -> dict[str, Any]:
        """MCP streamable HTTP boleh menjawab JSON biasa atau SSE."""
        if response.status_code == 202 or response.content == b"":
            return {}
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("text/event-stream"):
            hasil: dict[str, Any] = {}
            for line in response.text.splitlines():
                if not line.startswith("data:"):
                    continue
                potongan = line[len("data:") :].strip()
                if not potongan:
                    continue
                try:
                    hasil = json.loads(potongan)
                except json.JSONDecodeError as exc:
                    raise SAPToolError(f"balasan SSE bukan JSON: {potongan[:120]}") from exc
            return hasil
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise SAPToolError(f"balasan MCP bukan JSON: {response.text[:120]}") from exc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        body: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            body["params"] = params
        payload = self._payload_dari_response(self._post(body))
        error = payload.get("error")
        if error:
            pesan = error.get("message") if isinstance(error, dict) else str(error)
            raise SAPToolError(f"MCP {method} gagal: {pesan}")
        return payload.get("result") or {}

    def _notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mealchain-guardian", "version": "1.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True

    # ------------------------------------------------------------------ tool call

    def _call_tool(self, kunci: str, arguments: dict[str, Any]) -> Any:
        self._ensure_initialized()
        nama = self._tools[kunci]
        result = self._rpc("tools/call", {"name": nama, "arguments": arguments})
        if result.get("isError"):
            raise SAPToolError(f"tool MCP {nama!r} melaporkan galat: {_teks_konten(result)}")
        teks = _teks_konten(result)
        if not teks:
            return []
        try:
            return json.loads(teks)
        except json.JSONDecodeError as exc:
            raise SAPToolError(
                f"tool MCP {nama!r} menjawab bukan JSON: {teks[:120]}"
            ) from exc

    @staticmethod
    def _baris(rows: Any) -> list[dict[str, Any]]:
        if rows is None:
            return []
        if isinstance(rows, dict):
            # Sebagian server membungkus daftar: {"value": [...]} / {"items": [...]}
            for kunci in ("value", "items", "results", "data"):
                if isinstance(rows.get(kunci), list):
                    return [r for r in rows[kunci] if isinstance(r, dict)]
            return [rows]
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        raise SAPToolError(f"bentuk hasil tool tidak dikenali: {type(rows).__name__}")

    # ------------------------------------------------------------------ kontrak

    def get_material_stock(self, plant: str) -> list[MaterialStockRecord]:
        hasil = self._call_tool("material_stock", {"plant": plant})
        return [
            {
                "MaterialNumber": str(row.get("MaterialNumber", "")),
                "Plant": str(row.get("Plant", plant)),
                "StorageLocation": str(row.get("StorageLocation", "")),
                "Batch": str(row.get("Batch", "")),
                "MatlStkQty": row.get("MatlStkQty", 0),
                "BaseUnit": str(row.get("BaseUnit", "")),
                "DataSource": "SAP",
            }
            for row in self._baris(hasil)
        ]

    def get_purchase_orders(self, plant: str) -> list[PurchaseOrderRecord]:
        hasil = self._call_tool("purchase_orders", {"plant": plant})
        return [
            {
                "PurchaseOrder": str(row.get("PurchaseOrder", "")),
                "Supplier": str(row.get("Supplier", "")),
                "Material": str(row.get("Material", "")),
                "Quantity": row.get("Quantity", 0),
                "Status": str(row.get("Status", "")),
                "DataSource": "SAP",
            }
            for row in self._baris(hasil)
        ]

    def create_purchase_order(self, payload: dict) -> PurchaseOrderResult:
        """Hanya boleh jalan bila integrator menyalakan izin tulis eksplisit.

        Membuat PO adalah aksi mengubah system of record — di repo ini selalu
        berangkat dari approval manusia, jadi adapter tidak boleh diam-diam
        mengizinkannya hanya karena kredensialnya ada.
        """
        if not self._allow_write:
            raise PermissionError(
                "create_purchase_order lewat aws_mcp butuh SAP_MCP_ALLOW_WRITE=true "
                "dan approval manusia (Rules.md)"
            )
        hasil = self._call_tool("create_purchase_order", dict(payload))
        if isinstance(hasil, list):
            hasil = hasil[0] if hasil else {}
        nomor_po = str((hasil or {}).get("PurchaseOrder", ""))
        if not nomor_po:
            raise SAPToolError("tool create_purchase_order tidak mengembalikan PurchaseOrder")
        return {"PurchaseOrder": nomor_po, "DataSource": "SAP"}

    def get_business_partner(self, partner_id: str) -> BusinessPartnerRecord:
        hasil = self._call_tool("business_partner", {"business_partner": partner_id})
        baris = self._baris(hasil)
        if not baris:
            return cast(BusinessPartnerRecord, {})
        row = baris[0]
        return {
            "BusinessPartner": str(row.get("BusinessPartner", partner_id)),
            "SupplierName": str(row.get("SupplierName", "")),
            "DataSource": "SAP",
        }

    def get_product_master(self, product_id: str) -> ProductMasterRecord:
        hasil = self._call_tool("product_master", {"product": product_id})
        baris = self._baris(hasil)
        if not baris:
            return cast(ProductMasterRecord, {})
        row = baris[0]
        return {
            "Product": str(row.get("Product", product_id)),
            "ProductType": str(row.get("ProductType", "")),
            "BaseUnit": str(row.get("BaseUnit", "")),
            "ShelfLifeDays": int(row.get("ShelfLifeDays", 0) or 0),
            "DataSource": "SAP",
        }


def _teks_konten(result: dict[str, Any]) -> str:
    """Gabungkan semua bagian teks pada ``result.content`` MCP."""
    potongan: list[str] = []
    for bagian in result.get("content") or []:
        if isinstance(bagian, dict) and bagian.get("type") == "text":
            potongan.append(str(bagian.get("text", "")))
    return "".join(potongan).strip()
