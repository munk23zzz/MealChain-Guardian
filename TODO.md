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
| S0-04 | Verifikasi akses AWS trial (Bedrock invoke test) | Setup | In Progress | | Waiting for AWS credentials |
| S0-05 | Verifikasi akses AgentCore | Setup | Not Started | | |
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
| S2-03 | Endpoint `POST /evidence/fuse` | Backend/API | Not Started | | Evidence dasar + supervisor context tersedia (Task 12, commit ac33d24); endpoint fuse = carry-over |
| S2-04 | Auth: JWT login + 3 role (sppg_head, sppg_nutritionist, bgn_monitor) | Authentication | Not Started | | Di luar plan Sprint 2 eksekusi (decision intelligence) — carry-over eksplisit |
| S2-05 | RBAC middleware per endpoint | Authentication | Not Started | | Carry-over eksplisit (lihat atas) |
| S2-06 | Frontend: Login screen | Dashboard | Not Started | | Di luar plan Sprint 2 eksekusi; vitest runner terpasang (Task 0/13) |
| S2-07 | Frontend: Dashboard shell + peta 10 lokasi (data statis dulu) | Dashboard | Not Started | | Di luar plan Sprint 2 eksekusi |
| S2-08 | `openapi.json` bersih ter-generate | Backend/API | Not Started | | Carry-over eksplisit |

## Sprint 3 — Agent layer (PALING KRITIS)

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

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S4-01 | Event 2 (price anomaly) end-to-end interaktif | Demo Scenario | Not Started | | |
| S4-02 | Event 3 (safety disruption → reroute Bogor) end-to-end interaktif | Demo Scenario | Not Started | | |
| S4-03 | KPI Dashboard — 7 KPI dari data real | Dashboard | Not Started | | |
| S4-04 | Approval Modal — ringkasan lengkap | Dashboard | Not Started | | |
| S4-05 | Rehearsal checklist (workflows.md §6) — 3x lolos berturut-turut | QA/Demo | Not Started | | |
| S4-06 | Rekam video fallback | QA/Demo | Not Started | | |
| S4-07 | (Stretch) AgentCore Identity | Stretch | Not Started | | |
| S4-08 | (Stretch) Deploy ke AWS App Runner | Stretch | Not Started | | |

## Sprint 5 — Real SAP via AWS for SAP MCP Server (ON-DEMAND — cek Roadmap.md sebelum mulai)

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S5-01 | Provisioning AWS for SAP MCP Server ke tenant SAP trial | SAP Integration | Not Started | | Trigger: diminta juri/panitia |
| S5-02 | AgentCore Identity untuk kredensial SAP (naik dari stretch S4-07) | SAP Integration | Not Started | | |
| S5-03 | Implementasi `AWSforSAPMCPProvider` (Skill.md §7) | SAP Integration | Not Started | | |
| S5-04 | Contract test lolos untuk mock + aws_mcp | SAP Integration/Testing | Not Started | | Wajib sebelum switch default |
| S5-05 | Switch `SAP_MODE=aws_mcp`, re-run Event 1-3 | SAP Integration/Demo | Not Started | | |
| S5-06 | Siapkan talking point juri (IDEA.md) | Demo | Not Started | | |

## Backlog / belum dijadwalkan

| ID | Task | Kategori | Status | Catatan |
|---|---|---|---|---|
| BL-01 | Settings/Admin screen (manage users, lokasi) | Dashboard | Not Started | Nice-to-have, potong dulu kalau waktu mepet |
| BL-02 | Integrasi SAP nyata | Future | Not Started | Pasca-kompetisi |
| BL-03 | Hyperledger Fabric evidence ledger | Future | Not Started | Pasca-kompetisi |

---

## Cara update file ini

1. Ubah `Status` di baris terkait segera setelah berubah — jangan menumpuk perubahan
2. Isi `Assignee` (Roy/teman) supaya jelas siapa pegang apa — hindari kerja dobel
3. Isi `Catatan` singkat kalau ada blocker atau keputusan kecil yang perlu diingat
4. Kalau task baru muncul di tengah jalan (tidak ada di list ini), tambahkan baris baru dengan
   ID mengikuti pola sprint terkait (misal `S3-12`)
5. Jangan hapus baris yang sudah `Done` — itu jadi riwayat, biarkan
