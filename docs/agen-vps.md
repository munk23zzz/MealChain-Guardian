# Agen MealChain Guardian — menjalankan & memverifikasi di VPS demo

Status berkas: dokumen operasional baru (4 Nov 2026). Sumber kebenaran: kode repo,
bukan tangkapan layar atau ingatan. Semua path:line merujuk commit yang ada di
working tree saat dokumen ditulis.

Batas jujur dokumen ini: **tidak ada VPS hidup yang dihubungi saat menyusunnya.**
Yang bisa dinyatakan "terverifikasi" adalah **jalur kodenya** (endpoint ada, syarat
env terbaca, jalur degradasi terbukti dari fungsi yang dipanggil). Kolom "Status di
VPS demo" di §8 karena itu berbunyi *belum diuji di VPS hidup* sampai perintah di §7
dijalankan di mesin demo dan hasilnya ditempel.

---

## 0. Ringkasan lima baris

1. Ada **tiga keluarga** yang sering disebut "agen": (a) pipeline demo
   `POST /demo/agent/run`, (b) review **9 agen** (7 worker + supervisor + verifier),
   (c) supervisor baca-saja `GET /agent/supervisor/*`.
2. Di `infra/vps/.env.vps.example` hanya (a) dan (c) yang aktif. (b) **mati**
   karena `MULTI_AGENT_REVIEW=false` (`infra/vps/.env.vps.example:105`).
3. (a) tetap berjalan penuh tanpa kredensial model: angka, status, dan blokir
   seluruhnya deterministik; model hanya menyunting narasi.
4. Tanpa model, verifier menjawab `UNAVAILABLE` → keputusan lahir `proposed`
   (bukan `pending_approval`), dan supervisor health hanya berbunyi
   `configured`/`unconfigured` dengan `checked: "config_only"`.
5. AgentCore/Bedrock **tidak dikonfigurasi** di templat VPS: `AGENTCORE_RUNTIME_ARN`
   kosong, tidak ada `AWS_ACCESS_KEY_ID`/profil, tidak ada rantai
   `SUPERVISOR_MODEL_*`/`VERIFIER_*`/`FORECAST_*`.

---

## 1. Tiga keluarga "agen" dan endpoint pemicunya

| Keluarga | Apa yang benar-benar berjalan | Endpoint pemicu | Butuh model? |
|---|---|---|---|
| **Pipeline demo** | 8 tahap: DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → ANALYZE → DECIDE → SUPERVISE; menulis keputusan + baris `agent_traces` **tanpa** `agent_name` | `POST /demo/agent/run` (`backend/app/api/demo.py:1889`) | Tidak. Model hanya untuk narasi per tahap |
| **Review 9 agen** | 7 worker analitik + verifier + baris SUPERVISE, masing-masing satu baris `agent_traces` ber-`agent_name` | Dipicu **di dalam** `POST /demo/agent/run` dan `POST /demo/event1` lewat `agent_review_hook`, hanya bila `MULTI_AGENT_REVIEW=true` (`backend/app/services/agent_review_hook.py:50`) | Tidak wajib — worker deterministik tetap menghasilkan 9 baris; model hanya memperkaya ringkasan |
| **Supervisor baca-saja** | Jawaban dari tool GET (ledger, hitungan keputusan, rantai model); `writes: false` selalu | `GET /agent/supervisor/health`, `POST /agent/supervisor/ask` (`backend/app/api/agent.py:56`, `:90`) | Tidak pernah memanggil model di build ini; `mode: "deterministic"` |

Konsekuensi yang mudah salah dibaca: **`POST /demo/agent/run` bukan pemicu review
9 agen.** Ia memicu review hanya bila flag menyala. Di konfigurasi VPS sekarang,
tombol "Jalankan agent" tetap berjalan, tetapi panel "Kualitas per agen" dan kartu
sembilan agen **tidak akan terisi** — bukan karena bug, karena review dimatikan.

---

## 2. Inventaris 9 agen review (dari kode, bukan karangan)

Nama tampilan di UI berasal dari `frontend/lib/agent-swarm.ts:27-45`; kelas worker
dari `agent/workers/__init__.py:18-27`; peran/stage/endpoint baca dari
`agent/hierarchy.json`; kesembilan kunci juga didaftar di
`agent/workers/reasoner.py:79-90`.

