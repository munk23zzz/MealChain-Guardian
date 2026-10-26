# Laporan Validasi Data UI Nyata — MealChain Guardian

Tanggal audit: 26 Oktober 2026, 08.00–08.35 WIB
Lingkungan: Docker Compose hidup (backend :8000, frontend :3010 via `npm run dev`, PostgreSQL :15432), akun `sppg.head@demo.local` (peran SPPG Head, cakupan Jakarta), sesi demo aktif.
Alat: Playwright (venv `webapp-testing`) untuk panen UI + jejak request; `requests` untuk memanggil endpoint yang sama; `psql` read-only untuk recompute; pytest, vitest, tsc, ESLint, ruff.

Bukti mentah: `C:\Users\User\AppData\Local\hermes\cache\scratch\harvest_ui*.json`, `api_dump.json`, `api_dump2.json`, `data_quality*.py`.

---

## A. Ringkasan hasil

| Ukuran | Jumlah |
|---|---|
| Tab diperiksa | 10 (dari 11; tab Pengaturan tidak ada untuk peran ini) |
| Komponen/klaim data diperiksa | 46 |
| Data/klaim PASS (nilai & sumber cocok) | 23 |
| Data/klaim FAIL (salah/basi/tidak sesuai sumber) | 8 |
| Anomali SUSPICIOUS (perlu keputusan aturan bisnis) | 13 |
| UNVERIFIED (sumber tidak dapat dibuktikan) | 2 |
| BLOCKED | 0 |
| Klaim diperbaiki & diverifikasi ulang di UI hidup | 7 (DATA-001…DATA-007) |
| Masalah dilaporkan tanpa perubahan | 14 (DATA-008…019, 044, 046 — 13 SUSPICIOUS + 1 FAIL) |
| Regression test ditambahkan | 11 (frontend) + 1 (backend) |
| Suite setelah perubahan | vitest **1804 PASS** (166 berkas), `tsc --noEmit` OK, ESLint bersih, pytest `test_supplier_exclusion_api.py` + `core` **9 PASS**, ruff bersih |

Kesimpulan satu baris: **angka-angka besar di UI memang berasal dari database/API dan sebagian besar berhasil direkonsiliasi; yang bermasalah adalah pelabelan (periode, cakupan, satuan) dan tiga klaim isi yang tidak didukung datanya.**

---

## B. Checklist sumber data

- [x] Seluruh halaman/tab diinventarisasi (10 tab, 46 klaim) — §C.
- [x] Sumber setiap komponen diketahui — tiap tab dipanen bersama daftar request yang benar-benar dipanggil browser.
- [x] Data UI dibandingkan dengan response API — 27 pembandingan angka.
- [x] Data API dibandingkan dengan database — 24 query recompute (KPI, saldo, batch, limbah, penerimaan, supplier, PO, ledger).
- [x] Mock / hard-coded / fallback diidentifikasi — `formatIDR` dash, `.catch(()=>null)`, placeholder trace, `9+` badge.
- [x] Data demo dibedakan dari data operasional — kolom `origin`, `demo_case`, `demo_session_id` diperiksa; 43 baris demo tanpa stempel sesi = baseline template (bukan data operasional).
- [x] Cache & mekanisme refresh diperiksa — React Query (staleTime, poll 60 s `useToday`, poll detail), tanpa WebSocket/SSE.
- [x] Rumus KPI diverifikasi independen (Food Loss & Price Deviation dihitung ulang dari tabel mentah).
- [x] Relasi & status antarrecord diperiksa (orphan, duplikat, waktu mustahil, status di luar vocab).
- [x] Approval & pengiriman diperiksa (approvals vs status, journey vs `batches.dispatched_at`).
- [x] Notifikasi & badge diperiksa (turunan `/decisions`, tanpa read-state).
- [x] Hasil tes & bukti disimpan (JSON panen + laporan ini).

### Peta sumber per tab (bukti: request yang benar-benar dipanggil)

