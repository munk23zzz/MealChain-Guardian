"""Unit test probe AgentCore (S0-05) — boto3 mock, tanpa jaringan."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "aws"))

import pytest  # noqa: E402

# Skrip probe ada di infra/aws/ dan tidak disertakan di repo ini. Skip eksplisit
# supaya suite tetap bisa dikoleksi di lingkungan yang tidak punya probe-nya.
probe = pytest.importorskip(
    "verify_agentcore_access",
    reason="skrip probe infra/aws/verify_agentcore_access.py tidak ada di repo",
)


def _mock_session(mock_client: MagicMock) -> MagicMock:
    session = MagicMock()
    session.client.return_value = mock_client
    return session


def test_success_with_empty_runtime_list() -> None:
    mock_client = MagicMock()
    mock_client.list_agent_runtimes.return_value = {"agentRuntimes": []}
    with patch.object(probe.boto3, "Session", return_value=_mock_session(mock_client)):
        result = probe.run_probe("us-west-2", "")
    assert result == {
        "service": "bedrock-agentcore-control",
        "region": "us-west-2",
        "status": "ok",
        "runtime_count_returned": 0,
    }


def test_success_with_one_runtime_does_not_leak_arn() -> None:
    mock_client = MagicMock()
    mock_client.list_agent_runtimes.return_value = {
        "agentRuntimes": [
            {"agentRuntimeArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/x"}
        ]
    }
    with patch.object(probe.boto3, "Session", return_value=_mock_session(mock_client)):
        result = probe.run_probe("us-west-2", "")
    assert result["runtime_count_returned"] == 1
    assert "arn" not in str(result).lower()


def test_access_denied_maps_to_category() -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.list_agent_runtimes.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "ListAgentRuntimes"
    )
    with patch.object(probe.boto3, "Session", return_value=_mock_session(mock_client)):
        with pytest.raises(RuntimeError, match="iam_access_denied"):
            probe.run_probe("us-west-2", "")


def test_missing_region_exits_2() -> None:
    with patch.dict("os.environ", {"AWS_REGION": ""}):
        assert probe.main() == 2
