# REPAIR_PLAN — MealChain Guardian

> **Snapshot 25 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Disusun:** 2026-10-25 · **Basis:** `PROJECT_AUDIT_REPORT.md` (audit baseline, sebelum perubahan)
**Status keseluruhan:** 0 fix diterapkan. Rencana ini belum dieksekusi.

Aturan main:
1. Urut: Critical → High → Medium → Low. Setiap fix wajib punya test regresi yang **gagal pada baseline** (RED) lalu lulus (GREEN).
2. Safety gate tidak boleh dilunakkan, test tidak boleh di-skip/dihapus, expected result tidak boleh diubah mengikuti kode yang salah.
3. Perubahan sekecil mungkin; file pengguna yang sudah dirty tidak ditimpa. Jika tidak bisa digabung dengan yakin → `BLOCKED`.
4. Angka/ambang domain (mis. rentang suhu per komoditas) **bukan** keputusan saya: menunggu penetapan pemilik produk.

---

## 1. Tabel kerja

| ID | Temuan / akar masalah | Sev | Bukti baseline | Rencana | Tes regresi | File diperkirakan berubah | Risiko | Status |
|---|---|---|---|---|---|---|---|---|
| R1 | F-01: `POST /receipts/{id}/approve` hanya menolak `fail`; `pending`/`needs_verification`/null lolos ke stok | Critical | `backend/app/api/receipts.py:201` | Predikat fail-closed: setujui hanya bila `safety_status == "pass"` **dan** evidence suhu ada (`temperature_log` tidak kosong, `complete`), **dan** belum kedaluwarsa. Ekstrak ke helper domain agar bisa diuji tanpa DB. | test helper: `pending`, `needs_verification`, `None`, log kosong → tolak; `pass` + log lengkap → izinkan; endpoint test (DB) | `app/api/receipts.py`, helper baru di `app/core/` | Menolak penerimaan yang dulu lolos pada data demo → perlu cek seed/demo | TODO |
| R2 | F-02: log suhu kosong/tidak lengkap ⇒ `outside_fraction=0.0` ⇒ skor freshness bisa `pass` | Critical | `app/core/freshness.py:29-32` vs `app/core/safety.py:22-27` | Fail-closed: evidence tidak lengkap tidak boleh menghasilkan `pass`. Terapkan penalti penuh (`outside_fraction=1.0`) atau kembalikan flag `evidence_complete` yang dipakai `classify_freshness` untuk menurunkan ke `needs_verification`. Pilih satu kontrak dan selaraskan dengan safety. | `test_freshness`: log `[]`, 1 sampel, entri malformed, timestamp duplikat → **tidak** boleh `pass`; log lengkap bersih → `pass` | `app/core/freshness.py`, `tests/test_freshness.py` | Mengubah skor banyak batch demo & beberapa test lama yang mengharapkan `pass` | TODO |
| R3 | F-03: rentang aman hard-coded `0.0–8.0` untuk semua komoditas, menimpa `batch.safety_status` | Critical | `app/services/event3_service.py:59-60,153-155,157,269-272` | Buat satu sumber aturan: `app/core/commodity_rules.py` (dataclass + validasi, lookup per komoditas/kelompok penyimpanan). Komoditas tak dikenal → **fail-closed** (`needs_verification`), bukan default 0–8. `event3_service` memakai aturan ini; tidak menulis verdict dari luar core. | test lookup: komoditas dikenal → rentang eksplisit; tak dikenal → fail-closed; test bahwa event3 tidak lagi memakai konstanta | `app/core/commodity_rules.py` (baru), `app/services/event3_service.py`, `tests/test_event3_service.py` | **Butuh nilai domain dari pemilik** (ayam/beku vs telur vs wortel vs beras). Salah nilai = false-pass/false-fail pada juri | **BLOCKED — perlu keputusan pemilik** |
| R4 | A-01/F-06: gate eksekusi `any(status != "fail")`, abaikan quarantine & expiry; dispatch menulis ulang `usable_until` +6 jam | High | `app/api/actions.py:327-353`, `:321-322` | Gate `all(...)`: hanya batch `pass` + tidak dikarantina + belum kedaluwarsa + punya log suhu; batch hilang → tolak (bukan `True`). Hapus penulisan ulang `usable_until`; tolak dispatch batch kedaluwarsa. | test helper: campuran `pass`+`fail` → tolak; semua `pass` tapi satu kedaluwarsa → tolak; quarantined → tolak; tidak ada batch → tolak; dispatch tidak mengubah `usable_until` | `app/api/actions.py`, `tests/test_execute_safety_gate.py` (baru) | Bisa memblokir alur demo yang mengandalkan batch `pending` | TODO |
| R5 | F-09/A-02: `quantity_kg`/`safe_delivered_cost` dipercaya dari caller | High | `app/api/decisions.py:151-152` | Validasi server-side: `Decimal`, `> 0`, batas atas wajar, konsisten dengan `cost_breakdown`/harga acuan; recompute `safe_delivered_cost` dari komponen bila tersedia; tolak mismatch. Pastikan PO memakai nilai tersimpan hasil validasi. | test: `quantity_kg` negatif/0/`"abc"`/overflow → 422; cost tidak konsisten → 422; jalur valid → 201 | `app/api/decisions.py`, `app/schemas/*` terkait, test baru | Mengubah kontrak request; agen/seed yang mengirim angka aneh akan ditolak (memang tujuannya) | TODO |
| R6 | D-01: password demo fixed + seed produksi | Critical (secret) | `app/seed/seed_data.py:717-763`, `docker-compose.prod.yml:18` | Seed menolak berjalan tanpa `DEMO_MODE=true` **atau** password eksplisit dari env; tidak ada literal password; guard nilai default | test: seed menolak tanpa flag; menerima dengan env | `app/seed/seed_data.py`, `.env.example`, docs seed | Demo manual di VPS berhenti bila env belum diset → perlu instruksi jelas | MENUNGGU V3 |
| R7 | D-02/F-10: `/demo/*` destruktif saat session enforcement mati | High | `app/api/demo_session.py`, `app/api/demo.py` | Paksa sesi aktif untuk endpoint destruktif (server-side, bukan flag opsional); default aman | negative test: tanpa sesi → 409/403 | route demo + test | Alur demo juri bisa terblokir bila sesi belum dimulai | MENUNGGU V3 |
| R8 | F-08/D-04: `bgn_monitor` bisa menulis `/admin/*`; token panjang | High | `app/api/admin.py`, `app/api/auth.py` | **Butuh keputusan pemilik** (requirement tiga-role): pisahkan capability admin vs monitor, atau cabut write. Jangan menambah role diam-diam. | test matriks role per route | `app/api/admin.py`, `app/core/scope.py` | Perubahan model izin = perubahan produk | **BLOCKED — keputusan pemilik** |
| R9 | D-08/B-02: `GET /batches` tanpa scope; `GET /receipts?batch_id` eksemptif tapi lebih luas dari alasannya | High | `app/api/batches.py:36-53`, `app/api/receipts.py` | Terapkan scope lokasi; untuk receipts, batasi eksempti ke role pemantau (bukan semua role) | negative test cross-tenant | `app/api/batches.py`, `app/api/receipts.py` | UI demo lintas-lokasi bisa kosong | MENUNGGU V3 |
| R10 | D-03: rate limit via `X-Forwarded-For` + tanpa limit per akun | Medium | `app/api/auth.py`, compose prod | Counter per akun + trusted proxy eksplisit | test: brute force N kali → 429 meski IP berubah | auth + middleware | Login demo bisa kena limit | MENUNGGU V3 |
| R11 | D-06: compose prod mem-publish 15432/8000 ke 0.0.0.0, fallback password | High | `docker-compose.prod.yml:33-34,62-63` | Bind ke `127.0.0.1` atau network internal; hapus fallback password | pemeriksaan konfigurasi + healthcheck | `docker-compose.prod.yml` | Akses demo dari luar VPS bisa hilang → dokumentasikan cara akses aman | MENUNGGU V3 |
| R12 | C-05, C-09, C-12: provider exhaustion → 500; veto tidak memengaruhi status; model id tidak tercatat | High/Medium | `app/ai_providers/verifier_client.py`, `agent/orchestrator.py` | Tangkap `ProviderUnavailableError` → status `unverified`; persist `safety_veto` ke status/run; tambah metadata provider/model (non-secret) | test provider mati → `unverified`, bukan 500; test veto → status bukan `completed` | agent + verifier | Perubahan skema trace → cek migrasi | MENUNGGU V3 (C) |
| R13 | A-09: migrasi tidak dijalankan saat start; readiness tidak memeriksa schema | Medium | `backend/Dockerfile`, compose, `app/main.py` | Entrypoint migrasi sekali (bukan per-replica race) + readiness gate `alembic current == head` | uji fresh DB (butuh DB) | Dockerfile/compose/entrypoint | Bisa memperlambat start | BLOCKED (butuh DB) |
| R14 | R-01: drift `backend/openapi.json` (26/27 vs 75/77) | Medium | hitung route vs file | Regenerasi resmi + CI drift guard | CI step gagal bila beda | `backend/openapi.json`, `ci.yml` | Regenerasi besar pada satu file generated | MENUNGGU V4 |
| R15 | Lane topology ganda (`agent/hierarchy.json` vs `LANES`) | Medium | `agent/orchestrator.py`, `agent/hierarchy.json` | Satu sumber kebenaran; hapus/hidupkan data stale | test loader | agent | Risiko mengubah urutan lane | MENUNGGU V4 |
| R16 | Advisory dependency (next/maplibre/starlette dll) + drift dokumentasi | Medium/Low | lockfile + docs | Hanya upgrade yang terverifikasi advisory + kompatibel; sinkronkan docs **setelah** implementasi terbukti | npm audit / pip-audit + seluruh gate | `package.json`/lock, `requirements.txt`, docs | Upgrade bisa memecah build | MENUNGGU V4 |
| R17 | F-07: test regresi verifier guard dianggap tidak ada | — | `tests/test_verifier_safety_guard.py` ada, 4 test | **Tidak ada pekerjaan** (false positive) | — | — | — | **CLOSED — false positive** |
| R18 | Ruff `I001` di `alembic/versions/022_disposal_partner.py:17` | Low | `ruff check .` | Urutkan import | `ruff check .` → 0 | file migrasi | Nol (cosmetic) | TODO |

