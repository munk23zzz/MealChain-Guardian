# 9_AGENT_ORCHESTRATION_AUDIT — orkestrasi, supervisor, verifier, dan konflik prioritas

Status: **audit selesai, bukti terkumpul** — 26 Oktober 2026.

Objek: orkestrasi sembilan agent (`agent/orchestrator.py` + `agent/workers/*`),
perilaku Supervisor terhadap kegagalan, dan perilaku Independent Verifier.
Dokumen pasangan: `docs/audit/9_AGENT_DATA_AND_MATH_AUDIT.md` (AUD-9B-01 … -19).
Penomoran temuan di sini melanjutkan: **AUD-9B-20 … -36**.

Metode:
1. Baca kode orkestrasi baris per baris (bukan dokumentasi).
2. **Probe in-process** dengan worker palsu yang memakai kontrak produksi
   (`AgentFinding`), untuk menguji jalur gagal yang tidak bisa dipicu di DB demo.
3. **Probe live** `run_review` terhadap backend `localhost:8000` dengan token
   baca `bgn_monitor` (hanya GET + dua POST komputasi).
4. Query `agent_traces` + `decisions` (SELECT) untuk membandingkan klaim verifier
   dengan angka yang tersimpan.

Tidak ada kode/DB yang diubah. Tidak ada kredensial di dokumen ini.

---

## 1. Jawaban jujur di depan: ini bukan orkestrasi broker

**Orkestrasi yang sesungguhnya adalah pemanggilan fungsi internal deterministik
plus satu panggilan HTTP ke runtime.** Tidak ada message broker, tidak ada
antrean, tidak ada negosiasi antar-agent, tidak ada agent otonom.

Rantai yang benar-benar terjadi di produksi:

```
POST /demo/event1  atau  POST /demo/agent/run        (api/demo.py:1021, :1228)
  └─ _jalankan_agent_review()                        (api/demo.py:1025-1060)
       └─ review_decision(decision_id, timeout)      (services/agent_review_client.py:100-141)
            └─ caller(prompt JSON)                   ← HTTP ke AgentCore Runtime (ARN di .env)
                 └─ agent/runtime_server.invoke()    (agent/runtime_server.py:107-125)
                      └─ _review_response()          (:66-86)
                           └─ orchestrator.run_review()   ← SATU proses, SATU thread pool
                                ├─ get /decisions/{id}/approval-summary  → konteks
                                ├─ 3 lane paralel (ThreadPoolExecutor, max_workers=3)
                                │    lane-1: Supply → Demand        (sekuensial dalam lane)
                                │    lane-2: Safety → Freshness
                                │    lane-3: Price  → Logistics
                                ├─ Evidence (setelah lane, thread sendiri)
                                ├─ detect_contradictions() + run_status() + safety_veto()
                                ├─ _narrative()  ← TEMPLATE STRING, bukan LLM
                                ├─ verify_run()  ← deterministik
                                └─ VerifierWorker().audit()  ← deterministik
                      → JSON {AgentRun + trace_rows}
            └─ _catat_review_sukses/gagal()          (api/demo.py:1063-1131)
                 └─ persist_agent_review()           (services/trace_persistence.py:76-118)
                      └─ agent_traces (9 baris)
```

Yang penting dipahami (dan harus disebut apa adanya bila ditanya):

- **"Supervisor" pada jalur review bukan LLM.** Narasi supervisor adalah
  `if/elif` lima string tetap (`agent/orchestrator.py:190-212`). LLM supervisor
  yang sebenarnya ada di dua tempat lain: `services/supervisor_client.py`
  (dipakai `event1_orchestrator` untuk langkah SUPERVISE) dan
  `agent/supervisor_agent.py` (Strands, jalur hello-world/Joule). Untuk review
  9 agent, tidak ada model yang dipanggil sama sekali.
- **Delapan agent berjalan sebagai thread dalam satu proses**, bukan proses/SDK
  terpisah; workernya adalah objek singleton modul (`agent/workers/__init__.py:29`).
- **Tidak ada keputusan yang lahir dari sembilan agent.** Keputusan lahir dari
  `event1_orchestrator`/`supplier_procurement` (fungsi deterministik). Review 9
  agent berjalan **setelah** keputusan ada dan hanya advisory
  (`agent/orchestrator.py:1-9`).
- Komunikasi antar-agent **tidak ada**: setiap worker membaca API sendiri dan
  hasilnya hanya dipertemukan di `findings` untuk deteksi kontradiksi.

Konsekuensi untuk klaim ke juri: "sembilan agent" = **satu supervisor template +
tujuh pembaca read-only + satu auditor deterministik**, semuanya dalam satu
runtime. Menyebutnya "agen otonom yang bernegosiasi" tidak didukung kode
(AUD-9B-20).

---

## 2. Dependency graph AKTUAL (dari kode, bukan dokumen)

### 2.1 Siapa memanggil siapa dan field apa yang lewat

