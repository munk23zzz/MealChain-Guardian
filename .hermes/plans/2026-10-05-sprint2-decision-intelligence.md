# Sprint 2 — Decision Intelligence + Balancing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task. Every production-code task follows RED → GREEN → REFACTOR → spec-compliance review → code-quality review → parent verification.

**Goal:** Build a deterministic decision-intelligence layer that converts supply, demand, freshness, safety, price, logistics, and supplier reliability into ranked cross-regional candidates, Safe Delivered Cost, decision records, and approval-ready validity state.

**Architecture:** All calculations remain pure deterministic Python in `backend/app/core/`. Services orchestrate domain functions and database reads but never call an LLM. Thin FastAPI routers expose deterministic results; persistence stores decision facts and validity; the Supervisor receives structured results later and cannot recompute them.

**Tech Stack:** Python 3.12 in Docker, FastAPI, SQLAlchemy 2 async, PostgreSQL 16, Alembic, pytest, Ruff, Next.js 14, TypeScript, Vitest.

**Spec:** User-provided Sprint 2 plan in the chat; project contracts in `IDEA.md`, `Rules.md`, `workflows.md`, `Roadmap.md`, `TODO.md`, `docs/PRD.md`, `docs/Architecture.md`, `docs/Schema.md`, and `docs/Skill.md`.

## Global Constraints

- Exactly three roles: `sppg_head`, `sppg_nutritionist`, `bgn_monitor`.
- Obsolete roles `sppg_staff` and `dinas_admin` are forbidden.
- `safety_status = fail` is a hard exclusion and can never be resurrected by score.
- Freshness: `>= 0.85` = `pass`; `0.60 <= score < 0.85` = `needs_verification`; `< 0.60` = `fail`.
- LLM never calculates freshness, safety, price deviation, logistics, capacity, Candidate Score, Safe Delivered Cost, KPI, or approval requirement.
- Supervisor remains the only full LLM agent; no additional LLM worker agents are created.
- Mock SAP remains mock; no real SAP execution and no automatic PO execution.
- No autonomous approval; high-risk actions require human approval.
- `DEMO_MODE=false` remains the default.
- No secrets are added to Git.
- `pihps_reference` is the city/commodity market benchmark; `supplier_quote` is the supplier purchase signal with non-null `supplier_id`.
- `decisions.expires_at` is mandatory; `now < expires_at` is valid and `now >= expires_at` is expired.
- The live-only `price_signals.seed_key` drift is removed through an explicit reconciliation migration; deterministic UUID5/natural-key reconciliation remains the seed idempotency mechanism.
- Do not structurally redesign `Architecture.md` or `Schema.md` beyond the explicitly approved `expires_at` and `seed_key` reconciliation.
- Do not start Sprint 3.

## Execution Protocol

For every task that changes code:

1. Dispatch one fresh implementer subagent; never overlap writers.
2. Write the failing test first and run it in the backend container or frontend container.
3. Implement the minimum production behavior.
4. Run the focused test, then the relevant regression suite.
5. Refactor only after green.
6. Run spec-compliance review and code-quality review using the task diff.
7. Parent independently checks the diff and reruns the covering tests.
8. Update `TODO.md` only after verification and commit the task.
9. Record all deviations and rulings in `.superpowers/sdd/sprint2-decision-intelligence/progress.md`.

The subagent report is never final evidence. Delegation failure does not block safe parent execution, but the deviation must be recorded.

---

## Task 0: Sprint 1 Contract Reconciliation and Frontend Test Runner

**Objective:** Make the actual repository, database, migrations, ORM, seed, documentation, and frontend test command agree before adding decision logic.

**Files:**
- Modify: `docs/Schema.md` — add approved `decisions.expires_at TIMESTAMPTZ NOT NULL`.
- Modify: `docs/verification/sprint-1.md` — correct stale historical statements without hiding history; add the two approved rulings.
- Create: `backend/alembic/versions/005_reconcile_sprint1_schema.py`.
- Modify: `backend/app/models/price_signals.py` only if needed to prove no `seed_key` dependency; do not add the field.
- Modify: `frontend/package.json`.
- Create: `frontend/vitest.config.ts`, `frontend/tests/smoke.test.ts`, and the minimum frontend test setup if required.
- Create/update: frontend lockfile using the project’s package manager; do not hand-edit generated lock content.
- Test: `backend/tests/test_sprint1_contract_reconciliation.py`, plus existing contract tests.

