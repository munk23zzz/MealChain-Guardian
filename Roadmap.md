# Roadmap.md — MealChain Guardian

Target: 3-4 minggu ke live demo. Tiap sprint = checklist goal. Kalau ada goal terlewat di
akhir sprint, JANGAN lanjut ke sprint berikutnya sebelum ditandai di `TODO.md` sebagai
carry-over eksplisit.

---

## Sprint 0 — Setup (2-3 hari)

- [x] Repo greenfield diinisiasi sesuai struktur folder di `docs/Architecture.md` §4
- [x] Docker Compose jalan: backend (kosong/hello-world), postgres, frontend (kosong/hello-world)
- [x] Migration awal Postgres sesuai `docs/Schema.md` (tabel master data dulu)
- [ ] Verifikasi akses AWS trial: Bedrock model invoke berhasil, akses AgentCore dikonfirmasi
- [ ] Strands SDK "hello-world" agent berhasil jalan (belum perlu tool apapun)
- [x] `.env.example` dibuat, `.env` asli tidak ter-commit

**Definition of Done Sprint 0:** kalau salah satu di atas belum, JANGAN mulai Sprint 1 —
fondasi ini kalau salah akan menghambat semua sprint berikutnya.


## Sprint 1 — Business logic inti + data (Minggu 1)

- [x] Seed dataset sintetis: 10 lokasi, 3 komoditas (lihat `data/seed/`)
- [x] Endpoint `/supply/*`, `/demand/*` jalan + tertaut ke Postgres
- [x] Endpoint `/freshness/evaluate` — implementasi formula sesuai `docs/Skill.md` §3
- [x] Endpoint `/safety/evaluate` — implementasi hard constraint check, return
  PASS/FAIL/NEEDS_VERIFICATION
- [x] Endpoint `/price/deviation`
- [x] Endpoint `/logistics/estimate` (pakai data jarak antar 10 lokasi, boleh hardcode/precompute)
- [x] Unit test untuk semua fungsi di `core/` — minimal 1 test per hard constraint
- [x] Mock SAP: `sap_mock_material_stock`, `sap_mock_purchase_orders` terisi seed data

**Definition of Done:** semua endpoint di atas bisa dipanggil manual (Postman/curl) dan
menghasilkan angka yang sudah diverifikasi manual sesuai contoh di `docs/Skill.md` §7.

## Sprint 2 — Balancing engine + Auth + Frontend shell (Minggu 2)

> **Catatan eksekusi 2026-10-05/06:** Sprint 2 dieksekusi sesuai plan
> terkunci `.hermes/plans/2026-10-05-sprint2-decision-intelligence.md`
> (decision intelligence: candidate model, gap, generator, reliability,
> Candidate Score, SDC, ranking, decision persistence + `expires_at`,
> API, expiry, supervisor context, frontend test runner, demo 10×).
> Item Roadmap di luar plan tersebut adalah carry-over eksplisit
> (bukan kegagalan) — lihat `docs/verification/sprint-2.md`.

- [x] Engine `/cost/safe-delivered` (SDC penuh + breakdown; diekspos via `/balance/recommend`)
- [x] Endpoint `/balance/recommend` + `/balance/{location}/{commodity}` (gap facts)
- [x] Decision persistence + `expires_at` (valid/expired deterministik)
- [x] Supervisor decision context (assembler allowlist, tanpa kalkulasi LLM)
- [ ] Endpoint `/cost/safe-delivered` standalone (carry-over)
- [ ] Endpoint `/balance/analyze` penuh (carry-over)
- [ ] Endpoint `/evidence/fuse` (consistency check) (carry-over)
- [ ] Auth: login, JWT, 3 role (sppg_head, sppg_nutritionist, bgn_monitor), middleware RBAC per endpoint (carry-over)
- [ ] Frontend: Login screen, Dashboard shell (peta 10 lokasi, tanpa data live agent dulu) (carry-over)
- [ ] `openapi.json` backend ter-generate bersih (siap untuk Gateway di Sprint 3) (carry-over)

**Definition of Done:** login berfungsi untuk 3 role berbeda dengan scope akses yang benar;
`/balance/recommend` mengembalikan hasil yang masuk akal untuk skenario Cianjur→Jakarta manual.

## Sprint 3 — Agent layer (Minggu 3) — INI SPRINT PALING KRITIS

