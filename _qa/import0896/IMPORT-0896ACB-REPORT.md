# Impor dataset mealchain-0896acb → mealchain-guardian

Tanggal: 2026-10-28 (UTC 09:2x)
Operator: Hermes (otonom, atas instruksi pemilik)
Hasil: **DB kerja `mealchain` sekarang berisi dataset 0896acb pada skema 043 dengan kode guardian HEAD 728328f.**

## Ringkas langkah yang dieksekusi

1. Backup target (043) → `data/backups/pre-import-0896-20261028-1544.dump`.
   Backup sumber → `scratch/source-0896-20261028-1544.dump`.
2. `docker compose stop backend` (postgres tetap hidup), putuskan koneksi.
3. `CREATE DATABASE mealchain_import TEMPLATE template0`.
4. `pg_dump` sumber 039 dengan `--no-owner --no-acl` → `pg_restore --exit-on-error` ke `mealchain_import`
   (`alembic_version` = `039_agent_trace_parent_run_id`).
5. `alembic upgrade head` lewat `docker run` pada DB sementara → 040 → 041 → 042 → 043 tanpa error.
6. Verifikasi gerbang: 24 tabel berjumlah identik dengan sumber, `commodity_policies` = 4,
   `alembic_version` = 1 baris `043_least_privilege_app`, 0 FK yatim, 25 tabel.
7. Swap nama: `mealchain` → `mealchain_lama_20261028`, `mealchain_import` → `mealchain`.
8. Segarkan anchor ledger (`scripts/ledger_anchor.py`) → height 978, generation 18,
   checkpoint baru. Tanpa ini panel Integritas menampilkan `anchor.match=false`.
9. `docker compose start backend` → sehat; sesi demo dibuka ulang TANPA rebuild
   (`demo_session.mulai(kosongkan=False, mode="realtime")`).

## Angka DB kerja setelah impor

| tabel | baris |
|---|---:|
| suppliers | 60 |
| batches | 118 |
| supply_records | 5 240 |
| demand_records | 1 360 |
| price_signals | 5 924 |
| menu_plans | 660 |
| road_routes | 54 |
| decisions | 39 |
| decision_evidence | 57 |
| approvals | 24 |
| agent_traces | 133 |
| ledger_blocks | 978 |
| sap_mock_purchase_orders | 16 |
| sap_mock_material_stock | 40 |
| supplier_exclusions | 2 |
| batch_receipts | 1 |
| commodity_policies | 4 (dibuat migrasi 041) |
| users | 17 |

## Bukti bahwa data bisa dipanggil & dipakai

- **Cakupan endpoint**: `api-coverage-after.json` — 50 endpoint × 4 peran = 200 panggilan:
  187×200, 13×403 (RBAC/cakupan, sesuai harapan), 0 error. 23/24 tabel domain punya
  pembaca HTTP yang terbukti 200; satu-satunya tanpa rute baca: `sap_mock_material_stock`
  (celah lama, bukan akibat impor).
- **Mesin rekomendasi**: `/balance/analyze` mengembalikan kandidat nyata
  (beras 61 kandidat/24 tertahan; telur 16/8) pada jangkar sesi aktif.
- **Agent**: `POST /demo/agent/run` membuat keputusan + 9 jejak agen
  (supply, demand, freshness, logistics, price, safety, supervisor, verifier, evidence).
- **Rantai ledger**: `/ledger/verify` → `valid=true`, 978 blok, `anchor.match=true`,
  0 blok yatim, `linked_ratio=1.0`.
- **UI (browser, sesi SPPG Head)**: Recommendation Feed 16 kartu/10 perlu tindakan,
  pemasok impor tampil (CV Berkah Telur Bekasi, UD Cibinong Telur Berkah, dst),
  Agent Log menampilkan run 9 agen, KPI Simulasi menampilkan angka saat scope diarahkan
  ke sesi pemilik dataset.

## Hasil tes backend (2179 tes terkumpul)

Run penuh pada klon DB: **13 gagal / 2135 lulus / 32 skip** (18m01s).
Kegagalan itu diuji ulang pada klon yang setara DB kerja (ACL utuh + sesi aktif):

| tes | status pada klon setara | sebab |
|---|---|---|
| test_least_privilege_app_role (2), test_ledger_immutability (1) | **lulus** | klon pertama dibuat `--no-acl` sehingga GRANT hilang |
| test_api_decision_intelligence (2) | **lulus** | klon pertama tanpa sesi demo aktif |
| test_po_invoice_commercial (1), test_receipt_accepted_value (2) | **lulus** | — |
| test_agent_verifier_independence::test_ledger_belum_ada_aksi_tidak_menandai | gagal | dataset |
| test_demo_cases_procurement_binding::..._resolve_binding_dan_safety | gagal | dataset |
| test_demo_template_provenance_ledger::test_hapus_kasus_demo_menaikkan_generasi_ledger | gagal | dataset |
| test_supplier_procurement_eval (2) | gagal | dataset |

Lima kegagalan tersisa adalah tes yang memaku bentuk template guardian sendiri
(kasus demo, batch acuan kasus, pemasok telur Jakarta, generasi ledger dari penyemai sendiri).
Dataset 0896 dibuat oleh penyemai yang berbeda, jadi baris yang dicari tes itu tidak ada
atau tidak layak. Bukan kerusakan data, tapi ekspektasi tes yang perlu disesuaikan bila
dataset impor ini menjadi tetap.

## Catatan operasional (penting)

1. **Jangan tekan "Siapkan data demo" / `POST /demo/session/start`.** Endpoint itu
   memanggil `mulai_dengan_template` → `build_into(purge=True)` dan **mengganti seluruh
   dataset impor** dengan template guardian sendiri. Sesi kerja saat ini dibuka tanpa rebuild.
2. **Sesi sentinel `ce7a0000-…-0001` (cetakan) TIDAK boleh diaktifkan** —
   tes `test_cetakan_sesi_tidak_pernah_aktif` menjaganya. Sempat dicoba untuk membuat
   KPI Simulasi terisi, lalu dikembalikan ke `expired`/`cetakan`.
   Akibatnya KPI "Simulasi" untuk sesi aktif baru kosong (perilaku lama: baris dataset
   ditandai sesi cetakan, bukan sesi aktif). Angka KPI tersedia bila scope diarahkan
   ke sesi pemilik dataset — terbukti lewat API.
3. **Rantai ledger target lama (5 129 blok, generation 62..405) tidak ikut**.
   DB lama disimpan utuh sebagai `mealchain_lama_20261028` + dump.
4. Backend uji/jalan butuh `PYTHONPATH=/app:/` (bukan `/app:/agent`) agar `import agent` jalan;
   paket `agent` di-mount di `/agent` sehingga root `/` yang harus ada di path.
