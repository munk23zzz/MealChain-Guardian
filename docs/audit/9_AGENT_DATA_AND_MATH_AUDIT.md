# 9_AGENT_DATA_AND_MATH_AUDIT — angka & matematika jalur 9 agent

Status: **audit selesai, bukti terkumpul** — 26 Oktober 2026.

Objek: nilai numerik yang diproduksi/dikonsumsi jalur **sembilan agent**
(Supply, Demand, Freshness, Safety, Price, Logistics, Evidence, Verifier, Supervisor)
beserta angka hulu yang mereka baca (`recommendation_service` → `decisions`)
dan hilir yang mereka isi (`agent_traces` → UI).

Lingkungan: DB demo `mealchain` (container `mealchain-postgres`, port 15432) —
**SELECT saja**; backend `localhost:8000` (healthy); probe review dijalankan
dari host dengan token baca `bgn_monitor` (nilai token tidak pernah dicetak).

Aturan metode yang dipakai sepanjang dokumen:

1. **Fungsi produksi tidak dipakai sebagai oracle.** Setiap hitung ulang memakai
   aritmetika SQL/`Decimal` biasa dari kolom mentah (`supply_records`,
   `demand_records`, `price_signals`, `batches`, `decisions.cost_breakdown`).
2. **Angka yang tidak ada dilaporkan tidak ada** (`MISSING`), bukan diisi 0.
3. Setiap temuan punya ID `AUD-9B-xx`, severity P0–P3, status dari kosakata
   baku (PASS/FAIL/BLOCKED/NOT TESTED/UNVERIFIED/MOCK/STUB/MISSING/
   NEEDS_PRODUCT_DECISION).
4. Bukti berupa `file:baris`, query SQL, atau keluaran probe. Reproduksi ada di §9.

Dokumen pasangan: `docs/audit/9_AGENT_ORCHESTRATION_AUDIT.md` (ID AUD-9B-20
dan seterusnya). Dokumen ini **tidak** mengubah kode, DB, atau dokumen lain.

---

## 1. Peta jalur angka (ringkas)

```
DB (supply_records, demand_records, price_signals, batches, menu_plans)
  │
  ├─ recommendation_service.fetch_operational_facts()  [as_of = now, UTC]
  │     supplier_leg_map(), compute_freshness_score(), _menu_hierarchy_maps()
  │
  ├─ generate_candidates()  → quantity, demand_fit, supply_availability,
  │                           freshness (rata-rata berbobot kg), safety gabungan
  │
  ├─ calculate_candidate_score()  → score (produk 6 faktor, Decimal eksak)
  ├─ calculate_safe_delivered_cost() → SDC 6 komponen, 2 dp HALF_UP
  ├─ rank_candidates()           → rank 1..N (skor DESC, SDC ASC)
  │
  └─ decisions (quantity_kg, safe_delivered_cost, cost_breakdown jsonb)
        │
        ├─ GET /decisions/{id}/approval-summary   (read model; hitung ulang
        │     seconds_remaining, can_execute, safety dari batch SUMBER)
        │
        └─ 9 agent (agent/orchestrator.run_review)
              Supply    ← /balance/{loc}/{com}
              Demand    ← /demand/{loc}/{com} + /demand/forecast/...
              Freshness ← /batches (freshness_score tersimpan, usable_until)
              Safety    ← /batches + /supplier-exclusions
              Price     ← /price/quotes, POST /price/deviation, approval-summary
              Logistics ← /supplier-routes, POST /logistics/estimate
              Evidence  ← dossier/compliance/chain/approval-summary/ledger
              Verifier  ← run.verification (tanpa baca data)
              Supervisor← narasi template (agent/orchestrator._narrative)
                    │
                    └─ AgentFinding.facts (wajib sitasi per angka)
                          → agent_traces (9 baris) → AgentTraceViewer / UI
```

Dua jalur paralel yang **tidak** bertemu:

- `event1_orchestrator` (DETECT→VERIFY→…→SUPERVISE) memakai
  `run_verifier` (`ai_providers/verifier_client.py`) yang **LLM REST**, bukan agent.
  Verdict inilah yang ditulis ke `decisions.verifier_note` dan yang menjadi
  gerbang `can_approve` (`services/approval_summary.py:287-315`).
- `agent/orchestrator.run_review` memakai 8 agent yang seluruhnya deterministik;
  temuannya **advisory** dan tidak pernah menulis `decisions`.

Konsekuensi: label "Independent Verifier" pada UI/`agent_traces` menunjuk dua
mekanisme berbeda (lihat AUD-9B-30). Semua angka safety di sistem tetap berasal
dari `core/*` deterministik, bukan dari LLM — itu konsisten.

---

## 2. Inventaris nilai numerik

Kolom "DB" = nilai tersimpan; "API" = nilai yang benar-benar dikembalikan
endpoint pada probe 26 Okt 2026 16:55Z; "UI" = komponen yang mengikat field
tersebut (render piksel tidak diperiksa di audit ini → status UI `UNVERIFIED`
bila tidak dinyatakan lain).

### 2.1 Pasokan, permintaan, gap

