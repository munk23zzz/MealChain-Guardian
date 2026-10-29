# Laporan Remediasi — MealChain Guardian

**Tanggal eksekusi:** 29 Oktober 2026
**Basis temuan:** `docs/audit/AUDIT_2026-10-29_FULLSYSTEM.md` (AUD-001…AUD-050)
**Rencana acuan:** `docs/plans/audit-2026-10-29-remediation-plan.md`
**Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian` — branch `feature/db-modes-demo-coverage`, HEAD `9019eb1`
**Working tree saat mulai:** 146 entri (97 ` M`, 45 `??`) — pekerjaan pengguna yang belum di-commit, **tidak disentuh/direset**.

> Laporan ini hanya memuat pekerjaan yang benar-benar dieksekusi pada run ini. Yang belum dikerjakan ditulis
> sebagai `OPEN`/`BLOCKED`, bukan dihilangkan.

---

## 1. Ringkasan eksekusi

| Gate | Sebelum | Sesudah | Bukti |
|---|---|---|---|
| `ruff check .` (backend) | 12 error (7 fixable) | **0 error** | `All checks passed!` |
| `tsc --noEmit` (frontend) | 4 error | **0 error** | `npm run typecheck` exit 0 |
| `next lint` | bersih | bersih | `✔ No ESLint warnings or errors` |
| `alembic check` | **GAGAL** (drift index) | **bersih** | `No new upgrade operations detected.` |
| `vitest run` | 2728 lulus / 244 file | **2728 lulus / 244 file** | tanpa regresi |
| Artefak `openapi.json` | 87 path (3 endpoint hilang) | **90 path** | tes drift lulus |
| pytest (suite penuh) | 30 gagal / 2256 lulus / 36 skip / 3 error | lihat §7 | DB berbeda — lihat catatan §7 |

**DB demo `mealchain` tidak disentuh.** Semua pengujian yang menulis berjalan pada database sekali-pakai
`mealchain_fix` (dibuat ulang dari nol: `createdb` → `alembic upgrade head` → `seed_data`).

---

## 2. Temuan yang ditutup pada run ini

Format kolom mengikuti §10 prompt. Semua path relatif terhadap `mealchain-guardian/`.

### AUD-005 — Kredensial demo terbuka tanpa autentikasi

| Field | Isi |
|---|---|
| Status awal | OPEN — `GET /auth/demo-login` mengembalikan 7 akun + sandi (len 12–13) kepada pemanggil **tanpa token**, dengan `DEMO_MODE=true` + `DEMO_LOGIN_AUTOFILL=true` |
| Root cause | Dua flag saja sebagai kunci, tanpa syarat asal pemanggil. Backend bind `0.0.0.0:8000`, jadi siapa pun di jaringan yang sama (atau lewat tunnel) menerima sandi demo |
| File diubah | `backend/app/api/auth.py`, `.env.example`, `backend/tests/test_demo_accounts_browser.py` |
| Patch | Kunci **ketiga**: `boleh_autofill_dari(request)` — hanya loopback (`127.0.0.1`, `::1`), gateway container (host yang menjalankan browser demo, dibaca dari `/proc/net/route`), dan `testclient` yang dilayani. Klien LAN/publik menerima `enabled:false` tanpa daftar akun. Override eksplisit `DEMO_LOGIN_ALLOW_REMOTE=true` untuk kios/proyektor |
| Test | `pytest tests/test_demo_accounts_browser.py` (+ unit test `boleh_autofill_dari`) |
| Hasil sebelum | Endpoint 200 + 7 akun + sandi dari pemanggil mana pun |
| Hasil sesudah | **12 lulus**. `_Req("192.168.1.20")`/`_Req("10.0.0.7")` → `False`; gateway/loopback → `True` |
| Regression | `tests/test_auth.py` + `test_demo_accounts_browser.py` = 18 lulus |
| Risk | IP-based, bukan Host-based: penyerang di LAN tidak memperoleh sandi, tetapi klien yang lewat gateway (mis. reverse proxy) tetap dilayani. `DEMO_MODE` tetap wajib mati untuk deployment nyata |
| Status | **VERIFIED** |
| Evidence | `auth.py` → `_HOST_LOKAL`, `_ip_gateway()`, `boleh_autofill_dari()`, `demo_login_accounts()` |

Catatan verifikasi independen: dari host, `curl http://localhost:8000/auth/demo-login` semula berubah
`enabled:false` karena container melihat `172.20.0.1` — itulah yang memaksa aturan gateway ditambahkan
(bukan sekadar lolos tes). Setelah patch, endpoint host kembali melayani demo sementara tes membuktikan
IP LAN tetap ditolak.

