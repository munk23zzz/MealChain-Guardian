# FINAL VERIFICATION REPORT — MealChain Guardian

> **Snapshot 25 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tanggal:** 2026-10-25 (Asia/Jakarta) · **Siklus:** perbaikan pertama + verifikasi
**Basis:** `PROJECT_AUDIT_REPORT.md` (baseline) dan `REPAIR_PLAN.md` (rencana R1–R18)
**Catatan penting:** laporan ini **tidak** menyatakan proyek bebas cacat. Status keseluruhan: **PARTIALLY FIXED — 6 kelompok perbaikan terverifikasi, 5 temuan diblokir keputusan pemilik/environment, 1 temuan false positive.**

---

## 1. Executive summary

| Klaim | Status | Bukti |
|---|---|---|
| Penerimaan barang tidak lagi bisa meloloskan batch belum `pass` | **Fixed + teruji** | `app/api/receipts.py` memakai `receipt_blokir_alasan`; 2 test baru gagal sebelum patch, lulus sesudahnya |
| Bukti suhu kosong/tidak lengkap tidak lagi memberi skor `pass` | **Fixed + teruji** | `app/core/freshness.py:29-40`; 5 test baru (termasuk invarian lintas-lapisan) |
| Eksekusi/dispatch tidak lagi memakai batch ragu & tidak memperpanjang `usable_until` | **Fixed + teruji** | `app/api/actions.py`; 9 test wiring |
| Angka `quantity_kg`/`safe_delivered_cost` dari klien divalidasi sebelum dipakai PO | **Fixed + teruji** | `app/core/recommendation_numbers.py` + 9 test API |
| Password demo tidak lagi terpasang tanpa pernyataan mode demo | **Fixed + teruji** | `app/seed/demo_credentials.py`; seed menolak dengan pesan operator |
| Compose produksi tidak lagi memakai fallback password / mem-publish DB ke semua interface | **Fixed (config-level)** | `docker-compose.prod.yml`; `docker compose config` menunjukkan `host_ip: 127.0.0.1` |
| Lint backend bersih | **Fixed** | `ruff check .` → `All checks passed!` |
| Tidak ada regresi pada gate yang dapat dijalankan | **Sebagian** | lihat §7 (matriks test) |

---

## 2. Baseline (sebelum perubahan)

```
branch : feature/db-modes-demo-coverage
HEAD   : d414957 (2026-10-25 03:50:25 +0700)
dirty  : 7 modified, 38 deleted, 1 untracked  (milik pemilik, dipertahankan)
DB uji : mealchain_gate (DB baru, TERPISAH dari DB demo `mealchain`)
```

Gate baseline: `ruff check .` = **1 error** (`I001`), `tsc --noEmit` = 0, `next lint` = bersih, `vitest` = 1794 lulus, migrasi DB kosong → head `031` = bersih, suite backend penuh = tidak selesai pada baseline (dijelaskan §7.2).

---

## 3. Cakupan audit

Direktori: `backend/app/{api,core,services,ai_providers,seed,models}`, `backend/alembic/versions`, `backend/tests`, `agent/`, `frontend/{app,components,lib,tests}`, `docker-compose*.yml`, `verify/`, `.github/workflows/ci.yml`, `docs/*.md`.
Tidak disentuh: `docs/Architecture.md`, `docs/Schema.md` (aturan tugas), `memory/global/decisions.md` (milik pemilik).

---

## 4. Skills dan tools — status sebenarnya

| Nama | Sumber | Status | Dipakai untuk |
|---|---|---|---|
| `project-audit` | skill Hermes terpasang | dibaca + dijalankan | urutan audit, gate |
| `codebase-inspection` | skill Hermes terpasang | dibaca + dijalankan | inventaris, pygount |
| `test-driven-development` | skill Hermes terpasang | **dibaca + diikuti** (RED→GREEN) | seluruh siklus perbaikan |
| `.claude/skills/demo-data-builder`, `.claude/skills/db-mode` | skill lokal repo | dibaca (inventaris) | konteks domain |
| `npx skills` (vercel-labs/skills CLI) | terpasang di host | `--help` diperiksa; **tidak** memasang skill eksternal | discovery |
| Reviewer independen V3 (access/secrets), V4 (infra/docs) | subagent | dijalankan (hasil menyusul) | verifikasi ulang D-01…D-08, A-09, R-01 |
| Reviewer diff independen | subagent | dijalankan (hasil menyusul) | §9.7 & §12.4 prompt |
| Semgrep | tidak terpasang | **NOT RUN** | — |
| markdownlint-cli2 | tidak terpasang | **NOT RUN**; validasi manual tabel/fence/anchor | — |
| `pip-audit` / `npm audit` | tidak dijalankan | **NOT RUN** | advisory dependency (§11) |