| # | Field | Penghasil (file:fungsi) | Sumber | Rumus aktual | Unit | Ambang (konstanta, file) | Rounding | Konsumen | DB | API | UI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `supply_kg` | `api/balance.py:148-152` | `supply_records.quantity_kg` baris terbaru `recorded_at <= now` | diambil apa adanya (bukan dijumlah) | kg | — | `float()` saat serialisasi | Supply agent, `/balance/map`, chart | Bandung/telur 400.00 | 400.0 | `StockChart.tsx:45-46`, `OpsConsole` |
| 2 | `demand_kg` | `api/balance.py:153-157` | `demand_records` baris terbaru `<= now` | apa adanya | kg | — | `float()` | Supply agent | Bandung/telur 538.00 | 538.0 | idem |
| 3 | `demand.quantity_kg` (agent Demand) | `api/demand.py:81-96` | `demand_records` **tanpa** batas `<= now` | apa adanya | kg | — | `float()` | Demand agent | baris 4 Nov = 532.40 | 532.4 | `AgentTraceViewer` (summary) |
| 4 | `surplus_kg` / `shortage_kg` | `core/gaps.py:36-53,65-85` | #1,#2 | `max(s−d,0)` / `max(d−s,0)` | kg | 0 = batas (`balanced`) | `Decimal` eksak (tanpa kuantisasi) | Supply agent, `/balance/map`, `/balance/analyze` | 0 / 138 | 0.0 / 138.0 | `StockChart.tsx:45-46` |
| 5 | `quantity_kg` kandidat | `core/candidate_generation.py:200` | surplus sumber, shortage tujuan, `available_kg` batch | `min(surplus_s, shortage, available_kg)` | kg | 0 → kandidat dibuang | `Decimal` eksak | skor, SDC, keputusan | 300.00 (e7150) | `quantity_kg` 600.0 (approval-summary) | `RecommendationCard.tsx:167` |
| 6 | `demand_fit` | `core/candidate_generation.py:236` | #4,#5 | `quantity / shortage_tujuan` | rasio 0..1 | — | eksak | skor | tidak disimpan | ikut payload rekomendasi | `RecommendationCard` (bila skor ditampilkan) |
| 7 | `supply_availability` | `core/candidate_generation.py:237` | #4,#5 | `quantity / surplus_sumber` | rasio 0..1 | — | eksak | skor | tidak disimpan | idem | idem |
| 8 | `kebutuhan_menu_kg` | `core/menu_hierarchy.py:49-57` | `menu_plans.planned_portions` × `menu_grams_*` | `porsi × gram / 1000` | kg | gram 0 → butuh 0 | `quantize("0.01")` **default HALF_EVEN** | lantai shortage (`shortage_setelah_gizi`) | 100 baris `menu_plans` bertanggal masa depan | tidak diekspos | tidak ada |
| 9 | `cadangan_kontinuitas_kg` | `core/menu_hierarchy.py:60-64` | porsi × gram × `continuity_reserve_days` (1.0) | `kebutuhan_menu_kg × hari` | kg | hari cadangan 1.0 (`core/config.py:79`) | HALF_EVEN 2dp | plafon surplus ekspor | idem | tidak diekspos | tidak ada |

### 2.2 Kesegaran, keamanan, risiko

| # | Field | Penghasil | Sumber | Rumus aktual | Unit | Ambang | Rounding | Konsumen | DB | API | UI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | `freshness_score` (dihitung) | `core/freshness.py:12-41` | `harvested_at`, `shelf_life_days`, `temperature_log` | `clamp(1 − umur/(shelf×24j) − 0.30×fraksi_di_luar_rentang, 0, 1)`; bukti suhu tidak lengkap → fraksi = 1.0 (fail-closed) | rasio 0..1 | `PASS_THRESHOLD=0.85`, `VERIFY_THRESHOLD=0.60` (`core/freshness.py:7-8`) | `_score()` 6dp HALF_UP (`recommendation_service.py:76-77`) | skor kandidat, SDC (`expected_loss`) | contoh 995ea332: pipeline 0.9707 vs kolom 0.69 | `batches[].freshness_score` = 0.69 | `FoodSafetyBoard.tsx:346` → `Math.round(×100)%` |
| 11 | `freshness_score` (tersimpan) | penulis seed | kolom `batches.freshness_score` | **literal**: 0.82 untuk 39 batch `origin='demo'` (`seed/demo_activity.py:231`) | rasio | idem | 2dp | Freshness agent (`/batches`) | 0.69 / 0.82 / 0.92 (Bandung/telur) | sama | idem |
| 12 | `freshness_status` | `core/freshness.py:44-57` | #10 | `≥0.85 pass; ≥0.60 needs_verification; else fail` | enum | 0.85 / 0.60 | — | `is_batch_eligible` | tidak ada kolom | tidak diekspos | idem |
| 13 | `usable_until` | `core/freshness.py:60-69` | `harvested_at + shelf_life_days × score` | idem | timestamp UTC | — | — | Freshness agent (`expired_count`), demo_cost (`>= now`) | 48/120 baris **tidak cocok** dengan rumus | `batches[].usable_until` | `FoodSafetyBoard.tsx:347` |
| 14 | `safety_status` | kolom `batches.safety_status` (seed + `core/safety.py`) | batch | enum `pass/pending/fail/needs_verification` | enum | `fail` = hard exclusion (`core/constraints.py:41-42`) | — | Safety agent, scoring, SDC | Jakarta/ayam: 1 fail, 1 pending, 1 pass, 1 needs_verification | `safety.worst_status` (approval-summary) = `pass` (batch **sumber**) | `FoodSafetyBoard`, `ComplianceEvidencePanel` |
| 15 | `safety_risk_penalty` | `core/safe_delivered_cost.py:129-133` | #14 | `0.10 × purchase` **hanya** bila `needs_verification` | Rp | `_SAFETY_RISK_RATE=0.10` | 2dp HALF_UP | SDC | 1.200.000,00 dan 1.772.301,60 pada 2 keputusan | ikut `cost_breakdown` | `ApprovalModal` |
| 16 | `expected_loss` | `core/safe_delivered_cost.py:121-123` | purchase, #10/#11 | `purchase × 0.2 × (1 − freshness)` | Rp | `_EXPECTED_LOSS_RATE=0.2` | 2dp HALF_UP | SDC | 1.011.840,00 (e7150da4) | idem | idem |
| 17 | `freshness_risk_penalty` | `core/safe_delivered_cost.py:124-128` | #10/#11 | `0.50 × purchase` bila `freshness < 0.60` | Rp | `_FRESHNESS_RISK_THRESHOLD=0.60`, `_FRESHNESS_RISK_FACTOR=0.50` | 2dp | SDC | **0,00 di seluruh 29 keputusan** (ambang tidak pernah aktif) | 0.00 | idem |

### 2.3 Harga, biaya, logistik