**Required migration behavior:**

```python
revision = "005_reconcile_sprint1_schema"
down_revision = "004_supplier_quote_design"

# upgrade:
# - DROP COLUMN price_signals.seed_key only if it exists
# - do not delete price signal rows
# - no decision table yet unless the plan explicitly assigns it here

# downgrade:
# - restore only the migration's reversible schema change if a safe definition exists;
# - document that seed_key is intentionally not restored as an application contract.
```

The migration must be idempotent against the observed drift using PostgreSQL catalog checks or Alembic operations that work on the known database. It must not silently delete business rows.

**Frontend smoke contract:** `npm run test` must execute Vitest in a non-watch, reproducible mode and test that the existing shell renders or has its expected root content. Add only test infrastructure; do not build UI.

**Acceptance checks:**

```bash
docker compose exec -T backend alembic history
docker compose exec -T backend alembic current
docker compose exec -T backend alembic heads
docker compose exec -T backend pytest -q
docker compose exec -T frontend npm run test
docker compose exec -T frontend npm run lint
```

Verify directly that:

- `price_signals.seed_key` is absent after migration;
- `price_signals.supplier_id` exists in DB, ORM, migration, seed, and tests;
- 14 suppliers and 10 quote cities remain;
- source and supplier consistency constraints remain enforced;
- no obsolete role appears in active schema, migration, ORM, seed, or tests;
- `npm run test` exits 0.

**Commit:** `chore: reconcile Sprint 1 contracts before decision layer`

---

## Task 1: Deterministic Balancing Candidate Model

**Files:** Create `backend/app/core/candidate.py`; test `backend/tests/test_candidate.py`.

**Interface:** Define an immutable deterministic candidate representation with source location, destination location, commodity, positive quantity, demand fit, supply availability, freshness score/status, safety status, supplier reliability, logistics feasibility, price information, and delivered-cost inputs. Keep Candidate Score out of the model.

**Tests first:** cover positive quantity, source/destination reversal protection, invalid factor ranges, explicit safety status, and deterministic equality/serialization. A candidate with `source_location == destination_location` must be rejected; quantity must be strictly positive.

**Commit:** `feat: deterministic balancing candidate model`

## Task 2: Supply/Demand Gap Engine

**Files:** Create `backend/app/core/gaps.py`; test `backend/tests/test_gaps.py`.

**Interfaces:**

```python
calculate_surplus(supply_kg: Decimal, demand_kg: Decimal) -> Decimal
calculate_shortage(supply_kg: Decimal, demand_kg: Decimal) -> Decimal
calculate_supply_gap(supply_kg: Decimal, demand_kg: Decimal) -> SupplyDemandGap
```

Rules: surplus is `max(supply - demand, 0)`; shortage is `max(demand - supply, 0)`; negative quantities are rejected; no historical summing occurs in the pure engine. API/service latest-record selection must use the existing latest-record/source precedence contract.

Test Cianjur `1400/500 → surplus 900`, Jakarta `300/1000 → shortage 700`, equal values, zero values, negative rejection, and multiple snapshots selected by caller as latest only.

**Commit:** `feat: deterministic supply demand gap engine`

## Task 3: Capacity and Cross-Regional Candidate Generator

**Files:** Modify/create `backend/app/core/constraints.py` only through tested additions; create `backend/app/core/candidate_generation.py`; test `backend/tests/test_candidate_generation.py`.

**Interface:**

```python
generate_candidates(
    source_records, destination_records, batches, logistics_by_pair, *,
    commodity: str | None = None,
) -> list[Candidate]
```

Candidate quantity is:

```text
min(source_surplus, destination_shortage, available_eligible_quantity)
```