---

## 5. Finding register (status akhir)

| ID | Severity awal | Status | Bukti perubahan / alasan |
|---|---|---|---|
| F-01 penerimaan meloloskan status selain `fail` | Critical | **FIXED** | `app/api/receipts.py:201-215` → `receipt_blokir_alasan`; test `test_receipts_safety_gate.py` (2 kasus) |
| F-02 bukti suhu kosong ⇒ skor `pass` | Critical | **FIXED** | `app/core/freshness.py:29-40`; `test_freshness_evidence_integrity.py` (5 test) |
| F-03 rentang suhu hard-code 0–8 °C untuk semua komoditas | Critical | **BLOCKED — nilai domain** | mekanisme butuh tabel resmi per komoditas; angka tidak boleh dikarang. Rencana tertulis di `REPAIR_PLAN.md` R3 |
| A-01/F-06 gate eksekusi longgar + rewrite `usable_until` | High | **FIXED** | `app/api/actions.py:315-360,885-915`; `test_execute_safety_wiring.py` (9 test) |
| F-09/A-02 angka klien dipakai untuk PO | High | **FIXED (jalur create)** | `app/api/decisions.py:109-140`; `test_decisions_numeric_validation.py` (9 test). *Catatan:* jalur execute kini hanya menerima angka yang sudah lolos validasi ini |
| F-07 tidak ada test verifier guard | — | **FALSE POSITIVE** | `backend/tests/test_verifier_safety_guard.py` sudah ada (4 test) |
| D-01 password demo fixed + seed produksi | Critical (secret) | **FIXED (kode)** | `app/seed/demo_credentials.py`; `seed_data.py` fail-fast; rotasi tetap **BLOCKED — pemilik kredensial** |
| D-02/F-10 `/demo/*` destruktif saat `DEMO_SESSION_ENFORCE=false` | High | **OPEN** | belum diubah: perlu keputusan produk apakah default dev boleh destruktif |
| D-03 rate limit `X-Forwarded-For` | Medium | **OPEN** | perlu keputusan topologi proxy sebelum mempersempit trusted IP |
| D-04/F-08 `bgn_monitor` mengelola user | High→Medium | **ACCEPTED RISK (terdokumentasi)** | `app/api/admin.py:105-125` menyatakan ini keputusan owner 2026-10-17 (skema tanpa peran `admin`), dengan pagar: tidak boleh ubah peran sendiri + jejak ledger. Sisa risiko: token operasional agen memegang kemampuan tulis yang tidak ia butuhkan (least privilege) |
| D-05 credential historis masih dipakai | High (secret) | **BLOCKED — pemilik kredensial** | checklist rotasi di `REPAIR_PLAN.md` §3; kode tidak dapat merotasi kredensial provider |
| D-06 port prod terbuka + fallback password | High | **FIXED** | `docker-compose.prod.yml`: `127.0.0.1:15432`, `127.0.0.1:8000`, `127.0.0.1:8001`, `${POSTGRES_PASSWORD:?wajib}` (gagal start bila kosong) |
| D-08/B-02 `GET /batches` lintas tenant | High→Low | **ACCEPTED RISK (terdokumentasi)** | `app/api/batches.py:48-57` menyatakan daftar lintas lokasi disengaja untuk panel Event 3; memfilter per lokasi akan mengosongkan panel. Filter UI = kenyamanan, bukan kontrol akses. Kebutuhan produk: putuskan apakah panel chaos butuh endpoint terpisah |
| C-05 provider habis → 500 di verifier | High | **OPEN** | perubahan butuh penyelarasan status verifier; belum dikerjakan pada siklus ini |
| C-09 `safety_veto` tidak memengaruhi status run | High | **OPEN** | idem |
| C-12 model id tidak tercatat di trace | Medium | **OPEN** | idem |
| A-09 migrasi tidak dijalankan saat start | Medium | **PARTIAL** | `verify/docker-compose.mutations.yml` sudah `alembic upgrade head &&` (jalur verifikasi). Stack **produksi** tetap tidak menjalankan migrasi otomatis — sengaja, karena race multi-replica; butuh entrypoint sekali-jalan + readiness schema |
| R-01 drift `backend/openapi.json` | Medium | **OPEN** | butuh regenerasi resmi + drift guard di CI; belum dikerjakan |
| Lane topology ganda | Medium | **OPEN** | belum diverifikasi ulang |
| Ruff `I001` | Low | **FIXED** | `alembic/versions/022_disposal_partner.py:17` |