| # | Field | Penghasil | Sumber | Rumus aktual | Unit | Ambang | Rounding | Konsumen | DB | API | UI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 18 | `price_per_kg` quote/referensi | `price_signals`, dibaca `api/price.py:20-104` | tabel harga | apa adanya | Rp/kg | — | `float()` | Price agent | Bandung/telur quote 27.200 (26 Okt 15:13), ref 27.200 | `quotes[0]` = **26.655,17** (3 Nov, masa depan) | `RecommendationCard` (harga) |
| 19 | `deviation_pct` | `core/price.py:26-50` | #18 | `(supplier − referensi) / referensi × 100` | **persen** | `ELEVATED_PCT_DEFAULT=5`, `ANOMALOUS_PCT_DEFAULT=15` (`core/price.py:5-6`) | tanpa kuantisasi (dikirim `str(Decimal)` penuh) | Price agent, `/balance/*` `price_anomaly` | tidak disimpan | **null** (endpoint 409) | `AgentTraceViewer` summary |
| 20 | `quote_count`, `latest_quote_price` | `agent/workers/price.py:41-48,82-83` | `/price/quotes` | `len(quotes)`, `quotes[0]` (asumsi urut terbaru) | — /Rp/kg | — | — | facts Price | — | 12 quote, 26.655,17 | idem |
| 21 | `transport_cost` | `recommendation_service.py:399-409` | jarak linehaul (matriks) + jarak kaki pertama (haversine), kg | `300 × km × kg / 1000` (linehaul) + `300 × km_leg × kg/1000` | Rp | `TRANSPORT_RATE=300` Rp/km/ton (`:67`) | `_money` 2dp HALF_UP | SDC | 338,40 (e7150da4: leg 1,88 km, linehaul 0) | 338.4 | `ApprovalModal` |
| 22 | `handling_cost` | `recommendation_service.py:414` | konstanta | flat 150.000 per keputusan | Rp | `HANDLING_FLAT=150000` (`:68`) | 2dp | SDC | 150.000,00 | 150000.0 | idem |
| 23 | `safe_delivered_cost` | `core/safe_delivered_cost.py:104-150` | #15–#17,#21,#22 | `purchase + transport + handling + expected_loss + freshness_risk + safety_risk` (tiap komponen dibulatkan dulu) | Rp | `purchase > 0`, `freshness ∈ [0,1]`, `safety != fail` | 2dp HALF_UP per komponen | ranking, keputusan, agent Price/Evidence, KPI | 17.482.178,40 (e7150da4); **9.750.000,00 tanpa rincian kanonik** (3e2e3cc7) | 17482178.4 | `RecommendationCard.tsx:169`, `ApprovalModal` |
| 24 | `distance_km` | `core/logistics.py:67-73` | matriks 10 kota (sintetis, Cianjur–Jakarta 120 km) | `DISTANCE_KM[frozenset(pair)]` | km | — | `int` | `estimate_logistics`, SDC linehaul | 150 (Bandung–Jakarta) | /supplier-routes: 65,6–91,1 km (OSRM) | RouteFocus |
| 25 | `estimated_time_min` (ETA) | `core/logistics.py:93-98` | #24 | `km/60×60 + 30` (fixed handling) | **menit** | `speed_kmh=60`, `fixed_handling_min=30` (`:81-82`) | float (tidak dibulatkan); kandidat pakai `ROUND_CEILING` (`candidate_generation.py:227-228`) | `feasible`, `logistics_time_min` | tidak disimpan | agent: `min_duration_min=4.7` (OSRM, 3,4 km); model: 33,4 menit | `AgentTraceViewer` summary |
| 26 | `capacity_kg_per_week` | kolom `suppliers` | seed | apa adanya | kg/pekan | `check_capacity` (`core/constraints.py:15-25`) **tanpa pemanggil produksi** | — | hanya kolom + payload pemasok | 800–2.900 | `suppliers` API | panel pemasok |
| 27 | **`capacity utilization`** | — | — | **tidak ada** (tidak ada % utilisasi di kode/UI) | — | — | — | — | — | — | — |

### 2.4 Skor, bukti, waktu

| # | Field | Penghasil | Sumber | Rumus aktual | Unit | Ambang | Rounding | Konsumen | DB | API | UI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 28 | `score` kandidat | `core/scoring.py:66-90` | #6,#7,#10,#14,#26(reliability), logistik | `demand_fit × supply_availability × freshness × safety_eligibility(1) × reliability × (logistics?1:0)`; safety `fail` → 0 & `eligible=False` | rasio 0..1 | faktor wajib [0,1] | `_score` 6dp HALF_UP | ranking | **tidak disimpan** | hanya respons `POST /balance/recommend|analyze` | `RecommendationCard` |
| 29 | `supplier_reliability` | `core/reliability.py` (dibaca) + fallback | `suppliers.reliability_score` | `DEFAULT_RELIABILITY=0.80` bila tidak ada | rasio | 0.80 (`recommendation_service.py:69`) | — | skor | 60 pemasok | payload | panel pemasok |
| 30 | `evidence_count`/`approval_count`/`trace_count`/`inconsistent_evidence_count` | `agent/workers/evidence.py:93-99,110-132` | `/decisions/{id}/compliance` | `len(list)`, hitung `is_consistent is False` | cacah | — | — | facts Evidence | 5/2/4/0 (e7150da4); 0/0/3/0 (3e2e3cc7) | idem | `ComplianceEvidencePanel` |
| 31 | **"evidence completeness"** | — | — | **tidak ada rasio/kelengkapan wajib**; hanya cacah mentah | — | — | — | — | — | — | — |
| 32 | `ledger_blocks` | `api/ledger.py` (`/ledger/verify`) | `ledger_blocks` | `count(*)` | cacah | — | — | Evidence | 2.034 | 2034 | `IntegrityPanel` |
| 33 | `confidence` forecast | `core/forecasting_fallback.py` | 3 baris demand terakhir | fallback statistik | rasio | — | — | Demand agent | tidak disimpan | **1.0 selalu** (probe: 1.0 pada 2 keputusan berbeda) | `AgentTraceViewer` |
| 34 | **`decision time`** | — | — | **tidak ada metrik**; proksi: `total_latency_ms` (agent), `expires_at − created_at` (TTL), `expiry.seconds_remaining` | ms/detik | TTL 30–480 menit (seed) | — | — | `seconds_remaining` 2.585.831 | idem | `ApprovalModal` countdown |
| 35 | `duration_ms`/`latency_ms` trace | `agent/telemetry.py:26`, `workers/base.py:57-59` | `monotonic()` | `(t1−t0)×1000` | **ms** | — | `int()` | `agent_traces.duration_ms` | 960 (seed), NULL (review) | idem | `AgentTraceViewer` (`trace-duration`) |
| 36 | `seconds_remaining` | `services/approval_summary.py:249` | `expires_at − now` | `max(0, int(detik))` | **detik** | 0 = kedaluwarsa | `int()` | UI countdown | 2.585.831 | idem | `ApprovalModal` |