### AUD-007 — Sampel suhu terakhir diabaikan (keselamatan pangan)

| Field | Isi |
|---|---|
| Status awal | OPEN — `[5 °C, 5 °C, 20 °C]` pada band 0–8 °C menghasilkan `outside_minutes=0.0`, `complete=True` |
| Root cause | `summarize_temperature_log` menilai tiap interval hanya dari sampel `prev`; sampel terakhir tidak pernah menjadi `prev`, sehingga kenaikan di ujung log tidak pernah dihitung |
| File diubah | `backend/app/core/temperature.py`, `backend/tests/test_temperature.py` |
| Patch | Interval **terakhir** juga dihitung bila ujung `curr` di luar rentang. Interval lain tidak diubah — percobaan pertama ("salah satu ujung") **menggandakan** spike satu sampel dan memecah 2 tes kalibrasi freshness/safety, sehingga dibatalkan |
| Test | `test_out_of_range_last_sample_counts_its_interval` (baru), `test_out_of_range_first_sample_counts_its_interval`, `test_excursion_just_under_thirty_minutes_needs_verification`, `test_excursion_penalty_halves_score_to_seventy_five_percent` |
| Hasil sebelum | `(5,5,20)` → `outside=0.0` |
| Hasil sesudah | `(5,5,20) → outside=60.0`; `(20,20,5) → 120.0`; `(4,20,4) → 60.0`; `(5,5,5) → 0.0` |
| Regression | 75 lulus (temperature, freshness, freshness_evidence_integrity, safety, safety_gate_rules, safety_komoditas, execute_safety_wiring, receipts_safety_gate, agent_freshness_gate) |
| Risk | Interval terakhir hanya dihitung sekali; ekskursi yang berlanjut setelah sampel terakhir tetap tidak terlihat — batas data, bukan batas aturan |
| Status | **VERIFIED** |
| Evidence | `temperature.py` blok `prev_luar or (posisi == jumlah_interval - 1 and curr_luar)` |

Dua tes lain di `test_temperature.py` juga merah karena assertion-nya masih mencari kata Inggris
(`"malformed"`, `"sample"`) sementara pesan produk sudah dilokalkan ke Bahasa Indonesia. Assertion
diperbarui ke teks Indonesia; **perilaku yang diuji tidak berubah** (`complete=False`, `observed=0`).

### AUD-019 — Verifier meloloskan keputusan tanpa bukti ledger

| Field | Isi |
|---|---|
| Status awal | OPEN — `cek_ledger` mengembalikan `lulus=True` untuk `jumlah==0 and not aksi` **tanpa melihat status** |
| Root cause | Dua hal: (1) status dibaca hanya dari `fakta["status"]` sehingga pemanggil yang tidak mengirimnya membuat cabang status menjadi kode mati; (2) cabang pertama sudah meloloskan lebih dulu |
| File diubah | `agent/verifier_checks.py` |
| Patch | Status = `fakta["status"]` → fallback `klaim.status`; hanya status pra-eksekusi (`proposed`, `pending`, `menunggu`, `pending_approval`, `review_only`, `verifier_flagged`) yang boleh lulus dengan 0 blok |
| Test | `test_ledger_belum_ada_aksi_tidak_menandai` (proposed lulus, approved **tidak**), `test_ledger_tanpa_aksi_lulus_apa_pun_statusnya` (3 status pra-aksi lulus), `test_ledger_dengan_aksi_tetap_diaudit` |
| Hasil sebelum | `approved` + 0 blok → `lulus=True` |
| Hasil sesudah | `approved` → `False`; `proposed`/`pending_approval`/`verifier_flagged` → `True` |
| Regression | 81 lulus (verifier_angka_bersitasi, agent_verifier_independence, agent_verifier, agent_verify, verifier_*) |
| Risk | Keputusan `approved` yang belum dieksekusi (normal) kini ditandai dan menjadi `verifier_flagged`; sesuai default rencana (O4) `verifier_flagged` tidak memblokir approval, hanya tercatat |
| Status | **VERIFIED** |

### AUD-009 — Event 3 menilai semua komoditas dengan rantai dingin 0–8 °C

