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
| S1-01 | Seed dataset 10 lokasi x 3 komoditas | Data | Not Started | | |
| S1-02 | Endpoint `GET /supply/*` | Backend/API | Not Started | | |
| S1-03 | Endpoint `GET /demand/*` | Backend/API | Not Started | | |
| S1-04 | Endpoint `POST /freshness/evaluate` | Backend/API | Not Started | | |
| S1-05 | Endpoint `POST /safety/evaluate` | Backend/API | Not Started | | |
| S1-06 | Endpoint `GET/POST /price/*` | Backend/API | Not Started | | |
| S1-07 | Endpoint `POST /logistics/estimate` | Backend/API | Not Started | | |
| S1-08 | Unit test hard constraints (safety, freshness, capacity, delivery window) | Testing | Not Started | | |
| S1-09 | Mock SAP: material_stock + purchase_orders terisi seed | Mock SAP | Not Started | | |

## Sprint 2 — Balancing engine + Auth + Frontend shell

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S2-01 | Endpoint `POST /cost/safe-delivered` | Backend/API | Not Started | | |
| S2-02 | Endpoint `POST /balance/analyze`, `/balance/recommend` | Backend/API | Not Started | | |
| S2-03 | Endpoint `POST /evidence/fuse` | Backend/API | Not Started | | |
| S2-04 | Auth: JWT login + 2 role | Authentication | Not Started | | |
| S2-05 | RBAC middleware per endpoint | Authentication | Not Started | | |
| S2-06 | Frontend: Login screen | Dashboard | Not Started | | |
| S2-07 | Frontend: Dashboard shell + peta 10 lokasi (data statis dulu) | Dashboard | Not Started | | |
| S2-08 | `openapi.json` bersih ter-generate | Backend/API | Not Started | | |

## Sprint 3 — Agent layer (PALING KRITIS)

| ID | Task | Kategori | Status | Assignee | Catatan |
|---|---|---|---|---|---|
| S3-01 | AgentCore Gateway config dari openapi.json | Agent | Not Started | | |
| S3-02 | Supervisor Agent — panggil 1 tool via Gateway | Agent | Not Started | | |
| S3-03 | Supervisor Agent — alur penuh Event 1 (DETECT→ACT) | Agent | Not Started | | |
| S3-04 | Verifier Agent — audit output Event 1 | Agent | Not Started | | |
| S3-05 | AgentCore Memory terpasang | Agent | Not Started | | |
| S3-06 | AgentCore Observability aktif + trace bisa ditarik | Agent | Not Started | | |
| S3-07 | `agent_traces` table terisi dari trace asli | Backend/Data | Not Started | | |
| S3-08 | Frontend: Recommendation Feed (data asli) | Dashboard | Not Started | | |
| S3-09 | Frontend: Decision Detail + Evidence view | Dashboard | Not Started | | |
| S3-10 | Frontend: Agent Activity Log (trace timeline) | Dashboard | Not Started | | |
| S3-11 | Approval flow — approve → execute → SAP mock PO | Backend/Dashboard | Not Started | | |

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