---

## 3. Hitung ulang independen

Semua nilai di bawah dihitung dari kolom mentah (SQL/`Decimal`), **bukan** dengan
memanggil `core/*`. Waktu acuan: `2026-10-26 16:55Z` (23:55 WIB).

| # | Nilai | Nilai produksi | Hitung independen (cara) | Selisih absolut | Selisih relatif | Status |
|---|---|---|---|---|---|---|
| V1 | `shortage_kg` Bandung/telur | **138.0** (agent Supply) | `max(538 − 400, 0) = 138` (SELECT baris terbaru `recorded_at <= now`) | 0 | 0% | **PASS** |
| V2 | `safe_delivered_cost` e7150da4 | **17.482.178,40** | `16.320.000 + 338,40 + 150.000 + 1.011.840 + 0 + 0 = 17.482.178,40` (SQL `jsonb` → numeric, dijumlah) | 0,00 | 0% | **PASS** |
| V3 | `expected_loss` e7150da4 | **1.011.840,00** | `16.320.000 × 0,2 × (1 − 0,69) = 1.011.840,00` | 0,00 | 0% | **PASS** (konsisten dengan freshness **tersimpan**) |
| V4 | `expected_loss` bila freshness dihitung ulang | 1.011.840,00 | `16.320.000 × 0,2 × (1 − 0,970682) = 95.961,60` | **−915.878,40** | **−90,52%** | **FAIL** — basis kesegaran tidak dapat direproduksi (lihat AUD-9B-01) |
| V5 | `freshness_score` batch 995ea332 | **0,69** (kolom & API) | `1 − (0,8209 hari / 28 hari) − 0,30×0 = 0,970682` (semua sampel 4,1–4,6 °C, rentang aman 0–8 °C) | **−0,280682** | **−28,07 poin persen** | **FAIL** |
| V6 | `safe_delivered_cost` 3e2e3cc7 | **9.750.000,00** | `(28.500 + 1.800 + 950) × 300 = 9.375.000,00` | **−375.000,00** | **−3,85%** (4,00% dari nilai tertulis) | **FAIL** |
| V7 | `unit price` efektif 3e2e3cc7 | 32.500/kg (`9.750.000/300`) | harga beli saja ≥ `300 × 35.400 = 10.620.000` (quote sumber termurah) atau `300 × 40.300 = 12.090.000` (tujuan) | **≥ 870.000** (Rp/kg mustahil < harga beli) | ≥ 8,9% | **FAIL** — SDC lebih kecil dari komponen beli saja |
| V8 | `deviation_pct` Bandung/telur | **null** (agent: `endpoint_error`) | `(26.655,17 − 26.856,52)/26.856,52 × 100 = −0,7497%` → `normal` (|x| < 5) | tidak dapat dibandingkan | — | **NOT TESTED** (angka tidak pernah diproduksi) |
| V9 | Klaim "harga 40% di bawah referensi" (3 keputusan `price_anomaly`) | `supplier_quote_ratio = 0,60` → **−40%** | Rasio quote/ref pada `created_at` keputusan: Surabaya 28.200/28.200 = **1,0000**; Bandung 27.200/27.200 = **1,0000**; Jakarta 30.500/30.500 = **1,0000** | **40,0 poin persen** | — | **FAIL** — angka tidak berasal dari `price_signals` |
| V10 | `transport_cost` kaki pertama e7150da4 | **338,40** | `300 × 1,88 × 600/1000 = 338,40` | 0,00 | 0% | **PASS** |
| V11 | ETA 3,4 km | **4,7 menit** (agent, OSRM) | `3,4/60×60 + 30 = 33,4 menit` (model `core/logistics.py`) | **−28,7 menit** | **−85,9%** | **FAIL** — dua basis waktu berbeda (lihat AUD-9B-09) |
| V12 | `usable_until` vs `harvested_at + shelf×score` | 120 baris | 48 baris menyimpang; maksimum **75,433 hari** (mis. 3bc81364: +5,04 hari karena score 0,82 tetapi `usable_until` = panen + 28 hari penuh) | s.d. 75,4 hari | — | **FAIL** (AUD-9B-02) |

Ringkas: **3 angka gagal diverifikasi ulang** (V5 freshness, V6 SDC 3e2e3cc7,
V9 klaim anomali harga) — lihat §7. V4/V7 adalah konsekuensi turunan dari V5/V6.

Catatan penting yang jujur: **rantai SDC→komponen konsisten secara internal**
(V2, V3, V10 lulus). Yang gagal adalah *input*-nya (kesegaran literal, harga
dari komoditas/lokasi lain) dan satu baris warisan (V6). Jadi masalahnya bukan
aritmetika mesin, melainkan **kualitas basis angka**.

---

## 4. Campuran unit, basis waktu, dan rencana vs eksekusi