| Field | Isi |
|---|---|
| Status awal | OPEN — `event3_service` memanggil `evaluate_safety(log, 0.0, 8.0, 30.0)` untuk **semua** komoditas |
| Root cause | Nilai bawaan ditulis langsung di service, bukan diambil dari `CommodityPolicy` seperti `/safety/evaluate` |
| File diubah | `backend/app/services/event3_service.py` |
| Patch | `profil_untuk_komoditas(db, batch.commodity_id)` → `evaluate_safety(log, policy=policy)`. Fallback 0–8 °C hanya untuk batch tanpa profil (nilainya identik dengan bawaan profil: **tidak ada ambang baru**) |
| Test | `tests/test_event3_service.py`, `test_event3_api.py`, `test_commodity_policies.py`, `test_commodity_expansion.py` |
| Hasil sesudah | 55 lulus (1 gagal karena assertion pesan Inggris → diperbaiki, lihat AUD-014) |
| Risk | Belum ada tes level-service yang membuat 4 batch (beras/ayam/telur/sayur) lalu memeriksa status tersimpan. Wiring dibuktikan lewat pyright + seluruh tes event3 lulus, bukan lewat tes komoditas end-to-end → **butuh tes tambahan sebelum disebut tuntas** |
| Status | **FIXED** (bukan VERIFIED) |

### AUD-006 — Token layanan agen dapat mengelola pengguna

| Field | Isi |
|---|---|
| Status awal | OPEN — `MEALCHAIN_API_TOKEN` adalah JWT akun berperan `bgn_monitor`, dan `PATCH /admin/users` hanya butuh role itu |
| Root cause | RBAC tidak dapat membedakan sesi manusia dari token agen yang memakai akun manusia |
| File diubah | `backend/app/api/auth.py`, `backend/app/api/admin.py`, `backend/tests/test_admin_api.py`, `backend/tests/test_admin_jejak_audit.py`, + `backend/tests/test_admin_sesi_manusia.py` (baru) |
| Patch | `_issue_token` menambahkan klaim `typ:"user"`; `get_current_user` menyimpan `_token_typ`; `require_sesi_manusia` menolak token tanpa klaim itu; router `/admin` memakainya sebagai dependency level-router |
| Test | `test_token_layanan_tanpa_klaim_typ_ditolak_403`, `test_sesi_login_boleh_mengakses_admin` |
| Hasil sesudah | Token gaya layanan (JWT sah, role admin, tanpa `typ`) → **403**; token hasil login → **200** |
| Regression | `test_admin_api.py` + `test_admin_jejak_audit.py` 75 lulus (fixture identitas palsu kini menyatakan dirinya sesi manusia) |
| Risk | Token lama buatan tangan (mis. `MEALCHAIN_API_TOKEN` yang beredar) langsung 403 di `/admin` → **token layanan harus diterbitkan ulang**, dan itu tindakan pemilik akses (lihat AUD-004). Sesi manusia cukup login ulang |
| Status | **VERIFIED** (kontrol), **BLOCKED** (penerbitan ulang token layanan) |

### AUD-013 / AUD-020 — Kontrak KPI 7 vs 8 metrik

| Field | Isi |
|---|---|
| Status awal | OPEN — API mengembalikan 8 metrik; dokumen, tes, dan UI memakai 7 |
| Root cause | Metrik ke-8 (`Effective Price per Accepted Kg`) ditambahkan ke `METRIC_NAMES` tanpa keputusan kontrak |
| File diubah | `backend/app/services/kpi_service.py`, `backend/tests/test_kpi_harga_efektif.py` |
| Patch | `_daftar_metrik()` menjadi satu-satunya sumber; metrik ke-8 hanya ikut bila `KPI_EFFECTIVE_PRICE_ENABLED=true` (bawaan **false**). Komputasinya tidak dihapus. Assert internal memakai daftar runtime, bukan konstanta yang dibekukan saat impor |
| Test | `test_kpi.py`, `test_kpi_api.py`, `test_kpi_alasan_no_data.py`, `test_kpi_provenance.py`, `test_kpi_act_trace.py`, `test_kpi_harga_efektif.py` |
| Hasil sesudah | 51 lulus (kontrak 7) + 6 lulus (metrik ke-8 dengan flag aktif) |
| Risk | Fitur baru tidak tampil di UI sampai keputusan O1. **Bukan** penghapusan kemampuan: satu env menyalakannya kembali |
| Status | **VERIFIED** (kontrak), keputusan produk **OPEN (O1)** |

### AUD-008 — `evaluation_time` dapat dimundurkan/dimajukan pemanggil

