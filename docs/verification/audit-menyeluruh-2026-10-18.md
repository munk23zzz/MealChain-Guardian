# Audit Menyeluruh MealChain Guardian — 18 Oktober 2026

**Waktu audit:** 18 Okt 2026, 17:10–17:35 WIB
**Commit saat audit:** `c2e1ae1` (branch `feature/sprint2-decision-intelligence`)
**Metode:** tiga audit paralel read-only (siklus hidup keputusan & matriks izin backend; wiring UI↔API; integritas data & KPI), lalu temuan terberat diverifikasi ulang langsung lewat kode dan SQL oleh auditor utama. Tidak ada data yang diubah, tidak ada endpoint mutasi yang dipanggil.
**Catatan:** DB dipakai bersama sesi lain dan bergerak selama audit (keputusan 15→16→17, `ledger_blocks` 7685→7757, `menu_plans` 660→70→660). Semua angka dikunci pada waktu ukurnya.

---

## Ringkasan

Aplikasi tidak "rusak", tetapi ada lima hal yang membuat alur inti berhenti di tengah atau memberi kesan palsu — dan semuanya berada persis di jalur yang akan dicoba juri:

1. Event 1/2/3 selalu melahirkan keputusan `proposed` yang tidak punya tombol untuk diajukan.
2. "Setuju" sebelum "Verifikasi" mematikan keputusan secara permanen (dua 409 tanpa jalan pulih).
3. Status `approved` tidak pernah ditulis kode, sehingga kuorum penuh tak bisa dibedakan auditor.
4. Ledger 7.757 blok 100% yatim, tetapi `/ledger/verify` menyatakan `valid: true`.
5. 4 dari 6 approval disetujui lintas lokasi untuk keputusan yang sudah `executed`.

---

## A. BLOCKER

### A1. Event 1/2/3 berakhir di jalan buntu
- Ketiga pipeline menulis `status="proposed"`: `backend/app/services/event1_orchestrator.py:208`, `event2_service.py:221`, `event3_service.py:231`.
- Satu-satunya jalan ke `pending_approval` adalah `POST /actions/propose` (`backend/app/api/actions.py:141-160`, Head-only), dan tombolnya hanya dipakai `frontend/components/OpsConsole.tsx:167` untuk keputusan yang BARU dibuat lewat `/balance/analyze`.
- `visibleActions` tidak menawarkan aksi untuk status `proposed` (`frontend/components/DecisionActions.tsx:41-50`), sehingga popup hanya berisi "Tutup" + "Tidak ada tindakan mendesak".
- Bukti DB: 8 keputusan `proposed`, seluruhnya Jakarta, tidak satu pun bisa disetujui.
- Dampak demo: "Jalankan Event 1 penuh" / "Picu Event 3" / "Jalankan Event 2" menghasilkan keputusan mati; demo hanya tampak berjalan karena "Muat kasus demo" menanam kasus `pending_approval`.
- Saran: tombol "Ajukan untuk persetujuan" (`POST /actions/propose`) untuk Head saat `status=proposed` dan `expiry.valid`; jadikan itu isi `nextStep`.

### A2. Approve sebelum verify = mati permanen
- `approve` tidak memeriksa `verified_by` (`backend/app/api/actions.py:292-330`).
- `execute` menolaknya dengan 409 "decision belum terverifikasi" (`actions.py:407-408`).
- `verify` menolak 409 begitu sudah ada satu approval (`actions.py:234-243`), dan tidak ada endpoint pembatalan.
- Urutan paling alami bagi operator baru ("Setuju" → "Eksekusi") mematikan keduanya; pemulihan hanya lewat SQL manual.
- Saran: tolak approve bila `verified_by IS NULL` (409 `belum_terverifikasi`).

