# REPAIR LOG — MealChain Guardian

> **Snapshot 25 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Catatan setiap langkah perbaikan: alasan, perintah, hasil, risiko. Tidak memuat nilai secret.

---

## E1 — Persiapan lingkungan uji (2026-10-25)

- **Tindakan:** menyalakan Docker Desktop; daemon siap (server 29.4.3, linux). Kontainer `mealchain-postgres`, `mealchain-backend`, `mealchain-frontend`, `mealchain-mock-sap` sudah berjalan (restart policy `unless-stopped`).
- **DB uji:** dibuat ulang database **terpisah** `mealchain_gate` di kontainer Postgres (port host 15432). Database demo `mealchain` **tidak disentuh**.
- **Perintah:** `DROP DATABASE IF EXISTS mealchain_gate` + `CREATE DATABASE mealchain_gate` (SQL DROP diakui; hanya DB gate, disposable).
- **Gate C (migrasi DB kosong → head):** `alembic upgrade head` → seluruh revisi 000→031 berjalan, `alembic current` = `031_ledger_generation (head)`. **PASS** — ini bukti pertama bahwa migrasi fresh DB benar-benar dapat dijalankan (sebelumnya BLOCKED karena Docker mati).
- **Seed data uji:** `python -m app.seed.seed_data --reference-time <jam-berjalan> --with-demo-users --with-demo-suppliers --skip-routes` → `locations=10 commodities=4 suppliers=60 batches=78 users=7 receipts=0`.
  - Catatan teknis: pada Windows, seed async gagal dengan `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`; dijalankan lewat pembungkus `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())`. Ini quirk environment, bukan cacat repo.
  - `--skip-routes` dipakai agar tidak memanggil OSRM (layanan eksternal).

## E2 — Baseline gate (sebelum perubahan kode)

| Gate | Perintah | Hasil |
|---|---|---|
| Lint BE | `ruff check .` | 1 error `I001` di `alembic/versions/022_disposal_partner.py:17` |
| Typecheck FE | `tsc --noEmit` | exit 0 |
| Lint FE | `next lint` | bersih |
| Test FE | `vitest run` | 166 file / 1794 test lulus |
| Migrasi | `alembic upgrade head` (DB kosong) | 031 head, bersih |
| Suite BE penuh | `pytest -q` pada `mealchain_gate` | lihat E3 |

## E3 — Baseline suite backend ber-DB

- **Percobaan 1** (DB gate kosong, tanpa seed): puluhan `F`/`E` — bukan cacat produk, melainkan suite membutuhkan data demo (fixture memilih batch/lokasi dari data seed). Dihentikan, hasil dibuang agar tidak dipakai sebagai baseline.
- **Percobaan 2** (setelah migrasi + seed): hasil lengkap dicatat di `%LOCALAPPDATA%\hermes\cache\scratch\baseline_suite.txt`; ringkasan dimasukkan ke `FINAL_VERIFICATION_REPORT.md`.

## E4 — Verifikasi ulang temuan (bukan menyalin laporan lama)

| ID | Status | Bukti |
|---|---|---|
| F-01 | CONFIRMED | `app/api/receipts.py:201` hanya menolak `fail` |
| F-02 | CONFIRMED | `app/core/freshness.py:29-32` (`outside_fraction = 0.0` bila bukti tidak lengkap) vs `app/core/safety.py:22-27` |
| F-03 | CONFIRMED | `app/services/event3_service.py:59-60,153-155,269-272`; `:157` menimpa `batch.safety_status`; tidak ada master data rentang suhu |
| A-01/F-06 | CONFIRMED | `app/api/actions.py:327-353` (`any(... != "fail")`, `True` bila kosong) dan `:321-322` (rewrite `usable_until` +6 jam) |
| F-09/A-02 | CONFIRMED | `app/api/decisions.py:151-152` (nilai dari caller) → `app/api/actions.py:799-805` (qty/cost dipakai langsung untuk PO) |
| F-07 | **FALSE POSITIVE** | `backend/tests/test_verifier_safety_guard.py` sudah ada (4 test) |
| D-01 | CONFIRMED (kode) | `app/seed/seed_data.py` `DEMO_USERS` memuat password literal; `--with-demo-users` dipakai jalur seed produksi |
| D-02/F-10 | CONFIRMED (kode) | `app/api/demo_session.py:29-44` → `butuh_sesi_aktif` mengembalikan `None` saat `DEMO_SESSION_ENFORCE=false` |
| F-08/D-04 | CONFIRMED (kode) | `app/api/admin.py:80,95,155,166` — semua endpoint (termasuk `PATCH`) hanya `require_roles("bgn_monitor")` |

