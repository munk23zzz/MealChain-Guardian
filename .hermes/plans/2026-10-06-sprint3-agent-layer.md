# Sprint 3 — Agent Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to execute this plan task-by-task. Every production-code task follows RED → GREEN → REFACTOR, then spec-compliance review, code-quality review, parent verification, and a focused commit.

**Goal:** Membuktikan satu alur agentic end-to-end MealChain Guardian dari DETECT sampai ACT dengan Supervisor tunggal berbasis Strands/Bedrock AgentCore, deterministic backend tools, Verifier independen, human approval, dan Mock SAP yang dapat diaudit.

**Architecture:** Frontend memanggil FastAPI. FastAPI menyediakan auth/RBAC dan kontrak deterministic tools. Supervisor adalah satu-satunya full LLM agent dan berjalan di AgentCore Runtime melalui Strands. Supervisor hanya memilih/mengorkestrasi tools Gateway dan menafsirkan hasil; semua angka safety-critical tetap dihitung di deterministic core. Verifier adalah REST model call terpisah, bukan agent kedua berbasis Strands. Execution ke Mock SAP hanya terjadi sesudah approval manusia.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/Alembic, PostgreSQL 16, Next.js 14/TypeScript, Vitest, Strands SDK, Amazon Bedrock AgentCore Runtime/Gateway/Memory/Observability, SAP AI Core provider interface, Mock SAP.

**Spec:** `docs/verification/sprint-0-2-cross-sprint-audit.md`, `IDEA.md`, `TODO.md`, `Rules.md`, `workflows.md`, `Roadmap.md`, `docs/PRD.md`, `docs/Architecture.md`, `docs/Schema.md`, `docs/Skill.md`.

## Global Constraints

- Sprint 3 implementation **tidak boleh dimulai** sebelum S3-00 PASS.
- Exactly three roles: `sppg_head`, `sppg_nutritionist`, `bgn_monitor`; `sppg_staff` dan `dinas_admin` dilarang.
- Safety `FAIL` adalah hard exclusion dan tidak dapat dihidupkan kembali oleh LLM, verifier, score, atau Supervisor.
- LLM tidak menghitung freshness, safety, price deviation, logistics, capacity, Candidate Score, Safe Delivered Cost, KPI, atau approval requirement.
- Formula SDC final: `Expected Loss = 0.2 × (1 − freshness) × Purchase Cost`; freshness risk `0.50 × purchase` bila `< 0.60`; Decimal + HALF_UP 2dp.
- `supplier_quote` memakai `supplier_id` terpisah; `price_signals.seed_key` tetap tidak ada; `decisions.expires_at` tetap NOT NULL.
- Supervisor adalah satu-satunya full LLM agent. Verifier dan Forecast Provider bukan Strands agents.
- Semua external model calls memakai satu shared `with_fallback_chain`.
- Tidak ada autonomous approval atau automatic high-risk execution.
- Mock SAP tetap diberi label `X-Data-Source: MOCK`; tidak ada klaim SAP ERP production.
- `DEMO_MODE=false` default; tidak ada secret/credential/API key di Git, logs, prompt, context, trace payload, atau frontend bundle.
- PostgreSQL adalah operational source of truth; deterministic core tetap independently testable.
- `LEARN` hanya boleh dibuat sebagai explicit dependency sampai receiving inspection dan decision outcome tersedia.
- `docs/Architecture.md`, `docs/Schema.md`, `Rules.md`, `PRD.md`, `IDEA.md`, dan `Roadmap.md` tidak boleh diubah struktural tanpa ruling Owner.
- Sprint 3 tidak mengerjakan Event 2/3, KPI dashboard, chaos toggle, real SAP, atau Sprint 4.

## Preflight blockers dari audit

- Current AWS credentials/provider values tidak tersedia; `aws sts get-caller-identity` exit 253.
- Backend container AWS/provider env belum tersedia.
- `backend/openapi.json` belum ada.
- `agent/supervisor_agent.py`, `infra/aws/verify_bedrock_access.py`, dan `infra/aws/verify_agentcore_access.py` tidak ada di current tree; existing tests bersifat host-only/mock.
- Auth/RBAC, actions boundary, evidence fusion, receiving inspection, outcome, frontend login/dashboard masih carry-over.

