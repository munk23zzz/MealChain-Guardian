# RINGKASAN AUDIT MASTER — MealChain Guardian

| Field | Nilai |
|---|---|
| Tanggal | 26 Oktober 2026 (WIB) |
| Repo | `mealchain-guardian`, branch `feature/db-modes-demo-coverage`, HEAD `5885810` |
| Lingkup | 7 dokumen audit: database, logika bisnis, numerik/KPI, konsistensi UI↔API, alur agen, keamanan & dependensi, hasil tes |
| Database | `mealchain` (PostgreSQL, container `mealchain-postgres`), backend `mealchain-backend` `:8000` (`healthy`), `DEMO_SESSION_ENFORCE=true` |
| Status dokumen | Ringkasan eksekutif atas 7 audit + catatan perbaikan 4 defek hari ini |
| Artefak ukur | `verify/audit-db/` (audit DB), `verify/verify-out-invariants/` (gate), backup pra-perbaikan `sebelum-fix-20261026-2201.sql.gz` (scratch, di luar repo) |

> Dokumen ini tidak memuat kredensial. Semua angka "sesudah" diambil dari satu
> rebuild deterministik (`mulai_dengan_template`) pada 26 Okt 2026 22:1x WIB dan
> query `SELECT` sesudahnya.

---

## 1. Kondisi awal (sebelum perbaikan hari ini)

| Aspek | Terukur | Sumber |
|---|---|---|
| Skema | 24 tabel, 52 FK, 42 CHECK, 112 indeks, 0 drift (`alembic check` bersih), head `033_indeks_fk_hilang` | `DATABASE_INTEGRITY_AUDIT.md` §2–§5 |
| Integritas data | 134 cek mandiri: 132 PASS, **2 FAIL** (SDC≠Σ komponen, 12 blok ledger yatim) | idem §4 |
| Gate invarian | PASS 52 / FAIL 0 / SKIP 1 — tetapi **buta** terhadap 4 dari 5 cacat yang ditemukan audit | idem §6–§7 |
| Numerik/KPI | 7 KPI: rumus konsisten kode↔SQL, tetapi `Safe Delivered Cost` & `Decision Time` **mustahil `available`** karena 12/12 PO tanpa `decision_id` | `NUMERICAL_AND_KPI_AUDIT.md` §7 |
| Logika bisnis | 4 temuan P2 (termasuk rincian biaya tidak menjumlah), 5 P3 | `BUSINESS_LOGIC_AUDIT.md` §1 |
| Alur agen | 2 P2, 6 P3 — jejak `sdc` diselaraskan penyemai, `PREDICT` tidak dipakai `DECIDE` | `AGENT_WORKFLOW_AUDIT.md` §7 |
| UI↔API | 6 pasangan diukur, 3 selisih berpenyebab jelas (1 karena PO tanpa keputusan) | `UI_API_CONSISTENCY.md` §2–§3 |
| Keamanan | 2 **High** advisory dependensi produksi (`maplibre-gl`, `next`), 2 Medium, 3 Low | `SECURITY_AND_DEPENDENCY_AUDIT.md` §8 |
| Tes | 13 tes backend gagal pada klon DB (semua bertema keadaan data demo), 27 skip | `TEST_RESULTS.md` §4, §7 |

**Kesimpulan kondisi awal.** Tidak ada temuan **P0**. Yang ada adalah kelas cacat
"angka dan jejak audit tidak dapat dipertanggungjawabkan": rincian biaya yang
tidak menjumlah, rantai keputusan→PO yang tidak terbukti, blok ledger yang
menunjuk entitas hantu, dan provenance data demo yang dihapus proses pembekuan.

---

## 2. Cakupan 7 dokumen audit

