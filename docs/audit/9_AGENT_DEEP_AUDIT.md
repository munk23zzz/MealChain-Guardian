# 9_AGENT_DEEP_AUDIT — MealChain Guardian

Status: **audit mendalam berbasis kode + runtime** — 26 Oktober 2026, HEAD `57db099`.
Lingkungan: stack berjalan (`mealchain-backend` :8000, `mealchain-postgres` :15432 db `mealchain`,
frontend :3010). DB demo **hanya SELECT**. Tidak ada kode/DB yang diubah.
Ruang lingkup: identitas 9 peran agent, membedakan **deterministik vs LLM vs tool call vs worker**.
Pipeline DETECT→…→LEARN sudah diaudit di `AGENT_WORKFLOW_AUDIT.md`; dokumen ini tidak mengulanginya.

Pasangan: `9_AGENT_INVENTORY.md` (tabel peran + jumlah aktual).

---

## 0. Ringkasan temuan

| ID | Severity | Temuan singkat | Status |
|---|---|---|---|
| AUD-9A-01 | **P2** | Baris `SUPERVISE` pada putaran review adalah **template string**, bukan LLM/agent — padahal UI menyebut "Ringkasan supervisor" | FAIL |
| AUD-9A-02 | **P2** | 9 baris review **tidak pernah tersimpan** di DB demo (0 baris ber-`run_id`, 0 `SUPERVISE`); klaim "review 9 agen" tak punya bukti terekam | FAIL |
| AUD-9A-03 | **P1** | Verifier LLM berbagi **runtime + model + system prompt** dengan Supervisor; verdict `CONSISTENT` diberikan untuk freshness 0,82 (ambang certified: needs_verification) | **SEBAGIAN** — auditor lapis agent kini punya prompt + fakta sendiri (lihat §AUD-9A-03 "Status"); endpoint `/actions/{id}/verify` masih berbagi runtime/prompt |
| AUD-9A-04 | **P2** | Safety Guardian memveto berdasarkan daftar exclusion **global**, tidak di-scope ke keputusan; `GET /supplier-exclusions/context/{decision_id}` yang dideklarasikan tidak dipakai | FAIL |
| AUD-9A-05 | **P1** | Freshness Guardian tidak memakai ambang certified (PASS ≥0,85); batch skor 0,82 dilaporkan `ok` tanpa verdict `needs_verification`, `blocking=False` | FAIL |
| AUD-9A-06 | **P2** | Price & Logistics bergantung pada `POST` komputasi yang diblokir gerbang sesi demo (409) dan role guard (403) → degradasi permanen di luar sesi demo | FAIL |
| AUD-9A-07 | **P2** | Jalur 8 agent bergantung pada URL **quick tunnel** Cloudflare dan JWT agen ber-`exp` 2026-11-17 — bukan dependensi tetap | BLOCKED (risiko) |
| AUD-9A-08 | **P2** | Narasi supervisor memuat angka di luar konteks orkestrator (780 vs 685) dan menyebut "aman (PASS)" untuk freshness 0,82 | FAIL |
| AUD-9A-09 | **P2** | Forecast di jalur agent **selalu** statistik (`statistical_forecast`), bukan SAP-RPT; `confidence` = min(1, n/3) sehingga selalu 1.0 | FAIL |
| AUD-9A-10 | **P2** | Supply dan Demand melaporkan "permintaan" berbeda (1080 vs 1074,11 kg) dan Evidence Fusion tidak mendeteksinya | FAIL |
| AUD-9A-11 | P3 | `agent/hierarchy.json` (endpoint, stage verifier) menyimpang dari kode; `LANES` ganda (registry vs orchestrator) | FAIL |
| AUD-9A-12 | P3 | Verifier worker deterministik hanya **mewariskan** verdict gerbang; model tidak pernah dipasang (`model=None`) | PARTIAL |
| AUD-9A-13 | P3 | Gerbang `verify_run` memberi `flag` karena kata kunci tidak ada di narasi veto (salah tuduh) | FAIL |
| AUD-9A-14 | P3 | `agent/registry.py:42` berbunyi "tepat tujuh agent" padahal 8; docstring "tujuh worker" vs 8 kelas | FAIL |
| AUD-9A-15 | P3 | Uji worker memakai API double → jalur auth/sesi/peran (409/403) tidak pernah teruji; satu-satunya kegagalan live justru 409 | FAIL (coverage) |
| AUD-9A-16 | P3 | Tool call LLM (Supervisor) tidak terekam di jejak mana pun | UNVERIFIED |
| AUD-9A-17 | P3 | `StubWorker` P1 masih diekspor & dipakai tes; berisiko tertukar dengan worker nyata | STUB |
| AUD-9A-18 | P3 | Kolom `agent_traces.agent_name` di dataset demo berisi label template (`detection_agent`, `supervisor_agent`) | FAIL (data) |
| AUD-9A-19 | — | Definisi resmi "9 agen" (8 agent + 1 ringkasan) harus diputuskan pemilik produk untuk narasi juri | NEEDS_PRODUCT_DECISION |

Severity: **P1** = klaim inti/keselamatan tidak terpenuhi; **P2** = perilaku menyimpang/menyesatkan;
**P3** = kualitas kode/dokumentasi/coverage.

---

## 1. Supervisor