Jika blocker provider tidak dapat disediakan oleh Owner, implementasikan contract/interface + deterministic failure tests, tetapi tandai live-provider acceptance sebagai `BLOCKED`; jangan membuat successful fake evidence.

---

### S3-00: Preflight Contract Gate

**Objective:** Memastikan semua prerequisite lintas Sprint 0–2 jelas sebelum satu production-code task agent dimulai.

**Files:**
- Read: `docs/verification/sprint-0-2-cross-sprint-audit.md`, seluruh source-of-truth docs.
- Create/update: `docs/verification/sprint-3.md` hanya setelah implementasi selesai; untuk preflight gunakan audit doc/addendum yang disetujui.
- Do not modify domain logic.

**Checks:**

```bash
git status --short
docker compose exec -T backend alembic current
docker compose exec -T backend alembic heads
docker compose exec -T backend pytest -q
test -f backend/openapi.json
docker compose exec -T backend python -c "import sys; print(sys.version)"
```

**Acceptance:** migration single head 006; current final gate remains green; exactly three roles remain; no schema drift; OpenAPI decision documented; auth/RBAC/actions/evidence/provider blockers explicitly assigned. If any hard prerequisite is unresolved, stop and obtain Owner/provider action before S3-01.

**Commit:** documentation-only gate record if needed: `docs: record sprint 3 preflight contract gate`.

### S3-01: Auth, RBAC, Approval Matrix, and OpenAPI Readiness

**Objective:** Menutup prerequisite security/action contract dan menghasilkan OpenAPI artifact bersih tanpa mengubah deterministic formulas.

**Files:**
- Create/modify: `backend/app/api/auth.py`, auth dependency/security module, user service, and `backend/app/api/dependencies.py` following existing style.
- Create/modify: `backend/app/api/actions.py`, `backend/app/services/action_service.py`.
- Create migration/model only if approved contract requires `decisions.outcome`, receiving inspection, or demo account persistence; otherwise record dependency rather than guessing schema.
- Create: `backend/openapi.json` via reproducible generation command.
- Tests: `backend/tests/test_auth.py`, `backend/tests/test_rbac.py`, `backend/tests/test_actions.py`, `backend/tests/test_openapi_contract.py`.

**Required behavior:**

- JWT login returns a token containing DB-backed role and location scope.
- `GET` authenticated access follows the approved matrix; mutation requires `sppg_head|sppg_nutritionist`; `DELETE`/high-risk mutation requires admin-equivalent policy only if approved—do not invent a fourth role.
- `bgn_monitor` is read-only and cannot approve or execute.
- Verifier CONSISTENT requires one approval from either verifier role; FLAGGED/UNAVAILABLE requires both `sppg_head` and `sppg_nutritionist`.
- `actions.propose != actions.approve != actions.execute`.
- Execute rejects expired, rejected, unverified, or insufficiently approved decisions.
- Successful execute writes only Mock SAP and returns `X-Data-Source: MOCK`.
- Every protected route returns 401 without auth; no route silently remains open except explicitly documented health/readiness.
- Generate `backend/openapi.json` from the running FastAPI app and check deterministic diff/reproducibility.

**TDD acceptance:** focused tests must first fail for missing login/RBAC/actions, then pass; live unauthenticated probes must return 401; authenticated role matrix must be tested with real DB fixtures, not only mocks.

**Commit:** `feat: add jwt rbac and approval action boundary`.

### S3-02: Deterministic Tool Contract and AgentCore Gateway Registration

**Objective:** Register stable deterministic endpoints as Gateway tools without duplicating domain logic.

**Files:**
- Modify only thin routers/contracts: `backend/app/api/balance.py`, `backend/app/api/cost.py`, `backend/app/api/evidence.py`, and related schemas.
- Create/update: `backend/app/api/schemas.py` if established by current code style.
- Create: `agent/gateway_config/` or `infra/aws/agentcore-gateway/` registration artifact.
- Tests: `backend/tests/test_tool_contracts.py`, `backend/tests/test_gateway_mapping.py`.