| # | Kunci | Nama di UI | Stage | Kelas/Peran | Butuh apa (ringkas) |
|---|---|---|---|---|---|
| 1 | `supply` | Supply | DETECT | `SupplyWorker` | `GET /supply/{lok}/{kom}`, `GET /balance/{lok}/{kom}` |
| 2 | `demand` | Demand | PREDICT | `DemandWorker` | `GET /demand/{lok}/{kom}`, `GET /demand/forecast/{lok}/{kom}`, `GET /agenda` |
| 3 | `freshness` | Freshness | VERIFY | `FreshnessWorker` | `GET /batches` (profil komoditas di `commodity_policies`) |
| 4 | `safety` | Food Safety | VERIFY | `SafetyWorker` | `GET /batches`, `GET /supplier-exclusions` |
| 5 | `price` | Price | OPTIMIZE | `PriceWorker` | `GET /price/{lok}/{kom}`, `GET /price/quotes/...`, `POST /price/deviation` |
| 6 | `logistics` | Logistics | OPTIMIZE | `LogisticsWorker` | `POST /logistics/estimate`, `GET /supplier-routes` |
| 7 | `evidence` | Evidence | TRACE | `EvidenceWorker` | dossier, chain, compliance, traces, approval-summary, `GET /ledger/verify` |
| 8 | `supervisor` | Supervisor | SUPERVISE | `agent/supervisor_agent.py` + baris SUPERVISE | rantai `SUPERVISOR_MODEL_*` untuk narasi (template bila kosong) |
| 9 | `verifier` | Verifier | VERIFY | `VerifierWorker` (`agent/workers/verifier.py`) | model `VERIFIER_AGENT_MODEL`/`VERIFIER_MODEL_PRIMARY`; tanpa itu fail-closed |

Peran label di papan kualitas: `worker → "Agen analitik"`, `supervisor → "Pengawas"`,
`verifier → "Verifikator"` (`frontend/components/AgentQualityBoard.tsx:61-65`).

### 2.1 Peran di pipeline demo (`POST /demo/agent/run`)

Pipeline ini bukan sembilan agen; ia delapan tahap dengan pembagian tugas:

| Tahap | Siapa yang menghitung | Model dipakai? |
|---|---|---|
| DETECT | `evaluate_suppliers` (kode) | narasi opsional |
| VERIFY | `run_verifier` → rantai `verifier` | ya, bila chain terisi; tanpa chain `UNAVAILABLE` |
| TRACE | `persist_trace_steps` | narasi opsional |
| PREDICT | `forecast_kebutuhan` → rantai `forecast`/SAP-RPT | ya, bila terisi; tanpa itu `statistical_fallback` |
| OPTIMIZE | pemeringkatan pemasok (kode) | narasi opsional |
| ANALYZE | `hypothesis_client.narasi_tahap` → rantai `supervisor` | ya, bila terisi |
| DECIDE | kode; status diturunkan dari verdict | tidak |
| SUPERVISE | `supervisor_client.run_supervisor` | ya, bila terisi; tanpa itu `unavailable` |

Bukti: `backend/app/services/demo_procurement_orchestrator.py` (alur) dan
`:268-272` (verdict → status keputusan).

### 2.2 Endpoint pendukung agen

| Endpoint | Berkas:line | Peran akses | Sifat |
|---|---|---|---|
| `GET /agent/supervisor/health` | `backend/app/api/agent.py:56` | semua pengguna login | baca konfigurasi, **tanpa** panggilan provider |
| `POST /agent/supervisor/ask` | `backend/app/api/agent.py:90` | semua pengguna login | baca-saja, `writes:false` |
| `GET /agent/feedback/rejections` | `backend/app/api/agent.py:188` | semua pengguna login (cakupan lokasi) | baca-saja (langkah LEARN) |
| `GET /demo/agent/stream` | `backend/app/api/demo.py:2168` | `sppg_head` | SSE kemajuan; **tidak** menjalankan pipeline |
| `GET /demo/agent/commodities` | `backend/app/api/demo.py:2298` | `sppg_head`, `sppg_nutritionist` | pilihan + kasus per komoditas |
| `GET /demo/agent/last-run` | `backend/app/api/demo.py:2337` | `sppg_head`, `sppg_nutritionist` | bukti putaran terakhir dari DB |
| `POST /balance/analyze` | `backend/app/api/balance.py:365` | `sppg_head`, `sppg_nutritionist` | rekomendasi deterministik, tanpa agen |
| `POST /balance/recommend` | `backend/app/api/balance.py:226` | idem | idem |
| `GET /integrations/status` | `backend/app/api/integrations.py:149` | semua pengguna login | status env/artefak, `probes_run: 0` |

Catatan: tombol "Jalankan agent" di **Demo Control** memanggil
`POST /demo/agent/run`; tombol bernama sama di **Ops Console** memanggil
`POST /balance/analyze` (mesin rekomendasi deterministik, bukan pipeline agen).
Keduanya sah, tetapi hanya yang pertama menulis jejak agen.

---

## 3. Konfigurasi VPS demo sekarang (fakta dari templat)

