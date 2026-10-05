# Verifikasi Sprint 1 — Business Logic Inti + Data

> **ADDENDUM revisi Roy 2026-10-03 (setelah review Sprint 1):**
> 1. **Desain quote supplier (revisi kedua — FINAL):** source kembali ke dua nilai
>    generik `'pihps_reference' | 'supplier_quote'`; identitas supplier ada di
>    **kolom terpisah `price_signals.supplier_id`** (FK → suppliers.id) — BUKAN
>    dienkode ke string source (`supplier_A` dll ditiadakan). Tidak terbatas sampai
>    C: seed mendemokan **Supplier D** (25.400/kg) membuktikan skalabilitas.
>    Contoh payload: `{"source": "supplier_quote", "supplier": "Supplier A", "price": 12000}`.
>    Diimplementasi via **migration 004** (`004_supplier_quote_design`, menimpa desain
>    interim 003 yang dicabut): kolom supplier_id + FK + index, kontrak source dua
>    nilai, dan consistency check (`pihps_reference` ↔ supplier_id NULL;
>    `supplier_quote` ↔ supplier_id terisi). Schema.md §price_signals diperbarui.
>    Migration interim 003 di-downgrade dan dihapus dari repo.
> 2. **Role** — Schema.md §users diperbarui ke 3 role final
>    (`sppg_head`/`sppg_nutritionist`/`bgn_monitor`); migration 001 sudah benar sejak
>    awal; sisa wording role lama di docs dibersihkan.
> 3. **Harga regional realistis** — seed memuat referensi PIHPS-style untuk
>    **10 lokasi × 3 komoditas (30 titik harga)** dalam batas realistis Indonesia 2026
>    (telur 24–34 rb, ayam 32–46 rb, wortel 14–30 rb per kg), dengan kesenjangan antar
>    wilayah ≥5% per komoditas (rasio max/min; Medan/Jakarta termahal, Cianjur/Bandung
>    termurah — sesuai narasi root cause IDEA.md). Angka terkunci demo tetap utuh:
>    Cianjur telur ref 26.500, quote A 26.200 / B 27.000 / C 32.000 / D 25.400.
>    Bukti: `tests/test_price_regional_seed.py`, `tests/test_supplier_quote_design.py`,
>    `tests/test_supplier_quote_db.py`.
>    Hasil verifikasi ulang: **169 passed + 1 skipped**, ruff clean, seed idempoten 2×,
>    roundtrip migration OK, endpoint smoke OK.
>
> **REVISI KETIGA Roy 2026-10-03 — supplier lokal di SEMUA kota:**
> pihps_reference tetap sebagai acuan pasar per kota (benchmark `/price/deviation`),
> dan setiap kota kini punya **supplier lokal** dengan quote format
> `{"source": "supplier_quote", "supplier": "<nama wilayah>", "price_per_kg": ...}` —
> 14 supplier total, quote `supplier_quote × 14`, semua 10 kota ter-cover
> (Cianjur 4 quote terkunci; kota lain 1–2 supplier dengan komoditas utamanya).
> Bukti: `tests/test_supplier_city_coverage.py` (5 test).
> Hasil verifikasi: **174 passed**, ruff clean, seed idempoten 2×.
>
> **CATATAN DESAIN — disiplin pemakaian dua lapis harga (berlaku Sprint 2+):**
> Dua lapis ini adalah prasyarat Event 2 PRD ("deviasi harga pemasok vs referensi
> pasar") dan narasi root cause IDEA.md (kesenjangan antar wilayah). Nilainya hanya
> bertahan jika dipakai dengan disiplin:
>
> | Sinyal | Dipakai untuk | DILARANG untuk |
> |---|---|---|
> | `pihps_reference` | benchmark deviasi (`/price/deviation`), konteks gap antar kota, peluang arbitrase lintas wilayah | harga beli / kalkulasi PO |
> | `supplier_quote` | purchase cost, Safe Delivered Cost (Sprint 2), PO | dianggap "harga pasar kebenaran" |
>
> Anti-pattern yang harus dihindari: (1) menghitung biaya pembelian dari harga acuan —
> aritmetika Skill.md §8 memakai harga supplier (Rp25.000/kg × 500); (2) memvalidasi
> quote terhadap quote lain — deviasi hanya bermakna terhadap acuan pasar kotanya.
> Properti demo yang dijaga: semua quote kota lain deviasi ±0,8–2,3% (normal),
> Supplier C +20,8% satu-satunya anomalous+flagged — ambang 5%/15% tetap bermakna.

Tanggal verifikasi: 2026-10-03 (WIB)
Branch: `feature/sprint1-domain-core`
Runtime canonical: container Python 3.12 (docker compose), bukan host Python 3.11.
Semua hasil di bawah adalah output nyata perintah Task 13 — bukan hasil rekonstruksi.

## Fresh verification commands (urutan plan)

| # | Perintah | Hasil | Exit |
|---|---|---|---|
| 1 | `docker compose exec -T backend alembic upgrade head` | `002_operational_data (head)`, tanpa pending | 0 |
| 2 | `python -m app.seed.seed_data --reference-time 2026-10-01T12:00:00+00:00` (load #1) | `Seed selesai (idempoten). Row baru: {}` | 0 |
| 3 | `python -m app.seed.seed_data --reference-time 2026-10-01T12:00:00+00:00` (load #2) | identik — tidak ada row baru | 0 |
| 4 | `docker compose exec -T backend pytest -q` | **158 passed**, 1 warning (deprecation starlette/anyio — eksternal) | 0 |
| 5 | `docker compose exec -T backend ruff check .` | All checks passed | 0 |
| 6 | `docker compose exec -T frontend npm run test` | **BLOCKER**: script `test` tidak ada di package.json frontend (hanya dev/build/start/lint) | 1 |
| 7 | `docker compose exec -T frontend npm run lint` | `✔ No ESLint warnings or errors` | 0 |
| 8 | `docker compose ps` | 4 service Up; postgres healthy | 0 |

## Seed idempotency & dataset 10×3

Counts setelah dua kali load (identik):

```
locations=10  commodities=3  supply=30  demand=168
batches=6     prices=4       stock=6    po=1
```

- 10 lokasi terkunci: Jakarta, Bogor, Cianjur, Bandung, Semarang, Yogyakarta, Surabaya,
  Malang, Palembang, Medan.
- 3 komoditas: telur (28 hr), ayam (5 hr), wortel (21 hr — konfigurasi demo, bukan kolom DB).
- Angka terkunci terverifikasi test: Cianjur telur 1400/500; Jakarta 300/1000; Bogor 800/300;
  referensi 26.500; quote supplier 26.200 / 27.000 / 32.000.

## Bukti hard constraint (test: tests/test_sprint1_acceptance.py, 12 passed)

| Verifikasi | Bukti |
|---|---|
| Freshness boundaries | 0.85→pass; 0.849999→needs_verification; 0.60→needs_verification; 0.599999→fail |
| Safety hard constraint | batch excursion Surabaya → FAIL via API; tidak dapat diubah oleh payload lain; DB lowercase `fail` |
| Price anomaly | Supplier C 32.000 vs ref 26.500 → `anomalous`, `flagged=true`; exact 5%/15% boundary di test_price.py (Decimal) |
| Logistics boundary | Cianjur–Jakarta 120 km / 150 menit; window 150 → feasible; 149 → infeasible |
| Capacity constraint | available==required → sufficient; available<required → gagal |
| Delivery-window constraint | estimated==window → True; over → False |
| Forecast fallback | flat [100,100,100] × 7 hari → 700 kg; method selalu `statistical_fallback` |
| Mock SAP header | `X-Data-Source: MOCK` pada /supply mock_sap + mock-sap service; kontrak 5 method (Skill.md §6) |
| Endpoint Sprint 1 | /supply, /demand, /demand/forecast, /price, /price/deviation, /freshness/evaluate, /safety/evaluate, /logistics/estimate — semua 200 terhadap Postgres migration+seed |
| Docker health | 4 service Up, postgres healthy |

## Migration

- Roundtrip `upgrade head → downgrade 001_master_data → upgrade head` dijalankan pada
  database test terisolasi `mealchain_mig_test` (sudah di-drop) — semua sukses.
- `decisions` belum ada: `sap_mock_purchase_orders.decision_id` UUID nullable tanpa FK
  (FK menyusul Sprint 2) — sesuai plan Task 8.

## Keputusan kontrak (rulings) selama eksekusi

1. **price_signals.source** — plan minta `supplier_A/B/C`, Schema.md hanya
   `pihps_reference|supplier_quote`. Keputusan Roy (2026-10-03): pakai kontrak Schema;
   3 quote dibedakan nilai harga (26.200/27.000/32.000). Plan diperlonggar.
2. **Schema.md §users masih role lama** (sppg_staff/dinas_admin) — konflik dengan locked
   3 roles. DILAPORKAN, tidak diubah (aturan Task 0).
3. **freshness_status bukan kolom DB** — Schema.md batches hanya punya freshness_score +
   usable_until; status diturunkan deterministik via classify_freshness.
4. **shelf life = konfigurasi demo** (config.py), bukan kolom commodities (sesuai Schema.md).
5. **docker-compose.yml di-disk korup sejak restore 40415ce** (3 service, port 5432,
   mock-sap hilang) — dibetulkan sebagai bagian Task 10 (compose contract TDD).
6. **Delegation subagent tidak reliable** (502 provider berulang, 3 subagent mati) —
   verifikasi dilakukan parent sesuai kontrak plan ("laporan subagent bukan bukti final").

## Blocker

- `npm run test` frontend: script tidak tersedia di Sprint 0 frontend shell.
  Regresi frontend saat ini hanya ter-cover `npm run lint` (bersih).
  Rekomendasi: tambahkan test runner (vitest) di Sprint 2.
  **[Diselesaikan 2026-10-05, Task 0 Sprint 2 — lihat addendum di bawah.]**

## Deviasi terhadap plan

- Commit Task 9/10/11/12 dilakukan parent (bukan subagent implementer) karena kegagalan
  infrastruktur delegasi; disiplin TDD RED→GREEN tetap ditegakkan per task.
- Review spec-compliance Task 1–7 dilakukan parent (reviewer subagent mati 502).

## ADDENDUM Task 0 Sprint 2 (2026-10-05) — rekonsiliasi kontrak + frontend runner

Keputusan Roy 2026-10-05 (disetujui eksplisit, dicatat sebelum eksekusi):

1. **`decisions.expires_at TIMESTAMPTZ NOT NULL`** — ditambahkan ke `docs/Schema.md`
   sebagai kontrak. Aturan validitas: `now < expires_at` valid; `now >= expires_at`
   expired; keputusan expired tetap disimpan untuk audit, tidak dihapus, tidak
   dihidupkan ulang oleh approval. Implementasi kolom menyusul di migration
   006 (Task 8 Sprint 2).
2. **`price_signals.seed_key`** — kolom drift yang hanya ada di database live
   (tidak ada di migration 002/004, ORM, seed loader, API, tests, docs).
   Dihapus via migration `005_reconcile_sprint1_schema` (idempoten:
   `DROP COLUMN IF EXISTS`; downgrade sengaja no-op — kolom bukan kontrak).
   Idempotensi seed tetap UUID5 natural key di loader. Nol baris bisnis terhapus:
   44 price signals (30 pihps + 14 quote), 14 suppliers, 10 kota quote — terverifikasi
   test `backend/tests/test_sprint1_contract_reconciliation.py` (RED terbukti:
   kolom ada → migration → GREEN 3/3).

Perbaikan tambahan saat rekonsiliasi:

3. **Time-bomb test diperbaiki** — `test_freshness_evaluate_pass_band_persists`
   memakai batch seed dengan `harvested_at` tetap; decay mengikuti jam nyata
   sehingga skor meluruh 0.85+ → 0.83 per 2026-10-05 (mengikuti pola flaky yang
   sama dengan ruling 2026-10-03). Kini test membuat batch sendiri
   (`harvested_at = now() - 30 menit`, quantity 499.99 anti-tabrakan selector),
   self-cleaning. Suite penuh: **177 passed**.
4. **Frontend test runner ditambahkan** — blocker di atas selesai: script
   `test: vitest run`, devDependency `vitest@2.1.9`, `vitest.config.ts`
   (jsx automatic — tsconfig Next "preserve"), smoke test
   `frontend/tests/smoke.test.ts` (render shell → judul). RED terbukti
   (`Missing script: "test"`) sebelum install. `npm run test` 1 passed,
   `npm run lint` bersih, lockfile ter-generate via `npm install` di container.

Catatan proses: implementer subagent Task 0 mati untuk kelima kalinya
(HTTP 502 provider + max_iterations) tanpa menulis file; eksekusi dilakukan
parent dengan TDD ketat sesuai kontrak plan ("delegation failure does not
block safe parent execution; deviation must be recorded").

## Status S1-01..S1-11

| ID | Status | Bukti |
|---|---|---|
| S1-01 | Done | counts 10×3 + test_seed_data/test_seed_load_db |
| S1-02 | Done | test_api_supply_demand.py (13 test) |
| S1-03 | Done | test_api_supply_demand.py |
| S1-04 | Done | test_api_domain_tools.py::test_freshness_* |
| S1-05 | Done | test_api_domain_tools.py::test_safety_* |
| S1-06 | Done | test_api_domain_tools.py::test_price_* |
| S1-07 | Done | test_api_domain_tools.py::test_logistics_* |
| S1-08 | Done | test_constraints/test_safety/test_freshness/test_sprint1_acceptance |
| S1-09 | Done | sap_mock tables terisi (stock=6, po=1 confirmed) + kontrak test |
| S1-10 | Done | /demand/forecast + statistical_fallback |
| S1-11 | Done | usable_until pada kontrak evaluate + persistence |

Sprint 1 STOP di sini — Sprint 2 tidak dimulai otomatis (menunggu review Roy).
