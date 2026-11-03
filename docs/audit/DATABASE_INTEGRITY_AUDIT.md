# AUDIT INTEGRITAS DATABASE — MealChain Guardian

| Field | Nilai |
|---|---|
| Tanggal audit | 26 Oktober 2026 (WIB) |
| Lingkup | Skema, integritas referensial, integritas domain, migrasi, dan kecukupan invarian pada database demo `mealchain` |
| Database diperiksa | `mealchain` (PostgreSQL, container `mealchain-postgres`, port host 15432) |
| Backend | `mealchain-backend` (`:8000`), health `healthy` |
| Snapshot data | **2026-10-26 14:42:20Z** (21:42 WIB), satu transaksi `REPEATABLE READ` |
| Mode kerja | **Baca saja** terhadap DB demo. Satu-satunya DB baru (`audit_schema`) dibuat khusus uji migrasi lalu dihapus |
| Perkakas | `pg_catalog`/`information_schema` via `psql`, `alembic current` / `check` / `upgrade head`, `verify_stack.py`, hitung ulang hash chain dengan Python (`hashlib`), pembacaan kode sumber |
| Artefak bukti | `verify/audit-db/` (lihat §10) |

> **Kepatuhan aturan keras.** Tidak ada `INSERT`/`UPDATE`/`DELETE`/`DROP`/`TRUNCATE` terhadap database demo `mealchain`; tidak ada container di-restart; `.env` tidak diubah; tidak ada paket dipasang. Semua pemeriksaan data adalah `SELECT`. Uji migrasi dijalankan pada database baru `audit_schema` yang dibuat dari nol dan dihapus setelah pemeriksaan. Dokumen ini tidak memuat kredensial.

---

## 0. Ringkasan

**Verdict: skema sehat dan konsisten dengan model; integritas data punya 2 pelanggaran nyata yang belum ditutup invarian yang ada.**

| Aspek | Hasil |
|---|---|
| Tabel domain | 23 (+ `alembic_version`) = 24 tabel |
| Kolom | 240 kolom domain (241 termasuk `alembic_version`) |
| Constraint | 23 PK, **52 FK**, 9 UNIQUE, **42 CHECK** — semuanya `convalidated = true` |
| Indeks | 112, termasuk 8 indeks unik parsial; **0 kolom FK tanpa indeks pendukung** |
| Drift model ↔ DB | **0** (`alembic check` bersih pada DB demo *dan* pada DB baru hasil `upgrade head`) |
| Migrasi | head aktual **`033_indeks_fk_hilang`** = yang didokumentasikan; 33 revisi; `upgrade head` dari kosong sukses |
| Pemeriksaan integritas mandiri | **134 cek: 132 PASS, 2 FAIL** |
| `verify_stack.py` (`verify/invariants.spec.json`) | **PASS 52 / FAIL 0 / SKIP 1** (SKIP = lapisan browser, spec tanpa bagian `ui`) |
| Hash chain ledger | 1.742 blok, 30 generasi, **0 pelanggaran hash**, **0 pelanggaran linkage** |
| Blok ledger yatim generasi aktif | **12 blok** (4 keputusan yang sudah dihapus) — **temuan** |
| SDC ≠ Σ komponen `cost_breakdown` | **4 keputusan** (selisih Rp 4.724.709,71 dan Rp 6.624.258,72) — **temuan** |

Temuan ringkas (rincian §8): **D-01** SDC tidak sama dengan jumlah komponen biaya; **D-02** 12 blok ledger menunjuk entitas yang sudah dihapus; **D-03** sifat *append-only* ledger tidak ditegakkan database; **D-04** provenance data demo dihapus oleh proses `_bekukan`; **D-05** seluruh PO seed tidak punya `decision_id` sehingga rantai keputusan→PO tidak terbukti; **D-06–D-11** temuan kecil/informasional.

---

## 1. Ruang lingkup, aturan, dan metode

**Yang diperiksa.** (a) inventaris tabel + PK/FK/UNIQUE/CHECK/index dari katalog; (b) drift model SQLAlchemy vs skema aktual; (c) orphan, duplikat, dan nilai status di luar kosakata; (d) head migrasi aktual vs dokumentasi; (e) eksekusi `verify/invariants.spec.json`; (f) penilaian kecukupan invarian terhadap aturan domain penting.

**Cara.** Semua inventaris diambil dari katalog sistem (`pg_constraint`, `pg_indexes`, `pg_class`, `information_schema.columns`), bukan dari model maupun dokumen — supaya drift tidak bisa menyembunyikan diri. Pemeriksaan integritas dijalankan oleh skrip `verify/audit-db/run_checks.py`: 134 cek, masing-masing satu query, angka harapan 0 (pelanggaran), diekspor ke JSON. Hash chain ledger dihitung ulang **di luar aplikasi** (Python `hashlib`) memakai kontrak yang sama dengan `app/services/ledger_service.py` (`payload_hash = sha256(prev_hash + payload)`), sehingga lulusnya `/ledger/verify` tidak dipakai sebagai bukti tunggal.

**Catatan lingkungan (penting).** Backend demo berjalan dengan `--reload` dan seeder demo aktif. Isi tabel **bergerak** selama audit: pada 13:44Z tercatat 125 batch/48 keputusan/6.015 `price_signals`; pada snapshot 14:42:20Z menjadi 78/32/5.924. Karena itu setiap angka pada dokumen ini diberi konteks waktu, dan seluruh angka "isi tabel" diambil dari satu snapshot transaksional, bukan dari beberapa query terpisah.

**Batas kerja.** Audit ini tidak menulis apa pun ke DB demo, sehingga jalur tulis (approve, execute, penerbitan PO) tidak diuji secara transaksional — lihat §9.

---

## 2. Inventaris skema (dari `pg_catalog`)

### 2.1 Ringkasan objek

| Objek | Jumlah | Sumber query |
|---|---|---|
| Tabel `relkind='r'` di `public` | 24 (23 domain + `alembic_version`) | `pg_class` + `pg_namespace` |
| Kolom | 241 (240 domain) | `information_schema.columns` |
| Primary key | 24 | `pg_constraint contype='p'` |
| Foreign key | 52 | `pg_constraint contype='f'` |
| UNIQUE (constraint) | 9 | `pg_constraint contype='u'` |
| CHECK | 42, seluruhnya tervalidasi | `pg_constraint contype='c'`, `convalidated` |
| Indeks | 112 | `pg_indexes` |
| Indeks unik parsial (`WHERE`) | 8 | `pg_indexes.indexdef LIKE '%WHERE%'` |
| Kolom FK tanpa indeks pendukung | **0** | `pg_constraint` × `pg_index` (kolom pertama indeks) |
| Constraint `NOT VALID` | 0 (FK maupun CHECK) | `pg_constraint.convalidated = false` |
| Trigger non-internal | **0** | `pg_trigger where not tgisinternal` |

Ringkasan per tabel (kolom / FK keluar / tabel yang merujuk / UNIQUE / CHECK / indeks):

| Tabel | Kolom | FK keluar | Dirujuk | UNIQUE | CHECK | Indeks |
|---|---|---|---|---|---|---|
| `agent_traces` | 12 | 1 | 0 | 0 | 1 | 3 |
| `alembic_version` | 1 | 0 | 0 | 0 | 0 | 1 |
| `approvals` | 6 | 2 | 0 | 0 | 0 | 4 |
| `batch_receipts` | 12 | 5 | 0 | 0 | 1 | 8 |
| `batches` | 21 | 5 | 1 | 0 | 6 | 9 |
| `commodities` | 4 | 0 | 7 | 1 | 0 | 2 |
| `decision_evidence` | 6 | 1 | 0 | 0 | 1 | 2 |
| `decisions` | 22 | 6 | 7 | 0 | 4 | 10 |
| `delivery_events` | 9 | 2 | 0 | 0 | 1 | 5 |
| `demand_records` | 10 | 3 | 0 | 1 | 2 | 7 |
| `demo_sessions` | 8 | 1 | 13 | 0 | 1 | 4 |
| `disposal_events` | 11 | 3 | 0 | 0 | 1 | 6 |
| `ledger_blocks` | 10 | 0 | 0 | 1 | 1 | 4 |
| `ledger_meta` | 3 | 0 | 0 | 0 | 0 | 1 |
| `locations` | 7 | 0 | 11 | 1 | 0 | 2 |
| `menu_plans` | 8 | 2 | 1 | 1 | 1 | 4 |
| `price_signals` | 12 | 4 | 0 | 0 | 4 | 8 |
| `road_routes` | 13 | 1 | 0 | 1 | 3 | 3 |
| `sap_mock_material_stock` | 9 | 1 | 0 | 0 | 0 | 2 |
| `sap_mock_purchase_orders` | 11 | 3 | 0 | 1 | 3 | 5 |
| `supplier_exclusions` | 16 | 6 | 0 | 0 | 1 | 8 |
| `suppliers` | 13 | 2 | 5 | 0 | 6 | 4 |
| `supply_records` | 10 | 3 | 1 | 1 | 3 | 7 |
| `users` | 7 | 1 | 6 | 1 | 2 | 3 |