## E5 — Siklus RED→GREEN

| # | Temuan | RED (diamati) | Patch | GREEN (diamati) |
|---|---|---|---|---|
| R2 | F-02 | `pytest tests/test_freshness_evidence_integrity.py` → **4 gagal, 1 lulus** (log kosong/satu sampel/malformed/duplikat/invarian) | `app/core/freshness.py` penalti penuh saat bukti tidak lengkap | file sama: **5 lulus** |
| R1 | F-01 | `pytest tests/test_receipts_safety_gate.py` → **2 gagal** (`409` diharapkan, dapat `200`) | `app/core/safety_gate.py` + `app/api/receipts.py` | **2 lulus**; `test_receipts_approval.py` + `test_receipts_api.py` tetap lulus (47→79 lulus gabungan) |
| R4 | A-01/F-06 | `pytest tests/test_execute_safety_wiring.py` → **7 gagal, 2 lulus** | `app/api/actions.py`: fail-closed + hapus rewrite `usable_until` + `(dikirim, ditahan)` | **9 lulus**; `test_actions*`, `test_action_boundary_e2e`, `test_can_execute_parity` → 41 lulus |
| R5 | F-09/A-02 | `pytest tests/test_decisions_numeric_validation.py` → **9 gagal** (201 untuk qty negatif, 500 untuk `"abc"`) | `app/core/recommendation_numbers.py` + `app/api/decisions.py` | **9 lulus**; regresi decisions/actions/security → 44 lulus |
| R6 | D-01 | `import app.seed.demo_credentials` → `ModuleNotFoundError`; seed tanpa `DEMO_MODE` dulu **berhasil** memasang password demo | `demo_credentials.py` + fail-fast di `seed_data.py` + `semai_kanonik.py` | `resolve_demo_password` 8 test lulus; seed tanpa `DEMO_MODE` → `[seed] menolak memasang password demo…`; dengan `DEMO_MODE=true` → seed sukses (78 batch/7 user) |
| R11 | D-06 | `docker compose config` dulu `published: 15432` tanpa `host_ip`; fallback `mealchain_local` | batasi ke `127.0.0.1`, `${POSTGRES_PASSWORD:?wajib}` | `host_ip: 127.0.0.1` untuk 8000/8001/15432; probe tanpa password → exit 1 `required variable POSTGRES_PASSWORD is missing a value` |
| R18 | Ruff I001 | `ruff check .` → 1 error | satu baris kosong di migrasi 022 | `ruff check .` → `All checks passed!` |

Penyesuaian test lama (bukan pelemahan): `_batch()` di `test_receipts_approval.py` memilih batch `pass` + ≥2 sampel suhu, karena approval non-`pass` kini ditolak (aturannya diuji di `test_receipts_safety_gate.py`).

Temuan yang TIDAK diperbaiki dan alasannya:
- **F-03** (rentang suhu per komoditas): nilai ambang keselamatan pangan tidak boleh dikarang; mekanisme + fail-closed menunggu tabel dari pemilik.
- **D-08/B-02** (`GET /batches` lintas lokasi): `app/api/batches.py:48-57` menyatakan ini disengaja untuk panel chaos Event 3; memfilter per lokasi mengosongkan panel. Perlu keputusan produk (endpoint terpisah untuk panel).
- **D-04/F-08** (`bgn_monitor` mengelola user): `app/api/admin.py:105-125` menyatakan keputusan owner 2026-10-17 karena skema tanpa peran `admin`, dengan pagar anti-ubah-peran-sendiri + ledger. Sisa risiko least-privilege dicatat.
- **D-02, D-03, C-05, C-09, C-12, A-09, R-01** — tercatat di `REPAIR_PLAN.md` §1b dengan alasan.

## E6 — Catatan environment

