# MealChain Guardian 2.0 — Dokumen Menyeluruh

Satu berkas untuk memahami proyek ini dari ujung ke ujung: masalah yang
diselesaikan, komponen yang berjalan, data yang dipegang, aturan yang ditegakkan,
angka yang terukur, dan batas kemampuannya hari ini.

| Hal | Nilai |
|---|---|
| Repo | `E:\hackathon\HackathonAWS\mealchain-guardian` |
| Branch / HEAD | `feature/db-modes-demo-coverage` / `9019eb1` (443 commit) |
| Waktu ukur | **29 Oktober 2026, 11.12 WIB** — `docs/state-snapshot.md` (dihasilkan `scripts/snapshot_state.py`, baca-saja) |
| Backend | FastAPI + SQLAlchemy async + Alembic; 187 berkas Python, 46.742 baris di `backend/app` |
| Frontend | Next.js 14 (App Router) + React Query + Tailwind; 91 komponen, 244 berkas uji, 47.504 baris di `app/`+`components/`+`lib/` |
| API | **35 modul router**, **87 path / 89 operasi** (`backend/openapi.json`, drift-tested) |
| Basis data | PostgreSQL; **25 tabel** di schema `public` (23 domain + `alembic_version` + `ledger_meta`) |
| Migrasi | **39 berkas**, head `044_receipt_scoring` |
| Uji | **311 berkas backend**, **244 berkas frontend** |
| Versi dokumen | 1.0 — menggantikan angka di `docs/MEALCHAIN_GUARDIAN_LENGKAP.md` (26 Okt 2026) |

> **Kejujuran data.** Seluruh baris di database berasal dari penyemai demo
> (`origin='seed'`/`'demo'`) atau dari `mock-sap`. Tidak ada koneksi keluar ke
> SAP, PIHPS, sensor, atau laporan lapangan. Jangan menyebutnya "data
> operasional nyata" di depan siapa pun.

> **Kejujuran keadaan kerja.** Working tree saat dokumen ini ditulis memuat
> 144 perubahan (97 `M`, 43 `??`, 4 `D`) karena beberapa sesi bekerja paralel di
> mesin yang sama. Dokumen ini menjelaskan **kode yang ada di disk**, bukan
> hanya yang sudah di-commit.

---

## 0. Cara memakai dokumen ini

| Pertanyaan | Bagian |
|---|---|
| Sistem ini untuk apa, dan apa yang bukan urusannya | 1 |
| Apa saja yang berjalan, di port berapa | 2 |
| Bagaimana satu keputusan bergerak dari usul sampai diterima | 3 |
| Di folder mana kode apa | 4 |
| Tabel apa saja yang ada, dan jebakan relasinya | 5 |
| Siapa boleh apa, dan berapa approval yang dibutuhkan | 6 |
| Status apa yang mungkin, dan gerbangnya | 7 |
| Angka mana yang dihitung kode, bukan model | 8 |
| Agen: berapa, memakai LLM atau tidak, apa batasnya | 9 |
| Endpoint apa yang tersedia | 10 |
| Layar menyajikan apa, seberapa segar | 11 |
| KPI dihitung bagaimana, nilainya berapa | 12 |
| Kenapa angka demo bergerak saat presentasi | 13 |
| Keamanan dan apa yang belum layak produksi | 14 |
| Apa yang sudah diuji, dengan hasil apa | 15 |
| Batas kemampuan (kalimat yang tidak boleh diucapkan) | 16 |
| Risiko dan pekerjaan terbuka | 17 |
| Perintah operasional (nyalakan, verifikasi, bangun ulang) | 18 |
| Dokumen lain | 19 |
| Istilah | 20 |

---

## 1. Ringkasan produk

MealChain Guardian adalah **lapisan keputusan** untuk rantai pasok pangan
institusional (SPPG/BGN): mendeteksi ketidakseimbangan pasokan antar wilayah,
menilai keamanan pangan per batch, menghitung biaya kiriman yang aman,
mengusulkan tindakan, dan menjaga jejak audit sampai ke buktinya.

Yang **bukan** urusannya: menjadi sistem pencatatan. Pemesanan, stok, dan
eksekusi pengadaan tetap milik sistem sumber — SAP S/4HANA modul MM dalam
rancangan, `mock-sap` dalam demo ini.

Tiga akar masalah yang disasar, dan wujudnya di aplikasi:

| Akar masalah | Wujud konkret |
|---|---|
| Mismatch pasokan antar wilayah | `POST /balance/analyze` → keputusan transfer, peta saldo, rute |
| Visibilitas terfragmentasi (harga, mutu, suhu, dokumen) | `/suppliers`, `/batches`, `evidence/fuse`, kartu "Hari Ini" |
| Nilai yang bergantung waktu (kesegaran, masa layak, 4 jam) | `freshness/evaluate`, CCP, gerbang dispatch, SDC |

Tiga nilai yang dijual, dan bukti kodenya:

| Nilai | Bukti yang bisa ditunjuk |
|---|---|
| Keputusan bisa dipertanggungjawabkan | kuorum empat mata (`core/approval_matrix.py`), verifier terpisah, `decision_chain`, ledger hash-chain |
| Keamanan pangan tidak bisa dinegosiasikan | `safety_status` per batch, karantina, gerbang eksekusi, CCP per komoditas |
| Pemborosan dan biaya bisa dilacak | KPI Food Loss, Safe Delivered Cost, alokasi surplus, disposal |

Posisi terhadap SAP, satu kalimat: **SAP = sistem sumber dan eksekutor; MealChain
Guardian = lapisan keputusan dan pembuktian di atasnya.**

---

## 2. Peta runtime

Empat container dalam satu jaringan (`mealchain-network`, didefinisikan
`docker-compose.yml`):

| Container | Port host → container | Isi |
|---|---|---|
| `mealchain-backend` | 8000 → 8000 | FastAPI (uvicorn), SQLAlchemy async, Alembic |
| `mealchain-frontend` | 3010 → 3000 | Next.js 14 (App Router), proxy `/api/*` ke backend |
| `mealchain-postgres` | 15432 → 5432 | PostgreSQL + volume `postgres_data` |
| `mealchain-mock-sap` | 8001 → 8001 | Tiruan endpoint SAP (PO, stok material) |

Di luar Compose (opsional, tidak wajib untuk demo lokal):

| Layanan | Lokasi | Fungsi |
|---|---|---|
| Runtime agen | `agent/runtime_server.py` (`BedrockAgentCoreApp`) | Dijalankan di AWS Bedrock AgentCore; menyediakan `/ping` + `/invocations` dari framework, bukan route repo |
| Jembatan Joule (A2A) | `sap-joule/a2a_server` (port 8099) | Menjembatani Joule ke backend/agent; skrip bantu di `scripts/joule-perbaiki*.sh`, `tunnel_watchdog.py` |

Variabel `.env` yang menentukan perilaku (nilai, bukan rahasia):

