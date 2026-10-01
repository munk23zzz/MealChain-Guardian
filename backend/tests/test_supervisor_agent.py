"""Unit test Supervisor Agent (S0-07) — Strands di-mock, tanpa jaringan."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent"))

import pytest  # noqa: E402
import supervisor_agent  # noqa: E402


def test_system_prompt_states_deterministic_tools_rule() -> None:
    prompt = supervisor_agent.load_system_prompt()
    assert "safety-critical" in prompt.lower()
    assert "deterministik" in prompt.lower()


def test_build_agent_creates_one_agent_without_tools() -> None:
    mock_agent = MagicMock()
    with (
        patch.dict("os.environ", {"AWS_REGION": "us-west-2"}),
        patch("strands.models.BedrockModel") as mock_model,
        patch("strands.Agent", return_value=mock_agent) as mock_agent_cls,
    ):
        agent = supervisor_agent.build_agent("test-model-v1")
    assert agent is mock_agent
    mock_agent_cls.assert_called_once()
    # tanpa tools
    assert mock_agent_cls.call_args.kwargs["tools"] == []
    # model id diteruskan
    assert mock_model.call_args.kwargs["model_id"] == "test-model-v1"


def test_run_hello_world_requires_model_id() -> None:
    with patch.dict("os.environ", {"SUPERVISOR_MODEL_PRIMARY": ""}):
        with pytest.raises(RuntimeError, match="missing_config"):
            supervisor_agent.run_hello_world()


def test_run_hello_world_invokes_agent_with_prompt() -> None:
    mock_agent = MagicMock()
    mock_agent.return_value = MagicMock(__str__=lambda s: "MEALCHAIN_STRANDS_OK")
    with (
        patch.dict("os.environ", {"SUPERVISOR_MODEL_PRIMARY": "test-model-v1"}),
        patch.object(supervisor_agent, "build_agent", return_value=mock_agent),
    ):
        output = supervisor_agent.run_hello_world()
    mock_agent.assert_called_once_with("Balas tepat: MEALCHAIN_STRANDS_OK")
    assert "MEALCHAIN_STRANDS_OK" in output
