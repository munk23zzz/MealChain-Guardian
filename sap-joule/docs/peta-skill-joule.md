# Peta skill Joule → endpoint backend → data demo

Dokumen ini menjawab satu pertanyaan: **untuk setiap jawaban yang bisa diberikan jembatan A2A
lewat chat Joule, endpoint mana yang dibaca, tabel/kolom mana yang harus berisi data, dan
seperti apa jawaban yang keluar.** Dipakai oleh pembangun data demo supaya "tanya apa saja di
Joule, jawabannya bermakna" bisa direncanakan, bukan ditebak.

Sumber kebenaran (dibaca langsung, bukan dari ingatan):

- `a2a_server/server.py` — konstanta `SKILL_*`, tabel `_KEYWORDS`, `resolve_skill()`,
  `render_skill()`, dan `agent_card()`.
- `a2a_server/mealchain_client.py` — pemetaan metode klien → path HTTP backend.
- `a2a_server/report.py` — kolom dan kalimat yang benar-benar dirender.
- `joule/mealchain_capability/scenarios/*.yaml` — deskripsi NLU yang dibaca Joule.

Diperbarui: 22 Okt 2026 (versi capability `1.4.0`).

---

## 1. Ringkasan audit: skill jembatan vs scenario Joule

Jembatan mendefinisikan **15 konstanta** skill, tetapi hanya **14** yang masuk tuple `SKILLS`
dan ditawarkan di agent card (`/.well-known/agent-card.json`). `unsupported_domain` sengaja
tidak ditawarkan: jawabannya "domain ini belum tersedia", bukan data.

| # | Skill (`SKILLS`) | Scenario sebelum 22 Okt | Scenario sesudah | Status |
|---|---|---|---|---|
| 1 | `supply_situation` | `situasi_pasokan.yaml` | `situasi_pasokan.yaml` | ada (juga default) |
| 2 | `kpi_snapshot` | `indikator_kinerja.yaml` | `indikator_kinerja.yaml` | ada |
| 3 | `approval_queue` | `antrean_usulan.yaml` | `antrean_usulan.yaml` | ada |
| 4 | `purchase_order` | `detail_purchase_order.yaml` | `detail_purchase_order.yaml` | ada |
| 5 | `supplier_directory` | **tidak ada** | `direktori_pemasok.yaml` | **baru** |
| 6 | `price_intelligence` | `harga_pemasok.yaml` | `harga_pemasok.yaml` | ada |
| 7 | `demand_forecast` | `kebutuhan_prakiraan.yaml` | `kebutuhan_prakiraan.yaml` | ada |
| 8 | `food_loss` | `kehilangan_pangan.yaml` | `kehilangan_pangan.yaml` | ada |
| 9 | `supplier_risk` | `risiko_pemasok.yaml` | `risiko_pemasok.yaml` | ada |
| 10 | `receipts_queue` | **tidak ada** | `antrean_penerimaan.yaml` | **baru** |
| 11 | `quarantine_status` | **tidak ada** | `status_karantina.yaml` | **baru** |
| 12 | `decision_evidence` | `bukti_keputusan.yaml` | `bukti_keputusan.yaml` | ada |
| 13 | `system_status` | `status_sistem.yaml` | `status_sistem.yaml` | ada |
| 14 | `batch_detail` (29 Okt 2026) | **tidak ada** | `detail_batch.yaml` | **baru** |
| — | `unsupported_domain` (tidak di `SKILLS`) | tidak ada | tidak ada (sengaja) | di luar cakupan Joule |

Sebelum: **10 scenario / 13 skill** → tiga skill (`supplier_directory`, `receipts_queue`,
`quarantine_status`) punya kode dan laporan lengkap di jembatan, tetapi **tidak bisa dipicu
dari chat Joule sama sekali** karena Joule hanya melihat scenario. Setelah 22 Okt: **13 / 13**.
Sesudah 29 Okt: **14 / 14** — `batch_detail` menambahkan rincian keamanan satu batch
(`GET /batches/{id}`) yang sebelumnya tidak bisa dijangkau chat.

Tidak ada scenario yang menunjuk skill yang tidak ada: kesepuluh scenario lama memetakan satu
ke satu ke skill nyata (dikunci `test_semua_scenario_menargetkan_fungsi_yang_sama` dan kini
juga `test_setiap_skill_jembatan_punya_scenario`).

### Yang berubah 22 Okt 2026

- **Berkas baru**: `joule/mealchain_capability/scenarios/direktori_pemasok.yaml`,
  `antrean_penerimaan.yaml`, `status_karantina.yaml` (gaya sama: `description: >-` prosa
  Inggris 4–6 baris, menyebut SPPG/MBG, menyatakan baca-saja, memuat kata kunci pemicu
  Indonesia + Inggris yang persis sama dengan `_KEYWORDS` di `server.py`).
- **`capability.sapdas.yaml`**: `metadata.version` `1.3.0` → **`1.4.0`**. Ini kenaikan
  **MINOR**, bukan patch: kemampuan yang ditawarkan bertambah tiga domain, dan `description`
  capability ikut menyebut "antrean penerimaan barang" serta "status karantina batch" supaya
  NLU Joule punya kosakata yang sama.
