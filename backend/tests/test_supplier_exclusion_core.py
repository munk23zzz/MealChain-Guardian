from uuid import uuid4

import pytest

from app.core.supplier_exclusion import (
    ExclusionRequest,
    SupplierExclusionValidationError,
    is_supplier_excluded,
    validate_request,
)


def request(**changes):
    data = {
        "supplier_id": uuid4(),
        "scope_location_id": uuid4(),
        "reason": "temperature excursion",
        "evidence_refs": [{"type": "batch", "id": str(uuid4())}],
    }
    data.update(changes)
    return ExclusionRequest(**data)


def test_reason_must_not_be_blank():
    with pytest.raises(SupplierExclusionValidationError):
        validate_request(request(reason="  "))


def test_evidence_reference_is_required_and_typed():
    with pytest.raises(SupplierExclusionValidationError):
        validate_request(request(evidence_refs=[]))
    with pytest.raises(SupplierExclusionValidationError):
        validate_request(request(evidence_refs=[{"type": "batch", "id": "bad"}]))


def test_active_exclusion_matches_supplier_and_receiving_scope_only():
    supplier, scope = uuid4(), uuid4()
    row = type(
        "Row", (), {"status": "active", "supplier_id": supplier, "scope_location_id": scope}
    )()
    assert is_supplier_excluded([row], supplier, scope)
    assert not is_supplier_excluded([row], supplier, uuid4())
    row.status = "rejected"
    assert not is_supplier_excluded([row], supplier, scope)
