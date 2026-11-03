# RENCANA REMEDIASI — AUDIT 2026-10-29

**Sumber temuan:** `docs/audit/AUDIT_2026-10-29_FULLSYSTEM.md` (AUD-001 … AUD-050)
**Baseline yang diaudit:** branch `feature/db-modes-demo-coverage`, commit `9019eb1`, working tree kotor (146 entri)
**Sifat dokumen:** rencana, bukan laporan eksekusi. Status pengerjaan hidup di dokumen terpisah
(`audit-2026-10-29-remediation-report.md`) supaya teks audit aslinya tidak tertimpa.

---

## 0. Aturan kerja yang berlaku untuk SEMUA langkah

1. **Satu langkah = satu temuan (atau satu akar masalah).** Tes merah dulu (kontrak batas/edge),
   patch, tes hijau, regresi area itu, lalu **ukur ulang angka live** sebelum menyatakan selesai.
2. **Jangan menyentuh DB demo** untuk uji tulis. Pakai DB sekali-pakai:
   `createdb mealchain_fix_<step>` → `alembic upgrade head` → seed → uji → `dropdb`.
   DB demo `mealchain` hanya boleh `SELECT`.
3. **Jangan mengubah expected value tes agar lulus.** Kalau tes lama bertentangan dengan aturan baru,
   perbarui tes karena aturannya berubah — dan sebutkan di report.
4. **Status `Fixed` bukan bukti.** Hanya `Verified` yang ditulis setelah ada tes/ukur ulang.
5. **Rahasia tidak pernah dicetak** — termasuk saat memperbaiki AUD-004.
6. Setiap langkah yang mengubah perilaku produk **wajib punya keputusan owner** lebih dulu
   (daftar di §2). Tanpa itu, langkah berhenti di "usulan patch + tes merah".

---

## 1. Peta cakupan — setiap AUD punya langkah

| AUD | Langkah | AUD | Langkah |
|---|---|---|---|
| 001 | A1 | 026 | A5 |
| 002 | A4 | 027 | B5 |
| 003 | A4 | 028 | C4 |
| 004 | A3 | 029 | C5 |
| 005 | A2 | 030 | C5 |
| 006 | B10 | 031 | C5 |
| 007 | B1 | 032 | C6 |
| 008 | B2 | 033 | C6 |
| 009 | B3 | 034 | C6 |
| 010 | A5 | 035 | C7 |
| 011 | B4 | 036 | C7 |
| 012 | B5 | 037 | C6 |
| 013 | B6 | 038 | D1 |
| 014 | C1 | 039 | D1 |
| 015 | C2 | 040 | C7 |
| 016 | B7 | 041 | C8 |
| 017 | B9 | 042 | C8 |
| 018 | B11 | 043 | C8 |
| 019 | B8 | 044 | D1 |
| 020 | B6 | 045 | D1 |
| 021 | B7 | 046 | D1 |
| 022 | B7 | 047 | D1 |
| 023 | C3 | 048 | D1 |
| 024 | C3 | 049 | D1 |
| 025 | C6 | 050 | D1 |

Tidak ada temuan yang tidak punya langkah. Langkah yang menutup >1 temuan selalu karena **satu akar
masalah** (contoh: AUD-002/003 = privilege DB; AUD-012/027 = generasi ledger).

---

## 2. Keputusan owner yang memblokir (putuskan sebelum langkah terkait)

