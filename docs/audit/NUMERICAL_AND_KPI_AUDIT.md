# Audit Numerik & KPI — MealChain Guardian

- **Tanggal audit:** 26 Oktober 2026, 21:30–22:05 WIB (14:30–15:05 UTC)
- **Objek:** tujuh KPI `GET /kpi` (`backend/app/services/kpi_service.py`), periode server
  (`backend/app/core/kpi_period.py`), envelope API (`backend/app/api/kpi.py`), pembulatan
  (`backend/app/core/kpi.py`)
- **Lingkungan:** container `mealchain-backend` (healthy, `http://localhost:8000`),
  `mealchain-postgres` (PostgreSQL, DB `mealchain`, zona sesi **UTC**), `now()` DB =
  `2026-10-26 14:38 UTC` (21.38 WIB) saat pengukuran dimulai
- **Akun:** `sppg_head` (Jakarta, `location_id 275d1be7-…)` dan `bgn_monitor` (global).
  Kredensial dibaca dari `backend/app/seed/demo_credentials.py` dan **tidak** ditulis di
  dokumen ini.
- **Sifat audit:** baca-saja. Tidak ada `INSERT/UPDATE/DELETE/DROP/TRUNCATE`, tidak ada
  rebuild demo, tidak ada restart container, tidak ada perubahan `.env`. Semua angka di
  bawah berasal dari respons API nyata dan `psql` nyata pada DB `mealchain`.

Legenda status temuan: `CONFIRMED` (terbukti dengan bukti yang dijalankan),
`LIKELY` (mekanisme terbaca di kode, tidak terpicu data), `NOT_REPRODUCED` (tidak
terbukti pada data sekarang), `NEEDS_PRODUCT_DECISION` (butuh keputusan pemilik, bukan
perbaikan kode), `UNVERIFIED` (belum dapat diuji di lingkungan ini).

---

## 1. Ringkasan eksekutif

| Hal | Hasil |
|---|---|
| KPI dengan nilai API **sama persis** dengan hitungan SQL independen (setelah pembulatan 2 desimal) | **7 dari 7** — dari 42 sel (7 KPI × 3 periode × 2 scope), **28 sel `available` identik** dan **14 sel `no_data` tereproduksi** (alasan + `sample_count` sama) |
| KPI yang **tidak pernah bisa `available`** pada dataset panggung sekarang | **2** — `Safe Delivered Cost`, `Decision Time` |
| Temuan | **13** — 4 × P2, 9 × P3, 0 × P0/P1 |
| Baris bertanggal masa depan | **masih ada**: `supply_records` 720 baris (386.355,50 kg), `price_signals` 840 baris, `disposal_events` 20 baris (150,30 kg), `demand_records` 360 baris |
| Periode tidak valid (`start ≥ end`) | ditolak `422` dengan pesan yang benar |
| Zona waktu | benar: sumbu tanggal dihitung di `Asia/Jakarta`, instan yang sama menghasilkan angka identik walau offset pemanggil berbeda |
| Pembulatan | benar: `HALF_UP` 2 desimal (dibuktikan `85.625 → 85,63`, sedangkan `round()` Python memberi `85,62`) |

Kesimpulan singkat: **aritmetika tujuh KPI dapat dipercaya** (tidak ada satu pun selisih
numerik), tetapi **ketersediaan dua kartu** (`Safe Delivered Cost`, `Decision Time`) mati
secara struktural pada dataset panggung karena tidak ada satu pun PO yang tertaut ke
`decisions` — dan **jendela eksplisit yang ujungnya di masa depan** membuat KPI menghitung
fakta yang belum terjadi.

---

## 2. Snapshot data yang dipakai (terukur, `SELECT`)

| Tabel | Baris | Catatan terukur |
|---|---:|---|
| `menu_plans` | 660 | `plan_date` 2026-09-01 … 2026-11-05; 66 baris untuk lokasi Jakarta; `planned_portions` 1.082–1.224, **tidak ada** nilai 0 |
| `delivery_events` | 180 | `MAX(delivered_at)` = **2026-10-25** (WIB); **tidak ada** kiriman untuk 26 Okt |
| `disposal_events` | 83 | `MAX(disposed_at)` = 2026-11-05 19:00 WIB |
| `supply_records` | 5.240 | `MAX(recorded_at)` = 2026-11-04 19:00 WIB |
| `price_signals` | 6.015 | termasuk 840 baris masa depan |
| `demand_records` | 1.360 | termasuk 360 baris masa depan |
| `decisions` | 32 | 6 tanpa `demo_case`, 26 dengan `demo_case`; 9 punya `supersedes_id`; 23 akar lineage |
| `agent_traces` | 69 | `DETECT` 23, `ACT` **1**, `DECIDE` 23, `VERIFY` 4, `LEARN` 9, `OPTIMIZE` 3, `PREDICT` 6 |
| `approvals` | 13 | 11 keputusan berbeda; hanya 2 keputusan punya approval `approved = true` di jendela 7 hari |
| `decision_evidence` | 27 | hanya 3 `evidence_type`: `human_inspection` 21, `gps` 4, `market_price` 6 (3 di antaranya `is_consistent = false`) |
| `sap_mock_purchase_orders` | **12** | **12/12 `decision_id IS NULL`**; semua `created_at = 2026-10-26 13:42:46.72+00` |

Dataset ini dibangun ulang pada **2026-10-26 20:42 WIB** (`sap_mock_purchase_orders.created_at`,
sesi demo `cd56f00d-…` mulai 19:29 WIB, kedaluwarsa 21:29 WIB). Angka di dokumen
`kamus-kpi-dan-state-machine.md` §7 (mis. "Decision Time 20,98 menit") berasal dari
dataset **sebelum** rebuild ini, sehingga tidak lagi dapat diamati sekarang — lihat NUM-02.

---

## 3. Calculation inventory

Kolom *Expected* = nilai yang seharusnya keluar menurut definisi yang tertulis di kamus KPI;
*Actual* = nilai runtime pada audit ini (scope `sppg_head`, periode `today` kecuali disebut).

| # | Kalkulasi | Rumus di kode | Input | Unit | Filter | Pembulatan | Null handling | Expected | Actual | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | `resolve_periode(kunci, now)` | `today`: `[00:00 WIB, now]`; `7d`: `[00:00 H−6 WIB, now]`; `1bulan`: `[00:00 tgl 1 WIB, now]` | `now` berzona | instan UTC | kunci ∈ `{today,7d,1bulan}`; `now` naive → `ValueError` | tidak ada (instan) | `None` → error, bukan default | 1 Nov 00:30 WIB → `today` = 31 Okt 17:00Z | sama (diuji) | PASS |
| C2 | `quantize2` | `Decimal(v).quantize(0.01, ROUND_HALF_UP)` | nilai apa pun | — | — | **HALF_UP** 2 desimal | `None` tidak pernah masuk | `85.625 → 85,63` | `85,63` (`round()` Python = `85,62`) | PASS |
| C3 | `resolve_root(parent_map, id)` | telusuri `supersedes_id` sampai tak ada parent; berhenti bila ada siklus | 9 baris ber-`supersedes_id` | id | hanya baris yang punya parent | — | map kosong → id itu sendiri | siklus `a↔b` → `a` (aman) | `a` | PASS |
| C4 | `tanggal_kiriman_terakhir(acuan)` | `acuan ≥ 21.00 WIB` → tanggal WIB hari ini, selain itu kemarin | `end` | tanggal | — | — | — | 13:59:59Z → 25 Okt; 14:00:00Z → 26 Okt | sama | PASS |
| C5 | Meal Continuity Rate | `100 × Σ LEAST(delivered, planned) / Σ planned` | `menu_plans` ⋈ agregat `delivery_events` (per `menu_plan_id`) | percent | `plan_date` ∈ `[start::date, end::date]` WIB (dua ujung **inklusif**); `plan_date ≤ tanggal_kirim OR delivered IS NOT NULL`; `mp.location_id` | 2 desimal HALF_UP di output | penyebut nol → `no_data` + alasan spesifik | 7200/8411 = 85,6022 % (7d) | `85.60` | PASS |
| C6 | Avoidable Food Loss | `100 × Σ disposal_kg / (Σ disposal_kg + Σ supply_kg)` | `disposal_events`, `supply_records` | percent | `disposed_at` / `recorded_at` ∈ `[start,end)`; `location_id` | 2 desimal | buangan 0 & pasokan > 0 → `no_data`; keduanya 0 → `no_data` | 31,49/(31,49+5267,21) = 0,5943 % | `0.59` | PASS |
| C7 | Regional Imbalance Resolution Rate | `100 × akar(executed) / akar(DETECT)` | `decisions` ⋈ `agent_traces(DETECT)` | percent | `step_at ∈ [start,end)`; `demo_case IS NULL`; lokasi source **atau** target | 2 desimal | tanpa DETECT → `no_data` | 3 akar, 1 executed → 33,3333 % (7d) | `33.33` | PASS |
| C8 | Safe Delivered Cost | `mean(decisions.safe_delivered_cost)` | `decisions` ⋈ `sap_mock_purchase_orders` | IDR | `po.created_at ∈ [start,end)`; `safe_delivered_cost IS NOT NULL`; lokasi source/target | 2 desimal | tanpa baris → `no_data` | `null` (0 PO tertaut) | `null` | **FAIL (ketersediaan)** |
| C9 | Procurement Price Deviation | `mean( |quote − ref| / ref × 100 )` | `price_signals` (`supplier_quote`, `pihps_reference`) | percent | kutipan ∈ `[start,end)`; ref terakhir dengan `recorded_at ≤ recorded_at kutipan`, lokasi+komoditas sama; ref 0 / tak ada pasangan → dibuang | 2 desimal | tanpa pasangan → `no_data` + alasan | 2,655276 % (today, 17 kutipan) | `2.66` | PASS |
| C10 | Decision Time | `mean(MAX(ACT) − MIN(DETECT))` menit | `decisions` ⋈ `agent_traces`, `sap_mock_purchase_orders` | minutes | trace ∈ `[start,end)`; hanya bila ACT **committed** (PO dengan `created_at ∈ [start,end)`) | 2 desimal | tanpa ACT committed → `no_data` | `null` (0 PO tertaut) | `null` | **FAIL (ketersediaan)** |
| C11 | Evidence Completeness | `100 × keputusan(≥2 tipe bukti konsisten sebelum cutoff) / keputusan ber-approval` | `decisions`, `approvals`, `decision_evidence` | percent | `d.created_at ∈ [start,end)`; cutoff = `MIN(approved_at) FILTER (approved)`; `recorded_at < cutoff`; `is_consistent IS TRUE` | 2 desimal | tanpa approval → `no_data` + `coverage` | 0/1 = 0,0000 % (7d) | `0.00` | PASS |
| C12 | scope SPPG | `location_id` = lokasi user; `location_id` lain → 403 | user | — | — | — | user tanpa lokasi → 403 | 403 | 403 | PASS |
| C13 | scope `bgn_monitor` | `location_id` opsional; omit → global | query | — | — | — | lokasi tak dikenal → semua `no_data` | `no_data` | `no_data` | PASS (lihat NUM-10) |
| C14 | validasi rentang | `start < end`, `≤ 366 hari`, wajib berzona | query | — | — | — | — | 422 | 422 | PASS |

---

## 4. Per KPI: rumus kode vs hitungan SQL independen

Angka `API` = nilai yang dikirim server (string, 2 desimal). Angka `SQL` = implementasi
ulang independen (lihat lampiran) atas jendela yang **persis** sama (`period.start`/`period.end`
dari respons API). Selisih dihitung setelah **kedua sisi** dibulatkan ke 2 desimal, sehingga
`0,0000` berarti identik pada presisi yang dikirim API; selisih mentah sebelum pembulatan
selalu ≤ 0,005 (murni efek pembulatan, bukan selisih rumus).

### 4.1 Meal Continuity Rate — `percent`

- **Rumus kode** (`kpi_service.py:153-201`): `100 × Σ LEAST(COALESCE(SUM(delivery_events.delivered_portions),0), mp.planned_portions) / Σ mp.planned_portions`.
- **SQL independen**: CTE agregat `delivery_events` per `menu_plan_id`, lalu `LEAST(...)` yang sama, dengan predikat `plan_date` yang dikonversi lewat `AT TIME ZONE 'Asia/Jakarta'`.

| Scope | Periode | API | SQL (6 desimal) | Selisih abs | Selisih rel | sample | Berkas plan / porsi |
|---|---|---:|---:|---:|---:|---:|---|
| sppg_head | today | 0.00 | 0,000000 | 0,0000 | 0,000000 % | 1 | 1 / 1.211 |
| sppg_head | 7d | 85.60 | 85,602188 | 0,0000 | 0,000000 % | 7 | 7 / 8.411 |
| sppg_head | 1bulan | 67.73 | 67,733194 | 0,0000 | 0,000000 % | 26 | 26 / 30.629 |
| bgn_monitor | today | 0.00 | 0,000000 | 0,0000 | 0,000000 % | 10 | 10 / 12.057 |
| bgn_monitor | 7d | 85.63 | 85,627610 | 0,0000 | 0,000000 % | 70 | 70 / 84.057 |
| bgn_monitor | 1bulan | 68.32 | 68,316728 | 0,0000 | 0,000000 % | 260 | 260 / 306.534 |

**Uji sensitivitas (membuktikan pilihan sumbu waktu):**

| Varian rumus | 7d (Jakarta) | 1bulan (Jakarta) | Penjelasan |
|---|---:|---:|---|
| Kode sekarang (`plan_date`, ber-cap) | **85,60 %** | **67,73 %** | dipakai |
| Tanpa batas `tanggal_kirim` | 85,60 % | 67,73 % | tidak berbeda **sekarang** karena pukul 21.39 WIB sudah lewat ambang; berbeda pada pagi hari (lihat uji A/B di §6) |
| Tanpa cap `LEAST` (over-delivery dihitung) | 85,60 % | 67,73 % | **cap tidak pernah aktif** pada data ini: `delivered_raw` = `delivered_capped` di semua jendela (NUM-11) |
| Sumbu `delivered_at` (implementasi alternatif) | 100,00 % | 97,79 % | menaikkan angka ~14 poin karena rencana tanpa kiriman **hilang dari penyebut** — inilah alasan sumbu `plan_date` dipakai |

**Penjelasan:** hitungan cocok penuh. Nilai `today` = 0,00 % **bukan** bug aritmetika:
rencana 26 Okt (1.211 porsi) belum punya baris `delivery_events` sama sekali
(`MAX(delivered_at)` = 25 Okt), dan pada 21.39 WIB jendela kirim hari itu sudah lewat —
maka rumus menyatakan 0 % terukur. Dampaknya besar: satu baris kiriman yang belum ditulis
menurunkan `7d` dari 100,00 % menjadi 85,60 % (−14,40 poin). Lihat **NUM-04**.

### 4.2 Avoidable Food Loss — `percent`

- **Rumus kode** (`kpi_service.py:266-309`): `100 × disposed_kg / (disposed_kg + supply_kg)`.
- **SQL independen**: tiga subquery `SUM`/`COUNT` terpisah pada `disposal_events` dan `supply_records` dengan jendela `[start,end)`.

| Scope | Periode | API | SQL (6 desimal) | Selisih abs | Selisih rel | sample | disposal kg / supply kg |
|---|---|---:|---:|---:|---:|---:|---|
| sppg_head | today | 0.59 | 0,5943 | 0,0000 | 0,000000 % | 3 | 31,49 / 5.267,21 |
| sppg_head | 7d | 0.16 | 0,1618 | 0,0000 | 0,000000 % | 5 | 41,49 / 25.607,72 |
| sppg_head | 1bulan | 0.07 | 0,0688 | 0,0000 | 0,000000 % | 8 | 62,81 / 91.275,24 |
| bgn_monitor | today | 0.06 | 0,0627 | 0,0000 | 0,000000 % | 4 | 41,12 / 65.507,32 |
| bgn_monitor | 7d | 0.08 | 0,0762 | 0,0000 | 0,000000 % | 36 | 244,24 / 320.183,74 |
| bgn_monitor | 1bulan | 0.04 | 0,0385 | 0,0000 | 0,000000 % | 60 | 435,20 / 1.128.927,16 |

**Penjelasan:** cocok penuh, termasuk pembulatan `0,0385 → 0,04` (HALF_UP; `round()` Python
akan memberi `0,04` juga di sini, tetapi `0,005 → 0,01` membuktikan arah pembulatan).
Catatan definisi: karena buangan dijumlahkan **di pembilang dan penyebut**, nilai maksimum
matematis metrik ini adalah **50 %** (saat buangan = pasokan), bukan 100 % — lihat **NUM-08**.

### 4.3 Regional Imbalance Resolution Rate — `percent`

- **Rumus kode** (`kpi_service.py:312-344`): baris `decisions` ber-trace `DETECT` di jendela, `demo_case IS NULL`; peta `supersedes_id` **hanya dari baris di jendela**; akar di-dedupe; pembilang = akar yang punya anggota `executed`.
- **SQL independen**: recursive CTE menelusuri `supersedes_id` lewat **seluruh** tabel `decisions`.

| Scope | Periode | API | SQL (akar/executed) | Selisih | sample | Lineage penuh (akar/executed) |
|---|---|---:|---:|---:|---:|---|
| sppg_head | today | — (`no_data`) | 0 / 0 | — | 0 | 0 / 0 |
| sppg_head | 7d | 33.33 | 3 / 1 = 33,333333 | 0,0000 | 3 | 3 / 1 (identik) |
| sppg_head | 1bulan | 33.33 | 3 / 1 = 33,333333 | 0,0000 | 3 | 3 / 1 (identik) |
| bgn_monitor | today | 0.00 | 3 / 0 = 0,000000 | 0,0000 | 3 | 3 / 0 (identik) |
| bgn_monitor | 7d | 16.67 | 6 / 1 = 16,666667 | 0,0000 | 6 | 6 / 1 (identik) |
| bgn_monitor | 1bulan | 16.67 | 6 / 1 = 16,666667 | 0,0000 | 6 | 6 / 1 (identik) |

**Penjelasan:** cocok penuh; dedupe tidak mengubah angka karena pada 23 lineage yang ada
hanya **akar** yang punya trace `DETECT` (anak tidak), sehingga pendekatan "hanya baris
dalam jendela" dan "lineage penuh" kebetulan identik. Risiko latennya dicatat di **NUM-06**.
Perhatikan: 26 dari 32 keputusan ber-`demo_case` dikecualikan, jadi kartu ini **tidak
bergerak** saat kartu demo dieksekusi (keputusan terbuka #8 di kamus KPI).

### 4.4 Safe Delivered Cost — `IDR`

- **Rumus kode** (`kpi_service.py:347-371`): `AVG(d.safe_delivered_cost)` untuk `d JOIN sap_mock_purchase_orders po ON po.decision_id = d.id`, `po.created_at ∈ [start,end)`, `safe_delivered_cost IS NOT NULL`.
- **SQL independen**: join yang sama + hitungan PO tanpa tautan.

| Scope | Periode | API | SQL | Selisih | PO di jendela | PO `decision_id IS NULL` | Baris hasil join |
|---|---|---:|---:|---:|---:|---:|---:|
| sppg_head | today | — (`no_data`) | 0 baris | 0 | 12 | **12** | **0** |
| sppg_head | 7d | — | 0 baris | 0 | 12 | 12 | 0 |
| sppg_head | 1bulan | — | 0 baris | 0 | 12 | 12 | 0 |
| bgn_monitor | today/7d/1bulan | — | 0 baris | 0 | 12 | 12 | 0 |

**Penjelasan:** rumus **benar** tetapi **tidak dapat menghasilkan angka**: 12 dari 12 PO
seeding punya `decision_id = NULL`, sehingga join selalu kosong. `average` yang akan keluar
bila gate PO dilepas (rata-rata `safe_delivered_cost` semua keputusan ber-SDC di jendela)
adalah **14.178.614,58 IDR** (today, 9 keputusan), **14.677.124,18 IDR** (7d, 12 keputusan),
dan **15.914.115,94 IDR** (global today, 25 keputusan) — angka pembanding, bukan nilai KPI.
Lihat **NUM-01**.

### 4.5 Procurement Price Deviation — `percent`

- **Rumus kode** (`kpi_service.py:374-421`): untuk tiap `supplier_quote` di jendela, ambil `pihps_reference` terakhir dengan `recorded_at ≤` waktu kutipan pada lokasi+komoditas sama; `|q−r|/r×100`; rata-rata.
- **SQL independen**: `LEFT JOIN LATERAL` untuk pemilihan referensi (bukan loop per baris).

| Scope | Periode | API | SQL (6 desimal) | Selisih | sample | Kutipan / berpasangan / ref=0 |
|---|---|---:|---:|---:|---:|---|
| sppg_head | today | 2.66 | 2,655276 | 0,0000 | 17 | 17 / 17 / 0 |
| sppg_head | 7d | 3.04 | 3,042227 | 0,0000 | 30 | 30 / 30 / 0 |
| sppg_head | 1bulan | 3.59 | 3,587324 | 0,0000 | 56 | 56 / 56 / 0 |
| bgn_monitor | today | 2.38 | 2,384771 | 0,0000 | 72 | 72 / 72 / 0 |
| bgn_monitor | 7d | 2.85 | 2,846588 | 0,0000 | 132 | 132 / 132 / 0 |
| bgn_monitor | 1bulan | 3.06 | 3,063568 | 0,0000 | 252 | 252 / 252 / 0 |

**Penjelasan:** cocok penuh. Rata-rata **bertanda** (signed) akan memberi 0,977–1,261 %
(Jakarta) dan −0,489…−0,303 % (global) — jadi kontrak "magnitudo absolut" (O-NUM) memang
menggandakan angka dibanding rata-rata bertanda; itu keputusan desain yang terdokumentasi,
bukan selisih hitung. Jalur "kutipan tanpa pasangan dibuang" **belum teruji** oleh data:
252/252 kutipan punya referensi, 0 referensi bernilai nol.

### 4.6 Decision Time — `minutes`

- **Rumus kode** (`kpi_service.py:424-481`): per keputusan `MAX(step_at|ACT) − MIN(step_at|DETECT)`; hanya dihitung bila ada PO dengan `created_at ∈ [start,end)`; `coverage = sampel/eligible`.
- **SQL independen**: CTE `tr` (agregat trace) + CTE `po` (PO ber-`decision_id`), `AVG(EXTRACT(EPOCH …)/60)`.

| Scope | Periode | API | SQL | Selisih | eligible | ACT rows | ACT committed |
|---|---|---:|---:|---:|---:|---:|---:|
| sppg_head | today | — (`no_data`) | 0 baris | 0 | 7 | 0 | 0 |
| sppg_head | 7d | — | 0 baris | 0 | 12 | **1** | 0 |
| sppg_head | 1bulan | — | 0 baris | 0 | 12 | 1 | 0 |
| bgn_monitor | today | — | 0 baris | 0 | 18 | 0 | 0 |
| bgn_monitor | 7d | — | 0 baris | 0 | 23 | 1 | 0 |
| bgn_monitor | 1bulan | — | 0 baris | 0 | 23 | 1 | 0 |

**Penjelasan:** rumus benar, hasil selalu `no_data` karena `committed_ids` kosong.
Satu-satunya trace `ACT` di DB (`decision d2c7131c…`, `supplier_exclusion`, status `executed`,
`step_at 2026-10-24 10:46:46Z`) berjarak **4,00 menit** dari `DETECT`-nya
(`10:42:46Z → 10:46:46Z`) tetapi **dibuang** karena tidak ada PO. Jadi angka yang "hilang"
bukan abstrak: 4,00 menit nyata di jendela 7 hari tidak masuk sampel. Lihat **NUM-02**.

### 4.7 Evidence Completeness — `percent`

- **Rumus kode** (`kpi_service.py:484-557`): cutoff = `MIN(approved_at)` untuk `approved = true`; pembilang = keputusan dengan ≥ 2 `evidence_type` berbeda, `is_consistent = true`, `recorded_at < cutoff`; penyebut = keputusan di jendela yang punya approval.
- **SQL independen**: CTE `dec` (cutoff) + CTE `ev` (`COUNT(DISTINCT evidence_type)` sebelum cutoff).

| Scope | Periode | API | SQL | Selisih | sample (dinilai) | Keputusan di jendela | coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| sppg_head | today | — (`no_data`) | 0/0 | 0 | 0 | 11 | — |
| sppg_head | 7d | 0.00 | 0/1 = 0,000000 | 0,0000 | 1 | 15 | 0,07 |
| sppg_head | 1bulan | 0.00 | 0/1 | 0,0000 | 1 | 15 | 0,07 |
| bgn_monitor | today | 0.00 | 0/1 | 0,0000 | 1 | 28 | 0,04 |
| bgn_monitor | 7d | 0.00 | 0/2 | 0,0000 | 2 | 32 | 0,06 |
| bgn_monitor | 1bulan | 0.00 | 0/2 | 0,0000 | 2 | 32 | 0,06 |

**Penjelasan:** cocok penuh. `0,00 %` sah menurut definisi (penyebut = keputusan yang punya
approval; hanya 1–2 yang memenuhi, dan yang dinilai hanya punya 1 tipe bukti konsisten).
Yang perlu disadari saat demo: kartu berstate `available` dengan **cakupan 4–7 %** — 93–96 %
keputusan tidak bisa dinilai karena belum ada approval. Lihat **NUM-13**.

---

## 5. Tabel nilai API lengkap (3 periode × 2 scope)

Diambil dari `GET /kpi?periode=…` pada 2026-10-26 21.39–21.40 WIB. `—` = `no_data` /
`unavailable` (tidak ada angka), bukan 0.

| KPI | Unit | Jakarta today | Jakarta 7d | Jakarta 1bln | Global today | Global 7d | Global 1bln |
|---|---|---:|---:|---:|---:|---:|---:|
| Meal Continuity Rate | percent | 0.00 (1) | 85.60 (7) | 67.73 (26) | 0.00 (10) | 85.63 (70) | 68.32 (260) |
| Avoidable Food Loss | percent | 0.59 (3) | 0.16 (5) | 0.07 (8) | 0.06 (4) | 0.08 (36) | 0.04 (60) |
| Regional Imbalance Resolution Rate | percent | — (0) | 33.33 (3) | 33.33 (3) | 0.00 (3) | 16.67 (6) | 16.67 (6) |
| Safe Delivered Cost | IDR | — | — | — | — | — | — |
| Procurement Price Deviation | percent | 2.66 (17) | 3.04 (30) | 3.59 (56) | 2.38 (72) | 2.85 (132) | 3.06 (252) |
| Decision Time | minutes | — (7) | — (12) | — (12) | — (18) | — (23) | — (23) |
| Evidence Completeness | percent | — (0) | 0.00 (1) | 0.00 (1) | 0.00 (1) | 0.00 (2) | 0.00 (2) |

`(n)` = `sample_count`. `previous_value` dan `trend` = `null` untuk **semua** metrik
(belum ada perbandingan periode di backend — sesuai kamus KPI §1).

Jendela yang dipakai server (dibuktikan dari `period.start`/`period.end`):

| Kunci | `start` (UTC) | `end` (UTC) | Rentang `plan_date` (WIB) | `tanggal_kirim` |
|---|---|---|---|---|
| today | 2026-10-25T17:00:00Z | 14:39:57Z (now) | 2026-10-26 … 2026-10-26 | 2026-10-26 |
| 7d | 2026-10-19T17:00:00Z | 14:39:59Z (now) | 2026-10-20 … 2026-10-26 | 2026-10-26 |
| 1bulan | 2026-09-30T17:00:00Z | 14:40:01Z (now) | 2026-10-01 … 2026-10-26 | 2026-10-26 |

---

## 6. Uji periode tidak valid, batas, dan zona waktu

### 6.1 Validasi parameter

| Kasus | Permintaan | HTTP | `detail` | Verdict |
|---|---|---:|---|---|
| `start > end` | `start=2026-10-26T10:00+07:00&end=2026-10-25T10:00+07:00` | **422** | `start harus < end` | PASS |
| `start == end` | `10:00+07:00` → `10:00+07:00` | **422** | `start harus < end` | PASS |
| timestamp naive | `start=2026-10-25T00:00:00&end=2026-10-26T00:00:00` | **422** | `start/end wajib RFC3339 dengan offset zona waktu` | PASS |
| `periode` + `start/end` | `periode=today&start=…` | **422** | `kirim periode ATAU start+end, bukan keduanya` | PASS |
| kunci periode asing | `periode=30d` | **422** | `periode tidak dikenal: '30d'; pilihan: today, 7d, 1bulan` | PASS |
| tanpa parameter | `/kpi` | **422** | `wajib mengirim periode=…, atau start dan end sekaligus` | PASS |
| tanpa token | `/kpi?periode=today` | **401** | `butuh Bearer token` | PASS |
| scope asing (SPPG) | `location_id` lokasi lain | **403** | `scope lokasi di luar otoritas Anda` | PASS |
| rentang 366 hari | `2025-10-25Z → 2026-10-26Z` | **200** | (dihitung) | PASS (batas inklusif) |
| rentang 367 hari | `2025-10-24Z → 2026-10-26Z` | **422** | `rentang maksimum 366 hari` | PASS |

Catatan: `resolve_periode` melempar `ValueError` untuk `now` naive dan `KeyError` untuk kunci
asing; keduanya tidak bisa mencapai `resolve_periode` lewat API karena API memvalidasi lebih
dulu (`api/kpi.py:58-72`) — jadi tidak ada jalur 500.

### 6.2 Zona waktu

| Uji | Permintaan | Hasil | Verdict |
|---|---|---|---|
| Instan identik, offset berbeda | `00:00Z–07:00Z` vs `07:00+07:00–14:00+07:00` vs `09:00+09:00–16:00+09:00` | ketujuh metrik **identik** (state, value, sample, coverage) | PASS |
| Sumbu tanggal memakai WIB, bukan UTC | `17:00Z–23:00Z 25 Okt` (= 26 Okt 00:00–06:00 WIB) | Meal Continuity `no_data`, sampel 1 → tanggal rencana dibaca **26 Okt** (rencana tanpa kiriman); bila UTC dipakai, hasilnya akan 100,00 % dari rencana 25 Okt | PASS |
| Pembanding | `17:00Z–23:00Z 24 Okt` (= 25 Okt 00:00–06:00 WIB) | Meal Continuity `100.00` (1 sampel, rencana 25 Okt ada kirimannya) | PASS |
| Batas tengah malam | `2026-11-01T00:30+07:00` | `today` = 31 Okt 17:00Z, `1bulan` = 31 Okt 17:00Z (1 Nov WIB), `7d` melintasi bulan dengan benar | PASS |
| Akhir Februari | `2026-03-01T00:15+07:00` | `today` = 28 Feb 17:00Z, `7d` = 22 Feb 17:00Z | PASS |
| Ambang jam kirim | `end=20:59 WIB` vs `21:01 WIB` (26 Okt) | Meal Continuity: `no_data` → **`0.00` available**; berubah tepat pada 14:00:00Z (`tanggal_kiriman 25 Okt → 26 Okt`) | PASS (perilaku sesuai desain) |
| Envelope `period` | offset pemanggil dikembalikan apa adanya (`+00:00`, `+09:00`) walau `timezone` = `Asia/Jakarta` | instan benar, representasi tidak dinormalkan | **NUM-09** |

Jendela intra-hari tetap dibaca per **tanggal rencana**, sehingga jendela 1 detik
(`21:00:00–21:00:01`) mengembalikan Meal Continuity `available 0.00` dengan 1 sampel —
yakni satu hari rencana penuh, bukan satu detik. Ini konsekuensi wajar dari sumbu
`plan_date`, tetapi harus diketahui pemakai API (`start`/`end` eksplisit).

### 6.3 Baris bertanggal masa depan

Perintah wajib (`SELECT count(*) … WHERE … > now()`), dijalankan pada `now()` = 2026-10-26 14:38 UTC:

| Tabel | Baris masa depan | Keterangan |
|---|---:|---|
| `supply_records` (`recorded_at > now()`) | **720** | 386.355,50 kg; 640 di antaranya > 1 hari ke depan; maksimum 2026-11-04 19:00 WIB |
| `price_signals` (`recorded_at > now()`) | **840** | maksimum 2026-11-05 |
| `disposal_events` (`disposed_at > now()`) | **20** | 150,30 kg; maksimum 2026-11-05 19:00 WIB |
| `demand_records` (`recorded_at > now()`) | **360** | tidak dipakai KPI |
| `menu_plans` (`plan_date > hari ini WIB`) | **100** | 27 Okt–5 Nov (10 lokasi × 10 hari) |
| `delivery_events` (`delivered_at > now()`) | **0** | — |
| `sap_mock_purchase_orders` (`created_at > now()`) | **0** | — |

**Kesimpulan: baris masa depan masih ada** (720 + 840 untuk dua tabel yang ditanyakan).
Untuk jendela kanonik (`periode=today|7d|1bulan`) baris ini **tidak** masuk hitungan karena
semua query punya batas atas (`< end` / `<= end::date`). Yang bocor adalah jendela eksplisit
yang ujungnya di masa depan — dibuktikan di **NUM-03**: `27 Okt–5 Nov` menghasilkan
Meal Continuity `0.00` (9 rencana masa depan dianggap gagal), Avoidable Food Loss `0.02`
(1 disposal masa depan), Price Deviation `2.91` (26 kutipan masa depan).

---

## 7. Temuan

| ID | Severity | Status | Ringkas |
|---|---|---|---|
| NUM-01 | P2 | CONFIRMED | `Safe Delivered Cost` mustahil `available`: 12/12 PO ber-`decision_id` NULL |
| NUM-02 | P2 | CONFIRMED | `Decision Time` mustahil `available`: ACT tanpa PO dibuang (4,00 menit hilang) |
| NUM-03 | P2 | CONFIRMED | `start/end` eksplisit berakhir di masa depan → KPI menghitung fakta belum terjadi |
| NUM-04 | P2 | CONFIRMED | Meal Continuity `today` = 0,00 % setelah 21.00 WIB; 7d turun 100,00 % → 85,60 % |
| NUM-05 | P3 | CONFIRMED | `coverage` = "1.00" dilaporkan pada state `no_data`; UI mencetak "cakupan 100%" |
| NUM-06 | P3 | NOT_REPRODUCED (LIKELY) | Dedupe lineage hanya melihat baris di dalam jendela |
| NUM-07 | P3 | NOT_REPRODUCED (LIKELY) | Decision Time tidak menjepit durasi negatif (ACT < DETECT) |
| NUM-08 | P3 | NEEDS_PRODUCT_DECISION | Avoidable Food Loss terbatas maksimum 50 % secara struktur |
| NUM-09 | P3 | CONFIRMED | `period.start/end` menggemakan offset pemanggil, bukan WIB |
| NUM-10 | P3 | CONFIRMED | `location_id` tak dikenal (bgn_monitor) → semua `no_data`, tanpa error |
| NUM-11 | P3 | CONFIRMED | Cap `LEAST()` tidak pernah aktif; over-delivery belum teruji |
| NUM-12 | P3 | CONFIRMED | Baris masa depan masih ada (720 supply, 840 price, 20 disposal) |
| NUM-13 | P3 | NEEDS_PRODUCT_DECISION | Evidence Completeness `available 0,00%` dengan cakupan 4–7 % |

### NUM-01 — `Safe Delivered Cost` mustahil `available` pada dataset panggung

- **Severity:** P2 · **Status:** CONFIRMED
- **Bukti:**
  ```
  sap_mock_purchase_orders: 12 baris, 12 di antaranya decision_id IS NULL
  decisions JOIN sap_mock_purchase_orders ON po.decision_id = d.id → 0 baris (semua jendela)
  API: Safe Delivered Cost = no_data untuk 3 periode × 2 scope
  ```
- **Sebab:** rumus mensyaratkan PO yang tertaut ke `decisions` (`kpi_service.py:349-353`).
  Seeder membuat PO kanonik tanpa `decision_id` (`scripts/bangun_seed_realistis.py:601-643`),
  dan PO ber-tautan hanya lahir dari `POST /actions/execute` (`api/actions.py:824-839`).
- **Dampak:** 1 dari 7 kartu KPI selalu "—" saat juri melihat dashboard, kecuali operator
  sudah mengeksekusi satu kartu pada sesi itu. Alasan yang ditampilkan
  ("tidak ada batch terkirim yang punya biaya") **menyesatkan**: penyebabnya tautan data,
  bukan tidak ada biaya — `decisions.safe_delivered_cost` terisi pada 28 keputusan.
- **Pembanding (bukan nilai KPI):** rata-rata SDC semua keputusan ber-SDC di jendela
  14.178.614,58 IDR (Jakarta today, n=9), 14.677.124,18 IDR (7d, n=12),
  15.914.115,94 IDR (global today, n=25).
- **Saran:** (a) tautkan PO seed ke keputusan `executed`, atau (b) tambahkan kolom
  `decision_id` pada builder seed, atau (c) ubah `reason` agar menyebut sebab sebenarnya
  ("PO tidak tertaut ke keputusan"). Opsi (a)/(b) mengubah data panggung → butuh keputusan owner.

### NUM-02 — `Decision Time` mustahil `available`; satu ACT nyata dibuang

- **Severity:** P2 · **Status:** CONFIRMED
- **Bukti:**
  ```
  agent_traces: step_name='ACT' → 1 baris (decision d2c7131c…, supplier_exclusion, executed)
  DETECT 2026-10-24 10:42:46.57Z → ACT 2026-10-24 10:46:46.57Z = 4,00 menit
  PO dengan decision_id di jendela mana pun → 0 baris
  API 7d: no_data, sample_count 12 (eligible), coverage null
  ```
- **Sebab:** `committed_ids` diambil dari `sap_mock_purchase_orders WHERE created_at ∈ [start,end)`
  (`kpi_service.py:440-446`); himpunan itu kosong karena NUM-01. Karena ACT hanya dihitung
  bila committed, durasi 4,00 menit itu keluar dari sampel.
- **Dampak:** kartu "Waktu keputusan" tidak pernah bergerak. Ini juga berarti klaim di
  `kamus-kpi-dan-state-machine.md` §7.7 ("20,98 menit (1 sampel)") **tidak dapat direproduksi**
  pada dataset sekarang — angka itu berasal dari sesi sebelum rebuild 20:42 WIB.
- **Catatan:** jalur perbaikannya sudah ada di kode (`execute` menulis PO ber-`decision_id`
  + trace ACT), jadi setelah satu eksekusi nyata metrik ini hidup. Risiko yang tersisa
  adalah **urutan demo**: selama belum ada eksekusi, kartu ini mati.
- **Saran:** jangan mengubah rumus; cukup pastikan satu kartu dieksekusi sebelum segmen KPI,
  atau tautkan PO seed (lihat NUM-01) agar riwayat punya sampel committed.

### NUM-03 — Jendela eksplisit berakhir di masa depan menghitung fakta yang belum terjadi

- **Severity:** P2 · **Status:** CONFIRMED
- **Bukti (API nyata):**

  | Permintaan | Meal Continuity | Avoidable Food Loss | Price Deviation |
  |---|---|---|---|
  | `start=2026-10-27T00:00+07:00&end=2026-11-05T00:00+07:00` (100 % masa depan) | `available 0.00`, 9 sampel | `available 0.02`, 1 sampel | `available 2.91`, 26 sampel |
  | `start=2026-10-25+07:00&end=2026-10-29+07:00` (3 hari ke depan) | `available 24.94`, 4 sampel | `available 0.20`, 3 sampel | `available 2.70`, 30 sampel |

- **Sebab:** tidak ada penjepitan `end` ke `now()` untuk permintaan eksplisit; guard jendela
  kirim memakai `tanggal_kiriman_terakhir(end)` (`kpi_service.py:167,172`), sehingga bila
  `end` berada 9 hari di depan, `tanggal_kirim` = tanggal `end` dan rencana yang belum
  terjadi **lolos** guard lalu dihitung sebagai gagal (0 porsi terkirim).
- **Dampak:** dua kerusakan sekaligus — (a) melanggar aturan kamus §3 "`end` selalu `now`:
  KPI tidak boleh menghitung fakta yang belum terjadi"; (b) angka bisa dibuat terlihat buruk
  (0 %) atau "ada data" hanya dengan memilih jendela ke depan, padahal tidak ada kejadian.
- **Tidak terkena:** jendela `periode=today|7d|1bulan` (end = now) — semua nilai di §5 aman.
- **Saran:** jepit `end = min(end, now)` di `api/kpi.py` (atau tolak 422 bila `end > now +
  toleransi`). Ini perubahan kontrak kecil dan tidak mengubah angka jendela kanonik.

### NUM-04 — Meal Continuity `today` = 0,00 % setelah 21.00 WIB

- **Severity:** P2 · **Status:** CONFIRMED
- **Bukti:**
  ```
  MAX(delivery_events.delivered_at) = 2026-10-25 (WIB); 26 Okt: 0 baris
  menu_plans 26 Okt (Jakarta): planned 1.211, delivered 0
  API 20:59 WIB → no_data ("jendela kirim belum tiba", sampel 1)
  API 21:01 WIB → available 0.00 (sampel 1)
  API 21:39 WIB (periode=today) → available 0.00 ; 7d = 85.60
  ```
- **Sebab:** `JAM_KIRIM_UTC = 14` (21.00 WIB). Sebelum ambang, rencana hari ini dikecualikan;
  sesudah ambang ia masuk penyebut. Dataset dibangun 20:42 WIB — **sebelum** ambang — dan
  generator hanya menulis kiriman hari ini bila dijalankan setelah 21.00 WIB
  (`app/seed/timeseries.py:398-409`). Jadi baris kiriman 26 Okt tidak pernah ada.
- **Dampak:** bila demo berjalan setelah 21.00 WIB, kartu "Keberlanjutan menu" menampilkan
  **0,00 %** (bukan "—"), dan "7 hari" turun dari **100,00 %** ke **85,60 %** untuk Jakarta
  (−14,40 poin; 8.411/8.411 → 7.200/8.411), serta dari **99,97 %** ke **85,63 %** untuk global
  (−14,34 poin; 84.033/84.057 → 71.976/84.057). Selisih itu berasal dari **satu** baris
  `delivery_events` yang hilang (rencana 26 Okt: 1.211 porsi Jakarta, 12.057 porsi global).
- **Bukan bug rumus:** rumus menyatakan 0 % karena jendela sudah lewat dan tak ada kiriman —
  persis definisi. Masalahnya ada di pembangunan data.
- **Saran:** jalankan `generate_timeseries()` (atau rebuild template) **setelah** 21.00 WIB
  pada hari demo, atau tulis kiriman hari ini lebih awal. Butuh keputusan owner karena
  menyentuh data panggung.

### NUM-05 — `coverage` dilaporkan "1.00" pada state `no_data`

- **Severity:** P3 · **Status:** CONFIRMED
- **Bukti:** Regional Imbalance `no_data` tetap mengirim `coverage = "1.00"` dan `sample_count = 0`;
  Meal Continuity `no_data` (alasan "belum jendela kirim") mengirim `coverage = null`, sedangkan
  saat `available` selalu `1.00`. UI: `KPIDashboard.tsx:284-289` mencetak
  `cakupan ${fmtCoverage(m.coverage)}`; `fmtCoverage("1.00")` → **"100%"**
  (`frontend/lib/kpi.ts:281-287`).
- **Dampak:** kartu tanpa nilai bisa terbaca "sampel 0 · cakupan 100%". Kontrak `coverage`
  di kamus KPI ("bagian yang bisa dinilai") tidak terpenuhi.
- **Saran:** kirim `coverage = None` bila state ≠ `available`, atau isi `coverage` dengan
  angka nyata; samakan dengan lima metrik lain yang sudah `None`.

### NUM-06 — Dedupe lineage hanya melihat baris di dalam jendela

- **Severity:** P3 · **Status:** NOT_REPRODUCED (mekanisme LIKELY)
- **Bukti/mekanisme:** `parent_map` dan `root_status` dibangun dari `det_rows`
  (`kpi_service.py:322-333`), yaitu hanya keputusan yang punya `DETECT` di jendela.
  Konsekuensi: (a) anak yang DETECT-nya di jendela tetapi induknya di luar jendela dianggap
  akar baru; (b) status `executed` milik akar **di luar jendela** tidak terlihat, sehingga
  kasus yang sudah selesai bisa dihitung belum selesai.
- **Uji:** recursive CTE lewat seluruh tabel menghasilkan akar/executed **identik** dengan
  pendekatan kode di keenam sel (3/1, 3/1, 3/0, 6/1, 6/1, 3/1), karena pada 23 lineage yang
  ada hanya akar yang punya `DETECT` (anak: 0). Jadi **belum terpicu** pada data ini.
- **Saran:** bila kelak `repropose` menulis DETECT pada anak, hitung lineage dari tabel penuh
  (satu query rekursif) agar hasil tidak bergantung jendela.

### NUM-07 — Decision Time tidak menjepit durasi negatif

- **Severity:** P3 · **Status:** NOT_REPRODUCED (mekanisme LIKELY)
- **Mekanisme:** `(act_at − detect_at)` dibagi 60 tanpa `MAX(..., 0)`; kamus KPI sendiri
  mencatat `step_at` satu putaran bisa identik/lebih awal dari `created_at`, sehingga
  `ACT < DETECT` mungkin dan akan menurunkan rata-rata.
- **Uji:** satu-satunya ACT berjarak +4,00 menit; tidak ada durasi negatif pada data sekarang.
- **Saran:** buang atau jepit durasi negatif, dan laporkan jumlahnya sebagai bagian alasan.

### NUM-08 — Avoidable Food Loss terbatas maksimum 50 % secara struktur

- **Severity:** P3 · **Status:** NEEDS_PRODUCT_DECISION
- **Mekanisme:** `d / (d + s)`. Bila seluruh pasokan terbuang (`d = s`), hasilnya **50 %**,
  bukan 100 %; nilai hanya mendekati 100 % bila `s → 0` (pasokan tak tercatat). Karena itu
  label UI "persentase susut" tidak sama dengan "bagian input yang terbuang".
- **Uji:** nilai sekarang jauh di bawah batas (0,04–0,59 %), jadi tidak ada salah saji hari ini;
  yang salah adalah **tafsir** angka pada nilai ekstrem.
- **Saran:** putuskan definisi — `d / s` (bagian input terbuang, bisa > 100 % bila data
  pasokan kurang) atau tetap `d / (d + s)` dengan label "rasio buangan terhadap
  buangan + pasokan" dan skala maksimum 50 % di UI.

### NUM-09 — Envelope `period` tidak menormalkan zona

- **Severity:** P3 · **Status:** CONFIRMED
- **Bukti:** `GET /kpi?start=2026-10-26T00:00:00Z&…` mengembalikan
  `period.start = "2026-10-26T00:00:00+00:00"`, sedangkan permintaan setara dengan `+07:00`
  mengembalikan `"…+07:00"`; `period.timezone` tetap `"Asia/Jakarta"`. Nilai ketujuh metrik
  identik (dibuktikan), jadi ini murni representasi.
- **Dampak:** klien yang mem-parse `period.start` tanpa Normalisasi zona akan menampilkan
  tanggal yang bergeser 7 jam (mis. 31 Okt 20.00Z = 1 Nov WIB).
- **Saran:** normalkan `period.start/end` ke `ZoneInfo("Asia/Jakarta")` pada output, atau
  tambahkan field `start_wib`/`end_wib`. UI sekarang aman karena selalu memformat dengan
  `timeZone: "Asia/Jakarta"` (`frontend/lib/kpi.ts:199-271`).

### NUM-10 — `location_id` tak dikenal menghasilkan `no_data`, bukan error

- **Severity:** P3 · **Status:** CONFIRMED
- **Bukti:** `bgn_monitor` + `location_id=00000000-0000-0000-0000-000000000000` → HTTP 200,
  ketujuh metrik `no_data` (tanpa alasan khusus). Sebaliknya `bgn_monitor` +
  `location_id=275d1be7-…` menghasilkan angka **identik** dengan scope `sppg_head` Jakarta
  (dibuktikan: 7/7 metrik sama) — jadi filter lokasi sendiri benar.
- **Dampak:** salah ketik UUID tidak bisa dibedakan dari "lokasi ini memang belum punya data";
  pada dashboard monitor nasional, kesalahan konfigurasi tampak seperti kelangkaan data.
- **Saran:** validasi keberadaan lokasi → 404/422, atau sertakan `scope.location_known: false`.

### NUM-11 — Cap `LEAST()` tidak pernah aktif

- **Severity:** P3 · **Status:** CONFIRMED
- **Bukti:** `delivered_raw` = `delivered_capped` di semua enam sel (7200/7200, 20746/20746,
  71976/71976, 209414/209414, 0/0). Tidak ada rencana dengan kiriman melebihi porsi rencana.
- **Dampak:** bukan kesalahan, tetapi **klaim "over-delivery dipotong 100 %" belum punya bukti
  data**; bila kelak ada kiriman berlebih, perilakunya hanya dijamin oleh kode, bukan oleh uji
  runtime yang terdokumentasi di sini.
- **Saran:** tambahkan kasus uji (DB klon) dengan `delivered > planned` untuk mengunci perilaku.

### NUM-12 — Baris bertanggal masa depan masih ada

- **Severity:** P3 · **Status:** CONFIRMED
- **Bukti:** lihat §6.3 — `supply_records` **720** (386.355,50 kg), `price_signals` **840**,
  `disposal_events` **20** (150,30 kg), `demand_records` **360**, `menu_plans` 100.
- **Dampak:** tidak mengubah satu pun angka pada §5 (semua query berbatas atas), tetapi menjadi
  bahan bakar NUM-03 dan membuat setiap analisis "sampai akhir periode" harus memilih
  `end = now` dengan sadar.
- **Saran:** biarkan (data deret waktu memang ke depan) tetapi dokumentasikan di kamus KPI
  bahwa `end` kanonik = `now`, dan jepit `end` di API (NUM-03).

### NUM-13 — Evidence Completeness `available 0,00 %` dengan cakupan 4–7 %

- **Severity:** P3 · **Status:** NEEDS_PRODUCT_DECISION
- **Bukti:** penyebut 1 (Jakarta 7d/1bulan) dan 1–2 (global) dari 15/28/32 keputusan di jendela;
  `coverage` 0,07 / 0,04 / 0,06. Hanya 3 tipe bukti dipakai di seluruh DB
  (`human_inspection`, `gps`, `market_price`), dan satu-satunya tipe `market_price` yang
  konsisten berjumlah 3 baris.
- **Dampak:** kartu berstate "tersedia" dengan nilai 0,00 % mudah dibaca sebagai kegagalan
  proses, padahal 93–96 % populasi tidak bisa dinilai (belum ada approval). Definisi
  penyebutnya sudah benar dan terdokumentasi; yang kurang adalah kejelasan tampilan.
- **Saran:** tampilkan cakupan lebih menonjol daripada nilainya saat `coverage < 0,2`, atau
  batasi state `available` hanya bila cakupan ≥ ambang yang diputuskan owner.

---

## 8. Ringkasan PASS / FAIL / UNVERIFIED per KPI

| # | KPI | Aritmetika (kode vs SQL) | Ketersediaan pada data panggung | Kesimpulan |
|---|---|---|---|---|
| 1 | Meal Continuity Rate | **PASS** — 6/6 sel cocok (0,0000) | PASS (available 6/6) | **PASS** dengan catatan NUM-04 (0,00 % setelah 21.00 WIB) & NUM-11 |
| 2 | Avoidable Food Loss | **PASS** — 6/6 sel cocok (0,0000) | PASS (available 6/6) | **PASS** dengan catatan NUM-08 (batas 50 %) |
| 3 | Regional Imbalance Resolution Rate | **PASS** — 6/6 sel cocok (0,0000) | PASS (available 5/6) | **PASS** dengan catatan NUM-05, NUM-06 |
| 4 | Safe Delivered Cost | **PASS** (rumus) — 0 baris di kedua sisi | **FAIL** — `no_data` 6/6 sel, sebab struktural NUM-01 | **FAIL (ketersediaan)** |
| 5 | Procurement Price Deviation | **PASS** — 6/6 sel cocok (0,0000) | PASS (available 6/6) | **PASS** dengan catatan jalur "tanpa pasangan" belum teruji |
| 6 | Decision Time | **PASS** (rumus) — 0 baris di kedua sisi | **FAIL** — `no_data` 6/6 sel; ACT 4,00 menit dibuang (NUM-02) | **FAIL (ketersediaan)** |
| 7 | Evidence Completeness | **PASS** — 6/6 sel cocok (0,0000) | PASS (available 5/6) | **PASS** dengan catatan NUM-13 (cakupan 4–7 %) |

Yang **UNVERIFIED** (tidak diuji di lingkungan ini, dengan alasan):

| Hal | Alasan |
|---|---|
| Nilai `Safe Delivered Cost` / `Decision Time` **sesudah** `POST /actions/execute` | butuh mutasi data; skenario itu akan mengubah dataset panggung. Jalur kodenya dibaca (`api/actions.py:824-851`) dan konsisten, tetapi angkanya tidak diukur di sini |
| Klaim kamus KPI §7.7 "Decision Time 20,98 menit (1 sampel)" | berasal dari dataset sebelum rebuild 20:42 WIB; PO/ACT-nya sudah tidak ada |
| Perilaku cap `LEAST()` saat over-delivery (NUM-11) | tidak ada baris dengan `delivered > planned` |

---

## 9. Lampiran — query yang dipakai

Semua query dijalankan lewat `psql` read-only di dalam container (tanpa transaksi tulis).
`:start`/`:end`/`:loc` di sini adalah placeholder; pada eksekusi nyata nilainya diganti
literal ISO-8601 / UUID (psql tidak melakukan binding parameter), diambil **persis** dari
`period.start`/`period.end` respons API. Baris `MAX(delivered_at) max_at` hanya dipakai
untuk varian pembanding sumbu `delivered_at`, bukan untuk nilai yang dilaporkan.

```sql
-- C5 Meal Continuity (cap + guard tanggal kirim)
WITH de AS (SELECT menu_plan_id, SUM(delivered_portions) d, MAX(delivered_at) max_at
            FROM delivery_events GROUP BY 1)
SELECT COUNT(*), COALESCE(SUM(mp.planned_portions),0),
       COALESCE(SUM(LEAST(COALESCE(de.d,0), mp.planned_portions)),0),
       COALESCE(SUM(COALESCE(de.d,0)),0),
       COALESCE(ROUND(100.0*SUM(LEAST(COALESCE(de.d,0), mp.planned_portions))
              /NULLIF(SUM(mp.planned_portions),0),6),0)
FROM menu_plans mp LEFT JOIN de ON de.menu_plan_id = mp.id
WHERE mp.plan_date >= (CAST(:start AS timestamptz) AT TIME ZONE 'Asia/Jakarta')::date
  AND mp.plan_date <= (CAST(:end   AS timestamptz) AT TIME ZONE 'Asia/Jakarta')::date
  AND (mp.plan_date <= DATE :tanggal_kirim OR de.d IS NOT NULL)
  AND mp.location_id = :loc;                      -- dihilangkan untuk scope global

-- C6 Avoidable Food Loss
SELECT (SELECT COALESCE(SUM(quantity_kg),0) FROM disposal_events
          WHERE disposed_at >= :start AND disposed_at < :end AND location_id = :loc),
       (SELECT COALESCE(SUM(quantity_kg),0) FROM supply_records
          WHERE recorded_at >= :start AND recorded_at < :end AND location_id = :loc);

-- C7 Regional Imbalance: lineage penuh (pembanding dedupe versi kode)
WITH RECURSIVE det AS (
  SELECT DISTINCT d.id, d.status FROM decisions d
  JOIN agent_traces t ON t.decision_id = d.id AND t.step_name='DETECT'
  WHERE t.step_at >= :start AND t.step_at < :end AND d.demo_case IS NULL),
walk AS (
  SELECT det.id AS origin, det.id AS cur, det.status FROM det
  UNION ALL
  SELECT w.origin, p.supersedes_id, w.status FROM walk w
  JOIN decisions p ON p.id = w.cur WHERE p.supersedes_id IS NOT NULL),
top AS (SELECT origin, cur AS root, status FROM walk w
        WHERE NOT EXISTS (SELECT 1 FROM decisions x
                          WHERE x.id = w.cur AND x.supersedes_id IS NOT NULL))
SELECT COUNT(DISTINCT root), COUNT(DISTINCT CASE WHEN status='executed' THEN root END) FROM top;

-- C8 Safe Delivered Cost (+ hitungan PO tanpa tautan)
SELECT COUNT(*), AVG(d.safe_delivered_cost),
       (SELECT COUNT(*) FROM sap_mock_purchase_orders po2
         WHERE po2.created_at >= :start AND po2.created_at < :end AND po2.decision_id IS NULL)
FROM decisions d JOIN sap_mock_purchase_orders po ON po.decision_id = d.id
WHERE po.created_at >= :start AND po.created_at < :end
  AND d.safe_delivered_cost IS NOT NULL;

-- C9 Procurement Price Deviation (referensi terakhir sebelum kutipan)
WITH q AS (
  SELECT ps.*, ref.price_per_kg AS ref_price
  FROM price_signals ps
  LEFT JOIN LATERAL (
    SELECT r.price_per_kg FROM price_signals r
    WHERE r.source='pihps_reference' AND r.location_id=ps.location_id
      AND r.commodity_id=ps.commodity_id AND r.recorded_at <= ps.recorded_at
    ORDER BY r.recorded_at DESC LIMIT 1) ref ON TRUE
  WHERE ps.source='supplier_quote' AND ps.recorded_at >= :start AND ps.recorded_at < :end)
SELECT COUNT(*), COUNT(ref_price),
       AVG(ABS(price_per_kg-ref_price)/ref_price*100) FILTER (WHERE ref_price > 0) FROM q;

-- C10 Decision Time (committed = PO ber-decision_id di jendela)
WITH tr AS (
  SELECT d.id, MIN(t.step_at) FILTER (WHERE t.step_name='DETECT') detect_at,
         MAX(t.step_at) FILTER (WHERE t.step_name='ACT') act_at
  FROM decisions d JOIN agent_traces t ON t.decision_id = d.id
  WHERE t.step_at >= :start AND t.step_at < :end GROUP BY d.id),
po AS (SELECT DISTINCT decision_id FROM sap_mock_purchase_orders
       WHERE created_at >= :start AND created_at < :end AND decision_id IS NOT NULL)
SELECT COUNT(*) FILTER (WHERE tr.detect_at IS NOT NULL) eligible,
       AVG(EXTRACT(EPOCH FROM (tr.act_at - tr.detect_at))/60.0)
         FILTER (WHERE tr.act_at IS NOT NULL AND po.decision_id IS NOT NULL)
FROM tr LEFT JOIN po ON po.decision_id = tr.id;

-- C11 Evidence Completeness
WITH dec AS (
  SELECT d.id, MIN(a.approved_at) FILTER (WHERE a.approved IS TRUE) cutoff
  FROM decisions d LEFT JOIN approvals a ON a.decision_id = d.id
  WHERE d.created_at >= :start AND d.created_at < :end GROUP BY d.id),
ev AS (
  SELECT e.decision_id, COUNT(DISTINCT e.evidence_type) n_types
  FROM decision_evidence e
  WHERE e.is_consistent IS TRUE AND e.recorded_at < (
     SELECT MIN(a.approved_at) FROM approvals a
     WHERE a.decision_id=e.decision_id AND a.approved IS TRUE)
  GROUP BY e.decision_id)
SELECT COUNT(*), COUNT(*) FILTER (WHERE dec.cutoff IS NOT NULL),
       COUNT(*) FILTER (WHERE dec.cutoff IS NOT NULL AND COALESCE(ev.n_types,0) >= 2)
FROM dec LEFT JOIN ev ON ev.decision_id = dec.id;

-- §6.3 baris masa depan
SELECT count(*) FROM supply_records WHERE recorded_at > now();   -- 720
SELECT count(*) FROM price_signals  WHERE recorded_at > now();   -- 840
```

Verifikasi pembulatan dan periode dijalankan di dalam container aplikasi (tanpa DB):

```python
quantize2(Decimal("85.625"))                      # 85.63  (round() Python: 85.62)
quantize2(Decimal("2.675"))                       # 2.68   (round() Python: 2.67)
quantize2(Decimal("0.005"))                       # 0.01
tanggal_kiriman_terakhir(datetime(2026,10,26,13,59,59,tzinfo=UTC))  # 2026-10-25
tanggal_kiriman_terakhir(datetime(2026,10,26,14, 0, 0,tzinfo=UTC))  # 2026-10-26
resolve_periode("today", datetime(2026,11,1,0,30,tzinfo=WIB))       # 2026-10-31T17:00Z … now
resolve_periode("1bulan", datetime(2026,11,1,0,30,tzinfo=WIB))      # 2026-10-31T17:00Z … now
resolve_periode("today", datetime(2026,10,26,10,0))                 # ValueError (naive)
resolve_periode("24h",   datetime(2026,10,26,10,0,tzinfo=UTC))      # KeyError
```

---

## 10. Kesimpulan dan urutan tindakan yang disarankan

1. **NUM-03** (jepit `end` ke `now`) — satu perubahan kecil di `api/kpi.py`, menutup jalur
   "KPI menghitung masa depan" dan membuat §6.3 tidak lagi berbahaya.
2. **NUM-01/NUM-02** — putuskan: tautkan PO seed ke keputusan `executed`, atau jadikan
   kedua kartu itu eksplisit "menunggu eksekusi" di UI. Salah satu harus dipilih sebelum
   dashboard dipakai sebagai bukti angka.
3. **NUM-04** — bangun ulang data setelah 21.00 WIB pada hari demo, atau terima bahwa
   "Keberlanjutan menu" hari itu akan terbaca 0,00 %.
4. **NUM-05/NUM-09/NUM-10** — perbaikan kontrak kecil (coverage, normalisasi zona, validasi
   lokasi) yang tidak mengubah satu pun angka.
5. **NUM-06/NUM-07/NUM-08/NUM-11/NUM-13** — keputusan produk atau penguncian dengan uji,
   bukan bug yang mendesak.

Tidak ditemukan satu pun selisih antara API dan hitungan SQL independen: **28 dari 28 sel
`available` identik setelah pembulatan 2 desimal**, dan **14 dari 14 sel `no_data`** juga
tereproduksi (alasan dan `sample_count` sama) — total 42/42 sel. Risiko numerik proyek ini bukan pada
aritmetika, melainkan pada **keterhubungan data** (PO ↔ keputusan) dan **batas jendela**.