| Env | Nilai di `infra/vps/.env.vps.example` | Efek nyata |
|---|---|---|
| `WORKER_AGENT_MODE` | `off` (`:104`) | 7 worker hanya memakai pemeriksa deterministik; tidak ada panggilan model |
| `MULTI_AGENT_REVIEW` | `false` (`:105`) | review 9 agen tidak dijalankan dan **tidak ada** baris review ditulis (`hook` berhenti di `:50`) |
| `AGENT_REVIEW_MODE` | **tidak ada** → default `"advisory"` (`backend/app/core/config.py:52`) | `transport()` menganggap ini jalur AgentCore (`agent_review_local.py:73-80`) |
| `AGENTCORE_RUNTIME_ARN` | tidak ada | jalur AgentCore langsung `unavailable` (`agent_review_client.py:119-123`) |
| `SUPERVISOR_MODEL_PRIMARY`/`VERIFIER_*`/`FORECAST_MODEL` | tidak ada | narasi tahap `unavailable`, verifier `UNAVAILABLE`, forecast `statistical_fallback` |
| `AWS_*` (kredensial) | tidak ada (SECURITY.md melarang kunci asli di berkas ini) | Bedrock/AgentCore tidak bisa dipanggil |
| `DEMO_MODE` | `true` | akun demo (`sppg.head@demo.local` dkk) berlaku |
| `DEMO_SESSION_ENFORCE` | `false` | `POST /demo/agent/run` tidak menolak 409 saat tidak ada sesi aktif |

Kredensial demo hanya dipakai saat `DEMO_MODE` aktif dan dapat ditimpa
`DEMO_PASSWORD_<ROLE>` (`backend/app/seed/demo_credentials.py:29-32`).

---

## 4. Syarat, degradasi, dan verifikasi per agen

Pola umum: **satu kali `POST /demo/agent/run`** menghasilkan satu keputusan dengan
8 baris jejak. Isi `agent_name` pada baris itu hanya lahir dari review 9 agen
(§5). Untuk memeriksa satu agen, bukti terkuat adalah **endpoint baca yang dipakai
agen itu** ditambah baris jejaknya.

Semua perintah memakai dua variabel:

```bash
BASE=https://api.<DOMAIN>      # mis. https://api.demo.mealchain.id
TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"sppg.head@demo.local","password":"<DEMO_PASSWORD_SPPG_HEAD>"}' \
  | jq -r .access_token)
```

Sandi demo: gunakan `DEMO_PASSWORD_SPPG_HEAD` yang Anda setel, atau sandi juri
bawaan saat `DEMO_MODE=true` tanpa override (lihat `demo_credentials.py`). Jangan
menempelkan sandi ke dokumen ini.

### 4.1 Supply (DETECT)

- **Nama UI:** Supply · **Stage:** DETECT
- **Yang menjalankannya:** `POST /demo/agent/run` (tahap DETECT), atau review 9 agen
  bila `MULTI_AGENT_REVIEW=true`.
- **Butuh:** baris `supply_records`/`demand_records` untuk lokasi+komoditas;
  `AGENT_LOCAL_API_URL` (default `http://127.0.0.1:8000`) bila review lokal.
- **Bila tidak dipenuhi:** run dijawab `409` dengan alasan per pemasok/komoditas
  ("tidak ada komoditas yang bisa diproses") — bukan jejak palsu.
- **Verifikasi:**

```bash
curl -s "$BASE/supply/Jakarta/telur" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE/balance/Jakarta/telur" -H "Authorization: Bearer $TOKEN" \
  | jq '{status,gap_kg,supply_kg,demand_kg}'
```

### 4.2 Demand (PREDICT)

- **Nama UI:** Demand · **Stage:** PREDICT
- **Butuh:** `demand_records` + histori ≥ ambang minimum untuk forecast; tanpa
  histori, forecast mengembalikan `statistical_fallback`/`None` dengan alasan.
- **Degradasi:** angka kebutuhan tetap keluar dari DB; hanya prakiraan yang jatuh
  ke statistik lokal.
- **Verifikasi:**

```bash
curl -s "$BASE/demand/Jakarta/telur" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE/demand/forecast/Jakarta/telur?horizon_days=7" \
  -H "Authorization: Bearer $TOKEN" | jq '{method,provider,fallback_used,qty_kg}'
```

`method: "statistical_fallback"` = **tidak ada model** yang menjawab; itu jawaban
jujur, bukan kerusakan.

### 4.3 Freshness (VERIFY, boleh memblokir)

- **Nama UI:** Freshness · **Stage:** VERIFY
- **Butuh:** batch dengan `harvested_at` + profil suhu komoditas
  (`commodity_policies`). Tanpa profil, endpoint menjawab `422`, bukan memakai
  rentang karangan.