| Variabel | Nilai terukur | Arti |
|---|---|---|
| `DEMO_SESSION_ENFORCE` | `true` | Tanpa sesi demo aktif, semua POST/PUT/PATCH/DELETE → **409** |
| `DEMO_SESSION_MINUTES` / `MAX_MINUTES` | `120` / `120` | Umur bawaan dan plafon absolut |
| `JWT_EXPIRE_MINUTES` | `720` | Umur token; nilai `.env` dijepit kode (`api/auth.py`) |
| `WORKER_AGENT_MODE` | `advisory` | 7 worker boleh memakai model untuk narasi, tidak boleh mengubah status/blokir |
| `AGENT_REVIEW_MODE` | `local` | Reviewer/verifier dipanggil lokal (`services/agent_review_local.py`) |
| `MULTI_AGENT_REVIEW` | `true` | Jalur supervisor + verifier aktif |
| `SAP_*_MODE` (PO, stok, BP, material doc, product master) | `mock` | Adapter SAP yang aktif = tiruan |

Tidak ada worker latar, scheduler, Redis, atau message broker. Tidak ada proses
yang berjalan sendiri: DETECT terjadi hanya saat endpoint/tombol dipanggil, dan
kedaluwarsa sesi dinilai malas saat ada request.

---

## 3. Arsitektur dan perjalanan satu keputusan

### 3.1 Lapisan

```
Browser (Next.js, konsol satu halaman 11 tab)
   │  fetch /api/* (proxy Next → backend)
   ▼
FastAPI  backend/app
   ├── api/            35 modul router, 89 operasi HTTP
   ├── services/       47 modul: kpi, agenda, sesi demo, keputusan, ledger,
   │                   procurement, receipt, dossier, supervisor/agent review
   ├── core/           48 modul aturan keras: approval_matrix, safety_gate,
   │                   safe_delivered_cost, commercial_cost, freshness,
   │                   allocation, ranking, price, supplier_exclusion, kpi_period
   ├── models/         SQLAlchemy (23 tabel domain, CHECK + index)
   ├── sap_integration/ mock (aktif) · aws_mcp/odata (stub yang menolak jalan)
   ├── ai_providers/   rantai provider model (primary + fallback)
   └── seed/           seed_data, timeseries, demo_template, demo_activity,
                       demo_extra, demo_kasus_bukti, jakarta_lengkap, dst.
   ▼
PostgreSQL — system of fact untuk keputusan, bukti, dan ledger
```

### 3.2 Satu keputusan, sepuluh langkah

Contoh: transfer penyeimbang Jakarta → Makassar.

1. **DETECT** — `POST /demo/event1` atau `POST /balance/analyze` menemukan
   lokasi surplus dan kekurangan; menulis `decisions` (`proposed`) +
   `agent_traces` tahap `DETECT`.
2. **PREDICT** — kebutuhan dari `demand_records` (deret empiris, bukan model
   terlatih).
3. **OPTIMIZE** — kandidat pemasok disaring `services/supplier_eligibility.py`:
   sertifikat, jarak, karantina, kesegaran, cakupan kota.
4. **DECIDE** — angka deterministik: `safe_delivered_cost`,
   `core/commercial_cost.py`, skor kandidat, alasan penolakan kandidat lain.
5. **VERIFY** — `POST /actions/verify` → `consistent` / `flagged` /
   `unavailable`. `unavailable` memberatkan syarat approval, bukan dilonggarkan.
6. **PROPOSE** — `POST /actions/propose` memindahkan `proposed|verifier_flagged`
   → `pending_approval` dan mengisi `expires_at`.
7. **APPROVAL empat mata** — `POST /actions/approve`; kuorum penuh → `approved`
   (belum ada PO, belum berangkat).
8. **EXECUTE** — `POST /actions/execute` memvalidasi ulang safety, freshness,
   masa layak, kuorum, lalu menulis `batches.dispatched_at`, membuat PO di
   `sap_mock_purchase_orders`, mengisi SDC, menambah blok ledger, status →
   `executed`.
9. **JOURNEY** — status truk **dihitung** (`core/journey.py`), tidak disimpan.
10. **RECEIVE** — `POST /receipts` + approve/reject; batch gagal uji bisa
    dikarantina (`POST /batches/{id}/quarantine`). **LEARN** mencatat iterasi
    `repropose` sebagai jejak — skor keandalan pemasok **tidak** diperbarui
    otomatis, hanya dinormalisasi saat dibaca (`core/reliability.py`).

---

## 4. Struktur kode

### 4.1 Backend (`backend/app`, 187 berkas, 46.742 baris)

| Folder | Isi (terukur) |
|---|---|
| `api/` | 35 modul router: `decisions`, `actions`, `kpi`, `agenda`, `batches`, `suppliers`, `supplier_exclusions`, `supplier_routes`, `receipts`, `waste`, `surplus`, `ledger`, `demo`, `demo_session`, `admin`, `auth`, `balance`, `price`, `demand`, `evidence`, `freshness`, `logistics`, `safety`, `cost`, `dossier`, `procurement`, `compliance`, `quarantine`, `events/*`, `sap`, `integrations`, `agent`, `health` |
| `services/` | 47 modul — antara lain `kpi_service`, `agenda_service`, `demo_session`, `demo_template_reset`, `demo_procurement_orchestrator`, `po_document`, `po_realization`, `receipt_gate`, `receipt_value`, `dossier_service`, `decision_packet`, `audit_facts`, `supplier_eligibility`, `supplier_procurement`, `event1_orchestrator`, `event2_service`, `event3_service`, `scenario_generator`, `ledger_service`, `signing_service`, `agentcore_gateway`, `supervisor_client`, `agent_review_local` |
| `core/` | 48 modul aturan keras — `approval_matrix`, `safety_gate`, `safe_delivered_cost`, `commercial_cost`, `freshness`, `temperature`, `commodity_limits`, `commodity_policy`, `allocation`, `candidate_generation`, `ranking`, `scoring`, `window`, `storage_window`, `delivery_policy`, `gaps`, `price`, `harga_monitor`, `supplier_exclusion`, `supplier_leg`, `supplier_shipping`, `receipt_scoring`, `decision_fingerprint`, `decision_validity`, `evidence_consistency`, `kpi`, `kpi_period`, `reliability`, `geo`, `road_route`, `po_number`, `rate_limit`, `policy_store` |
| `models/` | Tabel + constraint + index (23 domain) |
| `sap_integration/` | `interface`, `mock` (aktif), `aws_mcp`/`odata` (stub yang menolak jalan), `mapping`, `factory` |
| `ai_providers/` | `ai_provider_chain.py`, `model_registry.py` (primary + `fallback_1..9`) |
| `agent_tools/` | `registry.py`, `gateway_config.json` — alat yang diekspos ke agent/gateway |
| `seed/` | `seed_data`, `timeseries`, `demo_template`, `demo_activity`, `demo_extra`, `demo_kasus_bukti`, `jakarta_lengkap`, `demo_kpi_riwayat`, `demo_credentials`, `demo_sapu_lokasi` |