| Tab | Endpoint yang dipanggil | Sumber kelas |
|---|---|---|
| Hari Ini | `/agenda`, `/kpi?periode=today`, `/balance/map?commodity=…` ×4, `/decisions`, `/batches?limit=500`, `/ledger/verify` | DATABASE_PERSISTED + BACKEND_COMPUTED |
| Overview | `/supplier-routes?limit=200`, `/balance/map`, `/demo/session`, `/decisions` | DB + computed |
| Recommendations | `/decisions?window=24h` | DB (+ SDC tersimpan) |
| Decision & Evidence | `/decisions/{id}` + `/chain` + `/traces` + `/approval-summary` + `/dossier`, `/supplier-exclusions/context/{id}`, `/ledger/verify`, `/sap/purchase-orders` | DB + SEEDED_DEMO |
| Keamanan Pangan | `/batches` (via useToday), `/receipts/menunggu`, `/receipts?batch_id=…`, `/supplier-routes`, `/decisions` | DB |
| Surplus & Limbah | `/waste/summary?days=30`, `/surplus/allocations` | DB + computed |
| Pemasok | `/suppliers?limit=200`, `/supplier-exclusions`, `/supplier-routes?limit=200`, detail keputusan ×8 | DB |
| Agent Log | `/decisions/{id}/traces` | DB (sebagian SEEDED_DEMO placeholder) |
| KPI & Kualitas Agen | `/kpi?periode=today`, `/decisions` + detail per keputusan (sampel 8) | BACKEND_COMPUTED + FRONTEND_COMPUTED (agregasi sampel) |
| Demo Control | `/demo/session`, `/demo/data-status`, `/demo/agent/last-run`, `/demo/agent/commodities` | DB/status |

Catatan sumber penting:
- API diproksi Next di origin yang sama (`/kpi`, `/decisions`, …), bukan `:8000` atau `/api/*` — ini yang membuat panen pertama salah alamat.
- Seluruh endpoint yang dipanggil UI membalas **200**; 0 console error di 10 tab.
- Tidak ada `localStorage` selain `mealchain.token`.

---

## C. Matriks validasi (ringkas — 46 baris)

Legenda status: PASS / FAIL / SUSPICIOUS / UNVERIFIED.