| Field | Isi |
|---|---|
| Status awal | PARTIAL — `evaluation_time` diteruskan apa adanya ke `evaluate_safety` |
| Root cause | Tidak ada validasi; pemanggil dapat memakai waktu mana pun |
| File diubah | `backend/app/api/safety.py`, `backend/tests/test_safety_evaluation_time_guard.py` (baru) |
| Patch | `validasi_waktu_evaluasi()`: `None` tetap diizinkan (perilaku terdokumentasi: "nilai pada sampel terakhir" — log historis tidak otomatis stale); waktu tanpa offset → 422; waktu di masa depan (>300 s toleransi jam) → 422 |
| Test | 5 tes unit + `test_api_domain_tools.py` → 22 lulus |
| Risk | **Sisa:** `None` masih berarti "nilai pada sampel terakhir", sehingga pemanggil dapat menilai log 2 hari lalu dan mendapat `pass`. Itu keputusan produk yang terdokumentasi di `core/safety.py`, bukan bug — tetapi risiko demo harus disadari |
| Status | **FIXED** (guard), **ACCEPTED_RISK** (semantik `None`) |

### AUD-014 — Lint & TypeScript merah

| Field | Isi |
|---|---|
| Status awal | OPEN — ruff 12 error, tsc 4 error |
| Root cause | (a) 8 pelanggaran import/urutan; (b) 1 duplikat import (`USABLE`); (c) 4 baris >100 kolom; (d) tsc: `frontend/tsconfig.json` tanpa `target`, sehingga `for (const m of str.matchAll(...))` → `TS2802` |
| File diubah | `backend/app/api/receipts.py`, `backend/app/core/receipt_scoring.py`, `backend/tests/test_receipt_scoring.py`, `backend/tests/test_receipts_approval.py`, `frontend/tsconfig.json` + 8 file yang hanya dirapikan import-nya oleh `ruff --select I001,F401 --fix` |
| Patch | Import dirapikan terarah (bukan formatter massal); baris panjang dibungkus; `"target": "es2017"` ditambahkan |
| Hasil sesudah | `ruff check .` → `All checks passed!` (exit 0); `npm run typecheck` → exit 0; `next lint` → 0 |
| Catatan | `target` **terbukti** penyebab, bukan cache: menghapus `tsconfig.tsbuildinfo` saja tetap gagal; mengembalikan `target` + cache bersih → lolos. Cache `.tsbuildinfo` (gitignored) juga dihapus |
| Status | **VERIFIED** |

### AUD-023 — Schema drift (`alembic check` gagal)

| Field | Isi |
|---|---|
| Status awal | OPEN — `Detected removed index 'ix_batch_receipts_verdict'` |
| Root cause | Indeks dibuat migrasi 052 di DB tetapi tidak dideklarasikan di model, sehingga autogenerate ingin menghapusnya |
| File diubah | `backend/app/models/receipts.py` |
| Patch | `Index("ix_batch_receipts_verdict", "verdict")` dideklarasikan (indeks dipertahankan, bukan dijatuhkan) |
| Hasil sesudah | `alembic check` → `No new upgrade operations detected.` (exit 0) |
| Status | **VERIFIED** |

### AUD-036 — Artefak OpenAPI basi

| Field | Isi |
|---|---|
| Status awal | OPEN — artefak 87 path, aplikasi 90; 3 endpoint hilang (`/demo/agent/stream`, `/receipts/checklist`, `/receipts/riwayat`) |
| File diubah | `backend/openapi.json` (regenerasi dari `app.openapi()`) |
| Hasil sesudah | 90 path; `test_artefak_openapi_tidak_basi` lulus |
| Status | **VERIFIED** |

### AUD-029/030 — Tidak ada error boundary, halaman 404, atau layar gagal global

| Field | Isi |
|---|---|
| Status awal | OPEN — tidak ada `app/error.tsx`, `app/global-error.tsx`, `app/not-found.tsx`. Kegagalan render = layar kosong Next.js |
| File diubah | `frontend/app/error.tsx`, `frontend/app/global-error.tsx`, `frontend/app/not-found.tsx` (baru) |
| Patch | Tiga layar berbahasa Indonesia dengan jalan pulih ("Coba lagi" → `reset()`, "Kembali ke dasbor"), kode kejadian (`error.digest`) ditampilkan, **detail internal tidak** dibocorkan ke pengguna |
| Verifikasi | `tsc --noEmit` exit 0, `next lint` 0, vitest 2728 lulus |
| Risk | Belum diuji dengan backend dimatikan di browser sungguhan (butuh sesi browser + Next dev). Komponen belum tercakup tes otomatis |
| Status | **FIXED** |

### AUD-041 — Byte NUL di sumber frontend