### 2.2 Kolom per tabel

Tanda `*` = `NULLABLE`. Urutan sesuai `ordinal_position`.

| Tabel | Kolom (urut) | Jml |
|---|---|---|
| `agent_traces` | `id`, `decision_id`, `step_name`, `tool_called*`, `input_summary*`, `output_summary*`, `duration_ms*`, `step_at`, `run_id*`, `agent_name*`, `confidence*`, `citations*` | 12 |
| `alembic_version` | `version_num` | 1 |
| `approvals` | `id`, `decision_id`, `approved_by`, `approved`, `comment*`, `approved_at` | 6 |
| `batch_receipts` | `id`, `batch_id`, `checked`, `other_note*`, `recorded_by`, `recorded_at`, `demo_session_id*`, `status`, `reviewed_by*`, `reviewed_at*`, `review_note*`, `supply_record_id*` | 12 |
| `batches` | `id`, `commodity_id`, `location_id`, `supplier_id`, `quantity_kg`, `harvested_at`, `temperature_log`, `certification_status`, `freshness_score*`, `safety_status`, `usable_until*`, `created_at`, `origin`, `generated_at*`, `dispatched_at*`, `quarantine_status`, `quarantine_reason*`, `quarantined_at*`, `quarantine_updated_at*`, `quarantine_actor_id*`, `demo_session_id*` | 21 |
| `commodities` | `id`, `name`, `unit`, `created_at` | 4 |
| `decision_evidence` | `id`, `decision_id`, `evidence_type`, `payload`, `is_consistent*`, `recorded_at` | 6 |
| `decisions` | `id`, `decision_type`, `status`, `proposed_by`, `verified_by*`, `verifier_note*`, `source_location_id*`, `target_location_id*`, `commodity_id*`, `quantity_kg*`, `safe_delivered_cost*`, `cost_breakdown*`, `expires_at`, `created_at`, `rejection_reason*`, `iteration`, `supersedes_id*`, `demo_case*`, `origin`, `generated_at*`, `supplier_id*`, `demo_session_id*` | 22 |
| `delivery_events` | `id`, `menu_plan_id`, `delivered_portions`, `status`, `delivered_at`, `origin`, `generated_at*`, `demo_session_id*`, `source_ref*` | 9 |
| `demand_records` | `id`, `location_id`, `commodity_id`, `quantity_kg`, `needed_by`, `recorded_at`, `created_at`, `origin`, `generated_at*`, `demo_session_id*` | 10 |
| `demo_sessions` | `id`, `status`, `started_at`, `expires_at`, `anchor_now`, `ended_at*`, `template_version*`, `created_by*` | 8 |
| `disposal_events` | `id`, `location_id`, `commodity_id`, `quantity_kg`, `reason`, `disposed_at`, `origin`, `generated_at*`, `partner_name*`, `demo_session_id*`, `source_ref*` | 11 |
| `ledger_blocks` | `id`, `height`, `prev_hash`, `payload_hash`, `action`, `entity_id*`, `actor_id*`, `payload`, `created_at`, `generation` | 10 |
| `ledger_meta` | `id`, `generation`, `updated_at` | 3 |
| `locations` | `id`, `name`, `region`, `latitude`, `longitude`, `role_hint*`, `created_at` | 7 |
| `menu_plans` | `id`, `location_id`, `plan_date`, `planned_portions`, `created_at`, `origin`, `generated_at*`, `demo_session_id*` | 8 |
| `price_signals` | `id`, `location_id`, `commodity_id`, `price_per_kg`, `recorded_at`, `source`, `created_at`, `supplier_id*`, `origin`, `generated_at*`, `demo_session_id*`, `source_ref*` | 12 |
| `road_routes` | `id`, `route_key`, `profile`, `origin_lat`, `origin_lon`, `destination_lat`, `destination_lon`, `distance_m`, `duration_s`, `geometry`, `source`, `fetched_at`, `demo_session_id*` | 13 |
| `sap_mock_material_stock` | `id`, `material_number`, `plant`, `storage_location*`, `batch*`, `quantity`, `unit`, `created_at`, `demo_session_id*` | 9 |
| `sap_mock_purchase_orders` | `id`, `po_number`, `supplier_id`, `material_number`, `ordered_quantity`, `price`, `decision_id*`, `status`, `created_at`, `demo_session_id*`, `origin` | 11 |
| `supplier_exclusions` | `id`, `supplier_id`, `scope_location_id`, `status`, `reason`, `evidence_refs`, `source_decision_id`, `restoration_decision_id*`, `proposed_by`, `approved_at*`, `activated_at*`, `revoked_at*`, `revocation_reason*`, `created_at`, `updated_at`, `demo_session_id*` | 16 |
| `suppliers` | `id`, `name`, `location_id`, `reliability_score`, `created_at`, `latitude*`, `longitude*`, `commodity_id*`, `capacity_kg_per_week*`, `certification_status*`, `address*`, `contact_name*`, `updated_at*` | 13 |
| `supply_records` | `id`, `location_id`, `commodity_id`, `quantity_kg`, `recorded_at`, `source`, `created_at`, `origin`, `generated_at*`, `demo_session_id*` | 10 |
| `users` | `id`, `name`, `email`, `password_hash`, `role`, `location_id*`, `created_at` | 7 |

### 2.3 Primary key

Setiap tabel domain memakai PK tunggal `id uuid` dengan `DEFAULT gen_random_uuid()`, kecuali: `ledger_meta` (PK `id smallint`), `alembic_version` (PK `version_num varchar`). Penamaan: `<tabel>_pkey` (konsisten).

### 2.4 Foreign key (52)

Format: `kolom`→`tabel induk` (aksi `ON DELETE`; tanpa keterangan = `NO ACTION`).

| Tabel anak | Foreign key |
|---|---|
| `agent_traces` | `decision_id`→`decisions` (CASCADE) |
| `approvals` | `approved_by`→`users`, `decision_id`→`decisions` (CASCADE) |
| `batch_receipts` | `batch_id`→`batches` (CASCADE), `demo_session_id`→`demo_sessions` (SET NULL), `recorded_by`→`users`, `reviewed_by`→`users` (SET NULL), `supply_record_id`→`supply_records` (SET NULL) |
| `batches` | `commodity_id`→`commodities`, `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations`, `quarantine_actor_id`→`users` (SET NULL), `supplier_id`→`suppliers` |
| `decision_evidence` | `decision_id`→`decisions` (CASCADE) |
| `decisions` | `commodity_id`→`commodities`, `demo_session_id`→`demo_sessions` (SET NULL), `source_location_id`→`locations`, `supersedes_id`→`decisions` (SET NULL), `supplier_id`→`suppliers` (SET NULL), `target_location_id`→`locations` |
| `delivery_events` | `demo_session_id`→`demo_sessions` (SET NULL), `menu_plan_id`→`menu_plans` (CASCADE) |
| `demand_records` | `commodity_id`→`commodities`, `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations` |
| `demo_sessions` | `created_by`→`users` (SET NULL) |
| `disposal_events` | `commodity_id`→`commodities` (RESTRICT), `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations` (CASCADE) |
| `menu_plans` | `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations` (CASCADE) |
| `price_signals` | `commodity_id`→`commodities`, `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations`, `supplier_id`→`suppliers` |
| `road_routes` | `demo_session_id`→`demo_sessions` (SET NULL) |
| `sap_mock_material_stock` | `demo_session_id`→`demo_sessions` (SET NULL) |
| `sap_mock_purchase_orders` | `decision_id`→`decisions` (CASCADE), `demo_session_id`→`demo_sessions` (SET NULL), `supplier_id`→`suppliers` |
| `supplier_exclusions` | `demo_session_id`→`demo_sessions` (SET NULL), `proposed_by`→`users`, `restoration_decision_id`→`decisions` (SET NULL), `scope_location_id`→`locations`, `source_decision_id`→`decisions` (CASCADE), `supplier_id`→`suppliers` |
| `suppliers` | `commodity_id`→`commodities`, `location_id`→`locations` |
| `supply_records` | `commodity_id`→`commodities`, `demo_session_id`→`demo_sessions` (SET NULL), `location_id`→`locations` |
| `users` | `location_id`→`locations` |

