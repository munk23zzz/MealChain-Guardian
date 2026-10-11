# TODO.md — Pelacak Progress MealChain Guardian

**Ini adalah memory proyek.** Update baris di sini SETIAP KALI status berubah — jangan tunggu
sampai akhir sesi. Kalau tidak tercatat di sini, dianggap belum dikerjakan, siapapun/apapun
yang membaca sesi berikutnya.

Status yang valid: `Not Started` · `In Progress` · `Blocked` · `Done`

---

## Sprint 0 — Setup

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S0-01 | Init repo + struktur folder sesuai Architecture.md §4 | Setup | Done | Hermes | Commit 687e8bd |
| S0-02 | Docker Compose (backend, frontend, postgres) | Setup | Done | Hermes | Commit 687e8bd |
| S0-03 | Migration awal Postgres (master data tables) | Setup | Done | Hermes | Commit 0176540, needs Docker test |
| S0-04 | Verifikasi akses AWS trial (Bedrock invoke test) | Setup | In Progress | Roy | **Probe Hermes 2026-10-11 (kredensial .env)**: STS OK — akun 679583588036, `arn:aws:iam::679583588036:user/mealchain`. Katalog Bedrock 93 model TEXT / 97 inference profile. **`invoke_model` DITOLAK di lapisan IAM**: `AccessDeniedException` untuk `us.anthropic.claude-opus-4-6-v1` dan `us.meta.llama3-1-8b-instruct-v1:0` (`not authorized to perform: bedrock:InvokeModel`), sedangkan `us.anthropic.claude-3-haiku-20240307-v1:0` dan `claude-3-sonnet-20240229-v1:0` sudah EOL. Menurut taksonomi skill: ini **"akses model belum diberikan"**, BUKAN kuota habis. **Migrasi 2026-10-11 (Hermes)**: akun 679583588036 tidak dapat dimasuki lewat konsol → dependency AWS dipindah ke akun yang user kuasai, **624606539664** (user IAM `megu`); kunci di `secrets/aws-app.env` (terabaikan git) + `docker-compose.yml` `env_file` ganda. Bukti: STS dari dalam kontainer = 624606539664; invoke Bedrock **bukan lagi AccessDenied** melainkan `ThrottlingException: Too many tokens per day` — kuota *tokens per minute* Anthropic di Service Quotas masih **0.0** (adjustable); `get_use_case_for_model_access` sudah terisi. Aksi tersisa (user): Service Quotas → Amazon Bedrock → *tokens per minute* Claude Sonnet 4 + Haiku 4.5 → Request increase. `SUPERVISOR_MODEL_FALLBACK_1` kini Bedrock sonnet-4 nyata; `AGENTCORE_*` dikosongkan (ARN milik akun lama); suite 630 passed + live SAP 3 passed. Rincian + jebakan: `docs/verification/migrasi-akun-aws.md`. |
| S0-05 | Verifikasi akses AgentCore | Setup | Done | Hermes | Probe 2026-10-11: control plane TERBUKTI dengan kredensial `.env` — `list_agent_runtimes` 1, `list_gateways` 2, `list_memories` 2 (resource sudah ada, bukan nol). Operasi Identity tersedia: `ListApiKeyCredentialProviders` (relevan untuk S4-07/S5-02). |
| S0-06 | Strands SDK hello-world agent | Setup | Not Started | | |
| S0-07 | `.env.example` + `.env` lokal | Setup | Done | Hermes | Created |

## Sprint 1 — Business logic inti + data

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S1-01 | Seed dataset 10 lokasi x 3 komoditas | Data | Done | Hermes | Commit 81714c7; counts 10×3; docs/verification/sprint-1.md |
| S1-02 | Endpoint `GET /supply/*` | Backend/API | Done | Hermes | Commit 3fcd920; 13 test API |
| S1-03 | Endpoint `GET /demand/*` | Backend/API | Done | Hermes | Commit 3fcd920 |
| S1-04 | Endpoint `POST /freshness/evaluate` | Backend/API | Done | Hermes | Commit edbe5a9 |
| S1-05 | Endpoint `POST /safety/evaluate` | Backend/API | Done | Hermes | Commit edbe5a9 |
| S1-06 | Endpoint `GET/POST /price/*` | Backend/API | Done | Hermes | Commit edbe5a9 |
| S1-07 | Endpoint `POST /logistics/estimate` | Backend/API | Done | Hermes | Commit edbe5a9 |
| S1-08 | Unit test hard constraints (safety, freshness, capacity, delivery window) | Testing | Done | Hermes | 158 test backend; acceptance 12 test |
| S1-09 | Mock SAP: material_stock + purchase_orders terisi seed | Mock SAP | Done | Hermes | Commit 2e6cbc9 + 81714c7 |
| S1-10 | Endpoint `GET /demand/forecast/*` (forecast statistik fallback) | Backend/API | Done | Hermes | Commit 3fcd920 |
| S1-11 | Freshness `usable_until` pada kontrak evaluate + persistence batch | Backend/API | Done | Hermes | Commit edbe5a9 + eb207ff |

## Sprint 2 — Balancing engine + Auth + Frontend shell

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S2-01 | Endpoint `POST /cost/safe-delivered` | Backend/API | In Progress | Hermes | Engine SDC + perhitungan per kandidat selesai (Task 6/9, commit 9b1e083, a9bd9ae); endpoint standalone = carry-over plan-binding; Opsi A SDC dikunci 2026-10-06 |
| S2-02 | Endpoint `POST /balance/analyze`, `/balance/recommend` | Backend/API | In Progress | Hermes | `/balance/recommend` + `/balance/{loc}/{com}` selesai (Task 10, commit 353be20); final correction HEAD 5deb4ef; 296 test backend |
| S2-03 | Endpoint `POST /evidence/fuse` | Backend/API | Done | Hermes | Commit `93ca711` (S3-02); RBAC legacy ditutup 2026-10-08 (Revisi 10) |
| S2-04 | Auth: JWT login + 3 role (sppg_head, sppg_nutritionist, bgn_monitor) | Authentication | Done | Hermes | Commit `77d3fdc` (S3-01) + akun demo; ditandai selesai Roy 2026-10-08 |
| S2-05 | RBAC middleware per endpoint | Authentication | Done | Hermes | `require_roles`/`get_current_user` di SEMUA endpoint incl. legacy (Revisi 10, TDD + live probe); ditandai selesai Roy 2026-10-08 |
| S2-06 | Frontend: Login screen | Dashboard | Done | Hermes | S3-12 + polish Revisi 7/8; ditandai selesai Roy 2026-10-08 |
| S2-07 | Frontend: Dashboard shell + peta 10 lokasi (data statis dulu) | Dashboard | Done | Hermes | S3-12 dashboard shell (feed/detail/trace); peta 10 lokasi digantikan OpsConsole+RoleHero (Revisi 9); ditandai selesai Roy 2026-10-08 |
| S2-08 | `openapi.json` bersih ter-generate | Backend/API | Done | Hermes | Regenerated 26 paths = set route, security terisi (Revisi 10) |

## Sprint 3 — Agent layer (PALING KRITIS)