Exclude source shortage, destination surplus, commodity mismatch, safety fail, freshness fail, and infeasible logistics. Permit `needs_verification` as a review-required candidate, never as clean pass. Preserve exact capacity and delivery-window boundaries.

Tests must include Cianjur → Jakarta telur, multiple pairs, no overlap, insufficient quantity, safety/freshness hard exclusions, logistics infeasibility, and exact capacity feasibility.

**Commit:** `feat: cross regional candidate generation`

## Task 4: Supplier Reliability Foundation

**Files:** Create `backend/app/core/reliability.py`; test `backend/tests/test_reliability.py`.

**Interfaces:**

```python
normalize_supplier_reliability(value: Decimal | float | int | None) -> Decimal
get_supplier_reliability(supplier: SupplierFacts) -> Decimal
```

Accept values from 0 through 1 inclusive; reject values outside that range. Use the existing schema default `0.80` only when the contract explicitly supplies a missing value; do not invent prediction or ML behavior.

Tests: 0, 1, normal decimal, negative, greater than 1, and null/default behavior.

**Commit:** `feat: deterministic supplier reliability input`

## Task 5: Candidate Score Engine

**Files:** Create `backend/app/core/scoring.py`; test `backend/tests/test_scoring.py`.

**Interface:**

```python
calculate_candidate_score(factors: CandidateScoreFactors) -> CandidateScoreResult
```

Calculate:

```text
Demand Fit × Supply Availability × Freshness × Safety Eligibility
× Supplier Reliability × Logistics Feasibility
```

Validate all factors in `[0, 1]`. `safety_status == fail` produces score `0` and `eligible=False`; no score can resurrect it. Preserve `needs_verification` status in the result.

Tests: all ones, zero factor, safety fail, partial factors, needs verification, invalid bounds, repeated deterministic execution.

**Commit:** `feat: deterministic candidate score engine`

## Task 6: Safe Delivered Cost

**Files:** Create `backend/app/core/safe_delivered_cost.py`; test `backend/tests/test_safe_delivered_cost.py`.

**Interface:**

```python
calculate_safe_delivered_cost(inputs: SafeDeliveredCostInputs) -> SafeDeliveredCostResult
```

Use exactly:

```text
Purchase Cost
+ Transportation Cost
+ Handling Cost
+ Expected Loss
+ Freshness Risk Penalty
+ Safety Risk Penalty
```

Expected loss is `0.2 × (1 − freshness)`. Freshness risk triggers when freshness `< 0.60` with factor `0.50`. Safety risk is 10%. Safety fail is rejected before eligible-cost calculation and must not be ranked. Reject negative monetary inputs. Use Decimal for monetary values and deterministic rounding consistent with existing price behavior.

Tests: normal batch, freshness 1.0/0.85/0.75/<0.60, safety needs verification, safety fail, zero transport/handling, decimal values, negative rejection, repeatability. Keep the 0.75 example as arithmetic only, not PASS eligibility.

**Commit:** `feat: safe delivered cost engine`

## Task 7: Deterministic Candidate Ranking

**Files:** Create `backend/app/core/ranking.py`; test `backend/tests/test_ranking.py`.

**Interface:**

```python
rank_candidates(candidates: Sequence[ScoredCandidate]) -> list[RankedCandidate]
```

Primary key: Candidate Score descending. Secondary key: Safe Delivered Cost ascending. Explicit stable tie-breakers: source location, destination location, commodity, supplier id, and candidate id in ascending lexical order. Exclude safety-failed candidates before sorting; preserve a review-required marker for freshness verification.

Tests: score ordering, cost tie-break, exact tie, safety exclusion, freshness review status, repeated ordering.

**Commit:** `feat: deterministic candidate ranking`

## Task 8: Decision Persistence Schema

**Files:** Create `backend/alembic/versions/006_decision_persistence.py`; create decision ORM models under `backend/app/models/`; update `backend/app/models/__init__.py`; test `backend/tests/test_decision_schema.py`.

Follow `docs/Schema.md` exactly after the approved `expires_at` addition. Preserve source/destination, commodity, quantity, score, Safe Delivered Cost, cost breakdown, evidence references, status, created_at, expires_at, verifier fields, and approval fields where already defined. Add only explicitly required related tables/columns. Do not create a foreign key to a table that does not yet exist; respect migration ordering.