**Tanggung jawab.** (a) Meringkas putaran keputusan untuk reviewer manusia; (b) pada putaran review,
menutup 9 baris trace dengan ringkasan.

**Input.** (a) `outcome_ctx` dari `event1_orchestrator` (`commodity`, `surplus`, `shortage`,
`verifier_verdict`, `forecast`, `chosen`) — `backend/app/services/event1_orchestrator.py:332-342`;
(b) `AgentRun` yang sudah jadi (findings + contradictions + verification).

**Processing.**
- (a) `_build_prompt` → JSON, lalu `with_fallback_chain` (primary = slot pertama rantai env) —
  `backend/app/services/supervisor_client.py:36-50,94-102`.
- Rantai aktual diukur: `['primary:agentcore', 'fallback_1:sap_ai_core', 'fallback_2:bedrock', …]`
  (`backend/app/ai_providers/model_registry.py:123-125` **menambahkan ARN AgentCore sebagai primary**
  untuk supervisor, verifier, **dan** forecast).
- Di dalam runtime: `_handle_prompt` → `_narasi` → `build_agent(MODEL_ID)` → Strands + `BedrockModel` +
  4 tool baca (`agent/runtime_server.py:44-51,89-104`; `agent/supervisor_agent.py:84-95`).
- (b) Pada putaran review, "narasinya" adalah **string template** `_narrative()` di
  `agent/orchestrator.py:190-212` — dipilih berdasarkan `safety_veto`/`status`.

**Output.** `SupervisorResult(status, summary, provider, fallback_used, attempts)`;
baris trace `SUPERVISE` dengan `agent_name="supervisor"`, `tool_called="agent.review_summary"`
(`agent/telemetry.py:79-109`).

**Error handling.** Tanpa chain → `status="unavailable"` (bukan karangan); semua provider gagal →
`unavailable` + `attempts`; output tak terbaca → `status="error"`; keputusan tetap lahir
(`backend/app/services/supervisor_client.py:84-110`). Pada putaran review, kegagalan narasi tidak
mungkin terjadi karena narasi adalah template.

**Testing.** `backend/tests/test_supervisor_narration.py` (4 tes), `test_supervisor_agent.py` (6),
`test_supervisor_tools.py`. Semua memakai provider/Strands tiruan; tidak ada tes integrasi runtime nyata.

**Bukti runtime (read-only).**
```
run_supervisor(ctx, timeout_seconds=90)
→ status: narrated | provider: primary:agentcore | fallback: False | 6.7s
  attempts: [('primary','succeeded',None)]
  summary: "... Cianjur (surplus 685 kg) ke Jakarta (kekurangan 780 kg) ... Cianjur memiliki 3 batch
            aman (PASS) dengan kesegaran minimal 0.82 ... Verdict verifier: FLAGGED ..."
```

### AUD-9A-01 (P2, FAIL) — baris SUPERVISE di review adalah template
- Bukti: `agent/orchestrator.py:190-212` (`_narrative` mengembalikan string tetap), `:286`
  (`run.model_copy(update={"narrative": _narrative(run)})`), `agent/telemetry.py:79-109`.
- Runtime: baris SUPERVISE pada review = "Review 7 agen menemukan guardian yang memblokir…" (persis
  salah satu cabang template `orchestrator.py:191-196`).
- Dampak: UI menampilkan "Ringkasan supervisor" (`frontend/components/AgentSwarmPanel.tsx:117-120`)
  padahal tidak ada model yang menulisnya pada jalur review. LLM supervisor hanya hidup di Event 1.
- Tidak salah secara keamanan (template deterministik justru lebih aman), tetapi **atribusi**-nya salah.

### AUD-9A-08 (P2, FAIL) — narasi LLM memuat angka di luar konteks & mengklaim "aman"
- Bukti kode: konteks supervisor hanya `surplus/shortage` yang dikirim orkestrator
  (`event1_orchestrator.py:332-342`); tetapi agent punya tool `get_supply_demand`
  (`agent/tools.py:95-116`) sehingga model dapat mengambil angka lain sendiri.
- Bukti runtime: konteks uji berisi `shortage.quantity_kg = 685`, narasi menulis **"kekurangan 780 kg"**
  (angka 780 = `shortage_kg` dari worker Supply / `/balance`). Narasi juga menulis
  **"3 batch aman (PASS) … kesegaran minimal 0.82"** padahal ambang certified PASS adalah ≥0,85
  (`backend/app/core/freshness.py:7-8,53-57`) → 0,82 = `needs_verification`.
- Dampak: angka & kata "aman" pada narasi **tidak dapat direproduksi** dari jejak keputusan dan
  bertentangan dengan gerbang certified. Tidak membuka approval (verdict tetap penentu), tetapi
  dibaca manusia/juri sebagai ringkasan hasil audit.
- Rekomendasi: larang tool call pada jalur narasi ATAU rekam tool call + angka yang dipakai ke
  `agent_traces`; ganti kata "aman" dengan status hasil gate.

### AUD-9A-16 (P3, UNVERIFIED) — tool call supervisor tidak terekam
Tidak ada jejak tool (nama, argumen, hasil) untuk panggilan LLM: `agent/tools.py` tidak menulis apa pun,
`SupervisorResult` hanya menyimpan provider/attempts (`supervisor_client.py:26-33`).
Akibatnya klaim "agent memakai tool" tidak dapat dibuktikan/diaudit dari data, hanya dari kode.