| # | Dokumen | Yang diperiksa | Bukti utama |
|---|---|---|---|
| 1 | `DATABASE_INTEGRITY_AUDIT.md` | Katalog skema, FK/CHECK/indeks, drift, migrasi dari nol, 134 cek integritas, kecukupan invarian | `pg_catalog`, `run_checks.py`, hitung ulang hash chain di luar aplikasi |
| 2 | `BUSINESS_LOGIC_AUDIT.md` | State machine keputusan, empat mata, gerbang keselamatan, eligibility pemasok, rekonsiliasi SDC | kode + DB klon sekali pakai (`audit_logic`) |
| 3 | `NUMERICAL_AND_KPI_AUDIT.md` | 7 KPI: rumus kode vs SQL independen, 3 periode × 2 scope, batas tanggal/zona waktu | API + SQL paralel |
| 4 | `UI_API_CONSISTENCY.md` | 6 pasangan angka UI↔API↔DB | payload API + query DB |
| 5 | `AGENT_WORKFLOW_AUDIT.md` | Pipeline `DETECT…LEARN`: siapa menghitung apa, deterministik vs template, verdict `UNAVAILABLE` | jejak `agent_traces` + probe Event 1 nyata |
| 6 | `SECURITY_AND_DEPENDENCY_AUDIT.md` | `npm audit`, kebocoran kredensial, auth/otorisasi, CORS/header, dependensi Python | audit registry + probe 401/403 |
| 7 | `TEST_RESULTS.md` | Hasil suite backend pada klon DB, isolasi DB, penyebab 13 kegagalan | pytest pada `audit_test` |

---

## 3. Temuan per severity (AUDIT-ID)

### P0 — tidak ada

Tidak ada jalur yang mengeksekusi/menerbitkan PO tanpa approval + verifikasi, dan
tidak ada kegagalan integritas referensial pada data saat ini.

### P1 — tidak ada yang terbuka pada data hari ini, satu laten

| ID | Temuan | Status |
|---|---|---|
| BL-03 | Gerbang batch menganggap "log suhu lengkap" = "aman" (log 33 °C 60 menit lolos) | **Terbuka (laten)** — menjadi P1 begitu ada endpoint penambah log suhu |

### P2 — cacat nyata

| ID | Temuan | Status hari ini |
|---|---|---|
| **D-01 / BL-01 / NUM-01(a)** | `cost_breakdown` disalin utuh saat kuantitas & SDC diskalakan 0,7 → Σ komponen ≠ SDC pada 4 keputusan (selisih Rp 4.724.709,71 dan Rp 6.624.258,72) | **DIPERBAIKI** (§4.1) |
| **D-02** | 12 blok `ledger_blocks` generasi aktif menunjuk 4 keputusan yang sudah dihapus | **DIPERBAIKI** (§4.3) |
| **D-04** | `_bekukan()` menulis `origin='seed'` → 26 keputusan `demo_case` kehilangan provenance, cek kanonik lulus vakum | **DIPERBAIKI** (§4.4) |
| **D-05 / NUM-01** | 12/12 PO impor SAP tanpa `decision_id` → rantai keputusan→PO tidak terbukti, cek ">1 PO per keputusan" vakum | **SEBAGIAN** (§4.2): rantai kini punya 4 tautan sah + 3 invarian gate baru; 12 baris impor **tetap NULL** dan dibuktikan tidak punya pemicu |
| D-03 | Sifat *append-only* ledger tidak ditegakkan database (0 trigger, role aplikasi superuser + pemilik tabel) | Terbuka |
| NUM-01 (sisa) | Alasan `no_data` Safe Delivered Cost menyebut "tidak ada batch terkirim yang punya biaya", bukan sebab sebenarnya (tautan/PO) | Terbuka |
| NUM-02 | `Decision Time` hanya menghitung ACT yang punya PO tertaut; sampel hilang bila tak ada eksekusi | Terbuka (sebagian membaik: 2 sampel pada 7d/1bulan) |
| NUM-03 | `start/end` eksplisit berakhir di masa depan → KPI menghitung fakta yang belum terjadi | Terbuka |
| NUM-04 | Meal Continuity `today` = 0,00 % setelah 21.00 WIB | Terbuka |
| BL-02 | `executed` tidak berarti barang berangkat (semua batch ditahan) | Terbuka (perilaku sadar, label menyesatkan) |
| BL-04 | `quarantine_status='failed'` tetap menghasilkan kandidat → approve lalu 409 saat execute | Terbuka |
| AG-01 | Kecocokan `sdc` jejak ↔ keputusan dipaksakan `_selaraskan_sdc_jejak`; jejak bukan bukti komputasi independen | Terbuka |
| AG-02 | `PREDICT` tidak dipakai `DECIDE` (7.333,96 kg vs 685 kg) | Terbuka (dokumentasi) |
| SEC-01 | `maplibre-gl@4.7.1` XSS sanitizer bypass (CVSS 10) | Terbuka |
| SEC-02 | `next@14.2.14` DoS Server Actions + jalur `postcss` | Terbuka |
| SEC-03 | Literal sandi demo di 3 direktori build lama (tidak dilayani server, bocor bila diterbitkan) | Terbuka |
| SEC-04 | 6 advisory rantai alat pengembangan (vitest/vite/esbuild/…) | Terbuka |
| TST-01 | 13 tes backend gagal pada klon DB (keadaan data demo) | Terbuka |

