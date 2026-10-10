"""Pure validation rules for supplier exclusion boundaries."""

from dataclasses import dataclass
from uuid import UUID


class SupplierExclusionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExclusionRequest:
    supplier_id: UUID
    scope_location_id: UUID
    reason: str
    evidence_refs: list[dict]


def validate_request(request: ExclusionRequest) -> None:
    if not request.reason or not request.reason.strip():
        raise SupplierExclusionValidationError("reason wajib diisi")
    if not request.evidence_refs:
        raise SupplierExclusionValidationError("minimal satu evidence reference wajib")
    for ref in request.evidence_refs:
        if not isinstance(ref, dict) or ref.get("type") not in {"incident", "batch", "decision"}:
            raise SupplierExclusionValidationError("evidence reference tidak valid")
        try:
            UUID(str(ref.get("id")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise SupplierExclusionValidationError("evidence id tidak valid") from exc


def is_supplier_excluded(active_rows, supplier_id, scope_location_id) -> bool:
    return any(
        row.status == "active"
        and row.supplier_id == supplier_id
        and row.scope_location_id == scope_location_id
        for row in active_rows
    )
