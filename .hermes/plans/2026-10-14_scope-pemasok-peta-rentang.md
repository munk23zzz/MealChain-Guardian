# Rencana — Scope per-SPPG, Pemasok di Peta, dan Rentang Data s/d 5 Nov 2026

**Tanggal:** 14 Okt 2026
**Status (diperbarui 2026-10-15):** **Fase 0–8 SELESAI, termasuk §7.4b Fase 7d** (bukti:
`docs/verification/fase-6.md`, `docs/verification/fase-7.md`, `docs/verification/fase-7d.md`,
ruling `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`). Tidak ada fase yang tersisa di track ini.
Baris "RENCANA (belum ada kode yang diubah)" di bawah ini adalah keadaan saat plan
ditulis 2026-10-14 dan sudah tidak berlaku.
**Repositori:** `E:\hackathon\HackathonAWS\mealchain-guardian` (frontend di :3010, backend :8000, postgres :15432, mock-sap :8001)

---

## 1. Tujuan (versi pemilik)

1. **A.** Role `sppg_head` hanya melihat data **satu SPPG** (SPPG-nya sendiri).
2. **B.** Menambahkan **data pemasok** dan menampilkan para pemasok **di peta**.
3. **C.** Meng-**update DB sampai 5 November 2026** sehingga data banyak ("bakal banyak") dan bisa dipakai di **Demo Control**.

## 2. Fakta terverifikasi (dasar rencana — bukan asumsi)

Semua angka di bawah diambil dari repo/DB yang sedang jalan pada 14 Okt 2026.

### 2.1 Model & aturan yang sudah ada
| Fakta | Bukti |
|---|---|
| `users.location_id` WAJIB untuk `sppg_head`/`sppg_nutritionist`, WAJIB NULL untuk `bgn_monitor` | `backend/app/models/users.py:26-31` (CHECK constraint) |
| `GET /kpi` **sudah** scope-aware: SPPG hanya lokasinya (403 bila melenceng), `bgn_monitor` global | `backend/app/api/kpi.py:37-69` — **preseden yang harus dipakai ulang, bukan pola baru** |
| Tulis keputusan **sudah** dikunci ke lokasi sendiri | `_assert_target_location_allowed` (`api/decisions.py:36-62`) |
| Bacaan lintas lokasi **sengaja diizinkan** untuk approver | `_assert_decision_readable` (`api/decisions.py:65-88`) + "Ruling Owner 2026-10-08 (S4-05 p10)" → **bertentangan dengan permintaan A**, perlu keputusan |
| `GET /decisions` **tanpa filter scope apa pun** — semua peran melihat semua baris | `api/decisions.py:161-175` |
| `GET /balance/map` mengembalikan **semua** lokasi untuk semua peran | `api/balance.py:148-160` |
| Peta memakai **MapLibre GL**, penanda dibangun per lokasi (`createPin`/`refreshPin`/`syncMarkers`) | `frontend/components/SupplyMap.tsx:64-282` |

### 2.2 Data yang ada sekarang (inilah yang membuat rencana ini perlu hati-hati)
| Tabel | Jumlah | Rentang tanggal |
|---|---|---|
| `supply_records` | 30 | **hanya 2026-10-08** |
| `demand_records` | 312 | 2026-08-20 → 2026-10-08 (interval 7 hari, 7 observasi) |
| `price_signals` | 44 | **hanya 2026-10-08** |
| `batches` | 6 | 2026-09-10 → 2026-10-07 |
| `decisions` | 126 | 2026-10-06 → 2026-10-11 |
| `suppliers` | 14 | dibuat 2026-10-01 → 10-04 |
| `menu_plans` | 140 | 2026-09-24 → 2026-10-07 |

Hari ini **14 Okt** → seluruh snapshot sudah **±6 hari basi**.

- **SEMUA 126 keputusan menyasar Jakarta** (`select l.name, count(d.id) ... target_location_id` → Jakarta 126, sembilan lokasi lain 0). Konsekuensinya: **scope A hari ini tidak mengubah angka apa pun** (126 → 126). Ia baru berdampak begitu data multi-lokasi Fase 4 masuk — jadi A dan C saling mengunci: kalau C dikerjakan tanpa A, kepala SPPG Jakarta akan melihat keputusan Bandung/Surabaya dll.
- `locations` = 10 baris, `role_hint`: **`sppg` 8** (Jakarta, Bogor, Semarang, Yogyakarta, Surabaya, Malang, Palembang, Medan) dan **`supplier` 2** (Cianjur, Bandung). **Frontend sama sekali tidak membaca `role_hint`** (hanya `/admin/locations` yang mengembalikannya) → 2 hub pemasok itu tampil sebagai baris/pin setara SPPG di tabel, legenda, dan peta. Ini cacat label yang perlu dibetulkan bersamaan dengan B.
- `suppliers` = `{name, location_id, reliability_score, created_at}` — **tanpa koordinat**, tanpa komoditas, tanpa sertifikasi.
- **Tidak ada endpoint daftar pemasok** (`/openapi.json` tidak memuat `/suppliers`). Halaman Pemasok menyusun daftar dari **sampel keputusan** — workaround yang sudah didokumentasikan apa adanya di `frontend/lib/suppliers-board.ts:1-10`. Jadi B bukan sekadar "tambah data": perlu **endpoint baru** + keputusan tabel.
- Seeder bersifat **relatif waktu**: `build_seed_rows(reference_time)` dari `data/seed/sprint1_seed.json` (offset hari/jam) → menjalankan ulang pada hari demo otomatis "menyegarkan" snapshot.
- Migrasi dijalankan **manual**: `docker compose exec backend alembic upgrade head`. `CMD` backend hanya `uvicorn` (tidak auto-migrate). Head sekarang `011_supplier_exclusions`.
- Kanal seeding: `python -m app.seed.seed_data`, dan `POST /demo/seed` (4 kasus skrip, TTL di-guard ≥60 menit).

### 2.3 Jangkar angka yang bisa pecah bila data ditambah
Inventaris lengkap (berkas:baris) ada di **Lampiran A**. Ringkasnya:
- **15 berkas tes backend** menyebut angka snapshot kanonik; **5 di antaranya benar-benar akan gagal** bila baris data ditambah (bukan sekadar menyebut angkanya): `test_sprint1_contract_reconciliation.py` (jumlah SELURUH tabel), `test_supplier_city_coverage.py` (refs=30), `test_demo_users.py` (users=3), `test_api_supply_demand.py` (nilai record TERBARU Cianjur telur), `test_kpi_api.py` (jendela waktu terkunci).
- **5 berkas tes frontend** menyebut angka yang sama, tetapi semuanya memakai **fixture di dalam tes** (tidak memanggil API hidup) → tidak pecah oleh penambahan data, hanya pecah bila **bentuk payload** berubah.
- **Kode frontend tidak menyimpan angka jangkar sama sekali** (grep hanya menemukan `@media (min-width: 1080px)`) — Overview/tabel menghitung dari API. Artinya tampilan akan selalu mengikuti DB, sehingga menjaga konvergensi nilai kanonik penting demi cerita demo, bukan demi tes.
- Dokumen penyebut jangkar: `docs/verification/sprint-1.md:84` dan `docs/verification/sprint-0-2-cross-sprint-audit.md:105-107` (catatan verifikasi historis — biarkan sebagai sejarah, beri catatan bertanggal bila angkanya berubah). **`docs/design.md` tidak memuat angka-angka ini** (koreksi terhadap draf awal rencana ini).

### 2.4 Kondisi verifikasi sekarang (baseline)
99 berkas tes backend · 435 tes frontend lulus · `tsc` 0 error · `lint` bersih · 4 kontainer Up, `restarts=0`.

---

## 3. Keputusan yang perlu diambil pemilik (rekomendasi saya di kolom kanan)