### P3 / Low / Info

| ID | Ringkas | Status |
|---|---|---|
| D-06 | Indeks duplikat `suppliers.location_id` | Terbuka |
| D-07 | 1 akun uji `@test.local` di DB demo | Terbuka |
| D-08 | `invariants.spec.json` belum mencakup 8 aturan (rekonsiliasi SDC, cakupan ledger, empat mata, stamping demo, koordinat pemasok, kosakata `delivery_events`) | **SEBAGIAN DIPERBAIKI**: 7 cek baru (SDC, ledger yatim, provenance demo ×2, PO ×3) — 59 PASS; empat mata/koordinat/kosakata belum |
| D-09, D-11 | 28 indeks `idx_scan=0`; 10 database residu uji | Terbuka (kebersihan) |
| D-10 | 17 ekspresi CHECK berbeda teks demo vs DB baru | UNVERIFIED |
| NUM-05…NUM-13 | `coverage` "1.00" pada `no_data`; dedupe lineage; durasi negatif; cap `LEAST`; baris masa depan; evidence completeness; offset periode | Terbuka (mayoritas P3) |
| BL-05…BL-09 | Pesan `execute` generik; verdict `flagged` vs status; dokumen state machine salah; 1 approval untuk keputusan administratif; batch `dispatched` tak muncul di `dikirim`/`ditahan` | Terbuka |
| AG-03…AG-08 | `flagged` tanpa status; narasi SUPERVISE bertentangan; 10 jejak tanpa angka; `agent_traces` bukan append-only; `LEARN` bukan pembelajaran model; tak ada keputusan melewati 7 tahap | Terbuka |
| DIFF-01…DIFF-05 | SPPG melihat 0 PO (seed tanpa keputusan); batch lintas lokasi; paginasi 10 vs "60 pemasok"; teks penyebut Evidence; snapshot bergerak | **DIFF-01 membaik**: SPPG Head Jakarta kini melihat 2 PO (dari eksekusi); sisanya tetap |
| SEC-05…SEC-09 | monitor bisa menulis admin; kunci TLS di root repo; tak ada `pip-audit`; rate-limit login NOT TESTED | Terbuka / Accepted |
| TST-02…TST-06 | 27 skip; suite demo tidak deterministik; ukur di klon; build produksi/axe/beban belum di gate | Terbuka / Accepted |

---

## 4. Yang diperbaiki hari ini

Semua perbaikan menyentuh **akar masalah di builder/penyemai**, bukan gejalanya.
Definisi bisnis KPI tidak diubah, safety gate tidak dilonggarkan, dan tidak ada
assertion yang dimatikan.

