"""Factory SAP provider (Task 9) — default mock; AWS hanya dengan config eksplisit."""

from enum import Enum

from app.sap_integration.mock_provider import MockSAPProvider
from app.sap_integration.provider_interface import SAPDataProvider


class ProviderKind(str, Enum):
    MOCK = "mock"
    AWS_MCP = "aws_mcp"


def get_provider(kind: str | ProviderKind = ProviderKind.MOCK) -> SAPDataProvider:
    if isinstance(kind, str):
        kind = ProviderKind(kind)
    if kind is ProviderKind.MOCK:
        return MockSAPProvider()
    raise NotImplementedError(
        "AwsMcpSapProvider = Sprint 3; konfigurasi eksplisit + kredensial di .env"
    )
