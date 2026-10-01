"""Unit test probe Bedrock (S0-04) — semua dengan boto3 mock, tanpa jaringan."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "aws"))

import verify_bedrock_access as probe  # noqa: E402


def _mock_session(mock_client: MagicMock) -> MagicMock:
    session = MagicMock()
    session.client.return_value = mock_client
    return session


def test_success_returns_sanitized_result() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = {"output": {"message": {}}}
    with patch.object(probe.boto3, "Session", return_value=_mock_session(mock_client)):
        result = probe.run_probe("us-west-2", "test-model-v1", "")
    assert result == {
        "service": "bedrock-runtime",
        "region": "us-west-2",
        "model_id": "test-model-v1",
        "status": "ok",
    }


def test_access_denied_maps_to_category() -> None:
    from botocore.exceptions import ClientError

    mock_client = MagicMock()
    mock_client.converse.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied for account 123456789012"}},
        "Converse",
    )
    with patch.object(probe.boto3, "Session", return_value=_mock_session(mock_client)):
        with pytest.raises(RuntimeError, match="iam_access_denied"):
            probe.run_probe("us-west-2", "test-model-v1", "")


def test_error_message_is_sanitized() -> None:
    dirty = "user arn:aws:iam::123456789012:user/x is not authorized"
    clean = probe.sanitize(dirty)
    # Sanitasi valid = tidak ada kebocoran account-id / ARN apa pun bentuknya
    # (account-id bisa termask <account> ATAU terhapus utuh bersama <arn>).
    assert "123456789012" not in clean
    assert "arn:aws" not in clean


def test_missing_model_id_exits_2() -> None:
    with patch.dict("os.environ", {"AWS_REGION": "us-west-2", "SUPERVISOR_MODEL_PRIMARY": ""}):
        assert probe.main() == 2


def test_missing_region_exits_2() -> None:
    with patch.dict("os.environ", {"AWS_REGION": "", "SUPERVISOR_MODEL_PRIMARY": "m"}):
        assert probe.main() == 2


import pytest  # noqa: E402