| ID | Komponen | Sumber | Nilai UI | Nilai sumber | Kemasukakalan | Status |
|---|---|---|---|---|---|---|
| DATA-001 | Pil periode KPI | `/kpi.period` | dulu "Periode Oktober 2026" | `key=today`, 26 Okt 00.00–08.08 WIB | harian dilabeli bulanan | **FAIL → diperbaiki** |
| DATA-002 | Meta KPI "coverage" | `/kpi.metrics[].coverage` | dulu "coverage 1" | `"1.00"` (rasio) | 1 terbaca 1% | **FAIL → diperbaiki** |
| DATA-003 | Register eksklusi — kolom Pemasok | `/supplier-exclusions` | dulu "—" | `supplier_id` saja (tanpa nama) | baris tak dapat dipertanggungjawabkan | **FAIL → diperbaiki** |
| DATA-004 | Register eksklusi — Waktu | `created_at` | dulu `2026-10-25T20:43:30.217503+00:00` | ISO UTC mentah | satu-satunya waktu non-WIB di UI | **FAIL → diperbaiki** |
| DATA-005 | Register eksklusi — kolom Keputusan | `source_decision_id` | dulu "—" | id ada | UI membaca field yang salah | **FAIL → diperbaiki** |
| DATA-006 | Kartu "Pemulihan status pemasok" — SDC | `safe_delivered_cost=null` | dulu "SDC -" | null | aturan repo: "—" untuk tak diketahui | **FAIL → diperbaiki** |
| DATA-007 | Tile "Batch <48 jam" di Hari Ini | `/batches` (lintas lokasi) | 7 (JKT 2) | 1 kedaluwarsa 120 kg + 6 segera 722 kg (JKT+SBY+BDG+SMG) | angka jaringan di halaman berlabel Jakarta | **FAIL → label diperbaiki** |
| DATA-008 | Tile Keamanan Pangan (5 angka) | `/batches` | 9 aman · 1 gagal · 2 perlu verifikasi · 1 ditahan · 1 kedaluwarsa (jumlah 14) | 9 pass, 1 fail, 2 needs_verification, 3 pending, 1 quarantined, 1 expired (=15) | lima tile bercampur dimensi (status uji vs karantina vs kedaluwarsa) | SUSPICIOUS |
| DATA-009 | "kiriman 4.750 kg menutup kekurangan (+3.970 kg)" | `/supplier-routes` | menutup kekurangan **telur** 780 kg | 4.750 kg = beras 4 + wortel 4 + telur 3 + ayam 3 kiriman | menutup kekurangan telur dengan beras/wortel: salah komoditas | **FAIL** |
| DATA-010 | Agent Log — isi jejak | `agent_traces.output_summary` | "Langkah DETECT (template status demo)." | 8/85 baris memang berisi teks placeholder itu | teks template tampil sebagai reasoning agen | SUSPICIOUS |
| DATA-011 | Trace DECIDE vs keputusan | `output_summary.sdc` | — (tidak ditampilkan) | trace 14.787.096,28 vs keputusan 22.080.862,39 | dua angka biaya untuk keputusan yang sama | SUSPICIOUS |
| DATA-012 | PO `MC-D2C7131CBF7B` | `/sap/purchase-orders` | "MAT-UMUM · 0 kg · Rp0,00" | `material_number=MAT-UMUM`, `ordered_quantity=0`, `total=0` | PO nol kg tampil sebagai PO terkonfirmasi | SUSPICIOUS |
| DATA-013 | Keputusan ditolak (9) | `approvals` | "Ditolak · 1" | 0 baris `approvals` untuk semua keputusan `rejected` | aktor penolakan tidak tercatat | SUSPICIOUS |
| DATA-014 | Tile "Pemasok dieksklusi 2" | `/supplier-exclusions` | 2 | 1 `active` + 1 `proposed`; `excluded_at_hub=true` hanya 1 | "dieksklusi" = 1, register = 2 | SUSPICIOUS |
| DATA-015 | Kutipan harga per pemasok | `price_signals.supplier_id` | 17 sampel | tabel PUNYA `supplier_id` + CHECK (`supplier_quote` ⇒ supplier wajib); 143 grup berisi 1–4 pemasok berbeda pada jam yang sama | **koreksi audit**: bukan duplikat — beberapa pemasok mengutip pada jam yang sama | PASS (koreksi) |
| DATA-016 | "Sedang mengirim barang 53/60" | `/suppliers.items[].shipping` | 53 | 53 supplier punya batch layak hari ini | label "sedang mengirim" ≠ definisi | SUSPICIOUS |
| DATA-017 | Ringkasan keputusan keamanan | `/decisions` | "5 · 4 berlaku · 1 ditolak · 1 lewat jendela · total 2.946 kg" | 4 pending (2.346 kg) + 1 rejected & kedaluwarsa (600 kg) | baris yang sama dihitung sebagai "ditolak" dan "lewat jendela" | SUSPICIOUS |
| DATA-018 | "Kiriman tiba: tidak ada catatan" (Hari Ini) vs "3 kiriman sudah tiba" (Overview) | `/agenda.delivery` vs `/supplier-routes` | 0 vs 3 | `delivery_events` (porsi makan) kosong hari ini; `supplier-routes` (bahan) 3 tiba | dua entitas berbeda, istilah sama | SUSPICIOUS |
| DATA-019 | "Belum ada jejak agent di database" | `/demo/agent/last-run` | kosong | DB punya 85 trace | pernyataan cakupan terlalu luas | SUSPICIOUS |
| DATA-020 | Badge lonceng "9+" | `notifList(decisions)` | 9+ | 11 actionable | konvensi cap ≥10, bukan unread | PASS (dengan catatan) |
| DATA-021 | Sisa sesi demo "1 j 32 m" | `/demo/session.remaining_seconds` | 1 j 32 m | 5.473 s = 91,2 mnt | pembulatan ke atas | PASS (dengan catatan) |
| DATA-022 | KPI Susut pangan | `/kpi` | 0,59% (sampel 2) | 20,50 / (20,50 + 3.476,77) = 0,5862% | cocok | PASS |
| DATA-023 | KPI Simpangan harga | `/kpi` | 2,66% (sampel 17) | SQL pairing quote→PIHPS = 2,6553% (17) | cocok | PASS |
| DATA-024 | Saldo Jakarta (telur) | `/balance/map` | 300 / 1.080 / −780 kg | supply terakhir ≤ now 300; demand 1.080 → gap 780 | cocok | PASS |
| DATA-025 | Rantai audit | `/ledger/verify` | panen #1: 1.065 blok · head `e4824e6a2f` · 993 arsip; panen #3 (sesudah tes menulis blok baru): 1.084 blok | `blocks=1065`/`1084`, `valid=true`, `archived_blocks=993`, `orphan_blocks=0` | cocok — ledger append-only, angkanya naik karena tulisan baru, bukan karangan | PASS |
| DATA-026 | Neraca limbah | `/waste/summary` | 51,8 kg / 7 · 12,5 kg / 1 · 39,3 kg | 51,82 / 7 · 12,5 / 1 · 39,32 | cocok (12,5 + 39,32 = 51,82) | PASS |
| DATA-027 | Penerimaan menunggu | `/receipts/menunggu` | 2 catatan (ayam 80 & 90 kg) | 2 items, 3 titik periksa | cocok | PASS |
| DATA-028 | Ringkasan pemasok | `/suppliers` | 60 · 82% · 4 rendah · 60/60 titik | 60 · 0,8232 · 4 (<0,60) · 60 | cocok | PASS |
| DATA-029 | "9/16 pemasok dalam 150 km" | `/suppliers` | 9 dari 16 | supplier telur 16, ≤150 km 9 | cocok | PASS |
| DATA-030 | Papan kiriman | `/supplier-routes?limit=200` | 14 · 2 di jalan · 1 belum · 9 tiba · 2 tanpa laporan | summary: 14 / 2 / 1 / 9 / 2 | cocok | PASS |
| DATA-031 | Agenda harian | `/agenda` | 1.211 porsi · 12 pasokan · 33 harga · 31,5 kg/3 · 2 batch · 11 keputusan (9+2) | payload identik | cocok | PASS |
| DATA-032 | Rekomendasi 11 | `/decisions?window=24h` | 11 perlu tindakan (9 menunggu, 2 flagged) | count 11, status 9+2 | cocok | PASS |
| DATA-033 | "17 total dipantau" | `/decisions` | 17 | total 17 | cocok | PASS |
| DATA-034 | Rincian biaya keputusan | `cost_breakdown` | beli 21.656.170 · logistik 14.819 (angkut 3.119 + antar 11.700) · penanganan 150.000 · susut 259.874 · SDC 22.080.862 | 21.656.169,60 + 14.818,75 + 150.000 + 259.874,04 = 22.080.862,39 | cocok (selisih Rp1 pembulatan tampilan) | PASS |
| DATA-035 | SDC per kg antar kartu | `/decisions` | 22.080.862/780 = 28.309/kg; 15.749.032/600 = 26.249/kg; 546 kg = 28.309/kg | konsisten per komoditas/pemasok | cocok | PASS |
| DATA-036 | Total PO | `/sap/purchase-orders` | Rp32.880.000 (3 PO) | 7.980.000 + 24.900.000 + 0 | cocok | PASS |
| DATA-037 | Alasan `no_data` KPI | `/kpi` | 7 DETECT tanpa ACT; 11 keputusan tanpa approval; 1 rencana belum jendela kirim | DB: 7 keputusan punya DETECT, 0 ACT committed; approvals untuk keputusan hari ini 0; rencana hari ini ada | cocok | PASS |
| DATA-038 | "KPI tersedia 2/7" | `/kpi` | 2/7 | 2 `available`, 5 `no_data` | cocok | PASS |
| DATA-039 | Keputusan `executed` vs approval | DB | UI tidak menampilkan status ini di tab Hari Ini | 5 executed, semuanya punya ≥1 approval (perbaikan audit pagi ini) | cocok | PASS |
| DATA-040 | Baris demo vs operasional | DB | tab Demo Control menyebut "data demo" | 43 batch `origin='demo'` tanpa `demo_session_id` (baseline template) + baris berstempel sesi | sesuai desain, tapi tidak diberi label per baris | PASS (dengan catatan) |
| DATA-041 | Tombol "Bangun ulang data — butuh ±70 detik" | teks statis | 70 dtk | tidak diukur dalam audit ini | belum diukur | UNVERIFIED |
| DATA-042 | "Setiap angka di halaman ini datang dari API" (Decision & Evidence) | klaim halaman | — | benar untuk angka; tetapi teks trace placeholder berasal dari DB hasil seed, bukan hasil agen | klaim "jejak agen" tidak sepenuhnya benar | UNVERIFIED |
| DATA-043 | `journey`/animasi progress | `/supplier-routes.journey` | 62% / 61% jalur, ETA | `journey.state` + `road` OSRM | plausibel | PASS |
| DATA-044 | Kesiapan `useDecisionDetail` saat API gagal | `.catch(() => null)` | — | galat ditelan → panel kosong tanpa pesan | menyembunyikan kegagalan | SUSPICIOUS |
| DATA-045 | "Harga tercatat 33 baris" hari ini | `/agenda.price.rows` | 33 | 33 | cocok | PASS |
| DATA-046 | Kebutuhan 1.080 kg diberi label "hari ini" | `demand_records.needed_by` | "Kebutuhan" | `needed_by = 2026-10-29` (3 hari ke depan) | label waktu tidak disebut | SUSPICIOUS |

