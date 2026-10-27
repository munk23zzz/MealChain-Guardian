# MealChain Guardian 2.0 — Dokumen Lengkap

Dokumen ini menjelaskan sistem MealChain Guardian secara menyeluruh: apa yang
dikerjakannya, bagaimana ia dibangun, data apa yang dipegangnya, aturan bisnis
yang ditegakkan, sampai batas kemampuannya hari ini.

Semua angka di sini **diukur**, bukan dikutip dari ingatan sesi. Waktu ukur dan
perintah pengukurnya dicantumkan supaya siapa pun bisa mengulang.

| Hal | Nilai |
|---|---|
| Waktu ukur keadaan data | 26 Oktober 2026, 22.34 WIB (`docs/state-snapshot.json`) — sesudah perbaikan SDC/PO/ledger/provenance |
| Waktu ukur KPI | 26 Oktober 2026, 22.35 WIB (`GET /kpi?periode=today\|7d\|1bulan`) |
| Repo | `E:\hackathon\HackathonAWS\mealchain-guardian` |
| Branch / HEAD | `feature/db-modes-demo-coverage` / `5885810` + 4 commit perbaikan sesudahnya |
| Migrasi Alembic | 33 berkas, head `033_indeks_fk_hilang` |
| Ukuran kode | backend `app/` 32.455 baris · frontend `app+components+lib+tests` 56.044 baris |
| Berkas uji | 240 berkas backend · 167 berkas frontend |
| API | 32 modul router · 76 path · 78 operasi (`backend/openapi.json`) |
| Tabel | 22 tabel domain + `alembic_version` + `ledger_meta` |

> **Catatan kejujuran data.** Seluruh isi database berasal dari penyemai demo
> (`origin='seed'`/`'demo'`) atau `mock-sap`. Tidak ada koneksi keluar ke SAP,
> PIHPS, atau sensor. Jangan menyebutnya "data operasional nyata" atau "data
> eksternal aktual" di depan siapa pun.

---

## 0. Cara memakai dokumen ini

| Pertanyaan | Bagian |
|---|---|
| Sistem ini untuk apa, dan apa yang bukan urusannya | 1 |
| Bagaimana komponen berjalan bersama | 2, 3 |
| Di folder mana kode apa | 4 |
| Tabel apa saja yang ada, dan apa artinya | 5 |
| Siapa boleh apa | 6 |
| Bagaimana satu keputusan bergerak dari usul ke kiriman | 3.2, 7 |
| Agen bekerja dengan tahap apa | 8 |
| Endpoint apa yang tersedia | 9 |
| Layar menyajikan apa, dan seberapa segar | 10 |
| Angka KPI dihitung bagaimana | 11 |
| Mengapa angka berubah/tidak berubah saat demo | 12 |
| Keamanan dan risikonya | 13 |
| Apa yang sudah diuji, apa yang belum | 14 |
| Batas kemampuan | 15 |
| Apa yang perlu diputuskan pemilik produk | 16 |
| Dokumen lain yang harus dibaca | 17 |

---

## 1. Ringkasan

MealChain Guardian adalah **lapisan keputusan** untuk rantai pasok pangan
institusional (SPPG/BGN): ia mendeteksi ketidakseimbangan pasokan, menilai
keamanan pangan, menghitung biaya kiriman yang aman, mengusulkan tindakan, dan
menjaga jejak audit keputusan itu sampai ke bukti.

Yang **bukan** urusannya: menjadi sistem pencatatan. Pemesanan, stok, dan
eksekusi pengadaan tetap milik sistem sumber (SAP S/4HANA modul MM dalam
rencana; pada demo ini disimulasikan `mock-sap`). MealChain tidak menulis
angka safety-critical dengan LLM — semua skor, batas, dan gerbang keputusan
adalah kode deterministik.

Tiga nilai yang dijual, dan di mana ia terlihat di aplikasi:

| Nilai | Wujud konkret di aplikasi |
|---|---|
| Keputusan bisa dipertanggungjawabkan | Empat mata approval, verifier terpisah, `decision_chain`, ledger hash-chain |
| Keamanan pangan tidak bisa dinegosiasikan | `safety_status` per batch, karantina, gerbang eksekusi, CCP |
| Pemborosan dan biaya bisa dilacak | KPI Food Loss, Safe Delivered Cost, surplus allocation, disposal |

### 1.1 Angka kunci (keadaan terukur, 26 Okt 2026 22.34 WIB)

| Entitas | Jumlah |
|---|---|
| Batch | **120** (beras 31 · wortel 30 · telur 30 · ayam 29); `pass` 100 · `needs_verification` 14 · `fail` 3 (1.280 kg) · `pending` 3 · karantina 1 · kedaluwarsa <48 jam 8 |
| Keputusan | **36** (30 `origin='demo'` + 6 `origin='seed'`) — 15 `pending_approval` · 9 `rejected` · 5 `executed` · 4 `verifier_flagged` · 1 `approved` · 1 `proposed` · 1 `review_only` (19 terbuka) |
| Approval / bukti / jejak | **21 / 51 / 85** |
| Pemasok / lokasi / komoditas | **60 / 10 / 4** (HACCP 17 · hygiene 35 · tanpa sertifikat 8) |
| Rencana menu | 660 |
| Deret | pasokan 5.240 · harga 5.924 · permintaan 1.360 · pengiriman 190 · pembuangan 80 |
| Blok ledger | **2.034** (valid, 1.960 arsip, 74 blok entitas tertaut, 0 yatim; **+74 setiap build**) |
| Rute jalan | 53 baris cache; 12 kiriman Jakarta (3 di jalan · 8 tiba · 0 belum berangkat · 1 tanpa geometri) |
| PO mock SAP | **16** (14 `confirmed` · 2 `submitted`) — 4 tertaut keputusan, 12 baris impor SAP tanpa `decision_id` |
| Penerimaan | **2** (keduanya `menunggu`) |
| Kartu 24 jam Jakarta | **11** |
| Sesi demo | 11 baris riwayat, 1 aktif pada snapshot |