- **Degradasi:** tetap deterministik penuh; `WORKER_AGENT_MODE=off` hanya
  menghilangkan kalimat narasi, bukan verdict.
- **Verifikasi:**

```bash
BID=$(curl -s "$BASE/batches?limit=1" -H "Authorization: Bearer $TOKEN" | jq -r '.batches[0].id')
curl -s -X POST "$BASE/freshness/evaluate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"batch_id\":\"$BID\"}" | jq
```

### 4.4 Food Safety (VERIFY, boleh memblokir)

- **Nama UI:** Food Safety · **Stage:** VERIFY
- **Butuh:** log suhu batch + daftar pengecualian pemasok
  (`supplier_exclusions`).
- **Degradasi:** `evaluation_time` kosong = nilai pada sampel terakhir; menggeser
  jam ke depan ditolak `422` (`backend/app/api/safety.py:48-67`).
- **Verifikasi:**

```bash
curl -s -X POST "$BASE/safety/evaluate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"batch_id\":\"$BID\"}" | jq
curl -s "$BASE/supplier-exclusions" -H "Authorization: Bearer $TOKEN" \
  | jq '{count, items: .items[0:3]}'
```

### 4.5 Price (OPTIMIZE)

- **Nama UI:** Price · **Stage:** OPTIMIZE
- **Butuh:** kutipan pemasok + referensi harga (PIHPS) untuk komoditas itu.
- **Degradasi:** tanpa referensi, deviasi tidak dihitung; kandidat tidak diberi
  label anomali (tidak dikarang).
- **Verifikasi:**

```bash
curl -s "$BASE/price/Jakarta/telur" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE/price/quotes/Jakarta/telur" -H "Authorization: Bearer $TOKEN" \
  | jq '{reference, quotes: .quotes[0:3]}'
```

### 4.6 Logistics (OPTIMIZE)

- **Nama UI:** Logistics · **Stage:** OPTIMIZE
- **Butuh:** koordinat lokasi + rute pemasok (`supplier_routes`) atau OSRM hidup.
- **Degradasi:** tanpa rute, `feasible=false` dan jarak `null`; keputusan tetap
  lahir dengan catatan, bukan jarak tebakan.
- **Verifikasi:**

```bash
curl -s -X POST "$BASE/logistics/estimate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"source":"Jakarta","target":"Bandung","quantity_kg":500}' \
  | jq '{distance_km,estimated_time_min,feasible}'
curl -s "$BASE/supplier-routes?commodity=ayam" -H "Authorization: Bearer $TOKEN" \
  | jq '{summary, contoh: .routes[0:2]}'
```

Bila bentuk body berbeda di versi Anda, buka `/openapi.json` pada build
`ENABLE_DOCS=true`, bukan menebak field. Body di atas diambil dari
`LogisticsRequest` (`source`, `target`, `quantity_kg` wajib > 0).

### 4.7 Evidence (TRACE)

- **Nama UI:** Evidence · **Stage:** TRACE
- **Butuh:** keputusan yang sudah ada + blok ledger + dossier/compliance.
- **Degradasi:** keputusan tanpa bukti tetap bisa dibaca; field bukti kosong dan
  `ledger.valid` apa adanya — tidak ada tanda tangan karangan.
- **Verifikasi:**

```bash
DID=<decision_id dari POST /demo/agent/run>
curl -s "$BASE/decisions/$DID/chain" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE/decisions/$DID/dossier" -H "Authorization: Bearer $TOKEN" \
  | jq '{content_address, signature: .signature.state, evidence: (.evidence | length)}'
curl -s "$BASE/ledger/verify" -H "Authorization: Bearer $TOKEN" | jq '{valid,blocks,broken_at}'
```

### 4.8 Supervisor (SUPERVISE)

- **Nama UI:** Supervisor · **Stage:** SUPERVISE · label UI: "Pengawas"
- **Yang menjalankannya di pipeline:** `supervisor_client.run_supervisor` memakai
  rantai `SUPERVISOR_MODEL_PRIMARY` (+ fallback). Endpoint terpisah
  `POST /agent/supervisor/ask` **tidak** memakai model.
- **Butuh:** rantai model supervisor; untuk review 9 agen, narator supervisor juga
  memakai rantai yang sama (`agent_review_local.py:170-214`).
- **Degradasi:** `status: "unavailable"`, baris SUPERVISE tetap ditulis dengan
  `tool_called: supervisor.unavailable` dan `note` — jejak tidak dikosongkan.
  Di UI, status bar supervisor menulis "Supervisor terkonfigurasi, belum diuji
  hidup" untuk `configured` dengan `live:null`
  (`frontend/lib/agent-activity.ts:433`).