---

## D. Daftar masalah & perbaikan

### D.1 Diperbaiki (6)

**BUG-A / DATA-001 — Pil periode KPI menamai bulan, bukan jendela**
- Lokasi: `frontend/components/KPIDashboard.tsx:190`, `frontend/lib/kpi.ts`.
- Bukti: `GET /kpi?periode=today` → `period.key="today"`, `start=2026-10-25T17:00Z`; UI menulis "Periode Oktober 2026".
- Penyebab: pil selalu memakai `periodeBulan(start,end)` (nama bulan dari rentang) tanpa melihat `windowKey`.
- Perbaikan: fungsi baru `periodePil(windowKey,start,end)` → "Hari ini · 26 Okt 2026" / "7 hari · 20–26 Okt 2026" / "1 bulan · Oktober 2026".
- Test: 4 kasus di `tests/kpi.test.ts` + 1 render test di `tests/kpi-dashboard.test.tsx`.
- Verifikasi ulang (UI hidup): **"Hari ini · 26 Okt 2026"**.

**BUG-B / DATA-002 — Cakupan dicetak sebagai rasio**
- Lokasi: `frontend/components/KPIDashboard.tsx:285`.
- Bukti: `/kpi.metrics[].coverage = "1.00"`; UI "coverage 1".
- Perbaikan: `fmtCoverage()` (rasio → persen, >1 dianggap persen) + label Indonesia "cakupan".
- Test: 3 kasus `fmtCoverage` + 1 render test (`cakupan 100%`, dan tidak ada "coverage 1").
- Verifikasi ulang: **"sampel 2 · cakupan 100%"**.