---

## 2. Supply Agent

**Tanggung jawab.** Membaca saldo satu (lokasi, komoditas) dan melaporkan supply/demand/surplus/shortage.
**Input.** `WorkerContext{location, commodity, api}` dari `approval-summary`
(`agent/orchestrator.py:37-57`).
**Processing.** `GET /balance/{loc}/{com}`; **tidak menghitung ulang** gap — gap hanya dipakai bila
`data_state=="terukur"` dan kedua angka ada (`agent/workers/supply.py:47-55`). Angka `null` tidak
diganti 0; `bool` bukan angka (`agent/workers/base.py:173-189`).
**Output.** `AgentFinding(stage=DETECT, facts{supply_kg,demand_kg,surplus_kg,shortage_kg,…},
citations[])`; setiap angka wajib punya sitasi dengan nilai identik
(`agent/contracts.py:129-158`).
**Error handling.** 404 → `degraded` dengan semua angka `None` + `data_state="tidak_ada_baris"`;
error lain → `error`; tanpa `api` → `AgentApiError("missing_config…")` (`supply.py:22-41`,
`base.py:49-55`).
**Testing.** `test_agent_workers.py::supply_*` (3 tes: sitasi, null≠0, 404).
**Runtime.** `ok` — `supply_kg 300.0, demand_kg 1080.0, surplus_kg 0.0, shortage_kg 780.0`, latency 471 ms.

Tidak ada temuan khusus untuk agent ini; silang ke AUD-9A-10.

---

## 3. Demand Agent

**Tanggung jawab.** Permintaan terkini + forecast 7 hari.
**Input.** `WorkerContext`; `GET /demand/{loc}/{com}`, `GET /demand/forecast/{loc}/{com}?horizon_days=7`.
**Processing.** Tidak menghitung; hanya meneruskan angka + `forecast_method`
(`agent/workers/demand.py:24-58`). Bila demand 404 tapi forecast ada → `degraded` (bukan error),
dan sebaliknya (`demand.py:35-53`).
**Output.** `facts{quantity_kg, needed_by, forecast_qty_kg, forecast_method, forecast_confidence,
forecast_horizon}`.
**Error handling.** 404 → warning + angka `None`; error non-404 → `error` bila demand juga tidak ada.
**Testing.** `test_agent_workers.py::demand_*` (2 tes).
**Runtime.** `ok` — `quantity_kg 1074.11`, `forecast_qty_kg 7509.76`, `forecast_method statistical_fallback`,
`forecast_confidence 1.0`, latency 827 ms.

### AUD-9A-09 (P2, FAIL) — forecast jalur agent selalu statistik; "confidence" menyesatkan
- Bukti kode: `backend/app/api/demand.py:34-68` memanggil `statistical_forecast(...)` langsung —
  **tidak** lewat `run_forecast`/rantai provider. Jadi SAP-RPT-1.6 (`FORECAST_MODEL=sap-ai-core:rpt`)
  tidak pernah dipakai pada jalur agent; SAP-RPT hanya di Event 1 (`event1_orchestrator.py:265-271`).
- Bukti angka: `confidence = min(1.0, len(recent)/3)` (`backend/app/core/forecasting_fallback.py:41-47`)
  → dengan ≥3 titik historis **selalu 1.0**. Runtime menampilkan `forecast_confidence: 1.0`.
- Dampak: angka berlabel "confidence" dibaca sebagai keyakinan model, padahal itu proksi jumlah data.
  Tidak memengaruhi keputusan (PREDICT tidak dipakai DECIDE — AG-02), tetapi menyesatkan bila dikutip.

---

## 4. Freshness Guardian

**Tanggung jawab.** Kesegaran batch pada (lokasi, komoditas) + risiko kedaluwarsa.
**Input.** `GET /batches` **dengan paginasi** (`agent/api_client.py:68-97`; plafon 5.000 baris).
**Processing.** Filter di memori per lokasi+komoditas, hitung `batch_count`, `expired_count`
(`usable_until <= now`), `worst_freshness_score = min(scores)` (`agent/workers/freshness.py:56-91`).
**Output.** `facts{batch_count, expired_count, worst_freshness_score, earliest_usable_until,
expired_batch_ids}`; `blocking = expired_count > 0` (`freshness.py:118`).
**Error handling.** 404 → `degraded` semua `None`; `usable_until` tak terbaca dihitung + jadi warning;
daftar kosong = `degraded` (bukan "aman").
**Testing.** `test_agent_workers.py::freshness_*` (2 tes: batch kedaluwarsa, daftar kosong). **Tidak ada**
tes untuk klasifikasi PASS/NEEDS_VERIFICATION/FAIL.
**Runtime.** `ok` — `3 batch; 0 kedaluwarsa; skor kesegaran terburuk 0.82`, `blocking=False`.

### AUD-9A-05 (P1, FAIL) — Guardian tidak memakai gerbang kesegaran certified
- Ambang certified: `PASS_THRESHOLD=0.85`, `VERIFY_THRESHOLD=0.60`, `classify_freshness()`
  (`backend/app/core/freshness.py:7-8,44-57`).