**Required tool names/contracts:**

```text
supply.get
 demand.get
freshness.evaluate
safety.evaluate
price.deviation
logistics.estimate
evidence.fuse
cost.safe_delivered
balance.recommend
actions.propose
```

Schemas must expose exact input/output fields, Decimal strings where applicable, safety/freshness statuses, evidence IDs, expiry, and source labels. Do not expose secrets or raw DB credentials. `POST /cost/safe-delivered`, `/balance/analyze`, and `/evidence/fuse` remain explicit carry-over requirements; either implement them here or stop with a documented dependency before Gateway registration.

**Acceptance:** OpenAPI contains every registered tool; invalid payloads fail 4xx before domain execution; safety FAIL never reaches SDC; Gateway registration maps one tool to one existing endpoint; no formula is copied into router/Gateway code.

**Commit:** `feat: publish deterministic gateway tool contracts`.

### S3-03: Supervisor Minimal Tool Use

**Objective:** Make one actual Supervisor invocation call one deterministic tool through AgentCore Gateway.

**Files:**
- Create: `agent/supervisor_agent.py`.
- Create: `agent/prompts/supervisor_system_prompt.md`.
- Create: `agent/gateway_client.py` if Gateway SDK requires an adapter.
- Tests: `backend/tests/test_supervisor_contract.py`, `backend/tests/test_supervisor_gateway_call.py`.

**Implementation constraints:**

- Use Strands SDK and Bedrock model configured from environment.
- Supervisor receives structured decision context and tool schemas; it does not receive credentials.
- Tool result is treated as authoritative for all numeric/safety values.
- The prompt must explicitly prohibit arithmetic and safety override.
- Unit tests may use deterministic test doubles; one acceptance test must use an actual Gateway/backend path when provider access is available.

**Acceptance:** actual trace shows Supervisor invocation → Gateway tool call → backend deterministic result → Supervisor receives result. If AWS/provider access is unavailable, record the exact provider failure and leave live acceptance blocked; never label a mock trace actual.

**Commit:** `feat: add supervisor gateway tool use`.

### S3-04: Event 1 DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE

**Objective:** Orchestrate regional imbalance using current deterministic recommendation output while preserving all hard constraints.

**Files:**
- Modify: `agent/supervisor_agent.py`, agent context adapter, decision service only at orchestration seams.
- Tests: `backend/tests/test_event1_supervisor_flow.py`, `backend/tests/test_event1_safety_fallback.py`.

**Acceptance:**

- Event fixture identifies Cianjur surplus → Jakarta shortage.
- Supervisor retrieves supply/demand/evidence/candidates through tools.
- Unsafe candidate is excluded by deterministic tool; safe alternative remains available.
- Candidate Score and SDC values exactly equal deterministic backend output.
- Decision is persisted as `proposed` or `pending_approval`, never auto-approved.
- Expiry is persisted and later enforced.
- Event trace stores actual tool names/results, not fabricated text.

**Commit:** `feat: orchestrate event one regional imbalance`.

### S3-05: Shared Resilience Layer

**Objective:** Route every external model call through one bounded fallback chain.

**Files:**
- Create: `ai_providers/resilience.py` or the project-approved provider package location.
- Tests: `backend/tests/test_resilience.py`.

**Interface:**

```python
with_fallback_chain(
    primary=provider_a,
    fallback_1=provider_b,
    fallback_2=provider_c,
    timeout_seconds=...,
    retry_policy=...,
    circuit_breaker=...,
) -> ProviderResult
```

**Acceptance:** deterministic failure injection proves primary success; primary→fallback_1; primary→fallback_1→fallback_2; all unavailable; bounded timeout/retry; explicit provider status; no parallel custom fallback logic. Provider errors preserve code/message category without misclassifying every HTTP 402 as balance exhaustion.

**Commit:** `feat: add shared model resilience chain`.

### S3-06: Verifier REST Client

**Objective:** Add the independent verifier call without creating a second full agent.

**Files:**
- Create: `ai_providers/verifier_client.py`.
- Create: `agent/prompts/verifier_system_prompt.md`.
- Tests: `backend/tests/test_verifier_client.py`, `backend/tests/test_verifier_safety_guard.py`.