---

## 6. Changes made (akar masalah → patch)

1. **`app/core/safety_gate.py` (baru)** — satu tempat aturan gerbang keselamatan deterministik: status harus `pass`, karantina `none`/`released`, belum kedaluwarsa, bukti suhu lengkap (≥2 sampel valid, tanpa entri rusak/duplikat). Kumpulan kosong = blokir.
2. **`app/core/freshness.py`** — cabang bukti tidak lengkap dulu memberi penalti **nol**; sekarang penalti penuh (`outside_fraction = 1.0`) sehingga skor maksimum 0,70 dan tidak pernah `pass`. Rantai pendingin bersih tetap 0,90 (dikunci test regresi).
3. **`app/api/receipts.py`** — pesan 409 dipisah per alasan (kedaluwarsa / status belum `pass` / bukti suhu kurang) agar petugas tahu tindakan berikutnya.
4. **`app/api/actions.py`** — `_source_batches_still_safe` fail-closed (semua batch harus lolos; kosong = blokir); `_dispatch_bound_batches` tidak lagi menulis ulang `usable_until` dan mengembalikan `(dikirim, ditahan)`; respons `execute` memuat `ditahan`.
5. **`app/core/recommendation_numbers.py` + `app/api/decisions.py`** — validasi `Decimal` (bukan angka/negatif/>1.000 ton), batas biaya, kewajaran harga satuan, dan kecocokan `cost_breakdown.total`; pelanggaran → **422** (dulu 201 atau 500).
6. **`app/seed/demo_credentials.py` + `seed_data.py` + `semai_kanonik.py`** — password demo hanya dipakai bila `DEMO_MODE` aktif atau `DEMO_PASSWORD_<ROLE>` disuplai; seed berhenti **sebelum** menulis apa pun; seeder kanonik menyalakan `DEMO_MODE=true` untuk subprocess-nya.
7. **`docker-compose.prod.yml`** — semua port ke `127.0.0.1`, fallback password dihapus (`:?` → gagal start), dokumentasi seed diperbarui.
8. **`verify/docker-compose.mutations.yml`** — seed dijalankan dengan `DEMO_MODE=true` inline; aplikasi tetap `DEMO_MODE=false`.
9. **`alembic/versions/022_disposal_partner.py`** — satu baris kosong untuk `I001`.

Tidak ada migration baru, tidak ada dependency baru.

---

## 7. Test matrix

### 7.1 Gate statik

| Command | Environment | Exit | Hasil | Status |
|---|---|---:|---|---|
| `ruff check .` | review venv (ruff 0.6.9), backend | 0 | `All checks passed!` | **PASS** |
| `tsc --noEmit` | frontend/node_modules | (lihat §7.3) | — | — |
| `next lint` | frontend | (lihat §7.3) | — | — |
| `docker compose -f docker-compose.prod.yml config` | host | 0 | `host_ip: 127.0.0.1` pada 8000/8001/15432 | **PASS** |
| `docker compose -f verify/docker-compose.mutations.yml config` | host | 0 | command tergabung benar | **PASS** |
| `env -u POSTGRES_PASSWORD docker compose -f probe.yml config` | host | 1 | `required variable POSTGRES_PASSWORD is missing a value` | **PASS (fail-closed terbukti)** |

### 7.2 Gate database & domain

| Command | Environment | Hasil | Status |
|---|---|---|---|
| `alembic upgrade head` pada DB kosong | `mealchain_gate` | 000→031 bersih, head `031_ledger_generation` | **PASS** |
| `seed_data --with-demo-users` tanpa `DEMO_MODE` | `mealchain_gate` | `[seed] menolak memasang password demo: set DEMO_MODE=true …` (SystemExit, tanpa traceback) | **PASS (guard)** |
| `seed_data --with-demo-users --with-demo-suppliers` dengan `DEMO_MODE=true` | `mealchain_gate` | 10 lokasi / 4 komoditas / 60 pemasok / 78 batch / 7 user | **PASS** |
| Suite backend penuh `pytest -q` | `mealchain_gate` | **lihat §7.4** | — |

