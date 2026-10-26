# AUDIT_10 — Hasil Pengujian End-to-End

Lingkungan: stack Docker Compose berjalan (backend :8000, frontend :3010, postgres :15432), 26 Oktober 2026 07:00–08:50 WIB.
Alat: `verify_stack.py` (skill `fullstack-verification`) + Playwright (venv Hermes), pytest, vitest, psql.

## 10.1 Ringkasan angka

| Lapisan | Dijalankan | PASS | FAIL | SKIP/NOT TESTED |
|---|---|---|---|---|
| Gate BE+DB (`stack` 19, `invariants` 37, `roles` 20) | 76 pemeriksaan | **76** | 0 | 0 |
| Gate UI (matriks tab, 3 peran) | 3 flow | **3** | 0 | 1 (lapisan db tidak ada di spec — N/A) |
| Backend pytest (satu batch penuh) | 1487 tes | **1450** | **13** | 24 skip |
| Backend pytest (berkas gagal, diisolasi) | 57 tes | 54 | 3 | 0 |
| Backend pytest (berkas gagal, pengelompokan lain) | 18 tes | 18 | 0 | 0 |
| Frontend vitest | 1793 tes | **1793** | 0 | 0 |
| TypeScript | 1 | 1 | 0 | — |
| ESLint | 1 | 1 | 0 | — |
| ruff | 1 | 1 | 0 | — |
| alembic check | 2 (DB kerja + DB kosong) | 2 | 0 | — |

## 10.2 Skenario wajib

### E2E-01 — Startup sistem — **PASS**

- Prasyarat: stack compose hidup.
- Langkah: `docker ps`, `GET /health`, gate lapisan `process`, cek `docker events` untuk container mati.
- Expected: semua layanan sehat, tidak ada container mati dengan exit != 0.
- Actual: 4 container MealChain `Up`/`healthy`; `/health` 200 dalam 4 ms; 24–96 baris event direkam, **0 die dengan exit != 0**.
- Bukti: `verify/verify-out/report-*.md`, `verify-out-invariants/report-*.md`, `logs/docker-events.log`.

### E2E-02 — Data demo berasal dari DB — **PASS**

- Langkah: buka tab Hari Ini/Recommendations sebagai SPPG Head; bandingkan dengan DB.
- Actual: UI menampilkan 11 kartu siap tindak; DB `decisions` = 36 (Jakarta: 9 `pending_approval` + 2 `verifier_flagged`); 5 `demo_case` unik.
- Bukti: matriks tab PASS + query SQL.

### E2E-03 — Batas sesi dua jam — **PASS**

- Langkah: (a) `POST /demo/session/start`; (b) `POST /demo/session/extend {menit:240}`; (c) majukan `expires_at` ke masa lalu (fake clock, tanpa menunggu 2 jam) lalu cek `aktif()`; (d) mutasi tanpa sesi.
- Actual: (a) 120,0 menit, `remaining_seconds` 7199; (b) `expires_at` tidak berubah; (c) sesi tertutup dan baris demo milik sesi hilang, baris kerja tanpa stempel tetap; (d) `POST /actions/approve` → 409.
- Bukti: probe runtime + `tests/test_demo_sesi_batas_dan_enforcement.py` (6 tes) + `tests/test_demo_session.py` (skenario kedaluwarsa, opt-in, 14/14 pada DB salinan).

### E2E-04 — Reset demo — **PASS**

- Langkah: catat baseline → ubah data (eksekusi kartu) → `POST /demo/refresh`/rebuild → baca ulang → ulangi.
- Actual: idempoten (`dilewati: snapshot kanonik sudah ada`); setelah rebuild: 36 keputusan, 660 menu, 5.240 pasokan, 7 user, 1 sesi aktif; baris kanonik tidak berstempel sesi (invarian 0).
- Catatan: 3× rebuild nyata dalam sesi ini, hasil konsisten.
- **Temuan saat uji ini:** rebuild pertama setelah suite pytest membuat gate invarian merah (`executed tanpa persetujuan = 2`). Ditelusuri ke penyemai template yang hanya menangani `regional_balance` (BUG-006), diperbaiki, rebuild ulang → **invarian 37/37 PASS**, `approvals` 12, `executed tanpa approval` 0.

### E2E-05 — Lima rekomendasi Jakarta — **PARTIAL**

- Expected (PRD): 5 rekomendasi Jakarta hari ini.
- Actual: **11 kartu** siap tindak dari **5 skenario** unik; tidak ada duplikasi setelah refresh/rebuild.
- Status: PARTIAL — jumlah kartu ≠ 5, tetapi tidak ada duplikasi dan semua dapat ditelusuri ke `demo_case`.

### E2E-06 — KPI hari ini bergerak karena aksi — **PASS**

- Langkah: catat KPI → approve ×2 → execute → baca KPI lagi.
- Actual: Safe Delivered Cost 15.749.032,38 (n=1) → 18.914.947,39 (n=2); Price Deviation 3,28% (18) → 3,49% (19); Decision Time `—` (7 eligible) → 20,98 menit (1); Evidence Completeness `—` → 0,00% (1).
- Verifikasi DB: 2 baris `approvals`, 1 PO, 1 trace ACT, status `executed`.