Migrasi: **39 berkas**, head `044_receipt_scoring`; terbaru yang menyentuh
kepatuhan: `042_ledger_append_only`, `043_least_privilege_app`,
`044_receipt_scoring`.

### 4.2 Frontend (`frontend`, 91 komponen, 244 berkas uji, 47.504 baris)

| Bagian | Isi |
|---|---|
| `app/page.tsx` | konsol satu halaman, **11 tab** (dua di antaranya bersyarat peran) |
| `components/` | papan per domain: `KPIDashboard`, `FoodSafetyBoard`, `SupplierBoard`, `TodayDashboard`, `DemoControlPanel`, `AgentTraceViewer`, peta/rute, dossier keputusan |
| `lib/` | pemformatan & aturan tampilan (`today`, `kpi`, `food-safety`, `supplier-pins`, `agenda`, `nav`, `settings`) |
| `lib/hooks/` | hook React Query per domain (keputusan, KPI, saldo, rute, sesi, …) |
| `tests/` | 244 berkas (vitest + testing-library) |

### 4.3 Agen & integrasi

| Folder | Isi |
|---|---|
| `agent/` | `orchestrator.py`, `supervisor_agent.py`, `registry.py`, `tools.py`, `contracts.py` (`AgentFinding`/`AgentRun`), `telemetry.py`, `runtime_server.py`, `deploy_agentcore.py`, `hierarchy.json`, `prompts/` |
| `agent/workers/` | 7 worker: `supply`, `demand`, `freshness`, `safety`, `price`, `logistics`, `evidence` (+ `verifier.py`, `reasoner.py`, `base.py`, `sumber.py`) |
| `agent/prompts/workers/` | 7 prompt markdown, satu per worker |
| `sap-joule/` | `a2a_server` (jembatan Joule), `joule/`, dokumentasi, skrip perbaikan tunnel |
| `infra/` | `vps/` (rencana deploy VPS, dipilih owner), aset deploy |
| `scripts/` | `snapshot_state.py`, `smoke_e2e.py`, `ledger_anchor.py`, `provision_agentcore_gateway.py`, `probe_agentcore_gateway.py`, gate F3/F6/F7, `semai-demo.sh`, `siapkan_role_app.py` |
| `verify/` | `invariants.spec.json` + `verify_stack.py` (gate invarian data/HTTP) |

---

## 5. Model data

### 5.1 Volume tabel (snapshot 29 Okt 2026 11.12 WIB)

| Tabel | Baris | Tabel | Baris |
|---|---:|---|---:|
| `supply_records` | 5.240 | `decisions` | 49 |
| `price_signals` | 5.933 | `decision_evidence` | 61 |
| `demand_records` | 1.369 | `agent_traces` | 109 |
| `menu_plans` | 660 | `approvals` | 21 |
| `delivery_events` | 210 | `batch_receipts` | 5 |
| `batches` | 133 | `supplier_exclusions` | 2 |
| `disposal_events` | 80 | `demo_sessions` | 6 |
| `ledger_blocks` | 3.841 | `sap_mock_purchase_orders` | 17 |
| `locations` | 10 | `sap_mock_material_stock` | 40 |
| `commodities` | 4 | `commodity_policies` | (policy per komoditas) |
| `suppliers` | 60 | `road_routes` | 53 |
| `users` | 7 | `ledger_meta`, `alembic_version` | 1 masing-masing |

Rincian keadaan:

| Kelompok | Isi terukur |
|---|---|
| Keputusan | 49 total — `pending_approval` 27 · `rejected` 9 · `executed` 6 · `verifier_flagged` 4 · `proposed` 1 · `approved` 1 · `review_only` 1; **31 terbuka** |
| Batch & mutu | `pass` 110 · `needs_verification` 18 · `fail` 3 · `pending` 2; karantina 1; kedaluwarsa <48 jam 14 |
| Pemasok | 60 — sertifikat `hygiene` 35 · `haccp` 17 · `none` 8; eksklusi `active` 1 · `proposed` 1 |
| Kiriman (cakupan Jakarta) | 13 rute — 12 berjalur, 1 tanpa jalur; tahap `belum_berangkat` 4 · `di_jalan` 2 · `sudah_tiba` 6 · `tidak_diketahui` 1 |
| Ledger | 3.841 blok, `valid=true`, arsip 3.743, yatim 0, generasi 108, jangkar ketinggian 978 cocok |
| PO mock SAP | 17 (`confirmed` 15, `submitted` 2), nilai total Rp190.099.434 |

Komoditas: **ayam, beras, telur, wortel**. Lokasi (10): Bandung, Bogor, Cianjur,
Jakarta, Makassar, Medan, Palembang, Semarang, Surabaya, Yogyakarta.

> Angka ini bergerak: setiap build ulang menambah blok ledger (generasi naik),
> dan jam kejadian mengikuti `datetime.now()` saat build. Yang relatif tetap
> adalah **jumlah** baris; yang bergeser adalah stempel waktu dan arsip ledger.

### 5.2 Aturan yang ditegakkan database

- **`origin`** pada tabel fakta hanya menerima `'seed'` dan `'demo'` (CHECK).
  Jalur `live`/`scheduled` butuh migrasi nilai ketiga — belum ada.
- **Satu keputusan = satu approval per akun** (unique index) → pelanggaran 409,
  bukan 500.
- **Satu sesi demo aktif** (`uq_demo_sessions_satu_aktif`).
- **Status keputusan** dibatasi CHECK (tujuh nilai, §7.1).
- **Setiap keputusan wajib punya ≥ 1 `agent_traces`** (gate invarian).
- **Setiap keputusan `rejected` wajib punya approval negatif.**
- **PO demo** tidak boleh `ordered_quantity <= 0` dan tidak boleh `MAT-UMUM`.
- **SDC keputusan = jumlah komponen `cost_breakdown`** (selisih 0).
- **Ledger**: tiap blok menyimpan `prev_hash` + `payload_hash`; trigger
  `ledger_blocks_no_mutation` dan `ledger_blocks_no_truncate` menolak
  UPDATE/DELETE/TRUNCATE (migrasi `042`). Catatan jujur: role DB `mealchain`
  **masih** memegang privilege `UPDATE`/`DELETE`/`TRUNCATE`, jadi yang menahan
  adalah trigger, bukan privilege — superuser atau `ALTER TABLE ... DISABLE
  TRIGGER` tetap bisa membuka. `GET /ledger/verify` membuktikan **rantai hash
  utuh**, bukan ketahanan terhadap admin DB.

### 5.3 Hubungan yang sering disalahpahami

| Hal | Kenyataan di skema |
|---|---|
| `delivery_events` per lokasi? | Tidak ada `location_id`; lokasi diturunkan lewat `menu_plans.location_id` |
| Status perjalanan truk | Tidak ada kolomnya; dihitung `core/journey.py` dari `dispatched_at` + `road_routes.duration_s` |
| Status keamanan batch | Kolom `safety_status`; tidak pernah di-override agent/model |
| Kutipan harga | `price_signals` punya `supplier_id`; beberapa pemasok pada jam yang sama itu wajar |
| Bukti keputusan | `decision_evidence` menyimpan tipe bukti + `is_consistent`; kelengkapan dihitung terhadap approval pertama |
| Pemasok tambahan | Tidak ada. Builder hanya membaca direktori; residu lokasi/pemasok uji (`F9-*`, `@uji-*.local`) dibersihkan dan dijaga tes (`test_demo_sapu_lokasi_asing.py`) |