| Pemanggil | Dipanggil | Data yang lewat | Validasi di batas | Bila gagal |
|---|---|---|---|---|
| `api/demo.py:1021/1228` | `_jalankan_agent_review` | `outcome["decision_id"]` (str) | `decision_id` harus non-kosong | `{status: failed}`; decision tetap 201 |
| `_jalankan_agent_review` | `review_decision` (threadpool) | `decision_id`, `timeout` (1–45 dtk) | `timeout = min(max(cfg,1),45)` (`:1037`) | `AgentReviewResult(status='failed')` |
| `review_decision` | runtime caller (HTTP) | `{"task":"review_decision","decision_id":…}` | JSON string (`agent_review_client.py:117-119`) | `unavailable` bila ARN kosong; `timeout`; `failed` |
| runtime `invoke` | `run_review` | `decision_id` | non-kosong (`runtime_server.py:114`) | `{"status":"unavailable","error":…}` |
| `run_review` | `GET /decisions/{id}/approval-summary` | → `target_location`, `commodity`, `source_location`, `quantity_kg` (`context_from_approval`, `:37-57`) | `target_location`+`commodity` wajib; `quantity_kg` boleh None | `ValueError` → RuntimeError → `unavailable` |
| `run_review` | 8 worker (dict `AgentName→worker`) | `WorkerContext{run_id, decision_id, location (TUJUAN), commodity, source_location, quantity_kg, api}` | jumlah worker harus 8 (`:253-260`) | `ValueError: worker belum lengkap` (AUD-9B-21) |
| Supply worker | `GET /balance/{loc}/{com}` | → `supply_kg, demand_kg, surplus_kg, shortage_kg, *_state` | `data_state=='terukur'` + kedua angka ada → gap dipakai | 404 → `degraded` + angka `None`; lain → `error` |
| Demand worker | `GET /demand/...`, `GET /demand/forecast/...?horizon_days=7` | → `quantity_kg, needed_by, forecast_qty_kg, method, confidence` | 404 per endpoint → warning; bila demand OK & forecast gagal → warning | 404 keduanya → `degraded`; error lain → `error` |
| Freshness worker | `GET /batches` (paginasi 500, plafon 5.000) | → `freshness_score`, `usable_until` per batch | filter lokasi+komoditas di memori | 404 → `degraded` (semua `None`); error → `error` |
| Safety worker | `GET /batches`, `GET /supplier-exclusions` | → hitungan status + `items[].status` | `items` harus list | exclusion gagal → warning, `active_exclusion_count=None` |
| Price worker | `GET /price/quotes/...`, `GET /price/...`, `POST /price/deviation`, `GET approval-summary` | → quote, referensi, `deviation_pct`, `classification`, `flagged`, `safe_delivered_cost`, `quantity_kg`, `can_execute`, `expiry.valid` | POST hanya bila kedua harga ada; allowlist komputasi (`api_client.py:22`) | 403 → alasan `role_read_only`; lain → `endpoint_error`; degraded |
| Logistics worker | `GET /supplier-routes?...`, `POST /logistics/estimate` | → `distance_km`, `duration_min`, `estimated_time_min`, `feasible` | `routes` harus list; filter **tujuan+komoditas** | tanpa rute + tanpa sumber/qty → `degraded`; estimasi gagal → `degraded` |
| Evidence worker | `GET dossier`, `compliance`, `chain`, `approval-summary`, `ledger/verify` | → `evidence_count`, `approval_count`, `trace_count`, `chain_length`, `ledger_valid`, `signature_*` | dossier & compliance wajib (gagal → `error`) | deskriptif `degraded` |
| `detect_contradictions` | semua findings | `location`, `commodity`, `batch_count`, `decision_valid`, `can_execute`, `quantity_kg`, `safe_delivered_cost` | `findings` harus 7 (`validate_findings`) | — |
| `verify_run` | `run.findings` + `run.status` | tidak membaca fakta/DB | — | selalu menghasilkan `pass|flag` |
| `VerifierWorker.audit` | `run.verification` + `run.narrative` | teks alasan + verdict | — | exception → **ditelan** (`orchestrator.py:303-306`) |
| `_catat_review_sukses` | `persist_agent_review` | `trace_rows` (8 atau 9) + satu `run_id` | 8/9 baris, `run_id` UUID tunggal | ditulis 1 baris SUPERVISE error |

### 2.2 Yang TIDAK ada dalam graf

- Tidak ada pemanggilan antar-worker (tidak ada `worker → worker`).
- Tidak ada aggregator yang menghitung ulang angka dari beberapa worker.
- Tidak ada penjadwal/antrean/retry lintas-run; idempotensi hanya pada
  `persist_agent_review` (per `run_id` per decision).
- Tidak ada jalur balik dari review ke keputusan: review tidak menulis
  `decisions`, tidak mengubah status, tidak memblokir approval.
  **Veto agent hanya teks** (`_narrative`), bukan gerbang.

---

## 3. Kontrak dan validasi (empat lapis)

| Lapis | Aturan | Kode | Konsekuensi bila dilanggar |
|---|---|---|---|
| 1 | Setiap **angka** di `facts` wajib punya `Citation` dengan `claim == path` dan nilai+tipe identik; `bool` bukan angka; `0` ≠ `0.0` | `agent/contracts.py:88-105,129-158` | `ValidationError` **di dalam worker** → ditangkap `_run_one` → finding `error` (probe: S6b sebelum sitasi ditambahkan) |
| 2 | `blocking=True` hanya untuk Safety/Freshness/Evidence | `contracts.py:131-134` | `ValidationError`; probe S12 menolak Supply blocking |
| 3 | `AgentRun.findings` tepat **7** agent analitik unik; `safety_veto` harus sama dengan `any(blocking && guardian)` | `contracts.py:185-228` | `ValidationError` → **seluruh review gagal** (S5) |
| 4 | Runtime → backend: `findings` harus 7 + `run_id` ada; persist: 8/9 baris, satu `run_id` UUID | `agent_review_client.py:89-97`; `trace_persistence.py:90-103` | `failed` / `ValueError`; 1 baris SUPERVISE error |

