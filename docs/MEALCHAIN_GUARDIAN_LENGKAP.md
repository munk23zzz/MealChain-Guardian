# MealChain Guardian 2.0 — Dokumen Lengkap

Dokumen ini menjelaskan sistem MealChain Guardian secara menyeluruh: apa yang
dikerjakannya, bagaimana ia dibangun, data apa yang dipegangnya, aturan bisnis
yang ditegakkan, sampai batas kemampuannya hari ini.

Semua angka di sini **diukur**, bukan dikutip dari ingatan sesi. Waktu ukur dan
perintah pengukurnya dicantumkan supaya siapa pun bisa mengulang.

| Hal | Nilai |
|---|---|
| Waktu ukur keadaan data | 26 Oktober 2026, 13.52 WIB (`docs/state-snapshot.json`) |
| Waktu ukur KPI | 26 Oktober 2026, ±17.57 WIB (`GET /kpi?periode=today\|7d\|1bulan`) |
| Repo | `E:\hackathon\HackathonAWS\mealchain-guardian` |
| Branch / HEAD | `feature/db-modes-demo-coverage` / `d414957` (25 Okt 2026) |
| Migrasi Alembic | 33 berkas, head `033_indeks_fk_hilang` |
| Ukuran kode | backend `app/` 31.896 baris · frontend `app+components+lib` 30.875 baris |
| Berkas uji | 235 berkas backend · 166 berkas frontend |

> **Catatan kejujuran data.** Seluruh isi database saat ini berasal dari
> penyemai demo (`origin='seed'`/`'demo'`) atau `mock-sap`. Tidak ada koneksi
> keluar ke SAP, PIHPS, atau sensor. Jangan menyebutnya "data operasional nyata"
> atau "data eksternal aktual" di depan siapa pun.

---

## 0. Cara memakai dokumen ini

| Pertanyaan | Bagian |
|---|---|
| Sistem ini untuk apa, dan apa yang bukan urusannya | 1 |
| Bagaimana komponen berjalan bersama | 2, 3 |
| Di folder mana kode apa | 4 |
| Tabel apa saja yang ada, dan apa artinya | 5 |
| Siapa boleh apa | 6 |
| Bagaimana satu keputusan bergerak dari usul ke kiriman | 7 |
| Agen bekerja dengan tahap apa | 8 |
| Endpoint apa yang tersedia | 9 |
| Layar menyajikan apa, dan seberapa segar | 10 |
| Angka KPI dihitung bagaimana | 11 |
| Mengapa angka berubah/tidak berubah saat demo | 12 |
| Keamanan dan risikonya | 13 |
| Apa yang sudah diuji, apa yang belum | 14, 15 |
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

Angka kunci keadaan demo (26 Okt 2026 13.52 WIB):

| Entitas | Jumlah |
|---|---|
| Batch | 120 (lulus 100 · perlu verifikasi 14 · gagal 3 · belum diuji 3 · ditahan 1 · kedaluwarsa <48 jam 8) |
| Keputusan | 36 (terbuka 19: 15 menunggu approval + 4 ditandai verifier) |
| Pemasok | 60 (HACCP 17 · hygiene 35 · tanpa sertifikat 8) |
| Rencana menu | 660 |
| Catatan pasokan | 5.240 · kutipan harga 5.924 · permintaan 1.360 · pengiriman 180 · pembuangan 80 |
| Blok ledger | 1.598 (valid, 1.526 arsip, 72 blok entitas tertaut, 0 yatim; +72 setiap build) |
| Rute jalan | 53 · penerimaan menunggu 2 · PO 16 (14 confirmed, 2 submitted) |
| Sesi demo | 3, semuanya `expired` |

---

## 2. Peta runtime

Empat container, satu jaringan Docker (`mealchain-network`):

| Container | Port host | Status ukur | Isi |
|---|---|---|---|
| `mealchain-backend` | 8000 | healthy, Up 14 jam | FastAPI + SQLAlchemy + Alembic |
| `mealchain-frontend` | 3010 → 3000 | healthy, Up 23 jam | Next.js 14.2.14 (App Router) |
| `mealchain-postgres` | 15432 → 5432 | healthy, Up 23 jam | PostgreSQL, volume persisten |
| `mealchain-mock-sap` | 8001 | Up 23 jam | Tiruan endpoint SAP (PO, stok) |