---

## 6. Peran dan wewenang

Tiga peran, **7 akun** aktif: `sppg_head` 3 (Jakarta, Bandung, Surabaya),
`sppg_nutritionist` 3, `bgn_monitor` 1.

| Peran | Boleh | Tidak boleh |
|---|---|---|
| `sppg_head` | Approval, eksekusi, penerimaan, tab Demo Control | Mengelola pengguna/lokasi (milik `bgn_monitor`) |
| `sppg_nutritionist` | Approval (wajib berpasangan), verifikasi keamanan pangan | Eksekusi tanpa pasangan |
| `bgn_monitor` | Membaca seluruh dashboard, KPI, agent log; **mengelola pengguna & lokasi** (`/admin/*`, tab Pengaturan) | Approval/eksekusi (bukan `APPROVER_ROLES`) |

Kuorum (`core/approval_matrix.py`):

| Verdict verifier | Tipe keputusan | Syarat |
|---|---|---|
| `consistent` | administrasi (eksklusi/restorasi pemasok) | 1 approval: `sppg_head` **atau** `sppg_nutritionist` |
| `flagged`/`unavailable` | administrasi | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |
| apa pun | operasional (transfer, pengadaan, safety, harga) | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |

Aturan tambahan: satu penolakan menggugurkan kuorum; approval dari lokasi lain
tidak dihitung saat eksekusi; kuorum penuh hanya berarti `approved` — PO dan
keberangkatan lahir di langkah `execute`.

Kredensial demo:

- Sumber tunggal: `backend/app/seed/demo_credentials.py` atau
  `DEMO_PASSWORD_<ROLE>` di `.env`. Tidak ada kata sandi di bundel klien.
- `GET /auth/demo-login` membuka email **dan** sandi hanya bila `DEMO_MODE` dan
  `DEMO_LOGIN_AUTOFILL` aktif; di instalasi nyata jawabannya `{enabled:false}`.
- `GET /auth/demo-accounts` menuntut token `bgn_monitor` (tanpa token 401,
  peran lain 403).

---

## 7. State machine

### 7.1 Keputusan

```
POST /decisions ─────────────► proposed
/actions/repropose ──────────► proposed (pengganti, supersedes_id)
/actions/propose ────────────► pending_approval    [dari proposed|verifier_flagged]
/actions/verify (FLAGGED) ───► verifier_flagged    [CONSISTENT tidak mengubah status]
/actions/approve (tolak) ────► rejected            [wajib komentar]
kuorum terpenuhi ────────────► approved
/actions/execute ────────────► executed            [kuorum + verdict + belum kedaluwarsa]
Event 2 (gangguan keamanan) ─► review_only         [tidak bisa approve/execute]
```

Gerbang `execute` (semua ditegakkan kode): `review_only` ditolak lebih dulu ·
`executed` → 409 (idempoten) · verdict wajib `consistent`/`flagged` ·
`expires_at` lewat → 409 · status harus `pending_approval`/`verifier_flagged`/
`approved` · kuorum diperiksa global **dan** per `target_location_id` · safety,
freshness, dan masa layak batch divalidasi ulang.

### 7.2 Pengiriman (dihitung, bukan disimpan)

| State | Syarat |
|---|---|
| `belum_berangkat` | `dispatched_at IS NULL` |
| `di_jalan` | sudah berangkat, `dispatched_at + duration_s` belum lewat |
| `sudah_tiba` | sekarang ≥ ETA |
| `tidak_diketahui` | sudah berangkat, durasi rute belum ada — tidak diklaim "di jalan" |

Batch yang ditahan (safety, karantina, `usable_until`, suhu) tidak diberi
`dispatched_at`, sehingga tidak pernah tampil sebagai truk di peta.

### 7.3 Sesi demo

```
kosong ──START──► active (≤120 menit) ──expired──► kosong
                     │  ▲
                  EXTEND┘ (tidak bisa melewati plafon absolut)
                     │
                     └──END──► kosong (baris origin='demo' milik sesi dibuang)
```

Kedaluwarsa dinilai **malas** saat ada request, bukan oleh cron. Tidak ada
pembekuan jam: `anchor_now` dicatat, waktu berjalan normal. Tanpa sesi aktif,
semua tulisan → 409; bacaan tetap jalan.

### 7.4 Batch, karantina, PO, penerimaan

| Objek | Alur |
|---|---|
| Batch mutu | `pass` · `needs_verification` · `fail` · `pending` → `fail`/tahanan bisa dikarantina (1 baris karantina saat ini) |
| PO mock SAP | `draft` → `submitted` → `confirmed`; tiap PO tertaut `decision_id` atau ditandai impor SAP |
| Penerimaan | `menunggu` → `approved`/`rejected`; approve memicu skor penerimaan (`core/receipt_scoring.py`) dan nilai diterima (`services/receipt_value.py`) |

---

## 8. Mesin deterministik (angka tidak pernah dari model)

| Keluaran | Modul | Sifat |
|---|---|---|
| Safe Delivered Cost + rincian komponen | `core/safe_delivered_cost.py`, `core/commercial_cost.py` | deterministik; SDC = jumlah komponen |
| Skor & peringkat kandidat | `core/ranking.py`, `core/scoring.py`, `core/candidate_generation.py` | deterministik |
| Gerbang keselamatan | `core/safety_gate.py`, `core/batch_eligibility.py`, `core/temperature.py` | deterministik, tidak bisa dilonggarkan |
| Kesegaran & masa layak | `core/freshness.py`, `core/storage_window.py`, `core/delivery_policy.py` | deterministik |
| Alokasi surplus & kekurangan | `core/allocation.py`, `core/gaps.py`, `core/window.py` | deterministik |
| Anomali harga | `core/price.py`, `core/harga_monitor.py` | deterministik |
| Eksklusi pemasok | `core/supplier_exclusion.py` | deterministik, butuh approval |
| KPI | `core/kpi.py`, `services/kpi_service.py` | SQL agregat, `method_version` dicantumkan |
| Nomor PO, cap keputusan | `core/po_number.py`, `core/decision_fingerprint.py` | deterministik (idempoten) |

Konsekuensi yang harus diucapkan saat demo: **kg, rupiah, skor, verdict, dan
status reproducible; teks narasi dan latensi tidak.**

---

## 9. Lapisan agen

Sembilan peran: **7 worker** + **supervisor** + **verifier**.