| # | Campuran | Bukti | Dampak | ID |
|---|---|---|---|---|
| U1 | **Persen vs pecahan** | `deviation_pct` = persen (`core/price.py:35`), `freshness_score`/`score` = pecahan 0..1, `TOLERANSI_RINCIAN = 0.01` dipakai sebagai **fraksi** (`core/recommendation_numbers.py:28,107`) padahal docstring menyebut toleransi mutlak | Toleransi rincian = **1%** biaya, bukan Rp0,01; pada SDC 17,4 juta = **Rp174.821,78**. UI mengalikan freshness ×100 (`FoodSafetyBoard.tsx:346`), jadi 0,69 tampil "69%" sementara `deviation_pct` tampil "-0,75" tanpa `%` | AUD-9B-10 |
| U2 | **Per-unit vs total** | `cost_breakdown` 3e2e3cc7 berisi harga/angkut/risiko **per kg** (28.500/1.800/950) di kolom yang di 29 keputusan lain berisi **total** komponen SDC | Penjumlah komponen menghasilkan 31.250 (dibaca sebagai total = mustahil) atau 9.375.000 (dibaca per kg = beda 375.000). Skema ketiga ini tidak diproduksi mesin mana pun | AUD-9B-03 |
| U3 | **Kg vs gram** | `menu_grams_*` = 60/50/40/100 gram (`core/config.py:67-74`) → `kebutuhan_menu_kg = porsi×gram/1000` | Konversi benar; tetapi pembulatan memakai HALF_EVEN sementara SDC HALF_UP → dua mode pembulatan dalam satu pipeline | AUD-9B-17 |
| U4 | **Menit vs detik vs ms** | ETA menit (`logistics.py:94-95`), `seconds_remaining` detik (`approval_summary.py:249`), `duration_ms`/`latency_ms` ms (`telemetry.py:26`), `horizon_days` + string `"7 hari"` (`workers/demand.py:68`) | `forecast_horizon` adalah **string**, bukan angka → tidak dapat divalidasi/dijumlah; `expiry.seconds_remaining` 2.585.831 detik = 29,9 hari (bukan menit) | AUD-9B-17 |
| U5 | **UTC vs lokal** | `menu_plans` dipilih per tanggal **WIB** (`recommendation_service.py:250`), sedangkan semua `recorded_at`/`as_of` UTC; `demand_needed_by` dikirim `+00:00` | Pukul 00:00–07:00 WIB, "menu hari ini" memakai tanggal yang berbeda dari jendela data UTC | AUD-9B-06 |
| U6 | **Historis vs masa depan** | 720/5.240 `supply_records`, 360/1.360 `demand_records`, 840/5.924 `price_signals`, 100/660 `menu_plans` bertanggal > `now`. `/balance`, `/balance/map`, `recommendation_service` **membatasi** `recorded_at <= as_of`; `/demand`, `/demand/forecast`, `/price`, `/price/quotes`, `demo_cost._harga_satuan` **tidak** | Agent Demand membaca permintaan 4 Nov (532,4 kg) hari ini; agent Price memakai quote 3 Nov (26.655,17) dan referensi 4 Nov (26.856,52) sebagai "terbaru"; SDC e7150da4 memakai quote bertanggal 15:13 — **44 menit setelah keputusan dibuat 14:29** | AUD-9B-06, -08 |
| U7 | **Rencana vs eksekusi** | `menu_plans` (rencana) dipakai sebagai **lantai** kebutuhan padahal `demand_records` adalah fakta; `decisions.status='executed'` vs `can_execute=false` (karena alasan "sudah dieksekusi"); `needed_by` disimpan tetapi **tidak dipakai** pemeriksaan apa pun | Keputusan 3e2e3cc7 memindahkan 300 kg dari Bandung yang **kekurangan 58 kg** (supply 250 < demand 308) → melanggar aturan surplus/kontinuitas pipeline sendiri | AUD-9B-06, -35 |

---

## 5. Temuan

Severity: P0 = merusak klaim inti/keselamatan; P1 = angka salah atau tidak dapat
diaudit pada jalur demo; P2 = salah label/ambang tidak berfungsi; P3 = kebersihan.