Konfigurasi yang menentukan perilaku demo (`.env`, tidak ikut di-commit):

| Variabel | Nilai sekarang | Arti |
|---|---|---|
| `DEMO_SESSION_ENFORCE` | `true` | Tanpa sesi demo aktif, semua POST/PUT/PATCH/DELETE → 409 |
| `DEMO_SESSION_MINUTES` | `120` | Umur sesi bawaan |
| `DEMO_SESSION_MAX_MINUTES` | `120` | Plafon absolut START maupun EXTEND |
| `sap_provider` | `mock` | Adapter SAP aktif = tiruan, bukan koneksi asli |

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
   ├── api/          33 router, 77 operasi HTTP (75 path)
   ├── services/     logika bisnis: kpi, agenda, kandidat, eligibility,
   │                 journey, demo_session, ledger, event1..3
   ├── core/         aturan keras: approval_matrix, kpi_period, journey,
   │                 hash (ledger), security (JWT), pagination
   ├── models/       SQLAlchemy 22 tabel
   ├── sap_integration/  adapter: mock (aktif) · aws_mcp/odata (stub jujur)
   └── seed/         init master, timeseries, demo_template
   ▼
PostgreSQL — system of fact untuk keputusan, bukti, ledger
```

### 3.2 Perjalanan satu keputusan (contoh: transfer penyeimbang)

1. **DETECT** — `POST /demo/event1` (atau pemanggilan `/balance/analyze`)
   menemukan lokasi surplus dan lokasi kekurangan untuk komoditas yang sama.
   Tertulis baris `decisions` (status `proposed`) + `agent_traces` tahap
   `DETECT`.
2. **PREDICT/OPTIMIZE** — kebutuhan beberapa hari dihitung dari
   `demand_records`; kandidat pemasok disaring (`supplier_eligibility`):
   sertifikat, jarak, status karantina, kesegaran batch.
3. **DECIDE** — angka deterministik dihitung: `safe_delivered_cost`, skor
   kandidat, alasan penolakan kandidat lain.
4. **VERIFY** — `/actions/verify` menghasilkan verdict `consistent`,
   `flagged`, atau `unavailable`. `flagged` mengubah status ke
   `verifier_flagged`; `unavailable` berarti belum dinilai.
5. **Propose** — `/actions/propose` memindahkan `proposed|verifier_flagged`
   → `pending_approval` dan mengisi `expires_at`.
6. **Approval empat mata** — `/actions/approve`, kuorum sesuai
   `approval_matrix`. Kuorum penuh → status `approved` (belum berangkat).
7. **Execute** — `/actions/execute` memvalidasi ulang safety/freshness batch,
   menulis `batches.dispatched_at`, membuat PO di `sap_mock_purchase_orders`,
   mengisi `safe_delivered_cost`, menambah blok ledger, status → `executed`.
8. **Journey** — status truk **dihitung**, bukan disimpan:
   `belum_berangkat` → `di_jalan` → `sudah_tiba` (atau `tidak_diketahui`
   bila durasi rute belum ada).
9. **Receive** — `/receipts` + approve/reject menutup siklus; batch gagal uji
   bisa dikarantina (`POST /batches/{id}/quarantine`).
10. **LEARN** — mencatat iterasi ulang setelah keputusan ditolak (`repropose`)
    sebagai langkah `LEARN` di `agent_traces`. Skor keandalan pemasok **tidak**
    diperbarui otomatis; nilainya hanya dinormalisasi saat dibaca
    (`core/reliability.py`).

---

## 4. Struktur kode

### 4.1 Backend (`backend/app`, 31.896 baris)

| Folder | Isi |
|---|---|
| `api/` | 33 router: `decisions`, `actions`, `kpi`, `agenda`, `batches`, `suppliers`, `supplier_exclusions`, `supplier_routes`, `receipts`, `waste`, `surplus`, `ledger`, `demo`, `admin`, `auth`, `balance`, `price`, `demand`, `evidence`, `freshness`, `logistics`, `safety`, `compliance`, `dossier`, `sap`, `integrations`, `quarantine`, `events/*`, `health` |
| `services/` | `kpi_service`, `agenda_service`, `demo_session`, `demo_template` (di `seed/`), `supplier_eligibility`, `journey`, `event1/2/3`, `ledger`, `forecasting` |
| `core/` | `approval_matrix`, `kpi_period`, `journey`, `hash`, `security`, `config`, `pagination`, `cost` |
| `models/` | 22 tabel SQLAlchemy + constraint + index |
| `sap_integration/` | `interface`, `mock` (aktif), `aws_mcp`/`odata` (stub yang menolak jalan), `mapping`, `factory` |
| `seed/` | `init` master data, `timeseries`, `demo_template`, `demo_kpi_riwayat` |

### 4.2 Frontend (`frontend`, 30.875 baris)

| Bagian | Isi |
|---|---|
| `app/page.tsx` | konsol satu halaman, 2.035 baris, 11 tab |
| `components/` | 56 komponen: papan per domain (`KPIDashboard`, `FoodSafetyBoard`, `SupplierBoard`, `TodayDashboard`, `DemoControlPanel`, `AgentTraceViewer`, …) |
| `lib/` | 63 modul: pemformatan (`today`, `kpi`, `food-safety`, `supplier-pins`, `agenda`), aturan tampilan, tipe |
| `lib/hooks/` | 17 hook React Query (keputusan, KPI, saldo, rute, hari ini, sesi, …) |
| `tests/` | 166 berkas uji (vitest) |

### 4.3 Basis data

22 tabel, tidak ada tabel riwayat bayangan: perubahan status dicatat di
`approvals`, `agent_traces`, `decision_evidence`, dan `ledger_blocks`.

---

## 5. Model data

### 5.1 Kelompok tabel

| Kelompok | Tabel | Peran |
|---|---|---|
| Master | `locations` (10), `commodities` (4), `suppliers` (60), `users` (11) | Acuan yang tidak ikut dihapus saat reset demo |
| Pasokan | `supply_records` (5.240), `price_signals` (5.924), `demand_records` (1.360) | Fakta harian per lokasi+komoditas |
| Operasi | `menu_plans` (660), `delivery_events` (180), `batches` (120), `disposal_events` (80), `road_routes` (53) | Rencana, pengiriman, batch fisik, limbah, geometri rute |
| Keputusan | `decisions` (36), `approvals` (21), `decision_evidence` (51), `agent_traces` (85) | Inti nilai: usul, persetujuan, bukti, jejak |
| Keamanan & pemasok | `supplier_exclusions` (2), `batch_receipts` (2) | Eksklusi/usulan pemasok, penerimaan barang |
| Audit | `ledger_blocks` (1.598) | Hash-chain append-only |
| SAP tiruan | `sap_mock_purchase_orders` (16), `sap_mock_material_stock` (40) | Cermin dokumen SAP |
| Demo | `demo_sessions` (3) | Sesi 120 menit, penjaga tulisan |

Komoditas: ayam, beras, telur, wortel.
Lokasi (10): Bandung, Bogor, Cianjur, Jakarta, Makassar, Medan, Palembang,
Semarang, Surabaya, Yogyakarta.

### 5.2 Aturan integritas yang ditegakkan database

- **`origin`** pada tabel fakta hanya menerima `'seed'` dan `'demo'`. Tidak ada
  jalur untuk data "nyata" hari ini — ini batas penting kalau kelak ingin mode
  live (perlu migrasi baru).
- **Satu keputusan = satu approval per akun** (unique index migrasi 030);
  pelanggaran ditangani sebagai 409, bukan 500.
- **Satu sesi demo aktif** (partial unique index
  `uq_demo_sessions_satu_aktif` pada `status='active'`, migrasi 032).
- **Status keputusan** dibatasi CHECK: `proposed`, `verifier_flagged`,
  `pending_approval`, `approved`, `rejected`, `executed`, `review_only`.
- **PO tiruan** hanya menerima status `confirmed`/`submitted`; kolom uangnya
  (`ordered_quantity`, `material_number`) dipakai untuk jejak, bukan total.
- **Ledger** append-only: tiap blok menyimpan `prev_hash` dan `hash`; tidak ada
  endpoint untuk mengubah/menghapus blok.

### 5.3 Hubungan yang sering disalahpahami

| Hal | Kenyataan di skema |
|---|---|
| `delivery_events` per lokasi? | Tidak ada `location_id`; lokasi diturunkan lewat `menu_plans.location_id` |
| Status perjalanan truk | Tidak ada kolomnya; dihitung `journey.py` dari `dispatched_at` + `road_routes.duration_s` |
| Status keamanan batch | Kolom `safety_status` di `batches`, diisi hasil uji; tidak pernah di-override agent |
| Kutipan harga | `price_signals` punya `supplier_id`; 143 grup (lokasi, komoditas, sumber, waktu) bisa memuat 1–4 pemasok berbeda pada jam yang sama — itu wajar, bukan duplikasi |
| Bukti keputusan | `decision_evidence` menyimpan tipe bukti + `is_consistent`; kelengkapan bukti dihitung terhadap waktu approval pertama |

---

## 6. Peran dan wewenang

Tiga peran, 8 baris akun: 7 akun resmi aktif (`sppg_head` 3, `sppg_nutritionist` 3, `bgn_monitor` 1)
+ 1 akun uji yang **dinonaktifkan** (password dirotasi, tidak bisa login) karena memegang 2 approval historis.

| Peran | Boleh | Tidak boleh |
|---|---|---|
| `sppg_head` | Approval, eksekusi, penerimaan, tab Demo Control | Pengelolaan pengguna/lokasi (itu milik `bgn_monitor`) |
| `sppg_nutritionist` | Approval (wajib berpasangan untuk keputusan operasional), verifikasi keamanan pangan | Eksekusi tanpa pasangan |
| `bgn_monitor` | Membaca seluruh dashboard, KPI, agent log; mengelola pengguna & lokasi (`/admin/*`, tab Pengaturan) | Approval/eksekusi (tidak termasuk `APPROVER_ROLES`) |

Matriks kuorum (`core/approval_matrix.py`):

| Verdict verifier | Tipe keputusan | Syarat |
|---|---|---|
| `consistent` | administrasi (eksklusi/restorasi pemasok) | 1 approval: `sppg_head` **atau** `sppg_nutritionist` |
| `flagged`/`unavailable` | administrasi | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |
| apa pun | operasional (transfer, pengadaan, safety, harga) | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |

Aturan tambahan: satu penolakan menggugurkan kuorum; approval dari lokasi lain
tidak dihitung saat eksekusi; kuorum penuh hanya berarti `approved` — PO dan
keberangkatan baru lahir di `execute`.

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

Batch yang ditahan (`batch_blokir_eksekusi`: safety, karantina,
`usable_until`, suhu) tidak diberi `dispatched_at`, sehingga tidak pernah
digambar sebagai truk.

### 7.3 Sesi demo

```
kosong ──START──► active (≤120 menit) ──expired──► kosong
                     │  ▲
                  EXTEND┘ (tidak bisa melewati plafon absolut)
                     │
                     └──END──► kosong (baris origin='demo' dibuang)
```

Kedaluwarsa dinilai **malas** saat ada request, bukan oleh cron. Tidak ada
pembekuan jam: `anchor_now` dicatat, waktu berjalan normal.

---

## 8. Pipeline agen

Tujuh tahap yang tercatat di `agent_traces.step_name`, dengan jumlah baris pada
dataset sekarang: `DETECT` 27 · `DECIDE` 27 · `LEARN` 9 · `VERIFY` 8 ·
`PREDICT` 6 · `ACT` 5 · `OPTIMIZE` 3.

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
tidak menyimpan slot model penyedia (primary/fallback) — jadi jangan mengklaim
atribusi model per langkah dari tabel itu.

Jejak agen menyimpan **fakta keputusan** (kg, `safe_delivered_cost`, durasi),
bukan teks template. UI menampilkan kalimat ringkas + lipatan "Data mentah".

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
lengkap, sudah dieksekusi, kedaluwarsa), **422** (periode tidak sah, mis.
`24h` atau campuran `periode`+`start`), **401/403** (token/peran).

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
| Pengaturan | Pengguna & lokasi (`/admin/users`, `/admin/locations`) | peran `bgn_monitor` |
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
| Pemasok | tanpa polling (data nyaris statis) |

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

Nilai terukur (lokasi Jakarta, 26 Okt 2026 19.32 WIB, sesudah rebuild kanonik):

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

---

## 12. Arsitektur demo (mengapa angka bergerak atau tidak)

### 12.1 Dua lapis: cetakan dan adonan

| Lapis | Stempel | Umur | Dibuang saat sesi berakhir? |
|---|---|---|---|
| Template (cetakan) | `origin='seed'`, `demo_session_id=NULL` | permanen | tidak |
| Sesi (adonan) | `origin='demo'` + `demo_session_id` | ≤120 menit | ya |

Tampilan default kosong. Menekan **Siapkan data demo** membangun template lebih
dulu, baru membuka sesi — urutan ini wajib, karena sesi yang habis di tengah
pembangunan membuat penyapu menghapus baris demo yang baru ditulis (pernah
terjadi: 36 keputusan → 5).

### 12.2 Angka yang bergerak dan yang tidak

| Aksi | Yang berubah |
|---|---|
| Approve | `approvals`, status keputusan, kuorum di UI |
| Execute | batch berangkat, PO bertambah, `safe_delivered_cost`, blok ledger, Decision Time/SDC |
| Penerimaan | `batch_receipts`, stok SAP tiruan |
| Bangun ulang | seluruh dataset kembali ke angka awal (terukur 41 detik) |
| Waktu berjalan | "x menit lalu", posisi truk (interpolasi), sisa masa layak, jendela KPI melebar |

### 12.3 Dua jangkar waktu yang belum seragam

- Kejadian operasional (batch, keputusan, PO, jejak) dihitung relatif ke
  `datetime.now()` saat build → **ikut jam dinding**.
- Deret 65 hari (pasokan, harga, menu, permintaan, pengiriman, limbah) dipatok
  `2026-09-01 .. 2026-11-05` → **tidak ikut jam**.

Konsekuensi terukur: 760 baris `supply_records` dan 880 baris `price_signals`
bertanggal **masa depan** (deret s/d 4 Nov 2026 19.00). Hari ini Jakarta punya
12 baris pasokan dan 25 baris kutipan harga; **4 di antaranya** (masing-masing)
bertanda waktu setelah sekarang, yaitu slot 19.00 yang belum terjadi. KPI tidak terpengaruh (jendela berakhir di `now`), tetapi label
"tercatat hari ini" sedikit melebihkan. Setelah 5 November 2026 deret berhenti,
sehingga "hari ini" tidak punya baris lagi — KPI dan agenda akan kosong tanpa
error.

### 12.4 Jebakan operasional

- **Jangan** menjalankan `docker compose exec backend pytest` pada database
  yang dipakai demo: tes mem-purge baris `origin='demo'` (pernah membuat
  keputusan 36 → 9 dan meninggalkan 15 akun `@test.local`). Pakai DB klon.
- Sesi demo adalah satu-satunya penjaga tulisan; tanpa sesi, POST → 409
  (baca tetap jalan).
- Menekan "Siapkan data demo" memakan ±41 detik; jangan dilakukan di detik
  terakhir sebelum presentasi.

---

## 13. Keamanan dan kepatuhan

| Aspek | Keadaan |
|---|---|
| Auth | Bearer JWT (`api/auth.py`), default 30 menit, nilai `.env` dijepit ke rentang aman; peran & lokasi ikut di klaim |
| Otorisasi | Peran + cakupan lokasi; approver dibatasi `APPROVER_ROLES` |
| CORS | Dikonfigurasi dari `CORS_ORIGINS`; default hanya origin UI |
| Ledger | Hash-chain di Postgres; `GET /ledger/verify` → `valid=true`, 1.598 blok, 72/72 blok entitas tertaut, 0 yatim |
| Rahasia | `.env` tidak dilacak git, tetapi **pernah masuk riwayat** → rotasi wajib sebelum publik (SEC-01) |
| Kredensial demo | 7 akun demo tertanam di bundel klien (SEC-02) — siapa pun yang membuka instance bisa masuk sebagai approver. Aman hanya untuk demo tertutup |
| Dependensi | `next@14.2.14` dan `maplibre-gl@4.7.1` berstatus critical, `postcss` high (SEC-04) — risiko diterima untuk demo, bukan untuk produksi |

Mitigasi yang sudah dilakukan: dokumen operasional diberi header snapshot,
perintah pytest destruktif diganti resep DB klon di `AGENTS.md`, dan sesi demo
dibuat wajib (`DEMO_SESSION_ENFORCE=true`) dengan satu sesi aktif.

---

## 14. Pengujian dan verifikasi

| Lapis | Hasil terukur | Cara |
|---|---|---|
| Frontend unit/komponen | 1.818 lulus / 166 berkas; `tsc --noEmit` exit 0; ESLint bersih | `npx vitest run` |
| Backend | 1.487 tes: 1.450 lulus, 24 skip, 13 gagal **order-dependent** (lulus saat dijalankan sendiri) | diukur 25 Okt; jalankan pada DB klon, bukan DB demo |
| Invarian data | 52 PASS / 0 FAIL / 1 SKIP | `python …/verify_stack.py verify/invariants.spec.json` |
| OpenAPI | `openapi.json` cocok dengan kode (drift test) | bagian suite backend |
| UI hidup (Playwright) | 10 tab, 0 console error, semua endpoint 200 | `scratch/harvest_ui.py` |
| Rekonsiliasi angka | Food Loss 0,5862% · Price Deviation 2,6553% dihitung ulang dari DB | `scratch/data_quality.py` |

Yang **belum** diverifikasi dan tidak boleh diklaim: uji beban, `axe-core`
aksesibilitas, `pip-audit`/`bandit`, build produksi `next build` pada mesin
bersih, verifikasi visual manual seluruh 11 tab.

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

## 16. Risiko dan keputusan yang masih terbuka

| # | Hal | Dampak | Status |
|---|---|---|---|
| 1 | Regional Imbalance mengecualikan `demo_case` | Metrik tidak bergerak saat kartu demo dieksekusi | Menunggu keputusan pemilik |
| 2 | SDC memakai keberadaan PO, bukan status `executed` | PO yang dibatalkan tetap terhitung | Menunggu keputusan |
| 3 | Baris bertanda waktu masa depan (760 + 880) | Label "tercatat hari ini" melebihkan; agenda menghitung jam yang belum terjadi | Perlu perbaikan penyemai |
| 4 | Deret berhenti 5 Nov 2026 | Setelah itu KPI/agenda kosong tanpa error | Perlu jendela relatif |
| 5 | 13 tes backend order-dependent | Gate penuh belum bisa dipercaya sebagai hijau | Perlu isolasi/DB klon |
| 6 | SEC-01 rotasi `.env`, SEC-04 CVE, SEC-02 kredensial demo di bundel | Tidak layak produksi | Sebelum rilis |
| 7 | Belum ada `next build` bersih + axe-core + uji beban | Kualitas produksi belum terbukti | Sebelum rilis |

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
| `docs/demo/panduan-demo-singkat.md` | Panduan panggung 8 menit |
| `docs/demo/alur-demo-juri.md` | Alur demo juri babak demi babak |
| `docs/laporan/alur-fitur-mealchain.pdf` | Laporan alur semua fitur (12 halaman) |
| `UI_REAL_DATA_VALIDATION_REPORT.md` | Audit 46 klaim UI terhadap DB/API |
| `docs/audit/AUDIT_01…11` | Audit per lapisan (data, backend, frontend, keamanan, …) |
| `verify/invariants.spec.json` | 52+ invarian yang dijalankan gate |

### Memperbarui angka

```
python scripts/snapshot_state.py          # tulis docs/state-snapshot.json + .md (baca-saja)
```

Skrip itu hanya membaca (22 tabel + endpoint + KPI + ledger), tidak menulis ke
database, tidak menyentuh container. Dokumen hidup menyalin angka dari situ;
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
| `no_data` | Keadaan sah KPI ketika penyebut kosong — bukan 0 |