| Peran | Berkas | Sifat |
|---|---|---|
| 7 worker (`supply`, `demand`, `freshness`, `safety`, `price`, `logistics`, `evidence`) | `agent/workers/*.py` + `agent/prompts/workers/*.md` | pemeriksa deterministik; model hanya memperkaya narasi |
| Supervisor | `agent/supervisor_agent.py`, `backend/app/api/agent.py` | menyusun jawaban/ringkasan lintas domain |
| Verifier | `agent/workers/verifier.py`, `services/agent_review_local.py` | menilai konsistensi keputusan; verdict `consistent`/`flagged`/`unavailable` |

Saklar dan batasnya:

| Aspek | Keadaan |
|---|---|
| `WORKER_AGENT_MODE` | `off` (default repo) · `advisory` (nilai di stack demo ini) — model tidak pernah menghitung angka |
| Status & blokir | tetap milik pemeriksa deterministik; model tidak bisa melonggarkan (`status=guarded`) |
| Anti-karang | ringkasan model yang memuat angka di luar fakta ditolak utuh (`status=rejected`); perbandingan berbasis **nilai**, jadi `1.080,0` = `1080.00` |
| Model gagal/timeout/JSON rusak | temuan deterministik dipertahankan (`unavailable`/`invalid`), tidak pernah 500 |
| Verdict verifier tanpa model | `unavailable` → syarat approval memberat, bukan dilonggarkan |
| Jejak | `facts.reasoning` menyimpan status, provider, rationale, latensi (teks bersatuan) — **bukan** angka yang boleh disitasi |
| `agent_traces` | **tidak** punya kolom provider/slot model; jangan mengklaim atribusi `[primary]/[fallback_N]` per langkah |

Integrasi (dari `GET /integrations/status`, 29 Okt 2026):

| Komponen | Kategori |
|---|---|
| SAP AI Core (SAP-RPT-1.6) | kontrak diuji |
| Mock SAP (`sap_integration`) | kontrak diuji |
| AgentCore Runtime | terkonfigurasi |
| AgentCore Gateway | terkonfigurasi |
| AgentCore Memory | tersedia, belum dipakai aplikasi |
| Observability | gagal-tertutup |
| AWS for SAP MCP | belum dimulai |

Catatan: AgentCore tidak tersedia di region Jakarta; region yang dipakai
`ap-southeast-1`. Jalur ke Joule memakai A2A (`sap-joule/a2a_server`), bukan
konektor SAP satu-klik.

---

## 10. API

**87 path / 89 operasi** (`backend/openapi.json`, dijaga tes drift).

| Domain | Endpoint utama |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `GET /auth/demo-login`, `GET /auth/demo-accounts` (admin) |
| Keputusan | `GET/POST /decisions`, `GET /decisions/{id}` + `/chain` `/traces` `/approval-summary` `/dossier` `/compliance` `/audit-facts` `/ledger` `/packet`, `POST /decisions/{id}/review` |
| Aksi | `POST /actions/propose` `/verify` `/approve` `/execute` `/repropose`, `POST /actions/purchase-orders/{po}/approve` |
| Pasokan & saldo | `GET /supply/{loc}/{kom}`, `GET /balance/map`, `GET /balance/{loc}/{kom}`, `POST /balance/analyze`, `POST /balance/recommend` |
| Harga | `GET /price/{loc}/{kom}`, `GET /price/quotes/{loc}/{kom}`, `GET /price/monitor`, `POST /price/deviation`, `POST /events/price-anomaly` |
| Permintaan | `GET /demand/{loc}/{kom}`, `GET /demand/forecast/{loc}/{kom}` |
| Keamanan | `POST /safety/evaluate`, `GET /batches`, `GET /batches/{id}`, `POST /batches/{id}/quarantine`, `POST /events/safety-disruption` |
| Pemasok | `GET /suppliers`, `GET /supplier-routes`, `GET /supplier-exclusions`, `GET /supplier-exclusions/context/{id}`, `POST /supplier-exclusions/proposals`, `POST /supplier-exclusions/{id}/restore` |
| Penerimaan | `GET /receipts`, `GET /receipts/menunggu`, `POST /receipts`, `POST /receipts/{id}/approve\|reject` |
| Surplus & limbah | `GET /surplus/allocations`, `GET /surplus/regions`, `GET /waste/summary`, `POST /waste/disposals` |
| Biaya & logistik | `POST /cost/safe-delivered`, `POST /logistics/estimate` |
| Bukti & kesegaran | `POST /evidence/fuse`, `POST /freshness/evaluate` |
| Pengukuran | `GET /kpi` (`periode=today\|7d\|1bulan` atau `start`+`end`), `GET /agenda?start&end` |
| Audit | `GET /ledger/verify` |
| SAP | `GET /sap/purchase-orders`, `/summary`, `GET /sap/purchase-orders/{po}/pdf` |
| Pengadaan | `GET /procurement/summary` |
| Admin | `GET/PATCH /admin/users`, `GET/PATCH /admin/locations` |
| Demo | `GET /demo/session`, `POST /demo/session/start\|extend\|end`, `GET /demo/data-status`, `/demo/preview`, `POST /demo/template/rebuild`, `POST /demo/agent/run`, `POST /demo/hari-ini`, `POST /demo/refresh`, `POST /demo/event1`, `/demo/timeseries` |
| Agen | `POST /agent/supervisor/ask`, `GET /agent/supervisor/health`, `GET /demo/agent/last-run` |
| Integrasi | `GET /integrations/status`, `GET /health` |

Kontrak galat: **409** (tanpa sesi demo, kuorum belum lengkap, sudah dieksekusi,
kedaluwarsa, duplikat approval), **422** (periode tidak sah, campuran
`periode`+`start`), **401/403** (token/peran).

---

## 11. Frontend

11 item navigasi; dua bersyarat peran.

| Tab | Isi | Syarat |
|---|---|---|
| Hari Ini | Agenda harian: menu, kiriman, limbah, pasokan, harga, batch kedaluwarsa, tugas CCP, kartu keputusan | semua |
| Overview | Saldo per lokasi/komoditas, peta, rute | semua |
| Rekomendasi | Keputusan yang perlu tindakan (+ jumlah di label) | semua |
| Decision & Evidence | Rantai keputusan, bukti, approval, eksekusi, dossier | semua |
| Keamanan Pangan | CCP per batch, partisi status, ketersediaan bukti | semua |
| Surplus & Limbah | Alokasi surplus, pembuangan, biaya angkut | peran SPPG |
| Pemasok | Daftar pemasok, sertifikat, eksklusi/usulan, detail `?pemasok=`, ringkasan jarak | semua |
| Agent Log | Jejak agen per putaran | semua |
| KPI & Kualitas Agen | 8 metrik + sampel kualitas | semua |
| Pengaturan | Pengguna & lokasi (`/admin/*`) | `bgn_monitor` |
| Demo Control | Siapkan/bangun ulang data, jalankan agen, akhiri sesi | approver |

Pola data: **polling**, tanpa WebSocket/SSE.

| Data | Interval |
|---|---|
| Daftar & detail keputusan | 5 detik |
| Saldo peta | 5 detik |
| Posisi truk | 15 detik (`MAP_TRUCK_POLL_MS`) |
| KPI | 20 detik |
| Kueri umum (Hari Ini dsb.) | 60 detik |
| Agenda | stale 5 menit |
| Pemasok | 5 menit |

