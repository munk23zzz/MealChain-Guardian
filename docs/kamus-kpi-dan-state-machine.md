# Kamus KPI dan State Machine — MealChain Guardian

Status: **Langkah 2 (kamus + state machine) dan Langkah 3 (periode dihitung server)
selesai** — 25 Oktober 2026. Dokumen ini ditulis dari kode yang berjalan di
`backend/` dan `frontend/` pada branch `feature/db-modes-demo-coverage`, ditambah
`docs/Skill.md` §4 dan `docs/PRD.md`.

Aturan yang dipakai di seluruh dokumen ini:

1. **Kode adalah kebenaran**, dokumen menyusul. Bila `docs/Skill.md` berbeda dari
   implementasi, perbedaannya ditulis eksplisit di kolom *Diskrepansi* — tidak
   dirapikan diam-diam dan tidak dijadikan alasan mengubah rumus.
2. Tidak ada KPI baru yang dikarang. Tujuh metrik yang ada (`METRIC_NAMES` di
   `backend/app/services/kpi_service.py:41-49`) adalah daftar tertutup; urutannya
   diasersi di akhir `compute_kpis` (`kpi_service.py:476`).
3. Semua metrik berbentuk *state machine kecil*: `available` / `no_data` /
   `unavailable` + `reason`. Nilai nol hanya sah bila memang terukur nol —
   tidak boleh dipakai sebagai pengganti "belum ada data"
   (`kpi_service.py:52-73`).

---

## 1. Konvensi global

| Aspek | Kontrak aktual | Bukti |
|---|---|---|
| Endpoint | `GET /kpi?start=<RFC3339>&end=<RFC3339>[&location_id=]` | `backend/app/api/kpi.py:27-33` |
| Bentuk rentang | Setengah terbuka `[start, end)` untuk semua metrik, **kecuali** Meal Continuity yang memakai tanggal rencana dengan kedua ujung inklusif | `kpi_service.py:89-94`, `_plan_date_range` |
| Zona waktu | Timestamp wajib berzona (naive → 422) | `api/kpi.py:41-45` |
| Batas rentang | `start < end`, maksimum 366 hari | `api/kpi.py:46-52` |
| Scope SPPG | Hanya lokasi sendiri; `location_id` lain → 403; user tanpa lokasi → 403 | `api/kpi.py:54-67` |
| Scope `bgn_monitor` | Global bila `location_id` tidak dikirim, atau lokasi mana pun | `api/kpi.py:55-56` |
| Sumber | Agregasi langsung dari tabel fakta (`data_source: live_aggregate`), tanpa cache/snapshot | `api/kpi.py:77` |
| Envelope | `period`, `scope`, `computed_at`, `data_source`, `metrics[7]` | `api/kpi.py:70-79` |
| Per metrik | `name`, `unit`, `state`, `value`, `reason`, `sample_count`, `coverage`, `previous_value`, `trend` | `kpi_service.py:52-66` |

`value` dan `coverage` dikirim sebagai **string** hasil `quantize2` (dua desimal),
bukan float — jangan mengubahnya menjadi angka di klien tanpa alasan.

`previous_value`/`trend` selalu `null`: belum ada perbandingan periode sebelumnya
di backend. Kalau UI butuh tren, itu fitur baru, bukan angka yang boleh dikarang.

---

## 2. Kamus tujuh KPI

Untuk tiap metrik: definisi bisnis, rumus yang **benar-benar dijalankan**,
sumber data, filter, perilaku saat kosong, dan diskrepansi terhadap `docs/Skill.md`.

### 2.1 Meal Continuity Rate — `percent`

- **Definisi bisnis:** seberapa besar rencana porsi menu terpenuhi oleh porsi yang
  benar-benar dikirim.
- **Rumus (kode):**
  `100 × Σ LEAST(COALESCE(delivered_portions, 0), planned_portions) / Σ planned_portions`
  per baris `menu_plans`; `delivered` = `SUM(delivery_events.delivered_portions)`
  per `menu_plan_id`. Kelebihan kirim dipotong ke nilai rencana (tidak > 100%).
- **Sumbu waktu:** `menu_plans.plan_date` (tanggal rencana, WIB), **bukan**
  `delivered_at` dan bukan `created_at`. Kedua sisi (pembilang & penyebut) memakai
  sumbu yang sama; batas atas inklusif.