| ID | Sev | Status | Temuan | Bukti | Dampak |
|---|---|---|---|---|---|
| AUD-9B-01 | P1 | **FAIL** | `batches.freshness_score` tidak dapat direproduksi dari `core/freshness.compute_freshness_score`: 995ea332 tersimpan **0,69** vs hitung ulang **0,970682** (−28,07 pp). 39 batch `origin='demo'` memakai literal **0,82** (`seed/demo_activity.py:231`); bahkan batch seed yang "mirip" (0,92) menyimpang 1,49 pp dari hitung ulang sekarang | V5; `SELECT freshness_score, origin FROM batches GROUP BY 1,2` | `expected_loss` SDC memakai 0,69 → **overstatement Rp915.878,40** (5,2% SDC); agent Freshness melaporkan skor yang tidak sejalan dengan pipeline rekomendasi untuk batch yang sama |
| AUD-9B-02 | P1 | **FAIL** | `usable_until` bertentangan dengan `freshness_score`: 48 dari 120 batch menyimpang dari `harvested_at + shelf_life × score`, maksimum **75,4 hari**. Contoh 3bc81364: score 0,82 tetapi `usable_until` = panen + 28 hari (score 1,0) | V12 | `expired_count` (agent Freshness) memakai `usable_until` sementara `worst_freshness_score` memakai kolom score → dua jawaban berbeda untuk "apakah batch ini masih layak" |
| AUD-9B-03 | P1 | **FAIL** | `safe_delivered_cost` 3e2e3cc7 (9.750.000,00) tidak sama dengan jumlah rinciannya (9.375.000,00; Δ375.000, 3,85%) dan `cost_breakdown` memakai skema warisan **per kg** `{harga, angkut, risiko}` yang tidak diproduksi `core/safe_delivered_cost`. Harga 28.500 di rincian itu milik **Bogor/telur**, bukan Bandung/ayam | V6; `SELECT ... WHERE price_per_kg=28500` → Bogor/telur; `jsonb_object_keys` → 1 baris skema warisan | Keputusan `pending_approval` dengan rincian biaya yang tidak dapat diaudit; jika disetujui, PO memakai angka yang tidak berasal dari mesin biaya |
| AUD-9B-04 | P1 | **FAIL** | SDC/kg 3e2e3cc7 = 32.500 sedangkan harga beli saja ≥ 35.400/kg (quote sumber) atau 40.300/kg (quote tujuan) → **SDC < komponen beli**, mustahil karena semua komponen non-negatif | V7 | Melanggar invarian `SDC ≥ purchase`; tidak ada pemeriksaan invarian ini di API (`recommendation_numbers.py` hanya memeriksa `cost/quantity` ≤ 5.000.000) |
| AUD-9B-05 | P1 | **FAIL** | Klaim verifier "harga 40% di bawah referensi" (`supplier_quote_ratio 0,60`) tidak cocok data: rasio quote/referensi pada waktu keputusan = **1,0000** (0,00%) untuk Surabaya, Bandung, Jakarta; keputusan keempat 1,0176 (+1,76%) | V9 | `decisions.verifier_note='flagged'` + `evidence.is_consistent=false` untuk alasan yang tidak terbukti; approval terblokir oleh temuan yang tidak dapat direproduksi |
| AUD-9B-06 | P1 | **FAIL** | Jendela waktu tidak seragam: `/demand/{loc}/{com}` (`api/demand.py:81-90`), `/demand/forecast` (`:45-59`), `/price/{loc}/{com}` (`api/price.py:117-128`), `/price/quotes` (`:36-51`), dan `services/demo_cost.py:84-92` tidak membatasi `recorded_at <= now`, sedangkan `/balance` & `recommendation_service` membatasi | U6; hitungan baris masa depan | Agent membaca "terbaru" = baris 3–9 hari ke depan; anomali harga hari ini tidak mungkin terdeteksi; SDC keputusan memakai harga yang belum ada saat keputusan dibuat |
| AUD-9B-07 | P2 | **FAIL** | `POST /price/deviation` tidak pernah berhasil pada keadaan demo: 409 "sesi demo belum aktif" (gerbang `app/main.py:191-204` menolak semua POST non-allowlist). Agent mencatat alasan `endpoint_error`, bukan sebab sebenarnya | Probe e7150da4 & 3e2e3cc7: `deviation_pct=null`, warning HTTP 409 | `deviation_pct`, `classification`, `flagged` kosong pada **semua** review → prioritas "harga janggal" tidak pernah dievaluasi oleh agent |
| AUD-9B-08 | P2 | **FAIL** | Dua agent melaporkan "permintaan" berbeda untuk pasangan sama: Supply 538,0 kg vs Demand 532,4 kg (Δ5,6 kg, 1,04%); Jakarta/ayam 215,0 vs 217,37 (Δ2,37). Penyebab: basis waktu berbeda, bukan data berbeda | Probe + U6 | Pembaca yang menggabungkan kedua agent mendapat dua gap berbeda (shortage 138 vs 132,4) dan tidak ada konflik yang dilaporkan (lihat AUD-9B-26) |
| AUD-9B-09 | P2 | **FAIL** | ETA punya tiga basis: matriks statis 60 km/jam + 30 menit (`core/logistics.py:93-98`), OSRM `road.duration_min` (`/supplier-routes`), dan `logistics_time_min` kandidat (CEILING). Agent Logistics melaporkan 4,7 menit untuk 3,4 km; model produksi 33,4 menit. Filter rute memakai **tujuan** saja (`workers/logistics.py:36-40`), bukan pasangan sumber→tujuan keputusan | V11; probe: `road_source='osrm'`, `min_duration_min=4.7` | Angka "sampai kapan" pada review tidak dapat dipakai untuk keputusan; untuk transfer Bandung→Jakarta agent melaporkan rute 65,6 km (dari pemasok), bukan 150 km (matriks antar-SPPG) |
| AUD-9B-10 | P3 | **FAIL** | `TOLERANSI_RINCIAN = Decimal("0.01")` diberi komentar "toleransi ketidakcocokan" (mutlak) tetapi dipakai sebagai **fraksi** (`selisih > biaya × 0.01`) | `core/recommendation_numbers.py:27-28,104-111` | Mismatch rincian sampai 1% (Rp174.821,78 pada SDC 17,4 juta) lolos validasi |
| AUD-9B-11 | P3 | **FAIL** | Ambang `freshness < 0,60` → penalti 50% **tidak pernah aktif** di dataset demo: `one_minus_fresh_implied` tertinggi 0,31 (freshness 0,69) di 29 keputusan, dan `freshness_risk` = 0,00 di semuanya | SQL V3 + `SELECT DISTINCT freshness_risk` | Cabang biaya paling agresif tidak teruji demo; bila aktif, satu keputusan bisa naik 50% × purchase |
| AUD-9B-12 | P2 | **MISSING** | **Capacity utilization tidak ada** di seluruh sistem: `check_capacity()` (`core/constraints.py:15-25`) tidak punya pemanggil produksi (hanya tes), `capacity_kg_per_week` hanya disimpan/ditampilkan, tidak ada % utilisasi di API/UI | `grep -rn check_capacity` → hanya `tests/` | Klaim "kapasitas" pada narasi tidak punya angka pendukung; utilisasi kapasitas tidak dapat diaudit |
| AUD-9B-13 | P3 | **MISSING** | **`decision time` tidak ada** sebagai metrik. Proksi yang ada: `total_latency_ms` (review), `latency_ms`/`duration_ms` per langkah, TTL `expires_at − created_at`, `seconds_remaining` | `grep -rn "decision_time\|waktu_keputusan"` → 0 hasil | Tidak ada angka "berapa lama keputusan diambil" yang bisa dikutip; yang ada adalah durasi review dan umur approval |
| AUD-9B-14 | P2 | **FAIL** | `score` rekomendasi tidak dipersistensi dan tidak ada di read model mana pun; hanya ada di respons `POST /balance/recommend|analyze` (butuh role mutasi + sesi demo aktif) | `decisions` tidak punya kolom skor; `grep -c` di API read model = 0 | Skor yang tampil di UI tidak dapat diaudit ulang dari DB; setelah sesi berakhir, angka itu tidak dapat direproduksi |
| AUD-9B-15 | P3 | **UNVERIFIED** | `forecast_confidence` = 1,0 pada dua keputusan berbeda (telur & ayam), metode `statistical_fallback`; tidak ada dasar kalibrasi di kode | Probe: `forecast_confidence: 1.0` | Angka keyakinan 100% untuk forecast statistik tidak dapat dipertanggungjawabkan; berpotensi dibaca sebagai "pasti" |
| AUD-9B-16 | P1 | **FAIL** | Tidak ada pemeriksaan kelengkapan bukti: 2 keputusan ber-`SDC` tanpa bukti sama sekali (64ce3369 `proposed`, 3e2e3cc7 `pending_approval`), dan 3 keputusan ber-`SDC` tanpa rincian kanonik (3e2e3cc7, 64ce3369, 5e969ff1 yang berstatus **approved**) | SQL §9.4 | `can_execute` hanya memeriksa `quantity > 0` dan `sdc > 0`, bukan bukti; approval bisa berjalan tanpa bukti (lihat AUD-9B-3x di dokumen orkestrasi) |
| AUD-9B-17 | P3 | **FAIL** | Empat mode pembulatan dalam satu pipeline: HALF_UP (SDC, skor, `_money`), HALF_EVEN default (`menu_hierarchy.py:57,64`), CEILING (`candidate_generation.py:228`), `round()` Python + 3 desimal (`demo_cost.py:181-192`) | `core/*` | Total SDC dapat berbeda 0,01–0,05 antar jalur untuk input sama; sulit direkonsiliasi saat juri menjumlahkan sendiri |
| AUD-9B-18 | P3 | **FAIL** | Angka `numeric` DB dikirim sebagai `float` JSON (`approval_summary.py:397-402`, `balance.py:162-165`) → 17.482.178,40 menjadi `17482178.4`; `Decimal` 2dp hilang di batas API | Probe: `safe_delivered_cost: 17482178.4` | Rekonsiliasi klien (JS) rawan galat pembulatan bila menjumlahkan komponen |
| AUD-9B-19 | P1 | **FAIL** | Angka keamanan punya **dua basis**: read model `approval_summary._safety_view` memakai batch **sumber** (Bandung/ayam: `worst_status=pass`, `blocked=false`, 3 batch), agent Safety memakai batch **tujuan** (Jakarta/ayam: `worst_status=fail`, 1 batch gagal) | Probe 3e2e3cc7: `safety.blocked=false` vs agent `blocking=true` | Dua komponen sistem menyatakan hal berbeda tentang keamanan pengiriman yang sama; agent memveto pengiriman yang read model nyatakan aman (lihat AUD-9B-29) |