| # | Pertanyaan | Memblokir | Default bila owner diam |
|---|---|---|---|
| O1 | Apakah "Effective Price per Accepted Kg" jadi metrik KPI resmi ke-8? | B6 | Pertahankan 7 metrik (metrik ke-8 dicabut dari respons) karena kontrak+tes+dokumen sudah 7 |
| O2 | Apakah `bgn_monitor` tetap boleh mengelola pengguna (`/admin/*`)? | B10 | Pertahankan keputusan 2026-10-17, tetapi **cabut** peran itu dari token layanan agen |
| O3 | Apakah keputusan `verifier_flagged` boleh di-approve dan dieksekusi? | B8 (regresi) | Pertahankan perilaku sekarang (bersyarat catatan), dokumentasikan sebagai keputusan |
| O4 | Apakah `sppg_head`/`sppg_nutritionist` boleh mulai/akhiri sesi demo global? | C6 | Batasi ke peran nasional (`bgn_monitor`) |
| O5 | `GET /batches` lintas lokasi: pisah endpoint panel chaos vs endpoint biasa? | C6 | Biarkan (disengaja), tambahkan penanda `scope=panel` di respons |
| O6 | Label periode: "Hari ini" atau "Hari ini (jangkar simulasi 8 Okt)"? | B6 | Tampilkan jangkar di label |
| O7 | CCP masuk lingkup produk atau tidak? | D1 | Nyatakan di luar lingkup; hapus klaim CCP dari dokumen |
| O8 | Host permanen backend untuk jembatan Joule (VPS/CF URL tetap)? | A1 | Nonaktifkan jembatan dari demo |
| O9 | Siapa merotasi kunci AWS/SAP/InferHub dan kapan? | A3 | Rotasi sebelum demo berikutnya |

---

## 3. FASE A — Containment (P0). Tujuan: tidak ada klaim/kredensial/privilege yang bisa
dimanfaatkan atau menyesatkan selama demo.

### A1 · Putus klaim integrasi Joule — AUD-001 · Effort: S · Butuh: O8
- **Lokasi:** environment Cloud Foundry `mealchain-joule-bridge-*`; `sap-joule/a2a_server/server.py`.
- **Perubahan:** `MEALCHAIN_API_URL` → host milik sendiri (bukan `*.lhr.life`/`*.trycloudflare.com`);
  tambah auth token di bridge; `CORS_ORIGINS` eksplisit; `/health` melaporkan `git commit` + `dataset`.
- **Acceptance:** (a) `/health.dataset.decisions` == `select count(*) from decisions` di DB yang dipakai
  UI; (b) `curl` tanpa token → 401; (c) `grep -r "lhr.life\|trycloudflare" ` di repo+env = 0 hasil.
- **Regresi:** demo Joule (bila dipakai) harus tetap menjawab `message/send` dengan `messageId`.
- **Catatan:** bila O8 belum diputuskan, langkah minimal = **hapus panel/diagram "SAP live"** dan
  tandai bridge sebagai "belum terhubung" di UI.

### A2 · Tutup kebocoran kredensial demo — AUD-005 (+ bagian kredensial AUD-032) · Effort: S
- **Lokasi:** `backend/app/api/auth.py:154-181`; `.env` (`DEMO_LOGIN_AUTOFILL`); `docker-compose.yml`.
- **Perubahan:** `DEMO_LOGIN_AUTOFILL=false` sebagai default; endpoint demo-login hanya menjawab bila
  request dari loopback, atau hapus endpoint dan ganti daftar akun **tanpa** sandi.
- **Acceptance:** `/auth/demo-login` → `{enabled:false,accounts:[]}` dengan flag mati; dengan flag nyala
  + `DEMO_MODE=false` tetap `false`; tes regresi dua kombinasi flag.
- **Regresi:** layar login demo tidak boleh kehilangan tombol akun (pakai daftar tanpa sandi yang sudah
  ada di `frontend/lib/demo-accounts.ts`).

