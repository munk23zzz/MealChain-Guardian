"""Pemilihan provider SAP: mock tetap default, aws_mcp dipilih secara eksplisit.

Yang dijaga di sini adalah *kontrak pemilihan*, bukan perilaku adapter (adapter
punya tesnya sendiri di ``test_aws_mcp_provider.py``):

- tanpa konfigurasi, ``aws_mcp`` DITOLAK dengan pesan yang menyebut nama env —
  tidak ada fallback diam-diam ke mock (data SAP palsu yang tampak nyata jauh
  lebih berbahaya daripada aplikasi yang menolak jalan);
- dengan konfigurasi lengkap, factory benar-benar mengembalikan adapter MCP;
- adapter nyata memenuhi protokol kontrak (lima metode) — suite yang hanya
  memakai provider palsu tidak akan menangkap metode yang hilang.
"""

import pytest

from app.core.config import settings
from app.sap_integration.aws_mcp_provider import AwsMcpSapProvider, SAPConfigurationError
from app.sap_integration.factory import ProviderKind, get_provider
from app.sap_integration.mock_provider import MockSAPProvider
from app.sap_integration.provider_interface import SAPDataProvider, UnsupportedCapabilityError


def test_default_tetap_mock():
    assert isinstance(get_provider(), MockSAPProvider)
    assert settings.sap_provider == "mock"


def test_aws_mcp_tanpa_endpoint_ditolak_dengan_pesan_env(monkeypatch):
    monkeypatch.setattr(settings, "sap_mcp_endpoint", "")
    with pytest.raises(SAPConfigurationError, match="SAP_MCP_ENDPOINT"):
        get_provider(ProviderKind.AWS_MCP)


def test_aws_mcp_dengan_konfigurasi_mengembalikan_adapter_mcp(monkeypatch):
    monkeypatch.setattr(settings, "sap_mcp_endpoint", "https://mcp.sap.example/mcp")
    monkeypatch.setattr(settings, "sap_mcp_token", "token-tenant")
    provider = get_provider("aws_mcp")
    assert isinstance(provider, AwsMcpSapProvider)
    provider.close()


def test_nama_tool_dari_settings_dipakai_adapter(monkeypatch):
    monkeypatch.setattr(settings, "sap_mcp_endpoint", "https://mcp.sap.example/mcp")
    monkeypatch.setattr(settings, "sap_mcp_tool_stock", "custom_stock_tool")
    provider = get_provider("aws_mcp")
    assert provider._tools["material_stock"] == "custom_stock_tool"
    provider.close()


def test_capability_tidak_didukung_gagal_tertutup(monkeypatch):
    monkeypatch.setattr(settings, "sap_mcp_endpoint", "https://mcp.sap.example/mcp")
    provider = get_provider("aws_mcp")
    with pytest.raises(UnsupportedCapabilityError):
        get_provider("aws_mcp", capability="material_documents")
    provider.close()


def test_implementasi_nyata_memenuhi_seluruh_protokol_kontrak():
    """Regresi: setiap metode kontrak ada di adapter MCP dan bisa dipanggil."""
    for nama in (
        "get_material_stock",
        "get_purchase_orders",
        "create_purchase_order",
        "get_business_partner",
        "get_product_master",
    ):
        # Didefinisikan di kelas adapter sendiri, bukan hanya diwarisi dari ABC.
        assert nama in AwsMcpSapProvider.__dict__, nama
    assert set(SAPDataProvider.__abstractmethods__) <= set(AwsMcpSapProvider.__dict__)