- Worker: skor 0,82 → hanya **warning** ("belum sempurna, jangan menyimpulkan aman") dan **status `ok`**
  dengan `blocking=False` (`agent/workers/freshness.py:111-139`). Worker tidak pernah menghasilkan
  verdict `needs_verification` — status itu tidak ada di kosakata worker.
- Runtime terbukti: `worst_freshness_score 0.82` → `status ok`. Menurut gerbang certified, 0,82
  adalah **needs_verification** (0,60 ≤ 0,82 < 0,85).
- Dampak: Guardian yang seharusnya paling konservatif justru melaporkan "ok" untuk batch yang
  menurut aturan resmi belum lolos; `blocking` hanya menyala bila batch **sudah** kedaluwarsa
  (skor 0,30 pun tidak memblokir selama `usable_until` belum lewat).
- Rekomendasi: panggil `classify_freshness()` (atau endpoint `POST /freshness/evaluate`) dan
  set `blocking=True` untuk `fail`/`needs_verification`.

---

## 5. Safety Guardian

**Tanggung jawab.** Status keamanan batch + exclusion pemasok.
**Input.** `GET /batches` (paginasi), `GET /supplier-exclusions`.
**Processing.** Hitung `pass/pending/fail`, `worst_status`, lalu ambil **seluruh** exclusion berstatus
`active` dari daftar global (`agent/workers/safety.py:55-89`).
**Output.** `blocking = fail>0 OR active_exclusion_count>0` (`safety.py:126`).
**Error handling.** 404 batch → `degraded` semua `None`; exclusion gagal dibaca → warning +
`active_exclusion_count=None` dan `degraded` (tidak menyimpulkan aman).
**Testing.** `test_agent_workers.py::safety_*` (2 tes).
**Runtime.** `ok` tetapi **`blocking=True`** — `3 batch: 3 pass, 0 pending, 0 fail; exclusion aktif 1`.

### AUD-9A-04 (P2, FAIL) — veto safety tidak di-scope ke keputusan
- Bukti kode: `agent/workers/safety.py:75` memanggil `/supplier-exclusions` (daftar global) lalu
  menghitung semua `status=="active"` (`:79-86`); tidak ada penyaringan per supplier/lokasi/decision.
  Endpoint yang **dideklarasikan** untuk itu — `GET /supplier-exclusions/context/{decision_id}`
  (`agent/hierarchy.json:47`) — tidak pernah dipanggil.
- Bukti data (SELECT): keputusan `a693308f…` bertipe `price_anomaly`, **`supplier_id` NULL**,
  asal Cianjur → Jakarta, komoditas telur. Satu-satunya exclusion aktif di DB adalah
  `55bb6ed8…` untuk supplier **CV Ambarawa Telur Utama**, scope **Jakarta**.
- Akibat terukur: putaran review menulis `safety_veto=True`, narasi "JANGAN EKSEKUSI keputusan ini",
  padahal status keamanan batch `pass` dan keterkaitan exclusion ke keputusan tidak dapat dibuktikan
  (supplier keputusan tidak diketahui).
- Arah kesalahan adalah *over-blocking* (aman), tetapi secara semantik **veto tidak dapat
  dipertanggungjawabkan**: exclusion pemasok lain memblokir keputusan yang tidak menyebut pemasok itu.
- Rekomendasi: pakai endpoint konteks per keputusan; bila supplier `unknown`, hasilkan
  `needs_verification` (bukan `blocking`) + alasan eksplisit.

---

## 6. Price Agent

**Tanggung jawab.** Quote terbaru, harga referensi, deviasi kanonik, SDC, kelayakan eksekusi.
**Input.** `GET /price/quotes/{loc}/{com}`, `GET /price/{loc}/{com}`, `POST /price/deviation`,
`GET /decisions/{id}/approval-summary` (`agent/workers/price.py:31-35`).
**Processing.** Tidak menjumlah ulang rumus: deviasi dihitung endpoint, SDC dibaca dari read model
(`price.py:1-5,91-138`). Alasan deviasi tidak tersedia dibedakan eksplisit
(`data_missing` / `role_read_only` / `endpoint_error`).
**Output.** `facts{quote_count, latest_quote_price, reference_price, deviation_pct, classification,
flagged, safe_delivered_cost, quantity_kg, can_execute, valid, supplier_name}`.
**Error handling.** 404 quotes → `degraded` semua `None`; 403 deviasi → `degraded` + alasan peran;
supplier tak dikenal → warning `supplier_unknown`, **tidak ditebak**; `degraded` bila salah satu dari
6 kondisi (`price.py:192-199`).
**Testing.** `test_agent_workers_p3.py::price_*` (6 tes, termasuk 403 dan supplier unknown).
**Runtime.** **`degraded`** — `deviasi tidak tersedia`; `deviation_unavailable_reason="endpoint_error"`;
warning: `HTTP 409 pada /price/deviation: {"detail":"sesi demo belum aktif atau sudah kedaluwarsa … aksi tulis ditolak"}`;
`supplier_name: null`; SDC 15.749.032,38; `can_execute: false`.

### AUD-9A-06 (P2, FAIL) — komputasi read-only diblokir gerbang "aksi tulis" sesi demo
- Bukti kode: middleware `_konteks_sesi_demo` menolak **semua** metode POST/PUT/PATCH/DELETE saat tidak
  ada sesi demo aktif, kecuali 7 path di `_JALUR_TANPA_SESI` (`backend/app/main.py:156-167,191-204`).
  `POST /price/deviation` dan `POST /logistics/estimate` **tidak** ada di daftar itu, padahal keduanya
  komputasi murni (tidak menulis DB — `backend/app/api/price.py:150-156`).