### A3. Status `approved` tidak pernah diproduksi, `needs_verification` mustahil ada
- CHECK constraint: `proposed | verifier_flagged | pending_approval | approved | rejected | executed`.
- `grep "status *= *['\"]approved"` → 0 hasil; `approve` hanya menulis `rejected` (`actions.py:340-345`) dan tidak menyentuh status saat approve (`actions.py:332-359`).
- Sebaran status di DB: proposed 8, pending_approval 3, executed 3, rejected 3, verifier_flagged 1. Tidak ada `approved`, tidak ada `expired`.
- Konsekuensi: (a) tidak ada keadaan "disetujui, menunggu eksekusi" yang bisa dilaporkan; (b) blok ledger approval menyimpan `"status": "pending_approval"` (`actions.py:356`) sehingga approval ke-1 dan ke-2 (kuorum penuh) tak bisa dibedakan; (c) cabang UI `approved` mati, dan `needs_verification` yang dipakai `frontend/lib/topbar.ts:32-36` dilarang CHECK DB.
- Saran: tulis `approved` saat `evaluate_approvals(...).satisfied` pertama kali benar dan sertakan di payload ledger; selaraskan kosakata UI dengan CHECK.

### A4. Ledger 100% yatim, klaim "valid" menyesatkan
- SQL: `ledger_blocks` 7.757 baris, `7.757` di antaranya menunjuk `decisions.id` yang sudah tidak ada.
- `GET /ledger/verify` → `{"valid": true, "blocks": 7757}`; yang diperiksa hanya kontinuitas hash (`backend/app/services/ledger_service.py:78-98`), bukan keberadaan subjek.
- Tidak ada blok untuk `create`, `propose`, `verify`, `repropose`, `/events/*`, usul/`restore` exclusion, `/receipts` (`grep append_block` → hanya `actions.py:347,455,553` + `quarantine_service.py:89`).
- Docstring `ledger_service.py:3-6` ("setiap aksi mutasi keputusan menambah block") tidak benar.
- Saran: tambahkan blok `create`/`propose`/`verify` (+ verdict) dan kembalikan `orphan_blocks` di `/ledger/verify`; jangan tampilkan "valid" tanpa cakupan provenance.

### A5. Approval lintas lokasi untuk keputusan `executed`
- SQL: 6 approval total, 4 di antaranya oleh user ber-lokasi Jakarta untuk keputusan target Bandung/Surabaya; ketiganya `executed`.
- Endpoint menolak kombinasi ini (`_require_decision_scope`, `actions.py:306`), jadi baris tersebut lahir dari seed (`backend/app/seed/demo_activity.py:161-215`), bukan dari alur API.
- Akar tambahan: hanya ada 1 akun `sppg_head` dan 1 `sppg_nutritionist`, keduanya Jakarta — keputusan menyasar kota lain tidak akan pernah bisa di-approve siapa pun.
- Saran: seed approval memakai akun lokasi target; tambahkan akun head & nutritionist untuk Bandung/Surabaya.

---

## B. MAYOR

### Verifikasi & kepercayaan
- **Verify bisa diulang sampai verdict "menyenangkan"** (`actions.py:234-246`): tak ada batas percobaan, verdict lama ditimpa (`:274-275`), tanpa `append_block` dan tanpa `AgentTrace('VERIFY')`. FLAGGED → CONSISTENT menurunkan syarat administrasi dari 2 approval ke 1 (`core/approval_matrix.py:30-35`).
- **`verified_by` diisi walau verdict `UNAVAILABLE`** (`actions.py:272-278`, `verifier_client.py:146`); gerbang eksekusi hanya memeriksa kolom itu (`actions.py:97-98,407`).

### Eksekusi
- **`can_execute` ≠ hasil execute**: read model (`services/approval_summary.py:281-302`) tidak memeriksa kuantitas/harga (`actions.py:496-502` menolak 422) maupun eksklusi pemasok (`supplier_eligibility.py:198-212`).
- **`price_anomaly` dari Event 2 tanpa `quantity_kg`** (`event2_service.py:219-240`) → tidak pernah bisa dieksekusi dan tidak punya status terminal "review-only/closed".

### Izin & cakupan
- **`POST /actions/repropose` tanpa guard lokasi** (`actions.py:586-628`); hanya `ADMIN_TYPES` yang memakai `require_scope`. Anak menyalin `target_location_id` parent (`:614-628`).
- **Alat demo melanggar tenant**: `force=true` menghapus kasus demo semua lokasi (`demo.py:179-184`), lalu seed menanam kasus yang menyasar Jakarta (`demo.py:203,257,279,315`) tanpa memakai lokasi pemanggil.

