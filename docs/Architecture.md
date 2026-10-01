# Architecture.md — MealChain Guardian

**Prasyarat baca:** `../IDEA.md`, `PRD.md`

---

## 1. Prinsip arsitektur (baca ini sebelum ubah apapun)

1. **Matematika/keputusan safety tidak pernah dihitung oleh LLM.** Semua angka (Safe Delivered
   Cost, scoring, constraint check) = kode deterministik biasa, unit-tested. LLM hanya
   mengorkestrasi tool mana dipanggil, menafsirkan hasil, dan menjelaskan ke user.
2. **Setiap keputusan berisiko tinggi butuh persetujuan manusia** sebelum eksekusi ke SAP
   (mock). Tidak ada auto-execute untuk aksi yang mengubah data atau mengeksklusi supplier.
3. **Verifier Agent selalu mengaudit sebelum aksi ditampilkan sebagai "recommended".**
4. Setiap keputusan teknis harus bisa dijawab: *"ini membantu penuhi syarat juri yang mana?"*
   (lihat `IDEA.md` bagian syarat kompetisi).

## 2. Tech stack

| Layer | Pilihan | Kenapa |
|---|---|---|
| Backend API | **Python 3.12 + FastAPI** | Async native, OpenAPI spec otomatis (dibutuhkan AgentCore Gateway untuk auto-convert endpoint jadi MCP tools), tim sudah familiar Python |
| Agent framework | **Strands Agents SDK** | SDK resmi AWS, dirancang khusus untuk jalan di atas Bedrock AgentCore, ringan (bukan LangChain yang berat) |
| Agent infra | **Amazon Bedrock AgentCore** (Runtime, Gateway, Memory, Observability) | Wajib untuk memenuhi syarat "AWS/SAP Agentic AI" kompetisi secara literal, bukan cuma "pakai LLM" |
| Model | **Claude via Amazon Bedrock** (Supervisor + Verifier, prompt/persona berbeda) | Tersedia di Bedrock, tool-use matang |
| Database | **PostgreSQL 16** | Relasional cocok untuk data supply/demand/evidence yang saling terhubung; satu instance untuk semua data (bukan dipisah) |
| Frontend | **Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui** | Modern, cepat untuk build, tim tidak ada preferensi kuat jadi pilih yang paling banyak dukungan skill (`frontend-design`, `ui-ux-pro-max` Hermes sudah punya konvensi untuk stack ini) |
| Charting | **Recharts** | Konsisten dengan chart yang sudah dibuat untuk proposal |
| Map | **MapLibre GL JS** + tile OSM gratis | Konsisten dengan pemakaian OSM/OSRM di proposal, tidak butuh API key berbayar |
| Auth | **JWT + bcrypt**, RBAC sederhana (3 role) | Cukup untuk MVP, tidak perlu SSO enterprise |
| Dev environment | **Docker Compose** (backend, frontend, postgres, mock-sap) | Lokal, konsisten cross-machine untuk duo team |
| Hosting | Lokal untuk semua service KECUALI agent layer | AgentCore Runtime/Gateway **wajib** jalan di AWS asli (tidak bisa di-Docker-kan lokal) — lihat §5 |

## 3. Kenapa hosting "lokal + AWS asli untuk agent" (bukan full-AWS atau full-lokal)

- **Full-lokal tidak mungkin**: AgentCore Runtime/Gateway adalah managed service AWS, tidak
  ada versi self-hosted. Kalau mau syarat "Use of AWS/SAP Agentic AI" terpenuhi jujur, bagian
  agent HARUS memanggil AWS asli.
- **Full-AWS belum perlu**: backend/frontend/Postgres tidak butuh AWS untuk development —
  Docker Compose lokal lebih cepat untuk iterasi duo team, dan tidak ada pengumuman deployment
  yang mengharuskan online 24 jam saat ini.
- Kalau nanti dibutuhkan demo yang bisa diakses juri dari luar (bukan cuma live di ruangan),
  baru deploy backend+frontend ke AWS (ECS Fargate atau App Runner) — App Runner direkomendasikan
  karena setup paling sederhana untuk timeline sesempit ini.