| Field | Isi |
|---|---|
| Status awal | OPEN — `frontend/lib/api.ts` mengandung 1 byte NUL (pemisah kunci cache `${commodity}\x00${token}`) |
| Root cause | Escape ditulis sebagai byte mentah, bukan escape teks → git/grep memperlakukan berkas sebagai biner (diff tidak terlihat) |
| File diubah | `frontend/lib/api.ts` |
| Patch | Byte NUL diganti escape `\u0000` — nilai runtime identik |
| Hasil sesudah | `NUL tersisa: 0`; berkas kembali dapat di-diff (123 baris perubahan pengguna yang sebelumnya tak terlihat kini muncul) |
| Status | **VERIFIED** |

---

## 3. Temuan yang BELUM dikerjakan pada run ini

| AUD | Judul | Status | Alasan / yang dibutuhkan |
|---|---|---|---|
| AUD-001 | Klaim integrasi Joule/A2A pada host tunnel sementara | **BLOCKED** | Butuh keputusan pemilik atas host permanen + kredensial CF. Default rencana (nonaktifkan klaim di demo) belum dieksekusi karena menyentuh konfigurasi layanan eksternal |
| AUD-002/003 | Role runtime masih superuser; trigger ledger bisa dilewati | **OPEN** | Perlu uji transisi role di DB sekali-pakai + penerapan ke DB aktif. Belum dijalankan pada run ini |
| AUD-004 | Rotasi kredensial historis | **BLOCKED** | Rotasi/pencabutan hanya boleh dilakukan pemilik akses (AWS/SAP/JWT/DB). Tidak ada nilai secret yang dicetak |
| AUD-010/011/012/027 | Invarian data demo, `init-demo` tidak transaksional, generasi ledger saat purge | **OPEN** | Menuntut rebuild data demo = menulis ke DB demo. Dilarang pada fase ini |
| AUD-016/021/022 | Rekonsiliasi PO/invoice/SDC | **OPEN** | 4/17 PO `invoice_total ≠ price × qty` masih ada; keputusan arti "harga tagihan vs kutipan" adalah keputusan produk (O-item) |
| AUD-017 | `AGENTCORE_RUNTIME_ARN` dipakai sebagai slot model pertama | **OPEN** | Perubahan routing model tanpa izin panggilan model berbayar tidak dapat diverifikasi |
| AUD-018 | Dependensi rentan (30 advisory backend, 12 frontend) | **OPEN** | Upgrade `starlette`/`pyjwt`/`next`/`maplibre-gl` butuh build ulang container + uji regresi penuh; tidak dilakukan agar tidak mencampur risiko dalam satu run |
| AUD-028 | Polling berlebihan | **OPEN** | Butuh pengukuran 60 detik idle di browser |
| AUD-032…037 | Constraint, sesi demo global, revoke token, urutan otorisasi | **OPEN** | Sebagian butuh migrasi (CHECK constraint) dan keputusan produk |
| AUD-035 | Observability (request ID, structured log, versi/commit) | **OPEN** | Belum dikerjakan |

---

## 4. Perubahan berkas (hanya yang disentuh run ini)

**Backend (produksi)**
- `backend/app/api/auth.py` — kunci ketiga demo-login; klaim `typ`; `require_sesi_manusia`
- `backend/app/api/admin.py` — dependency router `/admin`
- `backend/app/api/safety.py` — `validasi_waktu_evaluasi`
- `backend/app/api/receipts.py` — hapus import duplikat
- `backend/app/core/temperature.py` — interval terakhir dihitung
- `backend/app/core/receipt_scoring.py` — baris panjang
- `backend/app/models/receipts.py` — deklarasi indeks `verdict`
- `backend/app/services/event3_service.py` — kebijakan komoditas
- `backend/app/services/kpi_service.py` — kontrak metrik tunggal + flag
- `agent/verifier_checks.py` — `cek_ledger` sadar status
- `.env.example` — dokumentasi `DEMO_LOGIN_ALLOW_REMOTE`

**Backend (tes)**
- Diubah: `test_demo_accounts_browser.py`, `test_temperature.py`, `test_commodity_policies.py`, `test_receipt_scoring.py`, `test_receipts_approval.py`, `test_admin_api.py`, `test_admin_jejak_audit.py`, `test_kpi_harga_efektif.py`
- Baru: `test_safety_evaluation_time_guard.py`, `test_admin_sesi_manusia.py`
- Hanya import dirapikan `ruff --fix`: `test_agent_progress.py`, `test_po_review_flow.py`, `test_agent_audit_facts_api.py`, `test_demo_sesi_batas_dan_enforcement.py`, `test_legacy_endpoint_rbac.py`, `test_po_document_pdf.py`, `test_po_invoice_commercial.py`, `app/api/agent.py`, `app/main.py`, `app/services/audit_facts.py`, `app/seed/rapikan_jejak.py`