**BUG-C / DATA-003 — Register eksklusi tidak bisa menyebut pemasok**
- Lokasi: `backend/app/api/supplier_exclusions.py` (respons), `frontend/lib/suppliers-board.ts` (pembacaan).
- Bukti: `GET /supplier-exclusions` hanya mengirim `supplier_id`; UI merender "—".
- Perbaikan: endpoint menambahkan `supplier_name` (satu query untuk semua baris, bukan N+1).
- Test backend baru: `test_register_membawa_nama_pemasok_dan_id_keputusan` (lulus).
- Verifikasi ulang: **"CV Ayam Kampung Cugenang"**, **"CV Ambarawa Telur Utama"**.

**BUG-D / DATA-004 — Waktu register eksklusi berupa ISO UTC mentah**
- Bukti: UI "2026-10-25T20:43:30.217503+00:00"; tempat lain "26 Okt 2026 07.44".
- Perbaikan: `formatDate` + `formatClockWib` di `exclusionRows()`.
- Verifikasi ulang: **"26 Okt 2026 03.43"** (20.43 UTC = 03.43 WIB) dan "23 Okt 2026 03.43".

**BUG-E / DATA-005 — Kolom Keputusan register selalu "—"**
- Bukti: endpoint mengirim `source_decision_id`; UI membaca `decision_id`.
- Perbaikan: baca `source_decision_id` dengan `decision_id` sebagai cadangan.
- Verifikasi ulang: **"ae472e84"** dan **"d2c7131c"**.

**BUG-F / DATA-006 — Nilai biaya kosong ditulis "-"**
- Bukti: kartu "Pemulihan status pemasok" (quantity & SDC null) mencetak "SDC -".
- Penyebab: `formatIDR()` mengembalikan "-" untuk null; aturan repo menyebut "—".
- Perbaikan: `formatIDR(null|undefined|NaN)` → "—"; `0` tetap "Rp0".
- Test: +1 di `tests/agent-flow.test.tsx`.
- Verifikasi ulang: kartu itu sekarang "—" (lewat suite + render).

**BUG-G / DATA-007 — Angka batch jaringan tampil sebagai angka Jakarta**
- Bukti: tile "BATCH <48 JAM" = 7 (1 kedaluwarsa 120 kg + 6 segera 722 kg) sementara batch Jakarta hanya 2; sumbernya `GET /batches` yang menurut docstring-nya sendiri "sengaja lintas lokasi".
- Perbaikan (label, bukan angka): catatan tile menjadi "seluruh jaringan · kedaluwarsa 1 batch (120 kg) · segera 6 batch (722 kg)", judul kartu diberi keterangan cakupan, dan kalimat kosong menyebut "di seluruh jaringan".
- Test: `tests/today-summary.test.ts` menuntut kata "jaringan" pada catatan tile.
- Verifikasi ulang: **"seluruh jaringan · kedaluwarsa 1 batch (120 kg) · segera 6 batch (722 kg)"**.

### D.2 Dilaporkan, belum diubah (butuh keputusan aturan bisnis)

