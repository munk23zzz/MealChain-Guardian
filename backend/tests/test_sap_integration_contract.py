"""Test kontrak SAPDataProvider / MockSAPProvider (Task 9)."""

import pytest

from app.sap_integration.factory import ProviderKind, get_provider
from app.sap_integration.mock_provider import MockSAPProvider
from app.sap_integration.provider_interface import SAPDataProvider


def test_factory_default_returns_mock():
    p = get_provider()
    assert isinstance(p, MockSAPProvider)


def test_factory_rejects_unknown_kind():
    with pytest.raises(ValueError):
        get_provider("unknown-provider")


def test_factory_aws_mcp_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        get_provider(ProviderKind.AWS_MCP)


def test_mock_stock_has_data_source_mock():
    p = MockSAPProvider()
    rows = p.get_material_stock("1000")
    assert len(rows) == 3
    assert all(r["DataSource"] == "MOCK" for r in rows)


def test_mock_po_and_create_order_guard():
    p = MockSAPProvider()
    pos = p.get_purchase_orders("1000")
    assert len(pos) == 1
    assert pos[0]["PurchaseOrder"] == "4500000001"
    with pytest.raises(PermissionError):
        p.create_purchase_order({"anything": 1})


def test_contract_defines_all_five_methods():
    """Plan Task 9: 5 methods wajib di kontrak SAPDataProvider."""
    for method in (
        "get_material_stock",
        "get_purchase_orders",
        "create_purchase_order",
        "get_business_partner",
        "get_product_master",
    ):
        assert hasattr(MockSAPProvider, method), f"method {method} hilang"
        assert method in SAPDataProvider.__abstractmethods__, (
            f"{method} bukan abstract method kontrak"
        )


def test_stock_fields_match_skill_md_section6():
    """Field kontrak Skill.md §6 API_MATERIAL_STOCK: MatlStkQty & BaseUnit."""
    p = MockSAPProvider()
    rows = p.get_material_stock("1000")
    required = {"MaterialNumber", "Plant", "StorageLocation", "Batch", "MatlStkQty", "BaseUnit"}
    for row in rows:
        missing = required - set(row)
        assert not missing, f"field kontrak hilang: {missing}"
        assert row["DataSource"] == "MOCK"


def test_unknown_plant_returns_empty_list():
    """Unknown material/plant → list kosong, bukan crash."""
    p = MockSAPProvider()
    assert p.get_material_stock("PLANT-UNKNOWN") == []
    assert p.get_purchase_orders("PLANT-UNKNOWN") == []


def test_business_partner_lookup():
    p = MockSAPProvider()
    bp = p.get_business_partner("SUP001")
    assert bp["BusinessPartner"] == "SUP001"
    assert bp["DataSource"] == "MOCK"
    assert p.get_business_partner("UNKNOWN") == {}


def test_product_master_lookup():
    p = MockSAPProvider()
    product = p.get_product_master("TELUR")
    assert product.get("Product") == "TELUR"
    assert product.get("DataSource") == "MOCK"