Lapis 1 adalah pertahanan terkuat di sistem ini: angka tanpa sitasi tidak bisa
lolos, dan sitasi yang tidak cocok nilai juga ditolak. **Tetapi** validasi itu
hanya memeriksa *bahwa angka sama dengan sumbernya*, bukan *bahwa sumbernya
masuk akal* (lihat §6, probe S10).

---

## 4. Perilaku Supervisor terhadap kegagalan (hasil probe)

Probe memakai 7 worker palsu + verifier produksi, `timeout_seconds` bervariasi.
`S*` = skenario. Semua hasil dapat direproduksi (lampiran §10).

| S | Skenario | Diharapkan | Aktual | Bukti | Status |
|---|---|---|---|---|---|
| S1 | Semua worker normal | `completed`, tanpa veto | `completed`, veto `false`, 7 findings, verification `pass`, verifier `ok` | probe | **PASS** |
| S2 | Satu worker melempar exception | worker lain tetap jalan; run `partial`; temuan error jujur | `partial`; supply=`error`; 6 worker lain `ok`; narasi menyebut "sebagian" | probe | **PASS** |
| S3 | Worker tidak terdaftar di dict | error finding "worker tidak terdaftar" untuk agent itu | **exception** `ValueError: worker belum lengkap: logistics` — review batal sebelum satu worker pun jalan | probe | **FAIL** (AUD-9B-21) |
| S4 | Worker mengembalikan `None` (kontrak dilanggar) | dianggap error untuk agent itu saja | **exception** `AttributeError: 'NoneType' object has no attribute 'status'` — seluruh review mati | probe | **FAIL** (AUD-9B-22) |
| S5 | Worker mengembalikan finding bernama agent lain (duplikat) | dideduplikasi/ditolak per worker | 8 findings → `ValidationError: List should have at most 7 items` — seluruh review mati | probe | **FAIL** (AUD-9B-23) |
| S6a | Dua worker beda `location` | kontradiksi + `partial` | kontradiksi `location` tercatat, `partial` | probe | **PASS** (deteksi) |
| S6b | Supply 538,0 vs Demand 532,4 (field berbeda, makna sama) | kontradiksi + `partial` | **`completed`, 0 kontradiksi** | probe + data nyata | **FAIL** (AUD-9B-25) |
| S6c | Safety `batch_count=3` vs Freshness `batch_count=5` | kontradiksi | kontradiksi `batch_count`, `partial` | probe | **PASS** |
| S7 | Satu lane lambat melewati deadline | lane lain yang sudah selesai tetap dipakai; `timeout`; evidence ditandai | `timeout`; **ketujuh** worker `error` (hasil lane sehat hilang karena loop berhenti di future pertama); evidence error | probe | **FAIL** (AUD-9B-27) |
| S8 | Worker mengembalikan `ERROR` (bukan exception) | dicoba ulang sekali | 2 panggilan; hasil akhir `ok`, run `completed` | probe (`calls: 2`) | **PASS** |
| S9 | `verifier.audit` melempar exception | jejak auditor tetap ada (minimal `degraded`) | `verifier_finding = None`; run tetap `completed`; **tidak ada baris audit** | probe | **FAIL** (AUD-9B-24) |
| S10 | Angka mustahil tapi bersitasi: supply 100, demand 200, `shortage_kg=5` | verifier menandai/arifmetika diperiksa | run `completed`; `verification=pass`; verifier "**Audit sepakat**: 7 temuan … konsisten" | probe | **FAIL** (AUD-9B-26) |
| S11 | Satu guardian `blocking=True`, semua worker `ok` | status tidak boleh `completed` saat veto aktif | `completed` + veto `true`; verifier `flag: safety_veto_aktif` | probe | **FAIL** (AUD-9B-28) |
| S12 | Worker non-guardian `blocking=True` | ditolak kontrak | `ValidationError` | probe | **PASS** |
| S13 | Price SDC 1.000 vs Evidence SDC 1.200 | kontradiksi + `partial` + verifier menandai | kontradiksi `safe_delivered_cost`, `partial`, tetapi `verification=pass`, verifier "Audit sepakat" | probe | **FAIL** (AUD-9B-26) |

Catatan S7: `cancel_futures=True` tidak menghentikan thread yang sedang berjalan;
worker lambat tetap hidup setelah review kembali (thread yatim). Dampaknya kecil
karena worker read-only, tetapi jumlah thread bisa menumpuk bila review
diulang-ulang saat backend lambat.

### 4.1 Retry: apa yang benar-benar dicoba ulang

```python
# agent/orchestrator.py:72-89
finding = worker.run(context)                 # exception → LANGSUNG error, TANPA retry
if retry_errors and finding.status is ERROR and monotonic()-started < 5:
    finding = worker.run(context)             # tepat satu percobaan ulang
```

- Retry **hanya** untuk `status=ERROR` yang dikembalikan worker (bukan exception).
- Hanya bila kegagalan pertama < **5 detik** (konstanta hard-coded).
- Maksimum **1** percobaan ulang; tidak ada backoff.
- Tidak ada retry untuk timeout (lane sudah dibatalkan).

### 4.2 Anggaran waktu: aritmetika

| Parameter | Nilai | Sumber |
|---|---|---|
| `timeout_seconds` review | 45,0 dtk default | `orchestrator.py:221` |
| `agent_review_timeout_seconds` (config) | 75 dtk default, **dijepit ke 45** | `core/config.py:53`; `api/demo.py:1037` |
| Timeout HTTP per panggilan worker | 15 dtk | `agent/api_client.py:18` |
| Worker per lane | 2 (sekuensial) | `LANES` `orchestrator.py:29-33` |
| Kasus terburuk 1 lane | 2 × 15 = **30 dtk** | — |
| Evidence sisa waktu | ≤ 15 dtk | `orchestrator.py:171` |
| Retry menambah | +15 dtk (tidak akan terjadi: retry butuh <5 dtk) | — |

