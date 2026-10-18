"""Factory SAP provider — default mock; unsupported mode/capability fail closed."""

from enum import Enum

from app.core.config import settings
from app.sap_integration.aws_mcp_provider import AwsMcpSapProvider
from app.sap_integration.mock_provider import MockSAPProvider
from app.sap_integration.provider_interface import (
    SAPCapability,
    SAPDataProvider,
    UnsupportedCapabilityError,
)


class ProviderKind(str, Enum):
    MOCK = "mock"
    AWS_MCP = "aws_mcp"


def _aws_mcp_provider() -> SAPDataProvider:
    """Bangun adapter MCP dari settings; tolak bila konfigurasi tidak lengkap.

    Endpoint dibaca dari env (``SAP_MCP_ENDPOINT``) — tanpa itu adapter tidak
    mungkin bicara ke SAP mana pun, dan menebak alamat adalah cara tercepat
    mengirim data ke tenant yang salah.
    """
    return AwsMcpSapProvider(
        endpoint=settings.sap_mcp_endpoint,
        token=settings.sap_mcp_token,
        timeout_seconds=settings.sap_mcp_timeout_seconds,
        allow_write=settings.sap_mcp_allow_write,
        tool_names={
            "material_stock": settings.sap_mcp_tool_stock,
            "purchase_orders": settings.sap_mcp_tool_purchase_orders,
            "create_purchase_order": settings.sap_mcp_tool_create_purchase_order,
            "business_partner": settings.sap_mcp_tool_business_partner,
            "product_master": settings.sap_mcp_tool_product_master,
        },
    )


def get_provider(
    kind: str | ProviderKind = ProviderKind.MOCK,
    *,
    capability: str | SAPCapability | None = None,
) -> SAPDataProvider:
    """Pilih adapter tanpa fallback diam-diam.

    ``capability`` opsional agar signature lama tetap valid. Jika diberikan,
    capability harus didukung adapter; material documents yang belum ada akan
    menghasilkan error deterministik, termasuk pada mode mock.
    """
    if isinstance(kind, str):
        kind = ProviderKind(kind)
    if kind is ProviderKind.MOCK:
        provider = MockSAPProvider()
    else:
        provider = _aws_mcp_provider()

    if capability is None:
        return provider
    try:
        requested = (
            capability
            if isinstance(capability, SAPCapability)
            else SAPCapability(capability)
        )
    except ValueError as exc:
        raise UnsupportedCapabilityError(
            f"SAP capability {capability!r} is unsupported"
        ) from exc
    if requested not in provider.capabilities:
        raise UnsupportedCapabilityError(
            f"SAP capability {requested.value!r} is unsupported by "
            f"provider {kind.value!r}"
        )
    return provider