- **Verifikasi:**

```bash
curl -s "$BASE/agent/supervisor/health" -H "Authorization: Bearer $TOKEN" | jq
curl -s -X POST "$BASE/agent/supervisor/ask" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"Bagaimana status rantai ledger?"}' | jq '{mode,tool,writes,answer}'
curl -s "$BASE/decisions/$DID/approval-summary" -H "Authorization: Bearer $TOKEN" \
  | jq '.verifier'
curl -s "$BASE/decisions/$DID/traces" -H "Authorization: Bearer $TOKEN" \
  | jq '.steps[] | select(.step_name=="SUPERVISE") | .output_summary'
```

Narasi supervisor tidak ada di `approval-summary`; sumbernya baris `SUPERVISE`
pada `traces` (`output_summary.narrative`/`status`) atau `GET /demo/agent/last-run`.

### 4.9 Verifier (VERIFY, auditor)

- **Nama UI:** Verifier · label UI: "Verifikator"
- **Yang menjalankannya:** (a) tahap VERIFY pipeline demo lewat `run_verifier`;
  (b) `VerifierWorker` di review 9 agen.
- **Butuh:** model verifier — `VERIFIER_AGENT_MODEL`, lalu
  `VERIFIER_MODEL_PRIMARY`, lalu `SUPERVISOR_MODEL_PRIMARY`
  (`agent_review_local.py:63-67`). Fakta audit selalu dari
  `GET /decisions/{id}/audit-facts`, bukan dari model.
- **Degradasi:** pada tahap VERIFY pipeline demo, `UNAVAILABLE` (fail-closed) membuat
  keputusan lahir `proposed`. Pada review 9 agen, `VerifierWorker` tanpa model menulis
  status `degraded` + warning `audit_unavailable` dan **tidak pernah** `consistent`
  (`agent/workers/verifier.py:216-262`).
- **Verifikasi:**

```bash
curl -s "$BASE/decisions/$DID/audit-facts" -H "Authorization: Bearer $TOKEN" | jq 'keys'
curl -s "$BASE/decisions/$DID/approval-summary" -H "Authorization: Bearer $TOKEN" \
  | jq '.verifier'
```

`{"verdict":"unavailable"}` = tidak ada model; itu keadaan yang benar di VPS demo
sekarang, bukan tanda sistem rusak.

### 4.10 Peran tambahan di pipeline: Forecast & Analyzer

Keduanya bukan kartu di papan 9 agen, tetapi memakai model dan punya jejak tahap:

| Peran | Tahap | Env model | Degradasi |
|---|---|---|---|
| Forecast | PREDICT | `FORECAST_MODEL` (+ fallback) | `statistical_fallback` lokal |
| Analyzer (hipotesis sebab) | ANALYZE | rantai `SUPERVISOR_MODEL_*` | `unavailable`; keputusan tetap lahir |

Verifikasi: baca `steps[].output_summary.{method,provider,status}` pada
`GET /decisions/$DID/traces`.

---

## 5. AgentCore/Bedrock: apa yang hilang di VPS demo

### 5.1 `WORKER_AGENT_MODE=off` vs `advisory`

`off` dan `advisory` **bukan** dua tingkat kualitas yang sama; keduanya memakai
pemeriksa deterministik yang identik, yang berbeda hanya apakah model boleh
menyunting ringkasan:

| | `off` (nilai VPS) | `advisory` |
|---|---|---|
| Angka, status, `blocking`, sitasi | kode | kode (tidak berubah) |
| Ringkasan worker | template | model boleh memperkaya, angka baru ditolak utuh |
| Panggilan model | tidak ada | ada, bila `WORKER_AGENT_MODEL` terisi |
| Kalau model gagal | tidak berlaku | temuan deterministik dipertahankan, alasan dicatat |

Implementasi: `agent/workers/base.py:190-253` dan `agent/workers/reasoner.py:63-96`.
Default kode adalah `advisory`; nilai `off` di VPS adalah keputusan operator, bukan
bawaan bahasa.

Catatan penting: `WORKER_AGENT_MODE` hanya menyentuh **7 worker di review 9 agen**.
Narasi tahap pipeline demo (`DETECT`..`SUPERVISE`) digerakkan oleh rantai
`SUPERVISOR_MODEL_*`/`VERIFIER_*`/`FORECAST_*`, bukan oleh flag ini.

### 5.2 Review 9 agen: dua transport, satu flag

- `MULTI_AGENT_REVIEW=false` → `jalankan_agent_review` mengembalikan
  `{"status":"disabled"}` dan **tidak menulis baris review**
  (`backend/app/services/agent_review_hook.py:49-51`).
