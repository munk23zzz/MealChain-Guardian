# Nabil Gap Points 1-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the useful Nabil patterns for SAP provider switching, supplier exclusion, and food-safety evidence without adding the two extra roles, while preserving our overview design and improving its location status presentation.

**Architecture:** Keep MealChain Guardian as the canonical system. Our existing deterministic backend, JWT/RBAC, Merkle evidence, AgentCore trace, three-role model, and Stitch-derived overview remain authoritative. Nabil's provider contract and compliance presentation are reference patterns only. The overview receives a focused presentation layer that consumes the existing `GET /balance/map` data and never recomputes safety-critical values in the browser.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Next.js 14 App Router, TypeScript, React, Recharts, MapLibre, Vitest, pytest, Ruff.

**Spec:** `docs/PRD.md`, `docs/Architecture.md`, `docs/Schema.md`, `docs/Skill.md`, `docs/design.md`, `Rules.md`, and `mockupui/cold_chain_integrity_console/DESIGN.md`.

## Global Constraints

- Keep exactly three roles: `sppg_head`, `sppg_nutritionist`, and `bgn_monitor`.
- Do not add `sppg_staff` or `dinas_admin`.
- Do not merge Nabil's mock-data mode or use fake values for live KPI, supply, demand, safety, or evidence states.
- LLMs never calculate safety-critical numbers. Deterministic backend code owns calculations and eligibility.
- High-risk actions require human approval before execution or supplier exclusion.
- `PASS`, `FAIL`, and `NEEDS_VERIFICATION` remain authoritative and cannot be overridden by UI or agents.
- Mock SAP data must remain visibly marked as mock data.
- Backend domain logic stays independent from API adapters.
- Write failing tests before production changes. Update `TODO.md` whenever a task status changes.
- Do not modify `docs/Architecture.md` or `docs/Schema.md` without Roy's explicit review.
- No commit, push, merge, or external deployment is part of this plan.

## Decisions shaped by poteto principles

- **Laziness Protocol** limits adoption to the smallest useful slices. We will not port Nabil's frontend or replace the existing dashboard.
- **Foundational Thinking** makes provider records, capability boundaries, and exclusion decisions explicit before implementation.
- **Redesign from First Principles** keeps one canonical three-role architecture instead of preserving incompatible role branches.
- **Subtract Before You Add** rejects Nabil's mock mode and duplicate UI data paths before adding provider and compliance capabilities.
- **Boundary Discipline** keeps provider selection, authentication, and exclusion validation at backend boundaries.
- **Type System Discipline** uses typed provider records and typed overview row data rather than `any` at new boundaries.
- **Experience First** drives the overview polish toward rapid shortage recognition without losing the current map, KPI strip, chart, or role-aware shell.
- **Exhaust the Design Space** is applied to the location breakdown by comparing compact table, grouped status sections, and responsive cards before selecting the least disruptive option.
- **Sequence Work into Verifiable Units** gives each phase a failing test, implementation, static gate, and runtime check.
- **Build the Lever** requires a reusable provider contract test and deterministic overview formatter rather than hand-checking each provider or row.
- **Prove It Works** requires real Docker API probes and browser interaction, not only unit tests.
- **Never Block on the Human** is applied to reversible exploration. Human confirmation remains required before execution because this plan changes scope and contracts.

## Scope

Included:

1. Point 1 from the gap analysis. Harden and extend the existing SAP provider-switchable architecture using the useful parts of Nabil's interface and capability model.
2. Point 2 from the gap analysis. Add a supplier exclusion workflow using our existing three-role approval boundary. No extra roles.
3. Point 3 from the gap analysis. Add a narrowly scoped compliance and food-safety evidence surface using deterministic rules and real stored evidence.
4. Preserve the existing overview design and combine only selected Nabil location-card ideas with it.
5. Polish the overview location breakdown for shortage, surplus, and balanced states.

Explicitly excluded:

- `sppg_staff` and `dinas_admin`.
- Wholesale replacement of our frontend with Nabil's frontend.
- Nabil's mock mode, mock KPI constants, and mock compliance readings.
- Real SAP tenant activation, AWS for SAP MCP provisioning, AgentCore Identity, and deployment.
- Changes to the locked schema or architecture documents before Roy reviews them.

## Alternatives

### Alternative A. Port Nabil's frontend and backend modules wholesale

Rejected. It duplicates contracts, introduces mock-mode risk, uses a different schema shape, and conflicts with our Merkle, AgentCore, and three-role decisions.

### Alternative B. Add only visual polish and defer all backend gaps

Rejected. Supplier exclusion and provider switching are boundary and safety concerns. Visual-only work would leave the identified capability gaps unresolved.

### Alternative C. Add narrow backend contracts, then thin UI adapters

Selected. It preserves our source of truth, allows Nabil's useful patterns to be evaluated independently, and makes every new capability testable without changing existing flows.

## Data structures