> **Status audit 2026-10-06:** Sprint 3 belum dimulai. Plan tersedia di
> `docs/superpowers/plans/2026-10-06-sprint3-agent-layer.md`. S3-00 wajib PASS
> terlebih dahulu; audit lintas Sprint 0–2 menemukan OpenAPI artifact,
> JWT/RBAC/action boundary, dan current AWS/AgentCore/Strands evidence belum
> tersedia. Lihat `docs/verification/sprint-0-2-cross-sprint-audit.md`.

- [ ] AgentCore Gateway dikonfigurasi, `openapi.json` di-register jadi MCP tools
- [ ] Supervisor Agent (Strands) berhasil memanggil minimal 1 tool lewat Gateway
- [ ] Supervisor Agent bisa menjalankan alur DETECT→VERIFY→...→ACT untuk Event 1
  (regional imbalance) end-to-end
- [ ] Verifier Agent dibuat, berhasil mengaudit output Supervisor untuk Event 1
- [ ] AgentCore Memory terpasang, state per sesi keputusan tersimpan
- [ ] AgentCore Observability aktif, trace bisa ditarik lewat API/SDK
- [ ] `agent_traces` table terisi dari trace asli (bukan mock)
- [ ] Frontend: Recommendation Feed + Decision Detail + Agent Activity Log terhubung ke data
  asli (bukan dummy)
- [ ] Approval flow: approve → `actions.execute` → `sap_mock_purchase_orders` terisi

**Definition of Done:** Event 1 bisa didemokan end-to-end dari UI, dan Agent Activity Log
menunjukkan trace asli dengan tool calls yang benar-benar terjadi.

## Sprint 4 — Event 2 & 3, KPI, polish, rehearsal (Minggu 4)

- [ ] Event 2 (price anomaly) end-to-end interaktif
- [ ] Event 3 (safety disruption/temperature excursion → reroute Bogor) end-to-end interaktif
- [ ] KPI Dashboard — 7 KPI terhitung dari data real (bukan hardcode)
- [ ] Approval Modal — ringkasan lengkap sebelum eksekusi
- [ ] Checklist rehearsal demo di `workflows.md` §6 dijalankan dan lolos
- [ ] Video fallback direkam
- [ ] (Stretch, kalau waktu ada) AgentCore Identity untuk credential handoff ke mock SAP
- [ ] (Stretch, kalau waktu ada) Deploy backend+frontend ke AWS App Runner untuk akses dari luar

**Definition of Done:** ketiga skenario demo lolos rehearsal 3x berturut-turut tanpa gagal;
video fallback ada; tim siap presentasi.

## Sprint 5 — Real SAP via AWS for SAP MCP Server (ON-DEMAND, bukan default MVP)

**Trigger:** hanya dieksekusi kalau juri/panitia secara eksplisit minta demo dengan SAP nyata,
atau tersedia akses tenant SAP trial kompetisi yang cukup. **Bukan blocker untuk demo utama** —
Sprint 0-4 harus tetap lolos dengan `SAP_MODE=mock` terlebih dahulu.

Ini BUKAN penambahan scope baru — proposal yang sudah lolos finalist sudah menyebut AWS for
SAP MCP Server sebagai konektivitas SAP kita (lihat `docs/Architecture.md` §9). Sprint ini
menunaikan itu.

- [ ] Provisioning AWS for SAP MCP Server, arahkan ke tenant SAP trial kompetisi
- [ ] Setup kredensial via AgentCore Identity (naikkan S4-07 dari stretch → wajib untuk sprint ini)
- [ ] Implementasi `AWSforSAPMCPProvider` sesuai `docs/Skill.md` §7 (field mapping)
- [ ] `test_sap_integration_contract.py` lolos untuk MockSAPProvider **dan**
  AWSforSAPMCPProvider (bukti tidak ada regresi business logic)
- [ ] Switch `SAP_MODE=aws_mcp`, re-run Event 1-3 end-to-end dengan data SAP nyata
- [ ] Siapkan talking point juri (lihat `IDEA.md` — "Framing: Mock vs Real SAP")

**Definition of Done:** ketiga skenario demo jalan identik secara business-logic baik di
`SAP_MODE=mock` maupun `SAP_MODE=aws_mcp` — perbedaan HANYA di sumber data, bukan di hasil
keputusan agent.

## Cara pakai roadmap ini

- Setiap goal yang selesai, checklist di sini DAN update baris terkait di `TODO.md` (dua-duanya,
  bukan salah satu) — `Roadmap.md` untuk gambaran besar per sprint, `TODO.md` untuk detail
  status/blocker per task
- Kalau ada goal sprint yang di akhir minggu masih `[ ]` — jangan diam-diam skip, catat
  eksplisit di `TODO.md` sebagai "carry-over" dengan alasan