Artinya konfigurasi 75 dtk **tidak pernah berlaku** — nilai efektif selalu ≤45
(AUD-9B-34). Bila satu worker menggantung 15 dtk dan pasangannya juga, lane
menghabiskan 30 dtk; tiga lane paralel tetap 30 dtk; evidence dapat ≤15 dtk.
Masih di bawah 45 dtk, jadi timeout praktis hanya terjadi bila API sangat lambat
atau worker dipanggil lebih dari sekali.

---

## 5. Independent Verifier: mengulang atau memeriksa?

### 5.1 Apa yang benar-benar dilakukan `VerifierWorker`

Masukannya **hanya** `run.verification` (hasil `verify_run`) + `run.narrative` +
`run.status`/`safety_veto`/status findings (`agent/workers/verifier.py:71-124`).
Ia **tidak** membaca DB/API, **tidak** menerima `facts`, dan **tidak**
menghitung ulang apa pun.

`verify_run` sendiri hanya memeriksa tiga hal (`agent/verify.py:18-65`):

1. `run.status` sama dengan `run_status(findings, contradictions)` — fungsi yang
   **sama** yang dipakai supervisor untuk menentukan status (`validation.py:154-167`);
2. veto aktif tetapi status `completed`;
3. kata kunci di narasi ("degraded/sebagian/error/gagal/tidak tersedia/partial")
   bila ada worker tidak utuh.

Jadi verifier = **pemeriksa konsistensi internal**, bukan penguji angka. Itu
sah sebagai desain (tertulis di docstring `verifier.py:1-22`), tetapi tidak
memenuhi makna "independent verification" bila yang dimaksud adalah
memeriksa ulang angka. Bukti paling telak: **S10** — `shortage_kg=5` untuk
supply 100/demand 200 lolos dengan verdict `pass` dan ringkasan "Audit sepakat".

### 5.2 Perbandingan 8 baris VERIFY di DB vs keputusan (minimal 5)

Sumber: `agent_traces` di DB demo (8 baris `step_name='VERIFY'`).

| # | Keputusan | Jenis/status | Isi VERIFY di `agent_traces` | Angka yang diklaim | Hitung independen dari DB | Cocok? |
|---|---|---|---|---|---|---|
| 1 | `3e2e3cc7` | regional_balance / pending_approval | `agent_name='verifier'`, `{"verdict":"consistent","catatan":"Tiga angka saling cocok."}` | "tiga angka cocok" (angka tidak disebut) | `(28.500+1.800+950)×300 = 9.375.000` vs `safe_delivered_cost 9.750.000` → **tidak cocok**, Δ375.000 | **FAIL** |
| 2 | `a693308f` | price_anomaly / verifier_flagged | `tool_called='evidence.crosscheck'`, `{"supplier_quote_ratio":0.6}` → `{"verdict":"FLAGGED","reason":"… 40% di bawah referensi"}` | rasio 0,6 = −40% | quote/ref pada `created_at` = 30.500/30.500 = **1,0000** (0,00%) | **FAIL** |
| 3 | `4ee4e0c5` | price_anomaly / verifier_flagged | idem | −40% | 27.200/27.200 = **1,0000** | **FAIL** |
| 4 | `00e276af` | price_anomaly / verifier_flagged | idem | −40% | 28.200/28.200 = **1,0000** | **FAIL** |
| 5 | `e7150da4` | supplier_procurement / executed | `tool_called='demo.verify'`, `{"ok":true}`, tanpa angka, `run_id NULL`, `citations NULL` | tidak ada | SDC 17.482.178,40 = Σ komponen (PASS), tetapi bukan hasil verifikasi | **UNVERIFIED** (tanpa angka) |
| 6 | `77528958` | supplier_procurement / executed | idem `{"ok":true}` | tidak ada | SDC 13.782.245,34 = Σ komponen | **UNVERIFIED** |
| 7 | `661695b2` | supplier_procurement / executed | idem `{"ok":true}` | tidak ada | SDC 8.667.970,74 = Σ komponen | **UNVERIFIED** |
| 8 | `b54d0f11` | supplier_procurement / executed | idem `{"ok":true}` | tidak ada | SDC 29.263.666,14 = Σ komponen | **UNVERIFIED** |