**Required provider order:** SAP AI Core primary → SAP AI Core fallback → Claude/Bedrock final fallback, all via S3-05.

**Acceptance:** verifier audits safety, freshness, candidate eligibility, evidence, logistics, cost, and rationale; returns structured `CONSISTENT|FLAGGED|UNAVAILABLE`; cannot override safety FAIL; unavailable maps to two-approval requirement; actual fallback list records only providers actually attempted/succeeded.

**Commit:** `feat: add verifier rest client with hard safety guard`.

### S3-07: Forecast Provider Client

**Objective:** Expose SAP-RPT-1.6 provider contract with honest deterministic fallback.

**Files:**
- Create: `ai_providers/forecast_client.py`.
- Tests: `backend/tests/test_forecast_client.py`.

**Acceptance:** primary label `SAP-RPT-1.6` is emitted only for actual successful provider response; unavailable provider returns `statistical_fallback` using Sprint 1 weighted moving average `0.5/0.3/0.2`; no fabricated SAP response; all calls use S3-05.

**Commit:** `feat: add forecast provider with statistical fallback`.

### S3-08: AgentCore Memory Decision Session

**Objective:** Isolate state between decision sessions and store only required operational context.

**Files:**
- Create: `agent/memory.py` or AgentCore Memory adapter.
- Tests: `backend/tests/test_agent_memory_isolation.py`.

**Acceptance:** session A and B cannot read each other's state; no secret/credential/unnecessary PII; memory keys include decision/session identity; provider unavailable is explicit and does not silently use shared global state.

**Commit:** `feat: isolate agent decision session memory`.

### S3-09: Actual AgentCore Observability

**Objective:** Capture real Supervisor/model/tool/fallback timestamps and trace IDs.

**Files:**
- Create: `agent/observability.py`.
- Tests: `backend/tests/test_observability_trace_contract.py` plus provider/live probe.

**Acceptance:** actual trace includes Supervisor invocation, tool call/result, model call, fallback only when it occurs, timestamps, decision context; test doubles are labeled synthetic; no fake trace is promoted as production evidence.

**Commit:** `feat: capture agentcore observability trace`.

### S3-10: Persist Actual `agent_traces`

**Objective:** Persist sanitized actual trace metadata to Postgres.

**Files:**
- Modify: `backend/app/models/decisions.py` only if fields are missing from approved Schema.
- Add migration only with explicit Schema ruling.
- Create trace persistence service and tests.

**Acceptance:** one row per actual trace step, decision FK valid, payload sanitized, fallback list exact, no fabricated `LEARN`; migration/model alignment verified.

**Commit:** `feat: persist actual agent trace metadata`.

### S3-11: Approval and Action Boundary E2E

**Objective:** Connect verified decisions to human approval and Mock SAP execution.

**Files:**
- Use S3-01 action router/service; add integration tests and frontend API client contract.
- Tests: `backend/tests/test_action_boundary_e2e.py`.

**Acceptance:** propose→verify→approval requirement→human approve→execute; rejected/expired decision blocked; BGN monitor cannot approve/execute; one consistent verifier approval vs flagged/unavailable dual approval; `sap_mock_purchase_orders` written only after valid approval; response/header remains MOCK.

**Commit:** `feat: enforce human approval before mock sap execution`.

### S3-12: Frontend Agent Flow

**Objective:** Add minimal real-data UI only after backend contracts are stable.

**Files:**
- Create/modify frontend login, recommendation feed, decision detail, agent activity components following `docs/design.md`.
- Tests: Vitest component/API contract tests and webapp-testing flow.

**Acceptance:** UI displays actual recommendation, score, SDC breakdown, safety/freshness, supplier, logistics, evidence, expiry, verifier state, approval state, and actual trace timeline. No hardcoded activity/recommendation. Login and role scope work against live API. Mock badge visible.

**Commit:** `feat: add real agent recommendation and approval views`.

### S3-13: Event 1 E2E Acceptance

**Objective:** Prove UI → Supervisor → AgentCore Runtime → Gateway → deterministic tools → verifier → decision → human approval → Mock SAP.

