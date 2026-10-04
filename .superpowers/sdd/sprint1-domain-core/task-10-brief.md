# Task 10 Brief — Seed Sintetis Deterministik + Loader Idempotent (Sprint 1 MealChain)

## Mode eksekusi
Kamu IMPLEMENTER. Ada seed JSON lama SALAH di working tree (data/seed/sprint1_seed.json) —
TDD tetap berlaku: tulis/ubah test DULU untuk perilaku yang belum ada, jalankan RED, baru
implementasi minimal. Kode seed module (`backend/app/seed/`) BELUM ADA — mulai dari nol.
File lama boleh di-overwrite karena terbukti salah terhadap kontrak plan.

## Global constraints (BINDING)
- Canonical runtime: container Python 3.12 via `docker compose exec -T backend ...`.
  Host python 3.11 BUKAN acceptance gate.
- TDD: RED (test gagal karena behavior belum ada) → GREEN (implementasi minimal) → REFACTOR.
- LLM tidak boleh dipakai untuk menghitung apa pun; seed murni deterministik.
- `DEMO_MODE=false` default; tidak ada secret baru; JANGAN baca/tulis `.env`.
- Commit per task dengan message yang ditentukan.

## Seed contract (BINDING — dari plan Task 10)
- TEPAT 10 lokasi: Jakarta, Bogor, Cianjur, Bandung, Semarang, Yogyakarta, Surabaya, Malang,
  Palembang, Medan. (JSON lama punya Depok/Tangerang/Bekasi/Sukabumi/Karawang/Subang → SALAH)
- TEPAT 3 komoditas: telur, ayam, wortel.
- Shelf life: telur 28 hari, ayam 5 hari, wortel 21 hari. (JSON lama wortel=30 → SALAH)
- Angka terkunci (jangan berubah): Cianjur telur 1400/500; Jakarta 300/1000;
  Bogor 800/300; referensi harga telur 26,500; Supplier A 26,200; B 27,000; C 32,000.
- Minimal 7 demand observations untuk pasangan yang dipakai forecast.
- Batch PASS Cianjur dan Bogor → freshness >= 0.85; band verify 0.60<=x<0.85; fail <0.60;
  ada batch dengan temperature excursion → safety FAIL.
- Supplier A/B/C dipersist sebagai price_signals dengan source unik per supplier
  ('supplier_A'/'supplier_B'/'supplier_C') — Schema price_signals tidak punya supplier_id.
- Determinism: `build_seed_rows(reference_time: datetime)` WAJIB menerima waktu eksplisit.
- Idempotency: UUID5 dari namespace proyek + natural key (atau lookup+update deterministik).
  Dua load dengan reference time sama → jumlah dan isi identik; TIDAK menambah row
  time-series. Tidak ada random di mana pun.
- Loader async membaca /data/seed/sprint1_seed.json + CLI: `python -m app.seed.seed_data
  --reference-time <ISO>`.
- Compose: mount `./data:/data:ro` ke service backend; test compose contract membuktikan
  /data/seed/sprint1_seed.json terlihat dari container TANPA mengubah jumlah 4 service.
- Verify mock material stock + 1 historical confirmed PO tersedia (seed mengisi sap_mock
  material stock dan PO konfirmasi historis).

## Deliverables
- Create: data/seed/sprint1_seed.json (REWRITE lengkap)
- Create: backend/app/seed/__init__.py, backend/app/seed/seed_data.py
- Modify: docker-compose.yml (mount ./data:/data:ro ke backend SAJA)
- Modify: backend/tests/test_compose_contract.py (mount data + tetap 4 service)
- Create: backend/tests/test_seed_data.py (transformer: counts, locked numbers, bands, no random)
- Create: backend/tests/test_seed_load_db.py (DB load idempotent: load 2x → identical counts
  + canonical payload hash; verify locked Cianjur/Jakarta/Bogor values; supplier quotes
  sebagai price_signals; mock stock + PO historis tersedia)
- Modify backend/alembic/env.py atau models import hanya jika diperlukan — jangan sentuh
  migration 001/002.

## Test commands
- Per test: docker compose exec -T backend pytest tests/test_seed_data.py -q (dst.)
- Compose contract: docker compose exec -T backend pytest tests/test_compose_contract.py -q
- DB idempotency: docker compose exec -T backend pytest tests/test_seed_load_db.py -q
- Regression: docker compose exec -T backend pytest -q
- Lint: docker compose exec -T backend ruff check app/seed/ tests/test_seed_data.py tests/test_seed_load_db.py

## Catatan state existing
- DB sudah terisi seed LAMA: locations=26 (10 lama + 14 test-rows TEST-LOC/S-BOUND),
  supply=14, demand=20, batches=5, price_signals=6. Loader idempotent WAJIB menangani
  reseed: upsert by natural key (UUID5), JANGAN duplicate. Row test-rows TIDAK boleh dihapus.
- Model ORM sudah ada: app/models/{locations,commodities,supply_records,demand_records,
  price_signals,batches,sap_mock}.py. Migration 002 sudah ter-apply (head).
- db.py punya create_engine/create_session_maker/get_db. Untuk script seed, buat engine
  dari DATABASE_URL env (default postgresql+asyncpg://mealchain:mealchain_local@postgres:5432/mealchain).
- locations table punya kolom: name unique, region, latitude, longitude.
- supply_records: location_id, commodity_id, quantity_kg, recorded_at, source.
- demand_records: location_id, commodity_id, quantity_kg, needed_by.
- price_signals: location_id, commodity_id, price_per_kg, recorded_at, source.
- batches: code, location_id, commodity_id, supplier_id, quantity_kg, harvested_at,
  shelf_life_days, freshness_score, freshness_status, safety_status, temperature_log (JSONB),
  usable_until, certification, dsb — baca model file untuk kolom persis.
- sap_mock tables: material stock (MaterialNumber, Plant, StorageLocation, Batch, MatlStkQty,
  BaseUnit style) dan purchase orders — baca backend/app/models/sap_mock.py untuk kolom persis.
- docker-compose.yml backend service TIDAK punya mount ./data sekarang — tambahkan
  ` - ./data:/data:ro` di bawah volumes backend.

## Report contract
Tulis laporan lengkap ke .superpowers/sdd/sprint1-domain-core/task-10-report.md:
RED evidence (output per test sebelum implementasi), GREEN evidence, idempotency evidence
(2x load → hash/counts), compose contract evidence, regression output, ruff output.
Return HANYA: status DONE/DONE_WITH_CONCERNS/BLOCKED, commits, one-line test summary,
concerns jika ada.
