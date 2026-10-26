# UI ↔ API ↔ DB CONSISTENCY — MealChain Guardian

Diukur 26 Oktober 2026, 21:40–21:46 WIB. Repo `E:\hackathon\HackathonAWS\mealchain-guardian`
(git `5885810`), stack Compose hidup, peran uji **`sppg_head` Jakarta** (kecuali disebut lain),
pembanding peran **`bgn_monitor`** (nasional).

## 1. Metode

| Lapisan | Cara mengambil nilai |
|---|---|
| API | Login `POST /auth/login` di dalam kontainer backend, lalu `GET` read-only (`urllib`), tanpa mencetak token |
| DB | `docker exec mealchain-postgres psql -U <user> -d mealchain -c "SELECT …"` (SELECT saja) |
| UI | Nilai yang **akan** dirender diturunkan dari payload API + fungsi murni/komponen yang dipakai (berkas + baris dikutip), bukan dari tangkapan layar |

Urutan tiap pasangan: panggil API → baca DB dalam < 1 menit → petakan ke kode UI. Tidak ada POST
selain login; DB demo tidak ditulis.

**Batas metode:** angka UI di bawah adalah hasil turunan kode (fungsi murni + label JSX) atas payload
API nyata. Audit ini tidak menjalankan browser, jadi tidak ada bukti DOM langsung; bila kelak ada
selisih render, penyebabnya paling mungkin ada di komponen, bukan di angka API.

## 2. Enam pasangan terukur

### KONS-01 — KPI "Hari ini" (7 kartu)

- API: `GET /kpi?periode=today` (`backend/app/api/kpi.py:33`, UI `frontend/lib/hooks/useKpi.ts:41-45` → `frontend/lib/api.ts:749`)
- Jendela yang dilaporkan server: `2026-10-25T17:00:00Z` → `2026-10-26T14:40:43Z` (= hari kalender 26 Okt WIB), `data_source: live_aggregate`, `scope.role: sppg_head`
- DB: agregat dihitung ulang dengan SQL yang sama seperti `app/services/kpi_service.py:127` (`compute_kpis`)
- UI: satu kartu per metrik, nilai `null` dirender "—" + alasan + `sampel N · cakupan` (`frontend/components/KPIDashboard.tsx:227-292`); strip "Hari Ini" menghitung metrik yang punya nilai (`frontend/components/TodayDashboard.tsx:203-206`)

| Metrik | API (nilai / state / sampel) | Hitungan DB | Cocok? |
|---|---|---|---|
| Meal Continuity Rate | `0.00` percent · available · sampel 1 | 1 baris `menu_plans` (plan_date 26 Okt, Jakarta): 1.211 porsi rencana, 0 porsi terkirim → 0,00 % | ✔ |
| Avoidable Food Loss | `0.59` percent · available · sampel 3 | disposal 31,49 kg; supply 5.267,21 kg → 31,49/(31,49+5.267,21) = 0,5943 % | ✔ |
| Regional Imbalance Resolution Rate | `null` · no_data · sampel 0 | 0 keputusan `demo_case IS NULL` berjejak `DETECT` di Jakarta pada jendela | ✔ (alasan "tidak ada DETECT" benar) |
| Safe Delivered Cost | `null` · no_data · sampel 0 | 12 PO dibuat < 24 jam, tetapi **0** ber-`decision_id` → JOIN ke `decisions` kosong | ✔ (lihat DIFF-01) |
| Procurement Price Deviation | `2.66` percent · available · sampel 17 | 17 kutipan `supplier_quote` berpasangan PIHPS; rata-rata deviasi absolut = 2,66 % | ✔ |
| Decision Time | `null` · no_data · sampel 7 | 7 keputusan Jakarta punya `DETECT`; **0** punya `ACT` → penyebut nol | ✔ |
| Evidence Completeness | `null` · no_data, alasan "11 keputusan ada, tetapi belum satu pun disetujui" | 11 keputusan dibuat dalam jendela di Jakarta, 0 di antaranya ber-approval | ✔ (lihat DIFF-04) |

Status: **MATCH** (7/7). Tiga metrik terisi, empat jujur "—" dengan alasan yang bisa dibuktikan di DB.