- `MULTI_AGENT_REVIEW=true` + `AGENT_REVIEW_MODE=local` → orkestrator repo berjalan
  **di dalam backend**; butuh token internal (dibuat dari pengguna pemanggil) dan
  `AGENT_LOCAL_API_URL` yang menunjuk backend itu sendiri.
- `MULTI_AGENT_REVIEW=true` + mode lain (termasuk default `advisory`) → jalur
  AgentCore; tanpa `AGENTCORE_RUNTIME_ARN` hasilnya `unavailable` dengan pesan
  "runtime AgentCore belum dikonfigurasi", dan hanya satu baris SUPERVISE kegagalan
  yang disimpan (`agent_review_hook.py:147-173`).

Artinya: **9 baris review bisa dibuat tanpa kredensial model sama sekali**, asalkan
`MULTI_AGENT_REVIEW=true` dan `AGENT_REVIEW_MODE=local`; verifier akan
`degraded/unavailable`, supervisor memakai narasi template. Yang tidak bisa adalah
mengklaim model menjawab.

### 5.3 Supervisor health hanya membuktikan konfigurasi

`GET /agent/supervisor/health` mengembalikan `status`, `live`, `checked`,
`slots`, dan `detail`:

- `live` **selalu `null`** — tidak ada probe provider di jalur ini
  (`backend/app/api/agent.py:56-79`).
- `checked: "config_only"` — bukti yang diberikan adalah "rantai env terbaca",
  bukan "model menjawab".
- `status: "configured"` hanya berarti `get_agent_chain("supervisor")` tidak kosong.
- `status: "unconfigured"` berarti jawaban agent memakai tool deterministik.

Karena itu, di VPS demo sekarang endpoint ini akan berbunyi `unconfigured` dengan
`slots: 0`. Jika suatu saat ARN/env terisi, ia berbunyi `configured` tetapi
**tetap bukan bukti hidup**. Satu-satunya bukti hidup adalah satu baris jejak
dengan `provider`/`duration_ms` nyata, atau `POST /agent/supervisor/ask` yang
menyebut tool yang dipakai (dan itu pun deterministik).

### 5.4 Yang hilang, daftar tertutup

| Kebutuhan AgentCore/Bedrock | Status di templat VPS | Bukti |
|---|---|---|
| `AGENTCORE_RUNTIME_ARN` | kosong | tidak ada di `.env.vps.example` |
| Kredensial AWS (role/env/profil) | tidak ada; SECURITY.md melarang kunci di `.env` | `.env.vps.example` tidak memuat `AWS_*` |
| Runtime image `agent/` ter-deploy | belum | `agent/README-deploy.md`; `/integrations/status` menulis "artefak siap" |
| `AGENTCORE_GATEWAY_URL` | kosong → gateway "belum dimulai" | `backend/app/api/integrations.py:99-110` |
| `AGENTCORE_MEMORY_ID` | kosong → memory "tidak tersedia" | `backend/app/api/integrations.py:111-125` |
| Rantai model `SUPERVISOR_MODEL_*` | kosong | `.env.example:189-201` (contoh, tidak disalin ke VPS) |
| `VERIFIER_AGENT_MODEL`/`VERIFIER_MODEL_PRIMARY` | kosong | `.env.example:203-216` |
| `FORECAST_MODEL` | kosong | `.env.example` |
| Probe hidup | **tidak ada** | `GET /integrations/status` → `probes_run: 0` |

### 5.5 Kalau ingin menyalakan model di VPS (urutan aman)

1. Isi kredensial AWS lewat mekanisme host (instance role / `secrets/aws-app.env`
   yang tidak masuk repo), bukan ke `.env.vps.example`.
2. Isi satu rantai saja dulu, mis. `SUPERVISOR_MODEL_PRIMARY` + `AWS_REGION`.
3. `MULTI_AGENT_REVIEW=true` **dan** `AGENT_REVIEW_MODE=local` untuk menghindari
   ketergantungan runtime AgentCore yang belum ter-deploy.
4. `WORKER_AGENT_MODE=advisory` + `WORKER_AGENT_MODEL=<id>` hanya setelah langkah 2
   terbukti (verifier butuh modelnya sendiri lewat `VERIFIER_AGENT_MODEL`).
5. Ulangi §7 dan pastikan baris jejak menyebut `provider`, bukan hanya `status`.

Jangan menyalakan `MULTI_AGENT_REVIEW=true` dengan `AGENT_REVIEW_MODE` default
(`advisory`) tetapi ARN kosong: hasilnya satu baris SUPERVISE gagal per keputusan —
kelihatan "ada review" padahal tidak ada.

---

## 6. Bacaan panel yang perlu disamakan

