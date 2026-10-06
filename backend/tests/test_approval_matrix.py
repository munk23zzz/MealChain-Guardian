"""Test approval matrix murni (S3-01, TDD) — kontrak verifikasi Roy.

- CONSISTENT  → 1 approval: sppg_head ATAU sppg_nutritionist.
- FLAGGED     → 2 approval: sppg_head DAN sppg_nutritionist.
- UNAVAILABLE → 2 approval: sppg_head DAN sppg_nutritionist.
- bgn_monitor TIDAK PERNAH dihitung sebagai approver.
- Reject (approved=false) menggugurkan eksekusi.
"""

import pytest

from app.core.approval_matrix import (
    VALID_VERIFIER_VERDICTS,
    approval_requirement,
    evaluate_approvals,
)


def test_requirement_consistent_single_approval():
    req = approval_requirement("consistent")
    assert req["verdict"] == "consistent"
    assert req["min_approvals"] == 1
    assert req["required_roles"] == [["sppg_head", "sppg_nutritionist"]]


def test_requirement_flagged_dual_approval():
    req = approval_requirement("flagged")
    assert req["min_approvals"] == 2
    assert req["required_roles"] == [["sppg_head"], ["sppg_nutritionist"]]


def test_requirement_unavailable_dual_approval():
    req = approval_requirement("unavailable")
    assert req["min_approvals"] == 2
    assert req["required_roles"] == [["sppg_head"], ["sppg_nutritionist"]]


def test_requirement_rejects_unknown_verdict():
    with pytest.raises(ValueError):
        approval_requirement("maybe")


def test_valid_verdicts_exactly_three():
    assert VALID_VERIFIER_VERDICTS == {"consistent", "flagged", "unavailable"}


def test_evaluate_consistent_passes_with_head_only():
    req = approval_requirement("consistent")
    rows = [{"role": "sppg_head", "approved": True}]
    result = evaluate_approvals(req, rows)
    assert result["satisfied"] is True
    assert result["missing"] == []


def test_evaluate_consistent_fails_without_approval():
    req = approval_requirement("consistent")
    result = evaluate_approvals(req, [])
    assert result["satisfied"] is False
    assert result["missing"] == [["sppg_head", "sppg_nutritionist"]]


def test_evaluate_consistent_ignores_bgn_monitor():
    req = approval_requirement("consistent")
    rows = [{"role": "bgn_monitor", "approved": True}]
    result = evaluate_approvals(req, rows)
    assert result["satisfied"] is False


def test_evaluate_flagged_requires_both_roles():
    req = approval_requirement("flagged")
    head_only = evaluate_approvals(req, [{"role": "sppg_head", "approved": True}])
    assert head_only["satisfied"] is False
    both = evaluate_approvals(
        req,
        [
            {"role": "sppg_head", "approved": True},
            {"role": "sppg_nutritionist", "approved": True},
        ],
    )
    assert both["satisfied"] is True


def test_evaluate_rejection_blocks_execution():
    req = approval_requirement("consistent")
    rows = [
        {"role": "sppg_head", "approved": True},
        {"role": "sppg_nutritionist", "approved": False},
    ]
    result = evaluate_approvals(req, rows)
    assert result["satisfied"] is False
    assert result["rejected"] is True