---

## 6. Ringkasan status per domain angka

| Domain | Status | Dasar |
|---|---|---|
| Supply/demand/gap | **PASS** (aritmetika) / **FAIL** (basis waktu) | V1 lulus; dua agent melaporkan demand berbeda (AUD-9B-08) |
| Kesegaran | **FAIL** | Skor tidak dapat direproduksi (AUD-9B-01), `usable_until` tidak konsisten (AUD-9B-02) |
| Keamanan | **PASS** (mesin) / **FAIL** (basis & cakupan) | `fail` = hard exclusion benar; agent memakai lokasi salah (AUD-9B-19) |
| Harga | **FAIL** | Masa depan (AUD-9B-06), deviasi tidak pernah dihitung (AUD-9B-07), klaim anomali tidak terbukti (AUD-9B-05) |
| Biaya/SDC | **PASS** (29/32 rincian menjumlah persis) / **FAIL** (3 baris + basis harga) | V2, V10 lulus; AUD-9B-03/-04 |
| Logistik/ETA | **FAIL** | Tiga basis waktu, filter tujuan saja (AUD-9B-09) |
| Kapasitas/utilisasi | **MISSING** | AUD-9B-12 |
| Skor rekomendasi | **FAIL** (tidak dapat diaudit) | AUD-9B-14 |
| Kelengkapan bukti | **FAIL** | AUD-9B-16 |
| Waktu keputusan | **MISSING** | AUD-9B-13 |

---

## 7. Tiga angka yang gagal diverifikasi ulang

1. **`freshness_score` batch `995ea332-1168-5cbc-ac40-002b5d8d2121` = 0,69.**
   Hitung ulang dari `harvested_at` (25 Okt 21:13Z), `shelf_life_days_telur=28`,
   dan `temperature_log` (4,1/4,3/4,6 °C, semua dalam 0–8 °C) menghasilkan
   **0,970682** pada 16:55Z (0,973214 saat batch dibuat, 0,974306 saat keputusan
   dibuat). Selisih **−0,280682 (−28,07 pp)**. Angka 0,69 adalah satu-satunya
   input kesegaran untuk `expected_loss` SDC e7150da4 (Rp1.011.840,00); dengan
   skor hasil hitung ulang, `expected_loss` menjadi Rp95.961,60 (**−90,52%**).
   Status: **FAIL**.