- **`a2a_server/tests/test_kontrak_joule.py`**: daftar scenario yang dikunci bertambah tiga
  nama, dan ada tes baru `test_setiap_skill_jembatan_punya_scenario` yang memetakan
  `set(SKILLS) - {supply_situation}` ke nama scenario. Asersi **menguat** (sebelumnya
  hardcode 10 nama saja; sekarang juga bijection skill→scenario + kata kunci). Tidak ada
  asersi yang dilemahkan.
- **Tidak diubah**: kode backend, skema database, `server.py`, `mealchain_client.py`,
  `report.py`, `agent_card`, dan semua scenario lama.

---

## 2. Peta per skill

Kolom "data minimal" ditulis sebagai syarat yang bisa diperiksa dengan satu query; angka
"sekarang" adalah snapshot backend lokal 22 Okt 2026 (akun `bgn.monitor`, nasional).

### 2.1 `supply_situation` — situasi pasokan (default)

- **Scenario**: `situasi_pasokan.yaml` · **Laporan**: `report.supply_report`
- **Endpoint**: `GET /batches?limit=500`, lalu `GET /balance/map?commodity=<kom>` untuk tiap
  komoditas yang benar-benar ada di batch; `GET /supply/{location_id}/{commodity}` **hanya**
  bila pengguna menyebut satu SPPG + satu komoditas. `GET /health` untuk catatan sumber data.
- **Tabel/kolom yang harus berisi data**:
  - `batches`: `location_id`, `commodity_id`, `quantity_kg`, `safety_status`,
    `freshness_score`, `usable_until` (join `locations.name`, `commodities.name`).
  - `supply_records`: baris terbaru (`recorded_at <= now`) per (`location_id`,`commodity_id`)
    → kolom "Pasokan".
  - `demand_records`: baris terbaru per pasangan yang sama → kolom "Kebutuhan" dan "Selisih".
- **Data minimal**: ≥3 SPPG × ≥2 komoditas punya batch; setiap pasangan yang ingin terlihat
  "seimbang/kurang/lebih" punya satu `supply_records` **dan** satu `demand_records`. Pasangan
  tanpa `demand_records` akan tampil sebagai ketimpangan — itu bukan bug, tapi salah kalau
  tidak disengaja.
- **Contoh pertanyaan**: "Berapa stok beras yang masih bisa dipakai di SPPG Jakarta?"
- **Bentuk jawaban**: dua tabel — `Keseimbangan pasokan per lokasi` (SPPG | Komoditas |
  Pasokan | Kebutuhan | Selisih | Status) dan `Inventaris batch` (SPPG | Komoditas | Jumlah |
  Keamanan | Skor kesegaran | Boleh dipakai sampai), plus baris "Baris pasokan terakhir …"
  bila satu pasangan disebut.
- **Sekarang**: 120 batch, 10 lokasi, 4 komoditas (ayam, beras, telur, wortel).

### 2.2 `kpi_snapshot` — indikator kinerja

- **Scenario**: `indikator_kinerja.yaml` · **Laporan**: `report.kpi_report`
- **Endpoint**: `GET /kpi?start=<ISO>&end=<ISO>` (default jendela **7 hari**, `KPI_DEFAULT_DAYS`).
- **Tabel/kolom**: `menu_plans` (`plan_date`, `planned_portions`) + `delivery_events`
  (`delivered_portions`, `status`, `delivered_at`) → Meal Continuity; `disposal_events`
  (`quantity_kg`, `reason`, `partner_name`, `disposed_at`) → Avoidable Food Loss;
  `decisions` (`decision_type`, `status`, `created_at`, `approved_at`,
  `safe_delivered_cost`, `source/target_location_id`) → imbalance resolution, decision time,
  evidence completeness; `price_signals` (`price_per_kg`, `recorded_at`) → price deviation.
- **Data minimal**: `menu_plans` + `delivery_events` di dalam jendela 7 hari (minimal 3 hari
  berturut), ≥1 `disposal_events` dengan `partner_name` terisi, ≥1 keputusan `executed`
  dengan `safe_delivered_cost` NOT NULL, ≥1 keputusan dengan `approved_at` NOT NULL.
- **Contoh pertanyaan**: "Tampilkan KPI MealChain minggu ini."
- **Bentuk jawaban**: satu tabel `Indikator kinerja MealChain Guardian (7 metrik …)`. Metrik
  yang tidak bisa dihitung tampil `—` **beserta alasannya**, bukan 0.
- **Sekarang**: 7 metrik, **2 di antaranya null beralasan** (jendela sempit). Itu perilaku
  benar; kalau demo butuh 7/7 hijau, data harus lebih rapat dari 7 hari terakhir.

### 2.3 `approval_queue` — antrean usulan keputusan