> **Angka ini bergerak.** Ledger bertambah 74 blok setiap build/rebuild, dan
> jam kejadian mengikuti `datetime.now()`. Yang tetap adalah **jumlah** baris;
> yang bergeser adalah stempel waktu dan arsip ledger.

---

## 2. Peta runtime

Empat container, satu jaringan Docker (`mealchain-network`):

| Container | Port host | Isi |
|---|---|---|
| `mealchain-backend` | 8000 | FastAPI + SQLAlchemy async + Alembic |
| `mealchain-frontend` | 3010 → 3000 | Next.js 14.2.14 (App Router) |
| `mealchain-postgres` | 15432 → 5432 | PostgreSQL, volume persisten |
| `mealchain-mock-sap` | 8001 | Tiruan endpoint SAP (PO, stok) |

Layanan di luar Compose: jembatan Joule `sap-joule/a2a_server` (:8099) dan
runtime agen `agent/runtime_server.py` (AWS AgentCore).

Konfigurasi yang menentukan perilaku demo (`.env`, tidak ikut di-commit):

| Variabel | Nilai sekarang | Arti |
|---|---|---|
| `DEMO_SESSION_ENFORCE` | `true` | Tanpa sesi demo aktif, semua POST/PUT/PATCH/DELETE → 409 |
| `DEMO_SESSION_MINUTES` | `120` | Umur sesi bawaan |
| `DEMO_SESSION_MAX_MINUTES` | `120` | Plafon absolut START maupun EXTEND |
| `DEMO_MODE` | `True` | Mengaktifkan akun demo satu-klik (`GET /auth/demo-accounts`). **Bukan** gerbang router demo — penjaga tulis tetap sesi demo (lihat §16) |
| `sap_provider` | `mock` | Adapter SAP aktif = tiruan |

`docker-compose.yml` mendefinisikan empat service itu; tidak ada worker,
scheduler, Redis, atau message broker. Tidak ada proses yang berjalan sendiri
di latar belakang.

---

## 3. Arsitektur dan alur satu keputusan

### 3.1 Lapisan

```
Browser (Next.js, satu konsol 11 tab)
   │  fetch /api/* → proxy Next ke backend
   ▼
FastAPI (backend/app)
   ├── api/          32 modul router, 78 operasi HTTP (76 path)
   ├── services/     logika bisnis: kpi, agenda, kandidat, eligibility,
   │                 journey, demo_session, ledger, event1..3
   ├── core/         aturan keras: approval_matrix, kpi_period, safety_gate,
   │                 hash (ledger), security (JWT), pagination
   ├── models/       SQLAlchemy 22 tabel
   ├── sap_integration/  adapter: mock (aktif) · aws_mcp/odata (stub jujur)
   └── seed/         init master, timeseries, demo_template, demo_extra
   ▼
PostgreSQL — system of fact untuk keputusan, bukti, ledger
```

### 3.2 Perjalanan satu keputusan (contoh: transfer penyeimbang)

1. **DETECT** — `POST /demo/event1` (atau `/balance/analyze`) menemukan lokasi
   surplus dan kekurangan. Tertulis `decisions` (status `proposed`) +
   `agent_traces` tahap `DETECT`.
2. **PREDICT/OPTIMIZE** — kebutuhan dihitung dari `demand_records`; kandidat
   pemasok disaring (`supplier_eligibility`): sertifikat, jarak, karantina,
   kesegaran.
3. **DECIDE** — angka deterministik: `safe_delivered_cost`, skor kandidat,
   alasan penolakan kandidat lain.
4. **VERIFY** — `/actions/verify` → `consistent`, `flagged`, atau `unavailable`.
5. **Propose** — `/actions/propose` memindahkan `proposed|verifier_flagged` →
   `pending_approval` dan mengisi `expires_at`.
6. **Approval empat mata** — `/actions/approve`; kuorum penuh → `approved`
   (belum berangkat).
7. **Execute** — `/actions/execute` memvalidasi ulang safety/freshness, menulis
   `batches.dispatched_at`, membuat PO di `sap_mock_purchase_orders`, mengisi
   SDC, menambah blok ledger, status → `executed`.
8. **Journey** — status truk **dihitung**, bukan disimpan (lihat §7.2).
9. **Receive** — `/receipts` + approve/reject menutup siklus; batch gagal uji
   bisa dikarantina.
10. **LEARN** — mencatat iterasi `repropose` sebagai langkah `LEARN`. Skor
    keandalan pemasok **tidak** diperbarui otomatis; hanya dinormalisasi saat
    dibaca (`core/reliability.py`).

---

## 4. Struktur kode

### 4.1 Backend (`backend/app`, 32.455 baris)

| Folder | Isi |
|---|---|
| `api/` | 32 modul router: `decisions`, `actions`, `kpi`, `agenda`, `batches`, `suppliers`, `supplier_exclusions`, `supplier_routes`, `receipts`, `waste`, `surplus`, `ledger`, `demo`, `demo_session`, `admin`, `auth`, `balance`, `price`, `demand`, `evidence`, `freshness`, `logistics`, `safety`, `sap`, `integrations`, `quarantine`, `events/*`, `health` |
| `services/` | `kpi_service`, `agenda_service`, `demo_session`, `demo_template_reset`, `supplier_eligibility`, `journey`, `event1/2/3`, `ledger_service`, `forecasting` |
| `core/` | `approval_matrix`, `kpi_period`, `journey`, `safety_gate`, `commodity_limits`, `safe_delivered_cost`, `hash`, `security`, `config`, `pagination` |
| `models/` | 22 tabel SQLAlchemy + constraint + index |
| `sap_integration/` | `interface`, `mock` (aktif), `aws_mcp`/`odata` (stub yang menolak jalan), `mapping`, `factory` |
| `seed/` | `seed_data`, `timeseries`, `demo_template`, `demo_activity`, `demo_extra`, `demo_kasus_bukti`, `demo_kpi_riwayat`, `suppliers_demo` |

### 4.2 Frontend (`frontend`, 56.044 baris TS/TSX termasuk tes)

