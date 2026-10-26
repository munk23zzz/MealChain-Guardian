# MealChain Guardian 2.0 — Dokumen Lengkap

Dokumen ini menjelaskan sistem MealChain Guardian secara menyeluruh: apa yang
dikerjakannya, bagaimana ia dibangun, data apa yang dipegangnya, aturan bisnis
yang ditegakkan, sampai batas kemampuannya hari ini.

Semua angka di sini **diukur**, bukan dikutip dari ingatan sesi. Waktu ukur dan
perintah pengukurnya dicantumkan supaya siapa pun bisa mengulang.

| Hal | Nilai |
|---|---|
| Waktu ukur keadaan data | 26 Oktober 2026, 20.47 WIB (`docs/state-snapshot.json`) — sesudah build kanonik + perbaikan pemasok/bukti |
| Waktu ukur KPI | 26 Oktober 2026, 19.30 WIB (`GET /kpi?periode=today\|7d\|1bulan`) |
| Repo | `E:\hackathon\HackathonAWS\mealchain-guardian` |
| Branch / HEAD | `feature/db-modes-demo-coverage` / `1b01961` + 9 commit sesudah `d414957` |
| Migrasi Alembic | 33 berkas, head `033_indeks_fk_hilang` |
| Ukuran kode | backend `app/` 31.958 baris · frontend `app+components+lib+tests` 55.926 baris |
| Berkas uji | 240 berkas backend · 167 berkas frontend (1.818 tes) |
| API | 32 modul router · 75 path · 77 operasi (`backend/openapi.json`) |
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

### 1.1 Angka kunci (keluaran builder, 26 Okt 2026 19.29 WIB)

| Entitas | Jumlah |
|---|---|
| Batch | **125** (wortel 32 · beras 32 · telur 31 · ayam 30); `pass` 102 · `needs_verification` 15 · `fail` 3 (740 kg) · `pending` 5 · karantina 2 (1 dilepas, 1 gagal) · kedaluwarsa <48 jam 8 |
| Keputusan | **48** — 17 `pending_approval` · 10 `rejected` · 9 `executed` · 5 `verifier_flagged` · 3 `approved` · 2 `proposed` · 2 `review_only` (22 terbuka) |
| Approval / bukti / jejak | **28 / 61 / 118** |
| Pemasok / lokasi / komoditas | **60 / 10 / 4** (HACCP 17 · hygiene 35 · tanpa sertifikat 8) |
| Rencana menu | 660 |
| Deret | pasokan 5.240 · harga 6.015 · permintaan 1.360 · pengiriman 180 · pembuangan 83 |
| Blok ledger | **1.742** (valid, 1.670 arsip, 72 blok entitas tertaut, 0 yatim; **+72 setiap build**) |
| Rute jalan | 54 baris cache; 15 kiriman Jakarta (7 di jalan · 6 tiba · 1 belum berangkat · 1 tanpa geometri) |
| PO mock SAP | **20** (15 `confirmed` · 3 `submitted` · 2 `draft`) |
| Penerimaan | **7** (5 `menunggu` · 1 `disetujui` · 1 `ditolak`) |
| Kartu 24 jam Jakarta | **14** (10 menunggu · 2 ditandai verifier · 2 sudah dieksekusi) |
| Sesi demo | 6 baris riwayat, 1 aktif pada snapshot |

> **Angka ini bergerak.** Ledger bertambah 72 blok setiap build/rebuild, dan
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
| `DEMO_MODE` | `False` | **Bukan** gerbang router demo (lihat §16) |
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
   ├── api/          32 modul router, 77 operasi HTTP (75 path)
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

### 4.1 Backend (`backend/app`, 31.958 baris)

