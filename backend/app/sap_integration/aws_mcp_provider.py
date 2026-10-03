"""AwsMcpSapProvider stub (Task 9) — eksplisit: belum diimplementasikan Sprint 1."""

from app.sap_integration.provider_interface import SAPDataProvider


class AwsMcpSapProvider(SAPDataProvider):
    """Stub eksplisit — pemilihan tanpa konfigurasi eksplisit ditolak factory."""

    def get_material_stock(self, plant: str) -> list[dict]:
        raise NotImplementedError("Sprint 3")

    def get_purchase_orders(self, plant: str) -> list[dict]:
        raise NotImplementedError("Sprint 3")

    def create_purchase_order(self, payload: dict) -> dict:
        raise NotImplementedError("Sprint 3")

    def get_business_partner(self, partner_id: str) -> dict:
        raise NotImplementedError("Sprint 3")

    def get_product_master(self, product_id: str) -> dict:
        raise NotImplementedError("Sprint 3")