### E2E-07 — KPI 7 hari & 1 bulan, zona waktu — **PASS**

- Actual: `today` start `2026-10-25T17:00Z` (= 26 Okt 00:00 WIB); `7d` 7 sampel Meal Continuity; `1bulan` 26 sampel (bulan berjalan, bukan 30 hari); `periode=24h` → 422.
- Bukti: probe + `test_kpi_period.py`, `test_kpi_batas_tanggal.py`.

### E2E-08 — Approval pihak pertama — **PASS**

- Actual: `POST /actions/approve` (sppg_head) → 200; status tetap `pending_approval`; tidak ada batch yang berangkat.

### E2E-09 — Approval pihak kedua — **PASS**

- Actual: approve `sppg_nutritionist` → 200; status `approved`; `execute` → `executed` + PO `MC-215FFA979FCB`.

### E2E-10 — Approval tidak valid — **PASS**

- Akun sama dua kali → 409 "approval sudah tercatat untuk akun ini".
- Peran tanpa izin → 403 (roles.spec).
- `execute` sebelum 2 approval → 409; sebelum verifikasi → 409.
- Approval atas keputusan yang tidak ada → 404 (invariants).
- Dua approval paralel: dijaga unique constraint; **tidak diuji dengan thread paralel** (NOT TESTED untuk race nyata).

### E2E-11 — Animasi pengiriman — **PASS**

- Actual: `dispatched_at` terisi untuk 5 batch; `GET /supplier-routes` 12 rute (`di_jalan` 6, `sudah_tiba` 5, `tidak_diketahui` 1); `progress` naik 6/6 rute dalam 8 detik.
- Catatan: UI mem-**poll**; tidak ada klaim real-time.

### E2E-12 — Notifikasi — **PASS (dengan batasan desain)**

- Actual: daftar turunan `/decisions`; 12 → 9 baris setelah 3 eksekusi; tanpa read-state (bukan fitur).

### E2E-13 — Kegagalan backend saat aksi — **NOT TESTED**

- Tidak ada fault injection (mematikan backend di tengah alur) pada audit ini; UI `.catch()` menelan galat sehingga risiko "tampak kosong" nyata (FE-01). Tidak diklaim PASS.

### E2E-14 — Hak akses — **PASS**

- 16 pemeriksaan roles: 401 tanpa token, 403 lintas lokasi, 403 monitor pada endpoint demo, 403 kepala SPPG pada `/admin/*`, 200 pada resource miliknya.

### E2E-15 — Isolasi demo & regresi — **PARTIAL (temuan P1)**

- Positif: invarian "baris kanonik tidak berstempel sesi" = 0 pelanggaran; reset tidak menyentuh master data.
- **Negatif (temuan baru):** menjalankan **seluruh suite pytest terhadap DB demo** (cara yang tertulis di `AGENTS.md`) menghapus seluruh baris `origin='demo'` dan meninggalkan 15 akun `@test.local`. Terukur setelah satu run penuh: `decisions` 36 → **9** (semua `origin='seed'`), `menu_plans` 660 → **70**, `supply_records` 5.240 → **40**, `agent_traces` 85 → **18**, `users` 7 → **22**. Baseline dipulihkan dengan rebuild (kembali 36/660/5.240/7).
- Status: PARTIAL — fungsional demo aman bila suite tidak dijalankan pada DB demo; prosedur yang didokumentasikan justru merusaknya.

## 10.3 Analisis 13 kegagalan pytest

| Berkas | Jumlah | Perilaku saat diisolasi | Kesimpulan |
|---|---|---|---|
| `test_demo_timeseries_api.py` | 4 | berkas + `test_timeseries_db` = 22/22 PASS | urutan/state |
| `test_timeseries_db.py` | 1 | PASS bila berpasangan dengan `test_tool_contracts` | urutan/state |
| `test_event3_api.py` | 1 | PASS di grup 6 berkas | urutan/state |
| `test_s4_verifier_independence.py` | 3 | PASS di grup 6 berkas | urutan/state |
| `test_sap_orders_api.py` | 2 | PASS di grup 6 berkas | urutan/state |
| `test_tool_contracts.py` | 2 | 18/18 PASS saat berpasangan dengan `test_timeseries_db` | urutan/state |

Kesimpulan: **tidak ada kegagalan deterministik** yang terbukti berasal dari kode produk; semuanya bergantung state DB yang ditinggalkan tes sebelumnya (suite tidak mengisolasi transaksi). Ini tetap cacat kualitas pengujian (AUD-TEST-01, P2) karena membuat CI lokal tidak dapat dipercaya.

## 10.4 Yang tidak diuji (eksplisit)

- Panggilan nyata ke Bedrock AgentCore / SAP AI Core (biaya & izin).
- Login melalui pengetikan password (kebijakan agen); login UI diuji lewat tombol peran demo.
- Fault injection backend mati saat aksi (E2E-13).
- Uji beban, kontras warna, axe-core, keyboard/fokus, reduced motion.
- Race approval paralel dan reset bersamaan.
- `verify/decisions.spec.json` (butuh stack terisolasi) dan `stack.coldstart.spec.json` (menghentikan stack demo).