Aturan tampilan yang mengikat:

- Nilai tidak diketahui ditulis **"—"**, tidak pernah diganti 0.
- Pil periode mengikuti jendela yang diminta, bukan nama bulan.
- Tile Keamanan Pangan adalah partisi saling lepas (aman / gagal uji / perlu
  verifikasi / ditahan / kedaluwarsa / belum diuji).
- Klaim penutupan kekurangan dihitung per komoditas.
- Label pasokan berbunyi "Stok layak · N kiriman" — bukan "sedang mengirim".
- Error fetch detail keputusan ditampilkan, tidak ditelan.

---

## 12. KPI

Delapan metrik (`GET /kpi`, `method_version` `kpi-2026.10.28`). **Cakupan
mengubah angkanya**, jadi sebutkan cakupannya setiap kali mengutip.

Cakupan **nasional** (`bgn_monitor`, 29 Okt 2026 11.13 WIB):

| KPI | Hari ini | 7 hari | 1 bulan |
|---|---|---|---|
| Meal Continuity Rate | no_data | 99,97 % (60) | 99,97 % (70) |
| Avoidable Food Loss | no_data | 0,46 % (20) | 0,46 % (20) |
| Regional Imbalance Resolution | 0,00 % (5) | 16,67 % (6) | 16,67 % (6) |
| Safe Delivered Cost | no_data | no_data | no_data |
| Procurement Price Deviation | 2,69 % (60) | 2,69 % (60) | 2,69 % (60) |
| Decision Time | no_data (5 DETECT) | no_data (6) | no_data (6) |
| Evidence Completeness | 0,00 % (1) | 0,00 % (2) | 0,00 % (2) |

Cakupan **Jakarta** (`sppg_head`, akun `sppg.head@demo.local`, 29 Okt 2026 11.22 WIB):

| KPI | Hari ini | 7 hari | 1 bulan |
|---|---|---|---|
| Meal Continuity Rate | no_data | 100,00 % (6) | 100,00 % (7) |
| Avoidable Food Loss | no_data | 0,56 % (2) | 0,56 % (2) |
| Regional Imbalance Resolution | 0,00 % (2) | 33,33 % (3) | 33,33 % (3) |
| Safe Delivered Cost | no_data | no_data | no_data |
| Procurement Price Deviation | 3,21 % (13) | 3,21 % (13) | 3,21 % (13) |
| Decision Time | no_data (2 DETECT) | no_data (3) | no_data (3) |
| Evidence Completeness | no_data (0) | 0,00 % (1) | 0,00 % (1) |

`docs/state-snapshot.md` mencatat cakupan Jakarta — itulah sebabnya angkanya
berbeda dari tabel nasional di atas; keduanya benar untuk penyebutnya
masing-masing.

Membaca tabel ini dengan benar:

- `no_data` adalah **keadaan sah** ketika penyebut kosong — bukan 0 dan bukan
  tanda rusak. UI menulis "—" beserta alasannya.
- `Safe Delivered Cost` kosong karena penyebutnya "keputusan yang punya PO";
  keputusan ber-PO pada jendela ini belum ada sesudah bangun ulang terakhir.
- `Decision Time` kosong walau DETECT ada: belum ada ACT yang committed di
  jendela itu.
- `Evidence Completeness` 0,00 % berarti bukti belum lengkap **sebelum**
  approval pertama pada sampel yang ada — bukan berarti tidak ada bukti.

Kontrak periode ditegakkan server: `periode=today|7d|1bulan` atau `start`+`end`,
maksimum 366 hari, campuran keduanya → 422. Envelope respons memuat `period`
yang benar-benar dipakai, `computed_at`, `data_source`, dan `method_version`.

Dua keputusan pemilik yang masih terbuka: Regional Imbalance mengecualikan baris
`demo_case`, dan SDC memakai keberadaan PO (bukan status `executed`).

---

## 13. Arsitektur demo (mengapa angka bergerak)

### 13.1 Tiga lapis data

| Lapis | Stempel | Umur | Dibuang saat sesi berakhir? |
|---|---|---|---|
| Kanonik | `origin='seed'`, `demo_session_id=NULL` | permanen | tidak |
| Template (cetakan) | `origin='demo'` + `demo_session_id=<sesi sentinel cetakan>` | permanen | tidak |
| Sesi (adonan) | `origin='demo'` + `demo_session_id=<sesi aktif>` | ≤120 menit | ya |

Tampilan default kosong. **Siapkan data demo** membangun template lebih dulu,
baru membuka sesi — urutan ini wajib, karena sesi yang habis di tengah
pembangunan membuat penyapu menghapus baris yang baru ditulis.

Dua jalur bangun menghasilkan volume berbeda, dan itu bukan bug:

| Jalur | Cakupan | Angka yang dihasilkan |
|---|---|---|
| `mulai_dengan_template` (template saja) | template inti | lebih kecil (mis. 36 keputusan) |
| `bangun_ulang` (tombol refresh di Demo Control) | + deret waktu + aktivitas + pelengkap cakupan (`seed/demo_extra.py`) | lebih besar (mis. 49–61 keputusan) |

Karena itu yang sah dikutip adalah **snapshot bertanggal**, bukan angka dari
ingatan sesi.

### 13.2 Angka yang bergerak

| Aksi | Yang berubah |
|---|---|
| Approve | `approvals`, status keputusan, kuorum di UI |
| Execute | batch berangkat, PO bertambah, SDC, blok ledger, Decision Time/SDC |
| Penerimaan | `batch_receipts`, stok SAP tiruan, skor penerimaan |
| Bangun ulang | isi kembali ke jumlah awal, **tetapi** ledger bertambah (arsip generasi) dan jam kejadian di-anchor ulang |
| Waktu berjalan | "x menit lalu", posisi truk (interpolasi), sisa masa layak, jendela KPI melebar |

### 13.3 Dua jangkar waktu yang belum seragam

- Kejadian operasional (batch, keputusan, PO, jejak) dihitung relatif
  `datetime.now()` saat build → ikut jam dinding.
- Deret 65 hari (pasokan, harga, menu, permintaan, pengiriman, limbah) dipatok
  `2026-09-01 .. 2026-11-04 19.00` (`app/seed/timeseries.py`) → tidak ikut jam.

Konsekuensi terukur: **520 baris `supply_records` dan 580 baris `price_signals`
bertanggal masa depan**. KPI tidak terpengaruh (jendela berakhir di `now`),
tetapi label "tercatat hari ini" sedikit melebihkan. Setelah **5 November 2026**
deret berhenti: "hari ini" tak punya baris, KPI dan agenda kosong tanpa error.

### 13.4 Jebakan operasional (yang sudah terbukti menggigit)

1. **Jangan menjalankan `pytest` pada database demo.** Tes mem-purge baris
   `origin='demo'`. Pakai DB klon (`mealchain_gate`, `mealchain_suite`).