- Kunci gerbang pytest (`tests/conftest.py::kunci_gerbang`) mengunci **per database**. Karena itu dua DB uji dibuat: `mealchain_gate` (baseline/suite penuh) dan `mealchain_gate2` (siklus targeted), sehingga run tidak saling mencabut data.
- Suite penuh ber-DB pada `mealchain_gate` sempat menggantung pada ~45% (dua percobaan, >6 dan >10 menit); dihentikan dan dijalankan ulang dengan `timeout 1500`. Angka yang dipakai adalah hasil run terakhir yang selesai.
- DB demo `mealchain` tidak pernah ditulis oleh siklus ini.

## E7 — Koreksi siklus pertama (25 Okt 2026, malam)

Pemicu: review diff independen + dua reviewer verifikasi. Tiga kerusakan yang saya
sebabkan sendiri, semuanya sudah ditutup dan diuji:

1. `DEMO_USERS["password"]` dihapus → 29 `KeyError` pada suite penuh (20+ pemakai:
   `app/seed/reference.py:77`, 5 `scripts/verifikasi_*.py`, banyak test). Ditutup
   dengan `AkunDemo` di `app/seed/demo_credentials.py`: pembacaan password
   diselesaikan lewat `resolve_demo_password`, jadi guard `DEMO_MODE` tetap satu
   pintu dan tidak ada literal di dalam dict.
2. Gate eksekusi terlalu luas ("semua batch loc×komoditas harus `pass`") →
   `pending` yang tak terkait memblokir eksekusi selamanya (Jakarta/ayam,
   Surabaya/telur, Medan/ayam pada seed kanonik). Ditutup dengan
   `penghalang_sumber()` di `app/core/safety_gate.py` (kosong/`fail`/karantina/
   kedaluwarsa) + `batch_sumber_transfer`.
3. Paritas `can_execute` ↔ `execute` pecah. Ditutup dengan membuat
   `supplier_eligibility.source_batch_safety_blocked` mendelegasikan ke
   `penghalang_sumber` — satu definisi untuk kedua sisi.

Tambahan: batas harga satuan di `recommendation_numbers.py` sempat menolak data
sah (12 kg / Rp1.000); ambang bawah dihapus, hanya absurditas yang ditolak.
`tests/conftest.py` menetapkan `DEMO_MODE=true` untuk proses tes dan kebijakan
event loop Windows (sumber 7 error `ProactorEventLoop`).

Hasil: `ruff check .` bersih; 4 test masih merah (2 freshness snapshot, 2 urutan
step trace) — didokumentasikan, tidak disembunyikan.

## E8 — Penghalang demo (25 Okt 2026)

TDD: tes ditulis lebih dulu, gagal, lalu patch.

1. `tests/test_semai_demo_script.py` (baru) — RED: `semai-demo.sh` menyemai
   `--with-demo-users` tanpa `DEMO_MODE` → abort di guard D-01. Patch:
   `-e DEMO_MODE=true` pada dua pemanggilan seed (`:32`, `:99`). GREEN 2/2,
   `bash -n` bersih.
2. `tests/test_demo_penerimaan_pilihan.py` (baru) — RED: helper pemilihan tidak
   ada. Patch: `pilih_batch_penerimaan()` di `app/seed/demo_template.py`
   (satu batch `pending` + satu `pass`) dan `_semai_penerimaan` memakainya.
   Efek: satu penerimaan demo bisa disetujui (stok bergerak), satu ditolak 409
   sebagai demonstrasi gate F-01. GREEN 5/5.

Klasifikasi sisa 4 tes merah (dijalankan pada DB BARU `mealchain_gate3`,
migrasi 000→031 + seed kanonik): `test_event1_e2e_acceptance`,
`test_decision_read_endpoints`, `test_recommendation_snapshot` (2) tetap gagal
dengan `DEMO_MODE=false` juga → bukan efek perubahan conftest. Dua tes trace
(urutan langkah `DETECT…DECIDE`) tidak tersentuh perubahan ini dan perlu
investigasi terpisah; dua tes snapshot mengunci skor freshness 1,0 untuk batch
tanpa bukti suhu lengkap, yang bertentangan dengan F-02 → ekspektasinya yang
harus diperbarui, bukan aturannya dilonggarkan.