Required decision validity contract:

```text
expires_at TIMESTAMPTZ NOT NULL
now < expires_at  => valid
now >= expires_at => expired
```

Migration must be reversible and tested upgrade → downgrade → upgrade in an isolated database. Test tables, constraints, indexes, nullable rules, `expires_at`, and status checks.

**Commit:** `feat: decision persistence schema`

## Task 9: Deterministic Recommendation Service

**Files:** Create `backend/app/services/recommendation_service.py`; test `backend/tests/test_recommendation_service.py`.

Pipeline:

```text
fetch operational facts
→ calculate latest supply/demand gaps
→ generate candidates
→ eliminate hard-constraint failures
→ calculate Candidate Score
→ calculate Safe Delivered Cost
→ rank
→ return deterministic recommendation set
```

Service must not import or call LLM/agent/SAP execution code. Cianjur → Jakarta telur must produce the expected candidate under the seed. Return structured facts sufficient for the future Supervisor context.

**Commit:** `feat: deterministic recommendation service`

## Task 10: Decision Intelligence API

**Files:** Create/update `backend/app/api/balance.py`, `backend/app/api/decisions.py`; update `backend/app/main.py`; tests `backend/tests/test_api_decision_intelligence.py`.

Implement only:

```text
GET  /balance/{location}/{commodity}
POST /balance/recommend
POST /decisions
GET  /decisions/{decision_id}
```

`/balance` returns supply, demand, surplus/shortage, and candidate availability. `/balance/recommend` returns ranked candidates with score, Safe Delivered Cost, freshness/safety, logistics, supplier, price, and eligibility. `POST /decisions` persists a selected deterministic recommendation with non-null `expires_at`; it never executes a PO or approves automatically. `GET /decisions/{id}` returns state and computed validity.

Routers remain thin and delegate formulas to core/service. Test happy path, invalid location/commodity, no candidate, safety fail exclusion, persistence, expires_at, and deterministic ranking.

**Commit:** `feat: decision intelligence API`

## Task 11: Decision Expiry and Validity

**Files:** Create `backend/app/core/decision_validity.py`; update decision service/model/API as needed; test `backend/tests/test_decision_validity.py`.

**Interface:**

```python
is_decision_valid(now: datetime, expires_at: datetime) -> bool
```

Require timezone-aware timestamps; reject invalid/mixed timezone input. Exact expiry is expired. Expired decisions cannot be eligible for later execution or recommendation reuse, but remain persisted for audit.

**Commit:** `feat: deterministic decision expiry`

## Task 12: Supervisor Decision Context Contract

**Files:** Create `backend/app/core/decision_context.py`; test `backend/tests/test_decision_context.py`.

Create a serializable structured context containing supply facts, demand facts, candidate list, Candidate Score, Safe Delivered Cost, safety/freshness statuses, price anomaly, logistics, supplier identity, and evidence references. No secrets, API keys, passwords, or raw credentials. The context is an output contract for the Supervisor; it must not calculate or reinterpret values.

Test JSON serialization, required keys, deterministic serialization/order, and secret absence.

**Commit:** `feat: supervisor decision context contract`

## Task 13: Frontend Test Infrastructure

**Files:** `frontend/package.json`, package lock, `frontend/vitest.config.ts`, `frontend/tests/smoke.test.ts`, minimal setup files.

Use Vitest with a non-watch script:

```json
"test": "vitest run"
```

Test the existing frontend shell only. Run inside the frontend container and ensure clean install reproducibility. Do not add dashboard, login, or decision UI.

**Commit:** `test: add frontend test runner`

## Task 14: Integration and Demo Scenarios

**Files:** Create `backend/tests/test_sprint2_scenarios.py`; update `TODO.md` only after evidence.

Run deterministic scenarios:

1. Cianjur 1400 supply / 500 demand → surplus 900; Jakarta 300 / 1000 → shortage 700; Cianjur → Jakarta telur candidate exists.
2. Reference 26,500 / Supplier C 32,000 → anomalous and flagged.
3. Temperature excursion → safety FAIL → candidate eliminated; safe alternative remains eligible where seeded.
4. Supplier A/B/C/D quotes preserve `supplier_id` independently from generic source.
5. Freshness in 0.60–<0.85 preserves `needs_verification` and is not clean PASS.

Repeat each deterministic scenario 10 times and compare canonical outputs. Target: at least 9/10 successful executions, with deterministic functions producing identical results on every successful repeat. Record actual results.

**Commit:** `test: Sprint 2 decision intelligence scenarios`

## Task 15: Full Acceptance Gate and Documentation

**Files:** Create `docs/verification/sprint-2.md`; update `TODO.md` and `Roadmap.md` only with verified statuses.

Run exactly:

```bash
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend pytest -q
docker compose exec -T backend ruff check .
docker compose exec -T frontend npm run test
docker compose exec -T frontend npm run lint
docker compose ps
```

Also verify migration current/head, PostgreSQL health, Sprint 1 regression, Sprint 2 tests, frontend test, Candidate Score, Safe Delivered Cost, hard constraints, ranking, Cianjur → Jakarta, price anomaly, Supplier D, decision persistence, expiry, no PO execution, no real SAP claims, and no secrets committed.

Record exit codes, pass/fail counts, migration status, Docker status, demo repeat results, blockers, deviations, and technical debt. Never fabricate results.

**Commit:** `docs: verify Sprint 2 decision intelligence`

## Task 16: Final Separate Review

Use a fresh reviewer subagent on the complete branch diff and progress ledger. Review spec compliance, architecture, schema, deterministic formulas, hard constraints, security, migration quality, API thinness, test quality, and scope creep. If a behavioral issue is found, use RED → fix → GREEN → regression → scoped re-review. Do not document a correctness defect as technical debt without fixing or adjudicating it under the review protocol.

After the final review, stop and wait for Roy. Do not start Sprint 3.

---

## Contract Reconciliation Decisions Already Approved

1. `decisions.expires_at` is a required `TIMESTAMPTZ NOT NULL` field and is part of the Schema/ORM/migration/API contract.
2. Live-only `price_signals.seed_key` is not part of the application contract and must be removed through explicit migration `005_reconcile_sprint1_schema`; price rows remain intact and seed idempotency remains UUID5/natural-key based.

## Risks and Mitigations

- **Schema drift:** Task 0 checks actual PostgreSQL catalog against Alembic/ORM and makes the reconciliation explicit.
- **Decision expiry ambiguity:** Task 8/11 use one timezone-aware validity predicate and exact-boundary tests.
- **Formula duplication:** all API routes call core/service functions; tests inspect route thinness and deterministic outputs.
- **Unsafe candidate resurrection:** candidate generation, scoring, cost, ranking, and API tests all enforce safety exclusion.
- **Frontend dependency reproducibility:** Task 13 adds declared dependency and lockfile, then runs `npm ci`/`npm run test` in the container.
- **Delegation outages:** parent may execute safely after recording the subagent deviation, but cannot skip independent verification or review.

## Plan Self-Review

- All user-provided Tasks 0–16 are represented.
- Approved `expires_at` and `seed_key` decisions are explicit in Task 0, Task 8, Task 11, and global constraints.
- No task starts Sprint 3 or implements prohibited UI, real SAP, autonomous PO execution, autonomous approval, or multi-agent LLM architecture.
- Every production-code task names a failing-test step and container verification command.
- Schema structural changes are limited to the explicitly approved `expires_at` addition and removal of the uncontracted live-only `seed_key` drift.
- Task dependencies are sequential: reconciliation → domain functions → persistence/service → API/context → frontend test infra → scenarios → acceptance/review.
- No placeholder decisions or invented formulas are left unresolved.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-05-sprint2-decision-intelligence.md`. Execute with `subagent-driven-development`: one fresh implementer per task, spec-compliance and code-quality review after each, and independent parent verification. Stop after Sprint 2 and wait for Roy review; do not start Sprint 3.