2. **Jangan membangun ulang dari dua tempat sekaligus.** Id batch bersifat
   deterministik; dua build bersamaan menabrak `batches_pkey`. Terukur 29 Okt
   2026: `python -m app.seed.demo_template` dan `POST /demo/template/rebuild`
   yang berjalan saat sesi lain juga membangun → `duplicate key value violates
   unique constraint "batches_pkey"`. Lock `_KUNCI` di
   `services/demo_template_reset.py` hanya berlaku dalam satu proses.
   Jalur aman: `POST /demo/template/rebuild` (in-process, 409 bila sibuk),
   setelah memastikan tidak ada build lain.
3. **Sesudah build, tunggu ~60 detik lalu hitung ulang.** Angka yang turun
   sendiri berarti sesi lain menutup sesi/membangun ulang di bawah kita
   (terukur: 133 batch/49 keputusan → 78/0 dalam 45 detik).
4. **Menekan "Siapkan data demo" memakan ±40–90 detik** — jangan di detik
   terakhir sebelum presentasi.
5. **Backup sebelum operasi destruktif**:
   `docker exec mealchain-postgres pg_dump -U mealchain -d mealchain | gzip > <scratch>.sql.gz`.

---

## 14. Keamanan dan kepatuhan

| Aspek | Keadaan terukur |
|---|---|
| Auth | Bearer JWT (`api/auth.py`); `.env` memakai `JWT_EXPIRE_MINUTES=720`, nilai dijepit kode ke rentang aman; peran & lokasi ikut klaim |
| Otorisasi | Peran + cakupan lokasi; approver dibatasi `APPROVER_ROLES`; `/admin/*` hanya `bgn_monitor` |
| Penjaga tulisan | Sesi demo (`DEMO_SESSION_ENFORCE=true`) — satu-satunya penjaga POST/PUT/PATCH/DELETE (409) |
| `DEMO_MODE` | **Bukan gerbang router.** Nilainya hanya dipakai untuk membuka akun demo satu-klik; mematikannya tidak menutup `/demo/*` |
| CORS | Dikonfigurasi dari `CORS_ORIGINS`; default hanya origin UI |
| Ledger | Hash-chain di Postgres + trigger penolak mutasi + jangkar berkas (`/data/anchors/ledger-checkpoint.json`, ketinggian 978 cocok). Append-only ditegakkan **trigger**, privilege role masih lebar |
| Rate limit | `core/rate_limit.py` pada endpoint tertentu |
| Rahasia (SEC-01) | `.env` tidak dilacak git, tetapi nilainya harus dianggap pernah bocor → **rotasi wajib** sebelum publik |
| Kredensial demo (SEC-02) | Ditutup: tidak ada kata sandi di bundel klien; `demo-login` hanya mengisi otomatis bila flag demo menyala |
| Dependensi (SEC-04) | `next@14.2.14` dan `maplibre-gl@4.7.1` berstatus critical, `postcss` high; perbaikan menuntut migrasi mayor (rencana di `docs/audit/SECURITY.md`) |
| Pemisahan hak DB | Migrasi `043_least_privilege_app.py` menyiapkan role aplikasi; verifikasi privilege masih perlu diulang tiap deploy |

---

## 15. Pengujian dan verifikasi

Hasil yang **diukur pada 29 Oktober 2026**:

| Lapis | Hasil | Cara |
|---|---|---|
| Lint backend (berkas yang disentuh) | `ruff check` bersih (4 berkas) | `ruff check app/seed/demo_template.py app/seed/seed_data.py tests/conftest.py tests/test_demo_sapu_lokasi_asing.py` |
| Backend, gate Pemasok + demo (klon `mealchain_gate`) | **77 lulus / 1 gagal** (56,5 dtk) | `pytest -q` pada 8 berkas supplier+demo |
| Frontend, area Pemasok | **131 tes / 7 berkas lulus** | `npx vitest run tests/supplier-* tests/shipment-*` |
| Frontend, suite penuh | 2.695 lulus / 5 gagal | `npx vitest run` (5 gagal di berkas yang sedang disunting sesi lain) |
| TypeScript | 7 error, semuanya di berkas uji sesi lain | `npx tsc --noEmit` |
| ESLint | 0 masalah | `npx next lint` |
| End-to-end demo | `POST /demo/template/rebuild` → 200 OK dalam **86,1 detik** | panggilan API nyata |

Kegagalan yang tersisa dan artinya:

| Tes | Gejala | Sebab sebenarnya |
|---|---|---|
| `test_suppliers_api.py::test_expired_batch_is_not_counted` | `assert 3 > 3` pada prasyarat "ada lot yang lewat tenggat" | Semua lot pemasok itu masih `usable_until` depan setelah build baru — prasyarat data, bukan regresi kode |
| 5 tes frontend (`agent-trace-viewer`, `food-safety`, `radius-scale-css`, `safety-export`) | asersi tampilan | Berkas sedang diubah sesi paralel |
| 2 tes `test_tool_contracts.py` (catatan 26 Okt) | `assert 0 > 0` | Klon tidak punya deret waktu demo; pulihkan deret dulu |

Riwayat yang sah dikutip sebagai pembanding (26 Okt 2026, DB klon, kode
working tree): **1.581 lulus / 2 gagal / 28 skip**, dan gate invarian
`verify/invariants.spec.json` **59 PASS / 0 FAIL / 1 SKIP**.

Yang **belum** diverifikasi dan tidak boleh diklaim: uji beban, `axe-core`,
`pip-audit`/`bandit`, `next build` pada mesin bersih, verifikasi visual manual
seluruh 11 tab, dan matriks Playwright UI penuh pada putaran ini.

---

## 16. Batas kemampuan hari ini

| Klaim yang menggoda | Kenyataan |
|---|---|
| "Real-time" | Tidak. Sumber = template demo; layar menyegar lewat polling 5–60 detik; tak ada scheduler/SSE/WebSocket |
| "Terhubung SAP" | Tidak. Adapter aktif `mock`; `aws_mcp`/`odata` adalah stub yang menolak jalan |
| "Agen berjalan sendiri" | Tidak. DETECT hanya saat endpoint/tombol dipanggil |
| "Data eksternal" | Tidak. Semua dari penyemai; PIHPS hanya nama sumber pada baris referensi |
| "Multi-agent otonom" | Belum. 7 worker punya lapisan narasi model, tetapi **read-only dan advisory**; tidak ada worker yang boleh approve/execute |
| "Forecast" | Deret empiris (`core/forecasting_fallback.py`), bukan model terlatih |
| "Bukti diterima regulator" | Belum. Ledger hash-chain + bukti internal, tanpa sertifikasi pihak ketiga |
| "Immutable secara database" | Sebagian. Trigger menolak mutasi, tetapi role aplikasi masih memegang privilege dan admin DB bisa melepas trigger |

Untuk benar-benar real-time dibutuhkan empat hal yang belum ada: penulis data
nyata (`origin='live'` + migrasi), konektor sumber (SAP/PIHPS/laporan suhu),
penjadwal, dan dorongan ke layar. Skema keputusan, state machine, dan KPI tidak
perlu diubah.