### KONS-02 — Jumlah kartu keputusan per status

- API: `GET /decisions?limit=200` (`backend/app/api/decisions.py:199`, scope lokasi dari `apply_location_scope`)
- DB: `SELECT status, count(*) FROM decisions d JOIN locations l ON l.id=d.target_location_id WHERE l.name='Jakarta' GROUP BY 1`
- UI: angka "N menunggu tindakan" (`frontend/app/page.tsx:936`, `frontend/components/DecisionEvidence.tsx:272`) memakai `countActionable` (`frontend/lib/topbar.ts:209`); daftar kartu memakai jendela "hari ini" (`/decisions?window=24h`)

| Ukuran | API | DB | UI | Cocok? |
|---|---|---|---|---|
| Keputusan dalam scope Jakarta (semua) | `total 15` | 15 | `decisions.length` = 15 (`DecisionEvidence.tsx:278`) | ✔ |
| `pending_approval` | 9 | 9 | badge per kartu | ✔ |
| `verifier_flagged` | 2 | 2 | badge per kartu | ✔ |
| `rejected` | 3 | 3 | badge per kartu | ✔ |
| `executed` | 1 | 1 | badge per kartu | ✔ |
| Menunggu tindakan (bisa ditindak) | 11 (9+2), `expired` 0 | 11 `pending_approval`+`verifier_flagged` dengan `expires_at > now()` | `countActionable` = 11 | ✔ |
| Jendela "hari ini" | `window=24h` → 11 | 11 dibuat dalam hari kalender WIB | daftar 11 kartu | ✔ |
| Scope nasional (`bgn_monitor`) | `total 32` | 32 | — | ✔ |

Status: **MATCH** (semua baris).

### KONS-03 — Batch & karantina

- API: `GET /batches?limit=500` (`backend/app/api/batches.py:36`; UI memanggil lewat `frontend/lib/hooks/useToday.ts:28-35` → `frontend/lib/api.ts:765`)
- DB: `SELECT quarantine_status, count(*) FROM batches GROUP BY 1`; agregat umur `< now()` dan `< now()+48h`
- UI: tile "Batch <48 jam" dari `batchExpiry` (`frontend/lib/today.ts:138-160`) lewat `summaryTiles` (`frontend/lib/today.ts:276-316`); tile "Ditahan (karantina)" di `frontend/components/FoodSafetyBoard.tsx:715`

| Ukuran | API | DB | UI | Cocok? |
|---|---|---|---|---|
| Total batch | `count 78`, `total 78` | 78 | daftar batch di "Hari Ini" | ✔ |
| Sebaran lokasi | 10 lokasi (Jakarta 8) | 10 lokasi (Jakarta 8) | — | ✔ |
| `quarantine_status = quarantined` | 1 | 1 (Jakarta, beras, 540 kg) | tile "Ditahan (karantina)" = 1 | ✔ |
| Batch kedaluwarsa (`usable_until < now`) | — (tidak dikirim sebagai agregat) | 1 (Jakarta) | bagian "kedaluwarsa 1 batch" | ✔ |
| Batch `< 48 jam` | — | 1 kedaluwarsa + 6 segera = 7 | tile "Batch <48 jam" = 7, catatan "seluruh jaringan" | ✔ |

Catatan jujur: `/batches` **sengaja lintas lokasi** (komentar di `backend/app/api/batches.py:50-56`:
panel chaos Event 3 butuh batch dari lokasi mana pun). Jadi "1 kedaluwarsa / 1 ditahan" adalah angka
jaringan, bukan angka Jakarta. UI sudah menyebut "seluruh jaringan" (`frontend/lib/today.ts:307-316`),
sehingga tidak ada klaim palsu — tetapi pembaca yang melewatkan catatan itu bisa menyimpulkan angka
Jakarta. Lihat DIFF-02.

Status: **MATCH** dengan catatan cakupan.

### KONS-04 — Pemasok & sertifikasi