| # | Pertanyaan | Rekomendasi |
|---|---|---|
| 1 | Aturan scope: `sppg_head` **dan** `sppg_nutritionist` hanya `target_location_id == user.location_id`, `bgn_monitor` global read-only? | **Ya.** Sekaligus **mengganti ruling 2026-10-08** "approver lintas lokasi": lokasi **tujuan** dikunci, lokasi **sumber** tetap lintas daerah (redistribusi Jakarta dari Cianjur tetap sah). Tulis ruling baru bertanggal. |
| 2 | Siapa yang menyetujui keputusan untuk lokasi lain (kalau `bgn_monitor` read-only)? | **Kepala SPPG masing-masing** menyetujui keputusan yang menyasar SPPG-nya. Jangan tambah role baru (kompleksitas tanpa nilai demo). |
| 3 | Bentuk data pemasok: koordinat di tabel `suppliers` (1 pemasok = 1 titik), atau tabel `supplier_sites` (multi-site)? | **Koordinat di `suppliers` dulu** (30–50 pemasok). Skema `supplier_sites` disiapkan sebagai jalur perpanjangan, tidak dibangun sekarang. |
| 4 | Arti "sampai 5 November": (a) riwayat nyata s/d hari ini **+ rencana** masa depan s/d 5 Nov, atau (b) baris "aktual" bertanggal masa depan s/d 5 Nov? | **(a).** Aktual masa depan = mengarang data; juri bisa menangkap. Masa depan yang wajar: `menu_plans.plan_date`, `demand.needed_by`, jadwal kirim, `decisions.expires_at`. Bila tetap ingin (b) di semua tabel, semua baris masa depan diberi `origin='demo'` + label "proyeksi" di UI. |
| 5 | Jangkar angka (4.900/3:7/Jakarta 300:1.080/Cianjur 1.400): dipertahankan atau diperbarui? | **Dipertahankan.** Generator Fase 4 dibuat **konvergen** ke nilai jangkar pada baris snapshot (record terakhir per lokasi×komoditas), sehingga 12 berkas tes + design.md §11 tetap benar. |
| 6 | Lokasi demo untuk kepala SPPG: hanya Jakarta, atau tambah user demo Bandung/Surabaya? | **Tambah 2 user demo** (Bandung, Surabaya) supaya scoping per-SPPG **terlihat** saat demo, bukan hanya di klaim. |
| 7 | Gambar garis rute pemasok→hub di peta? | **Opsional (Fase 3b)**, hanya kalau setelah Fase 3 peta masih terasa "kosong makna". Layer garis menambah risiko visual tanpa menambah nilai bukti. |
| 8 | Volume data target & bolehkah DB di-reset bersih? | Target: supply/prices **±2.000** baris, demand **±2.000**, batches **±200**, menu_plans **±660**, decisions **±300–500**. Reset bersih: **ya**, asal semua baris buatan generator bertanda `origin='demo'` sehingga bisa dihapus selektif. |

---

## 4. Rencana bertahap

Aturan kerja: satu fase = satu laporan terverifikasi (tes + tsc + lint + bukti DB/peramban), lalu berhenti menunggu keputusan pemilik. TDD untuk logika murni; migrasi selalu dua arah (upgrade + downgrade diuji).

