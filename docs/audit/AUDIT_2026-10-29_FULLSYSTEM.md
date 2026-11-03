# AUDIT MENYELURUH — MEALCHAIN GUARDIAN

**Tanggal audit:** 2026-10-29 (pengambilan angka 11:23–11:45 WIB; beberapa bukti diambil sub-reviewer 11:23–11:36)
**Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian`
**Branch:** `feature/db-modes-demo-coverage`
**Commit:** `9019eb1` — `docs(memory): catat Ringkasan Pemasok jadi KPI strip (Fase 34 / Ronde 56-58, 61)`
**Working tree:** **KOTOR** — 97 modified, 45 untracked, sisanya deleted/renamed = **146 entri**
**Stack terukur:** backend `:8000`, frontend `:3010`, Postgres `:15432` (DB demo `mealchain`), mock-sap `:8001`, stack terpisah `mcg0896-*` (`:18200/:13210/:25432`)

> **Batas penting:** audit ini menilai **working tree yang belum di-commit**, bukan rilis. 30 kegagalan
> suite dan beberapa temuan (KPI 8-vs-7, openapi drift) berasal dari pekerjaan yang sedang berjalan di
> branch ini, bukan dari commit `9019eb1` semata.
>
> **Level bukti** yang dipakai: **S** statis (kode/konfigurasi), **U** uji otomatis, **R** runtime HTTP,
> **D** database, **B** browser. Temuan tanpa level = hipotesis dan ditandai demikian.

---

## A. EXECUTIVE SUMMARY

### Kondisi umum

Ini bukan proyek yang "hanya tampak jalan". Lapisan yang biasanya paling rapuh di proyek hackathon —
**otorisasi per lokasi, empat-mata approval, gerbang keselamatan, dan integritas ledger** — di sini
benar-benar ditegakkan dan bisa dibuktikan:

| Kontrol | Bukti terukur | Status |
|---|---|---|
| Autentikasi | 12/12 rute privat → 401 tanpa token; `/docs`,`/redoc`,`/openapi.json` → 404 | **PASS** (R) |
| Cakupan lokasi (baca) | sppg_head Jakarta melihat 24 keputusan (semua target Jakarta), bgn_monitor 49 | **PASS** (R,D) |
| IDOR lintas lokasi | 7 sub-resource keputusan milik Surabaya → **403** untuk sppg_head Jakarta | **PASS** (R) |
| RBAC tulis | `PATCH /admin/users` → sppg_head 403, sppg_nutritionist 403 | **PASS** (R) |
| Empat mata | unique index + penolakan akun yang sama dua kali | **PASS** (S,U) |
| Revalidasi saat eksekusi | safety batch sumber dicek ulang + sidik bukti + tolak PO ganda | **PASS** (S) |
| Uang | semua kolom biaya `numeric(10,2)/(12,2)`, tidak ada float | **PASS** (D) |
| Hash-chain ledger | 3.841/3.841 blok cocok saat dihitung ulang di luar aplikasi | **PASS** (D) |

Tetapi ada **tiga kelas masalah** yang membuat sistem belum layak disebut siap:

1. **Batas kepercayaan angka jebol di lapisan data demo.** Empat keputusan berstatus `executed`
   padahal batch sumbernya kini `fail`/kedaluwarsa, satu di antaranya `executed` dengan **0 approval**,
   dan 12 dari 17 PO tidak terhubung ke keputusan mana pun. Mesin gerbangnya benar; **data yang
   disajikan tidak mematuhi gerbang itu**.
2. **Dua kontrol yang dirancang baik tidak diterapkan.** Aplikasi berjalan sebagai **superuser
   Postgres** (`APP_DATABASE_URL` kosong) sehingga pintu maintenance ledger terbuka dari koneksi
   aplikasi sendiri — saya membuktikannya dengan `UPDATE` yang berhasil (lalu rollback). Role
   least-privilege `mealchain_app` sudah ada di DB tapi tidak dipakai.
3. **Klaim integrasi melampaui bukti.** Jembatan SAP Joule/A2A **hidup** dan menjawab, tetapi
   melayani dataset **bukan dari DB repo ini** (11 keputusan/50 batch vs 49/133) lewat tunnel publik
   `lhr.life`, tanpa autentikasi. Adapter SAP nyata tidak dipanggil siapa pun; kontainer `mock-sap`
   hanya punya `/health`.

### Status kesiapan (dipisah, tidak digabung)

| Tahap | Verdict | Alasan berbasis bukti |
|---|---|---|
| **Demo readiness** | **CONDITIONAL (siap dengan syarat)** | Stack naik sehat, login/scope/safety gate bekerja, ledger valid. **Syarat:** (a) jangan tampilkan jembatan Joule sebagai "SAP live"; (b) KPI strip 5/8 `no_data` harus diisi atau disembunyikan; (c) 30 tes merah harus dijelaskan sebelum juri menanyakannya; (d) jangan mengklaim ledger "tamper-proof" tanpa menyebut batasnya. |
| **Staging readiness** | **NOT READY** | Gate statis merah (ruff 12, tsc 4), `alembic check` gagal, 30 tes gagal, tidak ada error boundary, polling 148 req/menit saat idle. |
| **Production readiness** | **NOT READY** | Aplikasi = superuser DB; rahasia AWS/SAP pernah ter-commit di riwayat; token demo terbuka tanpa auth; tidak ada observability (0 request-id, 0 alarm); tidak ada backup/restore teruji; CI tanpa secret-scan/build/deploy. |

### Ruang lingkup & batas

Diperiksa: 36 modul API (90 rute, 40 di antaranya tulis), 18 model / 25 tabel, 39 migrasi, 311 berkas
tes backend, 468 berkas TS/TSX frontend, `agent/` (9 entitas LLM), `sap-joule/`, compose dev+prod,
konfigurasi AWS/AgentCore, dan dokumen arsitektur.

**Tidak** diperiksa/dijalankan: panggilan model berbayar (Bedrock/Inferhub/SAP AI Core) — nol panggilan;
load test; restore/DR; render viewport 375/768 px; pengujian dengan pembaca layar; invoke AgentCore
Runtime terkini; destination/DA di tenant Joule (butuh login SSO manusia); ACL Windows pada berkas
rahasia.

---

## B. MATRIKS CAKUPAN

| Area | Cakupan pemeriksaan | Status | Bukti utama | Kesenjangan |
|---|---|---|---|---|
| Inventaris & baseline | commit, tree, modul, rute, model, migrasi, tes | **PASS** | §A metadata; 90 rute / 25 tabel / 39 migrasi / 311 berkas tes | — |
| Keamanan authn | JWT, klaim, expiry, alg, 401 | **PASS** | 12/12 401; `alg=none` & ttd palsu → 401 | `exp` runtime tidak diuji dgn secret asli |
| Keamanan authz | role × lokasi × objek (baca) | **PASS** | 6/6 endpoint `{location}` → 403; 7/7 sub-keputusan → 403 | IDOR **tulis** (approve/execute/receipt) tidak dieksekusi |
| Keamanan authz (tulis) | role pada aksi mutasi | **PARTIAL** | PATCH /admin/users: sppg 403, bgn_monitor lolos | Uji tulis penuh dibatasi mode read-only |
| Rahasia | working tree + riwayat git | **FAIL** | `.env` ter-commit `c4d22b3`, dihapus `8f95c98` | Rotasi belum terbukti |
| Dependensi | pip-audit, npm audit | **FAIL** | BE 30 advisory/6 paket; FE 12 advisory (4 critical) | Fix semver-major tidak diterapkan (benar) |
| Business logic safety | temperature, freshness, safety gate | **FAIL** | `temperature.py:170-174`; `event3_service.py:151-158` | CCP tidak ada di kode (bukan bug) |
| SDC & numerik | hitung ulang independen | **PASS** | 4 keputusan Δ=0,00; mean 5 = 14.816.828,31 = API | Estimasi KPI tidak diaudit |
| KPI | 8 metrik + periode + no_data | **PARTIAL** | 8/8 nilai cocok saat dihitung ulang; **tapi kontrak 7** | Definisi produk belum final |
| State machine & approval | transisi, kuorum, kedaluwarsa | **PASS** (kode) / **FAIL** (data) | `actions.py` benar; data demo melanggar invarian | Uji tulis end-to-end tidak dijalankan |
| Ledger | hash-chain, trigger, privilege | **PARTIAL** | 3.841/3.841 hash cocok; trigger menolak UPDATE/DELETE | Pintu maintenance terbuka via superuser |
| Migrasi & drift | head tunggal, `alembic check`, downgrade | **FAIL** | drift `ix_batch_receipts_verdict`; downgrade gagal di 023 | Upgrade dari DB kosong tidak diulang auditor utama |
| Constraint & integritas | PK/FK/unique/CHECK, orphan | **PARTIAL** | 25/25 PK, 53/53 FK ber-index, 0 orphan FK | Status tanpa CHECK; PO tanpa decision 12/17 |
| Performa | polling, query, bundle | **FAIL** | 148 req/menit idle; seq scan supply_records | Tanpa load test, tanpa EXPLAIN volume |
| Frontend & a11y | 18 tabel, dialog, kontras, gate | **PARTIAL** | tsc merah 4; lint bersih; 198 pasangan kontras ≥4.5:1 | Viewport kecil & screen reader tidak diuji |
| AI agents | inventaris, grounding, tool, fallback | **PASS** (grounding) / **FAIL** (verifier) | 167 lulus 1 gagal; `cek_ledger` dead branch | Model nyata tidak dipanggil |
| SAP | live vs mock vs stub | **FAIL** | Adapter 0 pemanggil; mock-sap hanya /health | — |
| SAP Joule / BTP | bridge A2A | **FAIL** | Bridge 200, `dataset decisions=11 batches=50`, `url=lhr.life` | Isi destination/DA tidak diverifikasi |
| AWS | AgentCore, IAM, memory | **PARTIAL** | Runtime `READY` v30; Gateway/Memory tidak terintegrasi | Invoke & IAM tidak diuji (AccessDenied) |
| CI/CD & ops | workflow, secret-scan, observability | **FAIL** | Gate tes ada; tanpa secret-scan/build/deploy; 1 logger, 0 request-id | — |
| Dokumentasi vs kode | 5 klaim integrasi | **PARTIAL** | §H tabel klaim-vs-bukti | — |

---

## C. REGISTER TEMUAN

Diurutkan berdasarkan severity lalu dampak. Kolom **Verif.** menyatakan siapa yang membuktikan:
**AU** = auditor utama (sesi ini, bukti di transkrip), **SR** = sub-reviewer (laporan domain, tidak
diulang auditor utama), **AU+SR** = keduanya.

### CRITICAL

**AUD-001 — Jembatan SAP Joule/A2A hidup tetapi melayani data dari backend asing lewat tunnel publik**
- Area: SAP/BTP · Verif.: **AU** (R + S) · Confidence: High
- Lokasi: `sap-joule/a2a_server/server.py`; health endpoint CF.
- Bukti aktual (curl tanggal 2026-10-29 11:44 WIB):
  `GET https://mealchain-joule-bridge-4sehat3trio.cfapps.ap10.hana.ondemand.com/health` →
  `{"status":"ok","backend":{"reachable":true,"url":"https://ffeed6a383e098.lhr.life",
  "dataset":{"decisions":11,"batches":50}}}`.
  DB repo ini: **49 keputusan / 133 batch**. `url_source=env` → bridge membaca `MEALCHAIN_API_URL`
  dari environment Cloud Foundry, bukan dari repo.