### 7.3 Test baru & targeted (semua dijalankan pada `mealchain_gate2` agar tidak bertabrakan dengan kunci gerbang)

| File test | Jumlah | RED (sebelum patch) | GREEN (sesudah) |
|---|---|---|---|
| `test_freshness_evidence_integrity.py` | 5 | 4 gagal, 1 lulus (kasus bersih) | lulus |
| `test_safety_gate_rules.py` | 18 | `ModuleNotFoundError: app.core.safety_gate` | lulus |
| `test_receipts_safety_gate.py` | 2 | 2 gagal (409 diharapkan, dapat 200) | lulus |
| `test_execute_safety_wiring.py` | 9 | 7 gagal (fail-closed belum ada) | lulus |
| `test_seed_credential_guard.py` | 8 | `ModuleNotFoundError: app.seed.demo_credentials` | lulus |
| `test_decisions_numeric_validation.py` | 9 | 9 gagal (201/500, bukan 422) | lulus |
| Regresi terkait (receipts/actions/decisions/security) | 79 + 41 + 44 | — | lulus |

Penyesuaian test lama yang **tidak melemahkan** apa pun: `tests/test_receipts_approval.py::_batch()` kini memilih batch `pass` dengan ≥2 sampel suhu, karena persetujuan batch non-`pass` memang tidak lagi sah (aturan barunya diuji terpisah di `test_receipts_safety_gate.py`).

### 7.4 Frontend

| Command | Hasil | Status |
|---|---|---|
| `tsc --noEmit` | `TSC_EXIT=0` | **PASS** |
| `next lint` | `✔ No ESLint warnings or errors` (`LINT_EXIT=0`) | **PASS** |
| `vitest run` | **166 file / 1794 test lulus** (`VITEST_EXIT=0`) | **PASS** |

Waktu: dijalankan setelah seluruh patch backend (frontend sendiri tidak diubah oleh tugas ini), sehingga gate ini berfungsi sebagai kontrol regresi antarmuka.

---

## 8. Security & safety validation

| Aspek | Bukti |
|---|---|
| Fail-closed penerimaan | `receipt_blokir_alasan` menolak `pending`/`needs_verification`/`fail`/null, bukti suhu <2 sampel, entri rusak, timestamp duplikat, kedaluwarsa |
| Fail-closed eksekusi | `kumpulan_batch_blokir_eksekusi` menolak bila ada batch yang tidak lolos; kumpulan kosong ditolak |
| Expiry tidak bisa "disiasati" | penulisan ulang `usable_until` dihapus dari `_dispatch_bound_batches` |
| Angka tidak dipercaya | `validasi_angka_rekomendasi`: bukan angka → 422, ≤0 → 422, >1.000 ton / >Rp 1 T → 422, harga satuan di luar 100–5.000.000/kg → 422, rincian tak cocok → 422 |
| Secret | tidak ada password/token yang ditulis di kode laporan; seed menolak tanpa `DEMO_MODE`/`DEMO_PASSWORD_*` |
| Config prod | port loopback; password wajib (fail-closed saat kosong) |
| Karantina | kini dihormati pada jalur dispatch & gate eksekusi (dulu tidak) |

---

## 9. Status integrasi

| Integrasi | Status jujur |
|---|---|
| SAP (mock) | **mock** — `SAP_*_MODE=mock`; tidak ada panggilan ke SAP nyata pada siklus ini |
| SAP AI Core / Bedrock | **configured, not verified live** — tidak ada kredensial yang dipakai |
| AgentCore | **configured** (deploy script ada), tidak dijalankan |
| OSRM | **tidak dipanggil** (`--skip-routes`) |
| Joule A2A | tidak diuji |

---

## 10. Review independen

- Dua reviewer independen (access/secrets, infra/docs) dijalankan pada awal siklus; hasilnya belum masuk ke laporan ini saat ditulis → **status: pending**, akan dilampirkan.
- Reviewer diff independen (adversarial) dijalankan atas patch di §6 → **status: pending**, akan dilampirkan. Poin yang diminta diperiksa: pemanggil `_dispatch_bound_batches`, bentuk respons `dikirim`/`ditahan` di frontend, efek samping perubahan freshness pada data demo, dan kualitas test (apakah test benar-benar gagal bila patch dibatalkan).

---

## 11. Unresolved / blocking