| Bagian | Isi |
|---|---|
| `app/page.tsx` | konsol satu halaman, ±2.027 baris, 11 tab |
| `components/` | papan per domain (`KPIDashboard`, `FoodSafetyBoard`, `SupplierBoard`, `TodayDashboard`, `DemoControlPanel`, `AgentTraceViewer`, …) |
| `lib/` | pemformatan (`today`, `kpi`, `food-safety`, `supplier-pins`, `agenda`), aturan tampilan, tipe |
| `lib/hooks/` | hook React Query (keputusan, KPI, saldo, rute, hari ini, sesi, …) |
| `tests/` | 167 berkas uji, 1.822 tes (vitest) |

### 4.3 Basis data

22 tabel domain, tanpa tabel riwayat bayangan: perubahan status dicatat di
`approvals`, `agent_traces`, `decision_evidence`, dan `ledger_blocks`.

---

## 5. Model data

### 5.1 Kelompok tabel (jumlah baris = snapshot 22.34 WIB)

| Kelompok | Tabel | Peran |
|---|---|---|
| Master | `locations` (10), `commodities` (4), `suppliers` (60), `users` (7) | Acuan yang tidak dihapus saat reset demo |
| Pasokan | `supply_records` (5.240), `price_signals` (5.924), `demand_records` (1.360) | Fakta harian per lokasi+komoditas |
| Operasi | `menu_plans` (660), `delivery_events` (190), `batches` (120), `disposal_events` (80), `road_routes` (53) | Rencana, pengiriman, batch fisik, limbah, geometri rute |
| Keputusan | `decisions` (36), `approvals` (21), `decision_evidence` (51), `agent_traces` (85) | Inti nilai: usul, persetujuan, bukti, jejak |
| Keamanan & pemasok | `supplier_exclusions` (2), `batch_receipts` (2) | Eksklusi/usulan pemasok, penerimaan barang |
| Audit | `ledger_blocks` (2.034), `ledger_meta` | Hash-chain append-only |
| SAP tiruan | `sap_mock_purchase_orders` (16), `sap_mock_material_stock` (40) | Cermin dokumen SAP |
| Demo | `demo_sessions` (11, 1 aktif) | Sesi 120 menit, penjaga tulisan |

Komoditas: ayam, beras, telur, wortel.
Lokasi (10): Bandung, Bogor, Cianjur, Jakarta, Makassar, Medan, Palembang,
Semarang, Surabaya, Yogyakarta.

### 5.2 Aturan integritas yang ditegakkan database

- **`origin`** pada tabel fakta hanya menerima `'seed'` dan `'demo'` (CHECK di
  6 tabel). Jalur `live`/`scheduled` butuh migrasi baru — rencana MG memesan
  `034`–`038`, jadi pekerjaan lain mulai **039**.
- **Satu keputusan = satu approval per akun** (unique index migrasi 030);
  pelanggaran → 409, bukan 500.
- **Satu sesi demo aktif** (`uq_demo_sessions_satu_aktif`, migrasi 032).
- **Status keputusan** dibatasi CHECK: `proposed`, `verifier_flagged`,
  `pending_approval`, `approved`, `rejected`, `executed`, `review_only`.
- **Setiap keputusan wajib punya ≥ 1 `agent_traces`.** Dijaga gate invariant;
  pernah gagal untuk 11 keputusan `extra:*` dan sudah diperbaiki 26 Okt 2026.
- **Setiap keputusan `rejected` wajib punya approval negatif.**
- **PO demo** tidak boleh `ordered_quantity <= 0` dan tidak boleh `MAT-UMUM`.
- **SDC keputusan = jumlah komponen `cost_breakdown`** (0 selisih).
- **Ledger append-only**: tiap blok menyimpan `prev_hash` dan `payload_hash`;
  reset menaikkan `generation`, blok lama menjadi arsip.

### 5.3 Hubungan yang sering disalahpahami

| Hal | Kenyataan di skema |
|---|---|
| `delivery_events` per lokasi? | Tidak ada `location_id`; lokasi diturunkan lewat `menu_plans.location_id` |
| Status perjalanan truk | Tidak ada kolomnya; dihitung `journey.py` dari `dispatched_at` + `road_routes.duration_s` |
| Status keamanan batch | Kolom `safety_status` di `batches`; tidak pernah di-override agent |
| Kutipan harga | `price_signals` punya `supplier_id`; beberapa pemasok pada jam sama itu wajar, bukan duplikasi |
| Bukti keputusan | `decision_evidence` menyimpan tipe bukti + `is_consistent`; kelengkapan dihitung terhadap approval pertama |
| Supplier tambahan | Sudah tidak ada. Builder dulu *mengganti nama* satu pemasok untuk contoh em dash, sehingga direktori DB ≠ berkas dan dua pin peta bertumpuk. Sejak 26 Okt 2026 builder hanya membaca; baris residu dihapus → **60 baris, 60 koordinat unik** |

---

## 6. Peran dan wewenang

Tiga peran, 7 baris akun, semuanya aktif: `sppg_head` 3, `sppg_nutritionist` 3,
`bgn_monitor` 1. Akun uji yang dulu dinonaktifkan sudah tidak ada di tabel
(`users` = 7 baris); 21 approval yang ada semuanya berasal dari enam akun demo
(`sppg.head@`, `.bandung@`, `.surabaya@` dan pasangan nutritionist-nya).

| Peran | Boleh | Tidak boleh |
|---|---|---|
| `sppg_head` | Approval, eksekusi, penerimaan, tab Demo Control | Pengelolaan pengguna/lokasi (milik `bgn_monitor`) |
| `sppg_nutritionist` | Approval (wajib berpasangan), verifikasi keamanan pangan | Eksekusi tanpa pasangan |
| `bgn_monitor` | Membaca seluruh dashboard, KPI, agent log; mengelola pengguna & lokasi (`/admin/*`, tab Pengaturan) | Approval/eksekusi (bukan `APPROVER_ROLES`) |

Matriks kuorum (`core/approval_matrix.py`):

| Verdict verifier | Tipe keputusan | Syarat |
|---|---|---|
| `consistent` | administrasi (eksklusi/restorasi pemasok) | 1 approval: `sppg_head` **atau** `sppg_nutritionist` |
| `flagged`/`unavailable` | administrasi | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |
| apa pun | operasional (transfer, pengadaan, safety, harga) | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |

Aturan tambahan: satu penolakan menggugurkan kuorum; approval dari lokasi lain
tidak dihitung saat eksekusi; kuorum penuh hanya berarti `approved` — PO dan
keberangkatan lahir di `execute`.

Kata sandi akun demo **tidak** ada di bundel klien (SEC-02). Sejak 26 Okt 2026
tombol akun demo hanya mengisi email; kata sandi diketik operator dari
`DEMO_PASSWORD_<ROLE>`. `GET /auth/demo-accounts` masih ada untuk skrip/operator
demo, tetapi menuntut Bearer token ber-peran admin (`bgn_monitor`) — tanpa token
401, token non-admin 403 — dan hanya mengeluarkan daftar saat `DEMO_MODE` aktif.
Sumber sandi tetap satu: `backend/app/seed/demo_credentials.py` (atau
`DEMO_PASSWORD_<ROLE>`), bukan JavaScript yang bisa dibaca siapa pun.

---

## 7. State machine

### 7.1 Keputusan

```
POST /decisions ─────────────► proposed
/actions/repropose ──────────► proposed (pengganti, supersedes_id)
/actions/propose ────────────► pending_approval   [dari proposed|verifier_flagged]
/actions/verify (FLAGGED) ───► verifier_flagged   [CONSISTENT tidak mengubah status]
/actions/approve (tolak) ────► rejected           [wajib komentar]
kuorum terpenuhi ────────────► approved
/actions/execute ────────────► executed           [kuorum + verdict + belum kedaluwarsa]
Event 2 (gangguan keamanan) ─► review_only        [tidak bisa approve/execute]
```

Gerbang `execute`: `review_only` ditolak lebih dulu · `executed` → 409
(idempoten) · verdict wajib `consistent`/`flagged` · `expires_at` lewat → 409 ·
status harus `pending_approval`/`verifier_flagged`/`approved` · kuorum diperiksa
global **dan** per `target_location_id` · safety & freshness batch divalidasi
ulang.

### 7.2 Pengiriman (dihitung)

| State | Syarat |
|---|---|
| `belum_berangkat` | `dispatched_at IS NULL` |
| `di_jalan` | sudah berangkat, `eta = dispatched_at + duration_s` belum lewat |
| `sudah_tiba` | sekarang ≥ `eta` |
| `tidak_diketahui` | sudah berangkat, durasi rute belum ada — tidak diklaim "di jalan" |

Batch yang ditahan (safety, karantina, `usable_until`, suhu) tidak diberi
`dispatched_at`, sehingga tidak pernah digambar sebagai truk.

### 7.3 Sesi demo

```
kosong ──START──► active (≤120 menit) ──expired──► kosong
                     │  ▲
                  EXTEND┘ (tidak bisa melewati plafon absolut)
                     │
                     └──END──► kosong (baris origin='demo' dibuang)
```

Kedaluwarsa dinilai **malas** saat ada request, bukan oleh cron. Tidak ada
pembekuan jam: `anchor_now` dicatat, waktu berjalan normal. Tanpa sesi aktif,
semua tulisan → 409; bacaan tetap jalan.

---

## 8. Pipeline agen

Tujuh tahap tercatat di `agent_traces.step_name`. Total jejak sekarang **85**.

| Tahap | Yang terjadi | Deterministik? |
|---|---|---|
| DETECT | Menemukan kasus (imbalance, anomali harga, gangguan keamanan) | ya |
| PREDICT | Kebutuhan beberapa hari ke depan | ya (deret/empiris) |
| OPTIMIZE | Memilih kandidat pemasok + rute | ya (skor + gerbang) |
| DECIDE | Menyusun usul, biaya, alasan | ya |
| VERIFY | Verdict `consistent`/`flagged`/`unavailable` | aturan deterministik |
| ACT | Eksekusi setelah approval | ya |
| LEARN | Iterasi ulang setelah penolakan (`repropose`) | ya |

Angka safety-critical — `safe_delivered_cost`, skor, gerbang — tidak pernah
dihitung LLM. Bila Verifier tidak tersedia, statusnya `unavailable` dan
keputusan tidak bisa dieksekusi; nilai kosong tidak diganti 0. `agent_traces`
tidak menyimpan slot model penyedia (primary/fallback), jadi jangan mengklaim
atribusi model per langkah dari tabel itu.

Jejak agen menyimpan **fakta keputusan** (kg, SDC, durasi), bukan teks template.
UI menampilkan kalimat ringkas + lipatan "Data mentah".

---

## 9. API

76 path, 78 operasi (OpenAPI `backend/openapi.json`, drift-tested terhadap kode).

| Domain | Endpoint utama |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `GET /auth/demo-accounts` (admin `bgn_monitor`; hanya mengeluarkan daftar saat `DEMO_MODE` aktif) |
| Keputusan | `GET/POST /decisions`, `GET /decisions/{id}` (+`/chain`, `/traces`, `/approval-summary`, `/dossier`, `/compliance`) |
| Aksi | `POST /actions/propose`, `/verify`, `/approve`, `/execute`, `/repropose` |
| Pasokan & saldo | `GET /supply/{loc}/{kom}`, `GET /balance/map`, `GET /balance/{loc}/{kom}`, `POST /balance/analyze`, `POST /balance/recommend` |
| Harga | `GET /price/{loc}/{kom}`, `GET /price/quotes/{loc}/{kom}`, `POST /price/deviation`, `POST /events/price-anomaly` |
| Permintaan | `GET /demand/{loc}/{kom}`, `GET /demand/forecast/{loc}/{kom}` |
| Keamanan | `POST /safety/evaluate`, `GET /batches`, `GET /batches/{id}`, `POST /batches/{id}/quarantine`, `POST /events/safety-disruption` |
| Pemasok | `GET /suppliers`, `GET /supplier-exclusions`, `GET /supplier-exclusions/context/{id}`, `POST /supplier-exclusions/proposals`, `POST /supplier-exclusions/{id}/restore`, `GET /supplier-routes` |
| Penerimaan | `GET /receipts`, `GET /receipts/menunggu`, `POST /receipts`, `POST /receipts/{id}/approve\|reject` |
| Surplus & limbah | `GET /surplus/allocations`, `GET /waste/summary`, `POST /waste/disposals` |
| Biaya & logistik | `POST /cost/safe-delivered`, `POST /logistics/estimate` |
| Bukti & kesegaran | `POST /evidence/fuse`, `POST /freshness/evaluate` |
| Pengukuran | `GET /kpi` (`periode=today\|7d\|1bulan` atau `start`+`end`), `GET /agenda?start&end` |
| Audit | `GET /ledger/verify` |
| SAP | `GET /sap/purchase-orders`, `GET /sap/purchase-orders/summary`, `GET /sap/purchase-orders/{po}/pdf` |
| Admin | `GET/PATCH /admin/users`, `GET/PATCH /admin/locations` |
| Demo | `GET /demo/session`, `POST /demo/session/start\|extend\|end`, `GET /demo/data-status`, `GET /demo/preview`, `POST /demo/template/rebuild`, `POST /demo/agent/run`, `POST /demo/hari-ini`, `POST /demo/refresh` |
| Integrasi | `GET /integrations/status`, `GET /health` |