**Frontend**
- Baru: `app/error.tsx`, `app/global-error.tsx`, `app/not-found.tsx`
- Ubah: `tsconfig.json` (+`target`), `lib/api.ts` (NUL → escape)

**Artefak**
- `backend/openapi.json` — regenerasi (87 → 90 path)

---

## 5. Keputusan yang diambil (dan dasarnya)

| # | Keputusan | Dasar |
|---|---|---|
| D1 | Kontrak KPI tetap **7**, metrik ke-8 di balik flag | Default O1 di rencana; dokumen + tes + UI sepakat 7 |
| D2 | `evaluation_time = None` **dipertahankan** | Perilaku terdokumentasi di `core/safety.py`; mengubahnya = keputusan produk baru. Guard masa depan ditambahkan, sisa risiko dicatat |
| D3 | Interval suhu: hanya interval **terakhir** yang diperluas | Percobaan "salah satu ujung" memecah 2 tes kalibrasi (freshness 0,75, safety 29,999 menit) — bukti bahwa aturan lama dikalibrasi sengaja |
| D4 | Status pra-aksi `verifier_flagged` ikut diloloskan `cek_ledger` | Kontrak `test_verifier_angka_bersitasi`; `verifier_flagged` = menunggu review, belum ada aksi |
| D5 | Metrik ke-8: tes fitur menyalakan flag sendiri | Tes fitur menguji angka metrik, bukan jumlah kontrak |
| D6 | Identitas palsu di fixture admin menyatakan `_token_typ="user"` | Harness harus menyerupai sesi manusia; perilaku yang diuji tidak berubah |

---

## 6. Perubahan perilaku yang perlu diketahui pengguna

1. **Login demo** hanya bekerja dari mesin yang menjalankan browser demo (loopback/gateway container). Dari perangkat lain di LAN, daftar akun demo kini kosong. Untuk kios: `DEMO_LOGIN_ALLOW_REMOTE=true`.
2. **`/admin/*` menolak token layanan.** `MEALCHAIN_API_TOKEN` yang dipakai agen harus diterbitkan ulang oleh pemilik akses; sampai itu terjadi, agen tidak bisa mengubah pengguna (memang tujuannya) dan **juga** tidak bisa memakai endpoint admin lain.
3. **KPI kembali 7 metrik**; "Effective Price per Accepted Kg" tidak tampil sampai `KPI_EFFECTIVE_PRICE_ENABLED=true`.
4. **Keputusan `approved` tanpa blok ledger** kini bisa ditandai `verifier_flagged` (tidak memblokir approval).
5. **Batch beras/ambient** tidak lagi dinilai dengan rentang rantai dingin 0–8 °C.

---

## 7. Hasil pengujian

### 7.1 Perintah dan lingkungan

```bash
# DB uji sekali-pakai (DB demo TIDAK disentuh)
createdb mealchain_fix && DATABASE_URL=...mealchain_fix alembic upgrade head
DATABASE_URL=...mealchain_fix python -m app.seed.seed_data --reference-time <now> \
  --with-demo-users --with-demo-suppliers --skip-routes

# gate
ruff check .            # backend
alembic check           # backend
npm run typecheck       # frontend
npx next lint           # frontend
npx vitest run --pool=forks --poolOptions.forks.singleFork=true
python -m pytest -q     # suite penuh, DATABASE_URL -> mealchain_fix
```

### 7.2 Angka

| Run | DB | Hasil | Durasi |
|---|---|---|---|
| Baseline audit | klon DB demo (`mealchain_audit`) | 30 gagal / 2256 lulus / 36 skip / **3 error** | 903,85 s |
| Mid-run (A2,B1,B3,B6,B8,C1,C3) | `mealchain_fix` | 15 gagal / 2285 lulus / 36 skip / **0 error** | 887,16 s |
| **Final (semua patch run ini)** | `mealchain_fix` | **5 gagal / 2300 lulus / 33 skip / 0 error** | **831,00 s** |

**Peringatan komparabilitas:** baseline memakai **klon DB demo**, run berikutnya memakai **DB uji yang baru
di-seed**. Jumlah total karena itu tidak setara satu-satu; perbandingan yang sah adalah per-tes pada temuan
yang sama (§2).

