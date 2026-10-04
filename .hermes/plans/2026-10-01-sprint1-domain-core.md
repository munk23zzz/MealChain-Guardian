# Sprint 1 — Business Logic Inti + Data Implementation Plan (Rewrite v2)

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` task-by-task. Every production-code task follows strict RED → GREEN → REFACTOR and must pass spec-compliance review before code-quality review.

**Goal:** Menyelesaikan seluruh Definition of Done Sprint 1: data sintetis 10 lokasi × 3 komoditas, domain tools deterministik untuk freshness/safety/price/logistics/forecast, adapter Mock SAP, tabel operasional, dan endpoint Sprint 1 yang terhubung ke PostgreSQL.

**Architecture:** Fungsi hitung hidup di `backend/app/core/*`, tidak mengimpor FastAPI/SQLAlchemy dan tidak memakai LLM. Endpoint FastAPI hanya memvalidasi input, mengambil/menyimpan data, lalu memanggil core. PostgreSQL menjadi sumber data operasional; Mock SAP mengakses kontrak provider yang sama dan selalu mengidentifikasi data sebagai simulasi.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 16, pytest, Ruff, Docker Compose.

**Spec:** `IDEA.md`; `Rules.md`; `workflows.md`; `Roadmap.md` Sprint 1; `TODO.md` S1-01..S1-11; `docs/PRD.md`; `docs/Architecture.md`; `docs/Schema.md`; `docs/Skill.md`; keputusan Roy 2026-10-01.

## Global Constraints

1. LLM tidak pernah menghitung freshness, safety, price deviation, logistics feasibility, atau forecast statistik.
2. Safety `fail` dan freshness `< 0.60` menggugurkan batch secara deterministik.
3. Ambang freshness final:
   - `score >= 0.85` → `pass`;
   - `0.60 <= score < 0.85` → `needs_verification`;
   - `score < 0.60` → `fail` / tidak layak.
4. Freshness dinilai pada kondisi stok yang tiba/berada di SPPG penerima. Umur dihitung dari `harvested_at`; riwayat suhu mencakup supplier → transit → gudang SPPG. Ambang final: pass ≥0.85, verify 0.60–<0.85, fail <0.60 (revisi Roy).
5. Ambang harga final: deviasi absolut `>= 5%` = `elevated`; `>= 15%` = `anomalous` dan `flagged=true`.
6. Model role tetap tiga: `sppg_head`, `sppg_nutritionist`, `bgn_monitor`. Sprint ini tidak membangun auth/RBAC.
7. Mock SAP wajib berlabel `X-Data-Source: MOCK`; tidak ada klaim SAP ERP nyata.
8. `DEMO_MODE=false` secara default. Tidak ada secret baru dan tidak membaca/menulis `.env` dalam implementasi plan ini.
9. `Architecture.md` dan `Schema.md` tidak diubah secara struktural tanpa persetujuan Roy. Sinkronisasi wording/threshold yang sudah diputuskan Roy diperbolehkan dan dicatat eksplisit.
10. Status `TODO.md` diubah menjadi `In Progress` saat task pertama mulai dan menjadi `Done` hanya sesudah bukti verifikasi task tersedia.
11. Canonical Python runtime untuk implementasi adalah container Python 3.12. Host `.venv` masih Python 3.11 dan bukan acceptance gate.
12. Plan ini hanya Sprint 1. Endpoint `/cost/safe-delivered`, `/balance/*`, auth, frontend, approval, evidence fusion, reliability update, dan rehearsal Event 1–3 tetap di sprint masing-masing.

## Keputusan Domain yang Dikunci

### Freshness

```text
base_score = clamp(1 - age_seconds / shelf_life_seconds, 0, 1)
outside_fraction = minutes_outside_safe_range / observed_minutes
freshness_score = clamp(base_score - 0.3 * outside_fraction, 0, 1)
usable_until = harvested_at + shelf_life * freshness_score
```

- Shelf life konfigurasi demo: telur 28 **hari**, ayam 5 **hari**, wortel 21 **hari**.
- Interval suhu memakai sample sebelumnya untuk rentang `[sample_i.timestamp, sample_i+1.timestamp)`.
- Sample diurutkan berdasarkan timestamp. Timestamp duplikat, timestamp tak valid, nilai suhu non-numerik, atau kurang dari dua sample membuat kualitas log tidak lengkap; safety menjadi `needs_verification`, bukan PASS diam-diam.
- Freshness score tetap dapat dihitung dari umur ketika log tidak lengkap, tetapi API tidak boleh menyamarkan status safety yang membutuhkan verifikasi.

### Safety

- `excursion_minutes >= 30` → `fail`.
- `0 < excursion_minutes < 30` → `needs_verification`.
- `excursion_minutes == 0` dan log lengkap → `pass`.
- Log kosong/rusak/tidak cukup → `needs_verification`.

### Price

```text
deviation_pct = abs(supplier_price - reference_price) / reference_price * 100
```

### Logistics

- Matriks jarak sintetis deterministik untuk seluruh pasangan 10 lokasi.
- Cianjur → Jakarta = 120 km.
- `estimated_time_min = distance_km / 60 * 60 + 30`.
- `estimated_time_min <= delivery_window_min` dianggap feasible.

### Forecast

- Weighted moving average tiga observasi terbaru, bobot terbaru→terlama `(0.5, 0.3, 0.2)`.
- Bobot dinormalisasi jika histori hanya 1–2 observasi; flat series 100 kg/hari menghasilkan 700 kg untuk horizon 7 hari.
- Response selalu membawa `method="statistical_fallback"`.

## Scope yang Sengaja Ditunda

Keputusan price threshold dan penalti Safe Delivered Cost sudah disetujui Roy, tetapi implementasi Safe Delivered Cost adalah Sprint 2 (`S2-01`). Formula yang disetujui tetap dicatat untuk plan Sprint 2: expected loss `0.2 × (1 − freshness)`, freshness-risk trigger `0.60`, faktor `0.50`, safety-risk penalty `10%`, dan safety FAIL tidak pernah dihitung cost. Candidate Score/balancing juga tetap Sprint 2. Contoh `freshness=0.75` di `docs/Skill.md` §8 hanya contoh aritmetika cost; dengan ambang baru batch tersebut `needs_verification`, bukan kandidat PASS.

---

## Task 0: Sinkronkan Kontrak Dokumentasi dan Baseline Eksekusi

**Objective:** Menghilangkan drift yang dapat membuat implementer mengikuti threshold/scope usang.

**Files:**
- Modify: `docs/Skill.md:60-68,93,161-174`
- Modify: `docs/Architecture.md:182,395-402` hanya bila wording aktif masih usang; jangan redesign.
- Modify: `Roadmap.md:15-16` untuk mencerminkan bukti Sprint 0 yang sudah `Done` di `TODO.md`.
- Modify: `TODO.md:24-38` saat status task berubah.

**Required edits:**
- `docs/Skill.md` hard constraint dan threshold menjadi 0.85/0.60/<0.60.
- Kontrak `freshness.evaluate` menambahkan `usable_until` karena S1-11 dan Schema sudah mewajibkan.
- Contoh §8 diberi catatan bahwa freshness 0.75 berada di band `needs_verification`; angka biaya tetap contoh matematika untuk Sprint 2.
- Diagram Architecture mengganti “SPPG/Dinas” dengan approver SPPG (`sppg_head`/`sppg_nutritionist`); `bgn_monitor` tetap read-only.
- Jangan mengubah formula/schema lain.

- [ ] **Step 1 — Baseline:** jalankan `git status --short`, `git branch --show-current`, dan `docker compose ps`.
- [ ] **Step 2 — Status:** buat/switch ke branch `feature/sprint1-domain-core`; set S1-01..S1-11 yang dikerjakan menjadi `In Progress`, assignee `Hermes`.
- [ ] **Step 3 — Edit docs:** terapkan empat sinkronisasi di atas.
- [ ] **Step 4 — Verify:** cari wording/angka aktif usang dengan `search_files` untuk `0.4`, `>= 0.6`, `SPPG/Dinas`, `2 role`, `sppg_staff`, `dinas_admin`; setiap hit harus historis atau diperbaiki.
- [ ] **Step 5 — Commit:** `docs: sinkron kontrak Sprint 1 dan ambang freshness final`.

## Task 1: Utility Time-Series Suhu

**Objective:** Membuat satu parser interval suhu yang dipakai freshness dan safety agar kedua engine tidak menghitung durasi dengan aturan berbeda.

**Files:**
- Create: `backend/app/core/temperature.py`
- Create: `backend/tests/test_temperature.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class TemperatureSummary:
    observed_minutes: float
    outside_minutes: float
    complete: bool
    issues: tuple[str, ...]

summarize_temperature_log(
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
) -> TemperatureSummary
```

**Tracer bullets:**

1. Dua sample valid dan in-range → observed minutes benar, outside=0, complete=True.
2. Sample pertama out-of-range selama interval ke sample kedua → outside minutes mengikuti sample pertama.
3. Input tidak terurut → hasil sama setelah sorting.
4. Duplikat timestamp, malformed entry, atau <2 sample → `complete=False` dan issue eksplisit; tidak crash.
5. `safe_min_c > safe_max_c` → `ValueError`.

Untuk setiap tracer bullet:
- [ ] Tulis satu test perilaku.
- [ ] Jalankan test spesifik: `docker compose exec -T backend pytest tests/test_temperature.py::<test_name> -v`; expected FAIL karena behavior belum ada, bukan syntax/import setup.
- [ ] Implementasi minimal.
- [ ] Jalankan test spesifik hingga PASS.
- [ ] Jalankan `docker compose exec -T backend pytest tests/test_temperature.py -q`.
- [ ] Refactor hanya saat hijau; ulangi suite.

- [ ] **Commit:** `feat: parser interval suhu deterministik`.

## Task 2: Freshness Engine dengan Ambang Final

**Objective:** Menghitung freshness di titik SPPG, mengklasifikasikan boundary final, dan menghasilkan `usable_until`.

**Files:**
- Create: `backend/app/core/freshness.py`
- Create: `backend/tests/test_freshness.py`

**Interfaces:**

```python
PASS_THRESHOLD = 0.85
VERIFY_THRESHOLD = 0.60
TEMP_PENALTY_WEIGHT = 0.30

compute_freshness_score(
    harvested_at: datetime,
    as_of: datetime,
    shelf_life_days: float,
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
) -> float

classify_freshness(
    score: float,
    pass_threshold: float = PASS_THRESHOLD,
    verify_threshold: float = VERIFY_THRESHOLD,
) -> Literal["pass", "needs_verification", "fail"]

compute_usable_until(
    harvested_at: datetime,
    shelf_life_days: float,
    score: float,
) -> datetime
```

**Mandatory test matrix:**

| Behavior | Input | Expected |
|---|---|---|
| fresh clean chain | age 2.8/28 hari, complete in-range log | score 0.90 |
| excursion penalty | base 0.90, 50% observed time outside | score 0.75 |
| expired | age > shelf life | 0.0 |
| future harvest | `harvested_at > as_of` | `ValueError` |
| invalid shelf life | 0 atau negatif | `ValueError` |
| pass boundary | 0.85 | `pass` |
| below pass | 0.849999 | `needs_verification` |
| verify boundary | 0.60 | `needs_verification` |
| below verify | 0.599999 | `fail` |
| invalid score | -0.01 / 1.01 / NaN | `ValueError` |
| usable until | known harvest, shelf life, score | exact timezone-aware datetime |

Untuk setiap behavior, lakukan RED spesifik → GREEN minimal → targeted PASS. Setelah seluruh tracer:

- [ ] Jalankan `docker compose exec -T backend pytest tests/test_temperature.py tests/test_freshness.py -q`.
- [ ] Jalankan Ruff pada dua file produksi/test.
- [ ] **Commit:** `feat: freshness engine ambang 0.85 dan 0.60`.

## Task 3: Safety Engine sebagai Hard Constraint

**Objective:** Menentukan PASS/FAIL/NEEDS_VERIFICATION tanpa jalur override.

**Files:**
- Create: `backend/app/core/safety.py`
- Create: `backend/tests/test_safety.py`

**Interface:**

```python
evaluate_safety(
    temperature_log: list[dict],
    safe_min_c: float,
    safe_max_c: float,
    max_excursion_minutes: float = 30,
) -> dict[str, object]
# keys: safety_status, reasons, excursion_minutes
```

**Mandatory test matrix:** clean complete log PASS; excursion 29.999 NEEDS_VERIFICATION; exactly 30 FAIL; >30 FAIL; malformed/empty/<2 samples NEEDS_VERIFICATION; invalid range/threshold ValueError; deterministic repeated call.

- [ ] Jalankan satu RED/GREEN cycle per behavior.
- [ ] Regression: `docker compose exec -T backend pytest tests/test_temperature.py tests/test_freshness.py tests/test_safety.py -q`.
- [ ] Tambahkan assertion bahwa tidak ada status di luar tiga nilai kontrak.
- [ ] **Commit:** `feat: safety hard constraint berbasis excursion`.

## Task 4: Price Deviation

**Objective:** Mengunci ambang harga yang disetujui Roy.

**Files:**
- Create: `backend/app/core/price.py`
- Create: `backend/tests/test_price.py`

**Interface:**

```python
price_deviation(
    supplier_price: Decimal | int | str,
    reference_price: Decimal | int | str,
    elevated_pct: Decimal = Decimal("5"),
    anomalous_pct: Decimal = Decimal("15"),
) -> dict[str, object]
```

**Mandatory tests:** reference exact 0%; Supplier A 26,200 normal; Supplier B 27,000 normal; Supplier C 32,000 anomalous/flagged; exact 5% elevated; exact 15% anomalous/flagged; invalid/non-finite/zero input rejected. Gunakan `Decimal`, bukan float, untuk boundary.

- [ ] RED/GREEN per behavior.
- [ ] Regression core suite.
- [ ] **Commit:** `feat: price deviation ambang 5 dan 15 persen`.

## Task 5: Logistics Matrix dan Feasibility

**Objective:** Menyediakan estimasi deterministik untuk seluruh pasangan lokasi seed.

**Files:**
- Create: `backend/app/core/logistics.py`
- Create: `backend/tests/test_logistics.py`

**Interfaces:**

```python
LOCATIONS: tuple[str, ...]  # tepat 10 lokasi seed
DISTANCE_KM: dict[frozenset[str], int]

estimate_logistics(
    source: str,
    target: str,
    quantity_kg: float,
    delivery_window_min: float | None = None,
    speed_kmh: float = 60,
    fixed_handling_min: float = 30,
) -> dict[str, int | float | bool]
```

**Mandatory tests:** 45 pasangan unik tersedia (`10 choose 2`); tidak ada key duplikat; Cianjur–Jakarta 120 km/150 menit; matriks simetris; same-location 0 km; exact boundary feasible; unknown location, quantity<=0, speed<=0, window<0 rejected.

- [ ] RED/GREEN per behavior.
- [ ] Regression core suite.
- [ ] **Commit:** `feat: matriks jarak lengkap dan logistics feasibility`.

## Task 6: Constraint Primitives untuk Capacity dan Delivery Window

**Objective:** Memenuhi S1-08 tanpa menarik balancing/recommendation Sprint 2 ke Sprint 1.

**Files:**
- Create: `backend/app/core/constraints.py`
- Create: `backend/tests/test_constraints.py`

**Interfaces:**

```python
check_capacity(available_kg: float, required_kg: float) -> dict[str, float | bool]
check_delivery_window(estimated_time_min: float, delivery_window_min: float) -> bool
is_batch_eligible(freshness_status: str, safety_status: str) -> bool
```

**Mandatory tests:** available==required lolos; available<required gagal; nilai negatif/non-finite ditolak; estimated==window lolos; estimated>window gagal; freshness `fail` atau safety `fail` membuat ineligible; `needs_verification` bukan PASS otomatis tetapi tetap dapat diteruskan sebagai status review; status tidak dikenal ditolak.

- [ ] RED/GREEN satu behavior per cycle.
- [ ] Regression seluruh core Sprint 1.
- [ ] **Commit:** `feat: constraint primitives capacity dan delivery window`.

## Task 7: Forecast Statistik Fallback

**Objective:** Menyediakan forecast tanpa SAP AI Core sejak Sprint 1.

**Files:**
- Create: `backend/app/core/forecasting_fallback.py`
- Create: `backend/tests/test_forecasting_fallback.py`

**Interface:**

```python
statistical_forecast(
    daily_kg: list[float],
    horizon_days: int = 7,
    weights: tuple[float, ...] = (0.5, 0.3, 0.2),
) -> dict[str, float | str]
```

**Mandatory tests:** flat `[100,100,100]` → 700; `[100,200,300]` memakai 300×0.5 + 200×0.3 + 100×0.2; histori 1–2 item menormalisasi bobot; histori >3 hanya memakai tiga terbaru; confidence 0..1 meningkat dengan histori; empty/negative/non-finite/horizon<=0/bobot invalid rejected; method selalu `statistical_fallback`.

- [ ] RED/GREEN per behavior.
- [ ] Regression seluruh core Sprint 1.
- [ ] **Commit:** `feat: forecast statistik fallback transparan`.

## Task 8: Migration 002 dan ORM Operasional

**Objective:** Menambahkan tabel Schema.md §2 dan §4 tanpa menarik tabel keputusan Sprint 2.

**Files:**
- Modify: `backend/requirements.txt` — tambahkan driver sync PostgreSQL yang dipakai schema tests jika belum tersedia eksplisit.
- Create: `backend/alembic/versions/002_operational_data.py`
- Create: `backend/app/models/supply_records.py`
- Create: `backend/app/models/demand_records.py`
- Create: `backend/app/models/price_signals.py`
- Create: `backend/app/models/batches.py`
- Create: `backend/app/models/sap_mock.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py` agar metadata model baru terdaftar.
- Create: `backend/tests/test_operational_schema.py`

**Schema contract:** persis `docs/Schema.md` §2/§4. Karena `decisions` belum ada, `sap_mock_purchase_orders.decision_id` nullable UUID tanpa FK pada migration 002; FK ditambahkan bersama tabel `decisions` di Sprint 2. Semua tabel memiliki `id` dan `created_at` sesuai header Schema. Buat indeks supply, demand, batches dari §5.

**Test isolation:** setiap test memakai transaction yang di-rollback atau identifier UUID unik. Jangan mengandalkan urutan test dan jangan meninggalkan row dengan natural name tetap.

- [ ] **RED:** test tabel/kolom/check/index belum tersedia; jalankan dan konfirmasi failure expected.
- [ ] Tambahkan dependency lalu rebuild hanya backend dan mock-sap: `docker compose build backend mock-sap`; restart keduanya.
- [ ] **GREEN:** buat migration + ORM, jalankan `docker compose exec -T backend alembic upgrade head`.
- [ ] Verify check constraints: quantity non-negative, price >0, freshness 0..1, safety enum.
- [ ] Verify `alembic downgrade 001_master_data` lalu `upgrade head` pada database test/backup-safe; jangan downgrade database bersama tanpa menjaga data.
- [ ] Regression: `docker compose exec -T backend pytest tests/test_master_data_schema.py tests/test_operational_schema.py -q`.
- [ ] **Commit:** `feat: migration 002 dan model data operasional`.

## Task 9: Kontrak SAPDataProvider dan MockSAPProvider

**Objective:** Memenuhi S1-02/S1-09 dan Architecture adapter pattern; endpoint tidak membaca tabel mock secara sembarang.

**Files:**
- Create: `backend/app/sap_integration/provider_interface.py`
- Create: `backend/app/sap_integration/mock_provider.py`
- Create: `backend/app/sap_integration/aws_mcp_provider.py` (stub eksplisit yang raise `NotImplementedError`, tanpa akses eksternal)
- Create: `backend/app/sap_integration/factory.py`
- Create: `backend/tests/test_sap_integration_contract.py`

**Interface methods:** `get_material_stock`, `get_purchase_orders`, `create_purchase_order`, `get_business_partner`, `get_product_master`. Sprint 1 mengimplementasikan read material stock/purchase orders di mock. `create_purchase_order` tidak dipanggil oleh endpoint Sprint 1 dan tidak boleh auto-execute.

**Mandatory tests:** factory default = mock; response field memakai nama kontrak SAP di Skill.md §6; data source = MOCK; unknown material/plant memberi list kosong, bukan crash; AWS stub tidak pernah dipilih tanpa config eksplisit; setiap kapabilitas switch independen; tidak ada credential nyata.

- [ ] RED/GREEN per contract behavior.
- [ ] Jalankan `docker compose exec -T backend pytest tests/test_sap_integration_contract.py -q`.
- [ ] **Commit:** `feat: kontrak SAP provider dan implementasi mock`.

## Task 10: Seed Sintetis Deterministik dan Loader Idempotent

**Objective:** Memuat data realistis tanpa random dan tanpa duplikasi pada rerun.

**Files:**
- Create: `data/seed/sprint1_seed.json`
- Create: `backend/app/seed/__init__.py`
- Create: `backend/app/seed/seed_data.py`
- Modify: `docker-compose.yml` — mount `./data:/data:ro` ke service backend; jangan copy/menduplikasi seed ke image.
- Modify: `backend/tests/test_compose_contract.py` — buktikan mount data read-only tersedia tanpa mengubah jumlah empat service.
- Create: `backend/tests/test_seed_data.py`
- Create: `backend/tests/test_seed_load_db.py`

**Seed contract:**
- Tepat 10 lokasi: Jakarta, Bogor, Cianjur, Bandung, Semarang, Yogyakarta, Surabaya, Malang, Palembang, Medan.
- Tepat 3 komoditas: telur, ayam, wortel.
- Angka terkunci: Cianjur telur 1400/500; Jakarta 300/1000; Bogor 800/300; referensi 26,500; A 26,200; B 27,000; C 32,000.
- Minimal 7 demand observations untuk pasangan yang dipakai forecast.
- Batch PASS Cianjur dan Bogor dihitung menghasilkan freshness `>=0.85`; batch band verifikasi menghasilkan `0.60<=x<0.85`; batch gagal freshness `<0.60`; batch temperature excursion safety FAIL.
- Semua supplier fiktif. Quote Supplier A/B/C dipersist sebagai `price_signals` dengan `source` unik per supplier (mis. `supplier_A/B/C`) karena Schema `price_signals` tidak memiliki kolom `supplier_id` — jangan mengubah Schema untuk ini.

**Determinism/idempotency:** `build_seed_rows(reference_time: datetime)` wajib menerima waktu eksplisit. Gunakan UUID stabil (UUID5 dari namespace proyek + natural key) atau lookup+update yang deterministik. Dua load dengan reference time sama menghasilkan jumlah dan isi sama; tidak menambah row time-series.

- [ ] RED host-independent di container: exact counts/numbers/threshold bands/no random.
- [ ] GREEN transformer JSON.
- [ ] RED DB load: database belum berisi seed.
- [ ] RED compose contract: `/data/seed/sprint1_seed.json` belum terlihat dari backend container.
- [ ] GREEN compose mount `./data:/data:ro`; recreate backend (bind mount config berubah, image rebuild tidak dibutuhkan untuk langkah ini) dan verifikasi file terlihat.
- [ ] GREEN loader async membaca `/data/seed/sprint1_seed.json` + CLI `python -m app.seed.seed_data --reference-time <ISO>`.
- [ ] Jalankan loader dua kali; query counts dan hash payload canonical harus identik.
- [ ] Verify mock material stock dan satu historical confirmed PO tersedia.
- [ ] **Commit:** `feat: seed sintetis deterministik dan loader idempotent`.

## Task 11: API Supply, Demand, dan Forecast

**Objective:** Mengekspos kontrak S1-02/S1-03/S1-10 dengan PostgreSQL/MockSAPProvider.

**Files:**
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/supply.py`
- Create: `backend/app/api/demand.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_api_supply_demand.py`

**Contracts:**
- `GET /supply/{location}/{commodity}` → `{quantity_kg, recorded_at, source}` plus `X-Data-Source: MOCK` ketika berasal dari Mock SAP.
- `GET /demand/{location}/{commodity}` → `{quantity_kg, needed_by}`.
- `GET /demand/forecast/{location}/{commodity}?horizon_days=7` → `{forecast_qty_kg, method, confidence}`.
- Location/commodity resolver menerima nama atau UUID; unknown→404; invalid horizon→422.
- “Terbaru” berarti record dengan `recorded_at` maksimum untuk pasangan, bukan menjumlahkan snapshot lintas waktu. Ketika satu pasangan punya beberapa source pada timestamp yang sama, pilih SATU record dengan precedence source (mock_sap > manual > sensor) — jangan SUM lintas source (menggandakan stok).
- Daftarkan `GET /demand/forecast/{location}/{commodity}` SEBELUM `GET /demand/{location}/{commodity}` (FastAPI mencocokkan berurutan; route generik dapat menangkap `forecast` sebagai `{location}`).
- Migration 002 menambahkan indeks `(location_id, commodity_id, recorded_at DESC)` untuk supply dan demand di samping indeks §5.

**Test fixture:** override `get_db` dengan async session test yang di-rollback per test atau gunakan database test terisolasi. Seed dipanggil eksplisit; jangan bergantung pada state test sebelumnya.

**Lifecycle DB (temuan audit):** `get_db()` saat ini membuat engine baru per request tanpa dispose. Refactor ke satu async engine + sessionmaker yang dibuat sekali pada app lifespan dan di-dispose saat shutdown; endpoint tetap menerima session via dependency. Tambahkan test kontrak bahwa lifespan tidak meninggalkan engine bocor (engine dipakai ulang antar request).

- [ ] RED endpoint per behavior: happy path, 404, method label, latest-record semantics, mock header.
- [ ] GREEN router tipis.
- [ ] Regression API + core + provider contract.
- [ ] **Commit:** `feat: API supply demand dan forecast statistik`.

## Task 12: API Freshness, Safety, Price, dan Logistics

**Objective:** Mengekspos domain engine tanpa perhitungan ulang di router.

**Files:**
- Create: `backend/app/api/freshness.py`
- Create: `backend/app/api/safety.py`
- Create: `backend/app/api/price.py`
- Create: `backend/app/api/logistics.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_domain_tools.py`

**Contracts:**
- `POST /freshness/evaluate {batch_id, as_of?}` → `{freshness_score,status,usable_until}`; persist tiga hasil terkait ke batch. `as_of` hanya boleh di-override dalam test/DEMO_MODE; normal runtime memakai waktu server.
- `POST /safety/evaluate {batch_id}` → `{safety_status,reasons,excursion_minutes}`; status API uppercase, DB lowercase.
- `GET /price/{location}/{commodity}` → reference terbaru.
- `POST /price/deviation` → `{deviation_pct,reference_price,classification,flagged}`.
- `POST /logistics/estimate` → `{distance_km,estimated_time_min,feasible}`.

**Mandatory API tests:** exact freshness boundaries 0.85/0.60 melalui core unit test dan satu integration persistence test; missing batch 404; excursion batch FAIL persists; Supplier C flagged; logistics boundary equal window feasible; malformed payload 422; router tidak memiliki rumus domain duplikat.

- [ ] RED/GREEN satu endpoint behavior per cycle.
- [ ] Verify persisted values dengan query sesi baru.
- [ ] Regression container suite.
- [ ] **Commit:** `feat: API freshness safety price dan logistics`.

## Task 13: Hard-Constraint Integration dan Acceptance Sprint 1

**Objective:** Membuktikan Sprint 1 memenuhi Roadmap/TODO tanpa mengimplementasikan Sprint 2–4.

**Files:**
- Create: `backend/tests/test_sprint1_acceptance.py`
- Modify: `docs/Skill.md` bila kontrak endpoint final berbeda dari draft Task 0.
- Modify: `TODO.md`
- Modify: `Roadmap.md`
- Create: `docs/verification/sprint-1.md`

**Acceptance tests:**
1. Freshness 0.85 PASS; 0.60 NEEDS_VERIFICATION; 0.599999 FAIL.
2. Safety FAIL tidak dapat berubah lewat API input lain.
3. Semua empat hard constraints Sprint 1 memiliki bukti: safety, freshness, capacity, dan delivery window.
4. Seed 10×3 dan angka Cianjur/Jakarta tepat.
5. Seluruh endpoint Sprint 1 dapat dipanggil terhadap PostgreSQL hasil migration+seed.
6. Mock SAP response memiliki header simulasi.
7. Forecast selalu melabeli fallback statistik.

**Fresh verification commands (jalankan berurutan dan simpan output ringkas):**

```bash
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m app.seed.seed_data --reference-time 2026-10-01T12:00:00+00:00
docker compose exec -T backend python -m app.seed.seed_data --reference-time 2026-10-01T12:00:00+00:00
docker compose exec -T backend pytest -q
docker compose exec -T backend ruff check .
docker compose exec -T frontend npm run test -- --run
docker compose exec -T frontend npm run lint
docker compose ps
```

- [ ] Catat exit code, jumlah passed/failed, dan service health di `docs/verification/sprint-1.md`; jangan menulis hasil sebelum command benar-benar dijalankan.
- [ ] Cocokkan setiap S1-01..S1-11 ke test/commit evidence.
- [ ] Set TODO/Roadmap `Done` hanya untuk item yang punya bukti; blocker tetap `Blocked` dengan alasan.
- [ ] Jalankan final whole-branch review melalui subagent terpisah.
- [ ] Perbaiki temuan review melalui TDD dan ulangi seluruh gate yang terdampak.
- [ ] **Commit:** `docs: verifikasi dan status Sprint 1`.
- [ ] STOP setelah Sprint 1 dan minta review Roy; jangan lanjut Sprint 2.

---

## Subagent-Driven Execution Contract

Untuk setiap Task 1–13:

1. Dispatch satu implementer fresh dengan hanya task, kontrak global, path relevan, dan perintah test.
2. Implementer wajib menunjukkan output RED yang benar sebelum production code.
3. Setelah implementer selesai, dispatch spec-compliance reviewer. Jika gagal, implementer yang sama memperbaiki.
4. Setelah spec pass, dispatch code-quality reviewer. Jika gagal, implementer memperbaiki dan kedua gate diulang bila perilaku berubah.
5. Parent memverifikasi diff dan test secara independen; laporan subagent bukan bukti final.
6. Update ledger/TODO setelah task benar-benar terverifikasi.
7. Jangan menjalankan dua subagent yang menulis file saling tumpang tindih secara paralel.

## Self-Review Checklist Plan

- [x] Scope cocok Roadmap Sprint 1; fitur Sprint 2–4 didefer eksplisit.
- [x] Freshness final konsisten: PASS >=0.85, verify 0.60–<0.85, fail <0.60.
- [x] Tiga role final digunakan; role usang dilarang.
- [x] Setiap task kode memiliki RED, expected failure, GREEN, targeted pass, regression, refactor/review.
- [x] Runtime test canonical = container Python 3.12, bukan host Python 3.11.
- [x] Migration menangani absennya tabel `decisions` tanpa FK prematur.
- [x] Seed mempunyai waktu eksplisit dan strategi idempotensi yang dapat diuji.
- [x] API tests mengisolasi database dan memverifikasi persistence.
- [x] Tidak ada UI work, browser automation, Obsidian write, atau skill authoring dalam Sprint 1; skill terkait sudah ditinjau tetapi tidak relevan untuk deliverable ini.
- [x] Tidak ada auto-execute, secret, SAP asli palsu, push, atau merge.