Kontrak galat yang sering muncul: **409** (tanpa sesi demo, kuorum belum
lengkap, sudah dieksekusi, kedaluwarsa), **422** (periode tidak sah, mis. `24h`
atau campuran `periode`+`start`), **401/403** (token/peran).

---

## 10. Frontend

11 item navigasi; dua di antaranya bersyarat peran:

| Tab | Isi | Syarat |
|---|---|---|
| Hari Ini | Agenda harian: menu, kiriman, limbah, pasokan, harga, batch kedaluwarsa, tugas CCP, kartu keputusan | semua |
| Overview | Saldo per lokasi/komoditas, peta, rute | semua |
| Recommendations | Daftar keputusan yang perlu tindakan (+ jumlah di label) | semua |
| Decision & Evidence | Rantai keputusan, bukti, approval, eksekusi | semua |
| Keamanan Pangan | CCP per batch, partisi status, ketersediaan bukti | semua |
| Surplus & Limbah | Alokasi surplus, pembuangan, biaya angkut | peran SPPG |
| Pemasok | Daftar pemasok, sertifikat, eksklusi/usulan, detail `?pemasok=` | semua |
| Agent Log | Jejak agen per putaran | semua |
| KPI & Kualitas Agen | 7 KPI, sampel kualitas | semua |
| Pengaturan | Pengguna & lokasi (`/admin/users`, `/admin/locations`) | `bgn_monitor` |
| Demo Control | Siapkan/bangun ulang data, jalankan agen, akhiri sesi | approver |

Pola data dan kesegaran layar (semua **polling**, tidak ada WebSocket/SSE):

| Data | Interval |
|---|---|
| Daftar keputusan | 5 detik |
| Detail keputusan | 5 detik |
| Saldo peta | 5 detik |
| Posisi truk | 15 detik (`MAP_TRUCK_POLL_MS`) |
| KPI | 20 detik |
| Kueri umum (Hari Ini dsb.) | 60 detik |
| Agenda | stale 5 menit |
| Pemasok | 5 menit |

Aturan tampilan yang mengikat:

- Nilai tidak diketahui ditulis **"—"**, tidak pernah diganti 0
  (`frontend/lib/today.ts`).
- Pil periode mengikuti **jendela yang diminta** ("Hari ini · 26 Okt 2026"),
  bukan nama bulan.
- Tile Keamanan Pangan adalah **partisi saling lepas** (aman / gagal uji /
  perlu verifikasi / ditahan / kedaluwarsa / belum diuji).
- Klaim penutupan kekurangan dihitung **per komoditas**, tidak mencampur telur
  dengan beras.
- Label pasokan berbunyi **"Stok layak · N kiriman"** — bukan "sedang
  mengirim", karena status kirim dan stok layak dua hal berbeda.
- Error fetch detail keputusan **ditampilkan**, tidak ditelan.

---

## 11. Tujuh KPI

Definisi lengkap + diskrepansi terhadap `docs/Skill.md` ada di
`docs/kamus-kpi-dan-state-machine.md`. Ringkasnya:

| KPI | Rumus | Jangkar waktu | Kosong → |
|---|---|---|---|
| Meal Continuity | `100 × Σ min(delivered, planned) / Σ planned` | `menu_plans.plan_date` | `no_data` + alasan |
| Avoidable Food Loss | `100 × disposed_kg / (disposed_kg + supply_kg)` | `disposed_at`, `recorded_at` | `no_data` bila tak ada buangan |
| Regional Imbalance | root DETECT vs yang `executed` | `agent_traces.step_at` | `no_data` tanpa DETECT |
| Safe Delivered Cost | `mean(decisions.safe_delivered_cost)` untuk yang punya PO | `po.created_at` | `no_data` bila penyebut kosong |
| Price Deviation | `mean(\|quote − ref\| / ref × 100)` | `price_signals.recorded_at` | kutipan tanpa pasangan dibuang |
| Decision Time | `mean(ACT − DETECT)` untuk ACT committed | `agent_traces.step_at` | `no_data` + coverage |
| Evidence Completeness | `lengkap sebelum approval pertama / keputusan ber-approval` | `approved_at` pertama | `no_data` tanpa approval |

Nilai terukur (lokasi Jakarta, 26 Okt 2026 22.35 WIB, snapshot `36` keputusan):

| KPI | Hari ini | 7 hari | 1 bulan |
|---|---|---|---|
| Meal Continuity | 100,00% (1) | 100,00% (7) | 71,69% (26) |
| Avoidable Food Loss | 0,59% (3) | 0,16% (5) | 0,07% (8) |
| Regional Imbalance | `—` (no_data) | 60,00% (5) | 60,00% (5) |
| Safe Delivered Cost | `—` (no_data) | Rp18.965.818,44 (2) | Rp18.965.818,44 (2) |
| Price Deviation | 2,81% (17) | 3,13% (30) | 3,63% (56) |
| Decision Time | `—` (no_data, 7 DETECT) | 20 menit (2) | 20 menit (2) |
| Evidence Completeness | `—` (no_data) | 66,67% (3) | 66,67% (3) |