### 4.1 D-01 — SDC tidak sama dengan Σ komponen `cost_breakdown`

- **Akar:** `_perkaya_kasus_jakarta` menskalakan kuantitas & SDC 70 % lalu menyalin
  `cost_breakdown` apa adanya, sehingga rincian tetap dibangun untuk 600/780 kg.
- **Perbaikan:** helper murni `skalakan_breakdown(breakdown, rasio, sdc_target)`
  (`app/seed/demo_template.py`): setiap komponen biaya × rasio, turunan internal
  (`logistics`, `transport_linehaul`, `transport_supplier_leg`) ikut diskalakan,
  kunci non-biaya (jarak, `basis`) tidak disentuh, breakdown naratif dikembalikan
  apa adanya, dan **sisa pembulatan diserap komponen terbesar** sehingga
  Σ komponen == SDC persis.
- **Bukti sesudah:** `SELECT … abs(SDC − Σ komponen) > 0.01` → **0 baris** (sebelum: 4).
  Empat kartu yang dulu salah kini `selisih = 0.00` (Rp 11.024.322,67 dan
  Rp 15.456.603,67).
- **Tes:** `tests/test_demo_template_breakdown.py` (7 tes) — termasuk kasus
  pembulatan yang tanpa penyerapan sisa akan meleset Rp 0,01–0,02.

### 4.2 D-05 / NUM-01 — PO tanpa `decision_id`

- **Akar:** 12 PO impor SAP (`4500000xxx`) masuk dari `load_seed` tanpa keputusan;
  KPI `Safe Delivered Cost` hanya menghitung PO yang tertaut (`kpi_service.py:349`).
- **Perbaikan:** langkah build `_tautkan_po_ke_keputusan` +
  helper murni `komoditas_material` / `pilih_keputusan_pemicu`
  (`app/seed/demo_template.py`). Tautan hanya diisi bila ada **tepat satu**
  keputusan `executed` dengan pemasok + komoditas + kuantitas yang sama; kandidat
  nol atau lebih dari satu → dibiarkan NULL dan dilaporkan
  (`laporan["po_tautan"]`). `_semai_bukti_dan_rantai` kini melewati pembuatan PO
  bila keputusan sudah punya PO (mencegah ">1 PO per keputusan").
- **Bukti sesudah:** `po_tautan = {ditautkan: 0, tanpa_kandidat: 12, ambigu: 0}`.
  Query pembanding (pemasok + komoditas + kuantitas + status `executed`) untuk
  ke-12 PO impor → **0 kandidat**: mengisi `decision_id` di sana berarti
  mengarang relasi, dan itu tidak dilakukan.
- **Yang tetap terbuka:** 12 PO impor **tetap** `decision_id NULL`. Baris impor
  SAP memang tidak lahir dari keputusan (lihat `api/sap_orders.py` §3–§4 dan
  `tests/test_sap_orders_api.py:303`), jadi target "0 PO tanpa keputusan" tidak
  dapat dicapai tanpa menghapus data impor atau mengarang 12 keputusan.
- **Kompensasi yang menutup kekosongan gate:** 3 invarian baru — "PO
  ber-`decision_id` ≥ 1" (rantai tidak vakum; kini **4**), "PO menunjuk keputusan
  yang tidak ada = 0", "PO tanpa `decision_id` yang bukan baris impor SAP = 0".
- **Dampak nyata:** SPPG Head Jakarta kini melihat **2 PO** di `/sap/purchase-orders`
  (sebelum: 0 — DIFF-01), karena PO hasil eksekusi tertaut ke keputusan bertarget
  Jakarta.

### 4.3 D-02 — blok ledger yatim

- **Akar:** `_seed_demo_cases(force=True)` menghapus keputusan yang sudah punya
  blok, tanpa menaikkan generasi. `ledger_blocks` tidak punya FK ke `decisions`,
  jadi penghapusan tidak meninggalkan jejak dan blok tetap dihitung generasi aktif.
