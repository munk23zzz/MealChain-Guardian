"""S3-14: Resilience acceptance — semua cabang chain disertifikasi via
failure injection deterministik (tanpa menunggu kegagalan provider acak).

Matriks (plan §S3-14):
    primary → success
    primary → fallback_1 → success
    primary → fallback_1 → fallback_2 → success
    primary → fallback_1 → fallback_2 → unavailable
Plus: verifier UNAVAILABLE → dual approval requirement (AND).
"""

from __future__ import annotations

import pytest

from app.ai_providers.resilience import (
    ProviderUnavailableError,
    with_fallback_chain,
)
from app.core.approval_matrix import approval_requirement


def test_branch_primary_success():
    def primary(prompt: str) -> str:
        return "ok-primary"

    result = with_fallback_chain(primary, prompt="p")
    assert result.text == "ok-primary"
    assert result.provider == "primary"
    assert result.fallback_used is False
    assert [a.name for a in result.attempts] == ["primary"]
    assert result.attempts[0].outcome == "succeeded"


def test_branch_primary_then_fallback1_success():
    def primary(prompt: str) -> str:
        raise RuntimeError("boom")

    def fallback_1(prompt: str) -> str:
        return "ok-f1"

    result = with_fallback_chain(
        primary,
        prompt="p",
        fallback_1=fallback_1,
        retry_policy={"max_retries": 0},
    )
    assert result.text == "ok-f1"
    assert result.provider == "fallback_1"
    assert result.fallback_used is True
    assert [a.name for a in result.attempts] == ["primary", "fallback_1"]


def test_branch_two_fallbacks_success():
    def primary(prompt: str) -> str:
        raise RuntimeError("boom")

    def fallback_1(prompt: str) -> str:
        raise RuntimeError("boom")

    def fallback_2(prompt: str) -> str:
        return "ok-f2"

    result = with_fallback_chain(
        primary,
        prompt="p",
        fallback_1=fallback_1,
        fallback_2=fallback_2,
        retry_policy={"max_retries": 0},
    )
    assert result.text == "ok-f2"
    assert result.fallback_used is True
    assert [a.name for a in result.attempts] == [
        "primary",
        "fallback_1",
        "fallback_2",
    ]


def test_branch_chain_exhausted_unavailable():
    def primary(prompt: str) -> str:
        raise RuntimeError("boom")

    def fallback_1(prompt: str) -> str:
        raise RuntimeError("boom")

    def fallback_2(prompt: str) -> str:
        raise RuntimeError("boom")

    with pytest.raises(ProviderUnavailableError) as exc:
        with_fallback_chain(
            primary,
            prompt="p",
            fallback_1=fallback_1,
            fallback_2=fallback_2,
            retry_policy={"max_retries": 0},
        )
    attempts = exc.value.attempts
    assert [a.name for a in attempts] == ["primary", "fallback_1", "fallback_2"]
    assert all(a.outcome == "failed" for a in attempts)


def test_unavailable_verifier_requires_dual_approval():
    """Verdict UNAVAILABLE → requirement dual AND (S3-01 terkunci)."""
    req = approval_requirement("unavailable")
    assert req["min_approvals"] == 2
    assert req["required_roles"] == [["sppg_head"], ["sppg_nutritionist"]]