| # | Item | Alasan | Tindakan yang diperlukan |
|---|---|---|---|
| B1 | F-03 rentang suhu per komoditas | Ambang keselamatan pangan tidak boleh dikarang | pemilik menetapkan tabel (ayam, telur, wortel, beras) + tanda tangan domain; mekanisme siap dipasang |
| B2 | D-05 rotasi kredensial | butuh akses provider | rotasi `SIGNING_KEY_HEX`, `POSTGRES_PASSWORD`, key provider, token agen; lalu pertimbangkan `git filter-repo` |
| B3 | D-02 default `DEMO_SESSION_ENFORCE=false` | keputusan produk untuk alur demo | putuskan default per-environment |
| B4 | D-03 trusted proxy | topologi proxy harus dipastikan | tetapkan IP/rentang proxy di `--forwarded-allow-ips` + counter per akun |
| B5 | C-05/C-09/C-12 | butuh perubahan skema trace/status | siklus berikutnya |
| B6 | R-01 OpenAPI drift | regenerasi resmi | jalankan generator repo + tambah langkah CI |
| B7 | Advisory dependency | `pip-audit`/`npm audit` belum dijalankan | jalankan pada environment dengan akses registry |

---

## 12. Residual risks

1. Perubahan freshness membuat batch tanpa bukti suhu **tidak lagi** mendapat skor `pass`; data demo yang statusnya `pass` tetapi log-nya kosong (jika ada) akan tampak tidak konsisten sampai disemai ulang.
2. Gate eksekusi kini menolak keputusan yang seluruh batch sumbernya tidak lolos — alur demo yang mengandalkan batch `pending` akan gagal (dan memang harus gagal).
3. `_dispatch_bound_batches` **tidak** membatalkan PO bila ada batch terikat yang ditahan; PO sudah terbit sebelum dispatch. Ini residual inconsistency yang dicatat, bukan diperbaiki (membatalkan PO memerlukan desain kompensasi).
4. Rentang suhu masih satu nilai generik (0–8 °C) karena F-03 diblokir keputusan domain.
5. Tidak ada bukti runtime untuk SAP/AgentCore/Joule.

---

## 13. Reproducibility

```bash
# 1) DB uji terpisah (jangan pakai DB demo)
docker exec mealchain-postgres psql -U mealchain -d postgres -c "CREATE DATABASE mealchain_gate"
export DATABASE_URL="postgresql+asyncpg://mealchain:<password>@127.0.0.1:15432/mealchain_gate"
cd backend && python -m alembic upgrade head

# 2) Seed (WAJIB DEMO_MODE=true untuk akun demo)
DEMO_MODE=true python -m app.seed.seed_data --reference-time 2026-10-25T11:00:00+00:00 \
  --with-demo-users --with-demo-suppliers --skip-routes

# 3) Gate
python -m ruff check .
python -m pytest -q                     # butuh Postgres + seed
cd ../frontend && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/next lint && ./node_modules/.bin/vitest run
```

Quirk Windows (bukan cacat repo): seed async gagal dengan `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`; jalankan lewat pembungkus `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`.

---

## 14. Change-integrity summary

**File yang diubah oleh tugas ini (10 diubah + 10 baru):**

```
M backend/app/core/freshness.py
M backend/app/api/receipts.py
M backend/app/api/actions.py
M backend/app/api/decisions.py
M backend/app/seed/seed_data.py
M backend/scripts/semai_kanonik.py
M backend/tests/test_receipts_approval.py
M backend/alembic/versions/022_disposal_partner.py
M docker-compose.prod.yml
M verify/docker-compose.mutations.yml
?? backend/app/core/safety_gate.py
?? backend/app/core/recommendation_numbers.py
?? backend/app/seed/demo_credentials.py
?? backend/tests/test_safety_gate_rules.py
?? backend/tests/test_execute_safety_wiring.py
?? backend/tests/test_freshness_evidence_integrity.py
?? backend/tests/test_receipts_safety_gate.py
?? backend/tests/test_seed_credential_guard.py
?? backend/tests/test_decisions_numeric_validation.py
?? PROJECT_AUDIT_REPORT.md / REPAIR_PLAN.md / REPAIR_LOG.md / FINAL_VERIFICATION_REPORT.md
```