- Bukti runtime: deviasi tidak pernah terhitung pada review di luar sesi demo (HTTP 409 di atas).
- Lapis kedua: `POST /logistics/estimate` dijaga `require_roles(*MUTATING_ROLES)`
  (`backend/app/api/logistics.py:23`), sedangkan token agen ber-role **`bgn_monitor`** (read-only) →
  estimasi akan 403 walau sesi aktif. Jalur estimasi hanya terpakai bila tidak ada rute aktif
  (`agent/workers/logistics.py:149-158`), sehingga kini `UNVERIFIED` di runtime tapi pasti gagal
  secara kode.
- Dampak: dua dari tujuh worker analitik kehilangan satu-satunya sumber angka penting
  (deviasi harga) di lingkungan normal; "Price Agent" praktis selalu `degraded`.
- Rekomendasi: masukkan endpoint komputasi murni ke allowlist sesi (atau pindahkan ke `GET`),
  dan turunkan guard peran untuk `/logistics/estimate` menjadi `get_current_user`.

---

## 7. Logistics Agent

**Tanggung jawab.** Rute aktif + jarak/durasi/kelayakan.
**Input.** `GET /supplier-routes?commodity&location&limit=50`; `POST /logistics/estimate` bila tidak ada rute.
**Processing.** Filter rute per tujuan+komoditas; statistik jarak/durasi hanya dari rute ber-geometri
jalan; estimasi hanya bila `source_location` + `quantity_kg>0` tersedia (`logistics.py:24-60,149-158`).
**Output.** `facts{route_count, with_road_count, min/max_distance_km, min/max_duration_min, road_source}`.
**Error handling.** Respons tanpa `routes` → `error`; rute tanpa geometri → `degraded`;
tanpa sumber/kuantitas → `degraded` dengan alasan (`logistics.py:31-33,232-255`).
**Testing.** `test_agent_workers_p3.py::logistics_*` (3 tes, termasuk estimasi Makassar).
**Runtime.** `ok` — `3 rute; 3 bergeometri; 22.0–23.1 km; 21.3–22.4 menit; road_source osrm`.

Temuan: lihat AUD-9A-06 (jalur estimasi).

---

## 8. Evidence Fusion Agent

**Tanggung jawab.** Merangkum bukti: dossier, compliance, chain, approval, ledger.
**Input.** `GET /decisions/{id}/dossier`, `/compliance`, `/chain`, `/approval-summary`, `/ledger/verify`.
**Processing.** Menghitung jumlah evidence/approval/trace, evidence tidak konsisten, status ledger,
status tanda tangan; **tidak** memanggil `/decisions/{id}/traces` (memakai `compliance.traces`).
**Output.** `blocking = ledger tidak valid OR inconsistent>0 OR signature invalid` (`evidence.py:184-188`).
**Error handling.** dossier/compliance gagal → `error` (keras, karena inti bukti); chain/approval/ledger
gagal → warning + `degraded` (`evidence.py:32-62`).
**Testing.** `test_agent_workers_p3.py::evidence_*` (5 tes).
**Runtime.** `ok` + `blocking=True` — `evidence 1, approval 0, trace 2, chain 1; ledger valid;
tanda tangan signed`; `inconsistent_evidence_count 1`; `ledger_blocks 2034`; `can_execute false`.

Catatan kejujuran: `ledger_blocks`/`ledger_valid` berasal dari `/ledger/verify` **global**
(seluruh ledger 2.034 blok), bukan verifikasi khusus keputusan ini — angka itu tidak boleh dikutip
sebagai "bukti keputusan ini masuk ledger".

---

## 9. Independent Verifier

Ada **tiga** hal berbeda yang memakai nama "verifier" — ini sumber kebingungan utama:

| Entitas | Sifat | Bukti | Dipakai kapan |
|---|---|---|---|
| `run_verifier` (LLM) | LLM, verdict `CONSISTENT/FLAGGED/UNAVAILABLE` | `backend/app/ai_providers/verifier_client.py:105-196` | Event 1 (`event1_orchestrator.py:162`), `POST /actions/verify` |
| `verify_run` (gerbang) | deterministik, `pass/flag` | `agent/verify.py:18-65` | setiap putaran review (`orchestrator.py:289`) |
| `VerifierWorker.audit` | deterministik, menilai `AgentRun` | `agent/workers/verifier.py:71-124` | setiap putaran review (baris trace ke-8) |

**Input VerifierWorker.** `run.verification` + daftar finding non-OK. **Bukan** data baru, **bukan**
hitungan ulang. **Output.** `AgentFinding(stage=VERIFY, blocking selalu False)`.
**Error handling.** `verification is None` → `degraded` "belum dinilai" (tidak mengaku lolos);
model opsional gagal → diabaikan (`verifier.py:76-87,60-67`).
**Testing.** `test_agent_verifier.py` (6), `test_agent_verify.py` (4), `test_verifier_client.py` (8),
`test_s4_verifier_independence.py` (5), plus `test_verifier_safety_guard.py`,
`test_verifier_tidak_bisa_diulang.py`, `test_verifier_verdict_recorded.py` (total ≥23).