Catatan: `Decision Time` "hari ini" kini `no_data` walau ada 7 langkah DETECT —
belum ada ACT yang committed di jendela itu, jadi penyebutnya kosong dan nilainya
ditulis `—`, bukan 0. `Regional Imbalance` "hari ini" juga `no_data` karena
DETECT hari ini belum punya pasangan `executed`.

Kontrak periode ditegakkan server: `periode=today|7d|1bulan` atau `start`+`end`,
maksimum 366 hari, campuran keduanya → 422. Envelope respons memuat `period`
yang benar-benar dipakai, jadi UI tidak menebak.

Dua keputusan pemilik yang masih terbuka: Regional Imbalance mengecualikan baris
`demo_case`, dan SDC memakai keberadaan PO (bukan status `executed`).

---

## 12. Arsitektur demo (mengapa angka bergerak atau tidak)

### 12.1 Dua lapis: cetakan dan adonan

| Lapis | Stempel | Umur | Dibuang saat sesi berakhir? |
|---|---|---|---|
| Data kanonik (snapshot `load_seed`) | `origin='seed'`, `demo_session_id=NULL` | permanen | tidak |
| Template (cetakan) | `origin='demo'` + `demo_session_id=<sesi sentinel cetakan>` | permanen | tidak |
| Sesi (adonan) | `origin='demo'` + `demo_session_id=<sesi aktif>` | ≤120 menit | ya |

Tiga lapis, bukan dua: sejak audit D-04 (26 Okt 2026) penanda beku **bukan** penulisan
ulang `origin`, melainkan stempel ke sesi sentinel `cetakan` (`demo_session.CETAKAN_ID`,
`status='expired'`, `template_version='cetakan'`) yang tidak pernah aktif dan tidak pernah
dihapus pembersih sesi. Konsekuensinya: baris TEMPLATE tetap ber-`origin='demo'` (provenance
jujur) dan yang wajib `demo_session_id IS NULL` adalah baris **kanonik** `origin='seed'` —
invarian itu dijaga gate (`verify/invariants.spec.json`) dan dijaga penjaga ORM
`demo_session.boleh_distempel()`: baris baru hanya distempel bila `origin`-nya benar-benar
`'demo'`. Tanpa aturan itu, "Siapkan data demo" yang berjalan saat sesi aktif menstempel
snapshot kanonik yang ditulis `load_seed` (terukur 27 Okt 2026: 78 batch + 7 keputusan +
40 fakta pasokan).

Tampilan default kosong. Menekan **Siapkan data demo** membangun template lebih
dulu, baru membuka sesi — urutan ini wajib, karena sesi yang habis di tengah
pembangunan membuat penyapu menghapus baris demo yang baru ditulis.

**Baseline yang boleh dikutip adalah snapshot:** 48 keputusan, 125 batch, 28
approval, 61 bukti, 118 jejak, 60 pemasok, 19 PO (12 impor SAP + 7 dari
keputusan), 2.244 blok ledger (27 Okt 2026 10.35 WIB, sesudah bangun ulang lewat
`services/demo_template_reset.bangun_ulang`). Angka ini **tergantung jalur
bangun**, jadi sebutkan jalurnya: `mulai_dengan_template` (template saja)
menghasilkan 36/120/21/51 karena tidak menjalankan pelengkap cakupan
(`seed/demo_extra.py`), sedangkan `bangun_ulang` (tombol refresh di Demo Control)
menambahkan deret waktu + aktivitas + pelengkap sehingga menjadi 48/125/28/61.
Karena itu jumlah demo bergerak mengikuti sesi — hanya snapshot terakhir yang sah
dikutip, bukan angka dari ingatan sesi.

### 12.2 Angka yang bergerak dan yang tidak

| Aksi | Yang berubah |
|---|---|
| Approve | `approvals`, status keputusan, kuorum di UI |
| Execute | batch berangkat, PO bertambah, SDC, blok ledger, Decision Time/SDC |
| Penerimaan | `batch_receipts`, stok SAP tiruan |
| Bangun ulang | isi kembali ke jumlah awal (48/125/28/61), **tetapi** ledger +74 blok (arsip generasi) dan jam kejadian di-anchor ulang |
| Waktu berjalan | "x menit lalu", posisi truk (interpolasi), sisa masa layak, jendela KPI melebar |

### 12.3 Dua jangkar waktu yang belum seragam

- Kejadian operasional (batch, keputusan, PO, jejak) dihitung relatif ke
  `datetime.now()` saat build → **ikut jam dinding**.
- Deret 65 hari (pasokan, harga, menu, permintaan, pengiriman, limbah) dipatok
  `2026-09-01 .. 2026-11-05` (`app/seed/timeseries.py`) → **tidak ikut jam**.

Konsekuensi terukur pada snapshot ini: **720 baris `supply_records` dan 840
baris `price_signals` bertanggal masa depan**. KPI tidak terpengaruh (jendela
berakhir di `now`), tetapi label "tercatat hari ini" sedikit melebihkan. Setelah
5 November 2026 deret berhenti, sehingga "hari ini" tidak punya baris lagi —
KPI dan agenda kosong tanpa error.

### 12.4 Jebakan operasional

- **Jangan** menjalankan `pytest` pada database yang dipakai demo: tes mem-purge
  baris `origin='demo'` (pernah membuat keputusan 48 → 9). Pakai DB klon
  (`mealchain_gate`, `mealchain_idem2`, `mealchain_suite`).
- Sesi demo adalah satu-satunya penjaga tulisan; tanpa sesi, POST → 409
  (baca tetap jalan).
- Menekan "Siapkan data demo" memakan 38–42 detik; jangan dilakukan di detik
  terakhir sebelum presentasi.
- Laporan endpoint `rebuild` kini **sama dengan isi tabel** (bug F7 diperbaiki
  26 Okt 2026 dan dijaga tes integrasi).

---

## 13. Keamanan dan kepatuhan