> **STATUS: DONE** — final gate PASS dari HEAD `a9eba93` (2026-10-08):
> backend 463 passed + ruff; frontend 55 + tsc + lint + build; Alembic
> `008_rejection_loop` (current=heads); Docker 4 service Up + health 200;
> OpenAPI 26 paths = 26 routes (0 drift); secrets scan 0; live probe
> auth/RBAC 10/10; AgentCore Runtime live invoke PASS (PONG asli).
> Evidence: `docs/verification/sprint-3.md`.

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S3-01 | AgentCore Gateway config dari openapi.json | Agent | Done | Hermes | Commit `93ca711`+`e47e11e`; tool registry + gateway config; `backend/openapi.json` 23 paths |
| S3-02 | Supervisor Agent — panggil 1 tool via Gateway | Agent | Done | Hermes | Commit `77d3fdc` (auth+matrix) + `0c21a39` (orchestrator tool call) |
| S3-03 | Supervisor Agent — alur penuh Event 1 (DETECT→ACT) | Agent | Done | Hermes | Commit `0c21a39`; + narasi SUPERVISE pasca-gate `92a95fc` |
| S3-04 | Verifier Agent — audit output Event 1 | Agent | Done | Hermes | Commit `689cf26`; fix verifier_note `5e5525b` |
| S3-05 | AgentCore Memory terpasang | Agent | Done | Hermes | Commit `dacc592` (memory isolation; ARN/Memory kosong = honest-unavailable) |
| S3-06 | AgentCore Observability aktif + trace bisa ditarik | Agent | Done | Hermes | Commit `dacc592` (observability + trace) |
| S3-07 | `agent_traces` table terisi dari trace asli | Backend/Data | Done | Hermes | Commit `ffc22b2` (persistence + whitelist) |
| S3-08 | Frontend: Recommendation Feed (data asli) | Dashboard | Done | Hermes | Commit `45cb20e`+`4999615` |
| S3-09 | Frontend: Decision Detail + Evidence view | Dashboard | Done | Hermes | Commit `45cb20e`+`4999615` |
| S3-10 | Frontend: Agent Activity Log (trace timeline) | Dashboard | Done | Hermes | Commit `45cb20e`; + ProviderPanel `92a95fc` |
| S3-11 | Approval flow — approve → execute → SAP mock PO | Backend/Dashboard | Done | Hermes | Commit `5e5525b`; E2E `c478d5c` (PO mock `MC-`, data_source=MOCK) |

### Catatan status eksekusi Sprint 3 (agent layer — sinkronisasi tabel penuh di S3-16)

> Penomoran TODO.md berbeda dari plan `.hermes/plans/2026-10-06-sprint3-agent-layer.md`
> (TODO.md = pandangan fitur; plan = slice eksekusi). Status per 2026-10-06 mengikuti plan:
>
> - **S3-00** Preflight: DONE — AWS LIVE via inference profile (STS+Bedrock ok), CRLF `.env` quirk, compose env wiring diperbaiki.
> - **S3-01** (plan) Auth JWT/RBAC + approval matrix + actions lifecycle + demo users: DONE — commit `77d3fdc`, 323 passed.
> - **S3-02** (plan) `/cost/safe-delivered`, `/balance/analyze`, `/evidence/fuse` + tool registry + gateway config: DONE — commit `93ca711`, fix `e47e11e`, 332 passed. `backend/openapi.json` ter-generate (22 paths).
> - **S3-05** (plan) Shared resilience `with_fallback_chain` (primary→fallback 1-3, 429 retryable, timeout, circuit breaker opsional): DONE — commit `a512e5a`, 340 passed.
> - **S3-06** (plan) Verifier REST client (SAP primary→SAP fallback→Bedrock final via S3-05, guard safety FAIL, UNAVAILABLE→dual approval): DONE — commit `689cf26`, 352 passed. Catatan: system prompt di `app/ai_providers/prompts/` (bukan `agent/prompts/`) karena `agent/` di luar bind-mount container.
> - **S3-07** (plan) Forecast provider (SAP-RPT-1.6→statistical_fallback 0.5/0.3/0.2 dari core, tanpa fabricate label SAP): DONE — commit `21ee4af`, 358 passed.
> - **S3-03+04** (plan) Event 1 orchestrator (`services/event1_orchestrator.py`, DETECT→VERIFY→TRACE→PREDICT→OPTIMIZE→DECIDE, AgentTrace persist, tanpa auto-approve): DONE — commit `0c21a39`, 365 passed. Catatan lokasi: di `app/services/` (bukan `agent/` root) karena `agent/` di luar bind-mount container.
> - **S3-08+09** (plan) Memory isolation + Observability trace (`agent_memory.py`, `agent_observability.py`; AgentCore tanpa konfigurasi = error eksplisit; label `synthetic` anti-promosi bukti palsu): DONE — commit `dacc592`, 379 passed.
> - **S3-10** (plan) Trace persistence service (`trace_persistence.py`, sanitasi payload + step_name whitelist + step_at monoton): DONE — commit `ffc22b2`, 382 passed.
> - **S3-11** (plan) Approval+action E2E: **bug nyata ditemukan & diperbaiki** — `/actions/verify` tidak pernah menulis `verifier_note` (jalur API tak pernah bisa CONSISTENT); sekarang verdict tertulis + status `verifier_flagged` + 422 verdict tak dikenal: DONE — commit `5e5525b`, 389 passed.
> - **S3-12** (plan) Frontend Agent Flow (login, feed polling 5s, decision detail, AgentTraceViewer dari DB, ApprovalModal friksi §1.3, role scope §1.4, badge mock): DONE — commit `45cb20e` + backend read endpoints `4999615` (25 test, tsc+lint+build bersih).
> - **S3-13+14** (plan) E2E acceptance (4/4: jalur penuh supervisor→PO mock MC-, data_source=MOCK; bug seam verifier_note orchestrator ditemukan & diperbaiki) + resilience acceptance (5/5: matriks 4 cabang chain via failure injection deterministik, UNAVAILABLE→dual AND): DONE — commit `c478d5c`, 401 passed.
> - **S3-15** (plan) Security/contract review: endpoint baca S3-12 diproteksi auth (unauth 401 — ditemukan via live probe), openapi.json regenerated 23 paths 0 missing, core→api boundary 0 pelanggaran, scan secrets bersih: DONE — commit `6744978`, 402 passed.
> - **S3-16** (plan) Final gate: fresh verification dari HEAD — alembic `006_decision_persistence (head)`, backend 402 passed + ruff bersih, frontend 25 test + lint bersih, compose 4 service Up (postgres healthy), log scan bersih pada state final, `/health` 200, `/decisions` unauth 401, DB readback bersih. Evidence lengkap: `docs/verification/sprint-3.md`. BLOCKED live (jujur): AgentCore Runtime ARN/Gateway/Memory kosong, model env verifier/forecast/supervisor belum lengkap — jalur lokal tersertifikasi penuh.
> - Selesai: seluruh slice S3-00..S3-16 (402 backend + 25 frontend test saat gate). Tabel fitur S3-01..S3-11 di atas sudah disinkron ke `Done` + referensi commit (ditandai selesai oleh Roy, 2026-10-06).
> - **Pasca-gate (permintaan Roy): model chain 3 slot per agent LIVE.** Verifier/Forecast/Supervisor kini primary Bedrock + 2 fallback Inferhub (cb/kimi-k3, cbcn/kimi-k3, ali/qwen3.8-max-0902 — semua terbukti live via probe); AgentCore ARN (bila diisi) jadi primary & menggeser slot env. Supervisor dapat langkah narasi SUPERVISE (non-safety-critical) + frontend ProviderPanel identitas model. Bug live ditemukan & fixed: prompt forecast tanpa kontrak output → parser menolak jawaban array harian model. Evidence: `docs/verification/sprint-3.md`. Backend **437 passed**, frontend **31 test**, ruff/tsc/lint/build bersih.
> - **Revisi 2 (arah Roy): chain PANJANG frontier-first, kimi/qwen di fallback TERAKHIR.** Probe 2 ronde katalog Inferhub → `cb/gpt-6-astra` (GPT-6 Astra), `cc/`, `cc/` LIVE (503 ronde-1 terbukti transien); `gpt-5.6-sol` 404 di katalog. .env dirapikan: 6 slot/agent identik (Bedrock Claude → Astra → Claude-5-5 → Claude-5 → kimi-k3 → qwen3.8-max), entry 503/502 lama dikosongkan. `AGENTCORE_RUNTIME_ARN` kini TERISI (runtime `mealchain-5iQ9raHpis`, dibuat Roy) → slot `primary:agentcore`, chain total 7. Registry slot 1..9 tanpa cap, `with_fallback_chain(fallbacks=[...])`, label dinamis. Backend **445 passed**, ruff bersih; frontend 31 test + tsc/lint bersih.
> - **Revisi 10 (2026-10-08): residual RBAC endpoint legacy Sprint 1/2 DITUTUP
>   + final gate Sprint 3 (arah Roy).** Guard JWT/RBAC di 10 router legacy
>   (13 endpoint; baca = JWT valid, mutasi = sppg_head/nutritionist —
>   bgn_monitor read-only 403), TANPA ubah architecture/domain logic
>   (Architecture.md §232, PRD §77). TDD RED→GREEN; 46 fallout test legacy
>   dibereskan via fixture `auth_headers` (login JWT nyata, assertion tak
>   diubah). Final gate PASS: backend **463 passed** + ruff; frontend 55 +
>   tsc + lint + build; Alembic current=heads=`008_rejection_loop`;
>   Docker 4 service Up + `/health` 200 + log scan bersih; OpenAPI
>   regenerated 26 paths = set route (0 drift); secrets scan 0 temuan;
>   live probe auth/RBAC 10/10 (401/403/200); **AgentCore Runtime live
>   invoke PASS** (HTTP 200, 4.89s, PONG asli — bukan fallback/synthetic).
>   Evidence: `docs/verification/sprint-3.md`. **Sprint 3: DONE.**
> - **Revisi 9 (2026-10-07): Ops Console interaktif + polish semua role.**
>   Demo-day guard TTL (pending/flagged ≥ 60 mnt pasca-seed, di-guard test).
>   Frontend: OpsConsole (muat kondisi nyata /balance → analisis agent
>   /balance/analyze → Ajukan → feed), RoleHero per role, header navy,
>   label kasus di kartu, tombol Verifikasi (syarat execute eksplisit).
>   Alur live: analyze → ajukan → 4-eyes approve → verify → execute →
>   PO mock SAP terbentuk. Backend 458 + ruff; frontend 55 + tsc + lint.
> - **Revisi 8 (2026-10-07): Rejection loop + 4 kasus demo (arah Roy).**
>   Penolakan WAJIB alasan (422 bila kosong; tersimpan `rejection_reason`) →
>   agent re-propose iterasi baru (`supersedes_id`, trace **LEARN** berisi
>   alasan — bahan learning/memory) → chain v1→v2→v3 via
>   `GET /decisions/{id}/chain`. Migration 008 (4 kolom). `POST /demo/seed`
>   idempotent: kuota (v1→v2→v3 fresh), shortage darurat (TTL 15 mnt),
>   supplier janggal (FLAGGED), gangguan logistik (re-rute). Frontend:
>   DecisionChain + badge v{n} + tombol alasan wajib & re-propose + "Muat
>   kasus demo"; link 404 dihapus; brand panel dirapikan (rute ❄ + angka
>   dihapus per arah Roy). Backend **458 passed** + ruff; frontend **45
>   passed** + tsc + lint. Live E2E terverifikasi (reject→repropose→chain→LEARN→restore).
> - **Revisi 7 (2026-10-07): CORS fix + polish UI login.** Keluhan "Failed to
>   fetch" root cause: backend tanpa `CORSMiddleware` (browser origin
>   3000 → API 8000 diblokir) → `app.add_middleware(CORSMiddleware)`
>   allow-list eksplisit `localhost:3000` + `127.0.0.1:3000` (TDD: 3 test
>   baru di `tests/test_cors.py`, backend **450 passed**). Login di-polish
>   (frontend-design skill): split layout — panel brand navy dengan signature
>   rute rantai dingin **Bogor → Jakarta** + angka demo asli (50 km, SDC
>   Rp16,2 jt, freshness 0,90), chips akun demo klik-isi, state
>   loading/error. Frontend **36/36** + tsc + lint bersih; verifikasi live:
>   preflight OPTIONS 200 + header `access-control-allow-origin`,
>   login 200, dev server restart → page serve desain baru.
> - **Revisi 6 (2026-10-07): AgentCore GATEWAY LIVE — AgentCore stack tuntas.** Policy file 1 (12 action incl. 3 WorkloadIdentity) di-attach Roy → create ulang sukses → **gateway READY** (`list_gateways` quirk count=0; verifikasi via get_gateway by ID dari host URL) → `AGENTCORE_GATEWAY_URL` append .env (92 char, newline disiplin) → backend recreate → container: gw_url len 92 + mem_id len 30 + provider **agentcore**. Gateway FAILED ronde-1 di-delete. Frontier 5 model: tetap sales-gated (pilihan Roy: ajukan AWS Sales). Kapasitas 12 slot/agent dipertahankan untuk masa depan.
> - **Revisi 3 (arah Roy, 2026-10-07): tambah fallback baru + koreksi verifikasi.** Probe ronde-3 awal salah sasaran (skrip menambah path pada `INFERHUB_URL` yang sudah endpoint penuh → 404 palsu termasuk kontrol; root cause fixed, probe diulang → SEMUA kandidat LIVE 'pong': `cx/gpt-6-astra` 4s, `cb/gpt-6-sol` 2s, `cx/gpt-6.1-sol` 1s, `cb/kimi-k3` 4s, `cbcn/kimi-k3` 8s, kontrol `cb/gpt-6-astra` 2s). Chain rev3 per agent (total 11 slot incl. AgentCore): primary AgentCore → Bedrock 4.6 → astra cb/cx → sol cb/cx → 2× claude cc/ lama → cb/kimi-k3 → cbcn/kimi-k3 → ali/qwen3.8-max TERAKHIR. `cx/` jadi prefix Inferhub resmi (TDD RED→GREEN). Backend **446 passed** + ruff; frontend 31 test. Dok: `docs/verification/sprint-3.md` (tabel chain + catatan verifikasi ronde-3).