**Bukti runtime (LLM).**
```
run_verifier(ctx{... freshness_score: 0.82 ...}, timeout_seconds=90)
→ verdict: CONSISTENT | provider: primary:agentcore | fallback: False | 5.6s
  reason: "Safety PASS dengan freshness 0.82 mendukung distribusi; … narasi audit selaras …"
```

### AUD-9A-03 (P1, FAIL) — Verifier LLM tidak independen dari Supervisor
1. **Rantai sama.** `get_agent_chain("verifier")` dan `("supervisor")` sama-sama diawali slot
   `agentcore` karena `AGENTCORE_RUNTIME_ARN` terisi (`backend/app/ai_providers/model_registry.py:123-125`).
   Diukur: `verifier -> [('agentcore','…supervisor_agent-1tWqipEGjw'), ('sap_ai_core','llm'), …]`.
   Nama runtime-nya sendiri: **`mealchain_supervisor_agent`**.
2. **Model & system prompt sama.** Runtime menjalankan `build_agent(MODEL_ID)` dengan
   `SUPERVISOR_AGENT_MODEL = us.anthropic.claude-haiku-4-5-20251001-v1:0` dan
   `load_system_prompt()` = `agent/prompts/supervisor_system_prompt.md`
   (`agent/runtime_server.py:39-51,89-104`). Prompt verifier hanya ditempel sebagai teks user
   (`verifier_client.py:120-121`), bukan system prompt.
3. **Bukti perilaku.** Untuk `freshness_score = 0.82` — yang menurut `core/freshness.py:7-8` adalah
   `needs_verification` — verifier LLM mengembalikan **CONSISTENT** dengan alasan
   "freshness 0.82 mendukung distribusi".
4. **Guard hanya menangkap satu kasus.** `enforce_verifier_guard` menaikkan CONSISTENT→FLAGGED hanya
   bila `safety_status == "FAIL"` (`verifier_client.py:86-102`); `freshness_score` tidak diperiksa sama sekali.
5. **Yang diuji selama ini** adalah independensi *asal verdict* (bukan dari klien browser) —
   lihat docstring `backend/tests/test_s4_verifier_independence.py:1-9`. Independensi **model**
   tidak pernah diuji.

Dampak: klaim "Independent Verifier / penilai independen" tidak terpenuhi pada konfigurasi sekarang;
penilai dan penulis narasi adalah model & prompt yang sama. Ini tidak otomatis membuka eksekusi
(approval tetap butuh role + empat mata), tetapi menghapus nilai audit yang dijual produk.
Rekomendasi: slot model verifier **tanpa** ARN AgentCore supervisor (mis. langsung `sap-ai-core:llm`
dengan system prompt verifier), atau runtime terpisah.

**Status 27 Okt 2026 — SEBAGIAN diperbaiki (lapis agent).**

Auditor lapis agent (`agent/workers/verifier.py`) sekarang:

1. punya **system prompt sendiri** (`agent/prompts/verifier_system_prompt.md`) yang menyatakan
   klaim supervisor bukan fakta dan melarang verifier menghitung/menaikkan verdict;
2. **membaca fakta sendiri** lewat toolset baca-saja `agent/verifier_facts.py` →
   `GET /decisions/{id}/audit-facts` (dihitung `backend/app/services/audit_facts.py` dari
   `recommendation_numbers`, `supplier_eligibility`, `core/freshness`,
   `supplier_exclusion_service`, ledger) + `GET /approval-summary`;
3. mengeluarkan **JSON tervalidasi** (`agent/verifier_contracts.py`) dengan `verdict`
   (`consistent|flagged|unavailable`), `checks[]`, `citations[]`; output tidak sah → `unavailable`;
4. dijaga **guard deterministik** pasca-LLM (`jaga_verdict`) — `consistent` turun menjadi
   `flagged` bila ada cek gagal / tanpa sitasi / gerbang `flag`; model tidak bisa menaikkan;
5. menyimpan jejak dengan **`run_id` sendiri + `parent_run_id`** (run induk) dan sitasi, lewat
   migrasi `039_agent_trace_parent_run_id` dan `persist_agent_review`.

Red-team terukur (klaim palsu yang sama, model diminta `consistent`): SDC ≠ Σ rincian,
batch `safety_status='fail'`, `decision_evidence` hilang, angka tanpa sumber, dan freshness
0,82 diklaim aman — **semua** `ok/pass` pada kode lama, **semua** `flagged/degraded` sekarang
(`backend/tests/test_agent_verifier_independence.py`, 14 tes).

**Masih terbuka:** endpoint `POST /actions/{decision_id}/verify`
(`backend/app/ai_providers/verifier_client.py`) tetap memakai runtime + prompt supervisor
(`get_agent_chain("verifier")` → slot `agentcore` supervisor). Perbaikan ini tidak menyentuh
jalur itu, jadi klaim "penilai independen" untuk endpoint tersebut **belum** benar.
Independensi model juga belum penuh: `VERIFIER_AGENT_MODEL` boleh kosong dan jatuh ke
`SUPERVISOR_MODEL_PRIMARY` — yang independen adalah prompt, sumber fakta, dan cek deterministik.