## 4. Struktur folder (monorepo)

```
mealchain-guardian/
├── IDEA.md
├── AGENTS.md
├── Rules.md
├── workflows.md
├── Roadmap.md
├── TODO.md
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── Architecture.md
│   ├── design.md
│   ├── Schema.md
│   └── Skill.md
├── backend/                      # FastAPI — semua tool deterministik
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── supply.py         # GET /supply, /supply/{location}/{commodity}
│   │   │   ├── demand.py         # GET /demand, /demand/forecast
│   │   │   ├── freshness.py      # POST /freshness/evaluate
│   │   │   ├── safety.py         # POST /safety/evaluate
│   │   │   ├── price.py          # GET /price, POST /price/deviation
│   │   │   ├── logistics.py      # POST /logistics/estimate
│   │   │   ├── evidence.py       # POST /evidence/fuse, GET /evidence/{decision_id}
│   │   │   ├── balance.py        # POST /balance/analyze, /balance/recommend
│   │   │   ├── cost.py           # POST /cost/safe-delivered
│   │   │   ├── decisions.py      # POST /decisions/evaluate, GET /decisions/{id}
│   │   │   └── actions.py        # POST /actions/propose|approve|execute
│   │   ├── core/                 # domain logic murni, tidak tahu soal HTTP
│   │   │   ├── scoring.py        # Candidate Score formula
│   │   │   ├── safe_delivered_cost.py
│   │   │   ├── constraints.py    # hard constraint checks
│   │   │   └── evidence_consistency.py
│   │   ├── models/                # SQLAlchemy models (cermin Schema.md)
│   │   ├── sap_integration/       # ADAPTER PATTERN — lihat §9. JANGAN panggil SAP
│   │   │   │                      # langsung dari core/ atau api/, selalu lewat sini.
│   │   │   ├── provider_interface.py   # SAPDataProvider (abstract): get_material_stock(),
│   │   │   │                            # get_purchase_orders(), create_purchase_order(),
│   │   │   │                            # get_business_partner(), get_product_master()
│   │   │   ├── mock_provider.py        # MockSAPProvider — implementasi default MVP,
│   │   │   │                            # meniru struktur OData persis (field sama)
│   │   │   ├── aws_mcp_provider.py     # AWSforSAPMCPProvider — implementasi real, lihat §9.
│   │   │   │                            # Ditulis sejak awal (boleh raise NotImplementedError
│   │   │   │                            # di body), supaya interface teruji sejak Sprint 1.
│   │   │   └── factory.py              # get_sap_provider() → baca env SAP_MODE=mock|aws_mcp
│   │   └── db.py
│   ├── tests/
│   │   └── test_sap_integration_contract.py  # test yang sama jalan untuk KEDUA provider
│   │                                            # (mock & aws_mcp) — bukti kontrak identik
│   └── openapi.json               # auto-generated, dipakai AgentCore Gateway. Endpoint yang
│                                     # menyentuh SAP tetap sama persis apapun SAP_MODE-nya.
├── agent/                         # Strands Agent — Supervisor + Verifier
│   ├── supervisor_agent.py
│   ├── verifier_agent.py
│   ├── gateway_config/            # target config AgentCore Gateway (dari openapi.json)
│   └── prompts/
│       ├── supervisor_system_prompt.md
│       └── verifier_system_prompt.md
├── frontend/                      # Next.js dashboard
│   ├── app/
│   │   ├── (auth)/login/
│   │   ├── dashboard/
│   │   ├── decisions/[id]/
│   │   ├── agent-log/
│   │   └── kpi/
│   ├── components/
│   └── lib/
├── infra/
│   ├── docker/
│   └── aws/                       # AgentCore Gateway/Runtime deployment config (Strands starter toolkit)
└── data/
    └── seed/                      # dataset sintetis 10 lokasi x 3 komoditas
```