| Aspek | Keadaan |
|---|---|
| Auth | Bearer JWT (`api/auth.py`), default 30 menit, nilai `.env` dijepit ke rentang aman; peran & lokasi ikut di klaim |
| Otorisasi | Peran + cakupan lokasi; approver dibatasi `APPROVER_ROLES` |
| CORS | Dikonfigurasi dari `CORS_ORIGINS`; default hanya origin UI |
| Ledger | Hash-chain di Postgres; `GET /ledger/verify` → `valid=true`, 2.034 blok (generasi 247), 74/74 blok entitas tertaut, 0 yatim, 1.960 blok arsip |
| Rahasia (SEC-01) | `.env` tidak dilacak git, tetapi nilainya harus dianggap bocor → **rotasi wajib** sebelum publik |
| Kredensial demo (SEC-02) | **Ditutup di kode, diperketat 26 Okt 2026**: tidak ada kata sandi di bundel klien. Tombol login hanya mengisi email; `GET /auth/demo-accounts` menuntut token admin (`bgn_monitor`) dan hanya mengeluarkan daftar saat `DEMO_MODE`; mode non-demo → `enabled:false` |
| Dependensi (SEC-04) | `next@14.2.14` dan `maplibre-gl@4.7.1` critical, `postcss` high; `npm audit fix` tanpa `--force` tidak menyelesaikan apa pun. Perbaikan menuntut Next 16 + maplibre 6 → rencana di `docs/audit/SECURITY.md` |

Mitigasi yang sudah dilakukan: dokumen operasional diberi header snapshot,
perintah pytest destruktif diganti resep DB klon di `AGENTS.md`, sesi demo wajib
(`DEMO_SESSION_ENFORCE=true`) dengan satu sesi aktif, dan kata sandi demo
dihapus dari bundel.

---

## 14. Pengujian dan verifikasi

| Lapis | Hasil terukur | Cara |
|---|---|---|
| Frontend unit/komponen | **1.822 lulus / 167 berkas**; `tsc --noEmit` exit 0; ESLint bersih | `npx vitest run` |
| Backend (berkas yang disentuh) | **20 lulus / 4 berkas** (`test_demo_accounts_browser`, `test_demo_template_breakdown`, `test_demo_po_tautan`, `test_demo_template_provenance_ledger`) + `test_openapi_artifact_drift` 1 lulus | DB klon sekali pakai |
| **Backend suite penuh** | **1.581 lulus, 2 gagal, 28 skip** (554,87 dtk) | `pytest -q` di container sekali-pakai, **kode working tree di-mount**, DB klon `mealchain_clone_v2` |
| Invarian data | **59 PASS / 0 FAIL / 1 SKIP** | `python …/verify_stack.py verify/invariants.spec.json` |
| OpenAPI | 76 path / 78 operasi cocok dengan kode (drift test) | `test_openapi_artifact_drift.py` |
| Lint backend | `ruff check app tests` bersih (termasuk 4 berkas uji baru) | — |
| UI hidup (Playwright) | **tidak dijalankan** pada putaran ini | — |
| Angka dokumen ini | **31/31 klaim cocok** dengan DB/snapshot/gate | `cek_dokumen.py` (§17) |

### 14.1 Dua kegagalan suite — prasyarat data, bukan dua bug produk

Yang tersisa di suite penuh hanya `tests/test_tool_contracts.py` (2 tes):

- `test_balance_analyze_full_pipeline_with_summary` → `assert 0 > 0` (tidak ada
  kandidat alokasi);
- `test_evidence_fuse_assembles_from_recommendation` → `seed harus menghasilkan
  minimal 1 rekomendasi`.

Keduanya membaca **deret waktu demo** (`supply_records`/`price_signals` bentuk
kanonik) yang tidak dibangun ulang di klon, karena penyemai deret menulis ke DB
dan DB demo tidak boleh ditulis. Pulihkan deret demo di klon lebih dulu, lalu
kedua berkas itu lulus — prosedurnya ada di `AGENTS.md`.

Perjalanan angkanya, supaya tidak dibaca sebagai perbaikan ajaib:

| Putaran | Lulus | Gagal | Skip | Catatan |
|---|---:|---:|---:|---|
| Sesi sebelumnya (dokumen lama) | 1.549 | 14 | 28 | keadaan data demo terkumpul |
| Audit 26 Okt 21:37 (klon `audit_test`) | 1.551 | 13 | 27 | `docs/audit/TEST_RESULTS.md` |
| Putaran ini 22:40 (kode working tree) | 1.580 | 3 | 28 | sebelum tes generasi ledger diperbaiki |
| Putaran ini 22:55 (sesudah perbaikan) | **1.581** | **2** | 28 | hanya prasyarat deret demo |

**Yang diperbaiki pada putaran ini** (bukan dengan melunakkan asersi):
(a) `openapi.json` tidak memuat `GET /auth/demo-accounts` sehingga drift test
akan merah — artefak diregenerasi (1 path bertambah, 76/78);
(b) `test_demo_template_provenance_ledger::test_hapus_kasus_demo_menaikkan_generasi_ledger`
semula mengandalkan keputusan demo yang sudah berblok, sehingga merah di suite
penuh (`generasi tidak naik`) walau lulus sendiri — tes kini **membuat bloknya
sendiri** lewat `ledger_service.append_block` sebelum menghapus, jadi hasilnya
tidak bergantung keadaan DB.

Yang **belum** diverifikasi dan tidak boleh diklaim: uji beban, `axe-core`,
`pip-audit`/`bandit`, build produksi `next build` pada mesin bersih, verifikasi
visual manual seluruh 11 tab, dan matriks tab Playwright (`verify/` spec UI)
pada putaran ini.

---

## 15. Batas kemampuan hari ini