Catatan katalog: 9 FK memakai `ON DELETE CASCADE`, 20 `SET NULL`, 1 `RESTRICT` (`disposal_events.commodity_id` — komoditas yang sudah punya riwayat limbah tidak boleh dihapus), dan 22 `NO ACTION`. `approvals.approved_by`, `supplier_exclusions.proposed_by`, dan `batch_receipts.recorded_by` sengaja `NO ACTION` sehingga akun yang pernah menyetujui tidak bisa dihapus begitu saja.

### 2.5 UNIQUE constraint (9)

| Tabel | Nama | Definisi |
|---|---|---|
| `commodities` | `commodities_name_key` | UNIQUE (name) |
| `demand_records` | `uq_demand_records_loc_com_time` | UNIQUE (location_id, commodity_id, recorded_at) |
| `ledger_blocks` | `ledger_blocks_height_key` | UNIQUE (height) |
| `locations` | `locations_name_key` | UNIQUE (name) |
| `menu_plans` | `uq_menu_plans_loc_date` | UNIQUE (location_id, plan_date) |
| `road_routes` | `uq_road_routes_key` | UNIQUE (route_key) |
| `sap_mock_purchase_orders` | `sap_mock_purchase_orders_po_number_key` | UNIQUE (po_number) |
| `supply_records` | `uq_supply_records_loc_com_time_source` | UNIQUE (location_id, commodity_id, recorded_at, source) |
| `users` | `users_email_key` | UNIQUE (email) |

### 2.6 Indeks unik parsial (8) — aturan domain yang ditegakkan database

| Tabel | Nama | Definisi |
|---|---|---|
| `batch_receipts` | `uq_batch_receipts_satu_disetujui` | (batch_id) WHERE (status = 'disetujui'::text) |
| `delivery_events` | `uq_delivery_events_source_ref` | (source_ref) WHERE (source_ref IS NOT NULL) |
| `demo_sessions` | `uq_demo_sessions_satu_aktif` | (status) WHERE ((status)::text = 'active'::text) |
| `disposal_events` | `uq_disposal_events_source_ref` | (source_ref) WHERE (source_ref IS NOT NULL) |
| `price_signals` | `uq_price_signals_quote` | (location_id, commodity_id, supplier_id, recorded_at) WHERE ((source)::text = 'supplier_quote'::text) |
| `price_signals` | `uq_price_signals_reference` | (location_id, commodity_id, recorded_at) WHERE ((source)::text = 'pihps_reference'::text) |
| `price_signals` | `uq_price_signals_source_ref` | (source_ref) WHERE (source_ref IS NOT NULL) |
| `supplier_exclusions` | `uq_supplier_exclusions_active_scope` | (supplier_id, scope_location_id) WHERE (status = 'active'::text) |

Di antara indeks unik parsial itu ada penjaga aturan bisnis yang tidak bisa ditulis sebagai CHECK: `uq_demo_sessions_satu_aktif` (**satu sesi demo aktif**), `uq_batch_receipts_satu_disetujui` (satu penerimaan disetujui per batch), `uq_supplier_exclusions_active_scope` (satu eksklusi aktif per pemasok per lokasi). Satu lagi bukan parsial tetapi sama pentingnya: `uq_approvals_decision_user` (indeks unik penuh pada `(decision_id, approved_by)`) — satu akun hanya boleh memberi satu keputusan approval per usulan, dasar aturan *four eyes*.

### 2.7 CHECK constraint (42)

| Tabel | Jml | Nama |
|---|---|---|
| `agent_traces` | 1 | `agent_traces_step_name_check` |
| `batch_receipts` | 1 | `batch_receipts_status_check` |
| `batches` | 6 | `batches_certification_check`, `batches_dispatch_after_harvest`, `batches_freshness_range_check`, `batches_quarantine_status_check`, `batches_safety_status_check`, `check_batches_origin_vocab` |
| `decision_evidence` | 1 | `decision_evidence_type_check` |
| `decisions` | 4 | `check_decisions_origin_vocab`, `decisions_decision_type_check`, `decisions_quantity_positive_check`, `decisions_status_check` |
| `delivery_events` | 1 | `check_delivery_events_origin_vocab` |
| `demand_records` | 2 | `check_demand_records_origin_vocab`, `demand_records_quantity_nonneg_check` |
| `demo_sessions` | 1 | `demo_sessions_status_check` |
| `disposal_events` | 1 | `check_disposal_events_origin_vocab` |
| `ledger_blocks` | 1 | `ledger_hash_len_check` |
| `menu_plans` | 1 | `check_menu_plans_origin_vocab` |
| `price_signals` | 4 | `check_price_signals_origin_vocab`, `price_signals_price_positive_check`, `price_signals_source_quote_check`, `price_signals_supplier_consistency_check` |
| `road_routes` | 3 | `check_road_routes_source_vocab`, `road_routes_distance_check`, `road_routes_duration_check` |
| `sap_mock_purchase_orders` | 3 | `sap_mock_po_origin_check`, `sap_mock_po_price_positive_check`, `sap_mock_po_status_check` |
| `supplier_exclusions` | 1 | `supplier_exclusions_status_check` |
| `suppliers` | 6 | `check_reliability`, `check_supplier_capacity_nonneg`, `check_supplier_certification_vocab`, `check_supplier_coordinates_pair`, `check_supplier_latitude_range`, `check_supplier_longitude_range` |
| `supply_records` | 3 | `check_supply_records_origin_vocab`, `supply_records_quantity_nonneg_check`, `supply_records_source_check` |
| `users` | 2 | `check_user_role`, `check_user_role_location_scope` |

Definisi lengkap setiap ekspresi CHECK ada di `verify/audit-db/01_catalog.txt` (§CHECK). Yang relevan untuk audit ini:

- `batches_dispatch_after_harvest`: `dispatched_at IS NULL OR dispatched_at >= harvested_at` — urutan waktu kiriman dijaga database.
- `ledger_hash_len_check`: `length(payload_hash)=64 AND length(prev_hash)=64` — bentuk hash dijaga, isi hash tidak (lihat D-03).
- `decisions_quantity_positive_check`, `demand_records_quantity_nonneg_check`, `supply_records_quantity_nonneg_check`, `sap_mock_po_price_positive_check`, `price_signals_price_positive_check`.
- `check_supplier_coordinates_pair` + `check_supplier_latitude_range` + `check_supplier_longitude_range` — koordinat pemasok harus lengkap sepasang dan dalam rentang bumi, **tetapi tidak ada constraint yang menjamin koordinat unik antar pemasok** (lihat §7).
- `check_*_origin_vocab` (9 tabel) — `origin` hanya `seed`/`demo`.
- `price_signals_supplier_consistency_check` — `pihps_reference` wajib tanpa `supplier_id`, `supplier_quote` wajib dengan.

### 2.8 Indeks (112)