- **Scenario**: `antrean_usulan.yaml` · **Laporan**: `report.approval_queue_report`
- **Endpoint**: `GET /decisions` lalu `GET /decisions/{id}/approval-summary` (maks 12 detail,
  `DETAIL_LIMIT`). Status yang dianggap "belum tuntas": `proposed`, `pending_approval`,
  `verifier_flagged`, `approved` (`PENDING_STATUSES`).
- **Tabel/kolom**: `decisions` (`decision_type`, `status`, `source_location_id`,
  `target_location_id`, `commodity_id`, `quantity_kg`, `expires_at`); `approvals`
  (`approved_by`, `approved`, `approved_at`).
- **Data minimal**: ≥1 `decisions.status='pending_approval'` dengan `source_location_id`,
  `target_location_id`, `commodity_id` **tidak null** (kalau null, kolom asal→tujuan dan
  komoditas jadi `—`); sebaiknya ≥1 per tipe (rebalancing, price anomaly, food-safety,
  supplier exclusion) supaya kolom "Jenis" beragam.
- **Contoh pertanyaan**: "Usulan keputusan apa yang masih menunggu persetujuan?"
- **Bentuk jawaban**: `Antrean usulan keputusan MealChain Guardian (n baris)` — ID | Jenis |
  Asal → tujuan | Komoditas | Jumlah | Status, dengan catatan tegas bahwa persetujuan
  dilakukan manusia di UI MealChain, tidak lewat Joule.
- **Sekarang**: 35 keputusan; status bervariasi (proposed … review_only).

### 2.4 `purchase_order` — purchase order

- **Scenario**: `detail_purchase_order.yaml` · **Laporan**: `report.purchase_order_report`
- **Endpoint**: `GET /sap/purchase-orders?limit=200`. Nomor PO dikenali dari regex
  `MC-<hex>` (`_PO_NUMBER`) atau kata `PO`/`purchase order`/`pesanan pembelian`
  (`_PO_WORD`), dan diperiksa **sebelum** antrean keputusan.
- **Tabel/kolom**: `sap_mock_purchase_orders` (`po_number`, `status`, `supplier_id`,
  `material_number`, `ordered_quantity`, `price`, `decision_id`, `origin`), join `suppliers`,
  `commodities`, `locations`, `decisions` untuk nama & status keputusan.
- **Data minimal**: ≥1 PO dengan `decision_id` **NOT NULL** dan `origin='execution'`, ≥1 PO
  dengan `decision_id` NULL dan `origin='demo'`, status mencakup `draft`, `submitted`,
  `confirmed`, dan **minimal satu** `po_number` berformat `MC-<12 hex>` untuk demo
  "sebut nomor PO".
- **Contoh pertanyaan**: "Tampilkan PO MC-661695B2C685" · "PO mana yang lahir dari keputusan?"
- **Bentuk jawaban**: tanpa nomor → tabel `Purchase order MealChain Guardian (n PO terbaca)`
  (Nomor PO | Status | Lokasi tujuan | Bahan | Jumlah | Total | Keputusan) + saran menyebut
  nomor; dengan nomor → blok rincian satu PO + asal keputusan.
- **Sekarang**: 16 PO, 4 punya `decision_id`, origin `demo` + `execution`, status
  `submitted`/`confirmed`.

### 2.5 `supplier_directory` — direktori pemasok **(scenario baru)**

- **Scenario**: `direktori_pemasok.yaml` · **Laporan**: `report.supplier_directory_report`
- **Endpoint**: `GET /suppliers?limit=200`. Kata kunci: `pemasok`, `supplier`, `direktori`,
  `vendor` (diperiksa **setelah** `supplier_risk` dan `price`, jadi "harga dari pemasok"
  tetap masuk skill harga).
- **Tabel/kolom**: `suppliers` (`name`, `location_id`, `commodity_id`,
  `reliability_score`, `capacity_kg_per_week`, `certification_status`, `address`,
  `contact_name`), join `locations`/`commodities`; blok "Kiriman aktif" dihitung dari
  `batches` (`supplier_id`, `usable_until >= now`); penanda `excluded_at_hub` dari
  `supplier_exclusions` (`status='active'`, `scope_location_id`).
- **Data minimal**: ≥10 pemasok tersebar di ≥3 SPPG (bukan satu hub saja), `reliability_score`
  dan `capacity_kg_per_week` **tidak null**, ≥1 pemasok tanpa batch aktif (harus tampil
  "belum mengirim", bukan 0), dan — untuk memunculkan penanda — ≥1 `supplier_exclusions`
  aktif yang `scope_location_id`-nya **sama dengan `suppliers.location_id`** pemasok itu.
- **Contoh pertanyaan**: "Pemasok mana yang melayani SPPG Bandung dan berapa kapasitasnya?"
- **Bentuk jawaban**: `Direktori pemasok (n pemasok, dikelompokkan per SPPG)` — Pemasok |
  SPPG | Komoditas | Keandalan | Kapasitas/minggu | Kiriman aktif (`3 batch · 120 kg`,
  `belum mengirim`, atau tambahan `· dikecualikan di hub`).
- **Sekarang**: 60 pemasok, 52 sedang mengirim, **0 penanda "dikecualikan di hub"** —
  lihat temuan §3.1.

