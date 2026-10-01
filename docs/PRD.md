# PRD.md — MealChain Guardian

**Status:** Draft v1.0 — locked untuk mulai development
**Konteks lengkap:** lihat `../IDEA.md` untuk latar belakang & positioning

---

## 1. Vision

Agentic AI yang menyeimbangkan pasokan pangan lintas lokasi untuk Program Makan Bergizi
Gratis (MBG), dengan keamanan pangan sebagai *hard constraint*, didemonstrasikan sebagai
working MVP untuk kompetisi Sokrates x SAP x AWS.

## 2. Goals

### Goals bisnis/kompetisi
- G1. Lolos syarat "use AWS/SAP agentic AI as core of the solution" — dibuktikan lewat
  penggunaan nyata Bedrock AgentCore (Runtime, Gateway, Memory, Observability)
- G2. Demonstrasi **working MVP** yang bisa diklik live di depan juri
- G3. Menunjukkan **autonomous multi-step reasoning** yang terlihat jelas (Agent Activity Log
  dari trace asli, bukan simulasi)
- G4. Cerita bisnis yang genuine dan practical — terhubung ke masalah nyata MBG yang sudah
  terverifikasi (lihat proposal untuk sitasi)

### Goals produk (kalau dilanjut pasca-kompetisi)
- G5. Mengurangi avoidable food loss & emergency procurement pada jaringan SPPG
- G6. Memberi Dinas/BGN audit trail berbasis bukti sebelum insiden terjadi

## 3. Target users

| Peran | Kebutuhan | Akses |
|---|---|---|
| **SPPG Staff** | Melihat rekomendasi alokasi, status supply/demand lokasinya, approve/reject aksi | Dashboard scoped ke lokasi sendiri |
| **Dinas/BGN Admin** | Melihat semua lokasi, audit evidence, approve aksi lintas-wilayah, monitor KPI | Dashboard scoped ke semua lokasi |
| **Juri kompetisi** | Melihat agent bekerja autonomous, memahami value proposition dalam < 10 menit demo | Guided demo flow, bukan role terpisah |

## 4. Scope MVP (3-4 minggu)

### In-scope
- 10 lokasi, 3 komoditas (telur, ayam, wortel) — dataset sintetis terkalibrasi
- 3 skenario demo **interaktif penuh**:
  - **Event 1** — Regional imbalance (Cianjur surplus → Jakarta shortage)
  - **Event 2** — Price anomaly (deviasi harga pemasok vs referensi pasar)
  - **Event 3** — Safety disruption (temperature excursion → source dikeluarkan → reroute ke Bogor)
- Supervisor Agent (Strands SDK di AgentCore Runtime) + Verifier Agent
- Tools deterministik untuk 7 fungsi worker: Supply, Demand, Freshness, Safety, Price,
  Logistics, Evidence Fusion + Balancing/Optimization Engine
- Mock SAP API (meniru struktur OData API_MATERIAL_STOCK, API_MATERIAL_DOCUMENT,
  API_PURCHASEORDER_PROCESS_SRV, API_BUSINESS_PARTNER, API_PRODUCT_SRV)
- Autentikasi + 3 role (sppg_head, sppg_nutritionist, bgn_monitor)
- Dashboard: peta 10 lokasi, feed rekomendasi, detail keputusan + evidence, Agent Activity
  Log (trace), approval flow, KPI dashboard
- Evidence ledger (Postgres, append-only, hash chain sederhana)

### Out-of-scope (MVP default, tapi siap di-switch — lihat `Architecture.md` §9)
- Integrasi SAP nyata via AWS for SAP MCP Server — di-mock sepenuhnya untuk demo default,
  TAPI dibangun di belakang adapter interface sejak Sprint 1 sehingga bisa dinyalakan lewat
  config change kalau juri/panitia meminta (rencana eksekusi: `Roadmap.md` Sprint 5). Ini
  bukan gap — proposal yang lolos finalist sudah menyebut AWS for SAP MCP Server sebagai
  konektivitas SAP kita.