Distribusi 112 indeks: **24** PK, **9** UNIQUE constraint, **9** indeks unik mandiri (`uq_approvals_decision_user` + 8 unik parsial), dan **70** B-tree non-unik. Seluruh 52 kolom FK sudah menjadi kolom pertama sebuah indeks (0 temuan) — memperbaiki temuan lama AUDIT_05 BUG-001.

**Temuan kecil:** `suppliers.location_id` punya **dua** indeks identik (`idx_suppliers_location` dan `ix_suppliers_location_id`) — duplikat, biaya tulis ganda tanpa manfaat baca.

Statistik `pg_stat_user_indexes`: **28 indeks belum pernah dipakai** (`idx_scan = 0`) sejak statistik terakhir direset. Ini bukan cacat — sebagian besar indeks melayani query yang belum dijalankan pada instance ini — tetapi daftarnya perlu ditinjau sebelum produksi (§8 D-09).

### 2.9 Isi tabel (snapshot 2026-10-26 14:42:20Z)

| Tabel | Baris | | Tabel | Baris |
|---|---|---|---|---|
| `agent_traces` | 69 | | `ledger_blocks` | 1.742 |
| `approvals` | 13 | | `ledger_meta` | 1 |
| `batch_receipts` | 1 | | `locations` | 10 |
| `batches` | 78 | | `menu_plans` | 660 |
| `commodities` | 4 | | `price_signals` | 5.924 |
| `decision_evidence` | 31 | | `road_routes` | 53 |
| `decisions` | 32 | | `sap_mock_material_stock` | 40 |
| `delivery_events` | 180 | | `sap_mock_purchase_orders` | 12 |
| `demand_records` | 1.360 | | `supplier_exclusions` | 2 |
| `demo_sessions` | 6 | | `suppliers` | 60 |
| `disposal_events` | 80 | | `supply_records` | 5.240 |
| | | | `users` | 8 |

Komposisi status saat snapshot: keputusan `pending_approval` 15, `rejected` 9, `verifier_flagged` 4, `proposed` 1, `approved` 1, `executed` 1, `review_only` 1. Sesi demo: 5 `expired` + 1 `ended`, **0 `active`**.

**Bukti bahwa DB ini hidup:** angka 13:44Z (125 batch / 48 keputusan / 6.015 `price_signals`) berbeda dari snapshot 14:42Z. Setiap angka pada dokumen ini harus dibaca dengan jamnya.

---

## 3. Drift model ↔ skema aktual

| Pemeriksaan | Perintah | Hasil |
|---|---|---|
| Tabel model vs tabel DB | ekstraksi `__tablename__` (23 model) vs `pg_tables` (23 domain) | **23 = 23**, tidak ada model tanpa tabel maupun tabel tanpa model |
| Autogenerate drift pada DB demo | `alembic check` (di container backend) | `No new upgrade operations detected.` |
| Autogenerate drift pada DB baru hasil migrasi | `alembic check` dengan `DATABASE_URL` → `audit_schema` | `No new upgrade operations detected.` |
| Indeks FK di model | `tests/test_fk_index_coverage.py` + katalog | 0 FK tanpa indeks (migrasi 033 sudah tercermin di model) |

**Kesimpulan: tidak ada drift.** Metadata SQLAlchemy, rantai migrasi, dan database demo menghasilkan skema yang sama — dibuktikan dari dua arah (DB demo yang berevolusi vs DB baru hasil `upgrade head`).

**Satu perbedaan tekstual yang perlu dicatat (bukan drift).** Membandingkan `pg_get_constraintdef` DB demo vs DB baru: 17 ekspresi CHECK berbeda **bentuk penulisannya** — DB demo menulis cast per elemen (`('none'::character varying)::text`), DB baru menulis cast seluruh array (`(ARRAY['none', ...])::text[]`). Himpunan nilai yang diizinkan identik pada semua 17 pasangan, dan `alembic check` menyatakan keduanya cocok dengan model. Perbedaan ini tidak mengubah perilaku; **penyebab pastinya tidak diverifikasi** (kandidat: file migrasi lama pernah disunting setelah diterapkan pada DB demo). Dicatat sebagai D-10/UNVERIFIED.

Perbedaan lain pada `pg_dump -s` (pemilik schema, `REVOKE USAGE ON SCHEMA public FROM PUBLIC`) adalah artefak lingkungan, bukan skema aplikasi.

---

## 4. Pemeriksaan integritas data — 134 cek

Skrip: `verify/audit-db/run_checks.py` (semua `SELECT`). Hasil lengkap: `verify/audit-db/05_checks.json`. Dijalankan 2026-10-26 21:37–21:49 WIB; dua kali eksekusi (21:45 dan 21:49) memberi angka identik, jadi angka di bawah stabil meski data demo bergerak.

**Ringkasan: 134 cek — 132 PASS, 2 FAIL.**

### 4.1 Orphan (referensial)

**Sapuan generik seluruh 52 FK** (bukan hanya yang diingat): untuk setiap `(tabel anak, kolom, tabel induk)` dihitung `count(*)` anak dengan kolom tidak null yang tidak punya induk.

```sql
SELECT count(*) FROM <anak> c LEFT JOIN <induk> p ON p.id = c.<kolom>
WHERE c.<kolom> IS NOT NULL AND p.id IS NULL;
```

**Hasil: 0 orphan pada seluruh 52 FK** (`orphan_fk_nonzero = {}`). Konsisten dengan 52 FK yang semuanya tervalidasi.

Pemeriksaan tambahan untuk referensi "lunak" yang tidak dijaga FK:

| Cek | Query (ringkas) | Hasil |
|---|---|---|
| Blok ledger yatim (generasi aktif) | `ledger_blocks.entity_id` tanpa baris di `decisions`/`batches`/`users`/`locations` untuk `generation = ledger_meta.generation` | **12 → FAIL** |
| `decision_evidence` yatim | `LEFT JOIN decisions` | 0 |
| Stempel `demo_session_id` menunjuk sesi tidak ada | `EXCEPT SELECT id FROM demo_sessions` | 0 |

Rincian 12 blok yatim: 4 `entity_id` berbeda × 3 aksi (`decision.created`, `verify`, `execute`), seluruhnya `generation = 239` (generasi aktif), `height` 1678–1689, `created_at = 2026-10-26 13:43:23.855448+00` — identik dengan waktu `ledger_meta.updated_at`. Keempat `entity_id` tidak ada lagi di `decisions`. `/ledger/verify` melaporkan hal yang sama secara jujur: `orphan_blocks: 12`, `coverage_warning: "12 blok generasi aktif menunjuk entitas yang sudah tidak ada"`, `valid: true`.

### 4.2 Duplikat

| Cek | Query (ringkas) | Hasil |
|---|---|---|
| `approvals` ganda per (keputusan, user) | `GROUP BY decision_id, approved_by HAVING count(*)>1` | 0 |
| >1 PO per keputusan | `GROUP BY decision_id HAVING count(*)>1` | 0 (vakum — lihat D-05) |
| >1 sesi demo `active` | `greatest(count(*)-1,0) WHERE status='active'` | 0 |
| >1 penerimaan `disetujui` per batch | `GROUP BY batch_id HAVING count(*)>1` | 0 |
| `ledger_blocks.height` ganda | `GROUP BY height HAVING count(*)>1` | 0 |
| Email pengguna ganda (case-insensitive) | `GROUP BY lower(email)` | 0 |
| Nama pemasok ganda | `GROUP BY lower(name)` | 0 |
| **Koordinat pemasok identik** | `GROUP BY latitude, longitude HAVING count(*)>1` | **0** (60 pemasok, 60 koordinat unik, 0 tanpa koordinat) |
| Pemasok dobel (nama+komoditas+lokasi) | `GROUP BY location_id, commodity_id, lower(name)` | 0 |
| `supply_records` ganda (loc, komoditas, waktu, sumber) | `GROUP BY ... HAVING count(*)>1` | 0 |
| Sinyal harga referensi ganda | `GROUP BY location_id, commodity_id, recorded_at` untuk `pihps_reference` | 0 |

