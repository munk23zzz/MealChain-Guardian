"""Kontrak SAPDataProvider (Task 9) — adapter pattern Architecture.md §6.3."""

from abc import ABC, abstractmethod


class SAPDataProvider(ABC):
    """Kontrak akses data SAP untuk seluruh worker.

    Implementasi: MockSAPProvider (Sprint 1) dan AwsMcpSapProvider (Sprint 3).
    Aturan: tidak ada kredensial di kode; DataSource=MOCK wajib di respons mock.
    """

    @abstractmethod
    def get_material_stock(self, plant: str) -> list[dict]:
        """Stok material per plant — field kontrak Skill.md §6 API_MATERIAL_STOCK."""

    @abstractmethod
    def get_purchase_orders(self, plant: str) -> list[dict]:
        """Daftar PO mock per plant."""

    @abstractmethod
    def create_purchase_order(self, payload: dict) -> dict:
        """Hanya via approval flow Sprint 2 — mock menolak dengan PermissionError."""

    @abstractmethod
    def get_business_partner(self, partner_id: str) -> dict:
        """Lookup business partner; unknown → dict kosong."""

    @abstractmethod
    def get_product_master(self, product_id: str) -> dict:
        """Lookup product master; unknown → dict kosong."""