## 5. Arsitektur agent (inti sistem)

```
                        ┌────────────────────────┐
                        │   Frontend (Next.js)   │
                        │  Dashboard / Approval   │
                        └───────────┬────────────┘
                                    │ REST (JWT auth)
                                    ▼
                        ┌────────────────────────┐
                        │  FastAPI Backend        │──────► PostgreSQL
                        │  (tool deterministik)   │
                        │  Supply/Demand/Freshness│
                        │  Safety/Price/Logistics │
                        │  Evidence/Balancing     │
                        └───────────┬────────────┘
                                    │ OpenAPI spec
                                    ▼
                        ┌────────────────────────┐
                        │  AgentCore Gateway      │  ← ubah endpoint FastAPI
                        │  (MCP tools)            │    jadi MCP tools otomatis
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │  AgentCore Runtime      │
                        │  ┌──────────────────┐   │
                        │  │ Supervisor Agent  │   │  ← Strands SDK, model Claude
                        │  │ (Strands)         │   │    via Bedrock, panggil tools
                        │  └─────────┬─────────┘   │
                        │            │ proposed     │
                        │            │ action       │
                        │  ┌─────────▼─────────┐   │
                        │  │ Verifier Agent     │   │  ← persona skeptis, audit
                        │  │ (Strands)          │   │    kecocokan aksi vs evidence
                        │  └────────────────────┘   │
                        │                            │
                        │  AgentCore Memory ─────────┼── state per sesi keputusan
                        │  AgentCore Observability ──┼── trace step-by-step
                        └────────────────────────────┘
                                    │
                                    ▼
                        Human approval (SPPG Head / SPPG Nutritionist) → Action Agent (tool) → SAP mock
```

### Mapping "9 worker agent" (nama di proposal) → implementasi teknis

| Nama di proposal | Implementasi nyata |
|---|---|
| Supply Agent | Tool group: `GET /supply/*` |
| Demand Agent | Tool group: `GET /demand/*` |
| Freshness Guardian | Tool: `POST /freshness/evaluate` |
| Safety Guardian | Tool: `POST /safety/evaluate` (return PASS/FAIL/NEEDS_VERIFICATION — agent TIDAK BOLEH override ini) |
| Price Agent | Tool group: `GET /price`, `POST /price/deviation` |
| Logistics Agent | Tool: `POST /logistics/estimate` |
| Evidence Fusion Agent | Tool: `POST /evidence/fuse` (consistency check GPS/timestamp/suhu) |
| Balancing/Optimization Engine | Tool: `POST /balance/recommend` + `POST /cost/safe-delivered` |
| Action Agent | Tool group: `POST /actions/*` (butuh approval sebelum `/execute`) |

Supervisor Agent = satu-satunya entitas yang "reasoning" — dia memutuskan tool mana dipanggil,
urutan apa, dan menyusun rekomendasi. Ini genuinely autonomous (bukan state machine hardcoded)
tapi selalu grounded ke tool deterministik untuk angka/safety.

### Kenapa Verifier Agent terpisah, bukan bagian dari Supervisor

**Ini bukan penambahan di luar proposal — ini implementasi konkret dari langkah `VERIFY` yang
sudah tertulis di alur keputusan proposal sendiri** (DETECT → **VERIFY** → TRACE → PREDICT →
OPTIMIZE → DECIDE → ACT → LEARN). Proposal juga sudah mengutip argumen explainable AI bahwa
akuntabilitas pada sistem otonom berisiko tinggi menuntut *pengawasan eksplisit*, bukan
keputusan tertutup oleh satu algoritma (Chukwunweike et al., 2024). Kalau `VERIFY` dieksekusi
oleh entitas yang sama yang mengusulkan (Supervisor menilai pekerjaannya sendiri), itu bukan
"pengawasan eksplisit" — itu cuma satu agent bicara pada dirinya sendiri. Verifier Agent
sebagai entitas independen adalah cara paling jujur untuk menunaikan klaim yang sudah kita
tulis, bukan menambah klaim baru.

