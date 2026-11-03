"""Focused factory contract tests for SAP provider selection."""

import pytest

from app.sap_integration.aws_mcp_provider import SAPConfigurationError
from app.sap_integration.factory import ProviderKind, get_provider
from app.sap_integration.mock_provider import MockSAPProvider


def test_factory_defaults_to_mock_without_mode_override():
    provider = get_provider()
    assert isinstance(provider, MockSAPProvider)


def test_factory_accepts_mock_string_and_enum():
    assert isinstance(get_provider("mock"), MockSAPProvider)
    assert isinstance(get_provider(ProviderKind.MOCK), MockSAPProvider)


def test_factory_rejects_unknown_mode():
    with pytest.raises(ValueError):
        get_provider("not-a-provider")


def test_factory_does_not_silently_fallback_for_unsupported_aws_mode():
    """Tanpa SAP_MCP_ENDPOINT, mode aws_mcp ditolak — bukan jatuh ke mock.

    Dulu stub melempar NotImplementedError; sekarang adapter MCP benar-benar ada
    (A4), jadi penolakannya berbentuk SAPConfigurationError yang menyebut env
    yang harus diisi.
    """
    with pytest.raises(SAPConfigurationError, match="SAP_MCP_ENDPOINT"):
        get_provider(ProviderKind.AWS_MCP)