---

## 17. Risiko dan pekerjaan terbuka

| # | Hal | Dampak | Status |
|---|---|---|---|
| 1 | Dua jangkar waktu (§13.3) | label "hari ini" melebihkan; deret berhenti 5 Nov 2026 | Perbaiki penyemai (jendela relatif) |
| 2 | Build bersamaan menabrak `batches_pkey` (§13.4) | rebuild gagal 500 saat dua sesi bekerja | Pakai jalur in-process + cek diam dulu |
| 3 | `Safe Delivered Cost` no_data di semua jendela | KPI unggulan kosong saat presentasi | Perlu keputusan: jangkar waktu SDC |
| 4 | Regional Imbalance mengecualikan `demo_case` | Metrik tidak bergerak saat kartu demo dieksekusi | Menunggu keputusan pemilik |
| 5 | SDC memakai keberadaan PO, bukan `executed` | PO batal tetap terhitung | Menunggu keputusan |
| 6 | SEC-01 rotasi kredensial | Tidak layak produksi | Tindakan pemilik |
| 7 | SEC-04 CVE `next`/`maplibre`/`postcss` | Tidak layak produksi | Migrasi mayor terpisah |
| 8 | 5 tes frontend + 7 error `tsc` di berkas sesi lain | Gate penuh belum hijau | Selesaikan setelah sesi paralel selesai |
| 9 | `DEMO_MODE` bukan gerbang router | Menutup router tidak berefek | Diketahui; gerbang sesi yang berlaku |
| 10 | Privilege DB pada `ledger_blocks` | Admin DB bisa melepas trigger | REVOKE + role pemilik tabel terpisah |
| 11 | AgentCore Memory belum dipakai aplikasi; Observability gagal-tertutup | Klaim "terintegrasi penuh" tidak sah | Ditandai di `/integrations/status` |

---

## 18. Perintah operasional

```bash
# 1. Menyalakan stack
cd /e/hackathon/HackathonAWS/mealchain-guardian
docker compose up -d
curl -s localhost:8000/health

# 2. Angka resmi (baca-saja, menulis docs/state-snapshot.{json,md})
python scripts/snapshot_state.py

# 3. Membangun ulang data demo (SAAT TIDAK ADA SESI LAIN YANG MEMBANGUN)
#    lewat API, bukan CLI, supaya lock in-process berlaku
curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"sppg.head@demo.local","password":"<DEMO_PASSWORD_SPPG_HEAD>"}'
curl -s -X POST localhost:8000/demo/template/rebuild -H "Authorization: Bearer ***"

# 4. Backup / restore
docker exec mealchain-postgres pg_dump -U mealchain -d mealchain | gzip > /tmp/mealchain-$(date +%H%M).sql.gz
# restore: hentikan backend → drop schema → psql < dump → start backend

# 5. Uji tanpa mengotori DB demo
docker exec mealchain-postgres psql -U mealchain -d postgres -c "CREATE DATABASE mealchain_gate"
docker exec mealchain-postgres bash -lc "pg_dump -U mealchain mealchain | psql -U mealchain -d mealchain_gate"
docker exec -w /app -e DATABASE_URL="postgresql+asyncpg://mealchain:***@postgres:5432/mealchain_gate" \
  mealchain-backend python -m pytest -q tests/test_suppliers_api.py

# 6. Verifikasi ledger
curl -s localhost:8000/ledger/verify -H "Authorization: Bearer ***"
```

Gerbang kualitas sebelum menyatakan "hijau": `ruff check app tests` ·
`npx tsc --noEmit` · `npx next lint` · `npx vitest run` · `pytest -q` di DB klon
· `python verify/verify_stack.py verify/invariants.spec.json`.

---

## 19. Peta dokumen

| Dokumen | Isi |
|---|---|
| `docs/MEALCHAIN_GUARDIAN_MENYELURUH.md` | **Berkas ini** — gambaran menyeluruh, angka 29 Okt 2026 |
| `docs/MEALCHAIN_GUARDIAN_LENGKAP.md` | Versi sebelumnya (26 Okt 2026); rincian naratif bagian agen masih relevan |
| `docs/state-snapshot.md` / `.json` | **Sumber angka resmi**; dihasilkan `scripts/snapshot_state.py` |
| `AGENTS.md` | Aturan kerja agen, urutan baca, larangan perintah destruktif |
| `IDEA.md`, `docs/PRD.md`, `Rules.md` | Masalah, posisi produk, aturan keras |
| `docs/Architecture.md` | Arsitektur, ADR, jalur SAP/AWS, fallback |
| `docs/Schema.md` | Skema tabel dan kontrak tipe |
| `docs/kamus-kpi-dan-state-machine.md` | Rumus KPI yang benar-benar dijalankan |
| `docs/demo/alur-demo-juri.md`, `docs/demo/panduan-demo-singkat.md` | Alur demo babak demi babak |
| `docs/audit/SECURITY.md` | Status SEC-01/02/04 + rencana upgrade |
| `verify/invariants.spec.json` | Pemeriksaan data/HTTP otomatis |
| `agent/README-deploy.md`, `agent/LANGKAH-DEPLOY-MANUAL.md` | Deploy runtime AgentCore |
| `sap-joule/README.md` | Jembatan Joule (A2A) |

---

## 20. Glosarium

| Istilah | Arti |
|---|---|
| SPPG | Satuan Pelayanan Pemenuhan Gizi — dapur penyedia makanan program MBG |
| BGN | Badan Gizi Nasional |
| Batch | Kumpulan bahan pangan dengan identitas, suhu, kesegaran, dan status uji |
| CCP | Critical Control Point — titik kendali keamanan pangan (suhu, FIFO/FEFO, thawing) |
| SDC | Safe Delivered Cost — biaya kiriman yang aman per pengiriman, dijumlahkan dari komponen |
| Empat mata | Dua peran berbeda harus menyetujui sebelum eksekusi |
| Verifier | Penilai independen: `consistent` / `flagged` / `unavailable` |
| Ledger | Rantai blok hash sebagai bukti audit |
| Kanonik | Keadaan hasil builder (`origin='seed'`) — bukan keadaan DB yang sudah dipakai tes |
| Template / adonan | Baris `origin='demo'` milik sesi cetakan (bertahan) vs milik sesi aktif (dibuang saat sesi berakhir) |
| `no_data` | Keadaan sah KPI ketika penyebut kosong — bukan 0 |
| Dossier | Paket bukti satu keputusan: rantai, bukti, approval, jejak, ledger |
| `method_version` | Penanda versi rumus KPI (`kpi-2026.10.28`) supaya angka bisa dibandingkan antar-waktu |

---

_Dokumen ini disusun dari pengukuran langsung terhadap repo, API yang hidup, dan
`docs/state-snapshot.md` 29 Oktober 2026 11.12 WIB. Bila angka di sini berbeda
dengan snapshot yang lebih baru, snapshot yang berlaku._