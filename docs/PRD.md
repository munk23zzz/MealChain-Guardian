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

**Cakupan data per peran (dikunci 2026-10-14 — `docs/ruling-2026-10-14-scope-lokasi.md`):**
`SPPG Staff` membaca **hanya lokasi sendiri** (keputusan yang targetnya lokasi itu, peta, supply,
demand); permintaan ke lokasi lain dijawab `403`. `Dinas/BGN Admin` (`bgn_monitor`) membaca
**semua lokasi** dan **read-only** — tidak boleh mengubah/mengisi data demo. Aturan ini berlaku
juga di dalam peta dan feed (angka yang sah berbeda antar peran bukan bug). Pengecualian yang
disengaja: **data sumber pemasok** (`GET /suppliers`, register eksklusi) boleh dibaca lintas
daerah oleh peran SPPG, karena memilih pemasok tidak dibatasi wilayah pengguna.

## 4. Scope MVP (3-4 minggu)

### In-scope
- 10 lokasi, 4 komoditas (telur, ayam, wortel, beras) — dataset sintetis terkalibrasi;
  beras adalah komoditas **ambient** (batas suhu ruang, bukan rantai dingin).
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

### Batas domain yang dikunci (Fase 12, 27 Okt 2026)

**Rantai yang dibuktikan berhenti di "bahan diterima".** Titik terakhir yang punya bukti adalah
`batch_receipts`: batch dinilai (evaluator `usable` / `on_hold` / `quarantined`), diceklis, lalu
diterima atau ditahan di lokasi tujuan. Sesudah itu **tidak ada klaim**: tidak ada pengolahan/
memasak, tidak ada porsi tersaji, tidak ada siswa yang dilayani. Metrik yang memerlukan fakta itu
harus berbunyi `no_data` (operasional) atau `simulated_estimate` berlabel (demo) — lihat
`docs/Skill.md` §4 dan `docs/kamus-kpi-dan-state-machine.md`. Kalimat "makanan sampai ke siswa"
atau "porsi terlayani" tidak boleh diucapkan; yang boleh: "bahan aman dan layak diterima di
dapur", beserta nama buktinya (`batch_receipts` + blok ledger).

### Out-of-scope (MVP default, tapi siap di-switch — lihat `Architecture.md` §9)
- Integrasi SAP nyata via AWS for SAP MCP Server — di-mock sepenuhnya untuk demo default.
  Adapter `AWSforSAPMCPProvider` **sudah ada** dan diuji dengan contract test yang sama seperti
  mock, tetapi itu **pekerjaan kontrak, bukan bukti koneksi**: tanpa tenant S/4HANA/ECC +
  kredensial OData/BTP ia menolak jalan (fail closed). Memindahkan system of record berarti
  menyediakan ERP + kredensial lebih dulu, bukan "satu baris config" (`Architecture.md` §9,
  `Roadmap.md` Sprint 5). Proposal yang lolos finalist memang menyebut AWS for SAP MCP Server;
  yang belum ada adalah tenant-nya.
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
6. **KPI Dashboard** — 7 indikator (lihat `Skill.md` untuk definisi).
   *Catatan 2026-10-15 (keputusan pemilik):* tab KPI dan halaman tambahan **Kualitas Agen**
   disatukan menjadi satu tab sidebar **"KPI & Kualitas Agen"** (KPI dulu, lalu mutu kerja agen);
   strip "Target KPI Demo Day" dihapus dari halaman KPI. Penyimpangan yang disengaja dari daftar
   layar §5 di atas — dicatat supaya klaim alignment PRD tidak dibaca berlebihan. Bukti:
   `docs/verification/fase-8.md`.
7. **Auth & Role-based View** — login, 3 role (sppg_head, sppg_nutritionist, bgn_monitor)

## 6. Technical requirements (ringkas — detail di `Architecture.md`)

- Backend: Python/FastAPI
- Frontend: React (Next.js) + TypeScript
- Database: PostgreSQL
- Agent: Strands Agents SDK; Supervisor Agent **sudah di-deploy ke AgentCore Runtime** (VERIFIED
  18 Okt 2026), sedangkan **Gateway belum aktif** (0 gateway; `AGENTCORE_GATEWAY_URL` kosong) dan
  **Memory tulis belum diizinkan IAM**. Observability aplikasi masih sink lokal, bukan X-Ray.
  Rincian per resource/target/invocation/aplikasi: `docs/verification/AGENTCORE_STATUS.md`.
- Dev environment: Docker Compose (lokal); komponen AgentCore memanggil AWS asli (trial account)
- Testing: TDD untuk business logic inti (safety & cost calculation wajib diuji)

## 7. Success metrics

### Metrics produk (7 KPI — definisi lengkap di `Skill.md`)
Meal Continuity Rate · Avoidable Food Loss · Regional Imbalance Resolution Rate ·
Safe Delivered Cost · Procurement Price Deviation · Decision Time · Evidence Completeness

### Metrics kompetisi (checklist penilaian juri)
| Kriteria juri | Bukti di MVP |
|---|---|
| AWS/SAP agentic AI sebagai inti | Supervisor Agent berjalan di AgentCore Runtime (VERIFIED), Verifier Agent + tool deterministik di backend; Gateway/Memory belum aktif (lihat `docs/verification/AGENTCORE_STATUS.md`). SAP: test double di balik adapter, adapter MCP diuji sebagai kontrak — **belum tersambung ke tenant** |
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