| Klaim | Kenyataan |
|---|---|
| "Real-time" | Tidak. Sumber data = template demo, bukan umpan eksternal; layar menyegar lewat polling 5–60 detik; tidak ada scheduler maupun SSE/WebSocket |
| "Terhubung SAP" | Tidak. Adapter aktif `mock`; `aws_mcp`/`odata` adalah stub yang menolak jalan |
| "Agen berjalan sendiri" | Tidak. DETECT hanya saat endpoint/tombol dipanggil |
| "Data eksternal" | Tidak. Semua berasal dari penyemai; PIHPS hanya nama sumber pada baris referensi |
| "Multi-agent otonom" | Belum. Yang ada satu alur tahapan deterministik; kontrak worker read-only masih kontrak |
| "Forecast" | `demand/forecast` memakai deret empiris, bukan model terlatih |
| "Bukti diterima regulator" | Belum. Ledger hash-chain + bukti internal, tanpa sertifikasi pihak ketiga |

Untuk menjadi benar-benar real-time diperlukan empat hal yang belum ada:
penulis data nyata (`origin='live'` + migrasi), konektor sumber (SAP/PIHPS/
laporan suhu), penjadwal (APScheduler/cron), dan dorongan ke layar (SSE/
WebSocket). Skema keputusan, state machine, dan KPI tidak perlu diubah.

---

## 16. Risiko dan pekerjaan terbuka

| # | Hal | Dampak | Status |
|---|---|---|---|
| 1 | Fase 2–6 rencana MG: 7 butir kontrak bisnis | Fase tidak boleh mulai | Menunggu keputusan pemilik |
| 2 | Regional Imbalance mengecualikan `demo_case` | Metrik tidak bergerak saat kartu demo dieksekusi | Menunggu keputusan |
| 3 | SDC memakai keberadaan PO, bukan status `executed` | PO yang dibatalkan tetap terhitung | Menunggu keputusan |
| 4 | Suite backend 2 gagal (§14.1: prasyarat deret waktu demo kosong di klon) | Gate penuh belum bisa disebut hijau | Pulihkan deret demo di klon sebelum menjalankan `test_tool_contracts` |
| 5 | Baris bertanda waktu masa depan (720 + 840) | Label "tercatat hari ini" melebihkan | Perbaiki penyemai / watermark `recorded_at <= now()` |
| 6 | Deret berhenti 5 Nov 2026 | Setelah itu KPI/agenda kosong tanpa error | Perlu jendela relatif |
| 7 | Migrasi 034–038 dipesan rencana | Pekerjaan baru (live/scheduled) mulai 039 | Catatan |
| 8 | SEC-01 rotasi kredensial | Tidak layak produksi | Tindakan pemilik |
| 9 | SEC-04 CVE `next`/`maplibre-gl`/`postcss` | Tidak layak produksi | Migrasi mayor terpisah |
| 10 | `next build` bersih + axe-core + uji beban | Kualitas produksi belum terbukti | Sebelum rilis |
| 11 | `DEMO_MODE` bukan gerbang router | Menutup router tidak berefek apa pun | Diketahui; gerbang sesi yang berlaku |

---

## 17. Peta dokumen

| Dokumen | Isi |
|---|---|
| `AGENTS.md` | Aturan kerja agen, urutan baca, larangan perintah destruktif |
| `docs/PRD.md`, `IDEA.md`, `Rules.md` | Masalah, posisi produk, aturan keras |
| `docs/Architecture.md` | Arsitektur, ADR, jalur SAP/AWS, fallback |
| `docs/Schema.md` | Skema tabel dan kontrak tipe |
| `docs/Skill.md` | Definisi KPI versi proposal (bandingkan dengan kode di kamus) |
| `docs/kamus-kpi-dan-state-machine.md` | Rumus KPI yang benar-benar dijalankan + 5 state machine |
| `docs/state-snapshot.md` / `.json` | **Sumber angka resmi**; dihasilkan `scripts/snapshot_state.py` |
| `docs/demo/panduan-demo-singkat.md` | Panduan panggung |
| `docs/demo/alur-demo-juri.md` | Alur demo juri babak demi babak |
| `docs/laporan/alur-fitur-mealchain.pdf` | Laporan alur semua fitur (12 halaman, angka kanonik) |
| `docs/audit/SECURITY.md` | Status SEC-01/02/04 + rencana upgrade |
| `docs/verification/phase-01-baseline.md` | Bukti Fase 1 rencana MG |
| `MG/audit-rencana-vs-kode.md` | Audit rencana 12 fase terhadap kode |
| `UI_REAL_DATA_VALIDATION_REPORT.md` | Audit 46 klaim UI terhadap DB/API (dengan koreksi pasca-suite) |
| `verify/invariants.spec.json` | 48 pemeriksaan data/HTTP + forensik container; gate terakhir **59 PASS / 0 FAIL / 1 SKIP** |

### Memperbarui angka

```
python scripts/snapshot_state.py          # tulis docs/state-snapshot.json + .md (baca-saja)
```

Skrip itu hanya membaca (seluruh tabel + endpoint + KPI + ledger), tidak menulis
ke database, tidak menyentuh container. Dokumen hidup menyalin angka dari situ;
laporan bertanggal tidak diubah angkanya, hanya diberi header "Snapshot
<tanggal>" lewat `scripts/tandai_snapshot_docs.py`.

---

## 18. Glosarium

| Istilah | Arti |
|---|---|
| SPPG | Satuan Pelayanan Pemenuhan Gizi — dapur penyedia makanan program MBG |
| BGN | Badan Gizi Nasional |
| Batch | Kumpulan bahan pangan dengan identitas, suhu, kesegaran, dan status uji |
| CCP | Critical Control Point — titik kendali keamanan pangan (suhu, FIFO/FEFO, thawing) |
| SDC | Safe Delivered Cost — biaya kiriman yang aman per pengiriman |
| Empat mata | Dua peran berbeda harus menyetujui sebelum eksekusi |
| Verifier | Penilai independen yang memberi verdict `consistent`/`flagged`/`unavailable` |
| Ledger | Rantai blok hash sebagai bukti audit yang tidak bisa diubah diam-diam |
| Template demo | Dataset cetakan (`origin='seed'`) yang bertahan setelah sesi berakhir |
| Adonan | Baris `origin='demo'` yang lahir selama sesi dan dibuang saat sesi berakhir |
| Kanonik | Keadaan hasil builder — bukan keadaan DB yang sudah dipakai tes |
| `no_data` | Keadaan sah KPI ketika penyebut kosong — bukan 0 |