- API: `GET /suppliers?limit=200` (`backend/app/api/suppliers.py:154`; UI `frontend/lib/api.ts:807`, hook `frontend/lib/hooks/useSuppliers.ts`)
- DB: `SELECT count(*), count(*) FILTER (WHERE certification_status='none'/'hygiene'/'haccp') FROM suppliers`
- UI: pil jumlah `{metrics.suppliers} pemasok` (`frontend/components/SupplierBoard.tsx:148`), kolom "Sertifikasi" (`:398, :442`), pemetaan `certification_status → certification` di `frontend/lib/supplier-pins.ts:221`, label manusiawi di `:394`

| Ukuran | API | DB | UI | Cocok? |
|---|---|---|---|---|
| Jumlah pemasok | `count 60`, `total 60` | 60 | pil "60 pemasok" | ✔ |
| `none` (tidak bersertifikat) | 8 | 8 | "Tidak bersertifikat" | ✔ |
| `hygiene` | 35 | 35 | label hygiene | ✔ |
| `haccp` | 17 | 17 | label HACCP | ✔ |
| Eksklusi aktif/usulan | `GET /supplier-exclusions` → 2 item | 2 baris register | panel eksklusi | ✔ |
| Baris tampil per halaman | 60 dikirim | 60 | **10 baris/halaman** (`SupplierBoard.tsx:67,120`) | ✔ (paginasi UI) |

Status: **MATCH** dengan catatan paginasi (DIFF-03).

### KONS-05 — Purchase order & penerimaan barang

- API: `GET /sap/purchase-orders?limit=200` + `/sap/purchase-orders/summary` (`backend/app/api/sap_orders.py:109,152`; UI `frontend/lib/hooks/usePurchaseOrders.ts:23,32`)
- DB: `SELECT status, count(*), count(*) FILTER (WHERE decision_id IS NOT NULL) FROM sap_mock_purchase_orders`
- UI: `frontend/components/PurchaseOrderList.tsx` — teks kosong dibedakan per cakupan (`:226-230`), catatan limit (`:234-245`)

| Ukuran | `sppg_head` (lokasi) | `bgn_monitor` (nasional) | DB | Cocok? |
|---|---|---|---|---|
| Daftar PO | `count 0` | `count 12` | 12 baris | ✔ untuk nasional; **0 untuk SPPG** (lihat DIFF-01) |
| Ringkasan status | `{draft 0, submitted 0, confirmed 0}`, nilai 0 | `{draft 0, submitted 2, confirmed 10}`, nilai **117.690.000** | 2 `submitted` + 10 `confirmed` | ✔ |
| PO tertaut keputusan | — | — | **0 dari 12** (`decision_id IS NULL` semua) | penyebab SDC kosong |
| Penerimaan menunggu | `GET /receipts/menunggu` → 1 item (batch ayam 80 kg, Jakarta) | — | 1 baris `batch_receipts` | ✔ |
| Teks UI saat kosong | "Belum ada purchase order untuk SPPG Anda." | "Belum ada purchase order tercatat." | — | ✔ jujur per cakupan |

Status: **MATCH** secara angka; ada **asimetri peran** yang perlu diketahui (DIFF-01).

### KONS-06 — Ledger blocks

- API: `GET /ledger/verify` (`backend/app/api/ledger.py:14`; UI `frontend/lib/hooks/useToday.ts:30-34`, `frontend/lib/api.ts:838`)
- DB: `SELECT count(*), count(*) FILTER (WHERE entity_id IS NOT NULL), count(*) FILTER (WHERE generation = max(generation)) FROM ledger_blocks`
- UI: `frontend/components/IntegrityPanel.tsx:146` (`{ledger.blocks}`), catatan cakupan `:164` lewat `frontend/lib/ledger.ts:23-40`

| Ukuran | API | DB | UI | Cocok? |
|---|---|---|---|---|
| Total blok | `blocks 1742` | 1742 | "Blok 1742" | ✔ |
| Blok generasi aktif (239) | `entity_blocks 72` | generasi 239 = 72 blok, semuanya ber-`entity_id` | — | ✔ |
| Blok tertaut | `linked_blocks 60` | — (dihitung layanan dari entitas yang masih ada) | "60 dari 72 blok masih tertaut" | ✔ |
| Blok yatim | `orphan_blocks 12` | 72 − 60 = 12 | peringatan cakupan | ✔ |
| Blok arsip | `archived_blocks 1670` | 1742 − 72 = 1670 | "1.670 blok generasi lama diarsipkan" | ✔ |
| Rantai valid | `valid true`, `head` terisi | — (verifikasi dihitung layanan) | chip rantai + head 12 karakter pertama | ✔ |