### A3 · Rotasi kunci yang pernah ter-commit — AUD-004 · Effort: M (aksi owner, bukan kode) · Butuh: O9
- **Kunci:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_BEARER_TOKEN_BEDROCK`,
  `SAP_AI_CORE_CLIENT_SECRET`, `INFERHUB_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`, `SIGNING_KEY_HEX`.
- **Acceptance:** kunci lama non-aktif (`aws sts get-caller-identity` gagal / AI Core 401 / InferHub 401);
  catatan rotasi bertanggal di `TODO.md`; `gitleaks` bersih pada riwayat **baru** (riwayat lama tetap
  tercatat sebagai risiko historis).
- **Regresi:** setelah `JWT_SECRET` berubah, semua sesi lama invalid — jalankan ulang smoke login 3 peran.

### A4 · Least privilege DB + tutup pintu maintenance ledger — AUD-002, AUD-003 · Effort: M
- **Lokasi:** `scripts/siapkan_role_app.py`; `docker-compose.yml:47-51`; migrasi `042`/`043`.
- **Perubahan:** buat `mealchain_app_login` (warisi `mealchain_app`, bukan `mealchain_migrator`); set
  `APP_DATABASE_URL`; migrasi lewat `MIGRATION_DATABASE_URL`; `prevent_ledger_mutation` hanya mengizinkan
  anggota `mealchain_migrator` **dan** bukan superuser.
- **Acceptance:** (a) `select current_user` dari backend = `mealchain_app_login`;
  (b) `has_table_privilege(...,'ledger_blocks','UPDATE') = false`;
  (c) sebagai role aplikasi, `SET LOCAL mealchain.ledger_maintenance='on'` + `UPDATE` **tetap ditolak**;
  (d) suite backend hijau dengan DSN baru.
- **Regresi:** tinggi — semua jalur tulis harus dicek (seed, demo reset, migrasi). Jalankan suite penuh
  di DB sekali-pakai sebelum menyentuh DB demo.

### A5 · Data demo patuh gerbangnya sendiri — AUD-010, AUD-026 · Effort: M
- **Lokasi:** `backend/app/seed/demo_template.py:567-592`; relasi PO↔decision.
- **Perubahan:** (a) setiap keputusan `executed` diberi ≥2 approval nyata dan batch sumber `pass` +
  belum kedaluwarsa pada jangkar sesi; (b) PO tanpa keputusan ditandai `origin='seed_template'` dan
  dipisahkan di UI/API, atau dihubungkan ke keputusan.
- **Acceptance:** query invarian = 0 baris:
  `executed` tanpa approval · `executed` dengan batch `fail`/`usable_until < anchor` ·
  PO `decision_id IS NULL AND origin <> 'seed_template'`; `test_invarian_riwayat_demo` hijau.
- **Regresi:** angka KPI demo bisa bergeser — catat sebelum/sesudah di report.

**Definition of Done Fase A:** tidak ada kredensial demo terbuka, tidak ada kunci historis aktif,
backend bukan superuser, pintu ledger tertutup untuk role aplikasi, data demo tidak melanggar gerbang,
dan tidak ada klaim "SAP live" yang tidak didukung.

---

## 4. FASE B — Integritas & keselamatan (P1)

### B1 · Atribusi interval suhu — AUD-007 · Effort: S · Paling murah, dampak keselamatan langsung
- **Lokasi:** `backend/app/core/temperature.py:170-174`.
- **Perubahan:** nilai `curr` juga dinilai (atribusikan interval ke `curr`, atau tambahkan penalti
  eksplisit untuk sampel terakhir di luar rentang). Jangan mengarang ambang baru.
- **Acceptance:** `[5,5,20]` → `outside_minutes > 0`; `[20,20,5]` → tetap `120`; `[5]` →
  `evidence_insufficient`; tes `test_temperature.py` (2 yang merah) hijau.
- **Regresi:** freshness/safety skor batch demo bisa turun → cek ulang 133 batch, laporkan distribusi
  status sebelum/sesudah.

### B2 · `evaluation_time` tidak lagi ditentukan pemanggil — AUD-008 · Effort: M
- **Lokasi:** `backend/app/core/safety.py:154-170`; `backend/app/api/safety.py:37,62-70`.
- **Perubahan:** default = jam server (bukan `None`); tolak nilai jauh di masa depan/lampau; pisahkan
  endpoint evaluasi (baca) dari endpoint yang menulis `batch.safety_status`.
- **Acceptance:** request tanpa `evaluation_time` = verdict jam server; `evaluation_time` +1 hari → 422;
  log umur 2 hari tanpa parameter → `needs_verification`.
- **Regresi:** Event 1–3 yang mengirim `evaluation_time` eksplisit harus tetap jalan.

### B3 · Event 3 pakai kebijakan per komoditas — AUD-009 · Effort: M
- **Lokasi:** `backend/app/services/event3_service.py:151-158`.
- **Perubahan:** `batch_policy_from(commodity)` menggantikan `evaluate_safety(0.0, 8.0)`; jangan menulis
  `batch.safety_status` dari jalur berkebijakan default.
- **Acceptance:** beras ambient → `pass`; ayam 9,5 °C → `fail`; tes per komoditas (4 komoditas).
- **Regresi:** 18 `needs_verification` + 3 `fail` di DB demo bisa berubah — dokumentasikan.

### B4 · `init-demo` idempoten & transaksional — AUD-011 · Effort: M
- **Lokasi:** `backend/app/db_mode.py:282-293`; `backend/app/seed/reference.py:33-40`.
- **Perubahan:** hapus+seed dalam satu transaksi (atau generasi baru yang ditukar setelah sukses);
  lookup kanonik by natural key, bukan hanya `stable_uuid`.
- **Acceptance:** `init-demo` 2× → exit 0, row count identik; simulasi gagal di tengah → 0 baris hilang;
  `commodities_name_key` tidak pernah muncul lagi.
- **Regresi:** tinggi — dipakai tombol "Siapkan data demo".

### B5 · Generasi ledger di semua jalur hapus — AUD-012, AUD-027 · Effort: M
- **Lokasi:** `db_mode.py:368-388`; `timeseries.py:1107-1112`; `demo_purge.py:77-80`.
- **Perubahan:** satu helper `hapus_entitas_berblok()` yang selalu `bump_generation`; dipakai ketiga jalur.
- **Acceptance:** setelah reset/purge/rebuild: `orphan_blocks` generasi aktif = 0; `/ledger/verify` tanpa
  `coverage_warning`; tes regresi 3 jalur.
- **Regresi:** archive generation bertambah — UI integritas harus menampilkan generasi aktif dengan benar.

### B6 · KPI: satu daftar metrik, label periode jujur — AUD-013, AUD-020 · Effort: M · Butuh: O1, O6
- **Perubahan:** putuskan metrik ke-8; satukan daftar di satu konstanta; `kamus-kpi`, tes, dan UI
  mengikuti. Perbaiki label periode agar menyebut jangkar simulasi.
- **Acceptance:** `len(metrics)` sama di kode/tes/dokumen; 3 tes merah (`test_kpi_api`×2, `test_kpi`,
  `test_hari_ini`×2) hijau; label di UI memuat jangkar.
- **Catatan AUD-020:** mengisi `no_data` adalah keputusan **data/demo**, bukan bug — pisahkan dari
  perbaikan kontrak; jangan mengubah `no_data` menjadi 0.

### B7 · Rekonsiliasi PO & SDC — AUD-016, AUD-021, AUD-022 · Effort: L · Butuh: keputusan penamaan field
- **Lokasi:** `backend/app/seed/jakarta_lengkap.py:733-744`; `backend/app/services/po_document.py`;
  `backend/app/core/commercial_cost.py`; `_harga_satuan_invoice`.
- **Perubahan:** dua field bernama jelas (`quoted_unit_price` vs `billed_unit_price`) + `invoice_total`
  konsisten dengan `billed`; migrasi/backfill 4 PO legacy; SDC tanpa breakdown → tolak saat dibuat,
  bukan 422 di hilir.
- **Acceptance:** untuk setiap PO `invoice_total == billed × qty` ±0,01; 41 keputusan ber-breakdown
  tetap Δ0,00; `test_po_invoice_commercial` hijau; keputusan `5e969ff1`-jenis tidak lagi 422.
- **Regresi:** panel PO + invoice + settlement; cek `variance_idr`/`variance_pct`.

### B8 · Verifier menangkap executed-tanpa-ledger — AUD-019 · Effort: S
- **Lokasi:** `agent/verifier_checks.py:454-461`.
- **Perubahan:** keputusan berstatus `executed` wajib punya blok; hapus cabang mati `:466-472`.
- **Acceptance:** `test_agent_verifier_independence.py:463` hijau; kasus "executed, 0 blok" → check gagal.

### B9 · Routing model per agen — AUD-017 · Effort: M
- **Lokasi:** `backend/app/core/model_registry.py:123-126`.
- **Perubahan:** `AGENTCORE_RUNTIME_ARN` tidak lagi dipakai sebagai slot pertama LLM generik;
  rantai forecast dimulai dari model forecast.
- **Acceptance:** `get_agent_chain("forecast")[0]` = model yang diniatkan; tes per rantai (supervisor,
  verifier, forecast).
- **Catatan:** ini mengubah perilaku runtime → butuh smoke `-m live` terpisah (berbayar, izin owner).

### B10 · Otorisasi admin & token layanan — AUD-006 · Effort: M · Butuh: O2
- **Perubahan:** minimal — cabut peran `bgn_monitor` dari `MEALCHAIN_API_TOKEN` (token layanan khusus);
  ideal — tambah peran admin di skema.
- **Acceptance:** matriks role×endpoint: `bgn_monitor` 403 di semua metode tulis `admin/*` (bila O2
  memilih pemisahan); token layanan tidak bisa mengubah pengguna.
- **Regresi:** `/admin/*` dipakai panel pengaturan — sesuaikan UI.

### B11 · Dependensi rentan — AUD-018 · Effort: L
- **Perubahan:** upgrade bertahap satu paket per commit: `next` 14.2.x patch terakhir → 15 (terpisah),
  `pyjwt`, `starlette`, `maplibre-gl`; jangan `npm audit fix --force`.
- **Acceptance:** `npm audit --omit=dev` tanpa critical/high; `pip-audit` tanpa advisory yang ada fix;
  suite FE+BE hijau; build produksi sukses.

**Definition of Done Fase B:** tes suhu/safety hijau, data demo tidak melanggar invarian, generasi ledger
bersih, kontrak KPI tunggal, PO/SDC rekonsiliasi, verifier menangkap kasus negatif, routing model benar.

---

## 5. FASE C — Gate & kualitas (P2)

### C1 · Gate statis hijau — AUD-014 · Effort: S
`ruff check .` → 0 (12 error: I001×4, F401×3, E501×3, F811×1); `tsconfig.json` beri `target`
→ `tsc --noEmit` 0 (4×TS2802). Acceptance: dua perintah exit 0; ditambahkan ke CI.

### C2 · Baseline suite hijau — AUD-015 · Effort: L
Buat DB uji bersih (`migrate` + seed khusus tes, **bukan** klon demo), kunci daftar kegagalan yang
diterima, tutup satu per satu (mulai dari 3 error `decisions_pkey`). Acceptance: `pytest` exit 0 pada DB
bersih; jumlah skip tercatat + beralasan; hasil dilaporkan per berkas.

### C3 · Drift & rollback migrasi — AUD-023, AUD-024 · Effort: S/M
Deklarasikan `ix_batch_receipts_verdict` di ORM (atau hapus dari migrasi bila tak dipakai — cek
`idx_scan=6`); dokumentasikan migrasi tak-reversible + sediakan jalur data sebelum constraint 023.
Acceptance: `alembic check` exit 0; `downgrade` terdokumentasi (bukan harus sukses ke `base`).

### C4 · Redam polling — AUD-028 · Effort: M
`/balance/map` 4 query × 5 s tanpa gating tab → satukan + gating; target <30 req/menit idle.
Acceptance: hitung ulang request/60 s idle (sekarang 148/mnt) dan lampirkan angkanya.

### C5 · UX kegagalan — AUD-029, AUD-030, AUD-031 · Effort: M
Tambah `app/error.tsx`, `global-error.tsx`, `not-found.tsx`; state `loading/error` eksplisit (jangan
tampilkan 0 saat gagal — terukur 0 → 17); konfirmasi "Akhiri sesi" + "Muat Demo (replace)".
Acceptance: matikan backend → app menampilkan error state, bukan putih/0; dua tombol meminta konfirmasi.

### C6 · Constraint, scope, sesi, urutan gate — AUD-025, AUD-032, AUD-033, AUD-034, AUD-037 · Effort: M · Butuh: O4, O5
CHECK pada kolom status; scope endpoint purge/rebuild demo; start-sesi dibatasi peran; `jti`+revoke
(minimal: logout menghapus server-side); urutkan gate sesi **setelah** otorisasi agar 403 tidak menjadi 409.
Acceptance: matriks role×endpoint diperbarui dengan angka nyata; uji negatif CHECK; bgn_monitor menerima
403 (bukan 409) pada endpoint tulis tanpa sesi.

### C7 · Label SAP, observability, artefak API — AUD-035, AUD-036, AUD-040 · Effort: M
`X-Data-Source` di semua respons data SAP; request-id + structured log + `/health` versi/commit;
regenerasi `openapi.json` di CI (atau hapus artefak ter-commit); hapus rujukan `core/observability.py`
yang tidak ada. Acceptance: grep panel integrasi tidak menunjuk file hilang; satu request punya id yang
muncul di log; `test_openapi_artifact_drift` hijau.

### C8 · Dead code, a11y, artefak berkas — AUD-041, AUD-042, AUD-043 · Effort: M
Putuskan 14 komponen mati (±2.739 baris): hubungkan atau hapus (+tesnya); nama aksesibel combobox,
`aria-selected` benar, fokus awal dialog; buang byte NUL di `lib/api.ts:1142`.
Acceptance: `grep -c $'\0'` = 0; axe/lighthouse tanpa violation baru pada 3 panel utama; jumlah tes FE
turun hanya untuk komponen yang benar-benar dihapus.

---

## 6. FASE D — P3 (perapian, tidak memblokir)

| Langkah | Temuan | Isi | Acceptance |
|---|---|---|---|
| D1 | AUD-038 | Batas atas jendela feed (`created_at < now`) | tes: baris masa depan tidak masuk feed |
| D1 | AUD-039 | Nyatakan artefak data masa depan (520 supply / 580 price / 240 demand) di dokumen; atau buang dari seed | snapshot menyebutnya eksplisit |
| D1 | AUD-044 | Rate limit per-IP lintas akun + backend bersama (bukan in-memory) bila >1 worker | uji 2 akun berbeda dari 1 IP |
| D1 | AUD-045 | Jepit `JWT_ALGORITHM` ke daftar sah; tambah `aud`/`iss` | alg asing ditolak saat start |
| D1 | AUD-046 | Hapus 2 blok `uji_generasi` dari DB demo | `select count(*) where action='uji_generasi'` = 0 |
| D1 | AUD-047 | Arsipkan/hapus 105 DB `mealchain_*` (4.940 MB) | daftar DB tinggal yang dipakai |
| D1 | AUD-048 | Anchor ledger menutup > tinggi 978 | anchor = head generation aktif |
| D1 | AUD-049 | Nyatakan CCP di luar lingkup atau implementasikan | dokumen konsisten |
| D1 | AUD-050 | Pisahkan compose prod (tanpa bind mount/`next dev`), CI secret-scan + build + rollback | `docker compose -f docker-compose.prod.yml config` tanpa mount dev |

---

## 7. Urutan eksekusi yang disarankan

```
A2 → A1 → A3 → A4 → A5        (containment; A4 butuh O8/O9/O2 lebih dulu)
   ↓
B1 → B2 → B3                  (keselamatan; B1 paling murah, kerjakan lebih dulu)
   ↓
B4 → B5 → B8 → B6 → B7        (integritas data & angka)
   ↓
B9 → B10 → B11                (runtime & dependensi)
   ↓
C1 → C3 → C2 → C4 → C5 → C6 → C7 → C8
   ↓
D1
```

**Alasan urutan:** A2/A1/A3 memutus paparan dan klaim palsu sebelum apa pun ditunjukkan. A4 harus
sebelum B-series diverifikasi, karena bukti "ledger aman" baru sah setelah role aplikasi bukan superuser.
B1–B3 mendahului B4–B7 karena menyentuh keselamatan dan perbaikannya kecil. C1/C3 didahulukan dari C2
supaya suite berjalan di atas kode yang lint/typecheck-nya bersih (kalau tidak, kegagalan alat bercampur
dengan kegagalan logika).

---

## 8. Definition of Done keseluruhan

Rencana ini selesai bila **semua** terpenuhi:

1. Semua AUD-001…050 berstatus `Verified` atau `Accepted risk` **dengan alasan tertulis** (tidak ada yang
   hilang diam-diam).
2. Gate: `pytest` exit 0 (DB bersih), `ruff` 0, `tsc` 0, `next lint` 0, `alembic check` 0, `vitest` 0.
3. `current_user` backend = `mealchain_app_login`; trigger ledger menolak UPDATE untuk role itu.
4. `/ledger/verify`: hash 100 % cocok, `orphan_blocks` generasi aktif = 0, tanpa `coverage_warning`.
5. KPI: satu daftar metrik; UI = API = hitung ulang SQL; label periode menyebut jangkar.
6. Data demo: 0 pelanggaran invarian (executed tanpa approval, executed di atas batch fail/expired,
   PO tanpa relasi).
7. `/health` setiap komponen melaporkan commit + dataset; jembatan Joule menunjuk host sendiri.
8. Kunci hasil AUD-004 terbukti non-aktif + catatan rotasi bertanggal.
9. Dokumen (`Architecture.md`, `Schema.md`, `kamus-kpi`, `state-snapshot`) konsisten dengan kode.
10. Laporan eksekusi terpisah ada, dengan angka sebelum→sesudah per langkah.

---

## 9. Risiko regresi per fase

| Fase | Risiko utama | Mitigasi |
|---|---|---|
| A4 | Semua jalur tulis patah karena privilege baru | uji di DB sekali-pakai dulu; commit terpisah; rollback = kembalikan DSN |
| A5 / B4 | Angka KPI demo bergeser, screenshot juri basi | catat sebelum/sesudah; regenerasi snapshot |
| B1 / B3 | Distribusi status batch berubah (banyak jadi `needs_verification`) | laporkan delta; jangan longgarkan ambang untuk "merapikan" |
| B7 | Panel PO/invoice berubah bentuk | tambah field, jangan ganti nama lama sampai UI diperbarui |
| B11 | Upgrade Next memecah App Router/build exFAT | satu paket per commit; build di root, bukan folder output |
| C2 | Suite tetap merah karena fixture | kunci daftar baseline, bukan menunda |

---

## 10. Yang TIDAK termasuk rencana ini

- Perubahan aturan bisnis baru (ambang suhu, definisi KPI, kuorum approval) — itu keputusan produk (O1–O7).
- Load test, restore/DR teruji, dan uji model berbayar — perlu izin, anggaran, dan environment terpisah.
- Uji IDOR tulis end-to-end pada DB demo — hanya di stack terisolasi.
- Perbaikan estetika UI di luar temuan a11y/kegagalan yang terdaftar.