### AUD-9A-12 (P3, DIPERBAIKI 27 Okt 2026) — auditor kini membaca fakta sendiri
Status lama: `VerifierWorker.audit` memakai `run.verification` apa adanya dan `model` tidak
pernah dipasang di produksi, jadi "agent ke-8" adalah presenter verdict.

Sesudah perbaikan: verifier mengambil fakta sendiri (`/decisions/{id}/audit-facts` +
`/approval-summary`), menjalankan 8 cek deterministik, memvalidasi JSON model, dan menjaga
verdict lewat `jaga_verdict`. `build_workers()` memasang model dari `VERIFIER_AGENT_MODEL`
(cadangan `SUPERVISOR_MODEL_PRIMARY`); tanpa model, verifier tetap menandai (`flagged`) bila
cek gagal dan menjawab `unavailable` bila semua lulus — `consistent` tidak pernah dikarang.
`blocking` tetap `False` dan status/veto run tetap dihitung dari worker analitik.

### AUD-9A-13 (P3, FAIL) — gerbang salah tuduh pada narasi veto
Runtime: `verification.reasons = ["narasi_tidak_menyebut_penurunan: worker price tidak utuh tetapi
narasi tidak menyebutnya"]` ketika narasi justru berbunyi "Review 7 agen menemukan guardian yang
memblokir. JANGAN EKSEKUSI…". Penyebab: pemeriksaan hanya mencari kata kunci
(`agent/verify.py:39-63`) dan narasi veto tidak memuat kata "degraded/sebagian/gagal/…".
Efeknya hanya `flag` (tidak memveto), tetapi menghasilkan temuan audit palsu yang terlihat serius di UI.

---

## 10. Temuan lintas-agent

### AUD-9A-02 (P2, FAIL) — 9 baris review tidak pernah tersimpan di DB demo
```
select step_name, agent_name, count(*), count(run_id) from agent_traces group by 1,2;
→ DETECT 27 | DECIDE 27 | LEARN 9 | VERIFY 8 | PREDICT 6 | ACT 5 | OPTIMIZE 3
  count(run_id) = 0 untuk SEMUA baris; step_name='SUPERVISE' → 0 baris
```
- Penulis baris review hanya dua endpoint: `POST /demo/event1` (`backend/app/api/demo.py:1021`) dan
  `POST /demo/agent/run` (`:1228`) → `persist_agent_review` (`backend/app/services/trace_persistence.py:76-119`).
- Tidak ada bukti eksekusi sejak container berjalan (log backend hanya memuat `POST /demo/session/end`;
  keputusan terakhir 2026-10-26 15:13Z lahir dari template demo, bukan Event 1).
- Konsekuensi: Agent Log pada data demo **tidak** menampilkan hasil 8 agent; klaim "review 9 agen
  tersimpan per keputusan" belum punya bukti. Jalur persist = **NOT TESTED** (butuh POST/tulis).

### AUD-9A-10 (P2, FAIL) — dua angka "permintaan" berbeda, fusion tidak mendeteksi
- Supply: `demand_kg = 1080.0` (dari `/balance`). Demand: `quantity_kg = 1074.11` (dari `/demand`).
  Selisih 5,89 kg muncul berdampingan di dua kartu UI.
- `detect_contradictions` hanya memeriksa `location`, `commodity`, `batch_count` (safety vs freshness),
  `decision_valid`/`can_execute`, serta `quantity_kg`/`safe_delivered_cost` **antara price vs evidence**
  (`agent/validation.py:90-151`). Pasangan supply↔demand tidak diperiksa sama sekali.
- Dampak: Evidence Fusion tidak menjalankan fungsi utamanya (rekonsiliasi lintas sumber) untuk
  pasangan yang paling mungkin berselisih.

### AUD-9A-07 (P2, BLOCKED/risiko) — dependensi jalur 8 agent bersifat sementara
- `MEALCHAIN_API_URL` di environment runtime = URL **quick tunnel** `https://age-debian-…trycloudflare.com`
  (bukan `http://backend:8000` di jaringan docker). Diverifikasi hidup: `GET /health` → `{"status":"healthy"}`.
  Quick tunnel Cloudflare berganti URL setiap kali dijalankan ulang; ada `.tunnel-watchdog.log` di repo.
- Token `MEALCHAIN_API_TOKEN` adalah JWT role `bgn_monitor` dengan `exp = 2026-11-17` dan **tanpa `iat`**;
  disimpan statis di environment runtime (tidak ada rotasi).
- Dampak: setelah tunnel berganti atau token kedaluwarsa, **seluruh** 8 agent mengembalikan `error`
  (run `partial`) dan narasi Event 1 jatuh ke `unavailable`. Perilakunya jujur (tidak mengarang), tetapi
  demo bisa mati mendadak. Perlu dicek H-1 demo + mekanisme rotasi.

### AUD-9A-11 (P3, FAIL) — kontrak `hierarchy.json` menyimpang dari kode
| Deklarasi (`agent/hierarchy.json`) | Kenyataan |
|---|---|
| safety: `GET /supplier-exclusions/context/{decision_id}` (`:47`) | tidak dipanggil (`safety.py:75`) |
| evidence: `GET /decisions/{id}/traces` (`:84`) | tidak dipanggil (`evidence.py:25-29`) |
| verifier: `GET /approval-summary`, `GET /traces` (`:97`) | tidak memanggil API sama sekali |
| lanes di JSON | diabaikan orkestrator; `LANES` didefinisikan ulang di `agent/orchestrator.py:29-33` |
`load_hierarchy()` memvalidasi lanes (`registry.py:106-109`) yang kemudian tidak dipakai — konfigurasi
terlihat mengikat padahal tidak. Risiko: orang mengubah JSON dan mengira perilaku berubah.