Generator-critic pattern: Supervisor mengusulkan, Verifier mengaudit kecocokan usulan itu
terhadap raw evidence sebelum ditampilkan sebagai rekomendasi. System prompt Verifier
diposisikan sebagai auditor skeptis (bukan asisten membantu) untuk mengurangi *correlated
failure* — lihat `agent/prompts/verifier_system_prompt.md`.

**Catatan penamaan (bukan kebetulan):** step "VERIFY" di loop → "Verifier" Agent. Konsistensi
penamaan ini sengaja dipertahankan supaya kalau juri membaca ulang proposal dan menonton demo
berdampingan, jelas terlihat sebagai satu garis lurus, bukan dua hal yang tidak nyambung.

## 6. Data flow — 3 skenario demo

### Event 1: Regional imbalance (Cianjur → Jakarta)
`Supervisor DETECT` → panggil `/supply` & `/demand` → deteksi surplus Cianjur + shortage
Jakarta → `VERIFY` → panggil `/freshness/evaluate` & `/safety/evaluate` untuk batch kandidat →
`OPTIMIZE` → panggil `/cost/safe-delivered` untuk tiap kandidat → `DECIDE` → Verifier
mengaudit → tampil di Recommendation Feed → SPPG Head/SPPG Nutritionist approve → `/actions/execute` → tulis
ke SAP mock (purchase order) → `LEARN` (update Memory untuk siklus berikutnya)

### Event 2: Price anomaly
`Supervisor DETECT` → panggil `/price/deviation` → deviasi > threshold → `TRACE` → panggil
`/evidence/fuse` untuk konteks tambahan → status "Procurement price deviation detected —
review required" (bukan tuduhan fraud) → masuk approval queue

### Event 3: Safety disruption (temperature excursion)
`Supervisor DETECT` (via webhook/polling sensor mock) → `VERIFY` panggil `/safety/evaluate`
→ hasil FAIL untuk batch Cianjur → batch otomatis dikeluarkan dari kandidat (tool-level,
bukan keputusan LLM) → `OPTIMIZE` ulang dengan kandidat tersisa (Bogor) → Verifier audit →
rekomendasi baru muncul di feed, log lama tetap terlihat di Agent Activity Log (transparansi
koreksi diri)

## 7. Keamanan (Security Architect view)

- Semua endpoint backend butuh JWT valid; role (`sppg_head` / `sppg_nutritionist` / `bgn_monitor`) di-embed di
  token, dicek di setiap endpoint sensitif
- SPPG Head/Nutritionist hanya bisa lihat/approve untuk `location_id` miliknya; `bgn_monitor` read-only lintas lokasi
- Kredensial AWS (Bedrock/AgentCore) disimpan di `.env`, tidak pernah di-commit — `.env.example`
  jadi template
- Mock SAP tidak punya kredensial nyata — clearly labeled sebagai simulasi di response header
  (`X-Data-Source: MOCK`) supaya tidak tertukar dengan data asli kalau nanti diganti SAP nyata
- Rate limiting dasar di endpoint publik-facing (kalau demo diakses dari luar)

## 8. Log keputusan teknis (ADR ringkas)

