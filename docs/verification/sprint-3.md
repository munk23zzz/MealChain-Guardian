# Sprint 3 Verification — Agent Layer (S3-00..S3-16)

> Semua angka di bawah adalah hasil eksekusi aktual (fresh run dari HEAD,
> 2026-10-06, container mealchain). Tidak ada klaim sukses provider eksternal
> tanpa evidence live; hop yang tidak tersedia dilaporkan jujur sebagai
> UNAVAILABLE/BLOCKED.

## Ringkasan gate

| Gate | Hasil | Evidence |
|---|---|---|
| Alembic upgrade/current/heads | PASS | `006_decision_persistence (head)` |
| Backend pytest | PASS | **402 passed**, 1 warning (pytest-asyncio deprecation, pre-existing) |
| Backend ruff | PASS | `All checks passed!` |
| Frontend vitest | PASS | **25 passed** (3 files) |
| Frontend lint | PASS | No ESLint warnings or errors |
| docker compose ps | PASS | backend/frontend/mock-sap Up, postgres healthy |
| Log scan backend+frontend | PASS | 0 SyntaxError/ImportError/Traceback pada state final (4 NameError historis selama edit import `User`, semua sebelum restart bersih `6660`) |
| `/health` unauth | PASS | 200 |
| `/decisions` unauth | PASS (diproteksi) | **401** setelah fix S3-15 (`6744978`) |
| OpenAPI vs routes | PASS | openapi.json regenerated — 23 paths, 0 missing/stale |
| core→api boundary | PASS | 0 import `app.api` di `app/core/` |
| Secrets/PII scan | PASS | 0 temuan (hanya docstring/detail 401) |
| DB readback | PASS | decisions/agent_traces 0 rows (test ter-cleanup), PO seed mock `4500000001/confirmed` utuh |

## Commit chain Sprint 3 (ground-truth git log)

```text
77d3fdc  feat: jwt auth rbac approval matrix action boundary (S3-01)
93ca711  feat: sdc standalone analyze evidence endpoints + tool registry gateway config (S3-02)
e47e11e  fix: serialize zero penalty as 2dp decimal (S3-02)
a512e5a  feat: add shared model resilience chain (S3-05)
689cf26  feat: add verifier rest client with hard safety guard (S3-06)
21ee4af  feat: add forecast provider with statistical fallback (S3-07)
0c21a39  feat: orchestrate event one regional imbalance (S3-03+04)
dacc592  feat: isolate agent decision session memory and observability trace (S3-08+09)
ffc22b2  feat: persist actual agent trace metadata (S3-10)
5e5525b  feat: enforce human approval before mock sap execution (S3-11)
45cb20e  feat: guardian dashboard ui with role scope and approval modal (S3-12)
4999615  feat: decision feed and agent trace timeline endpoints (S3-12 backend)
c478d5c  test: certify event one agent e2e path and provider fallback branches (S3-13+14)
6744978  fix: guard decision read endpoints behind auth (S3-15)
```

(Di atas ditambah 2 commit docs TODO.md. Baseline Sprint 2 = 296 passed →
final **402 passed** backend; frontend 25 test.)

## Bukti per slice (hasil aktual, bukan narasi)

- **S3-01 Auth/RBAC/actions boundary**: 323 passed. JWT HS256, 3 role
  (`sppg_head`, `sppg_nutritionist`, `bgn_monitor`), approval matrix
  CONSISTENT → OR; FLAGGED/UNAVAILABLE → dual AND
  `[["sppg_head"],["sppg_nutritionist"]]`.
- **S3-02 Tool registry + gateway config**: 332 passed. `/cost/safe-delivered`,
  `/balance/analyze`, `/evidence/fuse`, registry config-driven.
- **S3-05 Resilience chain**: 8/8. `with_fallback_chain(primary, prompt,
  fallback_1..3, timeout, retry_policy, circuit_breaker)`; kategori error
  402≠balance / 429 retryable; chain habis → `ProviderUnavailableError`.
- **S3-06 Verifier REST client**: 12/12. SAP primary → SAP fallback →
  Bedrock final via chain; guard keras: safety FAIL tidak bisa diangkat →
  FLAGGED; output tak terbaca → UNAVAILABLE.
- **S3-07 Forecast client**: 6/6. Label `SAP-RPT-1.6` hanya untuk response
  provider nyata; chain habis → `statistical_forecast` (0.5/0.3/0.2) dari
  core Sprint 1.
- **S3-03+04 Supervisor orchestrator (Event 1)**: 7/7. DETECT→VERIFY→TRACE→
  PREDICT→OPTIMIZE→DECIDE; trace aktual 6 langkah tersimpan; Strands Agent
  `agent/supervisor_agent.py` (root, di luar bind-mount) — **BLOCKED live**
  (AgentCore Runtime ARN kosong); orchestrator berjalan tanpa Strands di
  env lokal.
- **S3-08/09 Memory + Observability**: 14/14. Isolasi session (A≠B),
  sanitasi secret, trace aktual dengan label; AgentCore Memory/Gateway
  ARN kosong → adapter local, dilaporkan jujur.
- **S3-10 Trace persistence**: 382 passed. `persist_trace_steps` — payload
  disanitasi, `step_at` monoton per indeks (server_default `now()` membuat
  urutan hilang — fix eksplisit).
- **S3-11 Approval E2E**: 389 passed. Gap nyata ditemukan+fixed:
  `/actions/verify` tidak pernah menulis `verifier_note` → sekarang verdict
  tertulis; rejected/expired diblokir 409; bgn_monitor 403.