---

## 2. Mapping finding → perubahan → test → hasil

Diisi saat eksekusi. Format: `ID | file:line | test | RED (output) | GREEN (output) | commit? (tidak ada commit)`.

| ID | File | Test | RED | GREEN |
|---|---|---|---|---|
| — | — | — | — | — |

---

## 3. Checklist rotasi kredensial (tindakan pemilik — di luar kode)

Status seluruh item: **BLOCKED — perlu pemilik kredensial**. Membuat checklist tidak merotasi apa pun.

1. `SIGNING_KEY_HEX` — pernah ada di blob `.env` historis; ganti dan tanda-tangani ulang dossier uji.
2. `POSTGRES_PASSWORD` — ganti di VPS + `.env` produksi.
3. Provider key (InferHub/SAP/AWS sesuai `.env`) — rotasi di provider masing-masing.
4. `MEALCHAIN_API_TOKEN` — cabut, terbitkan baru dengan scope minimum.
5. Filter history (mis. `git filter-repo`) hanya setelah rotasi selesai, dan hanya bila pemilik memutuskan; jangan otomatis.

---

## 4. Acceptance criteria global (definisi "selesai" yang sah)

- [ ] Semua R1–R5 (Critical/High safety & integrity) fixed + test regresi lulus.
- [ ] R6–R11 diselesaikan atau ditandai `BLOCKED` dengan alasan yang diterima pemilik.
- [ ] `ruff` = 0 error; `tsc` = 0; `next lint` bersih; vitest lulus; pytest domain lulus.
- [ ] Tidak ada test/check yang dilemahkan, di-skip, atau dihapus.
- [ ] File pengguna (7 M / 38 D / 1 ??) tetap utuh; `docs/Architecture.md` & `docs/Schema.md` tidak disentuh sebelum keputusan pemilik.
- [ ] `git diff` hanya memuat perubahan yang disengaja.