Catatan penting: "koordinat pemasok unik" **terbukti benar untuk data saat ini, tetapi tidak dijamin database** — tidak ada `UNIQUE(latitude, longitude)`. Data baru bisa membuat dua pemasok berbagi titik tanpa penolakan (lihat §7).

### 4.3 Nilai status tak sah (kosakata)

Setiap kolom berstatus diuji dengan `NOT IN (<kosakata>)`; angka harapan 0. Semua **PASS**:

| Kolom | Kosakata yang ditegakkan | Pelanggaran |
|---|---|---|
| `decisions.status` | proposed, verifier_flagged, pending_approval, approved, rejected, executed, review_only | 0 |
| `decisions.decision_type` | regional_balance, price_anomaly, safety_disruption, supplier_exclusion, supplier_exclusion_restoration, supplier_procurement | 0 |
| `batches.safety_status` / `quarantine_status` / `certification_status` | pending/pass/fail/needs_verification · none/quarantined/released/failed · none/hygiene/haccp | 0 |
| `agent_traces.step_name` | DETECT, VERIFY, TRACE, PREDICT, OPTIMIZE, DECIDE, SUPERVISE, ACT, LEARN | 0 |
| `batch_receipts.status` | menunggu, disetujui, ditolak | 0 |
| `sap_mock_purchase_orders.status` | draft, submitted, confirmed | 0 |
| `supplier_exclusions.status` | proposed, active, rejected, revoked | 0 |
| `demo_sessions.status` | active, expired, ended | 0 |
| `users.role` | sppg_head, sppg_nutritionist, bgn_monitor | 0 |
| `price_signals.source` | pihps_reference, supplier_quote | 0 |
| `supply_records.source` | mock_sap, manual, sensor | 0 |
| `decision_evidence.evidence_type` | sap_purchase_order, sap_goods_receipt, gps, temperature, human_inspection, market_price | 0 |
| `road_routes.source` | osrm | 0 |
| `delivery_events.status` | delivered, delayed, missed | 0 (tanggungan aplikasi — lihat §7) |
| `origin` pada 9 tabel | seed, demo | 0 |

Status bukan-kosakata lain yang diperiksa: `approvals.approved IS NULL` = 0.

### 4.4 Aturan domain

| Cek | Hasil |
|---|---|
| Keputusan tanpa satu pun jejak langkah | 0 |
| Keputusan `executed` tanpa approval `approved=true` | 0 |
| Keputusan `rejected` tanpa baris `approvals approved=false` | 0 |
| Langkah `LEARN` pada status di luar rejected/proposed | 0 |
| Langkah `ACT` pada keputusan yang tidak `executed` | 0 |
| `agent_traces.step_at` kosong | 0 |
| Batch kuantitas negatif / diberangkatkan sebelum dipanen | 0 / 0 |
| `freshness_score` di luar [0,1] / `reliability_score` di luar [0,1] | 0 / 0 |
| Fakta pasokan/permintaan melewati horizon 31 hari | 0 / 0 |
| PO `ordered_quantity <= 0` / material generik `MAT-UMUM` | 0 / 0 |
| Koordinat pemasok setengah / di luar rentang bumi | 0 / 0 |
| Pengguna dengan peran lokasi tanpa lokasi (atau sebaliknya) | 0 |
| `max(height) <> count(*)` pada `ledger_blocks` | 0 (tidak ada lubang tinggi) |
| Sesi `active` yang sudah lewat `expires_at` | 0 |
| Keputusan `supplier_procurement` `executed` tanpa PO | 0 (vakum: tidak ada pengadaan executed) |
| **SDC ≠ purchase+transport+handling+expected_loss+freshness_risk+safety_penalty** | **4 → FAIL** |
| `cost_breakdown.total` (bila ada) ≠ SDC | 0 |

Informasi tambahan (bukan PASS/FAIL):

| INFO | Nilai | Tafsir |
|---|---|---|
| Keputusan approved/executed dengan <2 role approver | 0 | empat mata terpenuhi pada 2 keputusan yang lolos approval |
| Approval atas nama `bgn_monitor` | 0 | peran monitor tetap read-only |
| PO menunjuk keputusan yang tidak executed | 0 | — |
| **PO tanpa `decision_id`** | **12 dari 12** | rantai keputusan→PO tidak terbukti (D-05) |
| PO `draft` untuk keputusan executed | 0 | — |
| Keputusan `executed` tanpa jejak `ACT` / tanpa `decision_evidence` | 0 / 0 | — |
| Keputusan pending/proposed yang sudah kedaluwarsa | 0 | — |
| Sesi demo `active` | 0 | sesi terakhir berakhir 14:29Z |
| Baris yang masih berstempel `demo_session_id` | 0 | — |
| **Baris `origin='demo'`** | **0** | data demo tidak ada saat snapshot (sesi kedaluwarsa / dibekukan) |
| Akun uji `@test.local`/`@uji-peran.local` tertinggal | 1 | residu pytest (D-07) |
| **Keputusan ber-`demo_case` dengan `origin='seed'`** | **26** | dibekukan oleh `_bekukan` (D-04) |

### 4.5 Ledger: verifikasi independen

Dihitung ulang di luar aplikasi atas 1.742 blok (semua generasi, urut `height`):

- `prev_hash` tiap blok = `payload_hash` blok sebelumnya; blok `height=1` ber-`prev_hash` 64 nol (genesis): **0 pelanggaran**.
- `sha256(prev_hash + payload)` = `payload_hash` tersimpan: **0 pelanggaran**.
- `height` berurutan 1..1742 tanpa lubang: **0 pelanggaran**.
- Kepala rantai: `f8243b1ff4c27295ce281020d0098b61ab7c1b8ff7a080932072b367feb3accd`, cocok dengan `head` yang dilaporkan `GET /ledger/verify`.
- Generasi: 30 generasi (62…239); 1.670 blok diarsipkan (generasi < 239), 72 blok generasi aktif, 60 di antaranya tertaut ke entitas hidup, **12 yatim**.

Integritas kriptografis rantai **baik**. Masalahnya bukan hash, melainkan cakupan: blok yang menunjuk entitas yang sudah tidak ada, dan tidak adanya penegakan *append-only* di sisi database (§8 D-02, D-03).

### 4.6 Dua kegagalan — analisis akar

#### (1) `RULE-SDC-BREAKDOWN` — 4 keputusan

```sql
SELECT count(*) FROM decisions d
WHERE d.cost_breakdown ? 'purchase' AND d.safe_delivered_cost IS NOT NULL
  AND abs(d.safe_delivered_cost - (
        (d.cost_breakdown->>'purchase')::numeric
      + (d.cost_breakdown->>'transport')::numeric
      + (d.cost_breakdown->>'handling')::numeric
      + (d.cost_breakdown->>'expected_loss')::numeric
      + coalesce((d.cost_breakdown->>'freshness_risk')::numeric,0)
      + coalesce((d.cost_breakdown->>'safety_penalty')::numeric,0))) > 0.01;
-- hasil: 4
```

| Keputusan | Status | Qty | SDC | Σ komponen | Selisih |
|---|---|---|---|---|---|
| `a689f24e…` (gangguan-logistik) | pending_approval | 420 | 11.024.322,67 | 15.749.032,38 | 4.724.709,71 |
| `552ef62b…` (rejection-loop-kuota) | pending_approval | 420 | 11.024.322,67 | 15.749.032,38 | 4.724.709,71 |
| `ed68955c…` (shortage-darurat) | pending_approval | 546 | 15.456.603,67 | 22.080.862,39 | 6.624.258,72 |
| `30bce401…` (supplier-janggal) | verifier_flagged | 420 | 11.024.322,67 | 15.749.032,38 | 4.724.709,72 |

Akar masalah terukur, bukan dugaan:

1. `cost_breakdown.purchase = 15.269.400 = 600 kg × Rp 25.449/kg`, dan `expected_loss = 305.388 = 2% × purchase` — jadi breakdown dibangun untuk **600 kg** (dan 780 kg pada baris kedua: 21.656.169,60 = 780 × 27.764,32).
2. `quantity_kg = 420 = 600 × 0,7` dan `546 = 780 × 0,7`; `safe_delivered_cost = Σ komponen × 0,7` (dihitung: 15.749.032,38 × 0,7 = 11.024.322,666 → 11.024.322,67 persis).
3. Di `backend/app/seed/demo_template.py` baris 788–811, salinan "kartu kedua" menskalakan kuantitas dan biaya 70% tetapi **menyalin `cost_breakdown` apa adanya**:
   ```python
   kuantitas = (d.quantity_kg or Decimal("600")) * Decimal("0.7")
   biaya     = (d.safe_delivered_cost or Decimal("0")) * Decimal("0.7")
   ...
   quantity_kg=kuantitas, safe_delivered_cost=biaya,
   cost_breakdown=d.cost_breakdown,          # ← tidak diskalakan
   ```
4. Konsekuensi demo: kartu yang **menunggu approval manusia** menampilkan rincian yang bila dijumlahkan berbeda Rp 4,7–6,6 juta dari angka `safe_delivered_cost` yang disetujui. Ini persis kelas cacat yang membuat "angka di layar" tidak bisa dipertanggungjawabkan.
5. Invarian yang ada **tidak menangkapnya**: `sdc di jejak DECIDE == SDC keputusan` hanya membandingkan dua salinan angka yang sama-sama sudah diskalakan (`output_summary.sdc = float(biaya)`), sehingga PASS.

Catatan tambahan (bukan pelanggaran aritmetika): 3 keputusan lain memakai `cost_breakdown` naratif tanpa komponen (`{"catatan": ...}`, `{"quote_price_per_kg": ...}`), sehingga SDC-nya memang tidak bisa direkonsiliasi dari breakdown. Perlu penanda eksplisit bahwa breakdown bersifat naratif, bukan rincian biaya.

#### (2) `ORPH-LEDGER` — 12 blok

```sql
WITH g AS (SELECT generation FROM ledger_meta WHERE id=1)
SELECT count(*) FROM ledger_blocks lb, g
WHERE lb.generation = g.generation AND lb.entity_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM decisions d WHERE d.id=lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM batches b WHERE b.id=lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id=lb.entity_id)
  AND NOT EXISTS (SELECT 1 FROM locations l WHERE l.id=lb.entity_id);
-- hasil: 12
```

Fakta terukur: 4 `entity_id` × 3 aksi, semuanya `generation = 239`, `created_at` identik dengan `ledger_meta.updated_at` (13:43:23.855448Z), dan keempat keputusan sudah tidak ada. Urutan yang menghasilkan kondisi ini ada di `backend/app/seed/demo_template.py`:

- `_semai_bukti_dan_rantai()` memanggil `bump_generation()` lalu menulis blok untuk **semua keputusan yang ada saat itu** (baris 1337–1385).
- Pada bangun-ulang yang sama, `_penggandaan_jakarta()` memanggil `_seed_demo_cases(db, force=True, …)` yang **menghapus** keputusan demo ber-id acak (`backend/app/api/demo.py:325–332`) lalu membuat yang baru.

Karena `ledger_blocks` tidak punya FK ke `decisions`, penghapusan tidak meninggalkan jejak apa pun di ledger; karena generasi tidak dinaikkan lagi setelah penghapusan, blok itu dihitung sebagai yatim **generasi aktif**. Perbaikannya bukan di ledger (hash tetap valid) melainkan pada urutan/penandaan: tulis blok setelah himpunan keputusan final, atau naikkan generasi setiap kali baris yang sudah berblok dihapus.

---

## 5. Migrasi: head aktual vs dokumentasi

| Pemeriksaan | Hasil |
|---|---|
| `SELECT version_num FROM alembic_version` | **`033_indeks_fk_hilang`** |
| `alembic current` (DB demo) | `033_indeks_fk_hilang (head)` |
| Jumlah file revisi di `backend/alembic/versions/` | **33** |
| Rantai revisi | linear 001 → 002 → 004 → … → 033; tidak ada cabang (`down_revision` unik per revisi), tidak ada `down_revision` menunjuk revisi yang tidak ada |
| Nomor 003 | **tidak pernah ada** (lompatan penomoran 002 → 004), bukan revisi hilang |
| `alembic upgrade head` dari database kosong (`audit_schema`) | **sukses**, 33 revisi berjalan berurutan tanpa error |
| Skema hasil migrasi vs DB demo | kolom 241 = 241, constraint 127 = 127 (nama & jenis identik), indeks 112 = 112 → **identik** |
| `alembic check` pada DB hasil migrasi | `No new upgrade operations detected.` |

**Dokumentasi `docs/audit/AUDIT_05_DATABASE_DATA_LINEAGE.md` akurat pada tiga klaim yang bisa diuji ulang:** "24 tabel, 33 revisi migrasi, head `033_indeks_fk_hilang`" — ketiganya cocok dengan katalog dan `alembic_version`. Klaim BUG-001 ("22 indeks FK dibuat migrasi 033 tetapi tidak ada di model → `alembic check` gagal") **sudah tidak berlaku**: `alembic check` sekarang bersih di dua database berbeda, dan katalog menunjukkan 0 kolom FK tanpa indeks. Artinya perbaikan model benar-benar mendarat, bukan hanya di dokumen.

Yang tidak tercakup dokumen: lompatan nomor 003, dan fakta bahwa teks 17 CHECK berbeda antara DB demo dan DB baru (D-10).

---

## 6. `verify_stack.py` — PASS/FAIL/SKIP per invarian

Perintah: `python <skills>/fullstack-verification/scripts/verify_stack.py verify/invariants.spec.json`
Hasil: **VERDICT: PASS (PASS 52 / FAIL 0 / SKIP 1)** — laporan `verify/verify-out-invariants/report-20261026-214103.md`, log `verify/audit-db/07_verify_stack.log`.

**Proses/container (9 PASS).** Port 15432 dan 8000 terjangkau (external, tidak di-start gate), `/health` 200 `status=healthy`, `mealchain-backend` & `mealchain-postgres` `running/healthy`, `restartCount=0`, `oom=false`, tidak ada container mati dengan exit ≠ 0 (81 baris `docker events`), log backend bersih dari traceback.

**Lapisan BE (16 PASS).**

| Cek | Hasil |
|---|---|
| Tanpa token `GET /decisions` / `/batches` / `/ledger/verify` → 401 | 401 / 401 / 401 |
| Kepala SPPG `GET /admin/users` → 403 | 403 |
| `GET /batches?limit=1` bentuk `count,total,batches` | 200, `total=78` |
| `GET /decisions` `items` | 200, 15 item (scope peran) |
| `GET /demo/session` bentuk `active,enforced,session_id,status,expires_at,anchor_now,server_now` | 200 |
| `GET /ledger/verify` → `valid:true` | 200, 57 ms |
| `GET /decisions/<uuid tidak ada>/chain` → 404; id non-UUID → 422; batch tidak ada → 404 | 404 / 422 / 404 |
| `limit=0` → 422; `limit=1000` → 422; `limit=1` → `count=1` | 422 / 422 / 200 |
| `/health` → `status=healthy` | 200 |

**Lapisan DB (25 PASS: 1 cek koneksi + 24 invarian SQL).**

| Invarian | Angka |
|---|---|
| head migrasi = `033_indeks_fk_hilang` | PASS |
| jumlah batch DB == API | 78 == 78 |
| keputusan scope Jakarta (DB) == API | 15 == 15 |
| batch kuantitas negatif | 0 |
| batch diberangkatkan sebelum dipanen | 0 |
| baris kanonik batch/keputusan/pasokan berstempel sesi | 0 / 0 / 0 |
| `LEARN` di luar rejected/proposed | 0 |
| `ACT` pada non-executed | 0 |
| jejak yatim | 0 |
| keputusan tanpa jejak langkah | 0 |
| >1 PO per keputusan | 0 |
| `step_at` kosong | 0 |
| approval yatim | 0 |
| keputusan executed tanpa approval | 0 |
| fakta pasokan/permintaan melewati horizon 31 hari | 0 / 0 |
| PO `ordered_quantity<=0` | 0 |
| PO material `MAT-UMUM` | 0 |
| keputusan rejected tanpa pencatat | 0 |
| jejak berisi teks template | 0 |
| SDC di jejak DECIDE == SDC keputusan (±1) | 0 |