### AUD-9A-14 (P3, FAIL) — pesan & docstring tidak konsisten 7/8
`agent/registry.py:42` melempar `"hierarchy.json harus berisi tepat tujuh agent"` padahal
`:41` membandingkan dengan `len(AgentName)` = **8**. `agent/workers/__init__.py:1` menyebut
"tujuh analitik + verifier" pada modul yang mengekspor 8 kelas. Membingungkan saat membedah log/juri.

### AUD-9A-15 (P3, FAIL coverage) — uji worker tidak menyentuh lapisan HTTP nyata
Seluruh uji worker menyuntik objek API tiruan (`backend/tests/test_agent_workers.py`,
`test_agent_workers_p3.py`, `test_agent_golden_cases.py` — "mock transport".
Akibatnya kegagalan nyata yang ditemukan audit ini — **409 sesi demo** dan **403 role** — tidak
pernah bisa tertangkap suite. Satu-satunya bukti 409 adalah probe runtime pada dokumen ini.

### AUD-9A-17 (P3, STUB) — stub P1 masih diekspor
`StubWorker` + `STUB_WORKERS` + `build_stub_findings` (`agent/workers/base.py:32-166`,
`agent/workers/__init__.py:29-44`) masih dipakai tes (`test_agent_runtime_task.py:70`).
Tidak berbahaya, tetapi `run()` stub mengembalikan `status=skipped` — bila tak sengaja dipakai,
satu putaran review akan tampak "lengkap" padahal tidak ada pembacaan data.

### AUD-9A-18 (P3, FAIL data) — `agent_name` di dataset demo bukan nama agent nyata
```
agent_name: supervisor_agent 7 | detection_agent 6 | orchestrator 1 | verifier 1 | sap_agent 1 | (null) 69
output_summary->>'sumber' = "template demo" untuk baris-baris itu
```
`detection_agent` dan `sap_agent` **tidak ada** di kode agent mana pun (hanya label penyemai di
`backend/app/seed/demo_template.py` dan satu tes `test_po_ikut_keputusan_demo.py`). Jangan pakai
kolom ini sebagai bukti agent berjalan.

### AUD-9A-19 (NEEDS_PRODUCT_DECISION) — definisi resmi "9 agent"
Perlu keputusan tertulis: apakah "9 agent" berarti (a) 8 agent + 1 ringkasan supervisor
(didukung kode & UI `AgentSwarmPanel.tsx:1`), atau (b) 9 proses otonom (tidak didukung apa pun).
Rekomendasi: pakai (a) dan ganti istilah "9 agent" menjadi **"9 baris jejak: 7 worker + 1 verifier + 1 ringkasan"**.

---

## 11. Status per agent (rekap untuk laporan)

| Agent | Implementasi | Bukti runtime | Testing | Status akhir |
|---|---|---|---|---|
| Supervisor (narasi LLM) | lengkap + 4 tool | `narrated`, `primary:agentcore`, 6,7 s | 10 tes (mock) | **PARTIAL** (AUD-9A-08, -16) |
| Supply | lengkap | `ok`, 471 ms | 3 tes | **PASS** |
| Demand | lengkap | `ok`, 827 ms | 2 tes | **PASS** dengan catatan AUD-9A-09 |
| Freshness Guardian | ada, semantik menyimpang | `ok` untuk 0,82 | 2 tes | **FAIL** (AUD-9A-05) |
| Safety Guardian | ada, veto tidak di-scope | `blocking=True` tanpa dasar | 2 tes | **FAIL** (AUD-9A-04) |
| Price | ada | `degraded` (409) | 6 tes | **PARTIAL** (AUD-9A-06) |
| Logistics | ada | `ok`, 406 ms | 3 tes | **PARTIAL** (jalur estimasi) |
| Evidence Fusion | ada | `ok` + `blocking=True` | 5 tes | **PASS** dengan catatan kontradiksi (AUD-9A-10) |
| Independent Verifier | ada (3 entitas berbeda) | `flagged` (audit agent, 27 Okt) | ≥23 tes + 14 tes red-team | **SEBAGIAN** (AUD-9A-03: lapis agent diperbaiki, endpoint `/actions/verify` terbuka) |

---

## 12. Yang TIDAK diuji di audit ini

| Butir | Alasan |
|---|---|
| Persist 9 baris lewat `POST /demo/event1` / `/demo/agent/run` | butuh tulis DB demo — di luar izin audit (**NOT TESTED**) |
| Perilaku saat tunnel mati / token kedaluwarsa | tidak boleh mematikan layanan saat audit (**NOT TESTED**, dinilai dari kode) |
| Mutu penalaran model (apakah verdict/ narasi "benar" secara domain) | audit menilai struktur & perilaku, bukan kualitas model (**NOT TESTED**) |
| Idempotensi `persist_agent_review` (run_id sama → 0 baris) | butuh tulis (**NOT TESTED**) |
| Kalibrasi `confidence` forecast | tidak ada ground truth (**UNVERIFIED**) |