- **Kualitas per agen** menghitung run yang **berisi baris** agen itu, lalu yang
  barisnya membawa keluaran (`frontend/lib/agent-quality.ts:269-296`). Tanpa run,
  daftarnya kosong — bukan sembilan baris nol.
- Supervisor dihitung dari tahap `SUPERVISE` atau `tool_called` berawalan
  `supervisor.` (`agent-quality.ts:108-122`); verifier dari `agent_name=verifier`
  atau alias `verifier_agent`.
- Papan ini membaca `GET /decisions/{id}/traces` dan
  `GET /decisions/{id}/approval-summary`; verdict verifier tidak ditulis di
  `agent_traces`, jadi angkanya diambil dari approval-summary.
- Karena pipeline demo menulis baris **tanpa** `agent_name`, papan akan menulis
  "belum ada run agen yang tercatat" selama review 9 agen mati. Itu konsisten
  dengan konfigurasi, bukan kontradiksi.

---

## 7. Prosedur verifikasi berurutan (siap tempel)

```bash
BASE=https://api.<DOMAIN>
# 0) backend hidup (tanpa token)
curl -s "$BASE/health" | jq

# 1) token
TOKEN=$(curl -s -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"sppg.head@demo.local","password":"<DEMO_PASSWORD_SPPG_HEAD>"}' \
  | jq -r .access_token)
curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN" | jq '{role,location_name}'

# 2) data demo ada
curl -s "$BASE/demo/data-status" -H "Authorization: Bearer $TOKEN" | jq

# 3) status integrasi (harus probes_run: 0) + supervisor
curl -s "$BASE/integrations/status" -H "Authorization: Bearer $TOKEN" \
  | jq '{probes_run, components: [.components[] | {id,category}]}'
curl -s "$BASE/agent/supervisor/health" -H "Authorization: Bearer $TOKEN" | jq

# 4) komoditas yang benar-benar bisa dijalankan
curl -s "$BASE/demo/agent/commodities" -H "Authorization: Bearer $TOKEN" \
  | jq '.kasus[] | select(.bisa_dijalankan) | {commodity,status,gap_kg}'

# 5) jalankan satu putaran (jalur pipeline demo).
#    Tanpa "commodity" = satu putaran per komoditas; yang tidak punya celah
#    dilewati dan dilaporkan di "skipped" (bukan menggagalkan semuanya).
RUN=$(curl -s -X POST "$BASE/demo/agent/run" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"ttl_minutes":30}')
echo "$RUN" | jq '{decision_id, trace_steps, verifier: .verifier.verdict, supervisor: .supervisor.status, agent_review}'
DID=$(echo "$RUN" | jq -r .decision_id)

# 6) bukti jejak + keputusan
curl -s "$BASE/decisions/$DID/traces" -H "Authorization: Bearer $TOKEN" \
  | jq '[.steps[] | {step_name, tool_called, agent_name, duration_ms}]'
curl -s "$BASE/decisions/$DID" -H "Authorization: Bearer $TOKEN" | jq '{decision_id,status,valid,commodity,supplier}'
curl -s "$BASE/decisions/$DID/approval-summary" -H "Authorization: Bearer $TOKEN" | jq '.verifier'
curl -s "$BASE/demo/agent/last-run?decision_id=$DID" -H "Authorization: Bearer $TOKEN" \
  | jq '{found, agents, agents_run_id}'

# 7) supervisor tanya-jawab (deterministik, writes:false)
curl -s -X POST "$BASE/agent/supervisor/ask" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"Berapa keputusan yang menunggu persetujuan?"}' | jq

# 8) feedback/LEARN
curl -s "$BASE/agent/feedback/rejections?limit=5" -H "Authorization: Bearer $TOKEN" \
  | jq '{jumlah,cakupan,sumber}'
```

Yang diharapkan pada konfigurasi VPS sekarang:

- langkah 5: `trace_steps` berisi delapan tahap, `verifier.verdict = "UNAVAILABLE"`,
  `supervisor.status = "unavailable"`, `agent_review.status = "disabled"`;
- langkah 6: `agent_name` **null** di semua baris, `agents: []`;
- langkah 7: `mode: "deterministic"`, `writes: false`;
- langkah 3: `agentcore_runtime.category = "artifacts_ready"`,
  `agentcore_gateway.category = "not_started"`.

Bila angka itu berbeda, jangan menambal dokumen — periksa env kontainer lebih dulu:
`docker compose -f infra/vps/docker-compose.vps.yml exec backend env | grep -E 'WORKER_AGENT_MODE|MULTI_AGENT_REVIEW|AGENT_REVIEW_MODE|SUPERVISOR|VERIFIER|FORECAST|AGENTCORE'`.

### 7.1 Membuktikan review 9 agen (tanpa kredensial model)