- `SAPCapability` and `DataSource` identify provider capability and provenance.
- Typed SAP records represent material stock, purchase orders, business partners, and product master fields.
- `SupplierExclusionRequest` carries supplier identity, reason, scope, and decision reference.
- `Decision` with `decision_type="supplier_exclusion"` carries the approval lifecycle.
- `OverviewLocationRow` contains `location`, `status`, `supplyKg`, `demandKg`, `deltaKg`, and `displayReason` derived from the existing map response.
- `CcpEvidence` contains batch, rule, measured value, threshold result, source, and timestamp. Missing measurements remain verification-needed.

## Phases

### Task 1. Freeze contracts and write the red tests

**Files:**
- Modify: `backend/tests/test_sap_integration_contract.py`.
- Create or modify: `backend/tests/test_supplier_exclusion*.py`.
- Modify: `frontend/tests/*` for the overview row contract.
- Modify: `TODO.md` only when the task status changes.

- [ ] Add tests proving the provider contract returns the same typed shape for mock and future providers.
- [ ] Add tests proving unsupported provider capability selection fails closed.
- [ ] Add tests proving supplier exclusion cannot execute without approved decision state and cannot be performed by `bgn_monitor`.
- [ ] Add frontend tests for ten location rows, all three status labels, Indonesian number formatting, and no horizontal overflow contract.
- [ ] Run the focused tests and record the expected failures.

**Verification:** The new tests fail for the missing behavior and existing suites remain runnable.

### Task 2. Normalize provider boundaries

**Files:**
- Modify: `backend/app/sap_integration/provider_interface.py`.
- Modify: `backend/app/sap_integration/factory.py`.
- Modify: `backend/app/sap_integration/mock_provider.py` only where needed to satisfy the contract.
- Modify: `backend/app/sap_integration/aws_mcp_provider.py` only to preserve an explicit unavailable state.
- Test: `backend/tests/test_sap_integration_contract.py` and provider factory tests.

- [ ] Reuse the existing typed provider records and capability enums in our repository.
- [ ] Add capability-aware selection without allowing an implicit switch away from `mock`.
- [ ] Preserve `DataSource.MOCK` and response labeling for mock data.
- [ ] Keep AWS MCP unimplemented unless credentials and explicit mode are supplied in a later approved task.
- [ ] Ensure unsupported capabilities produce a deterministic provider error rather than silent fallback.

**Verification:** Contract tests pass for mock mode. Unsupported AWS capability tests fail closed. Ruff and focused pytest pass.

### Task 3. Add the supplier exclusion domain contract

**Files:**
- Create: `backend/app/core/supplier_exclusion.py`.
- Modify: `backend/app/api/actions.py`.
- Modify: existing decision model/service files only if the current decision contract already supports the new decision type.
- Test: `backend/tests/test_supplier_exclusion.py` and API tests.

- [ ] Define deterministic validation for a non-empty reason, known supplier, valid target scope, and safety or reliability evidence reference.
- [ ] Represent exclusion as a decision requiring approval rather than a direct supplier mutation.
- [ ] Reuse current `sppg_head` and `sppg_nutritionist` approval rules. Keep `bgn_monitor` read-only.
- [ ] Reject duplicate approvals, expired decisions, rejected decisions, and unapproved execution.
- [ ] Make retries idempotent. An already excluded supplier must not create a second exclusion record.
- [ ] Return mock SAP provenance when the exclusion affects mock SAP data.

**Verification:** Core tests cover valid request, missing reason, unknown supplier, invalid status, unauthorized monitor, expired decision, and repeated execution. API tests prove HTTP status and error shape.

### Task 4. Add the supplier exclusion frontend entry point

**Files:**
- Modify: `frontend/components/RecommendationCard.tsx` or the smallest existing decision-detail surface.
- Modify: `frontend/components/ApprovalModal.tsx` only if the existing summary can represent exclusion safely.
- Modify: `frontend/lib/api.ts` with a typed request function.
- Create or modify: focused Vitest tests.

- [ ] Render a supplier exclusion recommendation only when returned by the backend.
- [ ] Show supplier, reason, evidence reference, mock-data badge, and expiry before approval.
- [ ] Reuse the current approval modal. Do not add an approve-all path.
- [ ] Hide mutation controls from `bgn_monitor` while retaining visible read-only evidence.
- [ ] Show loading, success, and error feedback near the action.

**Verification:** Vitest passes. Browser verification covers approver review, rejection, approval, and monitor read-only behavior against the live API.

### Task 5. Create deterministic compliance evidence read models

**Files:**
- Inspect and reuse: existing safety, freshness, batch, evidence, and ledger services.
- Create: a read-only backend service or response assembler in the existing service layer.
- Create or modify: API route and tests only after the read model is defined.

- [ ] Reuse stored temperature, freshness, batch, and evidence records.
- [ ] Expose CCP-style evidence as a read model, not as frontend-calculated safety.
- [ ] Preserve `FAIL` and `NEEDS_VERIFICATION` when values are missing or thresholds fail.
- [ ] Include source, timestamp, rule identifier, and evidence linkage for transparency.
- [ ] Mark mock SAP evidence explicitly.

**Verification:** Unit tests cover PASS, warning or verification-needed, FAIL, missing measurement, and mixed batch summary. API tests prove RBAC and response provenance.