2. **`safe_delivered_cost` keputusan `3e2e3cc7-f53e-5cee-963d-728e87b6b949` = Rp9.750.000,00.**
   Rincian tersimpan `{harga: 28500, angkut: 1800, risiko: 950}` × 300 kg =
   **Rp9.375.000,00** (selisih **Rp375.000,00**, 3,85%). Harga 28.500 itu milik
   **Bogor/telur** (satu-satunya baris dengan nilai tersebut), sedangkan
   keputusan ini Bandung→Jakarta/**ayam**; quote ayam termurah pada waktu
   keputusan Rp35.400/kg (sumber) dan Rp40.300/kg (tujuan) — jadi SDC/kg
   (Rp32.500) bahkan **lebih kecil dari komponen beli saja**. Status: **FAIL**.

3. **Klaim "harga 40% di bawah referensi" pada tiga keputusan `price_anomaly`**
   (`a693308f` Jakarta, `4ee4e0c5` Bandung, `00e276af` Surabaya).
   `decision_evidence.payload.supplier_quote_ratio = 0,60` menyiratkan −40%,
   tetapi rasio quote/referensi dari `price_signals` pada `created_at` keputusan
   adalah **1,0000** (0,00%) untuk ketiganya (keputusan keempat `f45b955c`:
   1,0176 = +1,76%). Selisih **40,0 poin persen**. Status: **FAIL**.

Angka keempat yang perlu disebut meski bukan "gagal hitung": **ETA 4,7 menit**
(basis OSRM, rute pemasok) vs **33,4 menit** (basis model produksi) untuk jarak
yang sama — bukan salah hitung, tetapi salah **artefak** (AUD-9B-09).

---

## 8. Batas audit (yang TIDAK diuji)

- **Rendering UI** per angka tidak diperiksa (hanya pengikatan komponen). Status
  UI di §2 = `UNVERIFIED` bila bukan kutipan kode.
- **`POST /balance/recommend|analyze`** tidak dijalankan: butuh role mutasi +
  sesi demo aktif; skor/`cost_breakdown` produksi baru tidak dapat direproduksi
  dari DB (AUD-9B-14). Yang diaudit adalah 32 keputusan yang sudah tersimpan.
- **`GET /supplier-routes` OSRM** tidak divalidasi terhadap jarak nyata; hanya
  dibandingkan dengan matriks internal.
- **Provider LLM** (`run_verifier`, supervisor narasi) tidak dipanggil; audit ini
  hanya menilai angka. Verdict LLM yang tersimpan di `decisions` diperiksa
  terhadap data, bukan terhadap prompt.
- **Ledger**: `ledger_blocks=2.034` hanya dibaca; validitas rantai hash tidak
  diperiksa ulang di sini (ada di audit lain).

---

## 9. Lampiran: cara reproduksi

### 9.1 Gap dan baris masa depan

```sql
-- V1: supply/demand terbaru yang SUDAH terjadi
with s as (select x.quantity_kg from supply_records x
  join locations l on l.id=x.location_id join commodities c on c.id=x.commodity_id
  where l.name='Bandung' and c.name='telur' and x.recorded_at<=now()
  order by x.recorded_at desc, x.id desc limit 1),
d as (select x.quantity_kg from demand_records x
  join locations l on l.id=x.location_id join commodities c on c.id=x.commodity_id
  where l.name='Bandung' and c.name='telur' and x.recorded_at<=now()
  order by x.recorded_at desc, x.id desc limit 1)
select (select quantity_kg from s) supply, (select quantity_kg from d) demand,
       greatest((select quantity_kg from s)-(select quantity_kg from d),0) surplus,
       greatest((select quantity_kg from d)-(select quantity_kg from s),0) shortage;

-- U6: baris masa depan
select 'supply' t, count(*) filter (where recorded_at>now()) future, count(*) total from supply_records
union all select 'demand', count(*) filter (where recorded_at>now()), count(*) from demand_records
union all select 'price', count(*) filter (where recorded_at>now()), count(*) from price_signals
union all select 'menu', count(*) filter (where plan_date > (now() at time zone 'Asia/Jakarta')::date), count(*) from menu_plans;
```

### 9.2 SDC: jumlah komponen (V2) dan penyimpangan 3e2e3cc7 (V6)

```sql
-- V2: seluruh keputusan yang punya rincian kanonik
select id, safe_delivered_cost,
  ((cost_breakdown->>'purchase')::numeric+(cost_breakdown->>'transport')::numeric
  +(cost_breakdown->>'handling')::numeric+(cost_breakdown->>'expected_loss')::numeric
  +(cost_breakdown->>'freshness_risk')::numeric+(cost_breakdown->>'safety_penalty')::numeric) sum_komponen,
  safe_delivered_cost - ((cost_breakdown->>'purchase')::numeric+(cost_breakdown->>'transport')::numeric
  +(cost_breakdown->>'handling')::numeric+(cost_breakdown->>'expected_loss')::numeric
  +(cost_breakdown->>'freshness_risk')::numeric+(cost_breakdown->>'safety_penalty')::numeric) diff
from decisions where cost_breakdown ? 'purchase';   -- 29 baris, diff = 0.00 semua

-- V6: skema per-kg
select quantity_kg, safe_delivered_cost,
  ((cost_breakdown->>'harga')::numeric+(cost_breakdown->>'angkut')::numeric+(cost_breakdown->>'risiko')::numeric) per_kg,
  ((cost_breakdown->>'harga')::numeric+(cost_breakdown->>'angkut')::numeric+(cost_breakdown->>'risiko')::numeric)*quantity_kg total_per_kg,
  safe_delivered_cost/quantity_kg sdc_per_kg
from decisions where id='3e2e3cc7-f53e-5cee-963d-728e87b6b949';
-- per_kg 31250 | total_per_kg 9375000.00 | sdc 9750000.00 | sdc_per_kg 32500
```

### 9.3 Kesegaran (V5, V12)

```sql
with b as (
  select bt.id, bt.freshness_score s, bt.harvested_at, bt.usable_until, c.name kom,
         case c.name when 'telur' then 28.0 when 'ayam' then 5.0
                      when 'wortel' then 21.0 else 180.0 end sl
  from batches bt join commodities c on c.id=bt.commodity_id)
select id, s,
  round((greatest(0, 1 - (extract(epoch from (now()-harvested_at))/86400.0)/sl))::numeric,6) base_score_now,
  round((s - (greatest(0, 1 - (extract(epoch from (now()-harvested_at))/86400.0)/sl)))::numeric,6) diff,
  extract(epoch from (usable_until - (harvested_at + (sl*s) * interval '1 day')))/86400.0 usable_minus_formula_days
from b order by abs(s - (greatest(0, 1 - (extract(epoch from (now()-harvested_at))/86400.0)/sl))) desc;
-- 48/120 baris usable_minus_formula_days != 0; maks 75.433 hari
```

Catatan: `base_score_now` di atas adalah batas atas (penalti suhu 0). Untuk
995ea332 penalti memang 0 karena semua sampel 4,1–4,6 °C di rentang 0–8 °C,
sehingga nilai itu **adalah** skor sebenarnya.

### 9.4 Bukti dan rincian yang hilang (AUD-9B-16)

```sql
select count(*) filter (where safe_delivered_cost is not null) sdc_ada,
       count(*) filter (where safe_delivered_cost is not null
                        and (cost_breakdown is null or not (cost_breakdown ? 'purchase'))) tanpa_rincian_kanonik
from decisions;   -- 32 sdc, 3 tanpa rincian kanonik (satu di antaranya approved)
```

### 9.5 Probe review live (angka di §3 berasal dari sini)

`agent/orchestrator.run_review` dijalankan dari host terhadap backend
`localhost:8000` dengan token baca `bgn_monitor` (nilai token tidak dicetak):

```
$ python probe_review.py e7150da4-cb4b-5b46-a380-6fccbeaa3dc9
status partial  veto True
supply    ok  {supply_kg: 400.0, demand_kg: 538.0, shortage_kg: 138.0, status: shortage}
demand    ok  {quantity_kg: 532.4, forecast_qty_kg: 3734.962, forecast_confidence: 1.0}
freshness ok  {batch_count: 3, worst_freshness_score: 0.69, expired_count: 0}
safety    ok  {pass: 3, fail: 0, active_exclusion_count: 1}  blocking=True
price     degraded {quotes: 12, latest: 26655.17, ref: 26856.52, deviation_pct: null,
                    reason: endpoint_error (HTTP 409)}
logistics ok  {routes: 3, min_distance_km: 3.4, min_duration_min: 4.7, source: osrm}
evidence  ok  {evidence_count: 5, approval_count: 2, trace_count: 4, ledger_blocks: 2034}
verify    flag: narasi_tidak_menyebut_penurunan (worker price tidak utuh)
```

Konsumen angka: `AgentTraceViewer.tsx` (step/summary/duration),
`RecommendationCard.tsx:167-169` (kg, SDC), `ApprovalModal.tsx` (SDC, countdown),
`FoodSafetyBoard.tsx:346-347` (kesegaran %, `usable_until`),
`StockChart.tsx:45-46` (surplus/shortage), `IntegrityPanel` (`ledger_blocks`).