## 5. Blocker yang perlu keputusan/aksi manusia

| # | Blocker | Yang dibutuhkan | Dampak bila tidak ada |
|---|---|---|---|
| B1 | Tidak ada PostgreSQL uji / Docker daemon mati | izin menyalakan Docker Desktop + `docker compose up -d postgres`, **atau** DSN database test yang boleh dihapus | Gate C/D, R7, R9, R11, R13, R14 tidak dapat diverifikasi — hanya `BLOCKED` |
| B2 | Requirement model izin (tiga role) untuk R8 | keputusan pemilik: pisahkan capability admin / cabut write `bgn_monitor` | R8 tidak dikerjakan |
| B3 | Angka rentang suhu sah per komoditas untuk R3 | tabel dari pemilik/standar (ayam chilled/frozen, telur, wortel, beras) | R3 hanya bisa memakai mekanisme fail-closed, nilai tetap menunggu |

---

## 1b. Status akhir siklus pertama (2026-10-25)

| ID | Status | Bukti |
|---|---|---|
| R1 F-01 | **FIXED** | `app/core/safety_gate.py` + `app/api/receipts.py`; `tests/test_receipts_safety_gate.py` (2) |
| R2 F-02 | **FIXED** | `app/core/freshness.py`; `tests/test_freshness_evidence_integrity.py` (5) |
| R3 F-03 | **BLOCKED — nilai domain** | mekanisme belum dipasang; butuh tabel rentang sah per komoditas dari pemilik |
| R4 A-01/F-06 | **FIXED** | `app/api/actions.py`; `tests/test_execute_safety_wiring.py` (9) |
| R5 F-09/A-02 | **FIXED** | `app/core/recommendation_numbers.py` + `app/api/decisions.py`; `tests/test_decisions_numeric_validation.py` (9) |
| R6 D-01 | **FIXED (kode)** / rotasi **BLOCKED** | `app/seed/demo_credentials.py`; `tests/test_seed_credential_guard.py` (8) |
| R7 D-02 | **OPEN** | keputusan produk soal default `DEMO_SESSION_ENFORCE` |
| R8 D-04/F-08 | **ACCEPTED RISK** | `app/api/admin.py:105-125` = keputusan owner 2026-10-17 + pagar ledger; sisa risiko least-privilege dicatat |
| R9 D-08/B-02 | **ACCEPTED RISK** | `app/api/batches.py:48-57` = disengaja untuk panel Event 3; perlu endpoint terpisah bila ingin di-scope |
| R10 D-03 | **OPEN** | butuh keputusan topologi proxy |
| R11 D-06 | **FIXED** | `docker-compose.prod.yml` (loopback + password wajib) |
| R12 C-05/C-09/C-12 | **OPEN** | siklus berikutnya |
| R13 A-09 | **PARTIAL** | jalur verifikasi sudah `alembic upgrade head`; stack produksi belum punya entrypoint migrasi sekali-jalan |
| R14 R-01 | **OPEN** | regenerasi resmi + CI drift guard |
| R15 lane ganda | **OPEN** | belum diverifikasi ulang |
| R16 dependency/docs | **OPEN** | `pip-audit`/`npm audit` belum dijalankan |
| R17 F-07 | **CLOSED — false positive** | test sudah ada |
| R18 Ruff I001 | **FIXED** | `ruff check .` = 0 |