- **Sumber:** `menu_plans` ⋈ `delivery_events` (agregat per `menu_plan_id`).
- **Filter lokasi:** `menu_plans.location_id`.
- **`sample_count`:** jumlah `menu_plans` pada jendela (`plan_days`). `coverage` = 1.
- **Jendela kirim (26 Okt 2026, keputusan owner opsi b):** rencana yang jendela
  kirimnya belum tiba TIDAK masuk penyebut. Batasnya `tanggal_kiriman_terakhir(end)`:
  tanggal WIB hari ini bila `end` sudah lewat 14.00 UTC (21.00 WIB), selain itu
  kemarin. Pengecualian: bila rencana itu sudah punya baris `delivery_events`,
  ia tetap dinilai (data mengalahkan jam). Tanpa aturan ini, pagi hari metrik
  terbaca `0,00%` padahal kiriman hari itu memang belum berjalan.
- **Kosong:** `no_data` dengan tiga alasan berbeda — (a) ada menu plan tetapi
  total porsi rencana 0 ("penyebut nol, bukan data hilang"), (b) tidak ada menu
  plan, (c) rencana ada tetapi belum masuk jendela kirim ("belum ada yang bisa
  dinilai").
- **Diskrepansi:** `docs/Skill.md:66` menulis "menu terpenuhi **aman**"; kode tidak
  memfilter `safety_status` sama sekali. Angka ini mengukur kuantitas, bukan
  keamanan pangan. Jangan menyebutnya "porsi aman" di UI.

### 2.2 Avoidable Food Loss — `percent`

- **Definisi bisnis:** bagian makanan yang terbuang dibanding total makanan yang
  masuk pada periode itu.
- **Rumus (kode):** `100 × disposed_kg / (disposed_kg + supply_kg)`
  - `disposed_kg` = `SUM(disposal_events.quantity_kg)` dengan `disposed_at ∈ [start,end)`
  - `supply_kg` = `SUM(supply_records.quantity_kg)` dengan `recorded_at ∈ [start,end)`
- **Sumber:** `disposal_events`, `supply_records`.
- **Filter lokasi:** `location_id` pada kedua tabel.
- **`sample_count`:** jumlah baris `disposal_events` yang dipakai.
- **Kosong:** `disposed_kg = 0` dan `supply_kg > 0` → `no_data`
  ("tidak ada disposal event"), **bukan 0%**; keduanya nol → `no_data` "penyebut nol".
  Metrik ini hanya `available` bila ada buangan nyata.
- **Diskrepansi:** `docs/Skill.md:67` membatasi pada "batch yang **tidak
  teralokasikan** padahal **freshness masih lolos**". Kode tidak memakai kriteria
  alokasi/freshness — ia memakai semua `disposal_events`. Konsekuensi yang harus
  disadari saat demo: angka bisa naik karena pembuangan yang sah (mis. gagal uji),
  bukan hanya karena pemborosan.

### 2.3 Regional Imbalance Resolution Rate — `percent`

- **Definisi bisnis:** persentase kasus ketidakseimbangan (surplus/shortage) yang
  terdeteksi dan berhasil diselesaikan.
- **Rumus (kode):**
  - Denominator: **root case** yang punya jejak `agent_traces.step_name='DETECT'`
    dengan `step_at ∈ [start,end)`, `decisions.demo_case IS NULL`, setelah rantai
    `supersedes_id` diruntut ke akarnya (`resolve_root`) dan didedupe.
  - Pembilang: root yang punya anggota berstatus `executed`.
- **Sumber:** `decisions` ⋈ `agent_traces` (`step_name='DETECT'`).
- **Filter lokasi:** `decisions.source_location_id` **atau** `target_location_id`.
- **Kosong:** tidak ada DETECT → `no_data` "tidak ada DETECT pada periode ini".
- **Catatan:** keputusan ber-`demo_case` (kasus skrip demo) sengaja dikeluarkan dari
  metrik ini agar dataset panggung tidak menggeser angka operasional.
- **Diskrepansi:** `docs/Skill.md:68` hanya menyebut "status = executed dalam
  window". Kode menambahkan dedupe lineage dan pengecualian `demo_case`; keduanya
  memperbaiki, bukan mengubah, definisi bisnis.

### 2.4 Safe Delivered Cost — `IDR`

- **Definisi bisnis:** biaya rata-rata per pengiriman yang aman.
- **Rumus (kode):** `mean(decisions.safe_delivered_cost)` untuk keputusan yang
  punya baris `sap_mock_purchase_orders` dengan `po.created_at ∈ [start,end)` dan
  `safe_delivered_cost IS NOT NULL`.
- **Jangkar waktu:** `po.created_at` (komitmen eksekusi), **bukan**
  `decisions.created_at` dan bukan `decisions.status='executed'`.
- **Filter lokasi:** `source_location_id` atau `target_location_id` keputusan.
- **Kosong:** `no_data` "tidak ada batch terkirim yang punya biaya pada periode ini".
- **Diskrepansi:** `docs/Skill.md:69` menyebut "semua decisions yang **executed**".
  Kode memakai keberadaan PO sebagai bukti komitmen, tanpa memeriksa status. Dalam
  praktik keduanya hampir selalu sama, tetapi bila ada PO yang keputusannya bukan
  `executed` (mis. dibatalkan), angka ini tetap memuatnya. Perlu keputusan owner:
  samakan dokumen atau tambahkan filter status.

### 2.5 Procurement Price Deviation — `percent`

- **Definisi bisnis:** seberapa jauh harga kutipan pemasok menyimpang dari harga
  referensi (PIHPS) pada lokasi + komoditas yang sama.
- **Rumus (kode):** untuk tiap `price_signals` dengan `source='supplier_quote'` dan
  `recorded_at ∈ [start,end)`, cari `pihps_reference` terakhir dengan
  `recorded_at <= waktu kutipan` untuk lokasi+komoditas yang sama, lalu
  `|quote − reference| / reference × 100`; hasil di-*mean* (magnitudo absolut).
- **Sumber:** `price_signals` (`supplier_quote` dan `pihps_reference`).
- **Filter lokasi:** `price_signals.location_id` pada kutipan.
- **Eksklusi jujur:** kutipan tanpa pasangan referensi **dibuang dari sampel**
  (tidak dihitung 0%).
- **Kosong:** dua alasan berbeda — kutipan ada tetapi tanpa referensi ("penyebut
  nol") vs tidak ada kutipan sama sekali.
- **Diskrepansi:** tidak ada; konsisten dengan `docs/Skill.md:70`.

### 2.6 Decision Time — `minutes`

- **Definisi bisnis:** berapa lama dari deteksi masalah sampai tindakan tercatat.
- **Rumus (kode):** per keputusan, `MAX(step_at | ACT) − MIN(step_at | DETECT)`
  dalam menit; dirata-rata hanya untuk keputusan yang ACT-nya **committed**
  (punya PO dengan `created_at ∈ [start,end)`).
- **Sumber:** `decisions` ⋈ `agent_traces`; komitmen dari `sap_mock_purchase_orders`.
- **Filter lokasi:** `source_location_id` atau `target_location_id`.
- **Keputusan demo ikut dihitung (26 Okt 2026):** filter `demo_case IS NULL`
  DIHAPUS. Dulu metrik ini membuang kartu demo tanpa catatan, sehingga mustahil
  bergerak saat kartu dieksekusi di panggung, padahal trace dan PO-nya nyata.
  Regional Imbalance tetap mengecualikan `demo_case`.
- **`coverage`:** `sampel / eligible`, dengan `eligible` = keputusan yang punya
  jejak DETECT pada jendela. Ini penting: rata-rata hanya mencakup yang committed.
- **Kosong:** dua alasan — ada DETECT tetapi belum ada ACT committed ("penyebut
  nol"), atau tidak ada DETECT sama sekali.
- **Catatan:** `agent_traces.step_at` untuk satu putaran ditulis dalam satu
  transaksi sehingga bisa identik/lebih awal dari `decisions.created_at`; ratanya
  tetap sah sebagai durasi proses, tetapi jangan dipakai mengurutkan langkah.

### 2.7 Evidence Completeness — `percent`

- **Definisi bisnis:** persentase keputusan yang buktinya lengkap **sebelum**
  keputusan disetujui.
- **Rumus (kode):**
  - Cutoff = `MIN(approved_at)` dengan `approved IS TRUE` (approval pertama).
  - Pembilang: keputusan dengan ≥ 2 `evidence_type` **berbeda**, `is_consistent=true`,
    `recorded_at < cutoff`.
  - Denominator: keputusan pada jendela (`created_at ∈ [start,end)`) yang punya
    minimal satu approval.
- **Sumber:** `decisions`, `approvals`, `decision_evidence`.
- **Filter lokasi:** `source_location_id` atau `target_location_id`.
- **`coverage`:** `denominator / seluruh keputusan pada jendela`.
- **Kosong:** (a) tidak ada keputusan pada jendela, (b) ada keputusan tetapi belum
  satu pun disetujui — tanpa approval tidak ada cutoff, jadi tidak bisa dinilai.
- **Diskrepansi:** tidak ada; sesuai `docs/Skill.md:72` plus penajaman cutoff dan
  denominator (audit 16 Okt 2026).

---

## 3. Definisi periode (kontrak yang DITEGAKKAN sejak 25 Oktober 2026)

Sebelum langkah ini rentang dihitung klien (`frontend/lib/kpi.ts`) sebagai jam
bergulir — 24 jam dan 168 jam — sehingga "hari ini" bukan hari kalender. Sekarang
klien hanya mengirim **kunci** periode dan backend menghitung rentangnya sendiri
(`backend/app/core/kpi_period.py`, dipakai `GET /kpi?periode=…`).

| Kunci | Label UI | Rentang | Zona | Status |
|---|---|---|---|---|
| `today` | Hari ini | `[00:00 hari ini, sekarang]` | Asia/Jakarta | **Sudah** — dihitung server |
| `7d` | 7 hari | `[00:00 H−6, sekarang]` (7 tanggal kalender, termasuk hari ini) | Asia/Jakarta | **Sudah** — dihitung server |
| `1bulan` | 1 bulan | `[00:00 tanggal 1 bulan berjalan, sekarang]` | Asia/Jakarta | **Sudah** — dihitung server |

Kontrak API:

- `GET /kpi?periode=today|7d|1bulan` — rentang dari server. Envelope `period`
  memuat `key`, `label`, `timezone`, `start`, `end`.
- `GET /kpi?start=…&end=…` tetap diterima untuk tes batas dan klien lama.
- Mengirim `periode` **dan** `start/end` sekaligus → 422 (ambigu, bukan dipilih
  diam-diam). Tanpa keduanya → 422.

Aturan pelaksanaan:

1. Batas hari memakai `Asia/Jakarta`, bukan UTC: 31 Okt 20.00 UTC = 1 Nov WIB.
2. `end` selalu `now` — KPI tidak menghitung fakta yang belum terjadi.
3. Semua kartu, tabel, grafik, dan ringkasan memakai fungsi periode yang **sama**
   (`resolve_periode` di server); label bulan tetap dari `periodeBulan`.
4. Tidak ada cache jangka panjang; `computed_at` dikirim agar UI bisa menyatakan
   kesegaran data.
5. Uji yang sudah ada: `backend/tests/test_kpi_period.py` (batas tengah malam,
   konversi UTC→WIB, pergantian bulan, akhir Februari, kunci tak dikenal) dan
   tes API di `backend/tests/test_kpi_api.py` (envelope + tiga kasus 422).

**Catatan konsistensi yang masih terbuka:** feed rekomendasi (`lib/decisions-window.ts`)
memakai kunci sendiri (`24h`/`7d`/`30d`) dengan arti "24 jam bergulir" untuk
"Hari ini". Artinya tombol "Hari ini" di feed dan di KPI belum tentu menunjuk
jendela yang sama. Ini sengaja tidak diubah pada langkah ini (menyentuh filter feed
= perubahan perilaku terpisah) dan harus diselaraskan sebelum laporan akhir.


---

## 4. State machine

### 4.1 Sesi demo

Model: `demo_sessions` (`backend/app/models/demo_sessions.py`), CHECK
`status IN ('active','expired','ended')`.

```
        POST /demo/session/start
                 │  (template dibangun DULU, sesi dibuka BELAKANGAN)
                 ▼
   ┌─────────► active ──────────────┐
   │             │                  │ expires_at <= now()      → expired
   │             │ POST /demo/session/end                      → ended
   │             ▼
   └──── (sesi lama diakhiri lebih dulu)  expired / ended ──┐
                                                            ▼
                                          POST /demo/session/start (baru)
```

- **Batas waktu:** `expires_at = started_at + menit`, bawaan 120 menit
  (`core/config.py:34`, `services/demo_session.py:230-238`).
- **Plafon absolut 2 jam:** `_batas_akhir(started_at) = started_at +
  DEMO_SESSION_MAX_MINUTES` (120). Dipakai START **dan** EXTEND: mulai 110 menit
  lalu minta extend 240 menit tetap berhenti di 120 menit. `extend` hanya
  menambal sampai plafon, tidak pernah melewatinya.
- **Kedaluwarsa dinilai malas** saat ada request membaca status (`aktif()`,
  `services/demo_session.py:191-206`), bukan cron/timer proses. Status tetap benar
  sesudah restart karena berasal dari kolom `expires_at` di DB.
- **Satu sesi aktif dijamin DATABASE:** unique partial index
  `uq_demo_sessions_satu_aktif` pada `demo_sessions(status) WHERE status='active'`
  (migrasi `032_satu_sesi_aktif`, model `DemoSession`). Sebelumnya hanya
  `asyncio.Lock` satu proses + "akhiri sesi lama" di kode, sehingga dua worker
  bisa membuka dua jendela aktif. Riwayat `expired`/`ended` tidak dibatasi.
- **Penjaga mutasi MENYALA sebagai bawaan** (`DEMO_SESSION_ENFORCE=true` sejak
  25 Okt 2026). Middleware `_konteks_sesi_demo` menolak **409** untuk metode
  POST/PUT/PATCH/DELETE ketika tidak ada sesi aktif, kecuali jalur pengelola sesi
  (`/demo/session/start|extend|end`), `/auth/login`, `/health`, dan dokumentasi.
  Pembacaan (GET) tetap terbuka. Endpoint `/demo/session/start` adalah satu-satunya
  jalan masuk: ia membangun template lalu membuka sesi.

**Siklus data yang mengiringi status** (`services/demo_session.py`):

| Kejadian | Yang dihapus | Yang bertahan |
|---|---|---|
| Sesi mulai (mode enforce) | seluruh baris operasional sebelum template dibangun (`kosongkan_kecuali`) | master data, ledger (hanya `bump_generation`) |
| Sesi berakhir/kedaluwarsa | baris ber-`demo_session_id` dengan `origin='demo'` + baris `origin='demo'` tanpa stempel | `origin='seed'` (kanonik), users/locations/commodities/suppliers |
| `/demo/template/rebuild` | sama seperti di atas, lalu template dibangun ulang | jendela sesi **tidak** ditutup |
| Tidak ada sesi aktif | baris `origin='demo'` tanpa stempel (sapuan dijeda 10 dtk) | semua baris `origin='seed'` |

Kosakata `origin` dibatasi CHECK constraint: `seed|demo` (jangan menambah label baru
untuk membedakan sesi — pembedanya adalah `demo_session_id`).

### 4.2 Keputusan (decision)

CHECK constraint: `proposed | verifier_flagged | pending_approval | approved |
rejected | executed | review_only` (`models/decisions.py:46-50`).

```
POST /decisions ──────────────► proposed
actions/repropose ────────────► proposed (pengganti yang kedaluwarsa, supersedes_id)
POST /actions/propose ────────► pending_approval        [butuh status proposed|verifier_flagged]
POST /actions/verify (FLAGGED)► verifier_flagged        [CONSISTENT tidak mengubah status]
POST /actions/approve (tolak) ► rejected                [wajib comment]
kuorum approval terpenuhi ────► approved
POST /actions/execute ────────► executed                [butuh kuorum + verdict + belum kedaluwarsa]
Event 2 (safety disruption) ──► review_only             [tidak bisa di-approve/execute]
```

Penjaga yang berlaku saat `execute` (`api/actions.py:703-766`):

1. `review_only` ditolak lebih dulu (pesannya bukan "belum terverifikasi").
2. `executed` → 409 "decision sudah dieksekusi" (idempotensi).
3. Verdict verifier wajib `consistent`/`flagged`; `unavailable` = belum dinilai.
4. `expires_at` lewat → 409.
5. Status harus `pending_approval`/`verifier_flagged`/`approved`.
6. Kuorum approval diperiksa **dua kali**: global dan ter-scope ke
   `target_location_id`.
7. Safety/freshness batch sumber divalidasi ulang saat eksekusi
   (`services/supplier_eligibility.revalidate_transfer`, safety gate).

### 4.3 Approval (empat mata)

Matriks (`backend/app/core/approval_matrix.py`):

| Verdict verifier | Tipe keputusan | Requirement |
|---|---|---|
| `consistent` | administrasi (supplier exclusion/restoration) | 1 approval: `sppg_head` **atau** `sppg_nutritionist` |
| `flagged` / `unavailable` | administrasi | 2 approval: `sppg_head` **dan** `sppg_nutritionist` |
| apa pun | operasional (transfer, procurement, safety, price) | 2 approval: `sppg_head` **dan** `sppg_nutritionist` (`dua_role_wajib=True`, `api/actions.py:104-112`) |

Aturan tambahan:

- `bgn_monitor` tidak pernah dihitung sebagai approver (`APPROVER_ROLES`).
- Satu akun = satu approval per keputusan (unique index migrasi 030, ditangani
  sebagai 409 `IntegrityError`, `api/actions.py:577-591, 670-679`).
- Satu penolakan menggugurkan seluruh kuorum (`rejected` → status `rejected`).
- Approval dari lokasi lain tidak dihitung saat eksekusi (`api/actions.py:757-766`).
- Approve atas keputusan yang belum diverifikasi ditolak 409; rejection tetap boleh.
- Kuorum penuh mengubah status ke `approved` — tetapi **`approved` bukan
  "dikirim"**: PO, batch berangkat, dan status perjalanan lahir di `execute`.

### 4.4 Pengiriman (journey) — dihitung, bukan disimpan

Sumber: `backend/app/core/journey.py`; dipakai `api/supplier_routes.py`
(`journey_states`).

| State | Syarat |
|---|---|
| `belum_berangkat` | `batches.dispatched_at IS NULL` (atau masih di depan) |
| `di_jalan` | sudah berangkat, `eta = dispatched_at + road_routes.duration_s` masih di depan |
| `sudah_tiba` | sekarang ≥ `eta` |
| `tidak_diketahui` | sudah berangkat tetapi durasi rute belum ada — **tidak** diklaim "di jalan" |

- Tidak ada kolom status perjalanan di DB; semuanya aritmetika atas data yang ada.
- `execute` yang menulis `batches.dispatched_at` (`api/actions.py:882` →
  `_dispatch_bound_batches`, baris 280-343) adalah satu-satunya pemicu sah
  munculnya truk.
- **Tidak semua batch terikat berangkat.** `_dispatch_bound_batches` menyaring
  lewat `batch_blokir_eksekusi` (safety_status, quarantine_status, usable_until,
  suhu); batch yang gagal tetap `dispatched_at IS NULL` dan dilaporkan di respons
  sebagai `ditahan` beserta alasannya. Animasi/overview tidak boleh menggambar
  batch yang ditahan sebagai truk.
- Label UI: `STATE_LABELS` ("Belum berangkat", "Di jalan", "Sudah tiba",
  "Perjalanan belum bisa dipastikan").
- **Konsekuensi untuk animasi:** tahap "Disiapkan" tidak punya sumber data hari ini
  (tidak ada state antara `approved` dan `dispatched_at`). Animasi bertahap hanya
  boleh memakai `approved → executed (berangkat) → di_jalan → sudah_tiba`, dan
  tahap terakhir hanya setelah `eta` lewat — bukan segera setelah klik.

### 4.5 Notifikasi (lonceng)

**Definisi yang berlaku: daftar tugas yang menunggu tindakan manusia, bukan pesan
belum dibaca.** Tidak ada tabel notifikasi di DB dan tidak ada kode notifikasi di
backend; seluruh isinya diturunkan dari `GET /decisions` di klien
(`frontend/lib/topbar.ts`).

| Kelompok | Aturan |
|---|---|
| Dihitung (`total`) | status `PENDING_APPROVAL`, `APPROVED`, `VERIFIER_FLAGGED` (`ACTIONABLE_STATUSES`, baris 39-43); plus `PROPOSED` **hanya** untuk `sppg_head` (baris 129-136) |
| Tidak dihitung | `EXECUTED`, `REJECTED`, `REVIEW_ONLY` (tidak menuntut tindakan) |
| Dipisah | `expired` = menunggu tindakan tetapi lewat tenggat (backend menolak 409); `draft` = `proposed` yang kedaluwarsa |
| Tampil | maksimum `NOTIF_LIMIT = 5` baris, terbaru dulu; sisa dilaporkan sebagai `rest` |
| Read-state | **tidak ada** — dan tidak relevan selama definisinya "tugas menunggu". "Sudah ditangani" = status keputusan berubah |
| Reset demo | tidak ada baris notifikasi untuk direset; isinya ikut berubah karena keputusan ikut berubah |

Implikasi terhadap permintaan "notifikasi setelah approve/execute": tidak ada
mekanisme notifikasi peristiwa. Badge berubah semata karena status keputusan
berubah. Kalau owner menginginkan riwayat notifikasi (mis. "pengiriman berangkat"),
itu fitur baru: tabel + migrasi + endpoint + aturan reset, dan definisinya harus
dipisahkan dari badge tugas.

---

## 5. Peta KPI ↔ tindakan demo (apa yang mengubah angka apa)

| Tindakan (nyata, lewat API) | Tabel yang berubah | KPI yang bergerak |
|---|---|---|
| `POST /actions/propose` | `decisions.status` → `pending_approval` | — (belum ada angka) |
| `POST /actions/verify` | `decisions.verifier_note`, `agent_traces` VERIFY | — |
| `POST /actions/approve` (1/2) | `approvals`, `ledger_blocks`, status | Evidence Completeness (cutoff approval muncul), Decision Time (belum committed) |
| `POST /actions/approve` (2/2) | status → `approved` | idem |
| `POST /actions/execute` | `decisions.status` → `executed`, `sap_mock_purchase_orders`, `batches.dispatched_at`, `agent_traces` ACT, ledger | Safe Delivered Cost, Decision Time (committed), Regional Imbalance Resolution, dan truk muncul di peta |
| `road_routes.duration_s` lewat waktu | (tidak ada tulis) | journey `di_jalan` → `sudah_tiba` |
| `POST /receipts` + `/safety/evaluate` | `batch_receipts`, `batches.safety_status` | Meal Continuity (bila porsi terkirim berubah), Avoidable Food Loss (bila dibuang) |
| `POST /price/*` | `price_signals` | Procurement Price Deviation |
| `menu_plans` + `delivery_events` | fakta rencana/kiriman | Meal Continuity |

Aturan yang tidak boleh dilanggar saat demo: KPI **tidak** boleh dinaikkan dari
frontend, tidak boleh menghitung satu event dua kali, tidak boleh mencampur data
luar scope, dan **keputusan `approved` tidak boleh disebut "terkirim"**.

### 5.1 Kartu "hari ini" vs riwayat aksi (diperbaiki 25 Okt 2026)

Penyemai demo menggeser jejak AKSI Jakarta ke luar jendela 24 jam supaya panel
KPI mulai dari "belum ada aksi hari ini" (`app/seed/demo_kpi_riwayat.py`).
Sampai 25 Oktober penggeseran itu ikut memindahkan `decisions.created_at` untuk
SEMUA status, sehingga keempat kasus skrip template mendarat di kemarin dan feed
"Rekomendasi hari ini" tinggal 2–3 kartu — bertabrakan dengan permintaan lima
rekomendasi valid.

Aturan sekarang: status `pending_approval` dan `verifier_flagged` **tidak**
digeser (kartunya tetap hari ini, bisa ditindak); jejak aksinya (`agent_traces`,
`decision_evidence`, `approvals`, `sap_mock_purchase_orders`) tetap digeser, jadi
metrik berbasis aksi tetap mulai dari nol. Status lain tetap digeser seluruhnya:
`approved`/`executed`/`rejected`/`review_only` sudah pernah ditindak, `proposed`
masih draf agen. Terukur (Jakarta, 26 Okt 19.32 WIB, sesudah rebuild kanonik): 14 kartu di jendela 24 jam, 12 di antaranya bisa ditindak
(9 `pending_approval`, 2 `verifier_flagged`) atas 5 skenario unik, dan keenam KPI
berbasis aksi tetap `no_data`.

### 5.2 Template demo kini menyemai deret waktu (26 Okt 2026)

Temuan: `build_into` (tombol "Siapkan data demo") hanya memanggil `load_seed`,
yang menulis tujuh hari fakta. Dataset hasilnya jauh lebih tipis daripada
`init-demo`, dan tidak ada rencana menu untuk hari ini — Meal Continuity hanya
bisa `no_data`, grafik riwayat nyaris kosong.

Perbaikan: `build_into` memanggil `generate_timeseries()` sesudah data kanonik
`load_seed` (dengan `commit` lebih dulu, karena generator memakai koneksi
sendiri dan membaca baris kanonik sebagai jangkar) dan sebelum kasus skrip.
Angka sesudah perbaikan: `menu_plans` 660 (1 Sep–5 Nov), `supply_records` 5.240
(1 Sep–4 Nov), `demand_records` 1.360, `price_signals` 5.924, `delivery_events`
180 (8–25 Okt), `disposal_events` 80. Kegagalan generator dilaporkan sebagai
`{"gagal": ...}` di laporan build, bukan ditelan.

Sisa konsekuensi yang BELUM diputuskan: Meal Continuity "hari ini" bernilai
0,00% pada pagi hari, karena rencana menu hari ini ada tetapi kiriman hari ini
belum ditulis (aturan generator: kiriman hari ini baru terjadi setelah 21.00
WIB). Lihat §7.

---

## 6. Ringkasan bukti kode

| Objek | Berkas |
|---|---|
| Endpoint KPI + validasi rentang | `backend/app/api/kpi.py` |
| Periode hari kalender (server) | `backend/app/core/kpi_period.py` |
| Rumus 7 KPI + state metric | `backend/app/services/kpi_service.py` |
| Jendela periode (klien) | `frontend/lib/kpi.ts` |
| Sesi demo (service) | `backend/app/services/demo_session.py` |
| Sesi demo (router) | `backend/app/api/demo_session.py` |
| Model sesi | `backend/app/models/demo_sessions.py` |
| Approval matrix | `backend/app/core/approval_matrix.py` |
| Approve/execute | `backend/app/api/actions.py` |
| Status keputusan (CHECK) | `backend/app/models/decisions.py` |
| Journey pengiriman | `backend/app/core/journey.py`, `backend/app/api/supplier_routes.py` |
| Notifikasi (turunan) | `frontend/lib/topbar.ts` |
| Definisi KPI di dokumen | `docs/Skill.md` §4, `docs/PRD.md` |

---

## 7. Keputusan terbuka (butuh persetujuan owner sebelum kode berubah)

1. **Perpanjangan sesi vs batas 2 jam — SELESAI (25 Okt 2026).** Plafon absolut
   120 menit dipakai START dan EXTEND (`_batas_akhir`), jadi `extend` hanya
   menambal sampai 2 jam. Kalau kelak produk menghendaki sesi lebih panjang,
   ubah `DEMO_SESSION_MAX_MINUTES` — satu angka, bukan dua jalur berbeda.
2. **Enforcement sesi — SELESAI (25 Okt 2026).** `DEMO_SESSION_ENFORCE=true`
   sebagai bawaan; middleware menolak mutasi 409 tanpa sesi aktif. Suite tes
   mematikannya eksplisit di `tests/conftest.py` (bukan default produk) dan
   berkas destruktif `test_demo_session.py` butuh opt-in
   `DEMO_SESSION_TESTS_ENFORCE=1` + DB sekali-pakai.
3. **Notifikasi.** Tetap "daftar tugas menunggu" (tanpa read-state, tanpa tabel),
   atau naikkan menjadi notifikasi peristiwa (tabel + migrasi + aturan reset).
4. **Animasi overview.** Tahap yang didukung data hari ini hanya `approved`,
   `executed` (berangkat), `di_jalan`, `sudah_tiba`. Tahap "Disiapkan" butuh sumber
   data baru; jangan ditampilkan sebelum ada bukti di DB.
5. **Safe Delivered Cost.** Dokumen menyebut "executed", kode memakai keberadaan PO.
   Samakan salah satu sebelum laporan akhir.
6. **Meal Continuity pada pagi hari — SELESAI (26 Okt 2026, opsi b).** Rencana
   yang jendela kirimnya belum tiba dikeluarkan dari penyebut
   (`tanggal_kiriman_terakhir`), kecuali sudah ada kiriman tercatat. Terukur
   sesudah perubahan: `today` = 100,00% (1 sampel, rencana 25 Okt), `7d` =
   100,00% (7), `1bulan` = 98,47% (26) — bukan lagi 0,00% pagi hari.
7. **Decision Time & kartu demo — SELESAI (26 Okt 2026).** Filter `demo_case IS
   NULL` pada Decision Time dihapus (tidak pernah tercatat di kamus KPI dan
   membuat metrik mati saat kartu demo dieksekusi). Trace DETECT/PREDICT/DECIDE
   milik kartu demo yang tetap hari ini ikut dipertahankan; trace kartu non-demo
   tetap digeser supaya Regional Imbalance tidak berubah. Terukur: approve×2 →
   execute satu kartu `shortage-darurat` mengubah Decision Time `—` (7 eligible)
   → 20,98 menit (1 sampel), bersama Safe Delivered Cost, Price Deviation, dan
   Evidence Completeness.
8. **Regional Imbalance tidak bisa digerakkan kartu demo.** Metrik ini masih
   mengecualikan `demo_case` (aturan anti-noise). Kalau owner ingin angka ini
   bergerak di panggung, keputusannya adalah menghapus pengecualian itu — bukan
   menambah data.
9. **Animasi kiriman & notifikasi — terverifikasi 26 Okt 2026.** `execute`
   memberi `batches.dispatched_at` (5 batch dalam 30 menit); `GET
   /supplier-routes` mengembalikan 12 rute dengan `di_jalan` 6, `sudah_tiba` 5,
   `tidak_diketahui` 1, dan `journey.progress` NAIK pada 6/6 rute dalam 8 detik
   (0,521→0,527 dst.) — sumber gerak mobil di Overview. Lonceng notifikasi turun
   dari 12 menjadi 9 baris siap tindak setelah tiga kartu dieksekusi.
   *Catatan pengukuran ulang 26 Okt 2026: `di_jalan` 0, `sudah_tiba` 11,
   `tidak_diketahui` 1 — semua rute pendek sudah tiba sejak data dibangun pukul
   09.57. Ini bukti status perjalanan dihitung dari jam, bukan label statis; untuk
   melihat truk bergerak, siapkan data tepat sebelum tampil. Snapshot:
   `docs/state-snapshot.md`.*