Kesimpulan angka: **4 baris VERIFY memuat klaim angka, dan keempatnya tidak
cocok dengan data**; 4 baris sisanya tidak memuat angka apa pun (`{"ok": true}`)
sehingga tidak mungkin diverifikasi. Nol baris berasal dari
`agent/workers/verifier.py` — tidak ada `run_id`, `citations`, `facts`, atau
`duration_ms` pada baris-baris itu, sedangkan `build_trace_rows` selalu mengisi
keempat field tersebut (`agent/telemetry.py:13-77`). Baris-baris itu ditulis
oleh seed: `seed/demo_kasus_bukti.py:148-152` (literal "Tiga angka saling
cocok") dan `api/demo.py:585-588` (`supplier_quote_ratio: 0.60`).

### 5.3 Bukti bahwa verifier tidak memeriksa angka (probe)

```
S10_angka_salah_tapi_konsisten
  facts: {supply_kg: 100.0, demand_kg: 200.0, surplus_kg: 0.0, shortage_kg: 5.0}
  (setiap angka punya sitasi yang cocok, jadi kontrak lapis 1 lolos)
  → status: completed | contradictions: [] | verification: pass
  → verifier: "Audit sepakat: 7 temuan analitik konsisten dengan narasi"
```

Invarian `shortage = max(demand − supply, 0) = 100` tidak pernah dievaluasi.
Verifier akan meloloskan angka apa pun asalkan sitasinya cocok dengan sumber —
termasuk bila sumbernya sendiri salah.

---

## 6. Matriks konflik prioritas bisnis

Urutan prioritas yang diklaim: **safety > gizi/menu > kontinuitas > biaya > limbah**.
Diuji per skenario pada kode + data.

### C1. Harga murah tetapi batch tidak aman

- **Diharapkan:** kandidat murah dengan `safety_status=fail` tidak pernah masuk
  peringkat; biaya tidak boleh "menang" atas safety.
- **Aktual:** benar di mesin — batch `fail` dibuang sebelum kandidat
  (`candidate_generation.py:126-127`), skor dipaksa 0 & `eligible=False`
  (`scoring.py:70-73`), SDC melempar `ValueError` bila fail
  (`safe_delivered_cost.py:108-112`), `rank_candidates` mengecualikan yang tidak
  eligible (`ranking.py:78`).
- **Cacat di lapisan agent:** Price agent **selalu** `blocking=False`
  (`workers/price.py:214,222`), dan Safety agent memeriksa batch di **lokasi
  tujuan**, bukan sumber (`context_from_approval` memakai `target_location`;
  probe 3e2e3cc7: agent melihat Jakarta/ayam `fail`, read model melihat
  Bandung/ayam `pass`).
- **Status:** **PASS** (mesin) / **FAIL** (agent — AUD-9B-29).

### C2. Pasokan cukup tetapi terlambat

- **Diharapkan:** kandidat yang ETA-nya melewati jendela kirim dieksklusi.
- **Aktual:** `estimate_logistics(s_loc, d_loc, 1.0)` dipanggil **tanpa**
  `delivery_window_min` (`recommendation_service.py:364-367`), sehingga
  `feasible` selalu `True` (`core/logistics.py:96-98`). `needed_by` dari
  `demand_records` **tidak dipakai satu kali pun** di pipeline (grep: 0 hasil di
  luar model/seed/endpoint baca).
- **Bukti tambahan:** `logistics_time_min` hanya ikut di payload kandidat; tidak
  ada perbandingan dengan `needed_by` atau jam buka dapur.
- **Status:** **FAIL** (AUD-9B-35).

### C3. Supply vs demand beda angka

- **Diharapkan:** kontradiksi dilaporkan, status `partial`.
- **Aktual:** S6b → `completed`, 0 kontradiksi. Detektor hanya membandingkan
  `location`, `commodity`, `batch_count`, `decision_valid`, `can_execute`,
  `quantity_kg↔decision_quantity_kg`, `safe_delivered_cost↔decision_safe_delivered_cost`
  (`validation.py:90-151`). `demand_kg` (Supply) vs `quantity_kg` (Demand)
  **tidak pernah dibandingkan**.
- **Data nyata:** 538,0 vs 532,4 (Bandung/telur), 215,0 vs 217,37 (Jakarta/ayam).
- **Status:** **FAIL** (AUD-9B-25).

### C4. Reference price tidak valid

- **Diharapkan:** penolakan terkendali (4xx) dan agent melaporkan `degraded`
  dengan alasan jelas.
- **Aktual:** `price_deviation()` melempar `ValueError` untuk nilai ≤0/bukan
  angka (`core/price.py:21-22`); endpoint `POST /price/deviation` **tidak**
  menangkapnya (`api/price.py:174`) → **HTTP 500**. Agent memperlakukan 500
  sebagai `error` (bukan `degraded`), sehingga run menjadi `partial` dengan
  alasan generik.
- **Kasus referensi hilang (404):** agent benar → `degraded`, alasan `data_missing`.
- **Status:** **FAIL** untuk nilai tidak valid (AUD-9B-31); **PASS** untuk 404.

### C5. Evidence wajib hilang

- **Diharapkan:** keputusan tanpa bukti tidak bisa dieksekusi / ditandai.
- **Aktual:** dua keputusan ber-SDC tanpa bukti sama sekali — `64ce3369`
  (`proposed`) dan `3e2e3cc7` (`pending_approval`). Agent Evidence dengan
  `evidence_count=0` **tidak** degraded dan **tidak** blocking, karena
  `evidence_complete = isinstance(raw_evidence, list)` → `[]` dianggap "lengkap"
  (`workers/evidence.py:64-68,184-198`). `can_execute` di read model hanya
  memeriksa `quantity>0` dan `sdc>0` (`approval_summary.py:350-357`), bukan bukti.
- **Status:** **FAIL** (AUD-9B-16, lintas dokumen).

### C6. Verifier unavailable

- **Diharapkan:** approval diblokir; tidak ada klaim "terverifikasi".
- **Aktual:** gerbang approval **benar** — `unverified` → `can_approve=False`,
  `blocking_reasons` menyebut "decision belum terverifikasi"
  (`approval_summary.py:287-327`). Tetapi bila **agent verifier** gagal, exception
  ditelan (`orchestrator.py:303-306`) sehingga run `completed` **tanpa baris
  audit** (S9) — bertentangan dengan komentar "audit tetap harus ada supaya tidak
  ada putaran review tanpa jejak auditor".
- **Status:** **PASS** (gerbang approval) / **FAIL** (jejak audit — AUD-9B-24).

### C7. Dua agent bertentangan

- **Diharapkan:** kontradiksi + `partial` + verifier menandai.
- **Aktual:** kontradiksi tercatat dan status `partial` (S6a, S6c, S13), tetapi
  `verification` tetap `pass` dan verifier menulis "Audit sepakat … konsisten
  dengan narasi" (S13) — kontradiksi tidak pernah dibaca `verify_run`.
- **Status:** **FAIL** (verifier — AUD-9B-26).

### C8. Gizi/menu vs biaya

- **Diharapkan:** kebutuhan menu menjadi lantai kekurangan meski permintaan
  historis lebih rendah.
- **Aktual:** `shortage_setelah_gizi = max(demand−supply, menu−supply, 0)`
  (`menu_hierarchy.py:67-77`), dipakai `generate_candidates:153`; kontinuitas
  `surplus_setelah_kontinuitas` (`:80-89`). **Terimplementasi dan deterministik.**
- **Cacat basis:** `menu_plans` dipilih per tanggal **WIB** (`:250`) dan 100 dari
  660 baris bertanggal masa depan; rencana ikut menentukan "hari ini".
- **Status:** **PASS** (aturan) / **FAIL** (basis waktu — AUD-9B-06).

### C9. Kontinuitas vs biaya

- **Diharapkan:** sumber tidak mengekspor di bawah cadangan/permintaan lokalnya.
- **Aktual:** aturan dikode benar, **tetapi data keputusan melanggarnya**:
  `3e2e3cc7` memindahkan 300 kg dari Bandung→Jakarta untuk ayam, sementara
  Bandung/ayam pada saat itu supply 250 kg vs demand 308 kg (defisit 58 kg) →
  surplus ekspor = 0 menurut aturan yang sama.
- **Status:** **FAIL** (data/keputusan, bukan mesin — AUD-9B-35).

### C10. Limbah (prioritas #5)

- **Diharapkan:** ada agent atau aturan limbah dalam rantai keputusan.
- **Aktual:** tidak ada worker limbah di `AgentName` (`contracts.py:18-28`),
  tidak ada skor/ambang limbah di pipeline rekomendasi. Tabel/endpoint
  `waste`, `disposal_events`, `surplus` ada di backend, tetapi tidak terhubung ke
  sembilan agent maupun ke skor kandidat.
- **Status:** **MISSING** (AUD-9B-36).

Ringkasan matriks:

| Prioritas | Ditegakkan? | Bukti |
|---|---|---|
| 1. Safety | Ya di mesin; **tidak** di agent (cakupan lokasi salah) | C1, AUD-9B-29 |
| 2. Gizi/menu | Ya (lantai menu) | C8 |
| 3. Kontinuitas | Ya di mesin; dilanggar data | C9 |
| 4. Biaya | Ya (SDC ranking) tetapi basis harga cacat | C1, AUD-9B-03/06 |
| 5. Limbah | **Tidak ada** | C10 |

---

## 7. Dampak bila output sebuah agent tidak ada

| Output hilang | Yang terjadi di kode | Dampak bisnis | Status |
|---|---|---|---|
| Supply | run `partial`; tidak ada angka pasokan di ringkasan; narasi menyebut "sebagian" | Reviewer manusia tidak melihat surplus/shortage; keputusan tetap bisa disetujui | **PASS** (jujur) |
| Demand/forecast | `degraded`; `forecast_qty_kg=None` | Forecast tidak memengaruhi keputusan (memang tidak dipakai — lihat `AGENT_WORKFLOW_AUDIT` §6) | **PASS** |
| Freshness | `degraded`; `worst_freshness_score=None`; **tidak** blocking | Tidak ada yang memaksa manusia memeriksa kesegaran sebelum approve | **FAIL** (AUD-9B-24 pola serupa) |
| Safety | `error`/`degraded`; veto tidak aktif | Keputusan aman-tampak padahal tidak diperiksa | **FAIL** (AUD-9B-29) |
| Price | `degraded`; `deviation_pct=null` | Anomali harga tidak terlihat; SDC tetap dari read model | **FAIL** (AUD-9B-07) |
| Logistics | `degraded`; ETA kosong | Tidak ada peringatan keterlambatan (memang tidak pernah mengeksklusi) | **FAIL** (AUD-9B-09) |
| Evidence | `error` bila dossier/compliance gagal; bila `evidence_count=0` → tetap `ok` | Bukti hilang tidak terdeteksi | **FAIL** (AUD-9B-16) |
| Verifier | run `completed` tanpa `verifier_finding` (S9) | Klaim "sudah diaudit" tanpa auditor | **FAIL** (AUD-9B-24) |
| Supervisor (narasi) | `narrative=None`; pemeriksaan kata kunci dilewati | Tidak ada ringkasan; trace SUPERVISE kosong | **FAIL** (AUD-9B-26 pola) |

---

## 8. Temuan

| ID | Sev | Status | Temuan | Bukti | Dampak |
|---|---|---|---|---|---|
| AUD-9B-20 | P1 | **NEEDS_PRODUCT_DECISION** | Orkestrasi 9 agent adalah pemanggilan fungsi/thread dalam satu proses + satu invocation runtime; "supervisor" pada jalur review adalah template string, bukan LLM; tidak ada broker/antrean/negosiasi | `orchestrator.py:109-187,190-212`; `runtime_server.py:66-86` | Klaim "agen otonom"/"orkestrasi multi-agent" berisiko tidak lolos uji juri; label yang benar: 1 supervisor template + 7 pembaca + 1 auditor |
| AUD-9B-21 | P2 | **FAIL** | Worker yang tidak terdaftar membatalkan seluruh review (`ValueError` sebelum lane jalan), bukan menghasilkan temuan error untuk agent itu | probe S3; `orchestrator.py:253-260` | Satu registry salah → 0 temuan, bukan 6/7; kontrak "kegagalan satu worker tidak menghentikan worker lain" tidak berlaku untuk kasus ini |
| AUD-9B-22 | P2 | **FAIL** | Worker yang mengembalikan `None` mematikan review (`AttributeError`) | probe S4 | Kontrak dilanggar satu worker = kehilangan seluruh hasil review |
| AUD-9B-23 | P2 | **FAIL** | Finding dengan nama agent salah/duplikat membuat `AgentRun` gagal validasi → review batal | probe S5 | Sama seperti di atas; tidak ada jalur "buang yang duplikat" |
| AUD-9B-24 | P1 | **FAIL** | Kegagalan auditor ditelan (`except: pass`): `verifier_finding=None`, run tetap `completed` | probe S9; `orchestrator.py:303-306` | Review bisa berlabel selesai **tanpa jejak audit**, padahal komentar kode menjanjikan sebaliknya |
| AUD-9B-25 | P1 | **FAIL** | Angka pasokan vs permintaan antar-agent tidak pernah dibandingkan; `demand_kg` vs `quantity_kg` tidak ada di daftar kontradiksi | probe S6b; `validation.py:90-151`; data 538,0 vs 532,4 | Dua agent bisa berbeda 1% dan review tetap `completed` |
| AUD-9B-26 | P1 | **FAIL** | `verify_run` tidak memeriksa angka dan tidak membaca kontradiksi: aritmetika mustahil lolos `pass`, kontradiksi SDC juga `pass`; verifier lalu menulis "Audit sepakat" | probe S10, S13; `verify.py:18-65` | "Independent verifier" tidak memenuhi makna verifikasi independen; klaim ke juri harus dibatasi ke "pemeriksa konsistensi internal" |
| AUD-9B-27 | P2 | **FAIL** | Timeout di lane pertama membuang hasil lane lain yang sudah selesai; semua worker dilaporkan `error`; status `timeout` lalu ditandai "tidak konsisten" oleh verifier | probe S7 | Saat backend lambat, review kehilangan temuan yang sebenarnya sudah ada; flag verifier jadi derau |
| AUD-9B-28 | P2 | **FAIL** | `run_status` mengabaikan `blocking`: veto aktif dengan semua worker `ok` → status `completed` | probe S11; `validation.py:154-167` | Status "completed" berdampingan dengan "JANGAN EKSEKUSI" |
| AUD-9B-29 | **P0** | **FAIL** | Safety & Freshness memeriksa batch di **lokasi tujuan**, bukan sumber; ditambah hitungan exclusion **tanpa cakupan lokasi/pemasok** → satu exclusion aktif di Jakarta memveto review Bandung/telur dan Jakarta/ayam | probe e7150da4 & 3e2e3cc7 (`active_exclusion_ids=['55bb6ed8…']`, scope DB = Jakarta, supplier telur); `workers/safety.py:71-88,126`; `workers/freshness.py:56-62` | (a) Veto palsu pada **semua** review selama ada ≥1 exclusion aktif di DB; (b) batch sumber yang FAIL bisa lolos. Ini merusak kredibilitas guardian di demo |
| AUD-9B-30 | **P0** | **MOCK** | Review 9 agent tidak pernah tersimpan di DB demo: 0 baris `SUPERVISE`, 0 baris `agent_name` worker; 8 baris `VERIFY` yang ada adalah literal seed, dan 4 di antaranya berisi klaim angka yang tidak cocok data | SQL §10.1; `seed/demo_kasus_bukti.py:148-152`; `api/demo.py:585-588` | Bukti "9 agent berjalan" di UI berasal dari data semai, bukan dari runtime; 4/4 klaim angka verifier gagal diverifikasi |
| AUD-9B-31 | P2 | **FAIL** | `POST /price/deviation` mengembalikan 500 untuk harga referensi tidak valid (ValueError tidak dipetakan ke 422) | `api/price.py:146-180`; `core/price.py:21-22` | Klien menerima 500 untuk kesalahan input; agent mencatat `error` bukan `degraded` |
| AUD-9B-32 | P2 | **FAIL** | Dua POST komputasi yang dibutuhkan agent tidak dapat dipakai dalam keadaan demo: `/price/deviation` 409 (gerbang sesi), `/logistics/estimate` butuh role mutasi (`MUTATING_ROLES`, agent = `bgn_monitor`) | `main.py:191-204`; `api/logistics.py:20-24`; probe 409 | Dua dari tujuh worker **secara struktural** degraded/error pada demo tanpa sesi aktif; klaim "deviation & ETA dari server" tidak terbukti |
| AUD-9B-33 | P2 | **FAIL** | `step_name` bukan identitas agent: freshness, safety, dan verifier semuanya `VERIFY`; price & logistics `OPTIMIZE`. UI memakai `step_name` untuk panel provider | `hierarchy.json`; `telemetry.py:21`; `frontend/app/page.tsx:169-199` | Tiga baris `VERIFY` tidak dapat dibedakan; panel "verifier provider" bisa terisi dari baris safety/freshness (menampilkan `ok` karena `verdict` tidak ada) |
| AUD-9B-34 | P3 | **FAIL** | `agent_review_timeout_seconds` default 75 dtk dijepit diam-diam ke 45 di pemanggil | `core/config.py:53`; `api/demo.py:1037` | Konfigurasi tidak berperilaku seperti namanya |
| AUD-9B-35 | P1 | **FAIL** | Prioritas "pasokan cukup tetapi terlambat" tidak ditegakkan: `delivery_window` tidak pernah diberikan, `needed_by` tidak dipakai, dan tidak ada pemeriksaan kontinuitas pada keputusan tersimpan (3e2e3cc7 mengekspor 300 kg dari wilayah defisit 58 kg) | `recommendation_service.py:364-367`; `core/logistics.py:96-98`; grep `needed_by` = 0; SQL Bandung/ayam 250 vs 308 | Keterlambatan tidak pernah mengeksklusi kandidat; keputusan bisa memindahkan stok yang tidak ada |
| AUD-9B-36 | P2 | **MISSING** | Tidak ada agent/aturan limbah pada rantai 9 agent, meski limbah adalah prioritas #5 dalam urutan resmi | `AgentName` (`contracts.py:18-28`); `LANES`; `hierarchy.json` | Satu dari lima prioritas tidak terwakili; klaim "limbah diperhitungkan dalam keputusan" tidak punya kode |

---

## 9. Batas audit (yang TIDAK diuji)

- **Runtime AgentCore live** tidak dipanggil dari host (tanpa kredensial AWS).
  Yang diuji adalah `run_review` yang sama, dijalankan lokal terhadap backend.
  Klaim "runtime bekerja" tetap `UNVERIFIED` dari sisi infrastruktur.
- **`POST /demo/event1` / `POST /demo/agent/run`** tidak dieksekusi: butuh
  `sppg_head` + sesi demo aktif (sesi terakhir `expired` 26 Okt 17:13Z). Karena
  itu tidak dapat dibuktikan apakah `agent_review` benar-benar mengembalikan
  `completed` di produksi — dan DB menunjukkan **tidak ada jejaknya**.
- **Kegagalan jaringan nyata** (DNS, 502 gateway) tidak disimulasikan; yang
  disimulasikan adalah exception di worker.
- **Balapan (race)** antar-review bersamaan tidak diuji; worker adalah singleton
  tanpa state, sehingga risiko utamanya hanya thread menumpuk saat timeout.
- **UI** tidak dirender; klaim tentang panel provider berasal dari kode
  `frontend/app/page.tsx:169-199`.

---

## 10. Lampiran: reproduksi

### 10.1 Jejak yang ada di DB

```sql
select step_name, agent_name, count(*) from agent_traces group by 1,2 order by 1;
-- VERIFY: agent_name NULL (7), 'verifier' (1); SUPERVISE: 0 baris; worker agent: 0 baris

select count(*) from agent_traces where step_name='SUPERVISE';      -- 0
select count(*) from agent_traces where agent_name in
  ('supply','demand','freshness','safety','price','logistics','evidence');  -- 0

-- 4 baris VERIFY memuat klaim angka:
select decision_id, tool_called, output_summary
from agent_traces where step_name='VERIFY'
  and (output_summary ? 'verdict' or output_summary ? 'supplier_quote_ratio');
```

### 10.2 Probe perilaku supervisor (in-process, tanpa DB)

Skrip: worker palsu memakai kontrak produksi, `run_review` dipanggil dengan
`api=object()` dan `WorkerContext(decision_id='probe-decision', location='Bandung', commodity='telur')`.
Setiap fakta angka diberi `Citation` otomatis agar lolos lapis 1, kecuali
skenario yang sengaja melanggar.

Hasil ringkas:

```
S1  completed  veto=False  contradictions=[]            verify=pass   verifier=ok
S2  partial    veto=False  contradictions=[]            verify=pass   verifier=ok
S3  EXCEPTION ValueError: worker belum lengkap: logistics
S4  EXCEPTION AttributeError: 'NoneType' object has no attribute 'status'
S5  EXCEPTION ValidationError: List should have at most 7 items …
S6a partial    contradictions=['location']              verify=pass
S6b completed  contradictions=[]                        verify=pass
S6c partial    contradictions=['batch_count']           verify=pass
S7  timeout    semua worker error                       verify=flag  (status_tidak_konsisten)
S8  completed  worker ERROR lalu OK (2 panggilan)       verify=pass
S9  completed  verifier_finding=None                    verify=pass
S10 completed  angka mustahil (shortage 5)              verify=pass   "Audit sepakat"
S11 completed  veto=True                                verify=flag  (safety_veto_aktif)
S12 ValidationError (Supply blocking ditolak)
S13 partial    contradictions=['safe_delivered_cost']   verify=pass   "Audit sepakat"
```

### 10.3 Probe live (angka & keputusan)

```
$ python probe_review.py e7150da4-cb4b-5b46-a380-6fccbeaa3dc9
status partial veto True
safety  ok  {pass:3, fail:0, active_exclusion_count:1} blocking=True
price   degraded  deviasi null  reason=endpoint_error (HTTP 409)
demand  ok  quantity_kg 532.4  |  supply ok  demand_kg 538.0
verify  flag: narasi_tidak_menyebut_penurunan

$ python probe_review.py 3e2e3cc7-f53e-5cee-963d-728e87b6b949
status partial veto True
safety  ok  {fail:1, pending:1, pass:1} blocking=True      ← batch TUJUAN (Jakarta)
approval-summary: safety {worst_status: pass, blocked: false, batches_checked: 3}  ← batch SUMBER (Bandung)
evidence ok  {evidence_count: 0, approval_count: 0} blocking=False
price   ok/degraded  safe_delivered_cost 9750000.0  (tanpa rincian kanonik)
```

Perbedaan baris `safety` vs `approval-summary` pada keputusan yang sama adalah
bukti AUD-9B-29; `evidence_count: 0` yang tidak memblokir adalah bukti C5.
