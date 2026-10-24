# AUDIT.md — MealChain Guardian (checkout `E:\hackathon\HackathonAWS\mealchain-guardian`), independent pre-deployment audit

> Fase 1 (read-only). Kerangka: `E:\hackathon\audit-template\AUDIT_TEMPLATE.md`.
> Dokumen ini snapshot titik-waktu; perbaikan TIDAK dikerjakan di sini.

## 1. Executive summary

| Item | Value |
|---|---|
| Audit date | 2026-10-23, 22:45–23:35 WIB (UTC+07) |
| Audited commit | `a08d25e` ("demo: panduan panggung 5 halaman …"), branch `feature/db-modes-demo-coverage`, ahead 310 / behind 0 dari `origin/master` |
| Working tree | **tidak bersih** — 131 entri (68 `M`, 63 `??`); yang dimodifikasi mencakup `agent/*` (10 berkas), `backend/app/api/demo.py`, `backend/app/seed/*`, `frontend/lib/kpi.ts`, `TODO.md`; untracked termasuk `backend/uv.lock`, `docs/*.pdf`, `_qa/*` |
| Runtime | compose 4 layanan hidup (`backend`, `frontend`, `mock-sap`, `postgres`); Postgres 16.15; migrasi head `030_approval_four_eyes_unique`; frontend berjalan sebagai **`next dev`** |
| Scope | seluruh repo checkout ini (984 berkas tracked). Checkout kedua (`E:\hackathon\HackathonBil\MealChainGuardian`, repo publik untuk GitHub Pages) **tidak** diaudit selain satu pemeriksaan riwayat `.env` (§15). §3 menyatakan cakupan yang tidak diperiksa |
| Verdict | **NO-GO untuk deployment publik — GO bersyarat untuk demo lokal di depan juri** (lihat §20) |

**What holds up.** Disiplin read-only terjaga: hanya `GET` + `POST /auth/login` yang dijalankan, tidak ada `POST/PUT/PATCH/DELETE` lain, tidak ada push/deploy. Autentikasi berfungsi nyata: 7 akun demo `200`, tanpa token `401`, peran salah `403`, lokasi di luar cakupan `403` (R). Garda empat mata approval, verifikasi, dan penolakan eksekusi safety-FAIL terbukti bekerja di atas kode (`approval_summary` + requirement 2 peran). Sisi otomatis juga sehat: frontend `tsc` 0, `next lint` 0, `npm run build` sukses (4 rute statis), `vitest` **161 berkas / 1764 tes**; backend **1300 tes lulus / 0 gagal / 17 skip** pada DB salinan. Ledger hash-chain `GET /ledger/verify` → `valid: true` atas 353 blok (R).

**What blocks deployment.** (1) **SEC-01** — `.env` berisi kunci hidup pernah di-commit (`c4d22b3`); 42 nilainya masih identik dengan `.env` sekarang, termasuk `POSTGRES_PASSWORD`, `INFERHUB_API_KEY`, dan `SIGNING_KEY_HEX` (kunci tanda tangan dossier). (2) **SEC-02** — `JWT_EXPIRE_MINUTES=5256000` (±10 tahun): token demo tidak pernah kedaluwarsa, dan disimpan di `localStorage`. (3) **KPI-01** — *diperbaiki 2026-10-24: Meal Continuity 24 jam 0,00% → 100,00%; lihat §9* — KPI "Meal Continuity" di jendela 24 jam **selalu mengabaikan rencana hari ini** (`plan_date < CAST(end AS date)`), sehingga kartu unggulan demo menampilkan **0,00%** padahal 1.202 porsi Jakarta terkirim hari ini di dalam jendela. (4) ~~**DB-01**~~ *(diperbaiki 2026-10-24: `alembic check` bersih)* — tabel `ledger_blocks` (353 baris) hanya ada di DB, tidak di ORM, sehingga `--autogenerate` akan mengusulkan **DROP**; 20 indeks & 5 tipe kolom menyimpang. (5) ~~**DEP-01**~~ *(diperbaiki 2026-10-24: image `runner` `next start` + healthcheck backend)* — image/compose frontend menjalankan `next dev`, bukan hasil build produksi. (6) **DEP-04** — 9 berkas tes backend (`test_agent_*`) tidak bisa dikoleksi di image yang dikirim (`ModuleNotFoundError: agent`).

## 2. Methodology

**Inspected.** `AGENTS.md`, `Rules.md`, `TODO.md` (500 baris), `docker-compose.yml` + override, `backend/Dockerfile`, `frontend/Dockerfile`, `.gitignore`, `.env` (hanya **nama** kunci + panjang nilai), `git log`/`git show` riwayat `.env`, `backend/app` (auth, kpi_service, actions, demo, models, seed), `frontend/lib` (query/kpi/refresh), `openapi.json` live, skema DB live (`information_schema`, `pg_constraint`, `pg_stat_user_tables`), 3 dump di `data/backups/`.

**Executed fresh on the audited commit.**

| Check | Command | Result |
|---|---|---|
| Lint backend | `docker compose exec backend ruff check app tests` | **30 error** (19 `app`, 11 `tests`): 8 `I001`, 4 `F401`, 1 `F841`, 1 `W293`, 1 `N818`, sisanya `E501`. 12 auto-fixable |
| Lint frontend | `npx next lint` | `✔ No ESLint warnings or errors` |
| Typecheck | `npx tsc --noEmit` | exit 0 |
| Unit/integration test (FE) | `npx vitest run` | **161 berkas / 1764 tes lulus**, 43,70 dtk |
| Unit/integration test (BE) | `docker exec --env-file … pytest -q --ignore=9 berkas test_agent_*` (DB salinan) | **1300 lulus / 17 skip / 0 gagal**, 539,66 dtk (§2a) |
| Build | `npm run build` | **sukses**, 4 rute statis, `/` First Load JS 422 kB; warning `webpack.cache … Snapshot resolve dependencies` (exFAT) |
| Dependency audit (py) | `pip-audit -f json` di container sekali-pakai | 73 paket diaudit, **7 paket rentan / 55 advisory** |
| Dependency audit (npm) | `npm audit --json` | 628 dependensi, **15 rentan (4 critical, 5 high, 6 moderate)** |
| Schema drift | `alembic current` / `heads` / `check` | head `030…` (sama di DB & kode), **`alembic check` FAILED** (rincian §8) |
| Probe endpoint | skrip `audit_probe.py` (di dalam kontainer, login + GET) | 7 akun `200`; 27 path × 7 peran; `401` tanpa token; `403` peran/cakupan (rincian §7) |
| Query DB read-only | `psql -c "SELECT …"` (hitung baris, FK, orphan, date anatomy) | rincian §8/§13 |

### 2a. Hasil tes backend (angka final)