| Folder | Isi |
|---|---|
| `api/` | 32 modul router: `decisions`, `actions`, `kpi`, `agenda`, `batches`, `suppliers`, `supplier_exclusions`, `supplier_routes`, `receipts`, `waste`, `surplus`, `ledger`, `demo`, `demo_session`, `admin`, `auth`, `balance`, `price`, `demand`, `evidence`, `freshness`, `logistics`, `safety`, `sap`, `integrations`, `quarantine`, `events/*`, `health` |
| `services/` | `kpi_service`, `agenda_service`, `demo_session`, `demo_template_reset`, `supplier_eligibility`, `journey`, `event1/2/3`, `ledger_service`, `forecasting` |
| `core/` | `approval_matrix`, `kpi_period`, `journey`, `safety_gate`, `commodity_limits`, `safe_delivered_cost`, `hash`, `security`, `config`, `pagination` |
| `models/` | 22 tabel SQLAlchemy + constraint + index |
| `sap_integration/` | `interface`, `mock` (aktif), `aws_mcp`/`odata` (stub yang menolak jalan), `mapping`, `factory` |
| `seed/` | `seed_data`, `timeseries`, `demo_template`, `demo_activity`, `demo_extra`, `demo_kasus_bukti`, `demo_kpi_riwayat`, `suppliers_demo` |

### 4.2 Frontend (`frontend`, 55.944 baris TS/TSX termasuk tes)

| Bagian | Isi |
|---|---|
| `app/page.tsx` | konsol satu halaman, ±2.035 baris, 11 tab |
| `components/` | papan per domain (`KPIDashboard`, `FoodSafetyBoard`, `SupplierBoard`, `TodayDashboard`, `DemoControlPanel`, `AgentTraceViewer`, …) |
| `lib/` | pemformatan (`today`, `kpi`, `food-safety`, `supplier-pins`, `agenda`), aturan tampilan, tipe |
| `lib/hooks/` | hook React Query (keputusan, KPI, saldo, rute, hari ini, sesi, …) |
| `tests/` | 167 berkas uji, 1.818 tes (vitest) |

### 4.3 Basis data

22 tabel domain, tanpa tabel riwayat bayangan: perubahan status dicatat di
`approvals`, `agent_traces`, `decision_evidence`, dan `ledger_blocks`.

---

## 5. Model data

### 5.1 Kelompok tabel (jumlah baris = snapshot 19.29 WIB)

| Kelompok | Tabel | Peran |
|---|---|---|
| Master | `locations` (10), `commodities` (4), `suppliers` (60), `users` (8) | Acuan yang tidak dihapus saat reset demo |
| Pasokan | `supply_records` (5.240), `price_signals` (6.015), `demand_records` (1.360) | Fakta harian per lokasi+komoditas |
| Operasi | `menu_plans` (660), `delivery_events` (180), `batches` (125), `disposal_events` (83), `road_routes` (54) | Rencana, pengiriman, batch fisik, limbah, geometri rute |
| Keputusan | `decisions` (48), `approvals` (28), `decision_evidence` (61), `agent_traces` (118) | Inti nilai: usul, persetujuan, bukti, jejak |
| Keamanan & pemasok | `supplier_exclusions` (6), `batch_receipts` (7) | Eksklusi/usulan pemasok, penerimaan barang |
| Audit | `ledger_blocks` (1.742), `ledger_meta` | Hash-chain append-only |
| SAP tiruan | `sap_mock_purchase_orders` (20), `sap_mock_material_stock` (40) | Cermin dokumen SAP |
| Demo | `demo_sessions` (6, 1 aktif) | Sesi 120 menit, penjaga tulisan |

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

Tiga peran, 8 baris akun: 7 akun resmi aktif (`sppg_head` 3, `sppg_nutritionist`
3, `bgn_monitor` 1) + 1 akun uji **dinonaktifkan** (password dirotasi, tidak
bisa login) karena memegang 2 approval historis.

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

Kata sandi akun demo **tidak** ada di bundel klien (SEC-02, 26 Okt 2026):
tombol akun demo hanya mengisi email. Kata sandi tetap tersedia di sisi server
untuk juri — `backend/app/seed/demo_credentials.py` (hanya berlaku bila
`DEMO_MODE` aktif) atau variabel `DEMO_PASSWORD_<ROLE>` — bukan di JavaScript
yang bisa dibaca siapa pun.

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

Tujuh tahap tercatat di `agent_traces.step_name`. Total jejak sekarang **118**.

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