### Angka yang menyesatkan
- **"Lewat tenggat — tidak bisa ditindak lagi"** tidak akurat: approve keputusan biasa yang lewat tenggat masih diterima (`actions.py:307-315`, sengaja hanya menjaga tipe administrasi), tetapi keputusan itu disembunyikan dari hitungan dan pemilih default (`frontend/lib/topbar.ts:144-156`, `decision-picker.ts:126-130`).
- **"Menunggu tindakan (4)"** tidak menghitung 8 `proposed` yang menuntut tindakan Head (`frontend/lib/topbar.ts:32-36` dipakai lonceng, chip sidebar, kartu Overview).
- **"Hari Ini" mencampur cakupan**: tile batch memakai `GET /batches` seluruh jaringan (`backend/app/api/batches.py:21-26`, `frontend/lib/today.ts:138-152`), tile keputusan memakai lokasi sendiri. Di layar Jakarta: "2 batch kedaluwarsa (450 kg)" berisi Palembang 250 kg + Semarang 200 kg, sementara tab Keamanan Pangan Jakarta menulis "0 / kedaluwarsa".
- **KPI Decision Time 20 menit** dihitung dari DETECT yang terjadi 10 mnt 51 dtk SEBELUM `decisions.created_at`; semua bukti juga bertanggal sebelum keputusan lahir (`decision_evidence` 09:22–09:25 vs created 09:26:57).
- **Evidence Completeness 100,00%** dari n=1 keputusan (coverage 0,07); semua `decision_evidence.is_consistent=true` (0 false) sehingga metrik tak bisa turun.
- **Jendela "30 hari" = 31 hari dan membuang hari ini**: `CAST(:start AS date)` pada sesi UTC menggeser tanggal `+07:00` satu hari ke belakang; `plan_date < CAST(:end AS date)` mengecualikan hari berjalan.
- **53% "pengiriman" bertanggal masa depan**: `delivery_events` 190/360 (`max 2026-11-05`), `disposal_events` 38/78, `supply_records` 1050/3900, `price_signals` 1092/4054.
- **Transfer sumber = tujuan**: 3 keputusan `executed` (Jakarta→Jakarta, Bandung→Bandung, Surabaya→Surabaya) tetap dihitung "menyelesaikan ketidakseimbangan" (Imbalance Resolution Rate 20%).

### Data demo
- **3 keputusan `rejected` lahir sudah kedaluwarsa** (`created_at` 45/30/60 menit setelah `expires_at`) dan tanpa baris approval — tidak ada aktor penolak.
- **4 keputusan "menunggu tindakan" tanpa approval dan tanpa bukti**; satu di antaranya berlabel "verifier menyatakan konsisten" tanpa satu pun `decision_evidence`. 11 dari 16 keputusan tanpa bukti.
- **Batches menutup 7 dari 30 pasangan lokasi×komoditas**; Jakarta punya 3 batch (semua telur, 0 ayam) padahal ada PO 600 kg ayam; `batches` vs `sap_mock_material_stock` tidak sinkron.
- **`supplier_exclusions` = 0 baris** → fitur eksklusi/pemulihan pemasok tidak punya kasus untuk didemokan.

---

## C. MINOR

- Form "Ajukan exclusion" tampil untuk Ahli Gizi (`SupplierExclusionPanel.tsx:76-77,121-128`) karena server mengirim `can_propose=true` (`supplier_exclusion_context.py:87-90`), sementara endpoint `require_roles("sppg_head")` (`supplier_exclusions.py:36`) → pasti 403.
- Semua kegagalan tampil sebagai `HTTP 409: /actions/approve`: `ApiError` membuang body `detail` (`frontend/lib/api.ts:13-21`).
- Empty state menyuruh "jalankan analisis di tab Analisis" — tab itu tidak ada (`frontend/app/page.tsx:1403-1410`).
- Copy "approve/reject di feed" padahal kartu feed hanya membuka tab (`OpsConsole.tsx:255-259`, `RoleHero.tsx:19`).
- "Kelola persetujuan" tetap tampil saat tak ada pilihan (executed; rejected bagi Ahli Gizi) → popup kosong (`DecisionActions.tsx:76-78,150-162`).
- Pengaturan menawarkan ubah peran akun sendiri, backend menolak 422 (`SettingsPanel.tsx:241-252` vs `admin.py:104-106`).
- Usul exclusion identik dua kali → 201, bukan 409 (`supplier_exclusion_service.py:111-115`); baris `proposed` bisa menggantung selamanya; penolakan restoration tidak meninggalkan jejak.
- Dokumen menyebut restore cukup 1 approval bila consistent; kenyataannya selalu 2 (`verifier_note` NULL → `unavailable`, `approval_matrix.py:36-40`) dan tak ada langkah yang menjalankan verifier.
- `ProposeRequest` menerima `supplier_id`/`material_number` yang tidak mengikat apa pun (`actions.py:38-41`; `_resolve_supplier_id` `:661-672` tak pernah dipanggil).