### 2.6 `price_intelligence` — harga & kuotasi

- **Scenario**: `harga_pemasok.yaml` · **Laporan**: `report.price_report`
- **Endpoint**: `GET /price/{location_id}/{commodity}` + `GET /price/quotes/{location_id}/{commodity}`
  untuk tiap pasangan (SPPG, komoditas) yang ada di `/batches`. Maks **8 pasangan**
  (`PAIR_LIMIT`) per pertanyaan; sisanya disebut di catatan.
- **Tabel/kolom**: `price_signals` (`location_id`, `commodity_id`, `price_per_kg`,
  `supplier_id`, `recorded_at`, `source`, `origin`). Baris dengan `supplier_id` NULL = harga
  acuan; `supplier_id` terisi = kuotasi pemasok (join `suppliers.name`).
- **Data minimal**: untuk setiap pasangan yang ingin dijawab, ≥1 `price_signals` dengan
  `price_per_kg` > 0 dan `recorded_at` terbaru, plus ≥1 baris `supplier_id` NOT NULL
  (contoh nyata: `/price/quotes` untuk Jakarta/ayam mengembalikan 5 kuotasi).
- **Contoh pertanyaan**: "Berapa harga telur per kg di SPPG Surabaya, dan siapa yang
  mengutipnya?"
- **Bentuk jawaban**: `Harga acuan per SPPG dan komoditas (n pasangan terbaca)` (SPPG |
  Komoditas | Harga per kg | Sumber | Dicatat) + `Kuotasi pemasok terbaru (n kuotasi)`
  (Pemasok | SPPG | Komoditas | Harga per kg | Dicatat). Pasangan tanpa sinyal harga **tidak
  diisi 0**.

### 2.7 `demand_forecast` — kebutuhan & prakiraan

- **Scenario**: `kebutuhan_prakiraan.yaml` · **Laporan**: `report.demand_report`
- **Endpoint**: `GET /demand/{location_id}/{commodity}` + `GET /demand/forecast/{location_id}/{commodity}`,
  maks 8 pasangan (`PAIR_LIMIT`).
- **Tabel/kolom**: `demand_records` (`location_id`, `commodity_id`, `quantity_kg`,
  `needed_by`, `recorded_at`); prakiraan dihitung backend (`method`, `confidence`,
  `forecast_qty_kg`) — jembatan tidak meramal.
- **Data minimal**: ≥1 `demand_records` per pasangan dengan `needed_by` **di masa depan**
  (kalau lewat, baris tetap tampil tetapi tidak berguna untuk demo "kebutuhan mendatang");
  untuk menunjukkan metode non-fallback, model peramal harus aktif — data sekarang memakai
  `statistical_fallback` dengan `confidence 1.0`, dan itu ditampilkan apa adanya.
- **Contoh pertanyaan**: "Berapa kebutuhan beras SPPG Medan sampai akhir minggu ini?"
- **Bentuk jawaban**: `Kebutuhan dan prakiraan per SPPG (n pasangan terbaca)` — SPPG |
  Komoditas | Kebutuhan | Diperlukan sampai | Prakiraan | Metode prakiraan | Keyakinan (0–1).

### 2.8 `food_loss` — kehilangan pangan

- **Scenario**: `kehilangan_pangan.yaml` · **Laporan**: `report.food_loss_report`
- **Endpoint**: `GET /waste/summary?days=30` (jendela tetap 30 hari dari klien).
- **Tabel/kolom**: `disposal_events` (`location_id`, `commodity_id`, `quantity_kg`, `reason`,
  `partner_name`, `disposed_at`). `partner_name` NULL = belum punya mitra.
- **Data minimal**: dalam 30 hari terakhir ≥1 baris dengan `partner_name` terisi **dan** ≥1
  baris `partner_name` NULL (kalau semua terisi, "belum punya mitra" jadi 0 dan demo
  kehilangan pangan kehilangan kontrasnya), sebaiknya ≥2 nama mitra berbeda.
- **Contoh pertanyaan**: "Berapa limbah pangan yang belum punya mitra pengolahan bulan ini?"
- **Bentuk jawaban**: tiga angka terpisah — `Tercatat`, `Sudah dialihkan`, `Belum punya
  mitra` (+ periode) dan tabel `Mitra | Jumlah | Kejadian`. Ketiganya **tidak dijumlahkan**
  oleh agen.

### 2.9 `supplier_risk` — eksklusi pemasok & rute

- **Scenario**: `risiko_pemasok.yaml` · **Laporan**: `report.supplier_risk_report`
- **Endpoint**: `GET /supplier-exclusions` + `GET /supplier-routes?limit=200` +
  `GET /suppliers` dan `GET /admin/locations` (hanya untuk menerjemahkan id → nama).
- **Tabel/kolom**: `supplier_exclusions` (`supplier_id`, `scope_location_id`, `status`
  `proposed|active|revoked`, `reason`, `activated_at`, `revoked_at`); `road_routes`
  (`route_key`, `distance_m`, `duration_s`, `profile`, `fetched_at`) sebagai cache jarak
  jalan; kiriman aktif dari `batches` (`usable_until >= now`).