### 7.3 Kegagalan yang tersisa setelah run final

`5 failed, 2300 passed, 33 skipped, 2 warnings in 831.00s`

| Tes | Penyebab | Terkait |
|---|---|---|
| `test_demo_cases_procurement_binding::test_kasus_pengadaan_lolos_resolve_binding_dan_safety` | Butuh data kasus demo hasil `demo_template`; DB uji memakai `seed_data` | AUD-010 (data demo, OPEN) |
| `test_demo_template_provenance_ledger::test_hapus_kasus_demo_menaikkan_generasi_ledger` | Generasi ledger saat purge belum diseragamkan | AUD-012/027 (OPEN) |
| `test_po_invoice_commercial::test_daftar_po_menyebut_invoice_unit_price_secara_eksplisit` | Butuh `sap_mock_po` yang tidak dibuat `seed_data` | AUD-016 (OPEN) |
| `test_supplier_procurement_eval::test_pemasok_terpilih_punya_batch_di_sppg_itu` | Butuh seed `jakarta_lengkap` (pemasok telur + stok) | data uji, sudah gagal di baseline |
| `test_supplier_procurement_eval::test_peringkat_deterministik_dan_layak` | Idem | idem |

Tidak satu pun berasal dari patch run ini: tiga pertama adalah temuan yang memang masih OPEN, dua
terakhir sudah gagal pada baseline dan bergantung pada seed `jakarta_lengkap` yang tidak dijalankan pada
DB uji. **Tidak ada tes yang dihapus, di-skip, atau diubah expected value-nya untuk menutup kegagalan.**

Catatan flakiness: `test_api_decision_intelligence` (2 tes) dan `test_demo_timeseries_api` (1 tes) gagal
pada run antara tetapi lulus pada re-run terarah maupun run final — bergantung urutan/isi DB, bukan
regresi kode. Perlu diisolasi pada fase C2.

### 7.4 Bukti A4 (least privilege) — mekanisme bekerja, runtime belum memakainya

```
pytest tests/test_least_privilege_app_role.py tests/test_ledger_immutability.py
→ 17 passed in 5.94s
```

Tes itu membuat akun login yang mewarisi `mealchain_app`, lalu membuktikan: bisa baca tabel dan menulis
tabel kerja, **tidak** bisa `UPDATE`/`DELETE`/`TRUNCATE` `ledger_blocks`, dan **tidak** bisa DDL —
dijalankan di transaksi yang di-rollback. Artinya jalur least-privilege (migrasi 043 + `scripts/siapkan_role_app.py`)
sudah benar dan teruji.

Yang belum: `APP_DATABASE_URL` masih kosong, sehingga backend berjalan sebagai role `mealchain`
(superuser). Memindahkannya berarti mengubah koneksi DB demo secara langsung — dilarang oleh §2 prompt —
jadi langkah itu diserahkan sebagai aksi terpisah dengan persetujuan pemilik.

---

## 8. Status per fase rencana

| Fase | Langkah | Status |
|---|---|---|
| A — Containment | A2 (AUD-005) | ✅ VERIFIED |
| | A1 (AUD-001), A3 (AUD-004) | ⛔ BLOCKED — butuh pemilik akses/konfigurasi eksternal |
| | A4 (AUD-002/003), A5 (AUD-010/011) | ⬜ OPEN — menuntut DB sekali-pakai + rebuild data demo (di luar batas run ini) |
| B — Keselamatan & angka | B1, B2, B3, B6, B8, B10 | ✅ (B3 = FIXED, B2 = FIXED + ACCEPTED_RISK) |
| | B4, B5, B7, B9, B11 | ⬜ OPEN |
| C — Kualitas | C1, C3, C7(artefak OpenAPI), C8(NUL) | ✅ VERIFIED |
| | C2 (suite hijau penuh), C4, C5(uji browser), C6 | ⬜ sebagian / OPEN |
| D — Sisa | — | ⬜ OPEN |

---

## 9. Tambahan di luar daftar AUD: integrasi SAP-RPT-1.6 ke `/demand/forecast`

Diminta terpisah setelah audit. Temuan sebenarnya: klien RPT sudah lengkap
(`backend/app/ai_providers/sap_ai_core_caller.py`), tetapi endpoint peramalan memanggil
`statistical_forecast` langsung — jadi RPT tidak pernah dipakai meski kredensial terisi.
Dokumen `sap-joule/docs/rpt-forecast-notes.md` masih berjudul "belum diintegrasikan".