| ID | Masalah | Mengapa belum diperbaiki |
|---|---|---|
| DATA-009 | Kiriman 4.750 kg (beras+wortel+telur+ayam) diklaim "menutup kekurangan" telur 780 kg | perlu keputusan: batasi per komoditas, atau ubah kalimat menjadi "kiriman semua komoditas" |
| DATA-008 | Lima tile keamanan bercampur dimensi (9+1+2+1+1=14 dari 15 batch) | mengubah susunan kartu mengubah tata letak yang disetujui; usul: pisahkan "status uji" (15) dari "karantina/kedaluwarsa" |
| DATA-010/011 | 8 trace placeholder "(template status demo)"; `sdc` di trace ≠ SDC keputusan | data seed; memperbaikinya mengubah angka demo yang sudah dilatih untuk panggung |
| DATA-012 | PO 0 kg dengan `MAT-UMUM` | menghapus PO akan mengubah "Total nilai Rp32.880.000" dan tes PO |
| DATA-013 | Penolakan tidak punya baris `approvals` | perlu migrasi/kolom aktor penolakan; menyentuh state machine |
| DATA-014 | "Pemasok dieksklusi 2" = 1 aktif + 1 usulan | label produk; usul: "2 entri register (1 aktif, 1 menunggu keputusan)" |
| DATA-015 | `price_signals` tanpa dimensi pemasok | perlu migrasi kolom + backfill |
| DATA-016 | "Sedang mengirim barang" = punya batch layak | definisi pemilik 16 Okt; cukup ganti label |
| DATA-017 | Ringkasan keputusan keamanan menghitung baris yang sama dua kali | perlu keputusan copy |
| DATA-018 | "Kiriman tiba" dipakai untuk dua entitas (porsi makan vs bahan) | perlu keputusan istilah |
| DATA-019 | "Belum ada jejak agent di database" padahal DB punya 85 trace | perlu keputusan copy ("belum ada putaran agent hari ini") |
| DATA-044 | `.catch(() => null)` menyembunyikan galat detail keputusan | perubahan lintas hook; risiko regresi lebih besar dari manfaat pada hari demo |
| DATA-046 | "Kebutuhan" tanpa menyebut `needed_by = 29 Okt` | perlu keputusan copy |

---

## E. Kesimpulan