- **Data minimal**: ≥1 eksklusi `status='active'` dengan `activated_at` terisi, ≥1 eksklusi
  lain (mis. `revoked` atau `proposed`) supaya kolom Status beragam, dan `road_routes` yang
  memuat `route_key` untuk pasangan pemasok→SPPG tersebut. Tanpa cache rute, kolom Jarak
  jalan/Durasi jadi `—` (jujur, tetapi tidak demo-able).
- **Contoh pertanyaan**: "Pemasok mana yang dikecualikan di hub Cianjur dan mengapa?"
- **Bentuk jawaban**: `Eksklusi pemasok di hub (n baris)` — Pemasok | SPPG | Status | Alasan |
  Aktif sejak | Dicabut, lalu `Kiriman aktif dan rutenya (n kiriman)` — Pemasok | Tujuan |
  Komoditas | Jumlah | Jarak jalan | Durasi | Perjalanan.
- **Sekarang**: 2 eksklusi (1 `active`, 1 `proposed`), 10 rute dengan jarak jalan.

### 2.10 `receipts_queue` — antrean penerimaan barang **(scenario baru)**

- **Scenario**: `antrean_penerimaan.yaml` · **Laporan**: `report.receipts_queue_report`
- **Endpoint**: `GET /receipts/menunggu`. Kata kunci `penerimaan`, `receipt`, `receiving`,
  `barang datang`, `goods receipt`, `belum diperiksa`, `pemeriksaan barang` — diperiksa
  **sebelum** antrean keputusan, karena "penerimaan barang menunggu persetujuan" memuat kata
  `persetujuan` milik antrean.
  Jalur lain: "penerimaan barang batch `<uuid>`" → laporan pasokan + `GET /receipts?batch_id=`
  (`report.receipt_report`).
- **Tabel/kolom**: `batch_receipts` (`batch_id`, `status='menunggu'`, `checked` JSONB,
  `recorded_by`→`users.name`, `recorded_at`), join `batches` (`quantity_kg`, `safety_status`,
  `location_id`), `commodities`, `locations`.
- **Data minimal**: ≥1 `batch_receipts.status='menunggu'` yang `recorded_by`-nya menunjuk
  `users` nyata dan `checked` berisi ≥1 nilai `true` (kolom "Diperiksa" jadi `1/3`, bukan
  `0/3`); batch-nya harus berada di lokasi akun demo kalau pertanyaan diuji dengan akun SPPG
  (endpoint di-scope per lokasi).
- **Contoh pertanyaan**: "Penerimaan barang mana yang menunggu keputusan kepala SPPG?"
- **Bentuk jawaban**: `Ada n penerimaan barang yang menunggu keputusan` — Komoditas | Jumlah |
  Lokasi | Keamanan | Dicatat oleh | Diperiksa | Waktu, dengan catatan bahwa stok baru
  bertambah setelah persetujuan di UI.
- **Sekarang**: 2 baris menunggu (keduanya lolos join, `checked_count` terisi).

### 2.11 `quarantine_status` — status karantina **(scenario baru)**

- **Scenario**: `status_karantina.yaml` · **Laporan**: `report.quarantine_report`
- **Endpoint**: `GET /batches?limit=500`, disaring di jembatan pada
  `quarantine_status ∈ {quarantined, karantina}`. Tidak ada endpoint khusus.
- **Tabel/kolom**: `batches.quarantine_status` (+ `quarantine_reason`, `quarantined_at`,
  `quantity_kg`, `safety_status`, join `commodities.name`, `locations.name`).
- **Data minimal**: ≥1 batch dengan `quarantine_status='quarantined'`, `quantity_kg` > 0,
  `safety_status` yang jelas (mis. `unsafe`/`review_required`), dan satuan komoditas yang
  dikenal; idealnya 2 batch di 2 SPPG berbeda supaya tabelnya tidak satu baris.
- **Contoh pertanyaan**: "Batch mana yang sedang dikarantina dan berapa kilogramnya?"
- **Bentuk jawaban**: `Ada n batch berstatus karantina` — Batch | Komoditas | Jumlah | Lokasi |
  Keamanan. Daftar kosong berarti "tidak ada batch ditahan hari ini", bukan "data hilang".
- **Sekarang**: 1 batch `quarantined`. **Kolom "Batch" tampil `—`** — lihat temuan §3.2.

### 2.12 `decision_evidence` — bukti & jejak keputusan

- **Scenario**: `bukti_keputusan.yaml` · **Laporan**: `report.decision_evidence_report`
- **Endpoint**: `GET /decisions` (bila tidak ada UUID) lalu `GET /decisions/{id}/compliance`,
  `/chain`, `/traces`. Maks **3 keputusan** (`EVIDENCE_LIMIT`) bila tidak menyebut id.
