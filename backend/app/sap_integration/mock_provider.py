"""MockSAPProvider (Task 9) — data statis kontrak SAP, DataSource=MOCK, tanpa kredensial."""

from app.sap_integration.provider_interface import SAPDataProvider

_STOCK = {
    "1000": [
        {
            "MaterialNumber": "TELUR", "Plant": "1000", "StorageLocation": "FG01",
            "QuantityKG": 1400, "Unit": "KG", "DataSource": "MOCK",
        },
        {
            "MaterialNumber": "AYAM", "Plant": "1000", "StorageLocation": "FG01",
            "QuantityKG": 500, "Unit": "KG", "DataSource": "MOCK",
        },
        {
            "MaterialNumber": "WORTEL", "Plant": "1000", "StorageLocation": "FG01",
            "QuantityKG": 900, "Unit": "KG", "DataSource": "MOCK",
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


class MockSAPProvider(SAPDataProvider):
    def get_material_stock(self, plant: str) -> list[dict]:
        return list(_STOCK.get(plant, []))

    def get_purchase_orders(self, plant: str) -> list[dict]:
        return list(_POS.get(plant, []))

    def business_partners(self) -> dict:
        return dict(_BP)

    def create_purchase_order(self, payload: dict) -> dict:
        raise PermissionError(
            "create_purchase_order tidak boleh dieksekusi otomatis "
            "(Rules.md: butuh approval manusia)"
        )