- **Perbaikan (dua lapis):**
  1. `ledger_service.bump_bila_berblok(db, entity_ids)` dipanggil setiap kali
     `_seed_demo_cases(force=True)` menghapus keputusan — generasi naik hanya bila
     blok generasi aktif benar-benar menunjuk baris yang dihapus;
  2. `_rapikan_cakupan_ledger` di akhir `build_into` (jaring terakhir, di dalam
     transaksi build): ukur blok yatim, naikkan generasi bila perlu, lalu lengkapi
     blok untuk keputusan hidup lewat `_tulis_blok_keputusan` (idempoten per
     generasi). **Tidak ada blok sah yang dihapus** — rantai hash tetap utuh,
     blok lama menjadi `archived_blocks`.
- **Bukti sesudah:** `GET /ledger/verify` →
  `valid: true, blocks: 2.034, generation: 247, entity_blocks: 74,
  linked_blocks: 74, orphan_blocks: 0, archived_blocks: 1.960,
  linked_ratio: 1.0, coverage_warning: null` (sebelum: `orphan_blocks: 12`
  pada snapshot audit; 22 saat direproduksi dengan `force=True`).
- **Tes:** `tests/test_demo_template_provenance_ledger.py::
  test_hapus_kasus_demo_menaikkan_generasi_ledger` (generasi naik **dan**
  `orphan_blocks = 0`).

### 4.4 D-04 — provenance `origin='demo'` hilang

- **Akar:** `_bekukan()` menulis `origin='seed'` untuk semua baris berstempel,
  sehingga 26 keputusan `demo_case` menjadi "kanonik" dan cek
  `origin='demo'` tidak menemukan apa pun (lulus vakum).
- **Perbaikan:** `_bekukan()` **berhenti menyentuh `origin`**. Penanda beku
  sekarang adalah stempel ke sesi sentinel `cetakan`
  (`demo_session.CETAKAN_ID`, `status='expired'`, `template_version='cetakan'`)
  yang tidak pernah aktif, tidak muncul di `/demo/session`, dan dikecualikan
  `kosongkan_bertanda`. Jadi template tetap selamat dari "Akhiri sesi" **dan**
  provenance-nya jujur.
- **Bukti sesudah:** keputusan `origin='demo'` = **30** (sebelum: 0);
  `demo_case` ber-`origin='seed'` = **0** (sebelum: 26); total baris
  `origin='demo'` seluruh tabel = **12.950**; keputusan kanonik berstempel = **0**.
  Uji fungsional: `akhiri()` dijalankan → 36 keputusan & 120 batch **tetap ada**
  (template tidak ikut terhapus).
- **Tes:** `tests/test_demo_template_provenance_ledger.py` (2 tes) + cek kanonik
  baru di gate ("keputusan ber-origin demo ≥ 1", "demo_case ber-origin seed = 0").

### 4.5 Gate invarian diperluas (D-08 sebagian)

`verify/invariants.spec.json` +7 cek DB dan 1 asersi HTTP
(`/ledger/verify` harus `orphan_blocks: 0`):

| Cek baru | Hasil |
|---|---|
| SDC != jumlah komponen `cost_breakdown` | 0 |
| blok ledger generasi aktif menunjuk entitas terhapus | 0 |
| keputusan ber-origin demo (≥1) | 30 |
| keputusan `demo_case` ber-origin seed | 0 |
| PO ber-`decision_id` (≥1) | 4 |
| PO menunjuk keputusan yang tidak ada | 0 |
| PO tanpa `decision_id` yang bukan baris impor SAP | 0 |

---

## 5. Angka kanonik pasca-rebuild (26 Okt 2026, 22:1x WIB)

Perintah: `docker exec mealchain-backend python -c "…mulai_dengan_template(db, menit=120)…"`
(service in-process, tanpa app restart). Backup pra-perbaikan:
`sebelum-fix-20261026-2201.sql.gz` (scratch, di luar repo).