- **Tabel/kolom**: `decisions`; `decision_evidence` (`evidence_type`, `payload`,
  `is_consistent`, `recorded_at`); `approvals` (`approved_by`, `approved`, `approved_at`);
  `agent_traces` (`step_name`, `tool_called`, `output_summary`, `step_at`);
  `ledger_blocks` untuk keterkaitan blok.
- **Data minimal**: ≥1 keputusan yang punya **semua**: ≥2 `decision_evidence`, ≥1 `approvals`
  dengan `approved=true`, ≥3 `agent_traces` dengan `tool_called` terisi, dan (untuk rantai
  iterasi) satu keputusan turunan dengan `iteration >= 2` atau `rejection_reason` terisi.
  Tanda tangan baru berstatus `signed` bila `SIGNING_KEY_HEX` diset di `.env` backend;
  tanpa itu jawabannya `unsigned` beserta alasannya — jangan dikira bug.
- **Contoh pertanyaan**: "Tunjukkan bukti dan jejak keputusan `<uuid>`."
- **Bentuk jawaban**: `Bukti & jejak keputusan MealChain Guardian (n keputusan)` — per
  keputusan: status tanda tangan + hasil verifikasi, content address, tabel `Iterasi` dan
  tabel `Langkah | Tool | Ringkasan keluaran | Waktu`.

### 2.13 `system_status` — status integrasi, ledger, jaringan

- **Scenario**: `status_sistem.yaml` · **Laporan**: `report.system_status_report`
- **Endpoint**: `GET /integrations/status`, `GET /ledger/verify`,
  `GET /sap/purchase-orders/summary`, `GET /admin/locations`.
- **Tabel/kolom**: `locations` (jaringan SPPG); `ledger_blocks` (`height`, `prev_hash`,
  `payload_hash`, `action`, `entity_id`, `payload`) untuk `valid`, `blocks`, `linked_ratio`,
  `orphan_blocks`; `sap_mock_purchase_orders` untuk ringkasan PO; status komponen datang dari
  konfigurasi integrasi backend (bukan tabel).
- **Data minimal**: ≥3 `ledger_blocks` yang tersambung ke `entity_id` keputusan/batch yang
  **masih ada** (blok yatim menurunkan `linked_ratio` dan memunculkan `coverage_warning`),
  ≥5 lokasi SPPG, dan ≥1 PO di tiap status yang ingin ditampilkan.
- **Contoh pertanyaan**: "Apakah integrasi SAP dan ledger sehat dan berapa bloknya?"
  (jangan menyisipkan kata `bukti` — lihat §3.6)
- **Bentuk jawaban**: `Komponen integrasi (n komponen, diperiksa …)` — Komponen | Status |
  Bukti; ringkasan ledger (valid/ jumlah blok / rasio keterkaitan); ringkasan PO per status;
  daftar `Jaringan SPPG (n lokasi)`. Komponen yang belum menyala dilaporkan "belum menyala",
  tidak pernah dinaikkan jadi hijau.

---

### 2.14 `batch_detail` — rincian keamanan satu batch **(scenario baru, 29 Okt 2026)**

- **Scenario**: `detail_batch.yaml` · **Laporan**: `report.batch_detail_report`
- **Endpoint**: `GET /batches/{id}` (satu-satunya endpoint yang membawa kebijakan komoditas
  dan status evaluasi). Tanpa id batch, laporan memakai `GET /batches` hanya untuk daftar
  kandidat — bukan untuk menyimpulkan keamanan.
- **Tabel/kolom**: `batches` (`quantity_kg`, `safety_status`, `freshness_score`, `usable_until`,
  `receipt_status`, `quarantine_status`), `commodity_policies` (`safe_temp_min_c`,
  `safe_temp_max_c`, `cold_chain_required`, `shelf_life_days`, `min_temperature_samples`,
  `max_observation_age_minutes`, `max_excursion_minutes`, `policy_version`, `policy_basis`,
  `policy_kind`), `temperature_log` (diringkas backend menjadi `temperature_observation`,
  `sample_count`, `observed_at`, `evidence_state`, `evaluated_safety_status`).
- **Data minimal**: ≥1 batch dengan profil komoditas lengkap di `commodity_policies` dan
  ≥`min_temperature_samples` baris `temperature_log`. Tanpa profil, rentang suhu tampil `—`
  (bukan tebakan); tanpa log, `evidence_state` akan `insufficient` beserta alasannya.
- **Contoh pertanyaan**: "Batch `<id>` aman atau tidak?", "Suhu batch mana yang menyimpang?",
  "Kapan batch ini kedaluwarsa?", "Bukti suhu batch `<id>` cukup?"
- **Bentuk jawaban**: judul `Batch <id8> · <komoditas> · <lokasi>`, baris `Kelayakan pakai:
  **…**` + penghalang + langkah berikutnya, tabel `Aspek batch | Nilai` (status keamanan
  **tersimpan** dan **hasil evaluasi** sebagai dua baris terpisah), tabel `Kebijakan | Nilai`
  (suhu aman, rantai dingin, masa layak, sampel minimum, batas usia observasi, toleransi
  penyimpangan, **jenis kebijakan**, versi), lalu satu baris bukti suhu.