### Fase 0 — Keputusan & inventaris jangkar (½ hari, tanpa mengubah kode)
- Kunci jawaban §3 (terutama #1, #4, #5) ke `docs/` (ruling baru) + berkas ini.
- Inventaris mekanis: `grep` semua jangkar angka (4.900/1080/1400/3:7) di `backend/tests/**` + `docs/**` + komponen frontend; hasilnya jadi daftar "tes yang boleh berubah" vs "jangkar yang harus tetap".
- **Selesai bila:** daftar jangkar + keputusan tertulis ada, nol kode tersentuh.

### Fase 1 — Scope server-side per peran (1–2 hari) → A
- **Baru:** `backend/app/core/scope.py` berisi `location_scope(user)` dan `apply_scope(stmt, model, user)` + `assert_location_allowed(user, location_id)` — pola & pesan galat mengikuti `kpi.py` supaya tidak lahir dua gaya scope.
- **Diterapkan ke:** `GET /decisions` (target), `approval-summary`/traces/evidence (assert read), `GET /balance/map`, `/supply`, `/demand`, `/price`, `/batches`, `/safety`, `/supplier-exclusions` (`scope_location_id`), `/admin/locations`, `/events`.
- `_assert_decision_readable`: `VERIFIER_ROLES` ikut scope lokasi (ruling baru) — tes `test_s4_rulings_tdd.py` diubah **sadar & bernomor**.
- **Frontend:** cakupan terkunci untuk `sppg_head` ("Cakupan: Jakarta — SPPG Anda", `aria-disabled` + tooltip alasan, bukan select bisu); `bgn_monitor` tetap bebas; hapus copy yang menyiratkan approver lintas lokasi bila ada.
- **Tes baru:** `backend/tests/test_scope_matrix.py` — matriks peran × endpoint (sppg_head / sppg_nutritionist / bgn_monitor) yang menegaskan jumlah baris yang terlihat dan status 403.
- **Selesai bila:** pytest hijau (termasuk matriks scope), 3 akun demo diuji manual (tabel expected vs actual), frontend hijau, tidak ada endpoint yang masih membocorkan lokasi lain.

### Fase 2 — Skema & data pemasok (1–2 hari) → B1
- **Migrasi 012:** `suppliers` + `latitude`, `longitude`, `commodity_id` (FK, boleh NULL), `certification_status` (`none|hygiene|haccp` — kosakata sama dengan `batches`), `capacity_kg_per_week`, `contact_name`, `contact_phone`, `address`, `origin`, `updated_at`; CHECK koordinat + index (`commodity_id`), (`location_id`). Backfill 14 pemasok lama (koordinat pusat kota hub-nya).
- **Seed:** 30–50 pemasok deterministik (`stable_uuid(SEED_NAMESPACE, "supplier", i)`), nama realistis Indonesia, koordinat dari **daftar statis kurasi** kota/kecamatan (tanpa panggilan geocoding → tanpa jaringan, tanpa rate-limit); sebaran fokus komoditas (telur/ayam/wortel), 3–5 pemasok skor rendah untuk kasus "supplier janggal".
- **Endpoint baru:** `GET /suppliers` (filter `commodity`, `location/hub`, `q`, paginasi; kolom sertifikasi & `excluded` dihitung dari `supplier_exclusions`) dan `GET /suppliers/map` **atau** tambahan `suppliers[]` pada `GET /balance/map` (payload ±40×6 field ≈ 4 KB → **satu kali polling lebih murah**; rekomendasi: tambah di `/balance/map`, tapi tandai eksperimental).
- **Tes:** unit filter/kualifikasi + tes endpoint + **tes kualitas data** (semua koordinat dalam bbox Indonesia, unik per pemasok, `commodity_id` valid, ≥3 pemasok per hub SPPG, jumlah total = target).
- **Selesai bila:** `alembic upgrade head` + `downgrade -1` bersih di DB baru; endpoint mengembalikan data dengan scope benar; tes kualitas data lulus.

### Fase 3 — Peta & halaman Pemasok (1–2 hari) → B2
- **SupplyMap:** layer penanda pemasok (bentuk/warna **berbeda** dari pin SPPG; legenda baru "Pemasok"; toggle "Tampilkan pemasok (N)" default **off**; popup: nama, keandalan %, komoditas, sertifikat, hub, status eksklusi; klik → buka keputusan terkait bila ada).
- **Anti-padat:** tampil hanya saat `zoom ≥ 8` atau di-cluster; ikut filter komoditas yang sudah ada; batasi satu komoditas per tampilan.
- **Halaman Pemasok:** ganti workaround sampel-keputusan dengan `GET /suppliers` (hapus asumsi "TIDAK punya endpoint daftar pemasok" di `lib/suppliers-board.ts`), tambah kolom koordinat/komoditas/sertifikat; aksi eksklusi tetap.
- **Lib murni + tes:** klasifikasi pin (aktif/eksklusi/keandalan rendah), urutan & ringkasan daftar, isi legenda; tes render komponen + wiring test (`SupplyMap` menerima `suppliers`).
- **Selesai bila:** peta memuat N pin pemasok di komoditas terpilih, toggle & legenda bekerja dengan keyboard, 0 error konsol, tangkapan layar sempit/lebar diperiksa, tes hijau.
- **Opsional 3b:** layer garis hub→SPPG + panel "rute pasokan".

### Fase 4 — Generator deret waktu & penanda origin (2 hari) → C1
- **Migrasi 013:** kolom `origin` (`seed|demo`) + `generated_at` pada `decisions`, `batches`, `menu_plans`, `supply_records`, `demand_records`, `price_signals`; index (`origin`, kolom tanggal).
- **Baru:** `backend/app/seed/timeseries.py` — parametrik `(start, end, interval, locations, commodities)`, RNG deterministik (seed turunan `stable_uuid`), pola mingguan (akhir pekan lebih rendah untuk SPPG sekolah), derau terkendali, anomali **hanya** untuk kasus skrip.
  - **Konvergensi jangkar:** baris snapshot terakhir per lokasi×komoditas = nilai kanonik (Jakarta 300/1.080, Cianjur 1.400, dst) → Overview/KPI/design.md §11 tidak berubah.
  - **Idempotent:** unique index `(location_id, commodity_id, recorded_at, origin)` + upsert; menjalankan dua kali tidak menggandakan.
  - **Masa depan** hanya di tabel yang memang merencanakan: `menu_plans`, kebutuhan (demand `needed_by`), jadwal kirim, `decisions.expires_at` — aktual (`recorded_at`/`harvested_at`) **tidak** dibuat di masa depan.
- **Endpoint demo:** `GET /demo/preview?start&end` (jumlah baris yang akan ditambah, tanpa menulis) dan `POST /demo/timeseries {start,end,force}` (menambah/memperbarui + ringkasan `{added, skipped, range, counts}`), plus `POST /demo/timeseries/purge` (hapus `origin='demo'` saja).
- **Tes:** deterministik (dua kali = identik), idempotent (tidak dobel), konvergensi jangkar, batas rentang (tolak tanggal ngawur/rentang terbalik), purge tidak menyentuh `origin='seed'`, dan **tes performa** (target: < 30 detik untuk rentang 66 hari).
- **Selesai bila:** setelah generate, `select count(*), min, max` per tabel sesuai target rentang; Overview masih 4.900 kg/3:7; 12 berkas tes jangkar tetap hijau.

### Fase 5 — Demo Control (1 hari) → C2
- Panel baru **"Data & rentang waktu"** di tab Demo Control: input mulai/selesai (default **1 Sep 2026 → 5 Nov 2026**), pratinjau "akan menambah N baris" (`/demo/preview`), tombol **Buat/perbarui data**, **Bersihkan data demo**, dan status terakhir ("snapshot: 14 Okt 22.31 · 1.842 baris demo").
- Satu tombol **"Segarkan ke hari ini"** = jalankan seeder relatif `now` + `POST /demo/seed` (4 kasus skrip tetap TTL ≥60 menit) — inilah tombol yang dipakai pada hari demo.
- Peringatan jujur di UI: 4 kasus skrip selalu di-anchor ke waktu sekarang; baris `origin='demo'` bisa dihapus; baris kanonik tidak tersentuh.
- **Selesai bila:** dari UI, ganti rentang → data bertambah; bersihkan → kembali ke angka kanonik; ulangi → hasil identik (bukti idempotensi lewat layar, bukan klaim).

### Fase 6 — Verifikasi menyeluruh, dokumen, latihan demo (1 hari)
- Matriks verifikasi end-to-end: 3 peran × endpoint × angka DB (satu tabel bukti), pytest/vitest/tsc/lint, tangkapan peta (dengan & tanpa layer pemasok, lebar sempit & lebar desktop).
- Dokumen: `docs/Schema.md` (§ suppliers + origin), `docs/design.md` (§ peta: pin SPPG vs pemasok vs hub; § mapping peran↔cakupan), `docs/PRD.md` (aturan scope baru), `AGENTS.md`/`TODO.md` (status).
- **Latihan demo 5 menit:** login kepala SPPG (cakupan sendiri) → feed (cari/urut/chip "Perlu tindakan") → popup approval → eksekusi → peta + layer pemasok → Demo Control (ganti rentang, segarkan ke hari ini, bersihkan).
- **Rollback tertulis:** `alembic downgrade` dua langkah + `PURGE origin='demo'` + restore snapshot kanonik.

---

## 5. Risiko & mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Jangkar angka (4.900/3:7/Jakarta 300:1.080) pecah saat data ditambah | 12 berkas tes + design.md salah, demo Overview berubah tanpa sengaja | Generator **konvergen** ke nilai kanonik; Fase 0 inventaris; kalau tetap harus berubah → perubahan sadar + catatan |
| Ruling 2026-10-08 (approver lintas lokasi) dicabut | `test_s4_rulings_tdd.py` gagal; alur approval yang pernah didemokan berubah | Ubah tes **sadar**, tulis ruling baru bertanggal + alasan di `docs/` |
| Migrasi tidak auto-jalan di kontainer | DB tidak sinkron dengan kode → error 500 membingungkan | Langkah manual didokumentasikan; uji `upgrade` **dan** `downgrade` di DB bersih sebelum lanjut |
| Seeder tidak idempoten | Baris ganda → KPI/Overview salah (mis. pasokan jadi 2×) | Unique index + upsert + `origin` marker; tes "jalankan dua kali" |
| Peta terlalu padat (10 SPPG + 2 hub + 40 pemasok) | Sulit dibaca, demo justru membingungkan | Toggle default off, ambang zoom/cluster, satu komoditas, legenda + hitungan |
| Aktual bertanggal masa depan | Kredibilitas di mata juri (data "karangan") | Batasi aktual ke masa lalu; masa depan hanya rencana (keputusan #4) |
| Feed ratusan keputusan | Halaman berat, pengguna bingung | Sudah ditangani: kotak cari, kontrol urutan, chip bahasa manusia, 24 kartu per halaman (14 Okt) + index (`target_location_id`, `created_at`) |
| Drive E exFAT + bind mount lambat | Tes/build lambat atau gagal aneh | Semua uji dijalankan di dalam kontainer (kebiasaan repo), bukan di host |

---

## 6. Perkiraan usaha & urutan

| Fase | Isi | Perkiraan |
|---|---|---|
| 0 | Keputusan + inventaris | ½ hari |
| 1 | Scope per peran (A) | 1–2 hari |
| 2 | Skema + data pemasok (B1) | 1–2 hari |
| 3 | Peta + halaman pemasok (B2) | 1–2 hari |
| 4 | Generator data s/d 5 Nov (C1) | 2 hari |
| 5 | Demo Control (C2) | 1 hari |
| 6 | Verifikasi + dokumen + latihan | 1 hari |
| | **Total** | **±8–10 hari kerja bertahap** |

Versi cepat (kalau waktu mepet): Jakarta saja (tanpa user demo tambahan) + 30 pemasok + riwayat 30 hari + tanpa layer garis rute ⇒ ±4–5 hari.

**Urutan wajib:** Fase 1 **sebelum** Fase 4. Kalau data multi-lokasi masuk lebih dulu, kepala SPPG Jakarta akan melihat data SPPG lain (kebocoran scope yang justru ingin dihilangkan).


---

# Lampiran A — Inventaris jangkar & benturan tes (keluaran Fase 0, 14 Okt 2026)

Dihasilkan dengan `grep -rnE "4[._]?900|1[._]?080|1[._]?400|4900|1080|1400|\\b300\\b"` atas
`backend/tests`, `frontend/tests`, `docs`, `frontend/{lib,components,app}`.

## A.1 Pemblokir keras — tes yang AKAN gagal bila baris data ditambah (tanpa perubahan sadar)

| # | Berkas:baris | Yang ditegaskan | Kenapa pecah |
|---|---|---|---|
| 1 | `backend/tests/test_sprint1_contract_reconciliation.py:61-64` | `count(*) price_signals = 44`, `count(*) suppliers = 14`, `refs (source='pihps_reference') = 30`, `quotes (source='supplier_quote') = 14` — query ke **DB hidup** | Menambah pemasok/harga mengubah jumlah SELURUH tabel |
| 2 | `backend/tests/test_supplier_city_coverage.py:53` | `len(refs) == 30` ("acuan pasar 10 kota x 3 komoditas tetap utuh") | idem, pada subset `pihps_reference` |
| 3 | `backend/tests/test_demo_users.py:41` | `len(rows) == 3` (user demo) | Menambah 2 user demo (Bandung, Surabaya) → 5 |
| 4 | `backend/tests/test_api_supply_demand.py:20,38` + `test_supply_latest_record_not_sum` | `LATEST = 2026-10-08T12:00Z`; `/supply/Cianjur/telur` → `quantity_kg == 1400.0` | Endpoint mengembalikan record **TERBARU**; baris baru bertanggal lebih akhir menggesernya |
| 5 | `backend/tests/test_kpi_api.py:20-22` | `NOW = 2026-10-08T12:00Z`, `START = NOW-1d`, `END = NOW` | Jendela KPI terkunci 1 hari; baris baru di dalam jendela itu mengubah 7 metrik |
| 6 | `backend/tests/test_balance_map.py:133-135` | Jakarta `supply_kg == 300.0`, `shortage_kg == 780.0` | Snapshot terbaru per lokasi |
| 7 | `backend/tests/test_api_decision_intelligence.py:47-60` | Jakarta `300.0/1080.0`, Cianjur `1400.0/1400.0` | idem |
| 8 | `backend/tests/test_s4_rulings_tdd.py` | Ruling 2026-10-08 (approver lintas lokasi) | **Pemblokir Fase 1**, bukan Fase 4 |

## A.2 Aman terhadap penambahan data (menyebut angka yang sama, tetapi dari fixture sendiri)

`test_candidate_generation.py`, `test_decision_context.py`, `test_event3_service.py`,
`test_gaps.py`, `test_price_regional_seed.py`, `test_recommendation_service.py`,
`test_seed_data.py`, `test_seed_load_db.py`, `test_sprint1_acceptance.py`, `test_sprint2_scenarios.py`
(sebagian memakai JSON seed, sebagian menyisipkan datanya sendiri).

Frontend (semua **fixture**, tidak memanggil API hidup → hanya pecah bila bentuk payload berubah):
`tests/overview-location-breakdown.test.tsx:8-37`, `tests/stock-chart.test.tsx:14-15`,
`tests/ops-console.test.tsx`, `tests/supply-map.test.tsx`, `tests/map-console.test.ts`.

## A.3 Tiga syarat yang mengikat desain generator (Fase 4)

- **C1 — konvergensi kanonik:** untuk setiap pasangan lokasi×komoditas, baris **terbaru**
  (`recorded_at` maksimum) wajib bernilai kanonik (Jakarta 300/1.080, Cianjur 1.400, dst).
  Ini yang membuat pemblokir #4, #6, #7 tetap hijau **dan** menjaga cerita demo.
- **C2 — jendela terlarang:** rentang `2026-10-07T12:00Z … 2026-10-08T12:00Z` tidak diisi
  baris baru apa pun yang dibaca KPI (menu plan, delivery, disposal, keputusan).
- **C3 — pisahkan seed kanonik dari data demo:** pemblokir #1, #2, #3 diubah **sadar**
  menjadi kontrak "seed kanonik" (mis. `refs` tetap 30, `suppliers` seed tetap 14) **plus**
  asersi baru bahwa data `origin='demo'` bersifat aditif dan bisa dihapus tanpa menyentuh
  seed. Perubahan ini dicatat per berkas di laporan Fase 4.

---

# Lampiran B — Keputusan pemilik (dikunci 14 Okt 2026)

| # | Pertanyaan | Jawaban pemilik | Akibat pada rencana |
|---|---|---|---|
| 1 | Arti "data sampai 5 November" | **Rencana saja:** aktual hanya masa lalu; masa depan = menu plan, kebutuhan, jadwal kirim, `decisions.expires_at` | Fase 4 menulis aktual hanya sampai **hari ini**; rentang s/d 5 Nov dipakai tabel rencana. UI boleh menampilkan "proyeksi" untuk baris rencana, tanpa label itu pada aktual |
| 2 | Mulai dari fase mana | **Fase 0 + 1** (kunci keputusan + scope server-side per peran) | Fase 0 **selesai 14 Okt** (dokumen ruling + Lampiran A). Fase 1 menyusul |
| 3 | Ruling 2026-10-08 (approver baca lintas lokasi) dicabut? | **Ya** — target dikunci ke SPPG sendiri, sumber tetap lintas daerah, `bgn_monitor` global read-only | Ditulis di `docs/ruling-2026-10-14-scope-lokasi.md`; tes `test_s4_rulings_tdd.py` + tes ringkasan keputusan yang memakai approver lokasi lain diubah sadar di Fase 1 |

Sisa keputusan §3 (#3 bentuk data pemasok, #5 jangkar, #6 user demo tambahan, #7 garis rute,
#8 volume) memakai rekomendasi di dokumen ini dan akan dikonfirmasi lagi saat fasenya tiba.


---

# Status pelaksanaan

## Fase 0 — SELESAI (2026-10-14)
`docs/ruling-2026-10-14-scope-lokasi.md` (ruling berlaku, menggantikan 2026-10-08) +
Lampiran A/B di rencana ini. Nol baris kode diubah.

## Fase 1 — SELESAI (2026-10-14)
- `backend/app/core/scope.py` (helper tunggal) + penerapan di `api/{decisions,balance,supply,demand,price,supplier_exclusions,events,dossier}.py`.
- Dikunci: feed & detail keputusan (+summary/traces/chain/dossier/compliance/context), `balance/map`,
  semua baca per-lokasi (`supply`/`demand`/`price`), `supplier-exclusions`, event (target).
- Pengecualian sadar: `GET /batches` (sisi sumber), `GET /ledger/verify` (integritas nasional),
  endpoint komputasi murni, `/admin/*` (sudah monitor-only).
- Frontend: `ChaosPanel` mengirim **lokasi SPPG pemakai** sebagai target (dulu lokasi batch — 403),
  pemilih lokasi di `OpsConsole`/`Event2Panel` terkunci untuk peran SPPG, kop peta "Peta SPPG Anda".
- Bukti: **pytest 691 lulus / 0 gagal** (dari 29 gagal saat penerapan pertama), frontend
  **53 berkas / 449 tes lulus**, `tsc` 0 error, `lint` bersih; matriks manual 3 akun demo
  14/14 baris sesuai harapan; feed kepala = 132 = `count(*)` target Jakarta (monitor = total).
- Keputusan: akun demo ahli gizi dipindah Bogor → Jakarta (satu SPPG, prasyarat matriks AND);
  uji aturan memakai fixture `far_nutritionist_headers` supaya tidak bergantung akun demo.
- Catatan: menjalankan suite backend penuh terhadap DB demo menyisakan beberapa baris uji
  (128 seed → 132). Fase 4 menggantikan seluruh dataset, jadi tidak dibersihkan manual di sini.

## Fase 6 — SELESAI (2026-10-15)
Bukti lengkap: **`docs/verification/fase-6.md`** (dibuat 2026-10-15). Ringkasnya: gerbang otomatis
hijau (pytest **757 lulus / 3 skip**, `ruff check .` bersih — 10 pelanggaran Fase 1–4 dibersihkan
dengan 5 auto-fix + 5 patch manual, vitest **518 lulus**, `tsc` 0, `next lint` 0, `next build` 0);
skrip bukti baru **`backend/scripts/verifikasi_fase6.py`** (matriks 3 peran × endpoint × angka DB,
API vs SQL, exit ≠0 bila berselisih) → **SEMUA COCOK**; latihan demo 6 ketukan dijalankan betulan
(masuk SPPG Head → feed `12 perlu tindakan / 156 total` → Decision & Evidence → `Setuju` → baris
`approvals` tercatat → `Eksekusi` → status `executed`, **ledger 2.197 → 2.198** `valid:true` →
peta 10 pin pemasok `telur`); dokumen disinkronkan (Schema § suppliers + § `origin`/`generated_at`,
design §2 cakupan/§3.1 layer pemasok/§3.8 Pemasok/§3.9 panel rentang, PRD §3, TODO bagian baru
"Track rencana 2026-10-14", vault `active_context.md` + `decisions.md`).
**Tertinggal:** `AGENTS.md` § Batasan kritis — berkas instruksi agent dilindungi, tulisan saya
tidak disetujui sesi ini; teks usulan ada di `docs/verification/fase-6.md` §4.4.
**Temuan baru yang mengikat cara kerja:** (a) suite pytest menulis ke DB demo → residu uji
(156 keputusan vs 15 milik narasi demo; `users` 1.073 baris untuk 3 akun) — usul `TEST_DATABASE_URL`;
(b) `next build` saat `next dev` hidup → chunk 404, halaman tanpa hidrasi sampai kontainer
di-restart; (c) filter komoditas UI memuat `beras` yang tidak ada di DB → `404` + galat jujur.

### Catatan asli Fase 6 (sebelum dikerjakan, disimpan untuk jejak)

Menunggu lanjut: verifikasi menyeluruh (matriks 3 peran × endpoint × angka DB), pembaruan dokumen
(Schema/design/PRD/AGENTS/TODO + vault), latihan demo 5 menit, dan rollback tertulis.
Termasuk dua temuan kebersihan dari Fase 5: 10 pelanggaran `ruff` di berkas Fase 1–4
(1 impor tak terpakai, 4 blok impor tak terurut, 5 baris >100 karakter; 5 auto-fix) dan daftar
komoditas UI yang di-hardcode di 4 tempat (memuat `beras` yang tidak ada di DB → 404).
**Fase 5 SELESAI 2026-10-15** — panel "Data & rentang waktu" sudah hidup di tab Demo Control;
rinciannya di bagian akhir berkas. **Fase 7 ditambahkan 2026-10-15** (permintaan pemilik: pemasok
mock harus di sekitar SPPG Jakarta — juga di bagian akhir berkas).

## Fase 2 — SELESAI (2026-10-14)
- **Migrasi `012_supplier_profile`**: `suppliers` + `latitude`, `longitude`, `commodity_id` (FK boleh NULL),
  `capacity_kg_per_week`, `certification_status`, `address`, `contact_name`, `updated_at`;
  CHECK rentang koordinat, CHECK koordinat BERPASANGAN (`(lat IS NULL) = (lon IS NULL)`),
  CHECK kapasitas >= 0, CHECK kosakata sertifikasi; index `location_id` + `commodity_id`.
  Backfill 14 pemasok lama dari titik hub-nya (9 posisi bergeser per hub). Diverifikasi
  `upgrade head` → `downgrade -1` → `upgrade head` di DB sementara (8 kolom profil, bersih).
- **Data**: `data/seed/suppliers_demo.json` (30 pemasok, 3 per hub × 10 hub, 3 komoditas masing-masing 10,
  4 pemasok skor <=0.45 tanpa sertifikasi) + seeder idempoten `backend/app/seed/suppliers_demo.py`
  (`python -m app.seed.suppliers_demo`; juga lewat `seed_data.py --with-demo-suppliers`).
  DB demo: **44 pemasok**, semuanya berkoordinat, 30 berkapasitas.
- **Endpoint `GET /suppliers`** (`backend/app/api/suppliers.py`): filter `commodity`/`location`/`q`,
  paginasi 1..200, `excluded_at_hub` + `excluded_scope_locations` dari eksklusi lokal aktif.
  Cakupan: sisi sumber → dibaca semua peran login (sejajar `GET /batches`), dicatat di ruling §4.2.
- **Tes baru**: `tests/test_suppliers_api.py` (15) + `tests/test_suppliers_data.py` (13) — termasuk
  kualitas data (bbox Indonesia, >=3 per hub, tak ada pin bertumpuk, skor rendah ada, id natural key)
  dan **kegagalan-terbuka** validator berkas. `test_sprint1_contract_reconciliation.py` diperbarui
  sadar: `suppliers == 14 + len(load_demo_rows())`.
- **Temuan Fase 2 (DIPERBAIKI, lihat "Fase 2b" di bawah)**: 3 pemasok kanonik (`Supplier A/B/C Cianjur`)
  di DB demo memakai nilai default kolom 0.80, bukan skor di `sprint1_seed.json` (0.92/0.88/0.81).
  Sebabnya loader seed hanya menambah bila NAMA belum ada, jadi baris warisan tak pernah dikoreksi.
- **Id kanonik**: 14 pemasok kanonik memakai UUID v4 acak (baris warisan), BUKAN UUID5 natural key yang
  dihitung `build_seed_rows`. Sengaja TIDAK dirapikan: mengganti primary key berarti menulis ulang seluruh
  FK yang menunjuknya (`batches`, `price_signals`, `supply_records`). Dipaku apa adanya oleh
  `test_canonical_supplier_ids_are_legacy_random_uuids` supaya perubahan id terjadi sadar.

### Penyimpangan dari rencana (disengaja, alasan tertulis)
- `contact_phone` **tidak** ditambahkan: tidak ada satu pun layar yang menampilkannya, dan mengarang
  nomor telepon untuk 30 pemasok sintetis hanya menambah data palsu tanpa nilai demo.
- `origin` **tidak** ditambahkan sebagai kolom: pemisahan kanonik vs demo sudah dijamin dua hal yang
  bisa diuji — berkas berbeda (`sprint1_seed.json` vs `suppliers_demo.json`) dan namespace id berbeda
  (`supplier::<nama>` vs `demo_supplier::<nama>`). Kolom tambahan tanpa konsumen = beban migrasi.
- **Tidak** menambah `suppliers[]` ke `GET /balance/map`: payload peta di-poll berkala, sedangkan data
  pemasok nyaris statis. Frontend akan mengambil `GET /suppliers` sekali dengan staleTime panjang
  (Fase 3), jadi tidak ada polling kedua DAN tidak ada pembengkakan payload peta.
- Seed demo memakai id dari NAMA (`demo_supplier::<nama>`), bukan indeks urutan seperti draf rencana:
  indeks berubah bila baris disisipkan di tengah, nama tidak.

## Fase 3 — SELESAI (2026-10-14)
- **Lib murni (tanpa DOM/MapLibre)**: `frontend/lib/supplier-pins.ts` — `supplierPinRows`,
  `supplierPinTone` (ok/low/unknown), `supplierPinClass`, `supplierPopupLines`, `supplierLayerSummary`,
  `supplierAccessibleLabel`, `suppliersForCommodity`, `shouldLoadSuppliers`, `supplierToggleLabel`,
  ambang zoom, `SUPPLIER_PIN_LEGEND`. Diuji `tests/supplier-pins.test.ts` (18).
- **`SupplyMap`**: prop `suppliers`, tombol `Tampilkan/Sembunyikan pemasok (N)` (default **mati**,
  `aria-pressed`), legenda "Pemasok:" dengan bentuk belah ketupat (beda dari titik bulat pin SPPG),
  penanda disinkronkan hanya saat lapisan nyala + zoom cukup, dibuang saat dimatikan/dijauhkan,
  hint `role="status"` kenapa lapisan masih kosong, popup (nama, komoditas, hub, keandalan, sertifikasi,
  status eksklusi). Satu handler `zoomend` mengurus cakupan zoom.
- **Halaman Pemasok**: `lib/suppliers-board.ts` + `components/SupplierBoard.tsx` ditulis ulang —
  sumbernya `GET /suppliers` (bukan lagi sampel keputusan); kolom Pemasok/Hub/Komoditas/Keandalan/
  Sertifikasi/Koordinat/Status, kartu Ringkasan (terdaftar, rata-rata, keandalan rendah, punya titik
  peta, dieksklusi), register eksklusi + panel usul eksklusi tetap. Data: `lib/hooks/useSuppliers.ts`,
  `lib/api.ts` (fetch `/suppliers`), `lib/query.ts` (`QUERY_STATIC_STALE_MS` + `keys.suppliers`),
  rewrite `/suppliers` di `next.config.js` (dipaksa tes `proxy-roots`).
- **Bukti mesin**: vitest **56 berkas / 487 tes lulus** (dari 449), `tsc --noEmit` 0 error, lint bersih.
  Tes perilaku peta: `tests/supply-map-layer.test.tsx` (9) memakai MapLibre palsu — pin tidak digambar
  saat lapisan mati, muncul/dibuang mengikuti zoom, putus saat unmount, label aksesibilitas utuh.
- **Bukti peramban (aplikasi nyata, bukan harness)**: kepala SPPG & BGN Monitor, login lewat tombol akun
  demo; tombol lapisan `aria-pressed` berubah lewat **Enter** (keyboard); zoom >= 8 → 10 pin pemasok
  berlabel (komoditas telur), 6 <= zoom < 8 → 10 titik TANPA nama, zoom < 6 → 0 pin + hint; popup
  "Telur Berkah Cianjur" berisi komoditas/hub/keandalan 38%/Tidak bersertifikat; halaman Pemasok
  **44 baris** (Pemasok terdaftar 44, rata-rata 79%, 4 keandalan rendah, 44/44 berkoordinat);
  **0 pesan konsol, 0 error JS**.

### Penyimpangan Fase 3 (disengaja, alasan tertulis)
- Draf rencana: "tampil hanya saat zoom >= 8". Pelaksanaan memakai **dua ambang**: titik di zoom >= 6,
  **nama** di zoom >= 8 (`SUPPLIER_PIN_MIN_ZOOM` / `SUPPLIER_LABEL_MIN_ZOOM`). Alasan: tampilan jaringan
  (10 lokasi) mendarat di zoom ~5–6, jadi ambang 8 tunggal membuat lapisan terlihat RUSAK pada demo
  peran monitor (nyala tapi kosong); sebaliknya nama kota di Jawa saling menimpa pada zoom 6–8.
  Nama tetap tersedia lewat `title`/`aria-label` di pita tengah, jadi tidak ada informasi hilang.
- `SupplierBoard` menampilkan pesan galat MANUSIA ("Tidak bisa memuat data pemasok") alih-alih
  `error` mentah dari `request()` yang memuat path API (aturan `ui-copy-hygiene`).

### Temuan saat verifikasi (bug lama, diperbaiki di kedua lapisan)
- **`aria-label` penanda peta hilang**: MapLibre 4.7 menulis `aria-label="Map marker"` pada elemen
  penanda SAAT konstruksi, menimpa keterangan yang dipasang sebelumnya — jadi pembaca layar
  membacakan "Map marker" untuk semua pin SPPG (bug sudah ada sebelum Fase 3) dan pin pemasok.
  Perbaikan: pasang `title`/`aria-label` SESUDAH `new maplibregl.Marker(...)`; tes memakai MapLibre
  palsu yang meniru perilaku menimpa itu, supaya urutannya terkunci.
- **Selesai**: drift skor 3 pemasok kanonik diperbaiki di Fase 2b (baris DB ← `sprint1_seed.json`).

## Fase 2b — SELESAI (2026-10-14): koreksi skor kanonik
Keputusan yang diambil: **baris DB diselaraskan ke berkas kanonik** (`data/seed/sprint1_seed.json`),
bukan sebaliknya. Alasan: JSON adalah sumber kebenaran yang ditulis tangan untuk 14 pemasok kanonik,
sedangkan 0.80 di DB adalah nilai DEFAULT kolom yang kebetulan menempel karena baris dibuat sebelum
skor kanonik terpasang — bukan angka yang pernah dipilih siapa pun.

- **`backend/app/seed/seed_data.py`**: loop pemasok tidak lagi hanya menambah baris baru. Bila nama
  kanonik SUDAH ada tetapi `reliability_score` berbeda dari JSON, skornya dikoreksi dan dihitung di
  `counts["suppliers_corrected"]`. Sengaja hanya skor: id/komoditas/sertifikasi/lokasi tidak disentuh
  supaya seeder tidak berubah menjadi alat perombak identitas baris.
- **Bukti**: `python -m app.seed.seed_data --reference-time 2026-10-08T12:00:00+00:00` → keluaran
  `Row baru: {'suppliers_corrected': 3}`, dan potret tabel SEBELUM vs SESUDAH identik
  (suppliers 44 / decisions 136 / batches 6 / supply 30 / demand 312 / prices 44). Jalan kedua →
  `{}` (idempoten penuh). Skor kanonik kini persis JSON: A 0.92, B 0.88, C 0.81 (D 0.85, dst).
- **Tes**: `test_known_canonical_drift_is_tracked_not_hidden` diganti dua tes yang lebih jujur —
  `test_canonical_supplier_scores_match_seed_json` (drift sekecil apa pun = merah; skor ini dipakai
  `services/recommendation_service.py` saat memilih pemasok) dan
  `test_canonical_supplier_ids_are_legacy_random_uuids` (memaku fakta id v4 warisan; merapikannya
  berarti menulis ulang FK di `batches`/`price_signals`/`supply_records`, jadi sengaja ditunda).
- **Sisa yang diketahui (bukan bug baru)**: keputusan Cianjur yang SUDAH tersimpan memuat angka turunan
  (`expected_loss`, `candidate_score`) yang dihitung dengan skor lama 0.80. Baris keputusan dibuat
  skrip/demo (bukan bagian `sprint1_seed.json`) dan loader memang tidak menghitung ulang baris lama;
  Fase 4 yang meregenerasi dataset akan menyegarkan angka itu.

## Fase 4 — SELESAI (2026-10-15): generator deret waktu & penanda `origin`

Hasil: dataset demo punya RIWAYAT 1 Sep → 5 Nov 2026 (sebelumnya satu snapshot 8 Okt 12:00),
tanpa satu pun jangkar kanonik bergeser.

- **Migrasi `013_origin_generated_at`**: kolom `origin` (`seed|demo`, default `seed`) + `generated_at`
  (NULL untuk baris kanonik) pada 6 tabel (`supply_records`, `demand_records`, `price_signals`,
  `menu_plans`, `batches`, `decisions`), CHECK kosakata, index `(origin, kolom tanggal)`, dan kunci
  upsert: `uq_supply_records_loc_com_time_source` (loc, com, waktu, **source**),
  `uq_demand_records_loc_com_time`, plus dua index parsial harga
  (`uq_price_signals_reference`, `uq_price_signals_quote`).
  **`downgrade()` MENGHAPUS baris `origin='demo'` lebih dulu** — tanpa kolom, baris demo akan terbaca
  kanonik dan menggeser jangkar; data demo turunan, dibangun ulang dalam detik.
  Diverifikasi dua arah: `upgrade head` → `downgrade -1` (kolom origin = 0, tabel berisi kanonik saja:
  supply 30 / prices 44 / menu 140) → `upgrade head` (6 kolom kembali).
- **`backend/app/seed/timeseries.py`** (baru): perencana baris MURNI (`actual_timestamps`,
  `supply_value`, `reference_price_value`, `quote_price_value`, `planned_portions`, `plan_*`,
  `plan_all`, `validate_range`) + orkestrasi DB (`generate_timeseries`, `preview_timeseries`,
  `purge_demo_rows`) + CLI (`python -m app.seed.timeseries [--preview|--purge]`).
  Determinisme dari `sha256(kunci)` (bukan RNG berjalan) → urutan iterasi tidak mengubah nilai.
  Pola mingguan: akhir pekan ×0,92 untuk pasokan, porsi rencana juga turun; derau ±6% (pasokan) / ±3% (harga).
- **Endpoint demo** (`backend/app/api/demo.py`): `GET /demo/preview` (hitungan tanpa menulis),
  `POST /demo/timeseries {start,end,interval_hours,force}` (force = purge lalu bangun),
  `POST /demo/timeseries/purge`. Peran sama dengan `/demo/seed`; bgn_monitor 403; rentang ngawur 422.
  Kasus skrip `/demo/seed` kini ditandai `origin='demo'` supaya purge ikut membersihkannya.
- **Dataset setelah generate**: `supply_records` 30 kanonik + **2.190 demo** (1 Sep → 7 Okt 00:00,
  selang 12 jam), `price_signals` 44 + **2.274 demo** (referensi + kutipan mingguan), `menu_plans`
  140 kanonik (24 Sep–7 Okt) + **520 demo** (1 Sep → **5 Nov**; hari kanonik sengaja menang).
- **Bukti**: pytest **754 lulus / 3 skip / 0 gagal** (dari 721; +33 tes baru: 16 perencana murni,
  9 DB, 8 endpoint) — dijalankan dengan dataset demo ADA di DB, kondisi paling ketat. Tes endpoint
  menegaskan lewat HTTP bahwa setelah generate `/supply/Cianjur/telur` tetap **1.400 kg** dan
  `/balance/map` tetap **4.900 kg, 3 surplus : 7 shortage**. Tes performa: 66 hari < 30 detik
  (nyata ~3 detik). `ruff check` bersih untuk semua berkas baru.

### Penyimpangan dari rencana Fase 4 (disengaja, alasan tertulis)
- **`demand_records` tidak digenerate.** `/demand/forecast` memakai **3 observasi terbaru** tanpa
  saringan origin; menambah observasi apa pun menggeser `daily_avg` dan nilai kebutuhan terbaru —
  yaitu jangkar yang harus tetap. Riwayat demand sudah 13 titik per pasangan sejak 20 Agu, jadi
  tidak ada lubang yang ditinggalkan. "Kebutuhan s/d 5 Nov" diwakili `menu_plans` (tabel yang memang
  dibaca metrik kontinuitas menu), bukan dengan mengarang baris demand.
- **`delivery_events`/`disposal_events` tidak digenerate** (alasan sama: `delivered_at` adalah aktual).
- **Kunci upsert memuat `source`, bukan `origin`.** Baris kanonik dan demo memang dipisah `origin`,
  tapi `(loc, com, waktu)` yang sama sah punya dua `source` berbeda (`test_supply_same_timestamp_source_precedence`),
  jadi kunci yang benar adalah kunci alami tabel + source. `menu_plans` justru `DO NOTHING` karena
  kunci uniknya tidak memuat `origin`.
- **`batches`/`decisions` dapat kolom `origin` tanpa baris generator.** Sumber baris demo untuk
  keduanya adalah kasus skrip Demo Control (sudah ditandai), bukan deret waktu.
- **Tiga tes kanonik diubah sadar & berkomentar tanggal** (semuanya disaring `origin='seed'`):
  `test_sprint1_contract_reconciliation.py::test_reconciliation_preserves_row_counts`,
  `test_seed_load_db.py::test_supplier_quotes_persisted_as_price_signals`,
  `test_price_regional_seed.py::test_no_orphan_price_rows_after_load`. Invarian ketiganya soal baris
  SEEDER; `count(*)` seluruh tabel adalah pembacaan yang terlalu longgar begitu data demo ada.
  Inilah "5 berkas pemblokir" §2.3 yang sudah diperkirakan rencana — dua lainnya (`test_supplier_city_coverage`,
  `test_api_supply_demand`) tetap hijau tanpa perubahan.

## Fase 5 — SELESAI (2026-10-15): panel "Data & rentang waktu" (Demo Control)

Hasil: riwayat demo bisa dibangun, diganti rentangnya, dan dibersihkan DARI LAYAR — dengan angka
yang bisa dicocokkan ke DB, bukan klaim.

- **Kode frontend** (backend tak perlu diubah; endpoint Fase 4 + `/demo/refresh` sudah ada):
  - `components/DemoDataPanel.tsx` (baru) — panel di tab Demo Control, ditaruh SEBELUM konsol
    analisis karena urutan demo nyata: siapkan data dulu, baru picu skenario.
  - `lib/demo-data.ts` (baru) — logika MURNI: validasi rentang, `toIsoDateTime` (offset wajib),
    dan SEMUA kalimat (pratinjau, hasil bangun, hasil hapus, hasil segarkan, status, peringatan).
  - `lib/api.ts` — 5 helper: `fetchDemoDataStatus`, `fetchDemoPreview`, `runDemoTimeseries`,
    `purgeDemoTimeseries`, `refreshDemoToToday`.
  - `app/globals.css` — gaya panel memakai token yang ada (batas kontrol `--line-input`, peringatan
    `--warn-bg/--warn-ink`, teks meta ≥12px sesuai design.md §4); nol hex mentah.
- **Keputusan desain yang disengaja**:
  - Pratinjau memakai tombol **"Pratinjau"**, bukan panggilan otomatis tiap ketikan tanggal
    (rentang 66 hari = 12 siklus network per ketik). Sebagai gantinya, mengubah rentang **membuang
    hasil/pratinjau lama** supaya layar tidak pernah menampilkan angka untuk rentang yang lain.
  - Hapus **dua langkah** (tombol → konfirmasi eksplisit), bukan `window.confirm`, supaya
    peringatan benar-benar terbaca dan bisa diuji tanpa DOM hidup.
  - Peringatan `REFRESH_WARNING` **ditampilkan apa adanya dari respons backend** setelah tombol
    segarkan; salinan klien (`refreshWarning()`) dipakai sebelum itu supaya peringatan sudah terbaca
    saat tombol belum ditekan.
- **Tes**: 31 tes baru — `tests/demo-data.test.ts` (22, logika murni; payload contoh diambil dari
  respons nyata) + `tests/demo-data-panel.test.tsx` (9, kontrak markup: peringatan terbaca sebelum
  aksi, keadaan "belum dimuat" tidak disamarkan jadi "tidak ada data", peran di luar cakupan tidak
  melihat kontrol). Gate: **vitest 518 lulus / 58 berkas**, `tsc` 0, `next lint` 0 warning.
- **Bukti layar** (browser, `sppg.head@demo.local`, `:3010`, tab Demo Control):
  | Langkah | Yang terlihat di layar | Silang-cek DB/API |
  |---|---|---|
  | Pratinjau rentang default | "Akan menambah untuk 66 hari: 2.190 baris pasokan · 2.274 harga · 660 rencana menu …" | `/demo/preview` sama |
  | Ganti rentang ke 1 Sep–30 Sep | "Rentang 30 hari…", pratinjau lama hilang, pratinjau baru 1.740 / 1.810 / 300 | `/demo/preview` sama |
  | "Buat/perbarui data" + force | "Dihapus dulu 5.054 baris demo. Ditambahkan 1.740 pasokan · 1.810 harga · 300 rencana menu." — **persis sama dengan pratinjau** | `supply demo=1.740`, status 3.850 baris |
  | Kembalikan rentang default + force | "Dihapus dulu 3.850 … Ditambahkan 2.190 · 2.274 · 590" | 5.054 baris demo |
  | Ulangi TANPA force (idempotensi) | "Ditambahkan 0 pasokan · 0 harga · 0 rencana menu. Isi tabel sekarang: 2.190 · 2.274 · 590." | DB tetap 5.054; `origin='seed'` tetap 144 |
  | "Bersihkan data demo" (2 langkah) | "Dihapus 5.054 baris demo (…)"; status berubah jadi "Belum ada deret waktu demo — tombol 'Buat/perbarui data' mengisinya." | `supply/prices/menu demo=0`, `seed` utuh; **`/balance/map` = 4.900 kg, 3 surplus : 7 shortage, Cianjur 1.400 kg** |
  | "Buat/perbarui data" (pulihkan) | "Ditambahkan 2.190 · 2.274 · 590" | 5.054 baris demo (keadaan akhir) |
- **Kondisi akhir DB demo**: sama seperti sebelum verifikasi (5.054 baris demo + 144 kanonik) supaya
  demo tidak rusak oleh verifikasinya sendiri.
- **Penyimpangan sadar**: tombol **"Segarkan ke hari ini" TIDAK ditekan** pada DB demo — seeder
  relatif memindahkan TANGGAL snapshot kanonik dan membuat tes backend yang memaku 8 Okt 12.00 tidak
  cocok. Perilakunya sudah dikunci tes yang memulihkan keadaan sendiri:
  `tests/test_demo_timeseries_api.py::test_refresh_hari_ini_bergeser_dan_bisa_dikembalikan`
  (menegaskan nilai jangkar tetap, peringatan ikut di respons, dan jumlah per `origin` kembali persis).
- **Regresi**: pytest **757 lulus / 3 skip / 0 gagal** (sama dengan baseline Fase 4) dijalankan
  DENGAN dataset demo ada di DB — jangkar kanonik tetap hijau setelah seluruh siklus hapus/bangun.
- **Temuan di luar Fase 5** (belum diperbaiki, layak masuk Fase 6):
  1. `ruff check` **10 pelanggaran** di berkas Fase 1–4 (bukan Fase 5): 1 impor tak terpakai
     (`api/decisions.py`), 4 blok impor tak terurut, 5 baris >100 karakter. 5 di antaranya auto-fix.
  2. Daftar komoditas di UI masih hardcoded dan tidak sinkron dengan DB (`beras` ada di UI,
     tidak ada di DB → `/balance/map?commodity=beras` 404). UI menampilkan galat + "Coba lagi"
     (jujur, tidak diam-diam kosong), tetapi daftar itu di-hardcode di 4 tempat
     (`app/page.tsx`, `OpsConsole`, `Event2Panel`, `chaos-scope`) — sumber tunggal dari
     `/commodities` akan menghilangkan kelas bug ini.

## Fase 7 — Pemasok mock yang benar-benar terjangkau SPPG Jakarta (SELESAI 2026-10-15: 7a + 7b + 7c)

### 7.1 Permintaan pemilik (2026-10-15)
> "tambahkan sebuah plan untuk memperbaiki DB supplier contoh SPPG Jakarta — anda membuat data mock
> supplier di sekitar SPPG Jakarta atau daerah sekitarnya saja yang masih mungkin terjangkau oleh
> SPPG Jakarta sebagai supplier mereka."

### 7.2 Fakta terverifikasi (probe DB + API hidup, 2026-10-15)
| Yang diperiksa | Angka / temuan | Bukti |
|---|---|---|
| Isi tabel `suppliers` | **44 baris** = 14 kanonik + 30 demo | `select count(*) from suppliers` |
| Kanonik (14) | `data/seed/sprint1_seed.json`, nama pola `Supplier <Kota>-N`, **tanpa** koordinat/komoditas/kapasitas; terikat **14 kutipan harga** | JSON seed + `quotes == 14` |
| Demo (30) | `data/seed/suppliers_demo.json`: **3 per hub × 10 kota**, 10 ayam / 10 telur / 10 wortel, koordinat = hub + geseran tetap ±2 km | `load_demo_rows()` |
| Pemasok untuk SPPG Jakarta | **4 baris**: Prima Ayam Sejahtera Jakarta (ayam, 0,44, `none`), Telur Berkah Jakarta (telur, 0,89, `haccp`), Sayur Segar Kramat Jati (wortel, 0,77, `hygiene`), + 1 kanonik `Supplier Jakarta-1` (tanpa komoditas/koordinat) | `GET /suppliers` + DB |
| Respons `GET /suppliers` untuk akun **kepala SPPG Jakarta** | `count: 44, total: 44` — **seluruh pemasok nasional**, termasuk Medan (1.418 km), Malang (669 km), Palembang (426 km) | probe API token SPPG Head |
| Akibat di layar | filter komoditas `telur` → **10 pin** dari Medan sampai Malang; halaman Pemasok menampilkan 44 baris lintas pulau kepada SPPG Jakarta | peta Overview `Tampilkan pemasok (10)` + `/suppliers` |
| Aturan jarak | **Tidak ada sama sekali**: backend (`app/api/suppliers.py`) hanya filter `commodity`/`location`/`q`; frontend (`lib/supplier-pins.ts`) hanya komoditas + ambang zoom 6/8 | baca kode |
| Dampak koordinat pemasok ke engine | **Nol**: jarak logistik keputusan dari matriks SPPG↔SPPG (`app/core/logistics.py`, Cianjur–Jakarta 120 km). Yang dipakai engine dari baris pemasok: `reliability_score` (faktor skor SDC `app/core/scoring.py`), komoditas + eksklusi (eligibilitas) | baca kode |
| 4 pemasok keandalan rendah (dipaku tes) | Wortel Lembang Bandung 0,41 · Telur Berkah Cianjur 0,38 · **Prima Ayam Sejahtera Jakarta 0,44** · Telur Berkah Surabaya 0,35 | `tests/test_suppliers_data.py:76` |
| Alasan `/suppliers` lintas lokasi | Ruling 2026-10-14 §4: profil pemasok = data sisi **SUMBER** (boleh dibaca lintas lokasi); yang dikunci per lokasi adalah keputusan/eksklusi | `app/api/suppliers.py` docstring |

### 7.3 Masalah yang mau diperbaiki (3, semuanya terukur)
1. **Cerita demo tidak masuk akal.** SPPG Jakarta disuguhi pemasok Medan/Malang/Palembang sebagai
   "pemasok mereka" — 1.418 km dari dapur SPPG.
2. **Klaster Jakarta tipis dan tidak berjenjang.** Hanya 1 pemasok per komoditas, semuanya di dalam
   kota, tanpa pemasok pinggiran yang justru paling realistis (sayur dari Puncak/Cianjur,
   telur & ayam dari Bekasi/Tangerang). Tidak ada variasi jarak, jadi tidak ada cerita "dekat vs
   penyangga" yang bisa didemokan.
3. **Tidak ada konsep "terjangkau"** — tidak di API, tidak di UI, tidak di data. Akibatnya tidak ada
   yang bisa diuji maupun ditampilkan sebagai peringatan jujur ("pemasok ini 1.418 km dari SPPG Anda").

### 7.4 Keputusan yang perlu pemilik (DIKUNCI 2026-10-15)
| # | Pertanyaan | Keputusan pemilik | Akibat |
|---|---|---|---|
| 1 | Cakupan klaster pemasok Jakarta | **Jabodetabek + penyangga Jawa Barat ≤ ~150 km** (Bekasi, Depok, Tangerang, Bogor, Cisarua/Puncak, Karawang, Subang, Cianjur) — 10–12 pemasok demo, jarak berjenjang 0–25 / 25–60 / 60–150 km | `data/seed/suppliers_demo.json` + skema koordinat absolut (7a) |
| 2 | Nasib pemasok 9 hub lain | **Tetap 1 pemasok lokal per hub** (turun dari 3) sebagai jaring nasional monitor & SPPG kota lain; **tidak pernah** ditampilkan sebagai pemasok SPPG Jakarta | total demo turun dari 30 → 12 + 9 = 21 baris; tes `test_suppliers_data.py:56/:64` diubah sadar |
| 3 | Aturan "terjangkau" | **Ya, sebagai RELEVANSI bukan scope**: `GET /suppliers?max_distance_km=…` + default tampilan 150 km untuk SPPG; `bgn_monitor` tetap nasional; Ruling 2026-10-14 §4 tidak berubah | 7b: API + `lib/supplier-pins.ts` + halaman Pemasok |
| 4 | Jarak pemasok masuk biaya engine | **YA — pemilik ingin jarak pemasok ikut dihitung dalam biaya SDC** | **Fase tersendiri (7d)**, bukan bagian 7a–7c: mengubah skor/keputusan demo, jadi butuh tes jangkar baru + catatan ruling. Dikerjakan setelah 7c dan setelah Fase 6. |
| 5 | Urutan eksekusi | **Fase 6 dulu** (termasuk bersihkan 10 pelanggaran ruff), baru Fase 7 | Fase 6 memakai keadaan data sekarang; dokumen supplier (`docs/Schema.md` § suppliers) diperbarui lagi di 7b/7c |

### 7.4b Fase 7d — jarak pemasok sebagai faktor biaya — **SELESAI 2026-10-15**
Rancangan awal yang harus diuji ulang saat tiba: `candidate_generation`/`scoring` memakai jarak
**pemasok→SPPG** (bukan hanya matriks SPPG↔SPPG `logistics.py`), sumber jarak = koordinat `suppliers`
+ koordinat lokasi, konstanta laju transport tetap 300 Rp/km/ton. Karena ini mengubah angka
keputusan demo, syaratnya: (a) tabel dampak angka sebelum/sesudah untuk 4 kasus skrip, (b) ruling
bertanggal + alasan, (c) jangkar kanonik (4.900 kg, 3 surplus : 7 surplus) tetap hijau atau
perubahannya dinyatakan sadar, (d) fallback jelas bila pemasok tanpa koordinat (jangan menebak).

**Eksekusi (2026-10-15, bukti `docs/verification/fase-7d.md`):** keempat syarat terpenuhi.
Modul murni baru `app/core/supplier_leg.py` (haversine bersama `app/core/geo.py`, 3 desimal);
`fetch_operational_facts` mengembalikan elemen ke-7 (peta `(supplier_id, lokasi) → km`) sementara
6-tuple kontrak Task 9 tetap sah; biaya angkut = **kaki pertama + linehaul**, satu tarif 300 Rp/km/ton,
komponen SDC tetap 6 (`safe_delivered_cost.py` tidak disentuh). Jarak linehaul dan kelayakan
delivery window TIDAK berubah → eligibilitas & skor tidak bergeser. Koordinat tidak lengkap ≠ 0 km:
ditandai `supplier_coordinates_missing` / `no_supplier` dan biayanya 0, tanpa tebakan.
Tabel dampak (delta = invarian; angka absolut bergerak sedikit antar run karena residu data suite):
Cianjur→Jakarta ±14.169.953 → **±14.170.235** (+**282,00**; kaki 1,880 km),
Bogor→Jakarta ±14.975.145 → **±14.981.798** (+**6.653,07**; kaki 45,075 km); 0 kandidat berpindah
peringkat; jangkar kanonik & 4.900 kg telur utuh; 14/14 kandidat punya kaki pertama terhitung.

### 7.5 Rencana bertahap
- **7a — Data (½ hari).** Perluas skema `data/seed/suppliers_demo.json` dengan **`latitude`/`longitude`
  absolut** (opsional; `offset_index` lama tetap sah), lalu tulis klaster Jakarta menurut keputusan #1
  (nama perusahaan + alamat + kontak yang jenaka wajar, kapasitas, sertifikasi) dan sisa hub menurut
  keputusan #2. `app/seed/suppliers_demo.py`: dukung koordinat absolut + validasi (koordinat di luar
  Indonesia ditolak; **invarian baru**: setiap pemasok hub Jakarta ≤ ambang jarak dari SPPG Jakarta).
  Tes baru: jarak tiap pemasok Jakarta ≤ ambang, tidak ada nama duplikat, 3 komoditas terwakili,
  tetap deterministik + idempoten, 4 pemasok berisiko tetap ada (nilai tidak berubah).
- **7b — "Terjangkau" sebagai aturan tampilan — SELESAI 2026-10-15.** `GET /suppliers` menerima
  `max_distance_km` (+ `commodity`) dan mengembalikan `distance_km` per baris, `distance_reference`,
  serta blok `reach` (`max_distance_km`, `excluded_out_of_reach`, `excluded_unknown_distance`).
  Titik rujukan = lokasi user (peran SPPG) → hub pada filter `location=` → tidak ada; **tanpa
  rujukan, penyaring dijawab 422**, bukan diabaikan diam-diam. `lib/supplier-pins.ts` mengenal
  `reachKm`/`SUPPLIER_REACH_KM` (150), nada `far`, `isWithinReach`, `distanceLabel`, `reachLabel`,
  `supplierPinsForMap`, `supplierReachNote`, `supplierReachMeta`; peta Overview memakai penyaring
  server (peran SPPG), halaman Pemasok memakai daftar penuh + kolom Jarak + penyaring pilihan
  pengguna. Tes: 7 backend baru + 14 frontend baru. **Keputusan operasional**: jarak dihitung
  SEPENUHNYA di server (satu implementasi haversine di `app/core/geo.py`); UI hanya membandingkan
  `distance_km` dengan ambang, jadi angka di layar tidak bisa berbeda dari angka di respons.
- **7c — Bukti — SELESAI 2026-10-15.** Lihat `docs/verification/fase-7.md`: layar SPPG Jakarta
  (4 pin telur dalam jangkauan dari 6, catatan "4 dari 6 … 2 di luar jangkauan tidak dipasang")
  vs layar `bgn_monitor` (6 pemasok telur nasional, tanpa ambang), tabel Pemasok SPPG
  (35 baris, 13 berlabel "di luar jangkauan", penyaring → 22 baris, kembali 35) vs tabel monitor
  (35 baris, kolom Jarak "—", tanpa penyaring), plus gate pytest/ruff/vitest/tsc/lint/build.
- **7d — Jarak pemasok masuk biaya SDC — SELESAI 2026-10-15.** Modul murni
  `backend/app/core/supplier_leg.py`; `fetch_operational_facts` menambah elemen ke-7;
  biaya angkut = kaki pertama + linehaul di `app/services/recommendation_service.py`;
  panel biaya Decision & Evidence menampilkan pecahannya bila ada. Bukti:
  `docs/verification/fase-7d.md`; ruling: `docs/ruling-2026-10-15-jarak-pemasok-biaya.md`;
  skrip dampak angka: `backend/scripts/verifikasi_fase7d.py`.

### 7.6 Berkas & tes yang tersentuh (blast radius, sudah diperiksa)
- Data: `data/seed/suppliers_demo.json` (30 baris), `backend/app/seed/suppliers_demo.py`.
- **Kanonik 14 JANGAN disentuh** — ia terikat 14 kutipan harga (`quotes == 14`) dan acuan PIHPS 10 kota.
- Tes yang memaku jumlah memakai `len(load_demo_rows())` (`test_suppliers_api.py:29`,
  `test_sprint1_contract_reconciliation.py:72`) → selamat selama berkas tetap satu sumber kebenaran;
  yang **pecah sadar**: `test_suppliers_data.py:56` (30 baris), `:64` (10 hub), `:76` (4 pemasok berisiko).
- Dokumen: `docs/Schema.md` (§ suppliers), `docs/design.md` (legenda + aturan jarak), `docs/PRD.md`
  (bila keputusan #3 diambil), `TODO.md`, `memory/global/decisions.md`.

### 7.7 Risiko
| Risiko | Dampak | Mitigasi |
|---|---|---|
| Klaster Jakarta terlalu padat | Pin menumpuk, peta tidak terbaca | batas 10–12 pemasok + ambang zoom 6/8 yang sudah ada; label baru di zoom ≥8 |
| Pemasok kota lain dihapus total | Peta nasional kosong, SPPG lain tanpa pemasok, tes 10 kota pecah | keputusan #2 Opsi A (1 per hub) |
| Nilai keandalan berubah | Skor SDC demo bergeser, cerita "pemasok berisiko" hilang | pertahankan 4 pemasok berisiko (nama/kota boleh pindah, nilai tetap) |
| Filter jarak disalahartikan sebagai scope | Monitor kehilangan pandangan nasional | default `bgn_monitor` tetap nasional + dokumentasi "relevansi, bukan scope" |

### 7.8 Urutan & perkiraan
**7a → 7b → 7c SELESAI** (7a 2026-10-15, 7b+7c 2026-10-15), dijalankan **setelah Fase 6** (pilihan pemilik 2026-10-15 di tabel §7.4: Fase 6
dulu, baru Fase 7 — supaya bersih-bersih `ruff` dan sinkronisasi dokumen selesai lebih dulu, dan
dokumen pemasok diperbarui lagi di 7b dengan keadaan data yang sudah final). Perkiraan
**±1–1½ hari kerja bertahap**.