- Kondisi pemicu: panggil `/health` bridge (aman, GET).
- Perilaku saat ini: bridge menjawab 200 dan menyajikan **dataset pihak ketiga** melalui tunnel
  `localhost.run` (`lhr.life`) yang bisa berubah/berhenti kapan saja, **tanpa autentikasi** dan dengan
  CORS default `*`.
- Perilaku seharusnya: bridge menunjuk backend yang pasti (URL tetap + auth), atau dinyatakan
  "belum terhubung" dan tidak dipakai dalam demo.
- Root cause: `MEALCHAIN_API_URL` di CF diisi URL tunnel sementara; tidak ada pinning/verifikasi
  identitas backend.
- Dampak: (a) integritas klaim — angka yang dilihat juri lewat Joule bukan angka aplikasi;
  (b) keamanan — endpoint internet publik meneruskan data institusional lewat tunnel pihak ketiga;
  (c) reliabilitas — sub-reviewer mengamati `backend.reachable=false` (`/health → 502`) 15 menit
  sebelumnya, artinya tunnel tidak stabil.
- Rekomendasi: hentikan pemakaian bridge untuk demo sampai `MEALCHAIN_API_URL` menunjuk host tetap
  milik sendiri (VPS/CF), tambahkan auth token di bridge, tetapkan `CORS_ORIGINS` eksplisit, dan
  tampilkan `dataset` + commit hash backend di `/health` agar bisa dibuktikan.
- Acceptance: `/health` melaporkan `dataset.decisions == count(decisions)` DB yang sama dengan yang
  dipakai UI; `curl` tanpa token → 401; tidak ada referensi `lhr.life`/`*.trycloudflare` di env mana pun.
- Dependensi: keputusan owner soal host backend permanen.

### HIGH

**AUD-002 — Aplikasi berjalan sebagai superuser Postgres; role least-privilege tidak diterapkan**
- Area: Database/Security · Verif.: **AU+SR** (D,R,S)
- Lokasi: `docker-compose.yml:47-51`; `scripts/siapkan_role_app.py`; migrasi `043_least_privilege_app`.
- Bukti: `DATABASE_URL` user = `mealchain`, dan `pg_roles`: `mealchain|rolsuper=t|createdb=t|createrole=t`.
  `APP_DATABASE_URL`/`MIGRATION_DATABASE_URL` **unset**. Role `mealchain_app` (INSERT+SELECT saja pada
  `ledger_blocks`) dan `mealchain_migrator` ada di DB, tetapi `mealchain_app_login` **tidak ada** di
  `pg_roles` → migrasi 043 belum pernah "dipakai".
- Dampak: kompromi aplikasi = kepemilikan penuh DB (DROP/ALTER/TRUNCATE), dan kontrol DB lain
  (AUD-003) kehilangan gigi.
- Rekomendasi: jalankan `scripts/siapkan_role_app.py`, set `APP_DATABASE_URL`, migrasi memakai
  `mealchain_migrator`, verifikasi dengan `uji_least_privilege_restore.sh`.
- Acceptance: `select current_user` dari koneksi backend = `mealchain_app_login`; `has_table_privilege
  ('mealchain_app_login','ledger_blocks','UPDATE') = false`; suite tetap hijau.

**AUD-003 — Klaim "ledger immutable" bisa ditembus dari koneksi aplikasi sendiri**
- Area: Database/Ledger · Verif.: **AU+SR** (D)
- Lokasi: `backend/alembic/versions/042_ledger_append_only.py:96-105` (fungsi `prevent_ledger_mutation`).
- Bukti di DB klon: `UPDATE ledger_blocks …` → **ditolak** (`ledger_append_only`).
  Dengan `SET LOCAL mealchain.ledger_maintenance='on'` pada koneksi user `mealchain` → **`UPDATE 1`
  berhasil** (lalu `ROLLBACK`). Penyebab: `pg_has_role(current_user,'mealchain_migrator','member')`
  = `t` karena superuser lolos semua cek peran.
- Perilaku seharusnya: hanya role migrasi yang bisa membuka pintu; role aplikasi tidak.
- Dampak: jaminan anti-manipulasi riwayat audit hanya berlaku terhadap mutasi tak sengaja/ORM.
  Setiap SQL pada koneksi aplikasi (atau aktor yang menguasainya) dapat menulis ulang riwayat.
- Rekomendasi: tutup lewat AUD-002. Tambahan: verifikasi di `/ledger/verify` bahwa
  `current_user` bukan superuser, dan laporkan `generation` + jumlah blok yatim (sudah ada).
- Acceptance: sebagai `mealchain_app_login`, `SET LOCAL mealchain.ledger_maintenance='on'` tetap
  ditolak trigger; uji regresi baru untuk dua peran.