> Angka isi tabel (keputusan/batch/approval/bukti/jejak/PO/provenance) diukur
> sesaat setelah bangun-ulang yang sama. Baris ledger memakai snapshot kedua
> (22:2x WIB) karena DB demo dipakai bersama: satu bangun-ulang tambahan
> menaikkan generasi 245 → 247 dan menambah 74 blok, tanpa mengubah isi tabel
> lain dan tetap `orphan_blocks = 0`.

| Metrik | Sebelum perbaikan | Sesudah perbaikan | Target | Catatan |
|---|---|---|---|---|
| decisions | 36 | **36** | 48 | builder deterministik hari ini; angka 48 adalah baseline historis (`docs/verification/phase-01-baseline.md`) saat dataset lebih besar — DB audit sendiri mencatat drift 48 → 32 dalam satu jam |
| batches | 120 | **120** | 125 | idem (pemangkasan Jakarta 3/komoditas) |
| approvals | 21 | **21** | 28 | idem |
| decision_evidence | 51 | **51** | 61 | idem |
| agent_traces | 85 | **85** | 118 | idem |
| purchase_orders | 16 | **16** | 20 | idem |
| PO `decision_id` NULL | 12 | **12** | 0 | **tidak dicapai** — 0 kandidat pemicu (lihat §4.2) |
| PO `decision_id` terisi | 4 | **4** | — | rantai tidak vakum; SPPG Jakarta melihat 2 |
| ledger_blocks (total) | 1.886 | **2.034** | — | snapshot 22:2x WIB; +74 blok per bangun-ulang (satu set lengkap) |
| ledger generasi aktif | 72 (gen 243) | **74 (gen 247)** | — | `linked_ratio 1.0`; DB demo dipakai bersama, generasi naik tiap bangun-ulang |
| `/ledger/verify` orphan_blocks | 12 (audit) / 22 (reproduksi) | **0** | 0 | `coverage_warning: null` |
| decisions `origin='demo'` | 0 | **30** | >0 | provenance pulih |
| `demo_case` ber-`origin='seed'` | 26 | **0** | 0 | — |
| Σ komponen ≠ SDC (>Rp0,01) | 4 | **0** | 0 | selisih 0,00 pada 4 kartu |
| >1 PO per keputusan | 0 (vakum) | **0** (4 tautan) | 0 | cek kini tidak vakum |
| Keputusan kanonik berstempel sesi | 0 | **0** | 0 | — |

---

## 6. Status tes & gate

| Gerbang | Perintah | Hasil |
|---|---|---|
| Tes terkait (DB klon `fix_verif`, `DEMO_SESSION_ENFORCE=false`) | 30 berkas: `test_demo_template*`, `test_demo_extra*`, `test_demo_session*`, `test_demo_kasus_bukti`, `test_invarian_riwayat_demo`, `test_bukti_dan_draf_demo`, `test_akun_multi_kota`, `test_kpi*`, `test_ledger*`, `test_po_*`, `test_sap_orders_api`, `test_actions`, `test_scope_matrix` | **170 passed, 15 skipped, 0 failed** (98,84 s) |
| Tes fokus (sama, subset 12 berkas) | `test_demo_template_breakdown`, `test_demo_po_tautan`, `test_demo_template_provenance_ledger`, `test_ledger*`, `test_kpi*`, `test_po_*`, `test_sap_orders_api` | **68 passed, 0 failed** (31,74 s) |
| Gate invarian | `python …/verify_stack.py verify/invariants.spec.json` | **VERDICT: PASS (PASS 59 / FAIL 0 / SKIP 1)** — exit code **0** |
| Lint | `ruff check` pada 7 berkas yang disentuh | bersih |

SKIP pada gate adalah lapisan browser (`no ui section in spec`) — spec invarian
ini memang tidak memuat `ui`, jadi bukan kegagalan. Tes `test_demo_session.py`
yang destruktif tetap opt-in (`DEMO_SESSION_TESTS_ENFORCE=1`) seperti sebelumnya;
15 skip pada run di atas berasal dari mekanisme itu dan penjaga host-only.

