"""Konteks supplier berasal dari relasi batch eksplisit, bukan lokasi."""

from types import SimpleNamespace
from uuid import uuid4


def test_context_without_supplier_is_honest():
    from app.api.supplier_exclusion_context import present_context

    result = present_context([], [], uuid4(), True)
    assert result["can_propose"] is False
    assert result["suppliers"] == []
    assert result["reason_unavailable"]


def test_context_monitor_read_only_and_batch_association():
    from app.api.supplier_exclusion_context import present_context

    supplier_id, batch_id, scope = uuid4(), uuid4(), uuid4()
    rows = [
        (
            SimpleNamespace(id=batch_id, safety_status="fail"),
            SimpleNamespace(id=supplier_id, name="Pemasok tercatat"),
        )
    ]
    result = present_context(rows, [], scope, False)
    assert result["can_propose"] is False
    assert result["suppliers"][0]["id"] == str(supplier_id)
    assert result["suppliers"][0]["evidence_refs"] == [{"type": "batch", "id": str(batch_id)}]
    assert result["suppliers"][0]["batches"][0]["safety_status"] == "fail"


def test_context_approver_requires_scope():
    from app.api.supplier_exclusion_context import present_context

    rows = [
        (
            SimpleNamespace(id=uuid4(), safety_status="pass"),
            SimpleNamespace(id=uuid4(), name="Pemasok"),
        )
    ]
    assert present_context(rows, [], None, True)["can_propose"] is False
    assert present_context(rows, [], uuid4(), True)["can_propose"] is True