**Lapisan compare (2 PASS).** `api_batches=78 == db_batches=78`; `api_decisions=15 == db_decisions=15`.

**SKIP (1).** `fe browser checks — no ui section in spec`. Lapisan browser tidak diuji oleh spec ini; tidak ada klaim UI dalam dokumen ini.

Catatan metodologis: spec ini sempat mencatat dua temuan historis (21 Okt 2026: 2 keputusan tanpa jejak, 1 keputusan executed tanpa approval). Keduanya sekarang 0 → perbaikan terverifikasi ulang, bukan hanya diklaim.

---

## 7. Apakah invarian yang ada sudah mencukupi?

Matrix aturan penting vs tempat penegakannya:

| Aturan domain | Ditegakkan DB? | Ada di `invariants.spec.json`? | Status cakupan |
|---|---|---|---|
| Keputusan tanpa `agent_traces` | tidak | **ya** (`NOT EXISTS agent_traces`) | **tercakup** |
| Approval ganda (satu akun dua kali per keputusan) | **ya** — `uq_approvals_decision_user` | tidak | tercakup DB, **tidak** oleh gate |
| Four-eyes (2 role berbeda sebelum approve/execute) | tidak (aturan ada di `app/core/approval_matrix.py`) | tidak | **tidak tercakup** |
| Sesi demo aktif ganda | **ya** — `uq_demo_sessions_satu_aktif` | tidak | tercakup DB, tidak oleh gate |
| SDC == Σ `cost_breakdown` | tidak | **tidak** (yang ada: SDC jejak == SDC keputusan) | **celah — terbukti ada 4 pelanggaran** |
| Hash-chain ledger utuh | hanya panjang hash (CHECK) | hanya lewat `GET /ledger/verify valid=true` | **parsial** — tidak ada hitung ulang independen, tidak ada cek `orphan_blocks = 0` |
| Cakupan ledger (blok menunjuk entitas hidup) | tidak | tidak | **celah — 12 yatim** |
| Koordinat pemasok unik | **tidak** (hanya pasangan + rentang) | tidak | **celah** (data saat ini kebetulan unik) |
| Data demo ber-`demo_session_id`/`origin='demo'` | tidak | hanya arah sebaliknya (kanonik **tidak** boleh berstempel) | **celah** — 0 baris demo & 0 baris berstempel, jadi cek kanonik lulus secara vakum |
| Rantai keputusan→PO | FK `ON DELETE CASCADE` | hanya ">1 PO per keputusan" | **vakum** — 12/12 PO tanpa `decision_id` |
| Keputusan `executed` punya PO (pengadaan) | tidak | tidak | vakum (0 pengadaan executed) |
| `delivery_events.status` kosakata | **tidak** (tanpa CHECK) | tidak | celah kecil |
| Batas horizon 31 hari, kuantitas positif, urutan dispatch | **ya** (CHECK) | ya (sebagian) | tercakup |

**Penilaian.** Invarian yang ada kuat pada hal-hal yang mudah di-SQL-kan dan yang pernah gagal di masa lalu (jejak agent, approval, kuantitas, horizon). Yang belum tercakup justru kelas aturan yang menyangkut **uang dan audit trail**: rekonsiliasi SDC dengan rinciannya, cakupan ledger, empat mata, dan provenance data demo. Tiga di antaranya sekarang terbukti punya pelanggaran nyata (D-01, D-02, D-04) — bukan sekadar teoretis.

**Usulan penambahan cek** (semua `SELECT`, harapan 0, siap ditempel ke `verify/invariants.spec.json`):

1. `SDC == purchase+transport+handling+expected_loss+freshness_risk+safety_penalty` (toleransi 0,01) untuk baris yang `cost_breakdown` punya kunci komponen — menangkap D-01.
2. `orphan_blocks = 0` untuk generasi aktif (query §4.6) **dan** `archived_blocks` dilaporkan sebagai informasi, bukan pelanggaran — menangkap D-02.
3. `count(*) FROM ledger_blocks` = `count(*)` hasil hitung ulang hash di luar aplikasi (atau minimal `bad_hash = 0` dari skrip Python) — menjadikan gate tidak bergantung pada aplikasi yang sedang diuji.
4. `PO dengan decision_id IS NOT NULL` ≥ 1 dan `PO menunjuk keputusan non-executed = 0` — menghidupkan kembali cek PO yang sekarang vakum.
5. `decisions approved/executed` wajib punya ≥2 approver role berbeda (kecuali admin `supplier_exclusion` dengan verdict `consistent`) — memindahkan matriks approval ke gate.
6. `origin='demo'` ⇒ `demo_session_id IS NOT NULL` **dan** ketika ada sesi aktif, minimal satu baris per tabel operasional berstempel sesi itu — mencegah cek kanonik lulus secara vakum.
7. `count(DISTINCT (latitude,longitude)) = count(*)` pada pemasok berkoordinat — mengawal aturan yang tidak ditegakkan DB.
8. `delivery_events.status IN ('delivered','delayed','missed')` — tutup kosakata yang tidak punya CHECK.

---

## 8. Temuan

Severity: **P1** memblokir demo/produksi · **P2** cacat nyata, perlu diperbaiki · **P3** kebersihan/kualitas · **INFO** catatan.

| ID | Severity | Status | Temuan | Bukti |
|---|---|---|---|---|
| **D-01** | P2 | OPEN | `safe_delivered_cost` ≠ jumlah komponen `cost_breakdown` pada 4 keputusan `pending_approval`/`verifier_flagged`; selisih Rp 4.724.709,71 dan Rp 6.624.258,72. Akar: `demo_template.py:788–811` menskalakan qty & SDC 70% tetapi menyalin breakdown utuh. Approver melihat rincian yang tidak menjumlah ke angka yang disetujui. | `run_checks.py` `RULE-SDC-BREAKDOWN` = 4; tabel §4.6; aritmetika 0,7 × 15.749.032,38 = 11.024.322,67 |
| **D-02** | P2 | OPEN | 12 blok `ledger_blocks` di generasi aktif (239) menunjuk 4 keputusan yang sudah dihapus. Hash chain valid, tetapi jejak audit menunjuk entitas hantu; `/ledger/verify` melaporkan `coverage_warning`. | `ORPH-LEDGER` = 12; API `/ledger/verify` `orphan_blocks: 12`; `demo_template.py:1356` vs `demo.py:325–332` |
| **D-03** | P2 | OPEN | Sifat *append-only* ledger **tidak ditegakkan database**: 0 trigger pada `ledger_blocks`, role aplikasi `mealchain` adalah **superuser + pemilik tabel**, dan `docker-compose.prod.yml` memakai role yang sama. Komentar `ledger_service.py` ("DB user aplikasi TIDAK diberi UPDATE/DELETE di produksi") baru benar bila ada role terpisah/trigger — saat ini tidak ada. | `pg_trigger` (0 baris), `pg_roles.rolsuper = t`, `docker-compose.prod.yml:38,73` |
| **D-04** | P2 | OPEN | Provenance data demo hilang setelah pembekuan: `_bekukan()` menyetel `origin='seed'` dan `demo_session_id=NULL` untuk **semua** baris bersesi. Saat ini 26 keputusan ber-`demo_case` ber-`origin='seed'`, **0** baris `origin='demo'`, **0** baris berstempel sesi. Akibatnya invarian "baris kanonik tidak boleh berstempel" lulus secara vakum dan data turunan demo tidak bisa dibedakan dari data kanonik. | `demo_template.py:1672–1684`; `INFO-KASUS-DEMO = 26`, `INFO-ORIGIN-DEMO = 0`, `INFO-BARIS-BERSESI = 0` |
| **D-05** | P3 | OPEN | 12/12 `sap_mock_purchase_orders` tanpa `decision_id` (PO mirror SAP `45000000xx`) → rantai keputusan→PO tidak terbukti; invarian ">1 PO per keputusan" dan "PO menunjuk keputusan non-executed" lulus secara vakum, dan tidak ada satu pun contoh PO hasil eksekusi keputusan di DB ini. | `INFO-PO-TANPA-KEPUTUSAN = 12`, `INFO-PO-LEAK = 0` |
| **D-06** | P3 | OPEN | Indeks duplikat: `suppliers.location_id` punya `idx_suppliers_location` **dan** `ix_suppliers_location_id` (definisi identik) — biaya tulis ganda. Reproduksi di DB baru → berasal dari migrasi, bukan residu manual. | query duplikat indeks §2.8; katalog 01/03 |
| **D-07** | P3 | OPEN | 1 akun uji `sppg_head-…@test.local` tertinggal di DB demo (residu pytest). | `INFO-PENGGUNA-UJI = 1`; daftar email `users` |
| **D-08** | P3 | OPEN | `verify/invariants.spec.json` belum mencakup 8 aturan pada §7 — termasuk rekonsiliasi SDC, cakupan ledger, empat mata, koordinat pemasok unik, dan stamping demo. Empat pelanggaran D-01 dan 12 pelanggaran D-02 lolos gate. | §7 + run `verify_stack` PASS 52 |
| **D-09** | INFO | OPEN | 28 indeks belum pernah dipakai (`idx_scan = 0`) pada instance ini. Bukan cacat; perlu ditinjau bersama D-06 sebelum produksi. | `pg_stat_user_indexes` |
| **D-10** | INFO | **UNVERIFIED** | 17 ekspresi CHECK berbeda teks antara DB demo dan DB baru hasil migrasi (cast per elemen vs cast array). Himpunan nilai identik, perilaku identik, `alembic check` bersih. **Penyebab tidak diverifikasi.** | `pg_get_constraintdef` kedua DB; `04_schema_diff.txt` |
| **D-11** | INFO | OPEN | 10 database residu uji tertinggal di instance Postgres yang sama (`audit_test`, `mealchain_gate*` ×4, `mealchain_idem*` ×2, `mealchain_iso`, `mealchain_sesiuji`, `mealchain_suite`). Tidak memengaruhi `mealchain` (yang diperiksa), tetapi menunjukkan pembersihan artefak uji belum konsisten. | `SELECT datname FROM pg_database` |

