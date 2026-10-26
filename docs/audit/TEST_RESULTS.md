# TEST RESULTS — MealChain Guardian

Dokumen ini mencatat hasil gerbang tes **yang benar-benar dijalankan** pada 26 Oktober 2026,
21:37–21:50 WIB. Setiap angka di bawah berasal dari keluaran perintah, bukan dari laporan lama.
Tidak ada kredensial, token, atau sandi yang ditulis di sini.

- Repo: `E:\hackathon\HackathonAWS\mealchain-guardian`
- Git: `5885810` — branch `feature/db-modes-demo-coverage`
- Stack: Docker Compose hidup (`mealchain-backend` :8000 healthy, `mealchain-frontend` :3010 healthy,
  `mealchain-postgres` :15432 healthy, `mealchain-mock-sap` :8001)

## 1. Lingkungan ukur

| Komponen | Versi / keterangan |
|---|---|
| Host | Windows 11, shell bash (MSYS/git-bash) |
| Container backend | Python 3.12.15, pytest 8.3.3, ruff 0.6.9, image `mealchain-guardian-backend` (5 hari) |
| Container frontend | Node v20.20.2, npx 10.8.2, TypeScript 5.6.2, vitest 2.1.9 (linux-x64), image `mealchain-frontend-dev` (2 hari) |
| Postgres | `postgres:16-alpine`, DB demo `mealchain` |
| Paket tes | backend `pytest` + `pytest-asyncio`, frontend `vitest` + jsdom |

## 2. Ringkasan gerbang

| # | Perintah (nyata) | Dijalankan di | Exit | Hasil |
|---|---|---|---|---|
| 1 | `docker compose exec -T frontend npx tsc --noEmit` | container frontend | **0** | tanpa keluaran (0 galat tipe) |
| 2 | `docker compose exec -T frontend npx vitest run` | container frontend | **0** | `Test Files 166 passed (166)` · `Tests 1818 passed (1818)` · 22,18 s |
| 3 | `docker compose exec -T frontend npx next lint` | container frontend | **0** | `✔ No ESLint warnings or errors` |
| 4 | `docker compose exec -T backend ruff check .` | container backend | **0** | `All checks passed!` |
| 5 | `docker compose run --rm -T -e DATABASE_URL=…/audit_test -e DEMO_SESSION_ENFORCE=false backend python -m pytest -q --tb=line` | container sekali-pakai, **DB klon** | **1** | `13 failed, 1551 passed, 27 skipped, 2 warnings in 577.84s (0:09:37)` |

Total tes backend yang terkumpul: **1.591** (1551 lulus + 13 gagal + 27 skip).

### Catatan kenapa `npx` dijalankan di kontainer (bukan `cd frontend && npx …` di host)

`node_modules` hidup di image frontend. `npx` di host tidak gagal dengan pesan jujur "deps tidak ada":
ia mengunduh paket bernama sama dari registry lalu mencetak galat yang bentuknya seperti galat kode
(mis. `This is not the tsc command you are looking for`, `Could not resolve "vitest/config"`).
Angka dari run seperti itu tidak sah sebagai gerbang, jadi perintah dijalankan di dalam kontainer
tempat dependensi yang sebenarnya berada. `frontend/node_modules` yang ada di host dipakai hanya untuk
membaca versi terkunci (`package-lock.json`).

## 3. Isolasi DB untuk pytest (wajib — DB demo hanya SELECT)

DB demo dipakai bersama dan tidak boleh ditulis oleh suite. Langkah yang dipakai:

1. Klon sekali dari DB demo di server Postgres yang sama:
   `docker exec mealchain-postgres sh -c 'dropdb -U <user> --if-exists audit_test; createdb -U <user> audit_test && pg_dump -U <user> -d mealchain | psql -q -U <user> -d audit_test'`
   → `audit_test` terisi (snapshot: 48 baris `decisions` saat klon dibuat).
2. Suite dijalankan di kontainer sekali-pakai (`docker compose run --rm -T backend`) dengan
   `DATABASE_URL=postgresql+asyncpg://<user>:<password>@postgres:5432/audit_test` dan
   `DEMO_SESSION_ENFORCE=false`.
   `backend/tests/dsn.py` membaca `DATABASE_URL`, jadi fixture dan aplikasi menunjuk DB yang sama.