| # | Keputusan | Alternatif dipertimbangkan | Kenapa ini yang dipilih |
|---|---|---|---|
| 1 | Strands SDK, bukan LangGraph/CrewAI | LangGraph, CrewAI | Strands = SDK resmi AWS, paling natural jalan di AgentCore, lebih ringan untuk timeline 3-4 minggu |
| 2 | 1 Supervisor + tool deterministik, bukan 9 agent LLM terpisah | 9 agent LLM saling panggil | 9x biaya/latensi, tidak menyelesaikan masalah "hitung salah" (LLM tetap tidak reliable untuk aritmatika), lebih sulit dipastikan reliable untuk live demo |
| 3 | Verifier Agent tambahan | Tanpa verifier, andalkan tool-grounding saja | Tool-grounding menyelesaikan "hitung salah", tapi tidak menyelesaikan "salah baca hasil tool" — Verifier menutup gap itu |
| 4 | AgentCore Observability sebagai sumber Agent Activity Log | Bikin logging custom sendiri | Lebih otentik (trace asli, bukan dikarang), dan langsung menjawab syarat juri "clear autonomous multi-step reasoning" |
| 5 | Postgres tunggal untuk semua data | Pisah OLTP vs analytics DB | Skala MVP kecil (10 lokasi), tidak perlu kompleksitas tambahan |
| 6 | Next.js + shadcn/ui | Plain React, Vue | Ekosistem skill Hermes (`frontend-design`, `ui-ux-pro-max`) paling matang untuk stack ini |
| 7 | SAP diakses lewat adapter interface (`SAPDataProvider`) sejak Sprint 1, bukan hardcode mock | Hardcode mock langsung di endpoint, refactor nanti kalau perlu real SAP | Proposal yang membuat kita lolos finalist SUDAH menyebut AWS for SAP MCP Server sebagai konektivitas SAP kita — harus siap dinyalakan tanpa refactor kalau diminta juri/panitia. Lihat §9 |

## 9. Dual-mode SAP Connectivity — Mock ↔ AWS for SAP MCP Server (siap-switch)

### Kenapa ini bukan penambahan scope, tapi menunaikan proposal

Proposal yang sudah lolos finalist secara eksplisit menyatakan: *"Konektivitas teknis
dimungkinkan oleh AWS for SAP MCP Server, yang mencapai general availability pada Bedrock
AgentCore per Mei 2026 dan memungkinkan agent membaca serta memperbarui purchase order,
material, dan dokumen keuangan SAP melalui protokol OData/MCP secara aman."* — ini sudah
tertulis, bukan klaim baru. MVP memakai mock karena tidak ada tenant SAP nyata di fase
development; begitu diberi akses (trial SAP kompetisi atau permintaan juri), kita **menunaikan**
apa yang sudah ditulis, bukan menambah sesuatu yang di luar proposal.

### Cara kerja switch (harus benar-benar cuma config, bukan rewrite)

```
SAP_MODE=mock        → factory.py mengembalikan MockSAPProvider
                        (baca dari sap_mock_material_stock, sap_mock_purchase_orders di Postgres)

SAP_MODE=aws_mcp      → factory.py mengembalikan AWSforSAPMCPProvider
                        (panggil AWS for SAP MCP Server → SAP tenant nyata via OData)
```

Tidak ada kode di `core/`, `api/`, atau agent (`agent/supervisor_agent.py`) yang berubah.
Semua business logic (Safe Delivered Cost, safety constraint, balancing) memanggil
`SAPDataProvider` interface yang sama — itu murni inovasi kita, bukan sesuatu yang SAP sediakan,
jadi tidak tersentuh sama sekali oleh switch ini.

### Langkah eksekusi kalau diminta juri/panitia (task list siap pakai — lihat `Roadmap.md` Sprint 5)

1. Provisioning AWS for SAP MCP Server dari AWS Marketplace/console, arahkan ke tenant SAP
   trial kompetisi (bukan tenant fiktif)
2. Setup kredensial via **AgentCore Identity** (bukan hardcode API key) — ini juga menaikkan
   stretch goal S4-07 di `Roadmap.md` jadi wajib, bukan opsional lagi
3. Implementasi `AWSforSAPMCPProvider` — mapping field sesuai `docs/Skill.md` §8 (real SAP
   field mapping, sudah disiapkan)
4. Jalankan `test_sap_integration_contract.py` — WAJIB lolos untuk kedua provider sebelum
   dianggap selesai, membuktikan tidak ada regresi di business logic
5. Ganti `SAP_MODE=mock` → `SAP_MODE=aws_mcp` di `.env`, restart, demo ulang Event 1-3 dengan
   data SAP nyata

### Framing kalau juri bertanya langsung

Lihat `../IDEA.md` bagian "Framing: Mock vs Real SAP" untuk talking points siap pakai.