```bash
# di infra/vps/.env
#   MULTI_AGENT_REVIEW=true
#   AGENT_REVIEW_MODE=local
#   WORKER_AGENT_MODE=off
bash infra/vps/deploy.sh          # build ulang + migrasi; seed dilewati
```

Lalu ulangi langkah 5–6. Harapan baru:

- `GET /decisions/$DID/traces` memuat **9 baris** dengan `agent_name`
  (`supply`…`verifier`, `supervisor`);
- verifier: `output_summary.status = "degraded"`, `audit_verdict = "unavailable"`;
- supervisor: narasi template (`source: "template"`), bukan model;
- papan "Kualitas per agen" seharusnya menampilkan 9 baris untuk keputusan itu
  (sampel panel = keputusan terbaru yang punya review).

Bila tetap kosong, periksa `agent_review` pada respons langkah 5: `unavailable`
dengan pesan "paket agent tidak dapat diimpor" berarti image backend tidak memuat
paket `agent/`; itu masalah build, bukan konfigurasi model.

---

## 8. Tabel ringkas

Kolom status dipisah dua: **jalur kode** (terverifikasi dari sumber di repo) dan
**VPS demo** (belum diuji di mesin hidup pada sesi penyusunan dokumen ini).

| Agen / peran | Endpoint yang menjalankannya | Butuh | Status jalur kode | Status di VPS demo |
|---|---|---|---|---|
| Supply | `POST /demo/agent/run` (DETECT); baca `/supply`, `/balance` | baris pasokan/kebutuhan | terverifikasi | belum diuji; diharapkan jalan (deterministik) |
| Demand | `POST /demo/agent/run` (PREDICT); baca `/demand`, `/demand/forecast` | histori demand | terverifikasi | belum diuji; forecast = `statistical_fallback` |
| Freshness | `POST /demo/agent/run` (VERIFY); `/freshness/evaluate` | batch + profil suhu | terverifikasi | belum diuji; deterministik |
| Food Safety | `POST /demo/agent/run` (VERIFY); `/safety/evaluate` | log suhu + exclusion | terverifikasi | belum diuji; deterministik |
| Price | `POST /demo/agent/run` (OPTIMIZE); `/price/*` | kutipan + referensi harga | terverifikasi | belum diuji; tanpa anomali bila referensi kosong |
| Logistics | `POST /demo/agent/run` (OPTIMIZE); `/logistics/estimate` | rute / OSRM | terverifikasi | belum diuji; `feasible` bisa false |
| Evidence | `POST /demo/agent/run` (TRACE); `/decisions/{id}/*`, `/ledger/verify` | keputusan + ledger | terverifikasi | belum diuji |
| Supervisor (narasi) | tahap SUPERVISE; `GET /agent/supervisor/health`, `POST /agent/supervisor/ask` | rantai `SUPERVISOR_MODEL_*` untuk narasi | terverifikasi | **belum** — `unavailable`; health `config_only` |
| Verifier | tahap VERIFY (`run_verifier`) + `VerifierWorker` | model `VERIFIER_AGENT_MODEL`/`VERIFIER_MODEL_PRIMARY` | terverifikasi | **belum** — `UNAVAILABLE`, keputusan `proposed` |
| Review 9 agen (keseluruhan) | dipicu di dalam `POST /demo/agent/run` / `/demo/event1` | `MULTI_AGENT_REVIEW=true` (+ `AGENT_REVIEW_MODE=local` bila tanpa AgentCore) | terverifikasi | **belum** — dimatikan di templat |
| Forecaster | tahap PREDICT | `FORECAST_MODEL`/SAP-RPT | terverifikasi | **belum** — fallback statistik |
| Analyzer (hipotesis) | tahap ANALYZE | rantai `SUPERVISOR_MODEL_*` | terverifikasi | **belum** — `unavailable` |
| AgentCore Runtime | transport review + slot model | `AGENTCORE_RUNTIME_ARN` + kredensial AWS + runtime ter-deploy | terverifikasi | **belum** — ARN kosong |
| AgentCore Gateway / Memory | `/integrations/status` | `AGENTCORE_GATEWAY_URL`, `AGENTCORE_MEMORY_ID` | terverifikasi | **belum** — "belum dimulai"/"tidak tersedia" |
| Feedback/LEARN reader | `GET /agent/feedback/rejections` | keputusan `rejected` + penerimaan `ditolak` | terverifikasi | belum diuji; baca-saja |

Cara mengubah kolom terakhir menjadi "terverifikasi": jalankan §7 di VPS demo,
tempel keluaran `verifier.verdict`, `supervisor.status`, `agent_review.status`, dan
`trace_steps` ke laporan demo. Dokumen ini tidak mengklaim lebih dari itu.