**Tidak disentuh:** `docs/Architecture.md`, `docs/Schema.md`, `memory/global/decisions.md`, dan seluruh file frontend yang sudah dimodifikasi pemilik (`supply-adequacy.css`, `SupplyAdequacyChart.tsx`, `next.config.js`, `tests/supply-adequacy-chart.test.tsx`), `backend/app/seed/demo_template.py`, `backend/tests/test_demo_template_kesegaran.py`, `backend/alembic/versions/018_agent_trace_worker_fields.py`.

Tidak ada commit, merge, reset, clean, force-push, deploy, migrasi produksi, atau seed ke DB demo.

---

## 15. Revisi 2026-10-25 (malam) — koreksi setelah review independen

Bagian ini MENGGANTIKAN angka dan sebagian kesimpulan di §5 dan §7.

### 15.1 Yang dikoreksi oleh reviewer (bukan oleh saya)

| Klaim awal saya | Kenyataan | Bukti |
|---|---|---|
| D-04 "tidak terbukti, tidak ada token statis" | SALAH. `backend/scripts/buat_token_agen.py:99-109` menerbitkan JWT `bgn_monitor` 30 hari dan melewati clamp `auth.py:54-78` | V3-access |
| `GET /receipts?batch_id` "eksenpsi terdokumentasi" | Terlalu lunak: rute tulis ber-scope, rute baca tidak (`receipts.py:388-399`) | V3-access |
| Review lama mengutip `frontend/lib/roles.ts` | File TIDAK ADA; yang nyata `api.ts:770` + `FoodSafetyBoard.tsx:1191-1210` | V3-access |
| "D-02 semua `/demo/*` destruktif tanpa gate" | Hanya `/demo/template/rebuild` (`demo_session.py:208-212`) | V3-access |
| "Dependency cryptography/python-multipart" | Bukan dependensi proyek; starlette 0.38.6 tidak dipin | V4-infra |

### 15.2 Kerusakan yang SAYA sebabkan (review diff menemukannya)

1. Menghapus `DEMO_USERS["password"]` memutus 20+ pemakai → **29 `KeyError: 'password'`** pada suite penuh.
2. Gate eksekusi "semua batch harus `pass`" atas seluruh batch lokasi+komoditas → satu batch `pending` memblokir eksekusi selamanya; seed kanonik Jakarta/ayam, Surabaya/telur, Medan/ayam terkena.
3. Paritas UI↔API pecah lagi (`can_execute` hanya melihat `fail`).

### 15.3 Perbaikan lanjutan (diterapkan & diverifikasi)

- `app/seed/demo_credentials.py`: kelas `AkunDemo` → `akun["password"]` diselesaikan lewat `resolve_demo_password` (guard `DEMO_MODE` tetap satu pintu, tanpa literal di dict).
- `app/core/safety_gate.py`: `penghalang_sumber()` — SATU definisi blokir eksekusi (kosong/`fail`/karantina/kedaluwarsa; `pending` TIDAK memblokir).
- `app/services/supplier_eligibility.py`: `source_batch_safety_blocked` kini mendelegasikan ke `penghalang_sumber` → paritas `can_execute` ↔ `execute` bukan kebetulan.
- `app/api/actions.py`: memakai `batch_sumber_transfer` + `penghalang_sumber`; helper duplikat dihapus.
- `app/core/recommendation_numbers.py`: batas harga satuan tanpa ambang bawah (data sah 12 kg / Rp1.000 pernah ditolak); hanya absurditas (≤0 atau >Rp5 juta/kg) yang ditolak.
- `tests/conftest.py`: `DEMO_MODE=true` untuk proses tes + kebijakan `WindowsSelectorEventLoopPolicy`.

### 15.4 Angka suite

| Tahap | Hasil |
|---|---|
| Suite penuh SEBELUM koreksi malam | **20 failed, 1479 passed, 25 skipped, 31 errors, 622 s** |
| Setelah koreksi (grup terdampak) | wiring 10/10; numeric 12/12; receipts+approval+parity 26/27; seed/supplier/akun/review_only/waste 64/65 |
| `ruff check .` | **All checks passed** |
| Masih merah | 4 test: `test_recommendation_snapshot` (2, kontrak freshness pasca-F-02), `test_event1_e2e_acceptance` (1, urutan step), `test_decision_read_endpoints` (1, urutan step) |

Catatan: `test_suppliers_api::test_expired_batch_is_not_counted` gagal di DB `mealchain_gate2` yang kotor tetapi **lulus 26/26 di `mealchain_gate` bersih** → artefak isolasi data, bukan regresi.