- AgentCore Identity (stretch goal kalau waktu ada)
- Blockchain permissioned (Hyperledger Fabric) — future extension, bukan MVP
- Mobile app
- Multi-tenant / multi-instansi selain skenario demo
- SSO/OAuth enterprise — auth MVP pakai JWT sederhana
- Real-time notification channel (WhatsApp/SMS) ke petani/SPPG
- Localization (selain Bahasa Indonesia)

## 5. Core features

1. **Location & Commodity Overview** — peta/list 10 lokasi dengan status surplus/shortage/tight
2. **Recommendation Feed** — daftar rekomendasi aktif dari Supervisor Agent, sorted by urgency
3. **Decision Detail & Evidence View** — breakdown Safe Delivered Cost, hard-constraint check,
   evidence yang mendukung/menolak
4. **Agent Activity Log** — trace step-by-step (DETECT→VERIFY→TRACE→PREDICT→OPTIMIZE→DECIDE→ACT→LEARN),
   diambil dari AgentCore Observability
5. **Approval Flow** — approver SPPG (SPPG Head / SPPG Nutritionist) approve atau reject aksi berisiko tinggi sebelum eksekusi; `bgn_monitor` read-only
6. **KPI Dashboard** — 7 indikator (lihat `Skill.md` untuk definisi)
7. **Auth & Role-based View** — login, 3 role (sppg_head, sppg_nutritionist, bgn_monitor)

## 6. Technical requirements (ringkas — detail di `Architecture.md`)

- Backend: Python/FastAPI
- Frontend: React (Next.js) + TypeScript
- Database: PostgreSQL
- Agent: Strands Agents SDK on Amazon Bedrock AgentCore (Runtime, Gateway, Memory, Observability)
- Dev environment: Docker Compose (lokal); komponen AgentCore memanggil AWS asli (trial account)
- Testing: TDD untuk business logic inti (safety & cost calculation wajib diuji)

## 7. Success metrics

### Metrics produk (7 KPI — definisi lengkap di `Skill.md`)
Meal Continuity Rate · Avoidable Food Loss · Regional Imbalance Resolution Rate ·
Safe Delivered Cost · Procurement Price Deviation · Decision Time · Evidence Completeness

### Metrics kompetisi (checklist penilaian juri)
| Kriteria juri | Bukti di MVP |
|---|---|
| AWS/SAP agentic AI sebagai inti | Supervisor+Verifier Agent nyata di Bedrock AgentCore, bukan wrapper API biasa; konektivitas SAP dibangun siap-switch ke AWS for SAP MCP Server (§9 Architecture.md), bisa didemokan live kalau diminta |
| Working MVP | 3 skenario demo end-to-end jalan live |
| Autonomous multi-step reasoning | Agent Activity Log dari trace asli AgentCore Observability |
| Genuine business challenge | Terhubung ke data MBG terverifikasi (lihat proposal) |
| Practical & usable outcome | Approval flow manusia tetap ada — bukan "black box AI" |

## 8. Assumptions & risks

| Asumsi/Risiko | Mitigasi |
|---|---|
| AWS trial account cukup untuk Bedrock + AgentCore selama development | Verifikasi akses di Sprint 0, sebelum commit ke arsitektur ini |
| Live LLM call bisa gagal/lambat saat demo di depan juri | Rehearsal berkali-kali + rekaman fallback (lihat `workflows.md`) |
| Timeline 3-4 minggu ketat untuk duo team | Scope MVP dipotong ketat (lihat Out-of-scope); AgentCore Identity & fitur non-esensial jadi stretch goal |
| Data sintetis harus tetap kredibel bukan asal-asalan | Kalibrasi terhadap sinyal pasar terverifikasi (lihat proposal, bagian sitasi) |

## 9. Future work (pasca-kompetisi, tidak dikerjakan sekarang)

Integrasi SAP nyata · AgentCore Identity penuh · Hyperledger Fabric evidence ledger ·
ekspansi ke rumah sakit/katering industri/bantuan kemanusiaan · notifikasi WhatsApp ke petani