- **Batas yang ditampilkan, bukan disembunyikan**: `policy_kind: simulated_policy` dirender
  sebagai "kebijakan simulasi (belum divalidasi pemilik domain)"; sampel suhu mentah belum
  diekspos backend sehingga yang tampil hanya ringkasannya (`sample_count` + status observasi).
- **Sekarang**: batch telur Bandung 300 kg — lolos/lolos, skor 0,95, layak sampai 28 Nov 2026,
  7 sampel, bukti cukup, kebijakan `sim-2026-10-27.v1` (0–8 °C, masa layak 28 hari).

---

## 3. Ketidaksinkronan lain yang ditemukan (belum diperbaiki — di luar tugas ini)

### 3.1 `supplier_directory`: penanda "dikecualikan di hub" tidak pernah muncul

`GET /suppliers` mengisi `excluded_at_hub` dengan membandingkan **nama lokasi pemasok**
(`suppliers.location_id`) terhadap nama lokasi cakupan eksklusi. Data sekarang: 60 pemasok,
2 eksklusi (`CV Ambarawa Telur Utama` @ Semarang, `CV Ayam Kampung Cugenang` @ Cianjur), tetapi
**0 pemasok** bertanda `excluded_at_hub` — artinya `scope_location_id` eksklusi tidak sama
dengan `suppliers.location_id` pemasok tersebut (eksklusi berlaku di hub lain). Akibatnya
skill direktori tidak pernah menampilkan penanda eksklusi, sementara skill risiko pemasok
menampilkan 2 baris. Kalau demo ingin keduanya konsisten, data demo harus membuat eksklusi
yang `scope_location_id`-nya = lokasi pemasok.

### 3.2 `quarantine_status`: kolom "Batch" selalu `—`

`report.quarantine_report` membaca `row.get("code") or row.get("batch_code")`, tetapi
`GET /batches` **tidak mengirim** kedua kunci itu (kontraknya: `id`, `location`,
`location_id`, `commodity`, `quantity_kg`, `safety_status`, `freshness_score`,
`usable_until`, `receipt_status`, `quarantine_status`). Jadi tabel karantina tampil dengan
kolom Batch kosong dan tidak ada cara menyebut batch tertentu dari chat. Perbaikan wajar:
tampilkan `id` (UUID pendek) atau tambahkan `code` di `/batches` — keduanya menyentuh kode
produksi, jadi tidak dikerjakan di sini.

### 3.3 Nomor versi agent card masih `1.3.0`

`server.py::agent_card` menulis `version="1.3.0"` sementara
`capability.sapdas.yaml` sekarang `1.4.0`. Tidak ada tes yang mengunci kesamaan keduanya, dan
Joule tidak memakainya untuk routing — tetapi dua angka berbeda untuk rilis yang sama
membingungkan saat menelusuri deploy. Disengaja tidak diubah di tugas ini karena menyentuh
kode jembatan; samakan pada rilis berikutnya.

### 3.4 `unsupported_domain` tidak punya scenario — dan itu benar

`unsupported_domain` tidak ada di `SKILLS` maupun di agent card, jadi Joule tidak pernah
menawarkannya sebagai skill. Memaksakan scenario untuknya berarti mengiklankan kemampuan yang
jawabannya "belum tersedia". Yang perlu dipahami pembangun demo: pertanyaan seperti
"pengiriman hari ini" **akan** dijawab jujur "belum tersedia" (jembatan mendeteksi kata kunci
`pengiriman`/`delivery`/`stok material SAP`), bukan data pasokan.

### 3.5 Batas jumlah yang membentuk jawaban (bukan bug, tapi memengaruhi demo)

`PAIR_LIMIT=8` (harga, kebutuhan), `DETAIL_LIMIT=12` (antrean keputusan), `EVIDENCE_LIMIT=3`
(bukti), `KPI_DEFAULT_DAYS=7`. Saat ini 120 batch mencakup **40 pasangan** (10 SPPG × 4
komoditas), jadi pertanyaan harga/kebutuhan tanpa menyebut SPPG atau komoditas akan memotong
sebagian besar pasangan (8 dari 40) dan menyebut sisanya di catatan. Untuk demo yang bersih,
sebut SPPG atau komoditas di pertanyaan.

### 3.6 Kata `bukti` merebut pertanyaan status sistem

Urutan `_KEYWORDS` menempatkan `decision_evidence` (kata kunci `bukti`, `jejak`, `audit`, …)
sebelum `system_status`. Akibatnya pertanyaan wajar seperti "apakah integrasi SAP dan **bukti**
ledger sehat?" dijawab sebagai berkas bukti keputusan, bukan status integrasi — terverifikasi
saat menguji contoh pertanyaan di dokumen ini (satu-satunya dari 13 contoh yang salah domain
sebelum kalimatnya diperbaiki). Ini bukan bug yang perlu diperbaiki sekarang (presedensi itu
disengaja: "bukti keputusan X" harus menang), tetapi **pembawa demo sebaiknya tidak memakai
kata "bukti" saat menanyakan status sistem** — cukup "integrasi", "ledger", atau "status sistem".