---

## D. ALUR YANG BELUM ADA SAMA SEKALI

1. **Batal/tarik keputusan (withdraw/cancel)** — tidak ada endpoint; satu-satunya cara membersihkan adalah `/demo/seed force` yang lintas lokasi. `repropose` hanya untuk `rejected`.
2. **Sweeper kedaluwarsa** — status tidak pernah berpindah ke terminal saat `expires_at` lewat; UI menambal dengan flag `valid`.
3. **Eskalasi approver kedua** ("menunggu Ahli Gizi di SPPG X") — tanpa akun gizi di lokasi target, keputusan berhenti dengan 409 generik.
4. **Status terminal untuk `price_anomaly`** (review-only/closed) dan untuk `needs_verification` yang hanya hidup di UI.
5. **Provenance ledger** — jumlah blok yatim, riwayat verdict verifier, blok `create`.
6. **Riwayat notifikasi** — lonceng tanpa arsip/"sudah dibaca".
7. **UI**: tombol "Ajukan untuk persetujuan" untuk `proposed`; laporan kepatuhan bertanda tangan (`fetchComplianceDossier` ada tapi tak pernah dipanggil); filter PO per keputusan (backend mendukung `decision_id`, UI memuat 200 PO).
8. **Satu sumber kebenaran stok** — `batches` (safety) vs `sap_mock_material_stock` (procurement).

---

## E. SARAN URUTAN PERBAIKAN

**Sebelum demo (≤2 jam)**
1. Tombol "Ajukan untuk persetujuan" untuk Head saat `proposed` + isi `nextStep` (menutup A1).
2. Tolak approve bila `verified_by` NULL (menutup A2 tanpa melonggarkan aturan).
3. Seed approval memakai akun lokasi target + tambah akun head/gizi Bandung & Surabaya (menutup A5).
4. `/demo/seed` memakai lokasi pemanggil; `force` hanya menghapus kasus demo lokasi itu.

**Setengah hari berikutnya**
5. Tulis `approved` saat kuorum penuh + payload ledger; selaraskan kosakata UI/DB (A3).
6. `/ledger/verify` mengembalikan `orphan_blocks` (A4).
7. Satu fungsi kelayakan eksekusi dipakai `execute` dan `approval_summary` (kuantitas, harga, eksklusi).
8. Masukkan `proposed` ke hitungan "perlu tindakan" (atau chip terpisah).
9. `ApiError` membawa `detail`; perbaiki wording "lewat tenggat".

**Sebelum juri (1 hari)**
10. KPI: `CAST` ke zona tampilan, sertakan hari ini, tolak sampel < 3, trace relatif ke `created_at`, pisahkan fakta vs forecast.
11. Seed koheren: `rejected` punya aktor & waktu; `pending` punya bukti; tolak `source = target` untuk `regional_balance`.
12. Sweep kedaluwarsa + endpoint withdraw/cancel.

---

## F. Batas verifikasi

- BLOCKER A1–A5 serta angka-angka utama diverifikasi ulang langsung oleh auditor utama lewat kode dan SQL (`SELECT` + `GET`).
- Masih **kode-saja** (belum diuji HTTP karena datanya kosong): alur supplier exclusion/restoration (`supplier_exclusions` 0 baris) dan 422 kuantitas untuk `price_anomaly` hasil Event 2.
- Angka DB dapat bergeser karena sesi lain aktif menulis selama audit.