**Files:**
- Create: `backend/tests/test_event1_e2e_acceptance.py` and frontend E2E flow.
- Create/update evidence in `docs/verification/sprint-3.md`.

**Acceptance:** every hop is actual in the available environment; unavailable external hop is marked BLOCKED with provider error and not replaced by synthetic success. Safety FAIL alternative path and approval boundary are observable.

**Commit:** `test: certify event one agent e2e path`.

### S3-14: Resilience Acceptance

**Objective:** Certify all provider chain branches using deterministic failure injection.

**Files:**
- Tests: `backend/tests/test_sprint3_resilience_acceptance.py`.

**Acceptance:**

```text
primary → success
primary → fallback_1 → success
primary → fallback_1 → fallback_2 → success
primary → fallback_1 → fallback_2 → unavailable
```

Unavailable verifier produces `verifier_unavailable` and dual approval requirement. Tests do not wait for random provider failure.

**Commit:** `test: certify provider fallback branches`.

### S3-15: Security and Contract Review

**Objective:** Perform adversarial review before final gate.

**Checks:** no secrets/log leakage/PII; 401 unauthenticated protected routes; role matrix; expired decision blocked; safety FAIL blocked; no auto-approval/execution; Mock SAP labels; actual fallback trace; deterministic core unchanged; OpenAPI matches deployed routes; no model↔migration drift.

**Files:**
- Tests/review evidence only; update `docs/verification/sprint-3.md`.

**Commit:** `docs: record sprint 3 security and contract review`.

### S3-16: Final Sprint 3 Gate

**Objective:** Run fresh final verification from the latest committed HEAD and write actual evidence.

**Commands:**

```bash
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend pytest -q
docker compose exec -T backend ruff check .
docker compose exec -T frontend npm run test
docker compose exec -T frontend npm run lint
docker compose ps
docker compose exec -T backend alembic current
docker compose exec -T backend alembic heads
docker compose exec -T backend alembic history
```

Also run authenticated/unauthenticated live probes, provider/AgentCore checks relevant to the environment, Event 1 E2E, fallback acceptance, DB trace/decision/PO readback, and container log scan for `SyntaxError|ImportError|Traceback`.

**Acceptance:** `docs/verification/sprint-3.md` contains actual commands, exit codes, counts, provider identity, fallback identity, trace IDs, DB readback, mock labels, blockers, and residual debt. No AWS/SAP success is claimed without live evidence.

**Commit:** `docs: verify sprint 3 agent layer`.

## Plan self-review

1. **Task coverage:** S3-00 through S3-16 cover preflight, OpenAPI/Gateway, Supervisor, Event 1, resilience, Verifier, Forecast, Memory, Observability, trace persistence, approval/actions, frontend, E2E, fallback tests, security, and final gate.
2. **No second full LLM agent:** Verifier is REST provider client; Forecast is provider client; only Supervisor is full Strands agent.
3. **No LLM deterministic calculation:** every numeric result comes from existing deterministic endpoints/core and is compared in tests.
4. **No autonomous PO:** actions are separated and require human role approval; Mock SAP only.
5. **Unfinished Sprint 2 carry-over is explicit:** auth/RBAC, evidence fusion, standalone cost/analyze, demo accounts, frontend shell/login, OpenAPI, actions, outcome/receiving inspection, expiry job are prerequisites or dependencies rather than silently dropped.
6. **Provider unavailability is honest:** interfaces and injected failures may be tested locally, but live-provider/AgentCore acceptance remains BLOCKED until actual credentials/access are available.
7. **Architecture preserved:** no redesign of `docs/Architecture.md` or `docs/Schema.md`; any structural schema addition is a separate Owner-approved contract checkpoint.
8. **Central story preserved:** cross-regional balancing + food safety hard constraint + single Supervisor reasoning + AWS AgentCore + SAP ecosystem + human approval + auditability.

## Execution boundary

Plan ini selesai sebagai **planning-only deliverable**. Sprint 3 implementation **belum dimulai**. S3-00 wajib dijalankan dan harus PASS sebelum task production-code mana pun dimulai.