**AUD-004 — Rahasia produksi pernah ter-commit di riwayat git; rotasi belum terbukti**
- Area: Security · Verif.: **AU+SR** (S)
- Lokasi: commit `c4d22b3` ("sertakan .env utk onboarding tim (KEPUTUSAN OWNER…)"), dihapus `8f95c98`.
- Bukti: `git log --all -- .env` menampilkan 7 commit; `.env` versi `c4d22b3` memuat kunci
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_BEARER_TOKEN_BEDROCK`,
  `SAP_AI_CORE_CLIENT_SECRET`, `INFERHUB_API_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD`, `SIGNING_KEY_HEX`.
  (Nilai **tidak** dikutip di laporan ini.) Sub-reviewer: tidak ditemukan di mirror publik
  `munk23zzz/MealChainGuardian` (51 commit) tetapi masih ada di `origin` privat.
- Dampak: siapa pun yang pernah meng-clone repo privat memegang kredensial AWS/SAP. Menghapus berkas
  dari HEAD tidak mencabut risiko historis.
- Rekomendasi: rotasi SEMUA kunci tersebut (AWS access key, SAP AI Core client secret, InferHub,
  `JWT_SECRET`, `POSTGRES_PASSWORD`, `SIGNING_KEY_HEX`); catat tanggal rotasi di `TODO.md:611`;
  pertimbangkan `git filter-repo` bila repo akan dibuka.
- Acceptance: kunci lama terbukti non-aktif (STS/`GetCallerIdentity` gagal / AI Core 401); catatan
  rotasi bertanggal ada di repo; `gitleaks` bersih pada riwayat baru.

**AUD-005 — `GET /auth/demo-login` membocorkan kata sandi akun demo tanpa autentikasi**
- Area: Security · Verif.: **AU+SR** (R)
- Lokasi: `backend/app/api/auth.py:154-181`.
- Bukti: tanpa token → 200 dan 7 akun lengkap dengan `password` plaintext, karena runtime
  `DEMO_MODE=True` **dan** `DEMO_LOGIN_AUTOFILL=True`. Kode mendokumentasikan konsekuensinya sendiri.
- Mitigasi terukur: `tailscale funnel status` / `serve status` → **"No serve config"**, jadi saat ini
  hanya terjangkau lokal/LAN. Dev compose mem-publish `0.0.0.0:8000` (`docker-compose.yml`).
- Dampak: bila demo diekspos (funnel/ngrok/VPS), siapa pun di internet memperoleh kredensial ketiga
  peran sekaligus — termasuk `bgn_monitor` yang bisa mengubah pengguna (AUD-006).
- Rekomendasi: matikan `DEMO_LOGIN_AUTOFILL` di luar sesi demo; jika perlu, batasi endpoint ke
  `127.0.0.1` atau balik di balik sesi; ganti sandi demo per sesi.
- Acceptance: `/auth/demo-login` → `{enabled:false, accounts:[]}` saat `DEMO_LOGIN_AUTOFILL=false`;
  uji regresi untuk dua kombinasi flag.

**AUD-006 — Peran pemantau `bgn_monitor` memegang tulis manajemen pengguna; token layanan agen memakai peran itu**
- Area: Security/API · Verif.: **AU+SR** (R,S)
- Lokasi: `backend/app/api/admin.py:95-107,166-170`; `MEALCHAIN_API_TOKEN`.
- Bukti: `PATCH /admin/users/{uuid}` dengan token `bgn_monitor` → **404 "pengguna tidak ditemukan"**
  (artinya lolos otorisasi), sedangkan sppg_head/nutritionist → **403**. Skema tidak punya peran
  `admin`; keputusan owner 2026-10-17 + pagar anti-ubah-peran-sendiri + ledger.
- Dampak: peran yang didokumentasikan "read-only nasional" dapat mengubah data pengguna; token layanan
  agen yang berperan `bgn_monitor` mewarisi wewenang itu.
- Rekomendasi: pisahkan peran admin (skema) atau batasi `admin/*` ke token layanan khusus; jangan
  pakai JWT `bgn_monitor` untuk worker agen.
- Acceptance: matriks role×endpoint menunjukkan `bgn_monitor` 403 pada semua metode tulis `admin/*`;
  test regresi menutup jalur token layanan.

**AUD-007 — Gerbang keselamatan suhu mengabaikan sampel terakhir (excursion di ujung log hilang)**
- Area: Business logic/Safety · Verif.: **AU** (U) + SR
- Lokasi: `backend/app/core/temperature.py:170-174`.
- Bukti (dijalankan di container):
  `summarize_temperature_log([5 °C, 5 °C, 20 °C], band 0–8)` → `outside_minutes=0.0, complete=True`;
  `[20 °C, 20 °C, 5 °C]` → `outside_minutes=120.0`.
- Perilaku saat ini: durasi di luar rentang diatribusikan ke sampel **sebelumnya**; sampel terakhir tidak
  pernah dinilai, dan waktu setelah sampel terakhir tidak dihitung sama sekali.
- Dampak: batch yang memanas di akhir perjalanan dinilai "tidak ada excursion" → lolos gerbang
  freshness/safety. Asimetris terhadap batch yang memanas di awal.
- Rekomendasi: nilai juga `ordered[-1]` (mis. atribusikan interval terakhir ke `curr`, atau tambahkan
  penalti untuk sampel terakhir di luar rentang); jangan mengarang ambang baru — hanya perbaiki
  atribusi interval.
- Acceptance: log `[5,5,20]` menghasilkan `outside_minutes > 0`; log `[20,20,5]` tetap 120; tes baru
  untuk kasus "sampel terakhir di luar rentang" dan "satu sampel saja" (yang tetap `evidence_insufficient`).

**AUD-008 — Staleness keselamatan bergantung pada `evaluation_time` dari pemanggil, dan endpoint menulis status batch**
- Area: Business logic/Safety · Verif.: **SR** (S,R)
- Lokasi: `core/safety.py:154-170`; `api/safety.py:37,62-70`.
- Bukti: log berumur 2 hari, `evaluation_time=None` → `pass`/`sufficient`; dengan jam sekarang →
  `needs_verification`. Parameter berasal dari body request.
- Dampak: pemanggil dapat melumpuhkan pemeriksaan kesegaran dengan tidak mengirim (atau memundurkan)
  `evaluation_time`; endpoint juga **menulis** `batch.safety_status`.
- Rekomendasi: `evaluation_time` default = jam server (bukan `None`), tolak nilai di masa depan atau
  lebih tua dari toleransi; pisahkan endpoint baca dan tulis status.
- Acceptance: request tanpa `evaluation_time` menghasilkan verdict yang sama dengan jam server; uji
  negatif `evaluation_time` di masa depan → 422.

**AUD-009 — Event 3 menilai semua komoditas dengan rentang rantai dingin 0–8 °C dan menulis statusnya**
- Area: Business logic/Safety · Verif.: **SR** (S,D)
- Lokasi: `services/event3_service.py:151-158`.
- Bukti: batch beras `45268526` (8 sampel @9,5 °C) tersimpan `fail`; dengan profil komoditas beras
  (ambient) mesin mengembalikan `pass`. Ini regresi bug "beras dinilai rantai dingin".
- Dampak: status keselamatan salah tersimpan permanen untuk komoditas ambient; batch sah diblokir, dan
  sebaliknya profil yang lebih longgar bisa membuat batch dingin lolos bila urutannya terbalik.
- Rekomendasi: pakai `CommodityPolicy` (`batch_policy_from`) di Event 3, seperti jalur lain; jangan
  menulis `batch.safety_status` dari jalur yang memakai kebijakan default.
- Acceptance: batch beras ambient → `pass`; batch ayam 9,5 °C → `fail`; tes regresi per komoditas.

**AUD-010 — Data demo memuat keputusan `executed` yang melanggar gerbangnya sendiri**
- Area: Data/Business logic · Verif.: **SR** + AU (D,R)
- Lokasi: `seed/demo_template.py:567-592`; keputusan `661695b2`, `08e732f6`.
- Bukti: `661695b2` `executed` + PO `confirmed`, tetapi batch sumbernya `fail` dan `usable_until` lewat;
  `/audit-facts` sendiri menjawab `statuses:["fail"]`, `penghalang:"batch_expired"`.
  `08e732f6` `executed` dengan **0 approval** (`satisfied:false, missing:[head,nutritionist]`).
  Tes repo menangkap ini: `test_invarian_riwayat_demo.py:105` gagal.
- Dampak: demo menyajikan bukti yang bertentangan dengan aturan inti produk. Juri yang membuka
  audit-facts akan menemukan sistem menyalahkan dirinya sendiri.
- Rekomendasi: perbaiki template seed agar setiap `executed` punya ≥2 approval dan batch sumber yang
  masih `pass`+belum kedaluwarsa pada jangkar waktu sesi; tambahkan invarian sebagai gate seed.
- Acceptance: `test_invarian_riwayat_demo` hijau; query "executed tanpa approval" = 0; query "executed
  dengan batch fail/expired" = 0.

**AUD-011 — `init-demo` tidak idempoten dan destruktif-sebagian: data kanonik hilang**
- Area: Database/Data · Verif.: **SR** (D, di klon)
- Lokasi: `backend/app/db_mode.py:282-293`; `app/seed/reference.py:33-40`.
- Bukti (klon identik): `exit=1`, `UniqueViolationError commodities_name_key (telur)`; `supply_records`
  5.240→5.200, `price_signals` 5.933→5.893, **baris kanonik 40→0**, jangkar harga 8 Okt hilang.
  Penyebab: `commit()` penghapusan baris kanonik terjadi **sebelum** seed ulang, dan lookup hanya by-ID.
- Dampak: satu klik/`init-demo` yang gagal di tengah meninggalkan DB tanpa data acuan, dan KPI
  kehilangan jangkar pembanding.
- Rekomendasi: bungkus hapus+seed dalam satu transaksi (atau tandai generasi baru dan tukar setelah
  sukses); lookup kanonik by natural key, bukan hanya UUID; gagal → rollback penuh.
- Acceptance: `init-demo` dua kali berturut-turut → exit 0 dan row count identik; simulasi kegagalan di
  tengah → tidak ada baris hilang.

**AUD-012 — `reset-demo` tidak menaikkan generasi ledger → blok yatim di generasi aktif**
- Area: Database/Ledger · Verif.: **SR** (S,D)
- Lokasi: `db_mode.py:368-388` vs `timeseries.py:1107-1112`, `demo_purge.py:77-80`.
- Bukti: setelah reset, semua blok entitas terhapus menjadi yatim di generasi aktif; `/ledger/verify`
  langsung memberi `coverage_warning`. Secara keseluruhan **1.486/3.841 blok (38,7%)** menunjuk entitas
  yang sudah tidak ada.
- Dampak: "rantai valid" ≠ "bukti lengkap". Panel integritas akan menampilkan peringatan cakupan.
- Rekomendasi: panggil `bump_generation` pada setiap jalur yang menghapus entitas ber-blok (reset, purge,
  rebuild); jadikan satu helper `hapus_entitas_berblok()`.
- Acceptance: setelah reset, `orphan_blocks` pada generasi aktif = 0; `/ledger/verify` tanpa
  `coverage_warning`; tes regresi untuk tiga jalur hapus.

**AUD-013 — KPI mengembalikan 8 metrik sementara kontrak, tes, dan dokumen menuntut 7**
- Area: API/Business logic · Verif.: **AU** (R,U)
- Bukti: `GET /kpi?periode=today` → `len(metrics)=8`; metrik ke-8 "Effective Price per Accepted Kg".
  Tes merah: `test_kpi_api.py:158` & `:267` (`assert 8 == 7`), `test_kpi.py:220`, `test_hari_ini.py:138`,
  dan `test_hari_ini.py:190` gagal dengan `['Effective Price per Accepted Kg']`.
- Dampak: kontrak tidak stabil; klien/dokumentasi yang mengunci 7 metrik akan pecah; gate rilis merah.
- Rekomendasi: putuskan apakah metrik ke-8 resmi (perbarui `kamus-kpi`, tes, dan dokumen) atau dicabut.
- Acceptance: satu sumber daftar KPI; `len(metrics)` sama di kode, tes, dan dokumen; suite hijau.

**AUD-014 — Gate statis merah: ruff 12 error, `tsc --noEmit` 4 error**
- Area: Frontend/Backend quality · Verif.: **AU+SR** (U)
- Bukti: `ruff check .` → exit 1, 12 error (I001×4, F401×3, E501×3, F811×1, termasuk
  `app/api/receipts.py:65` mengimpor ulang `USABLE`); `npx tsc --noEmit` → exit 2, 4×TS2802 di
  `tests/supplier-receipts-css.test.ts:32,58` dan `tests/supplier-summary-css.test.ts:15,30`
  (akar: `frontend/tsconfig.json` tanpa `target`). `next lint` bersih.
- Catatan: dua berkas tes yang gagal itu **tracked** → gate typecheck sudah merah di `9019eb1`.
- Acceptance: `ruff check .` exit 0; `npm run typecheck` exit 0; CI menjalankan keduanya.

**AUD-015 — Suite backend merah: 30 gagal + 3 error**
- Area: Testing · Verif.: **AU** (U)
- Bukti: `pytest -q` di DB klon → `30 failed, 2256 passed, 36 skipped, 3 errors in 903.85s`.
  Klasifikasi: 3 error = `IntegrityError duplicate key decisions_pkey` (fixture bertabrakan dengan baris
  demo di klon — artefak lingkungan); sisanya assertion, termasuk AUD-013, drift openapi, AUD-010,
  `test_po_invoice_commercial` (lihat AUD-016), `test_action_boundary_e2e` (7).
- Dampak: tidak ada baseline hijau → regresi baru tidak bisa dibedakan dari kebisingan.
- Rekomendasi: jalankan suite di DB **kosong+migrasi+seed khusus tes** (bukan klon demo), kunci daftar
  kegagalan yang diterima, dan perbaiki satu per satu.
- Acceptance: `pytest` exit 0 pada DB uji bersih; jumlah skip tercatat dan beralasan.

**AUD-016 — `invoice_total` tidak konsisten dengan harga satuan pada 4/17 PO (baris legacy)**
- Area: Business logic/Numerik · Verif.: **AU** (D,R)
- Bukti: 13/17 PO konsisten; 4 PO `legacy_unmigrated` tidak:

  | PO | `po.price` | `invoice_total` | total/qty | selisih/kg |
  |---|---:|---:|---:|---:|
  | MC-661695B2C685 | 13.300,00 | 8.372.050,74 | 13.953,42 | +653,42 |
  | MC-775289583C6E | 23.500,00 | 12.150.245,34 | 20.250,41 | −3.249,59 |
  | MC-B54D0F110D61 | 41.500,00 | 24.332.495,70 | 40.554,16 | −945,84 |
  | MC-E7150DA4CB4B | 25.132,39 | 16.472.159,28 | 27.453,60 | +2.321,21 |

  Penyebab: `invoice_total` diturunkan dari `cost_breakdown` (SDC: purchase+handling+logistics+
  expected_loss) sedangkan `price`/`invoice_unit_price` adalah kutipan pemasok; peta `HARGA` statis di
  `seed/jakarta_lengkap.py:733-744` tidak sama dengan `commercial_cost`.
- Dampak: klien yang mengalikan `invoice_unit_price × qty` mendapat angka berbeda dari `invoice_total`;
  variance/settlement dihitung di atas dua basis. Sudah ditandai `cost_legacy`, tetapi angkanya tetap
  tidak rekonsiliasi.
- Rekomendasi: sajikan dua field bernama jelas (`quoted_unit_price` vs `billed_unit_price`) dan
  `invoice_total` yang konsisten dengan `billed`; atau migrasikan 4 baris legacy.
- Acceptance: untuk setiap PO, `invoice_total == billed_unit_price × qty` (toleransi 0,01); tes
  `test_daftar_po_menyebut_invoice_unit_price_secara_eksplisit` hijau.

**AUD-017 — Model routing AgentCore ARN dipakai sebagai slot pertama supervisor, verifier, dan forecast**
- Area: AWS/AI · Verif.: **SR** (S, dijalankan `get_agent_chain`)
- Lokasi: `backend/app/core/model_registry.py:123-126`.
- Bukti: `AGENTCORE_RUNTIME_ARN` disisipkan sebagai slot pertama untuk ketiga rantai; akibatnya
  `sap-ai-core:rpt` (model peramal) tidak pernah menjadi peramal utama.
- Dampak: klaim "forecast lewat SAP AI Core" tidak benar pada konfigurasi berjalan; kualitas/atribusi
  model salah.
- Rekomendasi: pisahkan rantai per agen; jangan sisipkan ARN runtime sebagai model LLM generik.
- Acceptance: `get_agent_chain("forecast")[0]` = model forecast yang diniatkan; tes per rantai.

**AUD-018 — Dependensi rentan: 4 advisory critical di frontend, 30 di backend**
- Area: Security/Dependency · Verif.: **SR** (U)
- Bukti: `npm audit` → 12 advisory, 4 critical (termasuk `next` DoS, `maplibre-gl` XSS);
  `pip-audit` → 30 advisory/6 paket (`pyjwt 2.9.0` 17, `starlette 0.38.6` 7, `pypdf` 3). Fix = semver-major.
- Dampak: jalur serangan yang sudah diketahui publik pada komponen yang menyajikan UI.
- Rekomendasi: rencanakan upgrade terkontrol (Next 14.2.x patch → 15, `pyjwt`, `starlette`), satu per
  commit dengan suite hijau; jangan `npm audit fix --force`.
- Acceptance: `npm audit --omit=dev` tanpa critical/high; `pip-audit` tanpa advisory yang ada fix-nya;
  suite tetap hijau.

### MEDIUM

**AUD-019 — Verifier tidak bisa menandai "executed tetapi tanpa blok ledger"; cabang kode mati**
- Area: AI Agents · Verif.: **SR** + AU (S). Lokasi: `agent/verifier_checks.py:454-461`.
- Bukti: `cek_ledger` mengembalikan `True` setiap kali `count==0` dan `actions` kosong ("belum ada aksi"),
  sehingga cabang status di `:466-472` tidak pernah tercapai dan keputusan `executed` tanpa blok tidak
  tertangkap. Tes repo gagal: `test_agent_verifier_independence.py:463` (`assert True is False`).
- Acceptance: keputusan `executed` dengan 0 blok → check gagal; tes itu hijau.

**AUD-020 — Lima dari delapan KPI demo berstatus `no_data`**
- Area: Data/Product · Verif.: **AU** (R). Bukti `GET /kpi?periode=today`:
  Meal Continuity `no_data` (n=0); Avoidable Food Loss `no_data` (n=0); Safe Delivered Cost `no_data`;
  Effective Price `no_data`; Decision Time `no_data` (n=5); Evidence Completeness `available 0,00%` (n=1);
  Regional Imbalance `0,00%` (n=5); Price Deviation `2,69%` (n=60).
- Dampak: strip KPI yang menjadi wajah demo praktis kosong; juri melihat "—" di mayoritas kartu.
- Rekomendasi: keputusan produk — isi data sesi demo agar metrik punya sampel, atau tampilkan state
  kosong yang menjelaskan sebabnya.

**AUD-021 — Snapshot SDC tidak selalu sama dengan `cost_breakdown`**
- Area: Business logic · Verif.: **SR** (D,R).
- Bukti: `3e2e3cc7` breakdown 9.375.000 vs `safe_delivered_cost` 9.750.000 (Δ375.000); `08e732f6` SDC
  10.350.000 dengan `cost_breakdown` NULL. Fallback `_harga_satuan_invoice` membuat keputusan `approved`
  `5e969ff1` gagal di **422** yang menyesatkan.
- Catatan: 41/41 keputusan ber-breakdown **lengkap** menjumlah tepat ke SDC — jadi masalahnya pada baris
  tanpa breakdown / hasil fallback, bukan pada rumus inti.

**AUD-022 — Empat keputusan SDC tanpa rincian komponen; angka tidak dapat diaudit ulang**
- Area: Data · Verif.: **SR** (D). Termasuk dalam AUD-021; dipisah karena tindakannya beda
  (backfill vs perbaikan fallback).

**AUD-023 — `alembic check` gagal: index hanya ada di DB**
- Area: Database · Verif.: **AU+SR** (U,D). `ix_batch_receipts_verdict` dibuat `044:65-72` tetapi tidak
  dideklarasikan di `models/receipts.py:77`; autogenerate berikutnya akan mengusulkan `DROP INDEX`
  (index terpakai, `idx_scan=6`).

**AUD-024 — Rollback migrasi mustahil dengan data representatif**
- Area: Database · Verif.: **SR** (D, di klon). `alembic downgrade base`: 16 langkah OK, **gagal di 023**
  (`CheckViolation decisions_decision_type_check`, 28 baris `supplier_procurement`); DB tertinggal
  setengah turun.
- Rekomendasi: dokumentasikan migrasi yang tidak reversible, atau sediakan jalur data-migration sebelum
  constraint baru.

**AUD-025 — Constraint status longgar: beberapa kolom status tanpa CHECK**
- Area: Database · Verif.: **SR** (D). `ledger_blocks.action` menerima 8 nilai bebas (termasuk artefak uji
  `uji_generasi`, 2 blok bertanggal 29 Okt), `batch_receipts.verdict`, `approvals`, `proposed_by`/
  `verified_by` tanpa CHECK.
- Dampak: nilai status liar bisa masuk tanpa ditolak DB, memaksa lapisan aplikasi jadi satu-satunya penjaga.

**AUD-026 — 12 dari 17 PO tidak terhubung ke keputusan apa pun**
- Area: Data/Ledger · Verif.: **AU** (D). `select count(*) filter (where decision_id is null)` → **12/17**.
- Dampak: jejak bukti "PO lahir dari keputusan yang disetujui" tidak berlaku untuk mayoritas PO demo.
- Rekomendasi: tandai PO template sebagai `origin='seed'` dan tampilkan terpisah, atau hubungkan ke
  keputusan; tambahkan invariant check.

**AUD-027 — Cascade menghapus bukti: hapus 1 keputusan menghilangkan trace, evidence, approval + 102 blok jadi yatim**
- Area: Database · Verif.: **SR** (D). Bertaut dengan AUD-012 (generasi ledger).

**AUD-028 — Polling storm: 148 request/menit saat idle**
- Area: Frontend/Performance · Verif.: **SR** (B, terukur 163 request/66 dtk) + AU (33× `refetchInterval`).
- Penyebab utama: `/balance/map` 52× (interval 5 s × 4 komoditas, tanpa gating tab aktif),
  `/decisions` 26×, 6 endpoint detail 12× masing-masing.
- Dampak: beban server, baterai, dan risiko rate-limit saat demo.

**AUD-029 — Tidak ada error boundary: satu exception memutihkan seluruh aplikasi**
- Area: Frontend · Verif.: **AU** (S). `app/error.tsx`, `app/global-error.tsx`, `app/not-found.tsx`
  **tidak ada**.

**AUD-030 — Angka 0 ditampilkan saat data gagal dimuat**
- Area: UX/Integritas angka · Verif.: **SR** (B). Lonceng notifikasi menampilkan **0** saat memuat/gagal
  (terukur 0 → 17); saat poll gagal, angka lama (−780 kg · 300 kg · 28%) tetap tampil tanpa penanda basi.
- Dampak: langsung bertabrakan dengan prinsip proyek "jangan mengubah no_data menjadi 0".

**AUD-031 — Aksi destruktif demo tanpa konfirmasi**
- Area: UX/Safety · Verif.: **SR** (S). "Akhiri sesi" dan "Muat Demo (replace)" langsung jalan, sementara
  "Bangun ulang" berkonfirmasi (`DemoControlPanel.tsx:690,729` vs `:185-235`).

**AUD-032 — Endpoint purge/rebuild demo bersifat global; sesi demo bisa dimulai peran SPPG**
- Area: API/Security · Verif.: **AU+SR** (R,S). `POST /demo/session/start` → 200 untuk sppg_head dan
  sppg_nutritionist, 403 hanya untuk bgn_monitor; `/demo/timeseries/purge`, `/refresh`,
  `/template/rebuild` global (bandingkan `/demo/seed` yang ter-scope kota).
- Dampak: satu kepala SPPG dapat mereset/menghapus data demo seluruh lokasi.

**AUD-033 — `GET /batches` lintas lokasi untuk semua peran**
- Area: API/Data · Verif.: **AU+SR** (R). sppg_head Jakarta: 133 baris/10 lokasi + `quantity_kg`,
  safety/quarantine/freshness. Dinyatakan sengaja untuk panel chaos Event 3 (`batches.py:48-60`).
- Dampak: peran lokasi dapat membaca stok 10 SPPG. Bukan bug tersembunyi (keputusan terdokumentasi),
  tetapi rute baca tanpa scope sementara rute tulis ber-scope — sisa risiko yang harus tercatat.

**AUD-034 — Token tanpa pencabutan/refresh; logout hanya menghapus localStorage**
- Area: Security · Verif.: **SR** (S). `auth.py` hanya 4 rute; token berlaku sampai 720 menit.

**AUD-035 — Adapter SAP nyata tidak dipanggil; "mock SAP" bukan layanan**
- Area: SAP · Verif.: **SR** (S,R,log). `sap-joule`/adapter 299 baris MCP: **0 pemanggil**;
  `SAP_PROVIDER`/`SAP_MCP_ENDPOINT` unset; kontainer `mock-sap` hanya `GET /health`
  (**4 request seumur kontainer, 0 request data**). Data "SAP" yang dilihat UI berasal dari tabel
  Postgres `sap_mock_*`.
- Dampak: label/panel "SAP" harus jelas menyebut MOCK; jangan sampai diagram menyiratkan layanan hidup.

**AUD-036 — Observability praktis nol**
- Area: Operations · Verif.: **SR** (S). 1 logger, 0 request/correlation ID, 0 alarm CloudWatch;
  `X-Data-Source: MOCK` hanya di 1 endpoint (`api/supply.py:83`); panel integrasi menunjuk
  `core/observability.py` yang **tidak ada**.

### LOW / INFORMATIONAL

- **AUD-037** — Gate sesi demo (409) dievaluasi sebelum otorisasi peran: tanpa sesi aktif, bgn_monitor
  menerima 409 (bukan 403) pada endpoint tulis. Menyamarkan penolakan otorisasi. (AU, R)
- **AUD-038** — `/decisions?window=24h` hanya punya batas bawah → baris masa depan akan ikut bila ada
  (saat ini 0 keputusan bertanggal masa depan). (AU, S,D)
- **AUD-039** — Data bertanggal masa depan di sumber: `supply_records` 520, `price_signals` 580,
  `demand_records` 240, `batches.usable_until > now()+60d` 32. KPI memakai jendela berbatas sehingga
  tidak terpengaruh; feed tidak. (AU, D)
- **AUD-040** — Artefak `openapi.json` ter-commit sudah basi (tes `test_openapi_artifact_drift` gagal),
  sementara `/openapi.json` runtime → 404 (`ENABLE_DOCS` unset). (AU, R,U)
- **AUD-041** — 14 komponen frontend (±2.739 baris) tidak terjangkau dari `page.tsx` tetapi tetap dites →
  suite hijau menutupi UI mati. (SR, S)
- **AUD-042** — Aksesibilitas: `role="combobox"` tanpa nama aksesibel (`DecisionPicker.tsx:237-253`),
  `aria-selected` dipakai untuk sorotan (`:293`), fokus awal dialog ke tombol tutup. (SR, S)
- **AUD-043** — Byte NUL mentah di `frontend/lib/api.ts:1142` membuat berkas dianggap biner oleh
  grep/diff. (SR, S)
- **AUD-044** — Rate limit login hanya `(IP+email)`, in-memory, tanpa batas per-IP lintas akun
  (20/60 s; `Retry-After` terbukti). (SR, R)
- **AUD-045** — `JWT_ALGORITHM` diambil dari env tanpa jepitan; tidak ada `aud`/`iss`. (SR, S)
- **AUD-046** — Skema berisi artefak uji: 2 blok `ledger_blocks.action='uji_generasi'` bertanggal
  29 Okt 2026 di DB demo. (SR, D)
- **AUD-047** — 105 database `mealchain_*` (4.940 MB) di klaster yang sama; DB demo sendiri 28 MB. (SR, D)
- **AUD-048** — Anchor/checkpoint ledger hanya sampai tinggi 978 dari 3.841 blok. (SR, D)
- **AUD-049** — Tidak ada CCP (Critical Control Point) di kode; dokumen menyebut CCP sebagai konsep.
  (SR, S) — perlu keputusan produk, bukan bug.
- **AUD-050** — `docker-compose.prod.yml` ada, tetapi compose dev (bind mount, `next dev`, port
  `0.0.0.0`) masih yang dipakai; CI tanpa secret-scan/build/deploy/rollback. (SR, S)

---

## D. LAPORAN EKSEKUSI TES

| # | Perintah | Lingkungan | Hasil | Catatan |
|---|---|---|---|---|
| 1 | `pytest -q` (di `mealchain-backend`, `/app`) | DB klon `mealchain_audit` (pg_dump demo) | **30 failed, 2256 passed, 36 skipped, 3 errors**, 903,85 s, exit 1 | 3 error = fixture collision `decisions_pkey` |
| 2 | `ruff check .` | container backend | **12 error**, exit 1 | I001×4, F401×3, E501×3, F811×1 |
| 3 | `npx tsc --noEmit` | frontend (host) | **4 error**, exit 2 | semua di `tests/`, akar `tsconfig` tanpa `target` |
| 4 | `npx next lint` | frontend | **bersih**, exit 0 | — |
| 5 | `npx vitest run` | frontend | **2.728 test / 244 berkas lulus**, exit 0 | dijalankan sub-reviewer |
| 6 | `pytest` subset agen `-m "not live"` | container backend | **167 passed, 1 failed** (64 s) | kegagalan = AUD-019 |
| 7 | `alembic current` / `heads` | container | `044_receipt_scoring (head)` — head tunggal, tanpa cabang | — |
| 8 | `alembic check` | container | **FAILED**: `remove_index ix_batch_receipts_verdict` | AUD-023 |
| 9 | Probe HTTP authz (skrip read-only, di dalam container) | backend :8000 & clone :18200 | 401 ×12; 403 ×7 sub-resource; 403 role; 200 login | token tidak pernah dicetak |
| 10 | Hitung ulang hash-chain (di luar aplikasi) | DB demo | **3.841/3.841 cocok** | sub-reviewer |
| 11 | `pip-audit`, `npm audit --json` | container sekali-pakai / frontend | 30 & 12 advisory | AUD-018 |
| 12 | Uji fungsi `summarize_temperature_log` | container | `outside_minutes=0,0` untuk log `[5,5,20]` | AUD-007 |
| 13 | Uji trigger ledger + maintenance door | DB klon | tolak → tolak → **UPDATE 1 lolos** (rollback) | AUD-003 |

**Kegagalan yang sudah ada sebelumnya (bukan akibat perubahan audit):** `tsc` merah pada dua berkas tes
yang **tracked** di `9019eb1`; `alembic check` drift sudah ada sebelum sesi ini.

**Insiden alat (dicatat, hasilnya tidak dipakai sebagai bukti):**
- Satu sub-reviewer menjalankan `pytest` tanpa mengganti DSN, sehingga sebagian tes menyentuh **DB demo**
  langsung. Diukur ulang 11:23 vs 11:40: `decisions 49, batches 133, ledger 3841, supply 5240,
  price 5933, approvals 21, PO 17, executed 6` — **identik**, jadi tidak ada mutasi bersih. Risiko tetap
  dicatat karena fixture tes bisa menulis sebelum membersihkan.
- DB klon `mealchain_audit` dipakai bersama antar-reviewer dan sempat diubah oleh uji `init-demo`
  (batches 127 / decisions 32 / ledger 3882). **Jangan** dipakai sebagai baseline; angka kanonik dalam
  laporan ini diambil dari DB demo pada jam yang disebutkan.
- Auditor utama sempat menembak host `mealchain-guardian-…` (404) sebelum memakai host yang benar
  `mealchain-joule-bridge-…`; hasil 404 itu dibuang.

---

## E. VALIDASI LOGIKA BISNIS & DATA

### E.1 Yang cocok setelah dihitung ulang independen

| Objek | Metode independen | Hasil |
|---|---|---|
| Safe Delivered Cost (4 keputusan) | komponen dijumlah manual dari DB | 8.381.184,07 / 13.464.531,05 / 25.299.695,70 / 16.588.730,71 — **Δ 0,00** vs API |
| Rata-rata SDC 5 keputusan | agregat manual | 14.816.828,31 = API |
| 41 keputusan ber-breakdown lengkap | jumlah 6 komponen vs `safe_delivered_cost` | **tepat sama** |
| Meal Continuity | 65,2628 → 65,26 (n=210); Jakarta 8.400/8.400 → 100,00 | cocok |
| Avoidable Food Loss | 0,0303 → 0,03 (n=44); Jakarta 10/1.770 → 0,56 | cocok |
| Regional Imbalance | 0/5 → 0,00 | cocok |
| Decision Time | 20,00 menit (4/33 → coverage 0,12) | cocok |
| Evidence Completeness | 0/2 → 0,00 | cocok |
| Procurement Price Deviation | 2,69 % (n=60) | cocok |

`no_data` vs `0` konsisten: periode kosong → 8/8 `no_data` dengan alasan; periode ganda/naive → 422.
PO deterministik: 0 keputusan memiliki 2 PO.

### E.2 Yang tidak cocok

1. **AUD-007** — excursion suhu kehilangan sampel terakhir (dibuktikan dengan dua log).
2. **AUD-016** — 4/17 PO: `invoice_total` ≠ harga satuan × qty (selisih hingga 3.249,59/kg).
3. **AUD-021** — 4 keputusan: SDC tanpa `cost_breakdown` atau breakdown tidak menjumlah ke SDC.
4. **AUD-013** — jumlah metrik KPI 8 vs kontrak 7.

### E.3 Temporal

- Sesi demo aktif `mode=replay` dengan `evaluation_anchor=2026-10-08 12:00`, tetapi
  `GET /kpi?periode=today` berlabel "Hari ini, 2026-10-29" (SDC hari ini dihitung dari 2 PO).
  Ini pilihan desain simulasi, **tetapi label UI harus menyebut jangkar**, bukan "hari ini".
- Baris bertanggal masa depan: supply 520, price 580, disposal 16 (maks 4–5 Nov).
- `actions.py:384-394` mengganti jam gerbang dengan `evaluation_anchor` sesi demo: batch yang sama
  menghasilkan `batch_expired` (jam dinding) vs `usable` (jangkar). Perlu keputusan produk, bukan bug.

---

## F. LAPORAN KEAMANAN

**Terkonfirmasi (R/S):**
- AUD-001 (bridge A2A publik + tunnel), AUD-004 (rahasia di riwayat git), AUD-005 (kredensial demo
  tanpa auth), AUD-006 (bgn_monitor menulis admin + token layanan), AUD-018 (dependensi CVE),
  AUD-032 (purge demo global), AUD-034 (token tanpa revoke), AUD-044 (rate limit), AUD-045 (algoritma JWT).

**Kontrol yang terbukti benar — jangan diubah:**
- 12/12 rute privat → **401** tanpa token; `/docs`,`/redoc`,`/openapi.json` → **404**.
- Token `alg=none` dan tanda tangan palsu → **401**; peran selalu diambil dari DB, bukan klaim token.
- CORS: origin `evil.example` → 400 tanpa `Access-Control-Allow-Origin`; header keamanan
  (`X-Content-Type-Options`, CSP, HSTS, X-Frame-Options) ada termasuk pada respons 401/405.
- Cakupan lokasi: 6/6 endpoint `{location}` lintas-lokasi → 403; 8/8 sub-endpoint keputusan → 403;
  `procurement?location_id=` asing → 403; PO SAP: 3 item (SPPG) vs 17 item (monitor).
- Tidak ada `dangerouslySetInnerHTML`; tidak ada secret di `NEXT_PUBLIC_*`; token di `localStorage`
  (risiko XSS, dimitigasi CSP — tetapi CSP memuat `unsafe-inline`).

**Tidak dapat diverifikasi:** penegakan `exp` dengan secret asli; IDOR **tulis** (approve/execute/
receipt/quarantine) — sengaja tidak dieksekusi pada DB demo; kebocoran stack trace pada 500;
ACL Windows berkas rahasia; status privat `origin`.

**Rotasi wajib (nama kunci saja):** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_BEARER_TOKEN_BEDROCK`, `SAP_AI_CORE_CLIENT_SECRET`, `INFERHUB_API_KEY`, `JWT_SECRET`,
`POSTGRES_PASSWORD`, `SIGNING_KEY_HEX`.

---

## G. INTEGRITAS DATABASE

| Aspek | Hasil |
|---|---|
| PK | 25/25 tabel punya primary key |
| FK | 53/53 FK, **0 baris yatim**, 53/53 ber-index |
| Uang | semua `numeric(10,2)`/`(12,2)`; **tidak ada float**; 0 nilai negatif/nol |
| Migrasi | linier, satu head `044`, tanpa cabang; **downgrade gagal di 023** (AUD-024) |
| Drift ORM↔DB | satu-satunya drift = index `ix_batch_receipts_verdict` (AUD-023) |
| Hash-chain | **3.841/3.841 cocok** dihitung ulang di luar aplikasi |
| Blok yatim | **1.486/3.841 (38,7 %)** menunjuk entitas yang sudah tidak ada; generasi aktif 108: 98 blok, 0 yatim |
| Privilege | app = **superuser** (AUD-002); role `mealchain_app`/`mealchain_migrator` ada tapi inert |
| Trigger | `ledger_blocks_no_mutation` + `no_truncate` aktif; **pintu maintenance terbuka** (AUD-003) |
| Index | 4 index duplikat/prefiks (≈488 kB); tidak ada `(demo_session_id, recorded_at)` → seq scan `supply_records` (2.920 baris dibuang filter, 0,7 ms) |
| Cascade | hapus 1 keputusan → 3 trace + 1 evidence + 2 approval hilang, 102 blok yatim (AUD-027) |
| Constraint status | beberapa kolom status tanpa CHECK (AUD-025) |
| Backup/DR | **tidak ada** backup otomatis, restore teruji, atau PITR untuk DB demo |
| Skala | bukan RDS/Aurora; Postgres container tunggal, tanpa replika/failover |

**Kesimpulan DB:** struktur dan rumusnya sehat — yang bermasalah adalah **privilege**, **lifecycle
generasi ledger**, dan **invarian data demo**.

---

## H. AGEN AI & INTEGRASI

### H.1 Apa yang benar-benar dilakukan agen

- **Inventaris sesuai klaim:** 7 worker analitik + 1 verifier terdaftar di `AgentName`/`hierarchy.json`;
  supervisor adalah modul terpisah (bukan agen terdaftar) → 9 entitas pemanggil LLM.
  `agent/workers/` berisi 10 modul, 2 di antaranya helper (`reasoner.py`, `sumber.py`).
- **Worker read-only terbukti:** klien hanya `get()` + `post_compute()` dengan allowlist 2 endpoint
  komputasi murni; **tidak ada** jalur create-PO/approve/execute.
- **Grounding kuat:** setiap angka di `facts` wajib punya sitasi bernilai identik
  (`contracts.py:135-164`); model hanya boleh mengubah `summary`/`confidence`; angka baru → `rejected`;
  perubahan status/blokir → `guarded`. JSON rusak → `invalid`/`unavailable`, temuan deterministik tetap dipakai.
- **Bukan otonomi multi-step:** lane statis (`orchestrator.py:31-36`), model tanpa tool,
  jalur AgentCore memanggil `run_review` tanpa narrator. Secara jujur: **pipeline 9 tahap + narasi
  advisory**, bukan agen yang memilih langkah berikutnya.

### H.2 Apa yang tidak berjalan / menyimpang

- AUD-019 (verifier tidak menangkap executed-tanpa-ledger), AUD-017 (routing model).
- `verifier_flagged` **boleh** di-approve (cukup catatan) dan **boleh** dieksekusi; verdict agen hanya
  menjadi trace — tidak ada temuan verifier yang menghentikan eksekusi (keputusan produk, tetapi
  bertentangan dengan kesan "verifier sebagai gerbang").
- Dua verifier berbeda semantik: backend `UNAVAILABLE` memblokir approve; verifier agen `unavailable`
  hanya baris trace `degraded`.
- Klaim "semua tool read-only" bertentangan dengan artefak Gateway (10 tool, termasuk
  `POST /actions/propose` yang mengubah status) — belum terpasang di jalur kode hari ini.
- Sanitasi prompt tidak ada: `json.dumps(facts)` verbatim, narasi supervisor masuk prompt verifier;
  reachability terbatas (`/suppliers` GET-only).

### H.3 Status integrasi nyata (bukan disimpulkan)

| Komponen | Status terukur |
|---|---|
| S/4HANA / OData / MCP SAP | **TIDAK ADA** (stub) |
| Adapter SAP (`get_provider`, 299 baris) | **STUB**, 0 pemanggil |
| Kontainer `mock-sap` | **STUB** — hanya `/health`; 0 request data seumur kontainer |
| Data "SAP" yang dilihat UI | **MOCK dari Postgres** (`sap_mock_purchase_orders` 17 baris; `supply_records` 5.240 = `mock_sap`) |
| SAP AI Core | **KONFIGURASI-SAJA** (slot ke-2, bukan primary) |
| Joule A2A bridge (CF) | **LIVE tapi salah backend** → AUD-001 |
| AgentCore Runtime | **LIVE** — `READY`, versi 30, `lastUpdatedAt` 2026-10-26 |
| AgentCore Gateway / Memory | **PROVISIONED, tidak terintegrasi** |
| CI | gate tes ada; tanpa secret-scan/build/deploy/rollback |

### H.4 Klaim dokumen vs bukti

| Klaim | Bukti | Verdict |
|---|---|---|
| "LLM tidak pernah menghitung angka safety-critical" | `contracts.py` + `reasoner.py` menolak angka baru | **BENAR** |
| "Tidak ada auto-execute tanpa approval" | `actions.py` benar, **tetapi** data demo `08e732f6` executed 0 approval | **BENAR di kode, GAGAL di data** |
| "Safety status tidak pernah di-override" | tidak ada override di kode; **tetapi** `api/safety.py` menulis status & `evaluation_time` dari pemanggil | **PARTIAL** |
| "Data mock ditandai" | `X-Data-Source` hanya di 1 endpoint | **PARTIAL** |
| "SAP sebagai sumber & eksekutor" | adapter 0 pemanggil, mock-sap kosong | **TIDAK TERBUKTI** |
| "Ledger immutable" | trigger aktif, hash cocok, **tapi pintu maintenance terbuka** | **PARTIAL** |

---

## I. RISK REGISTER & RENCANA PERBAIKAN

### P0 — Immediate (containment, sebelum demo apa pun)

| # | Tindakan | Lokasi | Acceptance | Risiko regresi |
|---|---|---|---|---|
| P0-1 | Jangan tampilkan jembatan Joule sebagai "SAP live"; arahkan `MEALCHAIN_API_URL` ke host sendiri atau nonaktifkan | CF env / `a2a_server` | `/health.dataset` = DB yang sama; tanpa referensi `lhr.life` | Rendah |
| P0-2 | Rotasi SEMUA kunci yang pernah ada di `.env` historis | AWS/SAP/InferHub/env | kunci lama non-aktif (uji STS/401) | Sedang (butuh koordinasi) |
| P0-3 | Matikan `DEMO_LOGIN_AUTOFILL`, atau batasi `/auth/demo-login` ke loopback | `auth.py:154-181`, compose | endpoint → `{enabled:false}`; uji dua flag | Rendah |
| P0-4 | Terapkan role least-privilege (`mealchain_app_login`) | compose + `scripts/siapkan_role_app.py` | `current_user = mealchain_app_login`; UPDATE ledger = false | Sedang (migrasi hak) |
| P0-5 | Perbaiki data demo yang melanggar gerbang (2 keputusan: executed tanpa approval / batch fail) | `seed/demo_template.py` | invariant query = 0; `test_invarian_riwayat_demo` hijau | Rendah |

### P1 — High (integritas & keselamatan)

| # | Tindakan | Lokasi | Acceptance |
|---|---|---|---|
| P1-1 | Hitung excursion termasuk sampel terakhir | `core/temperature.py:170-174` | `[5,5,20]` → `outside > 0`; tes baru |
| P1-2 | `evaluation_time` default jam server; tolak masa depan; pisahkan endpoint tulis status | `core/safety.py`, `api/safety.py` | verdict sama tanpa parameter; 422 untuk masa depan |
| P1-3 | Event 3 pakai `CommodityPolicy` per komoditas | `services/event3_service.py:151-158` | beras → `pass`, ayam 9,5 °C → `fail` |
| P1-4 | `bump_generation` di semua jalur hapus entitas ber-blok | `db_mode.py`, `timeseries.py`, `demo_purge.py` | `orphan_blocks` generasi aktif = 0 |
| P1-5 | `init-demo` transaksional + idempoten | `db_mode.py:282-293` | 2× berturut exit 0, row count identik |
| P1-6 | Putuskan metrik KPI ke-8 dan samakan kode/tes/dokumen | `kpi_service.py`, `kamus-kpi` | `len(metrics)` seragam; suite hijau |
| P1-7 | Konsistenkan `invoice_total` vs harga satuan (atau migrasi 4 PO legacy) | `sap_orders.py`, `po_document.py` | `total == unit×qty` ±0,01 |
| P1-8 | Perbaiki `cek_ledger` agar executed-tanpa-blok gagal | `verifier_checks.py:454-461` | `test_agent_verifier_independence` hijau |
| P1-9 | Pisahkan rantai model per agen (jangan ARN AgentCore sbg LLM generik) | `model_registry.py:123-126` | rantai forecast benar |
| P1-10 | Perbaiki routing/otorisasi `admin/*` + token layanan agen | `admin.py`, `MEALCHAIN_API_TOKEN` | bgn_monitor 403 di semua tulis admin |
| P1-11 | Rencana upgrade dependensi (Next, pyjwt, starlette) satu per commit | `package.json`, `requirements` | audit tanpa critical/high; suite hijau |

### P2 — Medium (reliability, UX, maintainability)

- P2-1 Gate hijau: `ruff` 12 → 0; `tsc` 4 → 0 (tambah `target` di `tsconfig`).
- P2-2 Jalankan suite di DB uji bersih; kunci daftar gagal; tutup 30 kegagalan satu per satu.
- P2-3 `alembic check` bersih: deklarasikan `ix_batch_receipts_verdict` di ORM.
- P2-4 Redam polling: gating tab, satukan 4 query komoditas, naikkan interval idle (target <30 req/mnt).
- P2-5 Tambah `app/error.tsx` + `global-error.tsx` + `not-found.tsx`.
- P2-6 Hilangkan "0 saat gagal memuat": state `loading/error` eksplisit + penanda basi.
- P2-7 Konfirmasi untuk "Akhiri sesi" dan "Muat Demo (replace)".
- P2-8 Scope-kan endpoint purge/rebuild demo; batasi start-sesi ke peran yang berhak.
- P2-9 Tambah CHECK pada kolom status; hubungkan/tandai 12 PO tanpa decision.
- P2-10 Observability minimum: request id, structured log, versi+commit di `/health`, health dependency.
- P2-11 Bersihkan 14 komponen mati (±2.739 baris) atau hubungkan; perbaiki NUL byte di `api.ts`.
- P2-12 A11y: nama aksesibel combobox, `aria-selected` yang benar, fokus awal dialog.

### P3 — Continuous improvement

- Dokumentasi: perbarui `Architecture.md`/`Schema.md` untuk status integrasi nyata; hapus rujukan
  `core/observability.py` yang tidak ada; perbarui artefak `openapi.json` atau hasilkan di CI.
- Perbesar coverage: uji tulis end-to-end di stack terisolasi (approve 2 akun → execute → PO), uji
  konkurensi approval ganda, uji restore DB.
- Hapus/arsipkan 105 DB `mealchain_*` sisa; tambahkan retensi.
- Pertimbangkan `gitleaks` + `pip-audit`/`npm audit` sebagai gate CI wajib.

---

## J. EXIT CRITERIA

Audit ini **selesai sebagai audit**, tetapi temuan belum tertutup. Status audit dapat dinaikkan hanya bila:

1. P0-1…P0-5 selesai dengan bukti ulang (bukan patch).
2. `pytest` exit 0 pada DB uji bersih; `ruff` 0; `npm run typecheck` 0; `alembic check` bersih.
3. `current_user` backend = `mealchain_app_login`, dan uji "maintenance door" sebagai role aplikasi
   tetap ditolak trigger.
4. `/ledger/verify` pada generasi aktif: `orphan_blocks = 0`, hash 100 % cocok.
5. KPI: satu daftar metrik resmi, angka di UI = API = hitung ulang SQL.
6. Jembatan Joule tidak lagi menunjuk host asing; `/health.dataset` sama dengan DB aplikasi.
7. Semua kunci hasil AUD-004 terbukti sudah dirotasi.
8. Temuan berstatus `Fixed` diverifikasi ulang dengan tes/ukur, bukan dengan keberadaan patch.

---

## K. JAWABAN EKSPLISIT ATAS TUJUH PERTANYAAN

**1. Tiga risiko terbesar saat ini**
(a) **Kepercayaan pada angka**: aplikasi berjalan sebagai superuser DB dan pintu maintenance ledger
terbuka dari koneksi aplikasi sendiri — jaminan integritas riwayat audit bergantung pada niat baik,
bukan pada hak akses. (b) **Keselamatan vs data**: gerbang keselamatan benar di kode, tetapi
`temperature.py` mengabaikan sampel terakhir dan data demo memuat keputusan `executed` yang melanggar
gerbangnya sendiri — yang dilihat juri adalah bukti yang menyalahkan sistemnya sendiri.
(c) **Klaim integrasi**: jembatan SAP Joule hidup tetapi menyajikan dataset pihak ketiga lewat tunnel
publik tanpa autentikasi, sementara adapter SAP nyata tidak dipanggil siapa pun.

**2. Apakah ada masalah yang membuat jalur transaksi/keputusan tidak aman?**
Ya, tiga: `evaluation_time` dari pemanggil dapat melumpuhkan staleness keselamatan (AUD-008); Event 3
menulis status keselamatan semua komoditas dengan rentang rantai dingin (AUD-009); dan excursion suhu
di ujung log hilang (AUD-007). Jalur **approval → execute** sendiri aman secara kode (scope, kuorum,
revalidasi, sidik bukti, tolak PO ganda) — yang tidak aman adalah **jalur data** yang mengisi tabelnya
dan **jalur tulis status keselamatan**.

**3. Apakah angka dan KPI utama dapat dipercaya?**
Rumusnya ya: SDC 4 keputusan Δ0,00, 41/41 breakdown tepat, 8 KPI cocok saat dihitung ulang.
Yang tidak dapat dipercaya: **cakupan**-nya (5 dari 8 KPI `no_data` hari ini), **label periode**
("Hari ini" padahal jangkar simulasi 8 Okt), dan **rekonsiliasi PO** (4/17 baris `invoice_total` ≠
harga satuan × qty).

**4. Apakah pembatasan role, approval, dan safety gate benar-benar ditegakkan?**
Role & approval: **ya, di server dan DB** (401/403 nyata, IDOR 403 di 7 sub-resource, unique index
empat mata). Safety gate: **di kode ya**, tetapi dilemahkan tiga celah di atas dan oleh data demo yang
tidak mematuhi gerbang. Ledger: ditegakkan terhadap mutasi biasa, **tidak** terhadap koneksi superuser.

**5. Bagian mana yang sudah terverifikasi dan mana yang belum**
Terverifikasi: authn/authz baca, scope lokasi, IDOR baca, RBAC tulis dasar, hash-chain, tipe uang,
rumus SDC/KPI, trigger ledger, gate statis, integrasi nyata SAP/AWS/Joule.
Belum: IDOR **tulis** end-to-end, panggilan model nyata, load/performance, restore/DR, viewport kecil &
screen reader, invoke AgentCore, konfigurasi destination/DA Joule, ACL berkas rahasia.

**6. Urutan perbaikan paling tepat**
P0-1 (putus klaim integrasi) → P0-3 (tutup kredensial demo) → P0-2 (rotasi) → P0-4 (least privilege,
karena membuka jalan P1-1…P1-4 diverifikasi) → P0-5 (data demo patuh gerbang) → P1-1/P1-2/P1-3
(keselamatan) → P1-4/P1-5 (lifecycle data) → P1-6/P1-7 (angka) → P1-8/P1-9/P1-10 (agen & routing) →
P1-11 (dependensi) → P2.

**7. Bukti minimum sebelum tahap berikutnya**
(a) suite backend hijau di DB bersih + `ruff`/`tsc`/`alembic check` hijau; (b) `current_user` role
least-privilege + bukti trigger menolak UPDATE sebagai role itu; (c) `/ledger/verify` tanpa
`coverage_warning` pada generasi aktif; (d) KPI di UI = API = SQL, dengan daftar metrik tunggal;
(e) satu alur tulis end-to-end terekam di stack terisolasi (propose → verify → approve 2 akun →
execute → PO → ledger); (f) `/health` setiap komponen melaporkan commit + dataset yang cocok dengan DB;
(g) catatan rotasi kunci bertanggal.

---

## L. DEKLARASI INTEGRITAS AUDIT

- **Tidak ada** source code, migrasi, konfigurasi, atau data demo yang diubah. Working tree tetap 146
  entri seperti awal.
- Database demo `mealchain` diukur ulang sebelum dan sesudah (11:23 → 11:40) dengan angka **identik**.
- Uji destruktif (UPDATE ledger, `init-demo`, downgrade) hanya dijalankan pada DB **klon**.
- Tidak ada nilai rahasia yang dikutip; hanya nama kunci, panjang, dan `file:baris`.
- Tidak ada panggilan model berbayar.
- Angka yang dikutip berasal dari eksekusi sesi ini atau laporan sub-reviewer yang disebutkan
  sumbernya; klaim sub-reviewer yang tidak saya ulang ditandai **SR**, bukan **AU**.
- Insiden alat dicatat di §D dan hasil yang tidak sah dibuang.