Status: **MATCH** (semua angka bisa diturunkan dari DB).

## 3. Selisih dan penyebabnya

| ID | Severity | Status | Selisih | Penyebab | Dampak |
|---|---|---|---|---|---|
| DIFF-01 | Medium | Open (by design + celah seed) | SPPG Head melihat **0 PO** padahal DB berisi 12 PO (10 confirmed, 2 submitted, nilai 117,69 juta) | `sap_orders.py:126-129` (daftar) dan `:167-168` (ringkasan) menyaring `d.target_location_id = :lokasi`; 12 PO seed punya `decision_id NULL`, sehingga JOIN `decisions` menggugurkan semuanya. KPI Safe Delivered Cost ikut kosong karena alasan yang sama | Panel PO SPPG selalu kosong saat demo; pengawas nasional melihat 12. Angka "0" di sini benar untuk cakupan, tetapi jejak "PO terbit dari eksekusi" tidak bisa didemokan tanpa eksekusi baru |
| DIFF-02 | Low | Accepted (terdokumentasi) | SPPG Head Jakarta (punya 8 batch) melihat **78 batch** dan tile agregat jaringan (1 kedaluwarsa, 7 `<48 jam`, 1 ditahan) | `/batches` sengaja lintas lokasi untuk panel chaos Event 3 (`batches.py:50-56`); UI memberi label "seluruh jaringan" (`today.ts:307-316`) | Risiko salah baca: tile bisa disangka angka Jakarta. Tidak ada angka yang dikarang |
| DIFF-03 | Low | Accepted (UI) | Pil "60 pemasok" vs tabel 10 baris | Paginasi klien `BARIS_PER_HALAMAN = 10` (`SupplierBoard.tsx:67,120`); API mengirim 60 dengan `limit=200` | Bukan kehilangan data; tetapi "60" dan "10 baris" bisa tampak bertentangan tanpa membaca pager |
| DIFF-04 | Low | Open (teks) | Alasan Evidence Completeness menulis "11 keputusan ada" sementara scope punya 15 keputusan | `kpi_service.py` menghitung `ev_rows` hanya untuk `created_at` di dalam jendela 24 jam (11), sedangkan 15 adalah seluruh riwayat scope | Pembaca bisa mengira 4 keputusan hilang; angkanya benar untuk jendela KPI |
| DIFF-05 | Info | Limitation | `decisions` berubah 48 → 32 baris dalam 2 menit selama audit | DB demo dipakai bersama; proses/sesi lain menyentuh data demo (tidak ada DELETE dari audit ini) | Semua pasangan diukur sebagai snapshot berpasangan dan cocok saat itu; angka di dokumen ini tidak boleh dikutip sebagai keadaan sekarang |

## 4. Kesimpulan

- Enam pasangan yang diuji **cocok** antara API dan DB; UI menurunkan angka dari payload yang sama
  (tidak ada agregat yang dikarang di komponen).
- Dua selisih yang berdampak demo berasal dari **cakupan peran** (PO: DIFF-01) dan **cakupan endpoint**
  (batch: DIFF-02), keduanya tertulis di kode dan sebagian sudah diberi label di layar.
- Satu selisih teks (DIFF-04) layak diperbaiki karena menyebut penyebut yang berbeda dari cakupan
  halaman.
- Tidak ditemukan angka UI yang tidak dapat ditelusuri ke API/DB pada enam pasangan ini.

## 5. Yang tidak diuji

| Area | Status |
|---|---|
| Pembacaan DOM langsung (browser/Playwright) untuk enam pasangan ini | **NOT TESTED** |
| Pasokan lain: agenda, surplus/limbah, harga, rute pemasok, panel agen | **NOT TESTED** (di luar enam pasangan yang diminta) |
| Perilaku setelah mutasi (approve → execute → PO baru) | **NOT TESTED** (butuh tulis DB demo) |
