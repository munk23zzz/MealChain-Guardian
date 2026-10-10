"""Kontrak adapter data SAP, terpisah dari client model SAP AI Core.

Dictionary keys dan signature publik tetap SAP-shaped agar caller lama tidak berubah.
TypedDict di sini hanya memberi anotasi boundary; tidak mengubah payload runtime.
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Literal, TypedDict


class SAPCapability(StrEnum):
    """Kemampuan adapter yang boleh dipilih secara eksplisit."""

    MATERIAL_STOCK = "material_stock"
    PURCHASE_ORDERS = "purchase_orders"
    CREATE_PURCHASE_ORDER = "create_purchase_order"
    BUSINESS_PARTNERS = "business_partners"
    PRODUCT_MASTER = "product_master"
    MATERIAL_DOCUMENTS = "material_documents"


class UnsupportedCapabilityError(NotImplementedError):
    """Capability diminta tetapi belum disediakan adapter terpilih."""


DataSourceValue = Literal["MOCK", "SAP"]


class MaterialStockRecord(TypedDict):
    MaterialNumber: str
    Plant: str
    StorageLocation: str
    Batch: str
    MatlStkQty: int | float
    BaseUnit: str
    DataSource: DataSourceValue


class PurchaseOrderRecord(TypedDict):
    PurchaseOrder: str
    Supplier: str
    Material: str
    Quantity: int | float
    Status: str
    DataSource: DataSourceValue


class BusinessPartnerRecord(TypedDict):
    BusinessPartner: str
    SupplierName: str
    DataSource: DataSourceValue


class ProductMasterRecord(TypedDict):
    Product: str
    ProductType: str
    BaseUnit: str
    ShelfLifeDays: int
    DataSource: DataSourceValue


class PurchaseOrderResult(TypedDict, total=False):
    PurchaseOrder: str
    DataSource: DataSourceValue


class SAPDataProvider(ABC):
    """Kontrak akses data SAP untuk seluruh worker.

    Implementasi saat ini hanya ``MockSAPProvider``. Material documents sengaja
    tidak termasuk capability mock; pemilihannya harus gagal tertutup.
    """

    capabilities: frozenset[SAPCapability] = frozenset()

    @abstractmethod
    def get_material_stock(self, plant: str) -> list[MaterialStockRecord]:
        """Stok material per plant — field kontrak Skill.md §6."""

    @abstractmethod
    def get_purchase_orders(self, plant: str) -> list[PurchaseOrderRecord]:
        """Daftar PO mock per plant."""

    @abstractmethod
    def create_purchase_order(self, payload: dict) -> PurchaseOrderResult:
        """Hanya via approval flow — mock menolak dengan PermissionError."""

    @abstractmethod
    def get_business_partner(self, partner_id: str) -> BusinessPartnerRecord:
        """Lookup business partner; unknown → dict kosong."""

    @abstractmethod
    def get_product_master(self, product_id: str) -> ProductMasterRecord:
        """Lookup product master; unknown → dict kosong."""