### Task 6. Add a focused compliance surface

**Files:**
- Create: `frontend/components/ComplianceEvidencePanel.tsx` or equivalent focused component.
- Modify: `frontend/app/page.tsx` only to place it in the existing decision or agent-log context.
- Modify: `frontend/app/globals.css` for tokens and responsive layout.
- Test: focused component tests and role tests.

- [ ] Use the current Stitch console language and tokens.
- [ ] Present summary counts and a per-reading evidence list similar to Nabil's CCP board.
- [ ] Keep `Belum diukur` distinct from PASS.
- [ ] Link each reading to source and timestamp where available.
- [ ] Keep the panel read-only unless an existing approved workflow explicitly supports a mutation.

**Verification:** Vitest, TypeScript, lint, and live browser checks for all three roles. No new role or mock reading is introduced.

### Task 7. Redesign the overview location breakdown from the data shape

**Files:**
- Modify: `frontend/app/page.tsx` only for composition and derived display data.
- Modify or create: `frontend/components/OverviewLocationBreakdown.tsx`.
- Modify: `frontend/app/globals.css` for visual treatment.
- Test: `frontend/tests/overview-location-breakdown.test.tsx`.

- [ ] Keep the existing RoleHero, live-sync header, KPI strip, commodity pills, dark map panel, StockChart, and responsive shell.
- [ ] Add a dedicated location breakdown component so row layout is not embedded in the page.
- [ ] Use the existing `/balance/map` response fields. Do not recalculate safety or replace backend gap facts with a second formula.
- [ ] Use a compact desktop table with columns `Lokasi`, `Status`, `Pasokan`, `Kebutuhan`, and `Selisih`.
- [ ] Group or filter by status through accessible controls. Keep all ten locations available without hiding data.
- [ ] Use status badge plus text. Do not rely on color alone.
- [ ] Use tabular Indonesian number formatting and consistent spacing.
- [ ] Add a responsive card layout below the mobile breakpoint. Do not permit a wide table to overflow the viewport.

**Verification:** Component tests assert the supplied ten-location data is rendered exactly once, status semantics are present, and loading or empty states are honest. Browser checks cover desktop, tablet, and mobile widths.

### Task 8. Compare and polish three overview treatments

**Files:**
- Modify: `frontend/components/OverviewLocationBreakdown.tsx`.
- Modify: `frontend/app/globals.css`.
- Test: visual and semantic frontend tests.

- [ ] Compare compact table, three status sections, and responsive cards using the same `OverviewLocationRow` data.
- [ ] Select compact table plus status badges on desktop and cards on mobile. This keeps scan speed while preserving the current design.
- [ ] Render the target data as clear rows such as `Bandung | SURPLUS | 400 kg | 0 kg | Lebih 400 kg`, with no concatenated text.
- [ ] Add a summary line such as `4 surplus · 6 shortage · 0 seimbang` from the actual rows.
- [ ] Give surplus, shortage, and balanced rows distinct semantic labels and accessible contrast.
- [ ] Keep minimum interactive targets at 44 by 44 pixels if rows or filters are clickable.
- [ ] Add reduced-motion-safe transitions only for hover or selection feedback.

**Verification:** UI tests, accessibility assertions, and live browser inspection confirm readable spacing, no concatenated values, no horizontal scroll, and preserved map/chart design.

### Task 9. Full integration and review gate

**Files:**
- Modify: `TODO.md` with completed task notes.
- Create: verification evidence under `docs/verification/` if required by the active sprint.

- [ ] Run backend pytest and Ruff.
- [ ] Run frontend Vitest, TypeScript, lint, and production build.
- [ ] Probe provider mode and data-source labeling through the live backend.
- [ ] Exercise supplier exclusion through proposal, approval, rejection, and retry paths.
- [ ] Exercise compliance evidence with PASS, FAIL, and missing-measurement data.
- [ ] Log in as all three roles and verify overview, exclusion controls, and compliance visibility.
- [ ] Run Event 1, Event 2, and Event 3 rehearsal checks without changing their existing contracts.
- [ ] Review the diff for accidental extra roles, mock-mode leakage, secret exposure, and schema drift.

**Verification commands:**

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec frontend npm run test
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

## Applicable skills

- `writing-plans` for task boundaries and testable handoff.
- `ui-ux-pro-max` for accessibility, responsive table/card behavior, status semantics, and data-dense dashboard polish.
- `frontend-design` for visual implementation after plan approval.
- `test-driven-development` for new backend core logic.
- `webapp-testing` for live browser verification.
- `systematic-debugging` if a live flow exposes a regression.
- `verification-before-completion` before marking any task Done.
- `requesting-code-review` before merging work from the second developer.
- `receiving-code-review` when addressing Nabil's review comments.
- `deslop` and `unslop` before any commit or user-facing documentation update.

## Handoff

This is a plan only. No project source files were changed. The implementation requires Roy's confirmation because it adds backend contracts and a new approval-governed capability. The intended next step is to approve or revise the scope before execution.
