"""MockSAPProvider (Task 9) — field kontrak Skill.md §6, DataSource=MOCK, tanpa kredensial."""

from app.sap_integration.provider_interface import (
    BusinessPartnerRecord,
    MaterialStockRecord,
    ProductMasterRecord,
    PurchaseOrderRecord,
    PurchaseOrderResult,
    SAPCapability,
    SAPDataProvider,
)

_STOCK = {
    "1000": [
        {
            "MaterialNumber": "TELUR",
            "Plant": "1000",
            "StorageLocation": "FG01",
            "Batch": "BATCH-CIANJUR-TELUR-001",
            "MatlStkQty": 1400,
            "BaseUnit": "KG",
            "DataSource": "MOCK",
        },
        {
            "MaterialNumber": "AYAM",
            "Plant": "1000",
            "StorageLocation": "FG01",
            "Batch": "BATCH-CIANJUR-AYAM",
            "MatlStkQty": 500,
            "BaseUnit": "KG",
            "DataSource": "MOCK",
        },
        {
            "MaterialNumber": "WORTEL",
            "Plant": "1000",
            "StorageLocation": "FG01",
            "Batch": "BATCH-CIANJUR-WORTEL",
            "MatlStkQty": 900,
            "BaseUnit": "KG",
            "DataSource": "MOCK",
        },
    ],
}

_POS = {
    "1000": [
        {
            "PurchaseOrder": "4500000001",
            "Supplier": "SUP001",
            "Material": "TELUR",
            "Quantity": 500,
            "Status": "confirmed",
            "DataSource": "MOCK",
        }
    ],
}

_BP = {
    "SUP001": {
        "BusinessPartner": "SUP001",
        "SupplierName": "Supplier A Cianjur",
        "DataSource": "MOCK",
    },
    "SUP002": {
        "BusinessPartner": "SUP002",
        "SupplierName": "Supplier B Cianjur",
        "DataSource": "MOCK",
    },
    "SUP003": {
        "BusinessPartner": "SUP003",
        "SupplierName": "Supplier C Cianjur",
        "DataSource": "MOCK",
    },
}

_PRODUCT_MASTER = {
    "TELUR": {
        "Product": "TELUR",
        "ProductType": "FERT",
        "BaseUnit": "KG",
        "ShelfLifeDays": 28,
        "DataSource": "MOCK",
    },
    "AYAM": {
        "Product": "AYAM",
        "ProductType": "FERT",
        "BaseUnit": "KG",
        "ShelfLifeDays": 5,
        "DataSource": "MOCK",
    },
    "WORTEL": {
        "Product": "WORTEL",
        "ProductType": "FERT",
        "BaseUnit": "KG",
        "ShelfLifeDays": 21,
        "DataSource": "MOCK",
    },
}


class MockSAPProvider(SAPDataProvider):
    capabilities = frozenset(
        {
            SAPCapability.MATERIAL_STOCK,
            SAPCapability.PURCHASE_ORDERS,
            SAPCapability.CREATE_PURCHASE_ORDER,
            SAPCapability.BUSINESS_PARTNERS,
            SAPCapability.PRODUCT_MASTER,
        }
    )

    def get_material_stock(self, plant: str) -> list[MaterialStockRecord]:
        """Unknown plant → list kosong (bukan crash)."""
        return [dict(row) for row in _STOCK.get(plant, [])]

    def get_purchase_orders(self, plant: str) -> list[PurchaseOrderRecord]:
        return [dict(row) for row in _POS.get(plant, [])]

    def create_purchase_order(self, payload: dict) -> PurchaseOrderResult:
        raise PermissionError(
            "create_purchase_order tidak boleh dieksekusi otomatis "
            "(Rules.md: butuh approval manusia)"
        )

    def get_business_partner(self, partner_id: str) -> BusinessPartnerRecord:
        return dict(_BP.get(partner_id, {}))

    def get_product_master(self, product_id: str) -> ProductMasterRecord:
        return dict(_PRODUCT_MASTER.get(product_id, {}))
