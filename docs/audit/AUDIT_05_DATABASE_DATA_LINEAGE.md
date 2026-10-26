# AUDIT_05 — Database & Data Lineage

Database: PostgreSQL 16.15, database `mealchain` (container `mealchain-postgres`, port host 15432).
Waktu pengambilan angka: 26 Oktober 2026, 07:21 WIB — data demo dapat berubah bila ada sesi lain berjalan.

## 5.1 Struktur

- 24 tabel, 33 revisi migrasi, head `033_indeks_fk_hilang`.
- Kunci utama UUID (`gen_random_uuid()`), FK eksplisit, CHECK constraint untuk status & rentang.
- Constraint penting:
  - `decisions_status_check` (7 status), `decisions_decision_type_check` (6 tipe)
  - `sap_mock_po_status_check` (`draft|submitted|confirmed`)
  - `batches_safety_status_check`, `batches_certification_check`
  - `uq_approvals_decision_approver` (satu approval per keputusan per akun) & syarat empat mata
  - `uq_demo_sessions_satu_aktif` (partial unique, `status='active'`)
  - `uq_batch_receipts_satu_disetujui` (partial unique)
  - `check_supply_records_origin_vocab` / `check_demand_records_origin_vocab` (`seed|demo`)

## 5.2 Isi data kerja (terukur)

| Tabel | Baris | Catatan |
|---|---|---|
| decisions | 36 | 19 terbuka (Jakarta 11), 5 executed (riwayat), sisanya status lain |
| approvals | 12 | 0 duplikat akun per keputusan |
| sap_mock_purchase_orders | 16 | 0 keputusan dengan >1 PO |
| batches | 120 | 97 punya `dispatched_at` |
| batch_receipts | 2 | |
| demo_sessions | 1 | status `active`, tepat satu |
| agent_traces | 85 | 0 yatim, 0 `step_at` kosong |
| ledger_blocks | 805 | rantai valid (`/ledger/verify` 200) |
| users | 7 | 7 akun demo, 0 duplikat |
| menu_plans | 660 | 1 Sep – 5 Nov 2026 |
| delivery_events | 180 | 8 – 25 Okt 2026 |

## 5.3 Invarian yang diuji (gate `invariants.spec.json`, 19 pemeriksaan DB — semua PASS)

| Invarian | Hasil |
|---|---|
| batch kuantitas negatif | 0 |
| batch diberangkatkan sebelum dipanen | 0 |
| baris kanonik batch/keputusan/pasokan berstempel sesi demo | 0, 0, 0 |
| langkah LEARN pada status di luar `rejected/proposed` | 0 |
| langkah ACT pada keputusan yang tidak `executed` | 0 |
| jejak agent yatim | 0 |
| keputusan tanpa jejak langkah | 0 |
| lebih dari satu PO per keputusan | 0 |
| jejak dengan `step_at` kosong | 0 |
| persetujuan yatim | 0 |
| keputusan `executed` tanpa persetujuan | 0 |
| fakta pasokan/permintaan melewati horizon 31 hari | 0 / 0 |
| migrasi head | `033_indeks_fk_hilang` |

Pemeriksaan tambahan audit ini (SQL langsung, 07:21): `orphan_decisions = 0`, `orphan_approvals = 0`, `approval_ganda_akun = 0`, `sesi_aktif_ganda = 0`.

## 5.4 Data lineage (contoh yang ditelusuri penuh)

**Alur approve → execute → KPI**

1. UI `DecisionActions` → `POST /actions/approve` (kepala) → baris `approvals` (1).
2. `POST /actions/approve` (nutrisi) → `approvals` (2) → `decisions.status='approved'`.
3. `POST /actions/execute` → `decisions.status='executed'`, baris `sap_mock_purchase_orders` (1), `batches.dispatched_at`, `agent_traces` ACT.
4. `GET /kpi?periode=today` membaca `decisions` + `sap_mock_purchase_orders` + `agent_traces` + `decision_evidence` → angka berubah (Safe Delivered Cost, Price Deviation, Decision Time, Evidence Completeness).
5. UI KPI menampilkan angka baru; tidak ada cache klien yang menahan nilai lama (`useKpi` + React Query invalidate).

**Alur kiriman → animasi**

`batches.dispatched_at` → `GET /supplier-routes` (`journey.state/progress`) → `OverviewMap` menggambar posisi. `GET /balance/map` **tidak** terlibat dalam journey.

## 5.5 Migrasi

| Uji | Hasil |
|---|---|
| `alembic current` di DB kerja | `033_indeks_fk_hilang (head)` |
| `alembic check` di DB kerja (sebelum perbaikan) | **GAGAL**: 22 `remove_index` (indeks FK tidak ada di model) |
| `alembic check` sesudah perbaikan | **"No new upgrade operations detected"** |
| Migrasi dari database kosong (`mealchain_migrasiuci`) | lihat AUDIT_10 (dijalankan terpisah) |
| Migrasi berulang pada DB yang sudah head | tidak menghasilkan perubahan (alembic idempoten) |

## 5.6 Reset demo & isolasi data

- Penghapusan dibatasi `origin='demo'`; master data (`locations`, `commodities`, `suppliers`, `users`) tidak berstempel dan tidak disentuh.
- Ledger memakai `bump_generation` (`ledger_meta`) sehingga reset membuka generasi baru, bukan menghapus riwayat.
- Invarian "baris kanonik berstempel sesi = 0" memastikan sweep tidak menyentuh baris kanonik.
- Reset berulang diuji oleh `test_demo_template_deret.py` dan rebuild nyata tiga kali pada sesi ini (36 keputusan, 660 menu, 5.240 pasokan tetap konsisten; tidak ada duplikasi).

## 5.7 Temuan database

| ID | Temuan | Prioritas | Status |
|---|---|---|---|
| BUG-001 | Drift metadata vs DB: 22 indeks FK dibuat migrasi 033 tetapi tidak ada di model; `alembic check` gagal dan autogenerate berikutnya akan **menghapus** indeks itu | P2 | **DIPERBAIKI** |
| AUD-DB-01 | Dokumen lama (termasuk laporan sesi ini sebelum koreksi) menulis tabel `ledger`; nama aktual `ledger_blocks` + `ledger_meta` | P3 | Terdokumentasi (dikoreksi di AUDIT_01/05) |
| AUD-DB-02 | `price_signals` 5.924 dan `supply_records` 5.240 adalah deret sintetis; angka KPI 7d/1bulan bergantung pada deret ini, bukan pada data MBG asli | P2 | Terbuka — harus dinyatakan sebagai data demo di panggung |