- **S3-12 Frontend**: 25/25 + tsc 0 error + build sukses. Login, feed
  (polling 5s), detail, ApprovalModal (friksi disengaja §1.3), role scope
  (bgn_monitor read-only §1.4), AgentTraceViewer dari trace DB, badge mock.
- **S3-13 Event 1 E2E**: 4/4. Jalur penuh supervisor→decision→propose→dual
  approve→execute→PO mock (MC-…, data_source=MOCK). Bug seam nyata ditemukan
  di E2E: orchestrator tidak menulis verifier_note → decision tak pernah
  bisa dieksekusi; fixed (verdict ditulis saat pembuatan).
- **S3-14 Resilience acceptance**: 5/5. Matriks 4 cabang chain (primary→ok,
  f1→ok, f2→ok, exhausted→unavailable) via failure injection deterministik;
  UNAVAILABLE → dual AND requirement.

## Konfigurasi provider (state aktual, semua nilai [REDACTED])

- Bedrock: LIVE via profile inference (`us.*`) — dibuktikan saat S3-00
  (STS + invoke sukses). Belum dipakai runtime orchestrator default
  (SUPERVISOR_MODEL_PRIMARY terpotong di .env; verifier/forecast tanpa
  konfigurasi → UNAVAILABLE jujur saat E2E).
- Inferhub: LIVE (429 retryable). SAP AI Core: partial (URL/client kosong).
- AgentCore Runtime ARN / Gateway URL / Memory: **KOSONG** → BLOCKED live;
  berjalan config-driven local (tool registry, local memory, local trace).

## Blockers (jujur)

- Live AgentCore Runtime + Gateway + Memory: butuh ARN/URL dari Owner.
- Live verifier/forecast model: butuh `VERIFIER_MODEL_*`, `FORECAST_MODEL`,
  `SUPERVISOR_MODEL_PRIMARY` lengkap di .env (nilai saat ini kosong/terpotong).
- Strands agent live run: butuh AgentCore Runtime; jalur local orchestrator
  sudah tersertifikasi penuh.

## Residual debt

- RBAC untuk endpoint lama Sprint 2 masih terbuka (carry-over eksplisit —
  menunggu putusan Roy).
- pytest-asyncio deprecation warning (pre-existing, non-blocking).
- Frontend tsconfig.tsbuildinfo artifact build (untracked, non-blocking).

## Model chain live per agent (permintaan Roy, 2026-10-06 — pasca gate S3-16)

Setiap agent (supervisor/verifier/forecast) kini punya rantai TEPAT 3 model:
primary + fallback_1 + fallback_2 — satu model mati, dua backup siap.
Backend = sumber konfigurasi (env); frontend menampilkan identitas
model/provider dari trace DB (display-only, `ProviderPanel`).

| Agent | primary | fallback_1 | fallback_2 |
|---|---|---|---|
| Verifier | Bedrock `us.anthropic.…` (LIVE probe 2.2s) | Inferhub `cb/kimi-k3` (LIVE, max_tokens 4000) | Inferhub `ali/qwen3.8-max-0902` (LIVE 2.5s) |
| Forecast | Bedrock `qwen.qwen3-vl-235b-a22b` (LIVE 0.6s) | Inferhub `cbcn/kimi-k3` (LIVE) | Inferhub `cb/kimi-k3` (LIVE) |
| Supervisor | Bedrock `us.anthropic.…` (LIVE) | Inferhub `cb/kimi-k3` (LIVE) | Inferhub `ali/qwen3.8-max-0902` (LIVE) |

Catatan konfigurasi:
- `global.moonshotai.kimi-k3` (Bedrock) dan `us.anthropic.…`#2/#3 INVALID
  saat probe (ValidationException/AccessDenied) → diganti kandidat Inferhub.
- ARN AgentCore terisi → jadi primary agent dan menggeser slot env
  (total tetap 3); implementasi runtime AgentCore = stub eksplisit
  NotImplementedError (honest-unavailable).

Evidence live (dalam container, chain env asli):
- Verifier: verdict FLAGGED, `primary:bedrock`, fallback_used=False,
  attempts=[{primary, succeeded}] — jujur terhadap seed (bukan CONSISTENT
  karangan).
- Forecast: method `provider_forecast`, qty 7230.0, `primary:bedrock`
  (bug bentuk jawaban ditemukan & fixed: prompt kini memuat kontrak output
  JSON; parser menerima array harian → mean×horizon deterministik).
- Supervisor: SUPERVISE narrated, `primary:bedrock` — narasi terakhir,
  TIDAK safety-critical (tidak mengubah verdict/rekomendasi/angka).
- Fallback Inferhub live: chain tanpa Bedrock → kimi timeout →
  `fallback_2:inferhub` (qwen) sukses, fallback_used=True, attempts jujur.

Arsitektur tambahan (TDD penuh, 435 passed total):
- `app/ai_providers/model_registry.py` — parsing env per agent
  (bedrock/inferhub/agentcore), legacy `SUPERVISOR_MODEL_FALLBACK` backfill.
- `app/ai_providers/bedrock_caller.py` / `inferhub_caller.py` — transport
  (converse / OpenAI-compatible), error dengan status_code untuk chain.
- `app/ai_providers/ai_provider_chain.py` — env → callable (SATU pintu).
- `app/services/supervisor_client.py` + langkah SUPERVISE di orchestrator
  (whitelist trace + migration `007_supervise_step`).
- Isolasi test: conftest mengosongkan env model utk unit test; probe live
  via `pytest -m live` marker (tidak jalan di sesi biasa).
- Frontend: `ProviderPanel` (status jujur per agent, hijau hanya bila
  live) + identitas model di AgentTraceViewer; 31 test, tsc/lint/build
  bersih.