75 path, 77 operasi (OpenAPI `backend/openapi.json`, drift-tested terhadap kode).

| Domain | Endpoint utama |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me` |
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

Nilai terukur (lokasi Jakarta, 26 Okt 2026 19.30 WIB, sesudah rebuild kanonik):

| KPI | Hari ini | 7 hari | 1 bulan |
|---|---|---|---|
| Meal Continuity | `—` (jendela kirim hari ini belum tiba) | 100,00% | 70,52% |
| Avoidable Food Loss | 0,59% (3) | 0,16% | 0,07% |
| Regional Imbalance | 100,00% (2) | 60,00% | 60,00% |
| Safe Delivered Cost | Rp18.472.767,67 (2) | Rp18.472.767,67 | Rp18.472.767,67 |
| Price Deviation | 2,66% (17) | 2,92% | 3,42% |
| Decision Time | 20 menit (2) | 20 menit | 20 menit |
| Evidence Completeness | 66,67% (3) | 50,00% | 50,00% |

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
| Template (cetakan) | `origin='seed'`, `demo_session_id=NULL` | permanen | tidak |
| Sesi (adonan) | `origin='demo'` + `demo_session_id` | ≤120 menit | ya |

Tampilan default kosong. Menekan **Siapkan data demo** membangun template lebih
dulu, baru membuka sesi — urutan ini wajib, karena sesi yang habis di tengah
pembangunan membuat penyapu menghapus baris demo yang baru ditulis.

**Keluaran builder adalah baseline yang benar:** 48 keputusan, 125 batch, 28
approval, 60 pemasok, 1.742 blok. Angka 36/120/1.382 yang sempat dipakai
dokumen lama berasal dari DB yang sudah dipurge suite tes — bukan keluaran
builder.

### 12.2 Angka yang bergerak dan yang tidak

| Aksi | Yang berubah |
|---|---|
| Approve | `approvals`, status keputusan, kuorum di UI |
| Execute | batch berangkat, PO bertambah, SDC, blok ledger, Decision Time/SDC |
| Penerimaan | `batch_receipts`, stok SAP tiruan |
| Bangun ulang | isi kembali ke jumlah awal (48/125/28/61), **tetapi** ledger +72 blok (arsip generasi) dan jam kejadian di-anchor ulang |
| Waktu berjalan | "x menit lalu", posisi truk (interpolasi), sisa masa layak, jendela KPI melebar |

### 12.3 Dua jangkar waktu yang belum seragam

- Kejadian operasional (batch, keputusan, PO, jejak) dihitung relatif ke
  `datetime.now()` saat build → **ikut jam dinding**.
- Deret 65 hari (pasokan, harga, menu, permintaan, pengiriman, limbah) dipatok
  `2026-09-01 .. 2026-11-05` (`app/seed/timeseries.py`) → **tidak ikut jam**.

Konsekuensi terukur pada snapshot ini: **720 baris `supply_records` dan 858
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
| Ledger | Hash-chain di Postgres; `GET /ledger/verify` → `valid=true`, 1.742 blok, 72/72 blok entitas tertaut, 0 yatim |
| Rahasia (SEC-01) | `.env` tidak dilacak git, tetapi nilainya harus dianggap bocor → **rotasi wajib** sebelum publik |
| Kredensial demo (SEC-02) | **Ditutup di kode 26 Okt 2026**: tidak ada kata sandi di bundel klien; tombol login hanya mengisi email |
| Dependensi (SEC-04) | `next@14.2.14` dan `maplibre-gl@4.7.1` critical, `postcss` high; `npm audit fix` tanpa `--force` tidak menyelesaikan apa pun. Perbaikan menuntut Next 16 + maplibre 6 → rencana di `docs/audit/SECURITY.md` |

Mitigasi yang sudah dilakukan: dokumen operasional diberi header snapshot,
perintah pytest destruktif diganti resep DB klon di `AGENTS.md`, sesi demo wajib
(`DEMO_SESSION_ENFORCE=true`) dengan satu sesi aktif, dan kata sandi demo
dihapus dari bundel.

---

## 14. Pengujian dan verifikasi

| Lapis | Hasil terukur | Cara |
|---|---|---|
| Frontend unit/komponen | **1.818 lulus / 167 berkas**; `tsc --noEmit` exit 0; ESLint bersih | `npx vitest run` |
| Backend (target + integrasi) | 32 lulus (subset target) · **3 lulus** tes integrasi build (167 dtk) | DB klon `mealchain_idem2` |
| **Backend suite penuh** | **1.549 lulus, 14 gagal, 28 skip** (543 dtk) | `pytest -q` pada DB klon `mealchain_suite` |
| Invarian data | **52 PASS / 0 FAIL / 1 SKIP** | `python …/verify_stack.py verify/invariants.spec.json` |
| OpenAPI | `openapi.json` cocok dengan kode (drift test) | bagian suite backend |
| Lint backend | `ruff check app tests` bersih | — |
| UI hidup (Playwright) | 10 tab, 0 console error, semua endpoint 200 | `scratch/harvest_ui.py` |
| Angka dokumen ini | **24/24 klaim cocok** dengan DB/snapshot | penyapu ad-hoc (§17) |

### 14.1 Empat belas kegagalan suite — dua kelas, bukan 14 bug produk

Diuji satu per satu pada DB klon bersih (satu berkas per clone):

**Kelas A — gagal juga saat berdiri sendiri (6 tes).**
- `test_demo_timeseries_api.py` (4): prasyarat deret demo belum terbangun di
  klon (`deret demo belum dibangun`, `assert 0 > 0`), satu lagi
  `AttributeError: 'NoneType' … startswith`, dan pembulatan
  `1393.93 == 1400.0`.
- `test_demo_session_mulai_atomik.py::test_build_gagal_tidak_meninggalkan_sesi_aktif`
  (1): `decisions berubah padahal build gagal` — build yang gagal belum
  sepenuhnya rollback.
- `test_demo_harian.py::test_harga_harian_demo_tersedia_untuk_hari_ini` (1):
  satu kutipan harga demo tidak punya acuan PIHPS lebih dulu, sehingga metrik
  deviasi harga bisa kosong untuk baris itu.

**Kelas B — lulus sendiri, gagal di suite (8 tes).**
- `test_demo_seed_per_kota.py` (4) dan `test_akun_multi_kota.py` (2): lulus saat
  berkasnya dijalankan sendiri, gagal bila didahului berkas yang menyemai ulang
  atau mem-purge demo — kontaminasi satu database bersama.
- `test_tool_contracts.py` (2): order-dependent, lulus di jalur sendiri.

Perbaikannya isolasi (transaksi per tes atau schema per worker) dan penutupan
tiga cacat Kelas A — bukan mengubah angka produk.

**Yang sudah diperbaiki pada putaran ini.** (a) keluarga "konstanta jumlah
lama" (6 tes pemasok) hilang: builder tidak lagi mengganti nama pemasok demo,
residu 1 baris dihapus, direktori kembali **60 baris dengan 60 koordinat unik**
(dulu 61 baris, dua pin bertumpuk); (b) setiap keputusan skrip `extra:*` kini
punya `decision_evidence` (dulu 4 kartu tanpa bukti) — `test_bukti_dan_draf_demo`
hijau. Suite: **27 → 14 gagal**, lulus 1.536 → **1.549**.

Yang **belum** diverifikasi dan tidak boleh diklaim: uji beban, `axe-core`,
`pip-audit`/`bandit`, build produksi `next build` pada mesin bersih, verifikasi
visual manual seluruh 11 tab.

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
| 4 | Suite backend 14 gagal (§14.1: 6 Kelas A, 8 Kelas B) | Gate penuh belum bisa disebut hijau | Perlu isolasi DB per tes + perbaikan prasyarat |
| 5 | Baris bertanda waktu masa depan (720 + 858) | Label "tercatat hari ini" melebihkan | Perbaiki penyemai / watermark `recorded_at <= now()` |
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
| `verify/invariants.spec.json` | 52+ invarian yang dijalankan gate |

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