| Field | Isi |
|---|---|
| Status awal | Klien ada, **tidak tersambung** ke jalur saji |
| File diubah | `backend/app/api/demand.py`, `backend/tests/test_demand_forecast_rpt.py` (baru), `sap-joule/docs/rpt-forecast-notes.md`, `.env.example`, `backend/openapi.json` (regenerasi) |
| Patch | `susun_forecast()`: RPT bila klien terkonfigurasi → fallback statistik; respons menambah `source` + `fallback_used`; `confidence` menjadi nullable (tidak diisi 0.0 saat tak diketahui); saklar `FORECAST_PROVIDER=statistical` |
| Test | 5 kasus unit (RPT berhasil / balasan sampah / tanpa angka / pemanggil melempar / tanpa pemanggil) + suite peramalan lama |
| Hasil | 43 lulus. `ruff check .` tetap `All checks passed` |
| Bukti live | `GET /demand/forecast/Bandung/ayam?horizon_days=7` → `200 {"method":"sap_rpt_1_6","source":"SAP-RPT-1.6","confidence":0.99559,"fallback_used":false,"forecast_qty_kg":2166.92}` |
| Bukti saklar | `FORECAST_PROVIDER=statistical` → `{"method":"statistical_fallback","source":"statistical_fallback","fallback_used":true}` |
| Risk | Setiap GET memanggil AI Core (biaya + latensi) — **sudah ditutup** di tahap berikutnya |
| Status | **VERIFIED**, lalu **DIPERLUAS** (lihat baris berikut) |

**Tindak lanjut 29 Okt (setelah rencana integrasi penuh):** integrasi diperluas
menjadi satu pintu `backend/app/services/forecast_service.py` yang dipakai tiga jalur
(endpoint, `event1_orchestrator`, `demo_procurement_orchestrator`) dengan cache 15
menit, batas 20 panggilan/menit, circuit breaker, jendela riwayat 28 hari tanpa baris
masa depan, ambang minimum 7 titik, dan label sumber di kartu UI. Biaya yang tadinya
"risk" kini dibatasi dan terukur; rincian + bukti HTTP ada di
`docs/plans/sap-rpt-integration-plan.md` §9.

## 10. Definition of Done — posisi jujur

| Kriteria | Status |
|---|---|
| 1. Semua AUD-001…050 `VERIFIED`/`ACCEPTED_RISK` | ❌ 13 temuan disentuh; sisanya OPEN/BLOCKED |
| 2. Tidak ada temuan ditutup tanpa bukti | ✅ setiap baris §2 punya perintah + output |
| 3. Gate backend & frontend lulus | ✅ ruff 0, tsc 0, lint 0, alembic bersih, vitest 2728 |
| 4. DB uji bersih dapat dimigrasikan | ✅ `mealchain_fix` dibuat dari nol setiap run |
| 5. Role runtime bukan superuser | ⚠️ mekanisme TERBUKTI (`test_least_privilege_app_role.py`, 17 lulus); runtime **masih** superuser karena `APP_DATABASE_URL` kosong — peralihan butuh persetujuan (menyentuh DB demo) |
| 6. Maintenance ledger ditolak role runtime | ⚠️ idem — ditolak untuk akun `mealchain_app` di tes, belum untuk proses yang berjalan |
| 7. Safety gate/temperature regression lulus | ✅ 75 tes |
| 8. Data demo memenuhi invarian | ❌ belum (A5) |
| 9. KPI cocok perhitungan independen | ✅ untuk kontrak 7 + metrik ke-8 |
| 10. Klaim integrasi dibedakan mock/live | ⚠️ sebagian (artefak & UI, bukan koneksi live) |
| 11. Secret historis tidak aktif | ⛔ BLOCKED — butuh rotasi oleh pemilik |
| 12. Tidak ada drift OpenAPI/docs | ✅ OpenAPI; dokumentasi lain belum diaudit ulang |
| 13. Sebelum/sesudah tercatat | ✅ §7 |
| 14. Working tree pengguna utuh | ✅ tanpa reset/checkout destruktif; 146 → 168 entri (22 tambahan = 8 tes/berkas baru + hasil `ruff --fix`) |

**Kesimpulan:** remediasi **belum selesai**. Yang selesai adalah lapisan keselamatan-deterministik,
kontrak angka, dan gate kualitas. Yang masih terbuka justru dua risiko terbesar audit: **privilege DB**
(A4) dan **integrasi/rahasia** (A1/A3), keduanya menuntut keputusan atau akses pemilik.