`docker exec --env-file <scratch>/audit-env mealchain-backend python -m pytest -q --ignore=tests/test_agent_*.py`
→ **1300 passed, 17 skipped, 0 failed, 2 warning, 539,66 dtk (8:59)** pada DB salinan `mealchain_audit` (`DEMO_SESSION_ENFORCE=false`), dikonfirmasi oleh baris pertama log: `DB= mealchain_audit | user= mealchain` (bukan DB kerja). Warning: 1 deprecation Starlette, 1 `SAWarning` "garbage collector … non-checked-in connection" (indikasi connection pool tidak ditutup rapi di satu tes — P3, belum jadi temuan tersendiri).
Berkas yang **tidak** dikoleksi: 9 berkas `test_agent_*` (DEP-04) — *diperbaiki 24 Okt 2026: kini dikoleksi dan berjalan di dev (mount `agent/`), dilewati dengan jujur di image tanpa mount; lihat §21.*

**Read-only discipline.** Tidak ada berkas repo yang diubah kecuali `AUDIT.md` ini. Skrip probe disimpan di luar repo (`%LOCALAPPDATA%\hermes\cache\scratch\`). Tes backend diarahkan ke DB **salinan** (`mealchain_audit`, dibuat dari `pg_dump` DB kerja) — DB kerja tidak ditulis oleh tes. Tidak ada `deploy`, `git push`, atau panggilan layanan berbayar. Artefak yang tertulis sebagai efek samping alat: `frontend/.next/` (hasil `npm run build`), DB `mealchain_audit`, dan container sekali-pakai untuk `pip-audit`.

**Evidence levels.** S = pembacaan statis · U = tes otomatis · R = HTTP runtime · D = query DB · B = browser (tidak dipakai di fase 1).

**Not tested.** (a) Seluruh alur tulis dan UI di browser (klik approve/execute, animasi peta, tab Demo Control) — fase 2. (b) 9 berkas tes `test_agent_*` (butuh paket `agent/` di root repo + dependensi AWS). (c) Panggilan hidup ke Bedrock/AgentCore/SAP AI Core/OSRM — tidak dipanggil sama sekali di audit ini. (d) Beban/performa, konkurensi, race. (e) Aksesibilitas, responsif, mobile. (f) Uji restore dump (hanya keberadaan dump yang diperiksa). (g) Checkout kedua `HackathonBil` (hanya riwayat `.env`). (h) Rotasi/validitas kunci AWS/SAP — tidak ada panggilan keluar.

**Tooling incidents.** (1) Run pytest pertama gagal karena container `docker run` tidak memuat `/data/seed/sprint1_seed.json` (data di-mount oleh compose, tidak ada di image) — diulang memakai kontainer kerja + `DATABASE_URL` diarahkan ke DB salinan. (2) Run kedua gagal `ModuleNotFoundError: agent` — 9 berkas di-`--ignore`, dan fakta itu dicatat sebagai temuan DEP-04, bukan diperbaiki. (3) Run ketiga **tidak sah**: URL DB yang dibentuk lewat `sed` dari `.env` (berkas CRLF) rusak menjadi user `mealchain_audit?` sehingga 665 error adalah kegagalan autentikasi, bukan kegagalan kode — hasilnya dibuang dan dijalankan ulang dengan env-file yang bersih. (4) Dua percobaan awal menulis log ke `/tmp` MSYS yang tidak terbaca oleh Python native Windows — path dipindah ke direktori scratch. (5) Build pertama gagal karena rantai perintah `| python -c` (stdin bukan tty) — diulang tanpa pipa. (6) **DB kerja berubah di tengah audit** (data demo dibangun ulang oleh aktor lain ±23:00 WIB: `delivery_events` 360 baris, `menu_plans` sampai 5 Nov 2026). Semua angka DB di dokumen ini adalah snapshot pada jam yang dicantumkan, bukan keadaan stabil.

## 3. Repository coverage

984 berkas tracked: 426 `.py`, 173 `.ts`, 128 `.tsx`, 126 `.md`, 30 `.json`, 16 `.yaml`, 13 `.sh`, 17 `.png`. 74 path API / 76 operasi. 23 tabel DB, 21 di antaranya ada di ORM.

| Area | Diperiksa | Diuji runtime | Catatan |
|---|---|---|---|
| `backend/app/api` (auth, kpi, actions, demo, receipts, waste, admin) | ya (sebagian) | ya (GET) | jalur tulis hanya dibaca statis |
| `backend/app/services` (kpi, supplier_eligibility, demo_*) | ya (kpi, actions) | tidak | logika domain lain tidak ditelusuri penuh |
| `backend/app/seed` | ya (seed_data, demo_*) | tidak | nilai seed diambil dari DB |
| `backend/app/models` + migrasi | ya | ya (`alembic check`) | drift ditemukan |
| `frontend/components` (10 tab) | sebagian | tidak (fase 2) | — |
| `frontend/lib` (query, kpi, refresh) | ya | ya (vitest) | — |
| `sap-joule/`, `agent/`, `infra/`, `scripts/`, `mockupui/` | tidak | tidak | di luar fase 1 |
| `docs/` (126 `.md`) | sebagian (`Rules`, `TODO`, `Architecture` sekilas) | tidak | — |
| `verify/` (suite verifikasi) | tidak | tidak | fase 2 |

Coverage is **not complete**. Area terbuka: alur tulis (approve/execute/reset), UI/browser, lapisan agen & integrasi eksternal, `sap-joule`, `infra/`, dokumen verifikasi lama.

## 4. SSOT authority and reconciliation

`AGENTS.md` menetapkan urutan otoritas: `IDEA.md` → `TODO.md` (sumber kebenaran status) → `Rules.md` → `workflows.md` → `Roadmap.md` → `docs/*`. `memory/global/decisions.md` wajib di-append untuk keputusan baru.

Konflik yang ditemukan:

- **Rules.md §"Tidak ada secret di kode — semua lewat `.env`"** bertentangan dengan fakta: `.env` pernah di-commit (SEC-01). Aturannya benar, pelaksanaannya tidak.
- **Dokumen verifikasi lama** (`docs/design.md`, `docs/verification/*`) menyebut KPI 24 jam "7/7"; live hari ini `6/7` dengan Meal Continuity `0,00%`. Angka dokumen ≠ angka sistem (KPI-01). `TODO.md` sendiri sudah memuat catatan pembaruan 23 Okt, tetapi dokumen verifikasi tidak.
- **`TODO.md` vs kode**: status "Done" untuk beberapa berkas yang kini tidak lolos `alembic check` (model `ledger_blocks` tidak pernah ada di ORM). Ini temuan SSOT-01 (P3): status task tidak mencerminkan drift teknis.

## 5. Feature inventory and functional status

| Fitur | Status nyata (bukti) |
|---|---|
| Login 7 akun demo | Berfungsi (R: 7×`200`, `401` tanpa token, `403` peran salah) |
| 10 tab konsol (Hari Ini, Overview, Recommendations, Decision & Evidence, Keamanan Pangan, Surplus & Limbah, Pemasok, Agent Log, KPI & Kualitas Agen, Demo Control) | Ada di nav (B/S sebelumnya), **tidak diuji** fase 1 |
| KPI 7 metrik, 3 jendela | Endpoint jalan (R), **Meal Continuity salah di jendela 24 jam** (KPI-01) |
| Decision chain / dossier / compliance / approval-summary | `200`, dossier `signature.state=signed` (ECDSA secp256k1) (R) |
| Ledger hash-chain | `valid: true`, 353 blok, **256 blok yatim** (DB-02) |
| Buat/approve/execute keputusan | Tidak diuji (butuh POST; fase 2) |
| Agent swarm / Bedrock / AgentCore | Tidak dipanggil (fase 2) |
| Demo Control (siapkan data, jalankan agent, reset) | Tidak diklik (read-only) |

## 6. Button and UI control audit

**Not inspected (fase 1).** Bukti yang ada hanya statis: `frontend/components` memuat 10 tab dan panel Demo Control; tombol "Jalankan agent" dibatasi `role === "sppg_head"` (S, dibaca dari kode). Audit kontrol per-tombol/per-peran butuh browser + klik → fase 2.

## 7. Authentication, session, RBAC and scope

Matriks hasil probe (R, 27 path × 7 akun):

| Uji | Hasil |
|---|---|
| Tanpa token: `/health`, `/kpi`, `/decisions`, `/admin/users` | `200`, `401`, `401`, `401` |
| Login 7 akun `@demo.local` | `200` semua |
| `/admin/users`, `/admin/locations` | `403` untuk 6 akun SPPG; **`200` untuk `bgn_monitor`** |
| `/demo/agent/*`, `/demo/data-status` | `403` untuk `bgn_monitor`; `200` untuk SPPG |
| `/price|supply|demand|balance /Jakarta/*` dari akun Bandung/Surabaya | `403 "lokasi di cakupan lokasi di luar SPPG Anda"` |
| Operasi tanpa `security` di OpenAPI | hanya `GET /health` dan `POST /auth/login` |

Temuan: **SEC-02** (JWT 10 tahun), **SEC-03** (tanpa pembatas percobaan login; kata sandi demo ada di `DEMO_USERS` dalam kode), **SEC-04** (`/docs`, `/redoc`, `/openapi.json` publik, `200`), **AUTH-01** (P3): `bgn_monitor` — peran read-only lintas kota — justru satu-satunya yang boleh membaca `/admin/users` dan `/admin/locations`; perlu keputusan owner apakah itu disengaja.

## 8. Backend, API and database

- **Kontrak**: 74 path, 76 operasi; validasi input terlihat pada `422` yang tepat (mis. `/agenda` tanpa `start`, `/balance/map` tanpa `commodity`) — bukan cacat.
- **Drift ORM↔DB — DB-01. STATUS: DIPERBAIKI 2026-10-24** (`alembic check` → *"No new upgrade operations detected."*; ORM 22 tabel termasuk `ledger_blocks`, tes ledger 6 lulus). Temuan aslinya (D):
  - `remove_table ledger_blocks`: tabel 353 baris ada di DB, **tidak ada di `app/models`** (21 tabel ORM vs 23 tabel DB). `--autogenerate` akan mengusulkan DROP tabel ledger.
  - `remove_index` ×±20: indeks dibuat lewat SQL migrasi (`idx_supply_latest`, `idx_decisions_demo_case`, `uq_delivery_events_source_ref`, `idx_users_location`, dll.) tidak dideklarasikan di model.
  - `modify_type` ×5: `decisions.origin`, `delivery_events.origin`, `disposal_events.origin` = `varchar` di DB vs `Text` di model; `batches.quarantine_status` = `text` vs `String`; `disposal_events.quantity_kg` = `numeric(12,2)` di DB vs `Numeric(10,2)` di model → **ORM lebih sempit dari DB** (nilai > 9.999.999,99 ditolak aplikasi walau DB menerima).
- **Integritas**: 0 `approvals` yatim, 0 `agent_traces` yatim, 0 `decisions` tanpa `target_location` (D). 87 indeks di `public`.
- **Hibrida**: 23 `sap_mock_*` PO, 40 `approvals`, 90 `decisions`, 417 `agent_traces`.

## 9. Domain logic and numeric QA/QC

**KPI-01 (Confirmed, D+R) — Meal Continuity mengabaikan hari ini.** `backend/app/services/kpi_service.py` memakai:

```
WHERE mp.plan_date >= CAST(:start AS date) AND mp.plan_date < CAST(:end AS date)
```

`end` = sekarang (bukan tengah malam), jadi `CAST(:end AS date)` = **hari ini** dan rencana bertanggal hari ini **tidak pernah** masuk hitungan jendela apa pun. Bukti hari ini (23 Okt 23:08 WIB):

| Fakta | Angka |
|---|---|
| Rencana Jakarta hari ini (`plan_date = 23 Okt`) | 1.202 porsi |
| Kiriman Jakarta hari ini, `delivered_at` di dalam jendela 24 jam | 1.202 porsi |
| KPI Meal Continuity 24 jam yang ditampilkan | **0,00%** |
| KPI Meal Continuity 7 hari / 1 bulan | 85,42% / 72,15% (hari ini tetap tidak dihitung) |

Akibat: kartu unggulan demo bisa menampilkan 0,00% walau operasi hari itu berjalan penuh; dan setiap jendela kehilangan tepat satu hari (hari ini). Ini juga yang membuat "KPI pengiriman tidak naik saat truk tiba" — bukan karena animasi, tetapi karena barisnya memang tidak pernah dibaca untuk hari ini.

Reproduksi angka (D, `psql`, 23 Okt 23:1x WIB, akun Jakarta):

| Predikat | Penyebut (rencana) | Pembilang (terkirim) | Hasil |
|---|---|---|---|
| Sekarang: `plan_date >= start::date AND plan_date < end::date` | 1.179 (22 Okt) | 0 | **0,00%** |
| Inklusif: `plan_date <= end::date` | 2.381 (22+23 Okt) | 1.202 (23 Okt) | **50,48%** |

**STATUS: DIPERBAIKI 2026-10-24 00:2x WIB** (P1 → ditutup). Perubahan: `backend/app/services/kpi_service.py` — pembilang tidak lagi difilter `delivered_at` (difilter lewat `plan_date` yang sama dengan penyebut) dan batas atas jadi inklusif, plus konversi WIB eksplisit (`Asia/Jakarta`) agar 00:30 WIB tidak jatuh ke tanggal kemarin versi UTC. Tes kontrak baru `backend/tests/test_kpi_batas_tanggal.py` (5 tes, RED → GREEN). Bukti live: Meal Continuity 24 jam Jakarta **0,00% → 100,00%**; 7 hari **85,42% → 100,00%**; 46 tes KPI/demo lulus tanpa regresi. Rincian berikut adalah temuan aslinya (dibiarkan sebagai catatan).

**Akar masalahnya dua lapis** (KPI-01 = lapis pertama, desain = lapis kedua):
1. **Hari ini tidak pernah masuk** (`<` bukan `<=`). Ini murni bug.
2. **Sumbu waktu pembilang ≠ penyebut.** Penyebut memakai `plan_date`, pembilang memakai `delivered_at` di dalam jendela. Untuk jendela bergulir 24 jam yang berakhir pukul 23:00, rencana kemarin ikut ke penyebut tetapi kirimannya (kemarin siang) sudah keluar jendela → rasio maksimum secara struktural ±50%, bukan 100%. Karena itu perbaikan `<=` saja **tidak** menghasilkan 100,00%; definisi jendela harus diputuskan owner (lihat §18 #6).

Lain-lain: `delivery_events` hari ini 10 baris/11.779 porsi, `disposal_events` 78, `price_signals` 5.866. Angka KPI lain bergerak antar-build (Susut `no_data` sekarang, sempat 0,29–1,15%; Simpangan 2,64→12,46%) karena data demo ditulis ulang relatif `now`, bukan karena rumus berubah — jadi angka 24 jam tidak stabil sebagai bukti apa pun kecuali disebut jam pengambilannya. Bug batas tanggal juga mengenai akun global: BGN 24 jam Meal Continuity `0,00%` walau `7/7` metrik tersedia. Tidak ada probe deterministik KPI (n/n PASS) dijalankan — **not tested**.

## 10. Lifecycle guards

Bukti statis (S) yang kuat: `execute` menolak `review_only`, `executed`, `belum terverifikasi`, `rejected`, `expired`, status tak sah, approval belum memenuhi requirement, dan approval di luar cakupan lokasi; safety revalidation batch sumber dijalankan ulang saat eksekusi. `approvals` dijaga constraint empat mata (`030_approval_four_eyes_unique`). Uji perilaku 409/403 end-to-end **tidak** dijalankan (butuh POST; fase 2).

## 11. AI/agent/integrasi eksternal

`GET /integrations/status` (R) mengembalikan kategori per komponen (`contract_tested`, `configured`, `provisioned`, `fail_closed`, `unavailable`, `not_started`) dengan `probes_run: 0` — **tidak ada probe hidup** di audit ini. `MULTI_AGENT_REVIEW=true` di `.env`. Dossier `signed` dengan ECDSA (R) → jalur tanda tangan berjalan tanpa panggilan model. Pemanggilan Bedrock/AgentCore/SAP **not tested** (§2). Risiko anti-fabrikasi tidak dinilai di fase 1.

## 12. Event/demo mode

- `DEMO_SESSION_ENFORCE=false` di `.env` saat audit → isolasi sesi demo **mati**; 4 sesi demo berstatus `expired` tetap ada di DB.
- Konsekuensi: data demo dan data kerja berada di tabel yang sama (`decisions` 90, `sap_mock_purchase_orders` 23, `approvals` 40). Jalur "Akhiri sesi" tidak membersihkan apa pun dalam mode ini.
- 28 dari 35 baris `users` adalah residu suite (`@test.local`, `@uji-*`) — **DB-03, Confirmed (D)**. Akun residu bukan akun demo, tetapi ikut tampil di `/admin/users`.
- Risiko menghapus data nyata: rendah hari ini (semua data adalah data demo/seed), tetapi tidak ada pembeda tegas yang aktif di runtime.

## 13. Analytics/KPI

Definisi diambil dari `kpi_service.py` (S): Meal Continuity = Σ porsi terkirim / Σ porsi rencana per tanggal rencana; Avoidable Food Loss = kg disposal / kg pasokan; Imbalance = akar keputusan tereksekusi / terdeteksi (mengecualikan `demo_case`); Safe Delivered Cost = median/agregat PO dalam jendela; Price Deviation = |harga kutipan − referensi| / referensi; Decision Time = DETECT→ACT per keputusan committed; Evidence Completeness = keputusan dengan ≥2 jenis bukti konsisten **sebelum** approval pertama.

Angka live 23 Okt 23:08 WIB (R) — Jakarta: 24 jam **6/7 tersedia** (Meal Continuity 0,00; Imbalance 66,67; SDC Rp18.524.096,43; Simpangan 12,46; Decision Time 20,00 mnt; Evidence 100,00; Susut `no_data`), 7 hari 7/7, 1 bulan 7/7. Global BGN 24 jam 7/7.

Cacat yang dikonfirmasi: **KPI-01** (batas tanggal), **KPI-02** (P3): `state` dibedakan `no_data` vs nilai, tetapi `no_data` disajikan sebagai "—" tanpa membedakan "belum ada data" dan "penyebut nol" — dua sebab berbeda, satu tampilan. Label keadaan ada, tetapi penyebab tidak.

## 14. End-to-end test matrix

**Not executed (fase 1).** Yang ada hanya matriks baca: 27 GET × 7 peran (`§7`) + 6 endpoint detail keputusan. Alur tulis (Event 1 → propose → verify → approve ×2 → execute; Event 3 safety; reset demo) belum dijalankan di audit ini.

## 15. Security and privacy

| Temuan | Bukti |
|---|---|
| **SEC-01 P0/P1** `.env` pernah di-commit (`c4d22b3`, 94 baris, 67 kunci). 42 nilai masih identik dengan `.env` sekarang — termasuk `POSTGRES_PASSWORD` (15), `INFERHUB_API_KEY` (32), `SIGNING_KEY_HEX` (64), `SAP_AI_CORE_CLIENT_ID` (60). 13 kunci sudah diganti (termasuk `AWS_SECRET_ACCESS_KEY`, `JWT_SECRET`, `SAP_AI_CORE_CLIENT_SECRET`). | S+D (`git show c4d22b3:.env` vs `.env`, dibandingkan per kunci; **nilai tidak dicetak**) |
| **SEC-02 P1** `JWT_EXPIRE_MINUTES=5256000` (≈10 tahun), `HS256`, token disimpan `localStorage` (`app/page.tsx:709`) → XSS = pencurian token permanen. `JWT_SECRET` 64 char (kuat) tetapi panjangnya tidak divalidasi kode. | R+S |
| **SEC-03 P1** tidak ada rate-limit/lockout login; kata sandi 7 akun demo tertulis di `DEMO_USERS` (`app/seed/seed_data.py`) dan dipakai UI tombol cepat. | S |
| **SEC-04 P2** `/docs`, `/redoc`, `/openapi.json` publik `200` (76 operasi + skema). | R |
| **SEC-05 P2** tidak ada header keamanan (CSP, X-Frame-Options, HSTS) di `next.config.js` maupun middleware FastAPI. | S |
| **SEC-06 P2** dependensi: npm **4 critical** (`next 14.2.14`, `maplibre-gl 4.7.1` XSS sanitizer bypass, `vitest 2.1.9`, `tinypool`), 5 high, 6 moderate; Python **7 paket / 55 advisory** (`pyjwt 2.9.0` ×22, `starlette 0.38.6` ×14, `ecdsa 0.19.2` ×2 tanpa fix, `certifi`, `python-dotenv`, `pytest`, `pip`). | D |
| **SEC-07 P3** kunci privat TLS `mealchain-guardian.tailda91db.ts.net.key` + `.crt` ada di working tree (untracked, `.gitignore` menutup `*.key`/`*.crt`). | S |
| **SEC-08 P3** `secrets/aws-app.env` (kunci AWS akun baru) ada di disk, di-`.gitignore`; dibaca compose sebagai `env_file` kedua. Aman selama tidak ter-commit. | S |

**Repo publik (`HackathonBil/MealChainGuardian`, remote `git@github.com:munk23zzz/MealChainGuardian.git`)**: tidak ada commit yang menyentuh `.env` — pemeriksaan riwayat mengembalikan kosong. Jadi kebocoran SEC-01 terbatas pada repo kerja privat ini.

## 16. Build, infrastructure and deployment readiness

| Item | Keadaan |
|---|---|
| Backend image | `python:3.12-slim` (tag bergerak, tanpa digest), `pip install -r requirements.txt` (18/19 pin `==`) |
| Frontend image | **DIPERBAIKI 2026-10-24**: 4 stage (`deps` → `dev` / `builder` → `runner`). `runner` = `NODE_ENV=production`, `npm ci --omit=dev`, hasil `next build`, `CMD npm run start` (= `next start`), user non-root. Stack dev memakai target `dev` (perilaku lama), stack produksi `docker-compose.prod.yml` memakai `runner` |
| Build produksi | `npm run build` **berhasil** di host dan **sekarang dipakai image** (`builder` → `runner`). Bukti 2026-10-24: `mealchain-frontend-prod:latest` dibangun dari target `runner`; container uji menyajikan `:3011/` = 200, `/kpi` diteruskan ke uvicorn (401 `{"detail":"butuh Bearer token"}`), endpoint dev-only `/__nextjs_original-stack-frame` = **404** (di `next dev` :3010 = 400), `Config.Cmd` = `["npm","run","start"]`. **Belum diverifikasi**: `docker compose -f docker-compose.prod.yml up -d` penuh (percobaan menabrak Docker Desktop yang macet — lihat §21) |
| Healthcheck | `postgres`, `frontend`, **dan `backend`** (baru 2026-10-24: GET `/health` via python urllib). Terverifikasi di stack dev: `mealchain-backend … (healthy)`, dan frontend baru dinyalakan setelah backend healthy (`depends_on: condition: service_healthy`) |
| CI | **tidak ada** `.github/workflows` |
| Migrasi | `alembic upgrade head` tersedia; head `030` sama di DB & kode; `alembic check` gagal (DB-01) |
| Backup | 3 dump manual di `data/backups/` (`pre-dbfix-*`, `mealchain-pra-demo-2026-10-21.dump`); **tidak ada jadwal/otomasi**; uji restore tidak dilakukan |
| TLS | sertifikat Tailscale ada di disk, tidak dipasang di compose (frontend/backend HTTP polos) |
| Observability | log container + `ledger`; tidak ada metrik/tracing |
| Secret runtime | `.env` + `secrets/aws-app.env` dibaca `env_file`; tidak ada secret manager |

## 17. Defect register

| ID | Sev | Class | Summary | Evidence | Status | Blocking |
|---|---|---|---|---|---|---|
| SEC-01 | P1 | Security | **(terbuka — butuh pemilik)** `.env` pernah di-commit; 42 nilai masih sama dengan sekarang (termasuk `POSTGRES_PASSWORD`, `INFERHUB_API_KEY`, `SIGNING_KEY_HEX`) → anggap semua kunci itu bocor; wajib rotasi + bersihkan riwayat bila repo dibagikan | §15 | Confirmed (S/D) | Yes |
| SEC-02 | P1 | Security | ~~`JWT_EXPIRE_MINUTES=5256000` ⇒ token praktis abadi~~ **DIPERBAIKI 2026-10-24**: `.env` 720 menit, nilai dijepit 5–1440 di `auth._expire_minutes()`, tes mengunci perilaku; token tetap di `localStorage` (residu, butuh CSP) | §15 | Fixed | Yes |
| SEC-03 | P1 | Security | ~~Tidak ada pembatas percobaan login~~ **DIPERBAIKI 2026-10-24**: `app/core/rate_limit.py` (20 gagal/60 dtk per IP+email, 429 + `Retry-After`, reset saat berhasil). Kredensial demo tetap di kode **by design** (akun demo publik, hanya ada di DB demo) — residu terdokumentasi | §15 | Mitigated | Yes (publik) |
| KPI-01 | P1 | Data | Meal Continuity mengabaikan rencana hari ini (`plan_date < CAST(end AS date)`) + pembilang difilter `delivered_at` (sumbu waktu beda) ⇒ 0,00% walau 1.202 porsi terkirim hari ini | §9 | **Fixed 2026-10-24** (5 tes baru, live 0,00%→100,00%) | No (ditutup) |
| DB-01 | P1 | Data | `alembic check` gagal: `ledger_blocks` (353 baris) tak ada di ORM (autogenerate → DROP), ±20 indeks hanya di migrasi, 5 tipe kolom menyimpang (`quantity_kg` ORM lebih sempit dari DB) | §8 | **Fixed 2026-10-24** (`alembic check` bersih, 6 tes ledger lulus) | No (ditutup) |
| DEP-01 | P1 | Deploy | Image & compose frontend menjalankan `next dev` (bukan hasil build produksi); tidak ada healthcheck backend | §16 | **Fixed 2026-10-24** (target `runner` = `next build`+`next start`; healthcheck backend terpasang & terverifikasi `healthy`) | No (ditutup) |
| DEP-04 | P2 | Deploy | ~~9 berkas tes `test_agent_*` tak bisa dikoleksi di image (`ModuleNotFoundError: agent`)~~ **DIPERBAIKI 2026-10-24**: mount `./agent:/agent:ro` + `PYTHONPATH=/app:/` di dev compose, `pytest.importorskip("agent")` di tiap berkas → 96 tes agen BERJALAN di dev dan DILEWATI (bukan error) di image tanpa mount | §2 | Fixed | No (CI) |
| SEC-04 | P2 | Security | `/docs`, `/redoc`, `/openapi.json` terbuka tanpa autentikasi | §15 | **Fixed 24 Okt** — 404 default, terbuka hanya bila `ENABLE_DOCS`/`DEBUG` | Ya (`test_security_headers.py`) |
| SEC-05 | P2 | Security | Tidak ada CSP/X-Frame-Options/HSTS | §15 | **Fixed 24 Okt** — header di backend (JSON) dan `next.config.js` (HTML) | Ya (6 tes + curl) |
| SEC-06 | P2 | Security | 15 kerentanan npm (4 critical, termasuk `next` & `maplibre-gl`) dan 55 advisory Python (pyjwt ×22, starlette ×14, ecdsa tanpa fix) | §15 | Confirmed (D) | No (publik: wajib) |
| DB-02 | P2 | Data | 256/353 blok ledger menunjuk entitas yang sudah dihapus (coverage 27,5%); `/ledger/verify` tetap `valid: true` | §8 | Confirmed (D/R) | No |
| DB-03 | P2 | Data | 28 residu akun uji (`@test.local`, `@uji-*`) di DB demo, tampil di `/admin/users` | §12 | Confirmed (D) | No |
| EVT-01 | P2 | Lifecycle | `DEMO_SESSION_ENFORCE=false` ⇒ isolasi sesi demo mati; data demo & kerja bercampur; "Akhiri sesi" tidak membersihkan | §12 | Confirmed (R/D) | No (demo) |
| LINT-01 | P3 | Docs/UI | 30 error ruff (8 `I001`, 4 `F401`, 1 `F841`, 1 `W293`, 1 `N818`, sisanya `E501`) | §2 | Confirmed | No |
| AUTH-01 | P3 | Authz | `bgn_monitor` (read-only lintas kota) satu-satunya peran yang boleh `/admin/users` & `/admin/locations` | §7 | Confirmed (R) | No |
| KPI-02 | P3 | Data | `no_data` tidak membedakan "belum ada data" vs "penyebut nol"; penyebab tidak dikirim | §13 | Confirmed (S) | No |
| SSOT-01 | P3 | Docs | Dokumen verifikasi lama menyebut KPI 7/7 sementara live 6/7 & 0,00%; status "Done" tidak mencerminkan drift `ledger_blocks` | §4 | Confirmed | No |
| DEP-02 | P3 | Deploy | Tidak ada CI; build/typecheck/test hanya manual | §16 | Confirmed | No |

## 18. Owner decisions required

| # | Keputusan | Kenapa perlu owner | Default bila tidak diputuskan |
|---|---|---|---|
| 1 | Rotasi kunci (`POSTGRES_PASSWORD`, `INFERHUB_API_KEY`, `SIGNING_KEY_HEX`, `SAP_AI_CORE_CLIENT_ID`) + bersihkan riwayat `.env` (filter-repo/BFG) atau terima repo privat selamanya | Menyangkut kredensial hidup & histori git yang tidak bisa "dibatalkan" | Anggap bocor; rotasi sebelum repo dibagikan/di-push ke remote lain |
| 2 | Masa berlaku token: 30 menit (produksi) vs 10 tahun (kenyamanan demo) — boleh berbeda per `DEMO_MODE`? | Keamanan vs kenyamanan panggung | 30 menit + refresh, demo memakai flag khusus |
| 3 | Perbaiki batas tanggal KPI (`plan_date <= end::date`) sekarang atau setelah demo? | Mengubah angka yang dilihat juri | Perbaiki (kartu 0,00% adalah cacat, bukan pilihan) |
| 4 | Apakah `bgn_monitor` memang boleh `/admin/*`? | Matriks peran | Cabut (403) |
| 5 | Target deployment: demo lokal (compose dev) atau publik (butuh image produksi, TLS, CORS, CI) | Menentukan apakah DEP-01/SEC-04/05 blocking | Demo lokal: DEP-01 tidak blocking, tetapi tetap dicatat |
| 6 | Semantik jendela "24 jam": hari kalender WIB hari ini (00:00–sekarang) atau 24 jam bergulir? | Menentukan apakah Meal Continuity bisa 100,00% (bergulir selalu mencampur dua hari rencana) | Pakai hari kalender WIB untuk jendela 24 jam; 7 hari/1 bulan tetap bergulir |

## 19. Prioritized remediation plan

Effort: S < 1 hari · M 1–3 hari · L > 3 hari. Tidak ada perbaikan dikerjakan saat audit.

| # | Group | Task | Findings | Depends on | Acceptance | Regression test | Effort | Owner decision |
|---|---|---|---|---|---|---|---|---|
| 1 | Secret hygiene | Rotasi 4 kunci bocor; pindahkan `.env` ke secret store; `filter-repo` untuk hapus blob `.env` dari riwayat | SEC-01 | #1 | `git log --all -- .env` kosong; kunci lama ditolak provider | login ulang + `POST /dossier` tetap `signed` | M | Ya |
| 2 | Token & login | `JWT_EXPIRE_MINUTES` wajar (≤60) + refresh; rate-limit login (mis. 5/menit); token pindah ke cookie `HttpOnly` | SEC-02, SEC-03 | #2 | token kedaluwarsa terbukti (401 setelah TTL); login ke-6 dalam 1 menit = 429 | tes auth + probe 401 | M | Ya |
| 3 | ~~KPI correctness~~ **SELESAI 2026-10-24** | Sumbu waktu disamakan ke `plan_date` (pembilang tidak lagi difilter `delivered_at`), batas atas inklusif, konversi WIB eksplisit; tes `tests/test_kpi_batas_tanggal.py` (5) | KPI-01 | — | 24 jam Jakarta = 100,00% saat rencana hari ini terkirim penuh (bukan 0,00%, bukan 50,48%); 7 hari/1 bulan naik satu hari | tes baru `test_kpi_batas_tanggal` + `test_kpi_sumbu_waktu` | S | Ya |
| 4 | ~~Schema drift~~ **SELESAI 2026-10-24** | `LedgerBlock` baru (`app/models/ledger.py`) + 22 indeks dideklarasikan di model + 5 tipe kolom disamakan + FK commodity `ondelete=RESTRICT` | DB-01 | — | `alembic check` exit 0 (atau allowlist eksplisit) | jalankan `alembic check` di CI | M | No |
| 5 | Dependensi | Naikkan `next` ≥ 14.2.33/15.x, `maplibre-gl` ≥ 6.15, `vitest` ≥ 3; `pyjwt` ≥ 2.15, `starlette` ≥ 0.47 | SEC-06 | — | `npm audit` & `pip-audit` tanpa critical/high | suite FE 1764 + BE | M | No |
| 6 | Deploy | ~~Image produksi~~ **SELESAI 2026-10-24 untuk DEP-01** (Dockerfile 4 stage `deps/dev/builder/runner`, `.dockerignore`, `docker-compose.prod.yml`, healthcheck backend); **sisa**: CI + DEP-04 | DEP-01, DEP-02, DEP-04 | #5 | — | — | M | Ya |
| 7 | Ledger & data | Backfill/beri tanda blok yatim, atau reset ledger saat reseed; bersihkan 28 akun residu | DB-02, DB-03 | — | `linked_ratio` = 100% atau alasan eksplisit; 7 akun demo saja | `/ledger/verify` + `/admin/users` | S | No |
| 8 | Hardening | Matikan `/docs` saat bukan `DEBUG`; header CSP/X-Frame/HSTS; CORS allowlist eksplisit | SEC-04, SEC-05 | — | probe: `/docs` 404 di produksi; header ada | probe header | S | **Ya** — `/docs` 404, header terpasang di `:3010` dan `:8000`; CORS allowlist belum disentuh |
| 9 | Lint | `ruff check --fix` (12 auto) + sisa manual | LINT-01 | — | `ruff check app tests` exit 0 | — | S | No |

## 20. Final deployment verdict

**NO-GO untuk deployment publik.** Syarat minimal sebelum GO, bernomor:

1. SEC-01 ditutup: kunci dirotasi + riwayat `.env` dibersihkan (atau repo dijamin tetap privat dan tidak pernah dibagikan).
2. SEC-02 & SEC-03 ditutup: masa token wajar, rate-limit login, token tidak di `localStorage`.
3. DEP-01 ditutup: image/compose menyajikan build produksi + healthcheck backend; CI minimal (lint, tsc, test, build, `alembic check`).
4. DB-01 ditutup: `alembic check` bersih/allowlist eksplisit, `quantity_kg` disamakan.
5. SEC-06: tidak ada lagi kerentanan **critical/high** di npm; `pyjwt`/`starlette` dinaikkan.

**GO bersyarat untuk demo lokal di depan juri** (keadaan sekarang) dengan syarat: (a) data demo dibangun ulang tepat sebelum panggung (angka fakta bergerak karena ditulis relatif `now`), (b) presenter tahu kartu **Meal Continuity 24 jam akan tampil 0,00%** sampai KPI-01 diperbaiki — jangan mengklaim kartu itu sebagai bukti, (c) `GET /ledger/verify` disebut "rantai utuh, 27,5% blok tertaut" bila ditanya, (d) tidak membuka repo/port ke jaringan publik saat demo.

## 21. Audit integrity declaration

- **Executed:** `git` (log/show/ls-files), `docker compose ps/exec`, `ruff check`, `npx tsc --noEmit`, `npx next lint`, `npm run build`, `npx vitest run`, `pytest` (DB salinan), `pip-audit` (container sekali-pakai), `npm audit`, `alembic current/heads/check`, `psql` read-only, `curl`/`urllib` GET + `POST /auth/login`.
- **Not executed:** semua `POST/PUT/PATCH/DELETE` selain login; klik UI; panggilan Bedrock/AgentCore/SAP/OSRM; beban/race; restore dump; audit checkout `HackathonBil`.
- **Integrations genuinely invoked:** tidak ada integrasi berbayar. Yang benar-benar dipanggil hanya Postgres lokal, backend lokal, dan registry npm/PyPI (via `npm audit` & `pip-audit`).
- **Mocks and fixtures:** `mock-sap` berjalan tetapi tidak dipanggil; 9 berkas tes agen di-`--ignore`; angka DB berasal dari data demo/seed, bukan data produksi.
- **Unverified areas:** §3 + "Not tested" §2.
- **Modifications:** hanya `AUDIT.md` ini. Artefak di luar repo: skrip probe + log di `%LOCALAPPDATA%\hermes\cache\scratch\`; `frontend/.next/` hasil build. Database salinan `mealchain_audit` dibuat untuk tes lalu **di-drop** setelah run selesai (tidak ada jejak DB tambahan).
- **Database state:** DB kerja **tidak** ditulis oleh tes (tes memakai salinan). Namun DB kerja **berubah oleh aktor lain** selama audit (±23:00 WIB, data demo dibangun ulang: `delivery_events` 360, `menu_plans` 660, `decisions` 90). Tidak ada restore yang saya lakukan karena tidak ada mutasi dari pihak audit.
- **Deployment / git push / layanan berbayar:** tidak ada.
- **Tooling reliability:** 6 kegagalan alat yang memaksa pengulangan dicatat di §2 (`Tooling incidents`). Bagian yang hasilnya berasal dari percobaan yang gagal **tidak** dipakai sebagai bukti.
- **Insiden lingkungan (2026-10-24, saat perbaikan DEP-01):** percobaan menyalakan stack produksi kedua di mesin yang sama (postgres+backend+frontend+mock-sap, total 8 kontainer) membuat Docker Desktop berhenti merespons (`500 Internal Server Error` pada API). Pemulihan: proses Docker dihentikan → `wsl --shutdown` → Docker Desktop dijalankan ulang (dua kali, karena percobaan pertama tidak cukup). Stack dev pulih (kontainer hidup lagi otomatis), lalu `docker compose up -d` dijalankan untuk menerapkan healthcheck baru → `backend (healthy)`, `frontend (healthy)`, `:3010` = 200, `:8000/health` = 200. Volume Postgres tidak disentuh, tidak ada data yang hilang. Pelajaran: jangan menjalankan dua stack penuh berdampingan di mesin ini; verifikasi image produksi cukup satu kontainer frontend di jaringan stack dev.

## 22. Audit ulang 2026-10-24 17:20 WIB (pasca KPI-01, DB-01, DEP-01, pembersihan Docker)

Lingkup: verifikasi ulang bahwa fitur tetap aman dan berjalan setelah remediasi dan pembersihan.
Metode: sama seperti Fase 1 (read-only) — tes memakai salinan DB `mealchain_audit`, probe hanya `POST /auth/login` + `GET`.

### 22.1 Hasil

| Pemeriksaan | Hasil terukur |
|---|---|
| Backend pytest (klon `mealchain_audit`) | **1331 passed, 17 skipped, 0 failed**, 1 error koleksi `tests/test_agent_verifier.py` (`ModuleNotFoundError: agent` = DEP-04), 538,88 dtk |
| Frontend vitest | **166 berkas / 1792 uji lulus**, exit 0 |
| `tsc --noEmit` | exit 0 |
| `next lint` | exit 0 (No ESLint warnings or errors) |
| `alembic check` (klon) | **No new upgrade operations detected** |
| `ruff check app` / `tests` | 46 / 14 temuan (gaya: E501 28, I001 8, F401 3, N806 2, F841 2, W293, N818) — lihat N2 |
| Endpoint GET (dibangkitkan dari `/openapi.json`) | 39 diuji: **0 respons 5xx**, 0 endpoint >3 dtk; 35 lulus, 4 sisanya artefak pengisian parameter probe (diverifikasi manual 200: `/kpi`, `/demo/preview`) |
| Login 7 akun demo | 7/7 → 200 |
| Cakupan per peran | Kepala/Gizi Jakarta hanya melihat **Jakarta**; Bandung hanya **Bandung**; Surabaya hanya **Surabaya**; BGN Monitor melihat **Bandung, Jakarta, Surabaya** |
| UI (browser, akun SPPG Head) | Login → Hari Ini, KPI (24 jam/7 hari/1 bulan), Decision & Evidence, Agent Log, tab lain terender; **0 error JavaScript** |

### 22.2 Temuan baru

**N1 — P1 (kejujuran angka): baris "terkirim" bertanggal masa depan.**
`app/seed/timeseries.py::plan_delivery_rows` membuat satu `delivery_events` berstatus `delivered` untuk **setiap** rencana menu sejak `EVENT_DEMO_START`, tanpa memotong tanggal setelah hari ini; `delivered_at` selalu pukul 14:00 UTC (21:00 WIB) pada tanggal rencana.
- Terukur di DB kerja: **130 baris** `status='delivered'` dengan `delivered_at` di masa depan, 10 lokasi × 13 tanggal (2026-10-24 s/d 2026-11-05), semuanya pukul 21:00 WIB.
- Dampak langsung: Jakarta hari ini `menu_plans` 1.092 porsi; terkirim **sampai sekarang = 0**, terkirim **termasuk masa depan = 1.092** → kartu Meal Continuity 24 jam menampilkan **100,00%** padahal belum ada kiriman yang terjadi (jam layar 16.56 WIB).
- Ini kategori "angka palsu" yang dilarang prinsip repo, dan bertentangan dengan perilaku yang dijanjikan (KPI naik saat truk tiba).
- **Status: DIPERBAIKI 2026-10-24 17:10 WIB.** `app/seed/timeseries.py::plan_delivery_rows(menu_rows, now=None)` kini melewati rencana setelah hari ini (WIB) dan, untuk hari ini, hanya menulis kiriman bila pukul kirim (14:00 UTC = 21:00 WIB) sudah lewat; pemanggil meneruskan `now=now` sehingga penyemaian memakai jam yang sama dengan `generated_at`. Bukti: tes kontrak baru `tests/test_timeseries_kiriman_masa_depan.py` (6 tes) MERAH lebih dulu (`TypeError`/asersi), lalu HIJAU 6/6; suite deret waktu yang ada tetap 32 lulus; `ruff` bersih pada kedua berkas. Efek di DB kerja: kiriman bertanggal masa depan **130 → 0**, Jakarta hari ini rencana 1.092 porsi dengan terkirim 0 → Meal Continuity 24 jam turun dari **100,00%** menjadi **52,40%** (kemarin penuh + hari ini belum berangkat), sesuai perilaku yang dijanjikan: angka naik saat truk benar-benar tiba. **Tindak lanjut (suite penuh menemukan 2 tes yang mengunci aturan lama):** `tests/test_perluasan_kirim_limbah.py` ("setiap hari rencana harus punya kiriman") diperbarui menjadi "setiap hari yang SUDAH berjalan punya kiriman, tidak ada kiriman setelah hari ini"; dan harapan `event_plan["deliveries"]` di `preview_timeseries` kini diturunkan dari predikat yang sama (`kiriman_sudah_terjadi`), sehingga `pastikan_deret_demo` tidak lagi menganggap deret selalu kurang (penyebab `test_deret_demo_aman::test_idempoten_saat_deret_sudah_lengkap` gagal). Hasil suite backend penuh di klon: **1337 lulus, 17 dilewati, 0 gagal**, 1 error koleksi DEP-04, 519,62 dtk.

**N2 — P3 (gaya): `ruff` 46 temuan di `app`, 14 di `tests` — DIBERESKAN 2026-10-24 17:45 WIB.**
Terkonsentrasi di berkas baru `app/seed/hari_ini.py` (24, mayoritas E501). Tidak ada temuan fungsional.
Perbaikan: `ruff check --fix` (15 otomatis: I001/F401/W293) + 45 manual — E501 dibungkus (bukan `noqa`), `N806` `PULAU`/`MAKS_KM` → `pulau`/`maks_km` (+ semua pemakaian), `E741` `l` → `lok`, `N818` `Sibuk` → `SibukError` (+ pemakaian di `api/demo_session.py` dan tesnya), `F841` empat variabel mati dihapus (`surabaya`, `lokasi` di `rapikan.py`, `sebelum`, `hari`). Hasil: `ruff check app tests` → **All checks passed** (60 → 0). Regresi dijaga tes: 76 lulus / 12 dilewati pada 10 berkas terkait, dan `test_demo_template_reset.py` + `test_settlement.py` 13 lulus setelah rename; backend tetap sehat (`/health` 200) setelah reload.

**N3 — P3 (ledger): 1437 dari 1541 blok tidak lagi menunjuk entitas hidup — DIPERBAIKI 2026-10-24 18:05 WIB.**
`GET /ledger/verify` → `valid: true`, `blocks: 1541`, `linked_blocks: 104`, `orphan_blocks: 1437`, `linked_ratio: 0,067`, `coverage_warning: "rantai utuh, tetapi 1437 blok menunjuk entitas yang sudah tidak ada"`. Penyebab: ledger append-only, sedangkan reseed demo menghapus keputusan/approval. Rantai hash **tidak** rusak; yang hilang adalah keterkaitan ke entitas. Dossier tetap aman karena payload blok menyimpan snapshot.

Perbaikan (migrasi `031_ledger_generation` + `ledger_service`): setiap blok kini menyimpan **generasi** (`ledger_blocks.generation`), dan `ledger_meta.generation` naik satu langkah setiap data demo direset — dipanggil dari `demo_session.kosongkan_kecuali`, `demo_session.bersihkan`, dan `timeseries.purge_demo_rows`. Blok lama **tidak dihapus dan tidak ditulis ulang** (append-only + rantai hash tetap utuh); `verify_chain` tetap memeriksa seluruh rantai, tetapi cakupan (`linked_ratio`, `orphan_blocks`) hanya menghitung generasi aktif dan blok lama dilaporkan sebagai `archived_blocks`. UI (`lib/ledger.ts`) menyebut arsip itu apa adanya, bukan sebagai kerusakan.

Bukti terukur:
- Unit/tes integrasi baru `tests/test_ledger_generasi.py` (4 tes) + `tests/test_ledger.py` + `tests/test_ledger_linkage.py` (kontraknya diperbarui ke cakupan per generasi) → **10 lulus**; `alembic check` → "No new upgrade operations detected"; `ruff` bersih.
- Uji jalur nyata: `kosongkan_kecuali` menghapus 801 baris → generasi 2 → 3, 72 blok lama menjadi `archived_blocks: 72`, dan `GET /ledger/verify` pada generasi aktif: `valid: true`, `orphan_blocks: 0`, `linked_ratio: 1.0`.
- Setelah "Siapkan data demo" (`python -m app.seed.demo_template`): 72 blok, generasi 3, `orphan_blocks: 0`, `archived_blocks: 0`, `linked_ratio: 1.0` — angka yatim 1437 tidak bisa muncul lagi pada jalur reset mana pun.
- Frontend: `tests/ledger-coverage.test.ts` 4 lulus (termasuk kalimat arsip), `tsc` 0, `next lint` 0.
- Suite backend penuh di klon `mealchain_audit`: **1340 lulus, 18 dilewati, 0 gagal**, 1 error koleksi DEP-04 (`test_agent_verifier.py`), 526,39 dtk. Sebelumnya ada 2 kegagalan pada `test_ledger_linkage.py` (masih memakai definisi cakupan lama) yang sudah diselaraskan.

**N4 — info:** 6 keputusan tanpa `commodity_id`, semuanya bertipe `supplier_exclusion` / `supplier_exclusion_restoration` (menargetkan pemasok, bukan komoditas). Tidak menimbulkan error; catat supaya tidak dikira bug saat query per komoditas.

**N5 — info:** 120 `menu_plans` bertanggal ke depan (10/hari s/d 2026-11-05) adalah rencana, bukan kiriman; tidak memengaruhi KPI karena jendela dibatasi `end`.

### 22.3 Integritas data (read-only, DB kerja)

| Cek | Hasil |
|---|---|
| batch kembar (komoditas+lokasi+pemasok+panen) | 0 |
| pemasok nama ganda | 0 |
| batch tanpa pemasok/komoditas/lokasi | 0 / 0 / 0 |
| trace / bukti tanpa keputusan | 0 / 0 |
| keputusan `approved`/`executed` tanpa approval | 0 |
| kiriman porsi negatif, kiriman tanpa rencana menu | 0 / 0 |
| stok negatif, batch dipanen di masa depan, keputusan di masa depan | 0 / 0 / 0 |
| kiriman berstatus `delivered` di masa depan | **130** → N1 |

### 22.4 Kesimpulan audit ulang

- Semua lapisan yang diuji **berjalan**: 1331 tes backend lulus tanpa kegagalan, 1792 tes frontend lulus, tsc/lint bersih, skema selaras, 39 endpoint GET tanpa 5xx, dan UI terender tanpa error konsol.
- Dua hal yang **belum** "aman" untuk diklaim di depan juri: **N1** (Meal Continuity 24 jam 100% sebelum ada kiriman) dan **SEC-01/SEC-02/SEC-03** (tidak berubah sejak audit pertama).
- DEP-04 tetap terbuka: `tests/test_agent_verifier.py` tidak bisa dikoleksi di image karena paket `agent` tidak ada.
- Catatan metode: DB kerja tidak ditulis oleh audit ini; tes memakai klon `mealchain_audit` (dibuat dari dump DB kerja pada 16:59 WIB, di-drop setelah run).

