"""Factory SAP provider — default mock; unsupported mode/capability fail closed."""

from enum import Enum

from app.sap_integration.mock_provider import MockSAPProvider
from app.sap_integration.provider_interface import (
    SAPCapability,
    SAPDataProvider,
    UnsupportedCapabilityError,
)


class ProviderKind(str, Enum):
    MOCK = "mock"
    AWS_MCP = "aws_mcp"


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
        raise NotImplementedError(
            f"provider mode {kind.value!r} is unsupported: "
            "AwsMcpSapProvider requires a separately approved implementation "
            "and explicit credentials"
        )

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
