# Task 1-7 Review Brief — Core Engine Spec Compliance (Sprint 1 MealChain)

## Mode
Kode production + tests SUDAH ADA di working tree (sisa sesi sebelumnya, belum dicommit).
Tugasmu BUKAN implementasi, tapi VERIFIKASI SPEC-COMPLIANCE terhadap matriks wajib di bawah,
menjalankan test, dan melaporkan temuan. JANGAN mengubah kode — laporkan saja.

## Files under review
- backend/app/core/temperature.py + backend/tests/test_temperature.py (Task 1)
- backend/app/core/freshness.py + backend/tests/test_freshness.py (Task 2)
- backend/app/core/safety.py + backend/tests/test_safety.py (Task 3)
- backend/app/core/price.py + backend/tests/test_price.py (Task 4)
- backend/app/core/logistics.py + backend/tests/test_logistics.py (Task 5)
- backend/app/core/constraints.py + backend/tests/test_constraints.py (Task 6)
- backend/app/core/forecasting_fallback.py + backend/tests/test_forecasting_fallback.py (Task 7)

## Global constraints (binding)
1. Core modules TIDAK boleh mengimpor FastAPI/SQLAlchemy dan TIDAK boleh memanggil LLM.
2. LLM tidak pernah menghitung freshness/safety/price/logistics/forecast.
3. Canonical runtime = container Python 3.12. Semua test dijalankan via:
   `docker compose exec -T backend pytest tests/test_<name>.py -q`
4. Ruff harus bersih untuk file production terkait (abaikan alembic/ for this review).

## Task 1 — temperature.summarize_temperature_log
Interface wajib:
```python
@dataclass(frozen=True)
class TemperatureSummary:
    observed_minutes: float
    outside_minutes: float
    complete: bool
    issues: tuple[str, ...]

summarize_temperature_log(temperature_log: list[dict], safe_min_c: float, safe_max_c: float) -> TemperatureSummary
```
Tracer bullets (semua harus ada test-nya):
1. Dua sample valid in-range → observed_minutes benar, outside=0, complete=True.
2. Sample pertama out-of-range → outside_minutes mengikuti interval sample pertama.
3. Input tak terurut → hasil identik setelah sorting.
4. Duplikat timestamp / malformed entry / <2 sample → complete=False + issues eksplisit, tidak crash.
5. safe_min_c > safe_max_c → ValueError.
Aturan interval: sample_i berlaku untuk [sample_i.timestamp, sample_i+1.timestamp).

## Task 2 — freshness
Interface wajib: PASS_THRESHOLD=0.85, VERIFY_THRESHOLD=0.60, TEMP_PENALTY_WEIGHT=0.30,
compute_freshness_score(harvested_at, as_of, shelf_life_days, temperature_log, safe_min_c, safe_max_c) -> float,
classify_freshness(score, pass_threshold=0.85, verify_threshold=0.60) -> "pass"|"needs_verification"|"fail",
compute_usable_until(harvested_at, shelf_life_days, score) -> datetime.
Formula: base = clamp(1 - age/shelf_life, 0, 1); score = clamp(base - 0.3*outside_fraction, 0, 1);
usable_until = harvested_at + shelf_life * score.
Matriks wajib (semua harus ada test-nya):
- age 2.8/28 hari, log complete in-range → score 0.90
- base 0.90 + 50% observed outside → score 0.75
- age > shelf life → 0.0
- harvested_at > as_of → ValueError
- shelf_life 0/negatif → ValueError
- 0.85→pass; 0.849999→needs_verification; 0.60→needs_verification; 0.599999→fail
- score -0.01/1.01/NaN → ValueError
- usable_until exact tz-aware datetime
Ketika log tidak complete: outside_fraction fallback = 0.0 (score tetap dihitung dari umur).

## Task 3 — safety.evaluate_safety(temperature_log, safe_min_c, safe_max_c, max_excursion_minutes=30) -> dict keys {safety_status, reasons, excursion_minutes}
Matriks wajib: clean complete → pass; 29.999 → needs_verification; exactly 30 → fail; >30 → fail;
malformed/empty/<2 → needs_verification; safe_min>safe_max / threshold<=0 → ValueError;
deterministic repeated call; assertion tidak ada status di luar 3 nilai kontrak.

## Task 4 — price.price_deviation(supplier_price, reference_price, elevated_pct=5, anomalous_pct=15) -> dict
Formula: deviation_pct = abs(supplier - reference)/reference*100. Wajib Decimal (bukan float).
Matriks: reference exact → 0%; 26,200 vs 26,500 normal; 27,000 vs 26,500 normal; 32,000 vs 26,500
anomalous+flagged=true; exact 5% → elevated; exact 15% → anomalous+flagged; input
invalid/non-finite/zero/negatif → ValueError.

## Task 5 — logistics
LOCATIONS tuple tepat 10 lokasi seed: Jakarta, Bogor, Cianjur, Bandung, Semarang, Yogyakarta,
Surabaya, Malang, Palembang, Medan. DISTANCE_KM dict[frozenset, int].
estimate_logistics(source, target, quantity_kg, delivery_window_min=None, speed_kmh=60, fixed_handling_min=30).
estimated_time_min = distance/60*60 + 30. feasible = estimated_time_min <= delivery_window_min.
Matriks: 45 pasangan unik (10 choose 2); tidak ada duplikat key; Cianjur–Jakarta 120 km dan
150 menit; matriks simetris; same-location 0 km; boundary estimated==window feasible;
unknown location / quantity<=0 / speed<=0 / window<0 → ValueError.

## Task 6 — constraints
check_capacity(available_kg, required_kg) -> dict[str, float|bool] (keys minimal: sufficient/shortfall).
check_delivery_window(estimated_time_min, delivery_window_min) -> bool (equal → True).
is_batch_eligible(freshness_status, safety_status) -> bool.
Matriks: available==required lolos; available<required gagal; negatif/non-finite ditolak;
estimated==window lolos; estimated>window gagal; freshness "fail" ATAU safety "fail" → False;
needs_verification → True (bukan PASS otomatis, tapi dapat diteruskan sebagai review status);
status tidak dikenal → ValueError.

## Task 7 — forecasting_fallback.statistical_forecast(daily_kg, horizon_days=7, weights=(0.5,0.3,0.2)) -> dict[str, float|str]
Matriks: flat [100,100,100] horizon 7 → 700; [100,200,300] pakai 300*0.5+200*0.3+100*0.2 per hari
(→ 230*7=1610 total); histori 1-2 item menormalisasi bobot; histori >3 hanya 3 terbaru;
confidence 0..1 meningkat dengan jumlah histori; empty/negatif/non-finite/horizon<=0/bobot invalid → ValueError;
response selalu method="statistical_fallback".

## Cara kerja
1. Baca semua 14 file.
2. Jalankan per-file test: docker compose exec -T backend pytest tests/test_<name>.py -q (7 file).
3. Jalankan ruff pada 7 file production: docker compose exec -T backend ruff check app/core/.
4. Cocokkan SETIAP baris matriks di atas dengan test nyata (baca nama test, buka isi test
   bila nama tidak jelas). Tandai SETIAP baris: COVERED / MISSING / WEAK (weak = ada test
   tapi assertion tidak benar-benar memverifikasi perilaku).
5. Cek kontrak: tidak ada import fastapi/sqlalchemy di app/core/, tidak ada pemanggilan LLM,
   tidak ada random/non-determinisme.
6. LAPORKAN: verdict spec ✅/❌ per task, daftar temuan dengan severity
   (Critical/Important/Minor), dan coverage matriks per baris. JANGAN memperbaiki apa pun.