3. Kontainer dibuang (`--rm`); DB demo tidak menerima satu tulisan pun dari suite.

## 4. 13 tes backend yang gagal (DB klon)

Semua baris di bawah adalah nama tes + lokasi asersi + pesan ringkas dari keluaran `--tb=line`.

| # | Tes | Baris | Gejala | Dugaan kelas |
|---|---|---|---|---|
| 1 | `tests/test_akun_multi_kota.py::test_approval_riwayat_demo_sesuai_lokasi_target` | 139 | baris `executed` bertarget Medan/Bandung punya `approver_loc = Jakarta` | keadaan data |
| 2 | `tests/test_akun_multi_kota.py::test_semua_approval_sesuai_lokasi_target` | 158 | approval `approved` untuk target Bogor/Medan berasal dari approver Jakarta | keadaan data |
| 3 | `tests/test_demo_harian.py::test_harga_harian_demo_tersedia_untuk_hari_ini` | 241 | kutipan harga tanpa acuan PIHPS lebih dulu → metrik deviasi harga kosong | keadaan data (seed) |
| 4 | `tests/test_demo_seed_per_kota.py::test_seed_dari_bandung_menargetkan_bandung` | 116 | daftar kasus demo tidak sama dengan yang diharapkan (baris Cianjur/Semarang ikut) | keadaan data (seed) |
| 5 | `tests/test_demo_seed_per_kota.py::test_seed_idempoten_per_kota` | 134 | `assert 7 == 8` (jumlah kasus setelah seed ulang) | keadaan data (seed) |
| 6 | `tests/test_demo_seed_per_kota.py::test_force_bandung_tidak_menghapus_kasus_jakarta` | 154 | himpunan `demo_case` berbeda (`extra:supplier-*` vs `gangguan-*`) | keadaan data (seed) |
| 7 | `tests/test_demo_seed_per_kota.py::test_ahli_gizi_kota_boleh_menyemai` | 169 | hasil semai memuat kasus `extra:supplier_exclusion_restoration` yang tak diharapkan | keadaan data (seed) |
| 8 | `tests/test_demo_timeseries_api.py::test_membangun_deret_tidak_menggeser_jangkar` | 258 | `AssertionError: deret demo belum dibangun` | deret demo kosong |
| 9 | `tests/test_demo_timeseries_api.py::test_baris_aktual_berhenti_di_batas_rencana` | 502 | `assert 0 > 0` (tidak ada baris aktual) | deret demo kosong |
| 10 | `tests/test_demo_timeseries_api.py::test_data_status_membaca_db` | 667 | `AttributeError: 'NoneType' object has no attribute 'startswith'` | deret demo kosong |
| 11 | `tests/test_demo_timeseries_api.py::test_refresh_hari_ini_tidak_menggandakan_snapshot_kanonik` | 942 | `assert 1393.93 == 1400.0` (selisih 6,07 kg) | keadaan data (seed) |
| 12 | `tests/test_tool_contracts.py::test_balance_analyze_full_pipeline_with_summary` | 137 | `assert 0 > 0` (tidak ada kandidat alokasi) | deret demo kosong |
| 13 | `tests/test_tool_contracts.py::test_evidence_fuse_assembles_from_recommendation` | 160 | `seed harus menghasilkan minimal 1 rekomendasi` | deret demo kosong |

**Pembacaan yang jujur:** ke-13 kegagalan mengelompok pada satu tema — **keadaan data demo di klon**
(kasus demo per kota dan deret waktu belum/tidak lagi sesuai bentuk yang diharapkan tes), bukan pada
galat impor, 401, atau deadlock. Karena DB demo tidak boleh ditulis dan penyemai deret demo
(`app.seed.timeseries`, `seed_demo_activity`) menulis ke DB, keadaan itu **tidak dipulihkan** pada
audit ini. Konsekuensinya: angka 13 gagal **tidak boleh** dibaca sebagai 13 cacat produk; ia adalah
batas atas kegagalan pada snapshot data yang ada. Sebelum menyalahkan kode, pulihkan deret demo lalu
ulangi berkas-berkas tersebut (prosedur ada di `AGENTS.md` / skill dev-loop repo ini).