---

## 4. Cara memverifikasi ulang

Tes jembatan (tanpa venv Windows, memakai Python 3.12 di container, versi SDK dipin seperti
`requirements.txt`):

```bash
cd sap-joule
docker run --rm -v "$PWD:/w" -w /w python:3.12-slim sh -c \
  "pip install -q 'a2a-sdk[http-server]==0.3.25' pyyaml pydantic requests httpx pytest pytest-asyncio fastapi uvicorn && \
   python -m pytest a2a_server/tests -q"
```

Hasil 22 Okt 2026 (sesudah perubahan): **123 passed, 14 skipped**. Sebelum perubahan:
**122 passed, 14 skipped** (satu tes baru, tidak ada yang gagal). Ke-14 tes yang dilewati adalah
`test_integrasi_backend_hidup.py` — dilewati karena `MEALCHAIN_READ_USERNAME/PASSWORD` tidak
diisi di environment container, bukan karena gagal.

Catatan: `pip install a2a-sdk` **tanpa pin** memasang SDK 0.4.x dan membuat 2 modul tes gagal
di tahap koleksi (`ImportError: cannot import name 'MessageSendParams'`,
`No module named 'a2a.server.apps'`). Itu masalah versi dependensi, bukan tes kontrak Joule —
selalu pakai `==0.3.25` seperti `requirements.txt`.

Pemeriksaan cepat bahwa scenario baru benar-benar memetakan ke skill yang dimaksud (butuh
dependensi yang sama dengan tes di atas — jalankan di container yang sama):

```bash
python -c "import sys; sys.path.insert(0,'sap-joule/a2a_server'); from server import resolve_skill; \
print(resolve_skill('Pemasok mana yang melayani SPPG Bandung?')); \
print(resolve_skill('Penerimaan barang mana yang menunggu persetujuan?')); \
print(resolve_skill('Batch mana yang sedang dikarantina?'))"
```

---

## 7. Status as-built — 27 Oktober 2026 (Fase 12 MG)

Bagian ini **bukan** rancangan; isinya hasil pengukuran pada jembatan yang benar-benar
dijalankan di hari itu (`uvicorn server:app --port 18091`, `MEALCHAIN_API_URL` menunjuk backend
sesi rehearsal `127.0.0.1:18100`, akun baca `bgn.monitor@demo.local`). Bukti mentah:
`_qa/f12/out/joule-replay.json` dan `_qa/f12/out/joule-realtime.json`.

| # | Yang diuji | Hasil terukur |
|---|---|---|
| 1 | `GET /health` | `{status:"ok", service:"mealchain-joule-bridge", backend:{reachable:true}}`; **`GET /ready` → 404** (memang tidak ada) |
| 2 | Skill **pasokan** (`supply_situation`) | menjawab dari `/supply/*` + inventaris batch; menyebut kg, kebutuhan, selisih, status keamanan, skor kesegaran, bukti suhu |
| 3 | Skill **KPI** (`kpi_snapshot`) | 7 indikator; kaki laporan menyebut **`Sumber: catatan operasional MealChain Guardian`** dan **`historical_seed: N baris sumber`**, plus "2 indikator belum bisa dihitung" — bukan nol karangan |
| 4 | Skill **antrean** (`approval_queue`) | 32 usulan terbuka, id 8 karakter + jenis + asal→tujuan + jumlah + status |
| 5 | Skill **PO** (`purchase_order`) | 13 PO; setiap nomor `MC-…` yang disebut **ada** di `GET /sap/purchase-orders` backend (0 nomor karangan) |
| 6 | Skill **kiriman** (pertanyaan "status kiriman") | dirutekan ke keseimbangan pasokan per SPPG (tidak ada skill kiriman khusus) — dicatat apa adanya, bukan diklaim sebagai skill kelima yang terpisah |
| 7 | Permintaan **approval** ("setujui usulan <id>") | **ditolak** dan diarahkan ke cockpit; status keputusan di backend **tidak berubah** sebelum vs sesudah |

Batas yang ikut diukur:

- **Konteks sesi.** Sudah ditutup hari yang sama: jawaban KPI menutup dengan "Sesi demo aktif:
  mode …, jangkar …, sesi <id8> — angka KPI di atas tetap catatan operasional, bukan hasil
  simulasi." (`client.demo_session()` membaca `/demo/session`; `_kalimat_sesi()` menyusun kalimat;
  id sesi dicocokkan dengan backend). Cakupan KPI tetap operasional karena baris template milik
  sesi sentinel — memindahkan scope ke sesi operator mengembalikan `no_data`, dan itu lebih buruk
  daripada menyebut konteks. Tes: `tests/test_session_context.py` (4 kasus).
- **Kanal Joule/BTP sendiri** (destination, `joule list`) tidak diuji ulang: sesi CF milik
  operator ada, tetapi push ulang jembatan tidak dilakukan pada fase ini. Statusnya
  `INCONCLUSIVE`, bukan sukses.