## Sprint 4 — Event 2 & 3, KPI, polish, rehearsal

> **STATUS: IN PROGRESS** (Jangan tandai selesai — Roy yang menandai) —
> per 2026-10-09 (revisi 3): **final gate Sprint 4 LOLOS** — backend full
> **551 passed EXIT=0** (390s, pasca-polish; baseline 463→551), frontend
> **92/92** + tsc 0 + lint 0 + build PASS, Ruff 0, Alembic single head
> `008_rejection_loop`, OpenAPI live 32 paths + unauth 401 probe bersih,
> secrets scan 0 secret produksi, DEMO_MODE=False. Live browser: peta
> skematik Indonesia 10 lokasi (data DB real, Jakarta telur kurang 780 kg)
> + grafik surplus/shortage + sidebar per role; bgn_monitor read-only
> (tanpa tab Analisis/tombol mutasi). **Polish UI/UX per role done** (arah
> Roy): teks ramai dipindah ke sidebar, tab nav per role, `GET /balance/map`
> (TDD 5/5) + `SupplyMap` + `StockChart`. Laporan gate:
> `docs/verification/sprint-4-final-gate.md`. Video fallback = waived
> Owner. Residual: O-KPI 2 metrik menunggu kontrak data; Memory AgentCore
> IAM (aksi Roy). Sprint tetap IN PROGRESS — Roy yang menandai DONE.
> **Overhaul visual (arah Roy 2026-10-09, "masih sangat jelek")**: latar
> abu halus + kartu ber-depth, badge dot-status (EXPIRED tetap tampil —
> traceable, tidak disembunyikan), **filter chip status + count live**
> (Semua 63 / PROPOSED 49 / PENDING_APPROVAL 8 / REJECTED 5 / FLAGGED 1 —
> terverifikasi browser), peta & chart dibingkai panel, angka tabular.
> FE 93/93 + tsc 0 + lint 0 + build EXIT=0 (served fresh).
> **MapLibre GL (keputusan Roy 2026-10-09, lanjutan overhaul):** peta
> skematik SVG diganti MapLibre GL sungguhan (tile OSM raster, tanpa API
> key) — FE 95/95, build EXIT=0, terverifikasi live 10 marker;
> `docs/design.md` §3.1/§4/§5 diselaraskan.
> **PRD 2.4 alignment (keputusan Roy 2026-10-09):** navigasi konsol
> direstrukturisasi mengikuti 7 screen PRD → 5 tab: **Overview / KPI /
> Recommendations / Agent Log / Demo Control** (approver-only). Persona
> label = judul resmi PRD §2 (Operations Lead / Food Safety Officer /
> National Inspector). Tab KPI menampilkan **strip Target KPI Demo Day**
> (angka PRD §5 berlabel eksplisit "TARGET DEMO · bukan angka live";
> KPI live tetap jujur dari DB). Komponen kripto PRD (Polygon/IPFS/
> Merkle/FIDO2) & chaos sliders TIDAK dibuat — arsitektur & backend
> tetap keputusan terakhir. FE 101/101 + tsc 0 + lint 0 + build EXIT=0;
> live: sppg_head 5 tab + monitor tanpa Demo Control.
> **Paket 1–6 integrity & KPI (setuju Roy via clarify 2026-10-09/10):**
> P1 Merkle ledger append-only (migration `010_ledger_blocks` +
> `ledger_service` sha256 rantai + `GET /ledger/verify` + hook
> approve/execute); P2 dossier konten-addressed (`mc1-` SHA-256 bundle
> bukti, `GET /decisions/{id}/dossier`); P3 ECDSA secp256k1 signing per
> approval (kunci `SIGNING_KEY_HEX` di `.env`, tanpa kunci = `unsigned`
> jujur); P4 chaos sliders (`ChaosPanel` → `POST /events/safety-disruption`
> via API resmi + `GET /batches` read-only); P5 telemetry banner jujur di
> login (tanpa klaim sertifikasi); P6 tabel facts menu_plans/
> delivery_events/disposal_events (migration `009_kpi_facts_tables`) →
> **KPI Meal Continuity (100.00%) & Avoidable Food Loss (1.52%) LIVE**
> deterministik dari DB. FE **107/107** + tsc 0 + lint 0 + build EXIT=0;
> IntegrityPanel di tab agent-log, ChaosPanel approver-only di demo-control.
> **Ruling REF seed canonical (Roy 2026-10-09): REF 2026-10-08 12:00 UTC**
> — dataset demo ter-anchor di situ (id stable_uuid bergantung REF; REF lain
> menduplikasi baris). Test stale diselaraskan (`test_price_regional_seed`,
> `test_seed_load_db`, `test_api_supply_demand` LATEST + timestamp insert
> 10-15) → **backend full 567 passed EXIT=0** (253s, rerun pasca-paket 1–6).
> Sprint tetap IN PROGRESS — Roy yang menandai DONE.
> ---
> Riwayat revisi 2 (2026-10-08): S4-01..S4-04 Done; **S4-05 rehearsal 3 putaran
> selesai + 2 ruling Owner dieksekusi TDD + putaran 4 bersih LOLOS** —
> (1) approval-summary/detail lintas lokasi dibuka untuk VERIFIER_ROLES
> (selaras write path; monitor tetap 403) — terbukti live: nutritionist
> Bogor membaca summary + approve decision Jakarta via UI (2 approvals
> DB); (2) pipeline rekomendasi difilter per komoditas panel (`POST
> /balance/analyze` body opsional `commodity`) — terbukti live: panel ayam
> → 0 kandidat, panel telur → usulan telur (bug "panel ayam → usul telur"
> hilang). **Temuan higienitas test fixed**: test_event2 seed tanpa cleanup
> (polusi lintas-test) → fixture FK-safe + residu historis dibersihkan →
> full backend **546 passed**. **S4-06 done TANPA video** (arah Roy):
> evidence `docs/verification/sprint-4.md` + redaksi (`.env.example`
> dihapus sesuai aturan secrets; scan tracked files 0 secret produksi).
> DEMO_MODE kembali `False` (recreate terverifikasi). Sisa: polish UI/UX
> per role (arah Roy: kurangi teks ramai, grafik, map Indonesia, sidebar
> per role) + final gate.

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S4-01 | Event 2 (price anomaly) end-to-end interaktif | Demo Scenario | Done | Hermes | p2–p4 backend `event2_service` + `Event2Panel`; live: telur Jakarta −0,98% normal, ayam Bogor +0,79% normal (review-only, tanpa decision row) |
| S4-02 | Event 3 (safety disruption → reroute Bogor) end-to-end interaktif | Demo Scenario | Done | Hermes | p4 `event3_service` + `POST /events/safety-disruption`; live: batch Surabaya 90 mnt → FAIL → `revised` 201; batch ayam aman → `no_disruption` 200; UI trigger menunggu boundary ruling (rehearsal via API resmi) |
| S4-03 | KPI Dashboard — 7 KPI dari data real | Dashboard | Done | Hermes | p9: kpi core+service+API (20 test) + `KPIDashboard` FE (7/7) + wiring; live probe 7 metrik jujur (2 unavailable + 4 no_data, tanpa fake 0) |
| S4-04 | Approval Modal — ringkasan lengkap | Dashboard | Done | Hermes | p8: approval-summary read model kanonik + modal; p10: fix gate Setuju `can_execute`→`can_approve` (bug rehearsal, TDD RED→GREEN, 80/80) |
| S4-05 | Rehearsal checklist (workflows.md §6) — 4x lolos berturut-turut | QA/Demo | Done | Hermes | r1 telur E1-3 ✓+bug approval fixed; r2 ayam E2/E3 ✓; r3 per-role ✓; r4 bersih ruling ✓ (panel ayam 0 kandidat; telur → usulan telur; approve ganda lintas lokasi via UI, 2 rows DB) |
| S4-06 | Evidence docs + redaksi secrets (TANPA video — arah Roy) | QA/Demo | Done | Hermes | `docs/verification/sprint-4.md`; `.env.example` dihapus + gitignore (aturan secrets); scan tracked 0 secret produksi; DEMO_MODE kembali False |
| S4-06b | Polish UI/UX per role (arah Roy: kurangi teks ramai, grafik, map Indonesia, sidebar) | Dashboard | Done | Hermes | TDD: `GET /balance/map` (5/5) + FE test baru (RED→GREEN, 80→92); sidebar per role + tab nav (bgn_monitor tanpa tab Analisis), `SupplyMap` peta skematik 10 lokasi data DB real, `StockChart` recharts; tsc 0 + lint 0 |
| S4-06c | Final Sprint 4 Acceptance Gate (plan §17) | QA/Demo | Done | Hermes | Laporan `docs/verification/sprint-4-final-gate.md`: backend 551 EXIT=0, FE 92/92+build, Ruff 0, Alembic head tunggal, OpenAPI 32 paths + unauth probe, secrets scan bersih, live browser 2 role; video fallback waived Owner; sprint tetap IN PROGRESS — Roy yang menandai DONE |
| S4-09 | Adaptasi desain Stitch → design system (arah Roy 2026-10-10) | Dashboard | Done | Hermes | Kode Stitch (7 layar) diadaptasi VISUAL-ONLY via token CSS `globals.css` — palet teal Stitch (primary #005c55, container #0f766e, terminal #0F172A, accent #2DD4BF), status tint Stitch, sidebar ala Guardian Core, trace/hash panel terminal gelap, focus-visible ring, transisi 180ms. Struktur komponen, kontrak API (`../lib/api`), gating role (isApprover, monitor read-only) TIDAK diubah. Verifikasi fresh: FE 107/107 + tsc 0 + lint 0 + build EXIT=0; frontend 3000=200, backend health OK |
| S4-09b | Sinkronisasi UI ke mockupui/ (SSoT DESIGN.md) + audit fungsional penuh (arah Roy 2026-10-10) | Dashboard | Done | Hermes | SSoT = `mockupui/cold_chain_integrity_console/DESIGN.md`: token `:root` disamakan (canvas #F8FAFC, line #E2E8F0/#CBD5E1, ink #0B1C30, slate #64748B, elevasi L1/L2/L3 DESIGN.md, radius 8px); alias legacy navy/grey dipetakan; font Inter + JetBrains Mono via next/font (`layout.tsx`); semua hardcode #f6f8f9 dll. dinormalkan. Audit wiring: 0 tombol tanpa handler (scan otomatis seluruh components+page). Verifikasi live browser: login 3 akun demo OK (chip isi form, submit jalan), RBAC live — monitor read-only tanpa tab Demo Control & approve 403 via API, approver punya Demo Control + Event 2/3 terpicu sukses, Merkle verify valid 123 block, KPI honest no_data (window 24h di luar REF), peta 10 marker + grafik dari DB. Gate: FE 107/107 + tsc 0 + lint 0 + build EXIT=0; BE 567/567 + ruff clean; responsif dipertahankan (breakpoint 720/820/860px) |
| S4-09c | Sinkronisasi SELURUH layar ke mockupui (ekspansi S4-09b, arah Roy 2026-10-10) | Dashboard | Done | Hermes | 3 subagent paralel restyle per tab, hasil digabung & diverifikasi ulang parent: KPI (header konsol + bento 7 kartu + filter pill + chip trend SVG), Overview (subheader + strip KPI 3 kartu dari mapData real tanpa fake 0 + filter pill komoditas + split 60/40 peta di panel terminal gelap + tabel breakdown), Recommendations/AgentLog/DemoControl (kartu rekomendasi ala mockup, trace terminal gelap, panel demo). Data/logika/API/RBAC tidak diubah; token :root tidak disentuh; test mock fetch diperbarui utk kontrak resp.text (agent-flow, integrity-panel). Bonus: fix kelas pesan error non-JSON di lib/api.ts (tidak lagi bocor "Unexpected token '<'"). Verifikasi live 5 tab (Overview/KPI/Rekomendasi+approve modal jalan/AgentLog Merkle 152 block valid/DemoControl Event 2+3). Gate: FE 107/107 + tsc 0 + lint 0 + build EXIT=0; frontend 200, backend healthy |
| S4-09d | Adopsi selektif Nabil dan polish Overview | Dashboard/Backend | In Progress | Hermes | Roy meminta eksekusi ketiga plan sampai finish, termasuk schema exclusion lokal per SPPG dan restoration berbukti dengan approval baru. A/B, C, D1 dan D2 telah diimplementasikan; final regression terbaru: FE 138 passed, TypeScript 0, lint 0, build 0, BE 595 passed, Ruff clean, Alembic `011_supplier_exclusions (head)`, health 200. Browser Playwright fresh: 3 role × 3 viewport, 10 rows tanpa horizontal overflow; race komoditas tervalidasi. Compliance dilindungi auth (unauth 401); export dilakukan dari dossier authorized yang sudah dibaca, bukan endpoint publik baru. Tidak ada commit/push atau aktivasi SAP nyata. Sprint tetap In Progress sampai Roy menandai Done. |
| S4-07 | (Stretch) AgentCore Identity | Stretch | Not Started | | Catatan probe 2026-10-11: control plane AgentCore terbukti dan menyediakan `ListApiKeyCredentialProviders` → jalur identity/credential provider layak dicoba; belum dikerjakan karena prioritas S4-10/S4-11. |
| S4-08 | (Stretch) Deploy ke AWS App Runner | Stretch | Not Started | | Catatan 2026-10-11: belum diprobe; kredensial AWS ada tetapi izin IAM terbukti sempit (Bedrock ditolak) sehingga izin ECR/App Runner harus dipastikan lebih dulu. |
| S4-10 | Hidupkan SAP AI Core: RPT-1.6 (forecast primary) + Verifier primary (general 40+) — paket akses SAP (RPT 1.6, Joule Orchestrator chat UI, AI Core general 40+, AI Launchpad) | SAP Integration | Done | Hermes | **SELESAI 2026-10-11.** Data tetap mock; label `SAP-RPT-1.6` hanya untuk response asli. **Akses terbukti**: OAuth 200 (token 7.912 char, `expires_in` 43.199); 8 deployment RUNNING; `sap-rpt-1.6` `d76cf689a05d504f` + `anthropic--claude-4.6-sonnet` `dc9594f579d3e4c1`. **Kontrak terukur**: LLM → `/v2/inference/deployments/{id}/invoke` body gaya Bedrock (subpath `chat/completions`/`messages` DITOLAK); RPT → `/{id}/predict` dengan baris QUERY wajib (target = placeholder); `/oauth/token` WAJIB memuat `grant_type` di body (tanpa itu 400 `invalid_request`). **Kode**: `app/ai_providers/sap_ai_core_caller.py` (token di-cache + `invoke` + `predict`; total forecast dijumlahkan KODE; `confidence` diturunkan dari `confidence_interval` model, bukan diklaim model; rahasia hanya di header dan disapu dari pesan error) + prefix env `sap-ai-core:llm`/`sap-ai-core:rpt` di `model_registry`/`ai_provider_chain`; dua stub lama (`forecast_client._default_sap_rpt_caller`, `verifier_client._default_sap_ai_core_callers`) kini NYATA; `event1_orchestrator` memakai jalur RPT eksplisit supaya label jujur `SAP-RPT-1.6` benar-benar muncul; `.env` primary → `sap-ai-core:rpt`/`sap-ai-core:llm` (+ deployment id, resource group) dan compose meneruskannya. **Verifikasi**: 18 tes unit baru tanpa jaringan (transport disuntik, termasuk penjaga regresi `grant_type`) + 3 tes `-m live` LULUS di kontainer — LLM menjawab; RPT-1.6 mengembalikan 7 prediksi (total 3.164,17 kg, confidence 0,90); `run_forecast` → method `sap_rpt_1_6`, provider `SAP-RPT-1.6`, fallback False. Suite penuh **613 lulus** (sebelumnya 595). **Sisa**: keputusan kuota/biaya AI Core untuk demo dan apakah supervisor juga dipindah ke AI Core (sekarang masih Bedrock). Joule tetap talking point. |
| S4-11 | Settings/Admin screen (manage users, lokasi) — dipindah dari Backlog BL-01 | Dashboard | Done | Hermes | **SELESAI 2026-10-11.** **Keputusan peran**: skema hanya punya 3 peran final (tidak ada `admin`), jadi pengelolaan diberikan ke `bgn_monitor` — satu-satunya peran nasional tanpa ikatan lokasi; `sppg_*` ditolak 403. Tidak ada endpoint DELETE (pengguna/lokasi dirujuk keputusan & batch historis). Perubahan tidak menulis ulang sejarah: approval merujuk `users.id`, lokasi dirujuk lewat id. **Backend**: `app/core/admin_rules.py` (murni; mencerminkan CHECK constraint DB `role`↔`location_id`, monitor dipaksa `location_id NULL`) + `app/api/admin.py` (`GET/PATCH /admin/users`, `GET/PATCH /admin/locations`; id bukan UUID → 404 bukan 500; nama lokasi bentrok → 422). **Frontend**: tab `Pengaturan` di rail (hanya terlihat oleh monitor, ikon + NavId baru), `components/SettingsPanel.tsx` (dua tabel, ubah peran/lokasi/nama/wilayah, tombol Simpan nonaktif bila tak ada perubahan, `role=status`/`role=alert`), `lib/settings.ts` (murni: `canManageSettings`, `draftUserUpdate` hanya mengirim field yang berubah), helper `fetchAdminUsers/fetchAdminLocations/updateAdminUser/updateAdminLocation` di `lib/api.ts`, gaya `.settings-*` memakai token yang ada dengan tabel ber-`overflow-x:auto` supaya 375px tidak melebar. **Verifikasi**: 17 tes backend baru (9 aturan murni + 8 kontrak API, fixture memulihkan master data) + 5 tes frontend; backend **630 lulus**, frontend **356 lulus (43 berkas)**, `tsc` bersih. **E2E akun demo nyata** (`scripts/verifikasi_admin.py`): monitor → 200 (570 pengguna, 10 lokasi), role tak dikenal → 422, sppg_head → 403, tanpa token → 401. **Catatan**: 570 pengguna itu SISA data dari run tes historis (seed hanya membuat 3 akun demo) → tindak lanjut yang disarankan: filter/paginasi di tabel Pengguna. |
| S4-12 | Top bar global (header 64px acuan mockup: brand, dropdown cakupan lokasi, status jaringan, chip peran, notifikasi, identitas, keluar) | Dashboard | Done | Hermes | Langkah 1 permintaan Roy 2026-10-11. `components/TopBar.tsx` + `lib/topbar.ts` (logika murni teruji). Cakupan peran: hanya `bgn_monitor` boleh memilih lokasi; peran SPPG terkunci ke lokasi dari `GET /auth/me` (fail-closed). Notifikasi = hitungan keputusan yang menunggu tindakan. Lokasi aktif dari dropdown menyorot marker peta. Peta+identitas dimuat di SEMUA tab (sebelumnya hanya tab Overview). Verifikasi: vitest 166 passed/26 berkas, tsc 0, lint 0, build 0, audit viewport 375/768/1024 tanpa overflow + kontrol 44px di 375. |
| S4-13 | Peta gaya acuan (peta terang, legenda putih, kontrol MapLibre bawaan) | Dashboard | Done | Hermes | Revisi arah Roy 2026-10-11 (setelah versi panel gelap ditolak): peta kembali TERANG seperti acuan — kanvas OSM apa adanya, legenda putih kiri-bawah ("Status lokasi: Surplus · Seimbang · Shortage") dengan titik sewarna pin, kontrol bawaan MapLibre (zoom+kompas kanan-atas, atribusi kanan-bawah). Semua tambahan versi sebelumnya DIHAPUS sesuai pilihan Roy: kepala panel (judul koridor, jumlah node), toggle tampilan, kaki panel usulan pengiriman, dan panel gelap beserta token `--panel-dark-*`/`--pin-*`. Pin popup dibangun sebagai node DOM (nama lokasi dari database tidak masuk innerHTML). Sisa: `components/SupplyMap.tsx` (prop `console`/`showLabels`/`shortageOnly` dibuang), `components/NodeTelemetry.tsx` (kartu telemetri node tetap), `lib/map-console.ts` (`pinTone`, `pinLabel`, `nodeGauges`). Verifikasi: vitest 171 passed/27 berkas, tsc 0, lint 0, build 0, audit 375/768/1024/1440 tanpa overflow + kanvas 320/380/460 px + legenda & kontrol terukur. Bonus: titik surplus di legenda daftar lokasi disamakan jadi hijau (dulu biru brand, tidak cocok dengan badge baris). |
| S4-14 | Halaman "Hari Ini" (rekap operasional live) | Dashboard | Done | Hermes | Langkah 3 permintaan Roy 2026-10-11. Tab pertama di rail (halaman setelah login tetap Overview). Lima kartu, semua angka dari API: (1) keputusan menunggu tindakan — /decisions, hanya status actionable (PENDING_APPROVAL/NEEDS_VERIFICATION/VERIFIER_FLAGGED), urut lewat-tenggat dulu lalu terdekat, sisa waktu dari jam KLIEN (`now` prop) supaya tidak ada selisih hidrasi, daftar dipotong 6 baris + "+N lainnya"/"Lihat semua"; (2) batch kedaluwarsa vs <48 jam dari /batches (ambang DUE_SOON_HOURS), batch bertanggal tak terbaca tidak diklaim apa pun; (3) lokasi shortage dari /balance/map komoditas aktif, urut kekurangan terbesar; (4) KPI 24 jam dari /kpi memakai formatter tab KPI (fmtValue/STATE_LABEL diekspor — satu sumber, metrik no_data = "—"); (5) rantai audit /ledger/verify (status + jumlah blok + 10 huruf head). Logika murni di `lib/today.ts` (22 tes) + kontrak markup di `tests/today-dashboard.test.tsx` (21 tes). Catatan: `Number(null) === 0` — jumlah kg harus menyaring null/"" SEBELUM Number() atau total kg jadi 0 palsu (tertangkap tes); `fetchBatches` membuka amplop {batches:[...]} di `lib/api.ts`. Verifikasi: vitest 214 passed/29 berkas, tsc 0, lint 0, build 0; di :3011 angka layar = angka API (11 actionable, 6 batch, 7 metrik/2 tersedia, 758 blok, head 0fb6bff271), tanpa overflow di 1440 & 375. |
| S4-15 | Halaman "Decision & Evidence" (tab tersendiri, sidebar acuan) | Dashboard | Done | Hermes | Langkah 4 permintaan Roy 2026-10-11: "tambahkan semua halaman yang ada di sidebar referensi lalu disesuaikan". Sidebar acuan (mockupui/*/code.html) berisi 6 halaman: Overview Map & Supply, Recommendation Feed, Decision & Evidence, Agent Activity & Traces, KPI & Analytics, Demo Control Panel. Lima sudah ada; yang belum = Decision & Evidence (sebelumnya menempel di bawah feed Recommendations). Sekarang tab tersendiri: ringkasan + identitas/tenggat, biaya, keamanan & pemasok, governance (DecisionActions), riwayat iterasi (DecisionChain), bukti tersimpan/ledger/ttd (IntegrityPanel) dan ekspor; keadaan kosong menyarankan keputusan yang benar-benar menunggu tindakan + dropdown pemilih. Feed: klik kartu → pindah ke tab ini. Panel integritas PINDAH dari tab Agent Log ke sini (jejak agen vs bukti keputusan). Logika murni `lib/evidence.ts` (+7 helper, 22 tes) + kontrak `tests/decision-evidence.test.tsx` (11 tes). Seluruh angka dari API; yang tidak ada ditulis "—". Verifikasi: vitest 246/31, tsc 0, lint 0, build 0; di :3011 rute Cianjur → Jakarta, Rp16.206.000, PASS, Supplier A Cianjur 80%, ledger 758 blok, dossier mc1-4hags0k… (ttd saat itu unsigned; lihat S4-16) terbukti sama dengan payload API; 1440 & 375 tanpa overflow. |

## Sprint 5 — Real SAP via AWS for SAP MCP Server (ON-DEMAND — cek Roadmap.md sebelum mulai)

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S5-01 | Provisioning AWS for SAP MCP Server ke tenant SAP trial | SAP Integration | Blocked | | **Gate permintaan Roy: pastikan S/4HANA bisa diakses lebih dulu.** Status 2026-10-11: repo ini TIDAK punya konfigurasi S/4HANA sama sekali (tidak ada host/user/password/destination; yang ada hanya `SAP_*_MODE=mock` + service `mock-sap`), dan kredensial AWS yang tersedia DITOLAK saat memanggil Bedrock (izin sempit). Jadi belum bisa dipastikan S/4HANA terjangkau — butuh dari Roy: kredensial/destination S/4HANA (atau konfirmasi tenant trial panitia) + izin AWS terkait. |
| S5-02 | AgentCore Identity untuk kredensial SAP (naik dari stretch S4-07) | SAP Integration | Not Started | | |
| S5-03 | Implementasi `AWSforSAPMCPProvider` (Skill.md §7) | SAP Integration | Not Started | | |
| S5-04 | Contract test lolos untuk mock + aws_mcp | SAP Integration/Testing | Not Started | | Wajib sebelum switch default |
| S5-05 | Switch `SAP_MODE=aws_mcp`, re-run Event 1-3 | SAP Integration/Demo | Not Started | | |
| S5-06 | Siapkan talking point juri (IDEA.md) | Demo | Not Started | | |

## Backlog / belum dijadwalkan

| ID | Task | Kategori | Status | Catatan |
|---|---|---|---|---|
| BL-01 | ~~Settings/Admin screen (manage users, lokasi)~~ → **dipindah ke Sprint 4 sebagai S4-11** (arah Roy 2026-10-10) | Dashboard | Moved | Eksekusi di S4-11 |
| BL-02 | Integrasi SAP nyata | Future | Not Started | Pasca-kompetisi |
| BL-03 | Hyperledger Fabric evidence ledger | Future | Not Started | Pasca-kompetisi |

| S4-20 | Audit & upgrade UI/UX menyeluruh (11 tab × 3 lebar): kontras, target sentuh, tipografi meta, umpan balik tekan, konsolidasi token | Dashboard | Done | Hermes | Permintaan Roy 2026-10-11 lewat skill `ui-ux-pro-max` (4 tahap: audit → design system → upgrade → verifikasi), scope dipilih Roy = **konservatif** (A–D, identitas visual acuan tetap, TANPA dark mode; app belum punya `prefers-color-scheme` sama sekali dan itu item terbesar). **METODE**: probe CDP ke :3010 akun demo SPPG Head — 11 tab × 375/768/1440 = **33 keadaan**, tiap keadaan diukur (overflow halaman, target <44px, teks <12px, kontras WCAG dari warna terhitung + latar efektif, tombol ikon tanpa label, gambar tanpa alt) + analisis statis `globals.css` (3.522 baris, 536 selektor, 30 token) + hitung rasio kontras sendiri. Skrip: `audit-ui.mjs` / `shot-ui.mjs` di folder scratch Hermes (bisa dijalankan ulang). **TEMUAN (terukur)**: yang sudah baik — 0 overflow di 33 keadaan, 0 tombol ikon tanpa label, 0 gambar tanpa alt, 0 emoji sebagai ikon (NavIcon SVG), fokus terlihat di 7 tempat, `prefers-reduced-motion` dihormati, `tabular-nums` dipakai. Yang rusak — (1) kontras: `.rec-sep` & `.kpi-breadcrumb-sep` memakai **token garis sebagai warna teks** → 1,49:1 (48 pelanggaran di tab Recommendations); `.fact-warn` = `--status-warning #F9A825` sebagai teks → 1,97:1; label nav `.side-tab` rgba(255,255,255,0,6) → **2,84:1** (audit pertama saya MELEWATKAN ini karena tidak mencampur warna ber-alpha dengan latarnya — alat lalu diperbaiki); `.side-user-sub`/`.side-logout`/`.side-collapse` 2,40:1; `.top-bar-sppg`/`.top-bar-clock` 3,62:1; batas input `--line` 1,18:1. (2) target sentuh: `.side-tab` 40px, `.side-collapse` 28px, lonceng 32px, tombol aksi 34px, `select` panel 19-35px. (3) 13 selektor teks 10-11,5px, termasuk DATA NYATA (`.fact-hint` "keandalan 80%", `.today-row-meta`). (4) **0 aturan `:active`** di seluruh berkas → kontrol terasa mati saat diklik. (5) dua sistem lencana + `.badge[data-status="EXPIRED"]` **didefinisikan dua kali** (identik). (6) 61 hex mentah/26 warna di luar `:root`. (7) `aria-busy` hanya di 4 dari 30 komponen. **PERBAIKAN**: (Tahap 2) +28 token — `--ink-subtle` 5,27:1, `--line-input` ≥3:1, `--ok/--warn/--danger/--neutral-{bg,border,ink}`, `--ink-inverse`, `--on-dark-danger`, `--skeleton-base`, `--dur-1/2/3` + `--ease-standard`, `--space-1..6`, `--text-meta/micro`. (A) `.rec-sep`/breadcrumb → `--ink-subtle`; `.fact-warn` → `--warn-ink` (5,93:1); batas kontrol (`.field input`, `.filter-chip`, `.button-secondary`, `.integrity-panel button`, `.page-header-select`, `.commodity-pill`, `.event2-quotes li label`, `.ops-controls select`) → `--line-input`. (B) blok umpan balik tekan (20 selektor, transform 1px + peredupan, 90ms) + cincin fokus seragam untuk pil/chip/select + target sentuh 44px pada `(pointer: coarse)` **atau** `(max-width: 720px)` untuk nav rail, chip, pil, tombol ikon, `.button`, `input/select/textarea` (kontrol MapLibre dibiarkan 29px — masih di atas batas WCAG 2.2 = 24px — supaya tidak menabrak atribusi); semua gerak tekan dimatikan pada `prefers-reduced-motion`. (C) teks meta → ≥12px (13 titik); lencana/peringatan → token status; aturan EXPIRED duplikat dihapus; hex mentah → token (6 warna brand, 21 teks putih → `--ink-inverse`, 8 latar putih, skeleton). (D) komponen baru `LoadingState` (skeleton + `role="status"` + `aria-live` + `aria-busy`) dipakai di 6 tempat yang sebelumnya menulis teks "Memuat…" polos, + `aria-busy` di 4 papan. **VERIFIKASI**: audit ulang 33 keadaan → **kontras<AA 0, teks<12px 0, overflow 0** di SEMUA tab & lebar; sisa 3 target <44px hanya kontrol zoom MapLibre (29px, sengaja, >24px WCAG). vitest **317/324** (7 gagal = `tests/top-bar.test.tsx`, terbukti berasal dari edit Kiro di `components/TopBar.tsx` yang belum di-commit: brand `<strong>MealChain Guardian</strong>` di HEAD dipindah ke sidebar — bukan dari audit ini; dibuktikan dengan `git show HEAD:...`), tsc bersih untuk berkas audit, `next lint` 0. Fungsi & logika bisnis tidak disentuh; 29 berkas tes tampilan praktis tidak mengunci nama kelas (hanya 1 berkas). **CATATAN PENTING**: `components/globals.css`, `app/page.tsx`, `components/TopBar.tsx`, `components/StockChart.tsx` JUGA sedang disunting Kiro tanpa commit — kalau Kiro menyimpan buffer lama `globals.css`, pekerjaan audit ini bisa tertimpa: sudah di-commit agar aman. |
| S4-21 | Design system: token tunggal, aturan kontras, dan pola keadaan memuat (rujukan `docs/design.md` §4) | Dashboard | Done | Hermes | Bagian kedua permintaan 2026-10-11 (Tahap 2 & 4 skill `ui-ux-pro-max`). `docs/design.md` §4 diperluas: tabel token tambahan + **aturan mengikat** hasil audit — (a) token garis dilarang dipakai sebagai warna teks; (b) `#F9A825` dilarang sebagai warna teks di latar terang (1,97:1), teks peringatan = `--warn-ink`; (c) batas kontrol interaktif = `--line-input` (≥3:1, WCAG 1.4.11), `--line`/`--line-strong` hanya dekoratif; (d) teks di rail biru ≥ `rgba(255,255,255,0.92)` (4,64:1); (e) ukuran teks data ≥12px; (f) target sentuh ≥44px di perangkat sentuh atau ≤720px; (g) setiap kontrol punya `:active` + `:focus-visible` dan menghormati `prefers-reduced-motion`; (h) keadaan memuat satu pola (`LoadingState`). Catatan kejujuran: kueri `--design-system` skill mengembalikan pola "Enterprise Gateway" (landing page marketing) yang MELESET untuk konsol operasi — sudah diulang dengan kueri lebih sempit (`--density 8`) dengan hasil sama, jadi sesuai kontrak skill: tidak ada padanan pola terverifikasi, palet/struktur tetap dari dokumen acuan repo, dan yang dipakai dari skill hanya aturan prioritasnya (kontras, target sentuh, fokus, gerak, tipografi). |
---


## Cara update file ini

1. Ubah `Status` di baris terkait segera setelah berubah — jangan menumpuk perubahan
2. Isi `Assignee` (Roy/teman) supaya jelas siapa pegang apa — hindari kerja dobel
3. Isi `Catatan` singkat kalau ada blocker atau keputusan kecil yang perlu diingat
4. Kalau task baru muncul di tengah jalan (tidak ada di list ini), tambahkan baris baru dengan
   ID mengikuti pola sprint terkait (misal `S3-12`)
5. Jangan hapus baris yang sudah `Done` — itu jadi riwayat, biarkan
| S4-16 | Tanda tangan ECDSA dossier AKTIF (kunci diteruskan ke kontainer) | Infra | Done | Hermes | Permintaan Roy 2026-10-11 ("kerjakan saya mau lihat hasilnya"). Akar masalah: `SIGNING_KEY_HEX` sudah ada di `.env` (64 hex) tetapi `docker-compose.yml` TIDAK meneruskannya ke service `backend` (daftar `environment:` eksplisit) → service signing selalu `unsigned`. Fix: passthrough `SIGNING_KEY_HEX: ${SIGNING_KEY_HEX:-}`. Bukti: `GET /decisions/{id}/dossier` → `signature.state=signed`, `algorithm=ECDSA-secp256k1-sha256 (deterministic RFC6979)`, panjang ttd 128 hex, `verify=true`; uji tamper (`sign_payload(b'mealchain-demo')` lalu verifikasi payload diubah) → false; UI menampilkan "✅ ECDSA-secp256k1-sha256 … · verifikasi BERHASIL". Catatan: `docker compose restart` TIDAK cukup untuk env baru (harus `up -d --no-deps backend`); port host backend mengikuti `BACKEND_PORT` di `.env` (8000) sedangkan UI memakai path relatif lewat proxy Next. Verifikasi: vitest 251/32, tsc 0, lint 0, build 0, pytest backend 595 passed. |
| S4-17 | 4 halaman sidebar acuan yang belum ada (Keamanan Pangan, Surplus & Limbah, Pemasok, Kualitas Agen) | Dashboard | Done | Hermes | Langkah 5 permintaan Roy 2026-10-11: "ini adalah folder referensi E:\hackathon\HackathonBil\MealchainGuardian dan lu harus meniru fiturnya yang ada di sidebarnya dan pagenya". Recon `frontend/lib/nav.ts` acuan = 9 halaman; repo ini sudah setara 5 → 4 halaman dibangun baru dengan data API NYATA (acuan memakai data contoh/MOCK_AGENT_RUNS). (1) **Keamanan Pangan** (`/compliance`): ringkasan pengawasan (aman/gagal uji/perlu verifikasi/belum diuji + berat batch gagal), peringatan batch gagal menyebut lokasinya, kartu batch perlu segera dipakai (lewat batas atau ≤48 jam), tabel per batch (status, kesegaran, layak sampai, sisa masa dari jam klien) — dari `GET /batches`. (2) **Surplus & Limbah** (`/surplus`, peran SPPG saja seperti acuan): neraca surplus/kekurangan dari `/balance/map` komoditas aktif, rencana alokasi greedy (kebutuhan terbesar diisi surplus terbesar, jarak haversine dari koordinat, tombol "Lihat di peta"), kartu pencatatan limbah diisi "—" + ALASAN (tidak ada tabel disposal — menulis 0 kg akan terbaca "tidak ada limbah"). (3) **Pemasok** (`/suppliers`): daftar pemasok + keandalan disusun dari `approval-summary` sampel 8 keputusan terakhir (backend belum punya endpoint daftar pemasok — dinyatakan di halaman), register eksklusi dari `/supplier-exclusions`, panel usul eksklusi yang sudah ada dipakai ulang. (4) **Kualitas Agen** (`/quality`): skor agregat dari `GET /decisions/{id}/traces` + `verdict` `approval-summary` (run dinilai, langkah/run, kesesuaian verifier agree/(agree+disagree), tingkat fallback, keputusan diubah manusia = iterasi > 1, rata-rata durasi) + tabel per run dengan tautan ke Decision & Evidence; halaman menulis "dinilai 8 dari N". Logika murni: `lib/food-safety.ts`, `lib/surplus.ts`, `lib/suppliers-board.ts`, `lib/agent-quality.ts` (38 tes) + kontrak markup `tests/*-board.test.tsx` (25 tes). Refactor kecil: `FactList` diekstrak dari DecisionEvidence jadi komponen bersama; `FactTone` dapat "plain" (kelas CSS-nya sudah ada). Sidebar diurutkan mengikuti acuan + filter peran. Verifikasi: vitest 318/40, tsc 0, lint 0, build 0; di :3010 dengan akun SPPG Head — sidebar 11 tab, Keamanan Pangan 6 batch (5 aman/1 gagal 600 kg), Surplus 2.292 kg vs 830 kg + 6 baris alokasi, Pemasok 1 pemasok 80% + 0 eksklusi, Kualitas Agen 8 run/17 langkah/kesesuaian 75%; konsol bersih (hanya peringatan recharts lama); 1440 & 375 tanpa overflow HALAMAN — tabel lebar dibungkus `.board-table-wrap` (geser di dalam kartu) + petunjuk "Geser tabel ke samping" di ≤640px, karena di 375px tabel 529px dulu melebarkan seluruh halaman. Acuan TIDAK diubah. Commit `7b4ab32`. |
| S4-18 | Peta: sinkronisasi 5 detik tidak lagi mengubah zoom/geser | Dashboard | Done | Hermes | Permintaan Roy 2026-10-11: "buat untuk maps ketika sync tidak ngezoom atau bisa di bilang sync tidak menggangu ukuran zoom". Akar masalah: efek pembangunan peta bergantung pada `locations`, sedangkan polling `GET /balance/map` selalu mengembalikan array BARU → cleanup `map.remove()` + `new maplibregl.Map()` + `fitBounds()` tiap 5 detik → zoom pengguna hilang. Perbaikan: peta dibangun SEKALI (efek bergantung hanya pada ada/tidaknya data, data terbaru lewat `locationsRef`); sinkronisasi memakai tanda tangan ISI (`pinSignatures`/`pinDiff`) + `refreshPin` sehingga hanya penanda yang benar-benar berubah yang disentuh; keputusan fokus lewat `nextMapFocus` (murni) = `fit:true` HANYA saat pertama tampil atau saat lokasi aktif BERGANTI. Helper murni di `lib/map-console.ts` + 5 tes baru. Verifikasi: vitest 324/41, tsc 0, lint 0, build 0; bukti empiris CDP di :3010 — kanvas peta ditandai, zoom-out 3 langkah, tunggu 16 detik (3 siklus polling): elemen kanvas SAMA (peta tidak dibangun ulang) dan tangkapan area peta identik byte-per-byte; 10 penanda utuh; ganti komoditas telur→ayam memperbarui label (Bandung +400 kg → +250 kg) tanpa mengubah zoom; konsol bersih. Commit `1841763`. |
| S4-19 | Dev experience: edit dari Kiro/Hermes langsung terpakai (watcher polling) + port konsol 3010 | Infra | Done | Hermes | Pertanyaan Roy 2026-10-11: "kalau saya edit code dari kiro apakah otomatis tampilan di localhost:3010 berubah?" dan lanjutnya minta rekomendasi realtime. TEMUAN (terukur, bukan dugaan): (a) frontend memang TIDAK ikut berubah — berkas host disunting, ditunggu 75 detik, :3010 tetap kode lama dan 0 baris "Compiled" di log; sebabnya bind mount drive E: (exFAT) tidak meneruskan notifikasi berkas ke kontainer. (b) backend JUSTRU sudah jalan: `command: uvicorn … --reload` sudah ada di compose (bukan Dockerfile), dan uji nyata membuktikan GET /health berubah dalam ~12-15 detik setelah `backend/app/main.py` disunting dari Windows (dugaan awal saya "uvicorn tanpa --reload" SALAH — jangan percaya CMD Dockerfile tanpa memeriksa override compose). PERBAIKAN: `WATCHPACK_POLLING: "true"` + `CHOKIDAR_USEPOLLING: "true"` di service frontend; perintah backend dirapikan jadi `--reload --reload-dir /app/app --reload-exclude "*__pycache__*"` (cakupan lebih sempit, tidak memicu reload saat pytest menulis bytecode) dan TIDAK diberi WATCHFILES_FORCE_POLLING karena tidak perlu. PORT: `.env` FRONTEND_PORT 3000 → 3010 (port 3000 ditempati dev server aplikasi acuan, PID 39472, sengaja dibiarkan hidup sebagai pembanding); ONBOARDING.md ikut diperbarui. BUKTI: rute baru terdeteksi 4,1-4,6 detik; suntingan berkas yang sudah ada 6,3-6,5 detik; penghapusan 0,2 detik (tanpa restart sama sekali). CPU frontend di jendela tenang 90 detik: rata-rata 0,82% / median 0,01% / puncak 2,26% (baseline sebelum polling 0,59%); backend 4,57% vs 3,78% (dalam rentang variasi normal). Satu sampel 137% muncul sekali saat kompilasi dari berkas uji dan tidak berulang. Smoke: :3010 200, /health healthy, frontend vitest 324 passed. |
