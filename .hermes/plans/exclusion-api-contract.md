# Supplier exclusion API contract — canonical backend

**Coordination:** Parent implements `GET /supplier-exclusions/context/{decision_id}` in a separate API module (not `api/supplier_exclusions.py`, owned by backend worker). Context response: `{suppliers:[{id,name,batch_ids,evidence_refs}],scope_location_id,can_propose,reason_unavailable,exclusions:[record...]}`. Resolve evidence only from the exact decision and explicit batch FK; no location-derived supplier. Backend worker adds `supplier_governance` to approval-summary and blocks generic DecisionCreate administrative types.


## Create exclusion
`POST /supplier-exclusions/proposals` → 201
```json
{"supplier_id":"uuid","scope_location_id":"uuid","reason":"Measured issue","evidence_refs":[{"type":"batch","id":"uuid"}]}
```
Allowed evidence types: `batch` (Batch.id), `incident` (DecisionEvidence.id of type temperature), `decision` (Decision.id with persisted evidence referencing a supplier's batch). Every reference must exist and link to the chosen supplier. Scope is the **receiving SPPG**, matching actor.location_id. Roles head/nutritionist only; monitor 403.

Response record fields: `id`, `supplier_id`, `scope_location_id`, `status` (proposed|active|rejected|revoked), `reason`, `evidence_refs`, `source_decision_id`, nullable `restoration_decision_id`, `proposed_by`, nullable `activated_at`, `revoked_at`, `revocation_reason`, `created_at`. UUIDs/timestamps are strings. Administrative decision quantity, commodity and costs are null; no PO is created.

## Workflow (same existing actions, no separate approve endpoint)
Proposal creates a `pending_approval` decision. Call:
1. `POST /actions/verify {decision_id}` — existing server-side verifier, never browser verdict.
2. `GET /decisions/{decision_id}/approval-summary` — authoritative matrix/readiness.
3. `POST /actions/approve {decision_id,approved,comment}` — actual Approval rows. Reject requires comment. No activation yet.
4. `POST /actions/execute {decision_id}` — verifier, expiry, scoped approval matrix, current-state and evidence guards; atomically changes exclusion, decision and ledger. Administrative retry returns same executed state, no duplicate ledger.

## Restoration
`POST /supplier-exclusions/{id}/restore` → 201; body `{reason,evidence_refs}`. Must reference active exclusion and **new evidence IDs**. Response is same exclusion record (still `active`) with fresh `restoration_decision_id`. Apply the normal verify → fresh approvals → execute workflow to **this new ID**. Revocation never overrides FAIL batches. Exclusion itself never expires; only pending decisions expire (30 min).

## Read history
`GET /supplier-exclusions?supplier_id=uuid&scope_location_id=uuid&status=active` → `{items: record[], count: number}`. All authenticated roles can read. Each filter optional.

## Rejection and re-proposal
Rejected exclusion becomes `rejected`; rejected restoration leaves exclusion `active`. Generic `/actions/repropose` rejects administrative decisions with 409, directing operator to submit fresh evidence via the dedicated proposal/restore endpoint. This avoids copying old approvals or losing linkage. Exact duplicate pending exclusion proposal reuses its decision.

Errors use `{detail:string}`: 403 scope/role, 404 unknown supplier/exclusion, 422 invalid reason/evidence, 409 conflict/expired/unverified/missing approvals. Data source for administrative governance is `LOCAL`; no fabricated SAP provenance. Supplier/batch safety history remains independent.