Tidak ada temuan P1: tidak ada kegagalan integritas referensial, tidak ada status ilegal, tidak ada pelanggaran hash chain, dan skema yang dimigrasikan dari nol identik dengan DB demo.

---

## 9. NOT TESTED / UNVERIFIED

Bagian ini eksplisit: hal-hal berikut **tidak** diperiksa, atau diperiksa tetapi belum tuntas.

**Tidak diuji sama sekali**

1. **Jalur tulis** (approve, reject, execute, penerbitan PO, karantina, penerimaan barang). Aturan keras melarang menulis ke DB demo, sehingga constraint empat mata, cascade `ON DELETE`, dan idempotensi penerbitan PO hanya dibuktikan dari katalog dan kode — bukan dari transaksi nyata.
2. **Konkurensi/balapan**: dua approval bersamaan, dua sesi demo aktif bersamaan, dua penulis KPI bersamaan. Yang terbukti hanya *adanya* indeks unik parsial yang akan menolak duplikat.
3. **Backup/restore, PITR, round-trip `pg_dump` → restore**, serta integritas fisik (checksum halaman, `amcheck`).
4. **Performa**: tidak ada `EXPLAIN (ANALYZE)`, tidak ada pengukuran latensi query, tidak ada uji beban. "28 indeks belum terpakai" adalah statistik akumulatif, bukan hasil eksperimen.
5. **Pertumbuhan/retensi ledger**: 1.742 blok, 30 generasi, 1.670 blok arsip — tidak diuji berapa lama arsip boleh tumbuh, tidak ada uji beban tulis ledger.
6. **Seed data dari nol**: hanya **skema** yang diuji dari kosong (`upgrade head`). Penyemaian data dari DB kosong tidak dijalankan (butuh tulisan).
7. **Keamanan database**: enkripsi at-rest, TLS koneksi, `pgaudit`/log audit, row-level security, kebijakan password/role, hak `PUBLIC` pada schema.
8. **Paritas produksi**: `docker-compose.prod.yml` hanya **dibaca**, tidak dijalankan. Semua pengukuran berasal dari stack demo.
9. **Lapisan browser/UI**: `verify_stack.py` SKIP (spec tanpa `ui`). Tidak ada klaim tentang tampilan angka di layar.

**Diperiksa tetapi belum tuntas**

10. **Penyebab D-10** (teks CHECK berbeda) — belum dilacak ke revisi/kode tertentu.
11. **Asal-usul 4 keputusan yang dihapus pada D-02** — jejak waktu menunjukkan bangun-ulang template 13:43:23Z, tetapi pemanggil persisnya (endpoint vs seeder) tidak dapat dipastikan dari log yang tersisa.
12. **Kecukupan `MAT-UMUM`** sebagai satu-satunya penjaga material generik: 12 PO seed memakai kode numerik `1000`–`1003`, konvensi berbeda dari `MAT-<KOMODITAS>`; tidak ada cek yang mengawal kosakata material.
13. **Angka isi tabel bergerak** karena backend demo berjalan dengan `--reload` dan seeder aktif; semua angka pada §2.9 terikat pada snapshot 14:42:20Z dan tidak boleh dibandingkan dengan run lain tanpa memperhitungkan waktu.

---

## 10. Lampiran — artefak dan reproduksi

| Berkas | Isi |
|---|---|
| `verify/audit-db/01_catalog.txt` | Dump katalog: tabel, kolom lengkap (tipe/null/default), PK, 52 FK + aturan delete, 9 UNIQUE, 42 CHECK + ekspresi, 112 indeks, cek FK tanpa indeks, row count |
| `verify/audit-db/02_dump_demo.sql` | `pg_dump -s` database demo |
| `verify/audit-db/03_dump_fresh.sql` | `pg_dump -s` database baru hasil `alembic upgrade head` |
| `verify/audit-db/04_schema_diff.txt` | Diff kedua dump (dasar D-10) |
| `verify/audit-db/05_checks.json` | 134 cek + SQL + hasil + 14 INFO, JSON |
| `verify/audit-db/06_run.log` | Ringkasan eksekusi 134 cek |
| `verify/audit-db/07_verify_stack.log` | Keluaran `verify_stack.py` (52 PASS / 0 FAIL / 1 SKIP) |
| `verify/audit-db/08_snapshot.txt` | Snapshot transaksional isi tabel + komposisi status + daftar sesi |
| `verify/audit-db/09_drift.log` | `alembic check` pada DB demo dan DB baru |
| `verify/audit-db/run_checks.py` | Skrip pemeriksaan (read-only), dapat dijalankan ulang |
| `verify/verify-out-invariants/report-20261026-214103.md` | Laporan gate invarian |

Reproduksi:

```bash
# 1) pemeriksaan integritas (read-only)
python verify/audit-db/run_checks.py

# 2) gate invarian
python "$SKILLS/software-development/fullstack-verification/scripts/verify_stack.py" \
       verify/invariants.spec.json

# 3) drift
docker exec -w /app mealchain-backend alembic check

# 4) uji migrasi dari nol (database terpisah, tidak menyentuh DB demo)
docker exec mealchain-postgres psql -U mealchain -d postgres -c "CREATE DATABASE audit_schema"
docker exec -e DATABASE_URL='postgresql+asyncpg://...@postgres:5432/audit_schema' \
       -w /app mealchain-backend alembic upgrade head
docker exec -w /app mealchain-backend alembic check
docker exec mealchain-postgres psql -U mealchain -d postgres -c "DROP DATABASE audit_schema"
```

---

*Audit ini membaca, tidak mengubah. Semua angka dapat dipertanggungjawabkan ke query pada `verify/audit-db/`; yang tidak diperiksa dinyatakan pada §9, bukan diasumsikan lulus.*
