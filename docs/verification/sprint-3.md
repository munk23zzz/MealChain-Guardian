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

## Model chain per agent (revisi 2026-10-06 — chain panjang frontier-first)

Setiap agent (supervisor/verifier/forecast) kini punya rantai model PANJANG
(6 model), frontier dulu, open-weight (kimi/qwen) di posisi fallback
TERAKHIR (arah Roy). Backend = sumber konfigurasi (env); frontend menampilkan
identitas model/provider dari trace DB (display-only, `ProviderPanel`).
`AGENTCORE_RUNTIME_ARN` kini TERISI (runtime `mealchain-5iQ9raHpis`,
us-west-2, dibuat Roy) → jadi slot `primary:agentcore`; 6 slot env bergeser
menjadi fallback_1..6 (total 7 referensi per agent). Implementasi invoke
runtime AgentCore = stub eksplisit (honest-unavailable) → chain otomatis
jatuh ke fallback_1 Bedrock sampai implementasi runtime siap.

| Slot | Model | Status (probe live, 2026-10-06/07) |
|---|---|---|
| primary:agentcore | `AGENTCORE_RUNTIME_ARN` | terkonfigurasi; invoke menyusul |
| fallback_1 (env primary) | Bedrock `us.anthropic.` (the model 4.6) | LIVE + tersertifikasi E2E |
| fallback_2 | Inferhub `cb/gpt-6-astra` (GPT-6 Astra, GPQA-D 96.0%) | LIVE 2.3–7.1s (3 ronde; ronde-3 2026-10-07 'pong' 2s) |
| fallback_3 | Inferhub `cx/gpt-6-astra` | LIVE 4s 'pong' (ronde-3, 2026-10-07) |
| fallback_4 | Inferhub `cb/gpt-6-sol` | LIVE 2s 'pong' (ronde-3, 2026-10-07) |
| fallback_5 | Inferhub `cx/gpt-6.1-sol` | LIVE 1s 'pong' (ronde-3, 2026-10-07) |
| fallback_6 | Inferhub `cc/` | LIVE 2.5–5.2s (2 ronde) |
| fallback_7 | Inferhub `cc/` | LIVE 2.9s (503 ronde-1 = transien, pulih) |
| fallback_8 | Inferhub `cb/kimi-k3` | LIVE 7.9s / ronde-3 4s (max_tokens 4000) |
| fallback_9 | Inferhub `cbcn/kimi-k3` | LIVE 11.0s / ronde-3 8s |
| fallback_10 | Inferhub `ali/qwen3.8-max-0902` | LIVE 3.1s |

Catatan verifikasi 2026-10-07: probe ronde-3 awalnya salah sasaran — skrip
menambahkan `/chat/completions` pada `INFERHUB_URL` yang sudah endpoint penuh
→ 404 palsu untuk SEMUA ID termasuk kontrol. Root cause ditemukan (env =
endpoint penuh, bukan base URL), probe diulang benar → semua kandidat LIVE.
Pelajaran: label 404 hanya valid setelah kontrol terbukti 200 dengan path yang
sama. `cx/` kini prefix Inferhub resmi di registry (TDD: test RED→GREEN,
suite 446 passed).

### Model access frontier Bedrock (2026-10-07 — jalur SDK dari docs resmi)

Alur `model-access.html` (SDK/CLI): `ListFoundationModelAgreementOffers` →
`CreateFoundationModelAgreement` → poll `GetFoundationModelAvailability`.
Hasil untuk 5 kandidat frontier (5.5/5/fable-5.1/4.8/4.7): **CREATE_OK 5/5**;
setelah ~10 menit subscription akun selesai — `agreementAvailability:
AVAILABLE` + `authorizationStatus: AUTHORIZED` + `entitlementAvailability:
AVAILABLE`. Invoke masih `AccessDeniedException` → satu langkah tersisa di
sisi akun: attach policy `MealchainAgentcoreCreate` (file
`_iam_policy_mealchain.json` — `bedrock:InvokeModel`/`...WithResponseStream`
Resource `*`, `aws-marketplace:Subscribe/Unsubscribe/ViewSubscriptions`,
`bedrock-agentcore:CreateGateway/CreateMemory/Get*/List*/Delete*/Tag*`) ke
IAM user `mealchain`. Setelah attach, script enable diulang → invoke test →
restrukturisasi blok Bedrock (fallback_1 frontier terbaru → fallback_2
frontier kedua → fallback_3 opus 4.6).

### AgentCore Memory & Gateway (2026-10-07, pasca-attach policy)

- **Memory: SUKES** — `CreateMemory` OK via control client
  (`bedrock-agentcore-control`), status ACTIVE (`mealchain_memory`,
  eventExpiry 30 hari). `AGENTCORE_MEMORY_ID` terisi di `.env`; backend
  recreate → `memory_provider_from_env()` = **agentcore** (terverifikasi di
  container). Suite penuh 447 passed.
- **Gateway: terhalang `iam:PassRole`** — `CreateGateway` sudah lolos
  authorization AgentCore, tapi butuh `roleArn` runtime
  (`service-role/AmazonBedrockAgentC…`) yang menuntut `iam:PassRole` pada
  user `mealchain`. Role ARN runtime tersimpan di `_role_arn.txt`.
  Tambahkan `iam:PassRole` (Resource: role runtime tersebut) → rerun → isi
  `AGENTCORE_GATEWAY_URL`.
- Pelajaran boto3: runtime/gateway/memory = **control plane** (client
  `bedrock-agentcore-control`); client `bedrock-agentcore` = data plane
  (invoke runtime). `get_agent_runtime` ada di control client.
- Bug .env ditemukan & diperbaiki: append tanpa newline menyatu dengan baris
  qwen (`…0902AGENTCORE_MEMORY_ID=…`) — dipisah ulang; qwen slot valid lagi.

Kandidat dibuang dari .env (alasan terdokumentasi, bukan truncasi):
`cc/`/`cc/`/`cc/`/`cb/`
(503/502 down saat 2 ronde probe), `cc/` VALID live tapi
digantikan Astra/Sonnet-5 di slot atas. `gpt-5.6-sol` = 404 di katalog
Inferhub (cc/ dan cb/) — tidak bisa dipakai dengan nama itu. Entry mati
 dikosongkan dari .env; kimi-k3 & qwen3.8-max TIDAK dibuang (posisi terakhir).

Arsitektur chain panjang (TDD, backend **445 passed**):
- `model_registry.py` — slot fallback bernomor 1..9 tanpa cap 3; gap pertama
  menghentikan koleksi; AgentCore ARN = primary, env chain utuh.
- `resilience.py` — `with_fallback_chain(..., fallbacks=[...])` untuk chain
  panjang (kwargs lama tetap kompatibel) + `provider_slot_index()`.
- `ai_provider_chain.py` — label slot dinamis mengikuti panjang chain.
- Client verifier/forecast/supervisor — translasi label generik (fallback_N).
- conftest isolasi env mencakup fallback_3..9; compose passthrough slot
  baru (supervisor s.d. _11, verifier/forecast s.d. _9).

Evidence live (ronde 3-slot, arsitektur sama — jalur E2E tersertifikasi):
- Verifier FLAGGED jujur via `primary:bedrock`; forecast
  `provider_forecast` 7230.0 (bug kontrak output prompt ditemukan & fixed);
  supervisor SUPERVISE (non-safety-critical); fallback Inferhub live
  terbukti (kimi timeout → qwen mengambil alih, fallback_used=True).