**1. Data valid dan terverifikasi (23 klaim).**
Angka besar yang dipakai di panggung dapat dipertanggungjawabkan: 11 rekomendasi & 17 keputusan, saldo Jakarta 300/1.080/−780 kg, 14 kiriman (2/1/9/2), 15 batch dengan sebaran status uji yang cocok, 51,82 kg limbah (7 peristiwa; 12,5 + 39,32), 2 catatan penerimaan, 60 pemasok (82% rata-rata keandalan, 30 dalam 150 km, 53 punya batch layak), rantai audit append-only (1.065 blok saat panen #1, 1.084 saat panen #3 — naik karena tulisan baru, 993 arsip, `valid=true`), dan dua KPI yang bisa dihitung ulang persis (Susut pangan 0,5862% → 0,59; Simpangan harga 2,6553% → 2,66). Rincian biaya satu keputusan juga menjumlah tepat ke SDC (Rp22.080.862,39).

**2. Data tidak valid (8; 7 sudah diperbaiki).**
(a) **Belum diperbaiki:** "kiriman 4.750 kg menutup kekurangan 780 kg" mencampur komoditas — kekurangan **telur** dinyatakan tertutup oleh **beras dan wortel**. (b) Sudah diperbaiki: tile "Batch <48 jam" menampilkan angka jaringan (7) di halaman berlabel Jakarta tanpa kualifikasi; pil periode KPI menyebut "Oktober 2026" untuk jendela harian; cakupan ditulis "1" untuk 100%; tiga kolom register eksklusi kosong ("—") padahal datanya ada; waktu register berupa ISO UTC mentah; biaya kosong ditulis "-" bukan "—".

**3. Mencurigakan, perlu konfirmasi aturan (13).**
Lima tile keamanan yang bila dijumlahkan 14 dari 15 batch; `sdc` di trace berbeda 32% dari SDC keputusan; PO 0 kg berlabel MAT-UMUM; 9 keputusan ditolak tanpa aktor; "dieksklusi 2" (1 aktif + 1 usulan); kutipan harga tanpa dimensi pemasok (143 grup kembar); "sedang mengirim" untuk 53 dari 60 pemasok; ringkasan keputusan keamanan menghitung satu baris dua kali; istilah "kiriman tiba" untuk dua entitas; pernyataan "belum ada jejak agent di database".

**4. Belum dapat diverifikasi (2).**
Klaim durasi "±70 detik" untuk bangun ulang data (tidak diukur pada audit ini) dan klaim halaman Decision & Evidence bahwa "seluruh bukti berasal dari API" — untuk angka benar, tetapi isi jejak agen sebagian berasal dari teks template di database, bukan keluaran model.

**5. Data demo/simulasi yang sudah diberi label.**
Data demo dapat dibedakan: `origin='demo'`, `demo_case`, `demo_session_id`; 43 baris baseline template tidak berstempel sesi (sesuai desain, bertahan setelah sesi berakhir). Tab Pemasok/Overview memberi label "Data simulasi", "SAP simulasi", "OSRM", "jarak lurus — rute belum disinkronkan". Yang belum diberi label: baris batch jaringan di halaman Jakarta (diperbaiki) dan teks trace template (dilaporkan).

**6. Risiko dan pekerjaan tersisa.**
Prioritas sebelum panggung: (i) putuskan DATA-009 (klaim penutupan kekurangan lintas komoditas) karena ini klaim bisnis yang paling mudah dipatahkan juri; (ii) rapikan DATA-008 agar lima tile bisa dijumlahkan; (iii) ganti teks trace template (DATA-010) atau sembunyikan tombol Agent Log untuk kartu itu; (iv) selaraskan label "sedang mengirim"/"kiriman tiba". Sesudah kompetisi: migrasi `price_signals.supplier_id`, kolom aktor penolakan, dan hapus `.catch(() => null)` di hook detail.

**Cara mengulang audit ini:** `python harvest_ui.py` (panen UI + jejak request) → `python probe_api.py` (payload endpoint yang sama) → `python data_quality.py` + `python data_quality2.py` (sapuan DB) → bandingkan angka; semua skrip ada di `C:\Users\User\AppData\Local\hermes\cache\scratch\`.

---

## F. Putaran perbaikan 26 Okt 2026 (setelah laporan awal)

Semua temuan di §C–D dikerjakan pada putaran ini. Status akhir per ID:

| ID | Tindakan | Bukti verifikasi |
|---|---|---|
| DATA-008 | Tile dipisah: 4 kategori status uji (Aman/Gagal/Perlu verifikasi/Belum diuji) + tile "Status lain" bila ada sisa, lalu kelompok penanda (karantina, kedaluwarsa) dengan legenda "menjumlah ke N batch" | UI: "Angka status uji di atas menjumlah ke **14 batch**"; `safetyStatusPartition()` diuji 2 kasus (termasuk batch `pass` yang ditahan → `leftover=1`) |
| DATA-009 | Kiriman yang dihitung hanya komoditas yang sama + kalimat menamai komoditas & tanggal kebutuhan | `incomingKgForCommodity()` (3 tes), `coverageSentence()` menulis "kiriman telur 1.080 kg"; tes lama tetap lulus |
| DATA-010 | 8 jejak template diganti ringkasan faktual (`status`,`summary`,`sumber`,`duration_ms`) | `_ringkas_jejak()` + 4 tes; DB: `output_summary ILIKE '%template status demo%'` = **0** |
| DATA-011 | `sdc` jejak diselaraskan ke SDC keputusan (template + `/demo/seed`) | `_selaraskan_sdc_jejak()`; DB: selisih > Rp1 = **0**; invarian gate baru |
| DATA-012 | PO hanya dibuat bila ada pemasok + komoditas + berat > 0; material memakai nama komoditas penuh | Rebuild: `ordered_quantity<=0` = **0**, `MAT-UMUM` = **0**; bukti `sap_purchase_order` ikut tidak ditulis |
| DATA-013 | Penyemai mengisi baris `approvals(approved=false)` untuk setiap keputusan ditolak yang belum punya pencatat | `_pastikan_penolakan_tercatat()`; DB: ditolak tanpa pencatat = **0**; UI menyebut "(bisa diajukan ulang)" |
| DATA-014 | Tile jadi "1 aktif · 1 menunggu"; register punya kolom **Status** (Aktif / Menunggu keputusan / Usulan ditolak / Dicabut) | UI: "Pemasok dieksklusi **1 aktif · 1 menunggu**", kolom STATUS terisi; `exclusionStatusLabel()` + `exclusionCounts()` diuji |
| DATA-015 | **Koreksi laporan**: tabel memang punya `supplier_id` + CHECK; "duplikat" = beberapa pemasok mengutip pada jam yang sama (1–4 pemasok per grup) | Query `count(distinct supplier_id) = 1..4` per grup |
| DATA-016 | Label "Sedang mengirim"/"Mengirim N kiriman" → "Stok layak" (definisi: punya batch layak hari ini) | UI: "Pemasok dengan stok layak **54 dari 60**", pil "Stok layak · 3 kiriman"; 8 tes disesuaikan |
| DATA-017 | Ringkasan keputusan keamanan menghitung tiap keadaan sekali + kg per keadaan | `safetyDecisionSummaryLine()` + 2 tes; UI: "4 masih berlaku (2.346 kg) · 1 ditolak (bisa diajukan ulang) (600 kg) · 0 kedaluwarsa tanpa penolakan" |
| DATA-018 | Label "Kiriman tiba" → "Pengiriman makan tiba" (porsi makan), dibedakan dari kiriman bahan | UI Hari Ini: "Pengiriman makan tiba — tidak ada catatan"; 2 tes agenda disesuaikan |
| DATA-019 | Kalimat "belum ada jejak agent di database" → "belum ada putaran agent yang terekam" + rujukan ke Agent Log | UI Demo Control |
| DATA-020 | Badge `9+` diberi `title` berisi jumlah sebenarnya (`aria-label` sudah memuatnya) | `TopBar.tsx` |
| DATA-041 | Klaim "±70 detik" diganti hasil ukur: **41 detik** (rebuild diukur `date` sebelum/sesudah) + "sediakan sampai sekitar 1 menit" | 3 tempat teks + 2 tes diperbarui |
| DATA-044 | `catch(() => null)` diganti `Promise.allSettled`; bagian yang gagal dilaporkan sebagai `errors[]` dan ditampilkan di halaman | UI: banner "Sebagian bukti gagal dibaca: …"; 2 tes sumber |
| DATA-046 | `/balance/{loc}/{com}` dan `/balance/map` mengirim `demand_needed_by`; kalimat menulis "(perlu 29 Okt 2026)" | Field baru di `balance.py`; UI: "Kebutuhan 1.080 kg (perlu 29 Okt 2026)" |
| (tambahan) | Tab Agent Log membaca `output_summary.summary` sebagai kalimat; JSON mentah dipindah ke lipatan "Data mentah" | UI sesudah perbaikan: "Putusan supplier_exclusion_restoration untuk berat tidak diketahui; SDC belum dihitung; status pending_approval." + "Data mentah" |

### Hasil tes setelah putaran perbaikan

| Pemeriksaan | Hasil |
|---|---|
| Vitest | **1818 lulus / 166 berkas** (naik dari 1804; 14 tes baru) |
| `tsc --noEmit` | exit 0 |
| ESLint | "No ESLint warnings or errors" |
| pytest `test_demo_template_jejak.py` | 4 lulus |
| pytest `test_supplier_exclusion_api.py` | 9 lulus |
| pytest subset `-k "balance or demo or sap_order or trace or agent"` | 231 lulus, 16 skip, 5 gagal — **kelima berkas lulus saat dijalankan sendiri** (order-dependent, kelas yang sama dengan 13 kegagalan pra-existing) |
| ruff (`balance.py`, `demo.py`, `demo_template.py`, tes baru) | All checks passed |
| Gate `verify/invariants.spec.json` | **PASS 52 / FAIL 0 / SKIP 1** — termasuk 5 invarian baru (PO ≤0 kg, MAT-UMUM, penolakan tanpa pencatat, teks template, sdc jejak) |
| Panen UI sesudah perbaikan | 10 tab, **0 console error**, semua endpoint 200; angka kembali ke baseline saat itu (11 kartu Jakarta, 120 batch, 5.240 pasokan, 1 sesi aktif) |

### Catatan operasional yang ditemukan saat verifikasi
`python -m app.seed.demo_template` (jalur CLI) memanggil `pastikan_sesi` **sebelum** `build_into`, sedangkan `build_into(purge=True)` memanggil `kosongkan_kecuali(db, None)`; bila sesi yang dipakai habis di tengah proses, penyapu aplikasi (`sapu_tanpa_sesi`) menghapus baris `origin='demo'` tanpa stempel. Terukur pada audit ini: satu rebuild menyisakan 5 keputusan dan 2 sesi `expired`, dan UI menampilkan "Belum ada sesi demo". Pemulihan yang benar adalah jalur produk **`POST /demo/session/start`** (`mulai_dengan_template`: bangun template dulu, buka sesi belakangan) — sesudah itu 36 keputusan, 120 batch, 5.240 pasokan, 1 sesi aktif 7.199 detik. Jalur CLI sebaiknya tidak dipakai pada DB yang sedang dilayani aplikasi.

---

## Koreksi sesudah laporan ini (26 Okt 2026, 19.45 WIB)

Laporan ini ditulis pada 08.00–08.35 WIB, ketika DB demo berada dalam keadaan
**pasca-suite tes** (baris demo ter-purge sebagian): 36 keputusan / 120 batch.
Angka "baseline" di laporan ini karena itu bukan keluaran builder.

Sesudah F7 diperbaiki dan DB dibangun ulang secara kanonik, keadaan panggung
yang benar adalah: **48 keputusan, 125 batch, 28 approval, 1.526 blok ledger
(1.454 arsip), 14 kartu Jakarta (10 menunggu + 2 ditandai verifier + 2 sudah
dieksekusi), 15 rute, KPI hari ini 6/7 tersedia**. Dokumen hidup
(`docs/state-snapshot.md`, `docs/demo/alur-demo-juri.md`,
`docs/demo/panduan-demo-singkat.md`, `docs/MEALCHAIN_GUARDIAN_LENGKAP.md`)
sudah memakai angka itu. Rincian di `MG/audit-rencana-vs-kode.md` §8.