Catatan pembanding: laporan sesi sebelumnya mencatat 1.549 lulus / 14 gagal / 28 skip. Angka audit ini
1.551 lulus / 13 gagal / 27 skip pada klon yang sama jenisnya — selisih satu tes konsisten dengan
pergeseran keadaan data demo, bukan dengan perubahan kode (HEAD tidak berubah selama pengukuran).

## 5. Yang TIDAK diuji (NOT TESTED)

| Area | Status | Alasan |
|---|---|---|
| Build produksi (`next build`) | **NOT TESTED** | Di luar lingkup audit ini; build menulis ulang `frontend/tsconfig.json` dan membuat artefak baru di working tree bersama |
| Aksesibilitas otomatis (axe / WCAG) | **NOT TESTED** | Tidak ada runner axe di repo; audit a11y terpisah |
| Uji beban / latensi | **NOT TESTED** | Tidak ada alat beban (k6/locust) di lingkungan ini |
| Uji E2E browser (Playwright, matriks tab/peran) | **NOT TESTED** | Suite `verify/` tidak dijalankan pada audit ini |
| Tes host-only `agent/` (`test_supervisor_agent`, `test_supervisor_tools`, kontrak worker) | **SKIP** (bagian dari 27 skip) | Butuh mount repo + `strands-agents`, tidak ada di image backend |
| `pip-audit` / `bandit` (backend) | **NOT TESTED** | Tidak terpasang di image backend (lihat dokumen keamanan) |
| `ruff format --check` | **BUKAN gerbang** | `core.autocrlf=true` membuat semua berkas CRLF; `--check` selalu melaporkan "would reformat" bahkan untuk berkas yang tidak disentuh |
| Migrasi Alembic (`alembic check`) | **NOT TESTED** | Tidak dijalankan pada audit ini |

## 6. Keterbatasan pengukuran

1. **DB demo dipakai bersama dan bergerak selama audit.** `SELECT count(*) FROM decisions` memberi 48
   baris pada 21:39 dan 32 baris pada 21:41 tanpa ada perintah tulis dari audit ini — proses/sesi lain
   menyentuh DB demo. Semua perbandingan di dokumen konsistensi diambil sebagai snapshot berpasangan
   (API lalu DB dalam < 1 menit) dan cocok pada saat itu.
2. **Klon adalah potret, bukan baseline bersih.** Klon mewarisi keadaan demo saat itu (deret waktu dan
   kasus demo tidak dalam bentuk kanonik), sehingga tes yang bergantung data demo gagal.
3. **Angka gerbang dibaca tanpa pipa.** Setiap perintah dialihkan ke berkas lebih dulu lalu `EXIT=$?`
   dicetak terpisah; tidak ada status yang diambil dari ujung pipa (`| head`/`| tail`).
4. **Waktu jalan** suite backend 9 m 37 s di kontainer sekali-pakai dengan DB klon; suite frontend 22 s.

## 7. Temuan (AUDIT-ID)

| ID | Severity | Status | Temuan |
|---|---|---|---|
| TST-01 | Medium | Open | 13 tes backend gagal di DB klon; semuanya bertema keadaan data demo (kasus per kota + deret waktu). Tidak dapat dipastikan cacat produk tanpa memulihkan deret demo lebih dulu. |
| TST-02 | Low | Accepted | 27 tes skip, termasuk seluruh tes host-only `agent/` dan kontrak worker; suite normal tidak menyentuh lapisan agen. |
| TST-03 | Low | Open | Tes demo-seed/demo-timeseries tidak deterministik terhadap keadaan DB (jumlah kasus, jangkar deret), sehingga gerbang merah/hijau bisa berubah tanpa perubahan kode. |
| TST-04 | Info | Accepted | Pengukuran dilakukan pada klon `audit_test` (potret), bukan DB demo; gerbang penuh di DB demo tidak boleh dijalankan menurut aturan kerja. |
| TST-05 | Info | Open | Build produksi, axe, dan uji beban belum pernah menjadi bagian gerbang otomatis di lingkungan ini. |
| TST-06 | Info | Accepted | `ruff format --check` tidak dipakai sebagai gerbang karena CRLF; klaim kebersihan format tidak boleh diambil darinya. |