**Kondisi "sebelum" untuk pembanding.** Keempat defek diukur pada kode sebelum
perbaikan: `Σ komponen ≠ SDC = 4`, `origin='demo' = 0`, `demo_case` ber-`origin='seed' = 26`,
`orphan_blocks = 12` (snapshot audit) / `22` (reproduksi `force=True`), `PO tanpa
keputusan = 12`. Tes baru (`test_demo_template_breakdown`, `test_demo_po_tautan`,
`test_demo_template_provenance_ledger`) tidak ada sebelum perbaikan dan gagal
pada implementasi lama (import simbol belum ada untuk yang pertama, asersi
`size`/`origin`/`orphan` gagal untuk dua sisanya).

---

## 7. Sisa temuan yang belum tertangani

1. **D-05 sisa:** 12 PO impor SAP tetap tanpa `decision_id`. Butuh keputusan
   owner: (a) biarkan + dokumentasikan (keadaan sekarang), (b) hapus baris impor
   (memecah `test_seed_load_db`/`test_sap_orders_api`), atau (c) buat 12
   keputusan rekonstruksi (menambah data demo & mengubah angka KPI).
2. **D-03:** *append-only* ledger belum ditegakkan DB (0 trigger, role aplikasi
   superuser + pemilik tabel). Ini prasyarat produksi, bukan demo.
3. **SEC-01/SEC-02 (High):** `maplibre-gl` dan `next` perlu upgrade mayor/patch
   beserta uji regresi peta & build.
4. **SEC-03:** artefak build lama memuat literal sandi demo → bangun ulang +
   rotasi sandi sebelum penerbitan apa pun.
5. **NUM-01 (pesan)/NUM-02/NUM-03/NUM-04:** alasan `no_data` masih menyesatkan,
   `Decision Time` hanya hidup setelah ada eksekusi, `end` masa depan belum
   dijepit, Meal Continuity `today` pecah setelah 21.00 WIB.
6. **BL-02/BL-03/BL-04:** label `executed` vs "barang berangkat", safety gate
   "log lengkap = aman" (laten P1), `quarantine_status='failed'` masih jadi
   kandidat.
7. **AG-01/AG-02:** jejak `sdc` masih diselaraskan penyemai; `PREDICT` tidak
   mempengaruhi `DECIDE`.
8. **D-06…D-11, NUM-05…NUM-13, BL-05…BL-09, AG-03…AG-08, DIFF-02…DIFF-05,
   SEC-04…SEC-09, TST-01…TST-06:** P3/Info — lihat tabel §3.
9. **Empat mata, koordinat pemasok unik, kosakata `delivery_events`:** belum
   masuk gate invarian (D-08 sisa).
10. **TST-01/TST-03:** 13 tes gagal pada klon DB & suite demo tidak deterministik
    terhadap keadaan DB — belum diselesaikan (di luar 4 defek hari ini).

---

## 8. Catatan kerja

- Perbaikan hari ini **tidak** mengubah definisi bisnis KPI, tidak melonggarkan
  safety gate, tidak mematikan assertion, tidak mengubah `.env`, tidak
  menginstal paket, tidak menghapus volume, tidak `DROP` database demo, dan
  tidak push ke remote.
- DB demo hanya ditulis lewat jalur resmi (`mulai_dengan_template` / `akhiri`).
  Tes berjalan pada klon `fix_verif` (pg_dump dari `mealchain`) yang **dihapus**
  setelah selesai.
- Working tree memuat perubahan berjalan dari pekerjaan lain
  (`backend/app/api/auth.py`, `backend/app/seed/demo_credentials.py`,
  `frontend/app/page.tsx`, berkas demo-accounts) yang **bukan** bagian audit ini
  dan tidak disentuh.
