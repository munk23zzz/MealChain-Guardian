# 9_AGENT_INVENTORY — MealChain Guardian

Status: **inventarisasi berbasis kode + runtime** — 26 Oktober 2026.
Lingkungan: stack berjalan (`mealchain-backend` :8000, `mealchain-postgres` :15432, db `mealchain`),
HEAD `57db099`. DB demo **hanya SELECT**; tidak ada kode/DB yang diubah oleh audit ini.
Metode: baca kode (`agent/`, `backend/app/**`), jalankan probe **read-only** ke runtime
AgentCore (`review_decision`, `run_supervisor`, `run_verifier`), dan kueri DB.

Pasangan dokumen ini: `9_AGENT_DEEP_AUDIT.md` (temuan AUD-9A-xx per agent).
Audit lapisan pipeline (DETECT→…→LEARN) sudah ada di `AGENT_WORKFLOW_AUDIT.md` dan **tidak diulang** di sini.

---

## 0. Ringkasan satu paragraf

Sistem ini **bukan** berisi sembilan agent otonom. Yang ada: **8 kelas agent read-only**
di paket `agent/` (7 analitik + 1 auditor) yang dijalankan oleh satu orkestrator
(`agent/orchestrator.py`) di dalam **satu** AgentCore Runtime, ditambah **satu peran
Supervisor** yang hidup di dua tempat berbeda (klien narasi LLM di backend, dan baris
ringkasan template di putaran review). Kesembilan "baris" yang sering disebut "9 agen"
adalah **7 baris worker + 1 baris verifier + 1 baris SUPERVISE** di `agent/telemetry.py`
(`build_trace_rows`), bukan sembilan proses/agent terpisah. Tidak satu pun dari 8 worker
memanggil LLM; hanya Supervisor (narasi) dan Verifier LLM (backend) yang memanggil model.

---

## 1. Tabel 9 peran

Kolom "Jenis" membedakan tegas: **D** = deterministik (tanpa LLM), **LLM** = panggilan model,
**TOOL** = memanggil endpoint/tool, **WORKER** = kelas worker dalam satu putaran review.

| # | Peran (klaim) | Status | Implementasi (file:baris) | Jenis | Endpoint yang benar-benar dipanggil | Dependency runtime |
|---|---|---|---|---|---|---|
| 1 | **Supervisor** | **PARTIAL** | (a) narasi LLM: `backend/app/services/supervisor_client.py:73-125` → chain env; (b) agent Strands: `agent/supervisor_agent.py:84-95` + 4 tool `agent/tools.py:95,149,216,248`; (c) baris trace SUPERVISE di putaran review: **template** `agent/orchestrator.py:190-212` | LLM (a,b) + **template** (c) | `GET /balance/*`, `GET /batches`, `GET /decisions/{id}/approval-summary`, `GET /decisions/{id}/traces`, `GET /decisions/{id}/dossier` (via tool LLM) | AgentCore Runtime `READY v30`; model di runtime = `us.anthropic.claude-haiku-4-5-20251001-v1:0`; token API JWT role `bgn_monitor` exp **2026-11-17** |
| 2 | **Supply Agent** | **IMPLEMENTED** | `agent/workers/supply.py:13-113` | D + TOOL | `GET /balance/{loc}/{com}` | API backend (Bearer token agen) |
| 3 | **Demand Agent** | **IMPLEMENTED** | `agent/workers/demand.py:13-117` | D + TOOL | `GET /demand/{loc}/{com}`, `GET /demand/forecast/{loc}/{com}?horizon_days=7` | API backend; forecast = `statistical_forecast` (bukan SAP-RPT) — `backend/app/api/demand.py:63` |
| 4 | **Freshness Guardian** | **IMPLEMENTED (semantik menyimpang)** | `agent/workers/freshness.py:25-139`; ambang certified ada di `backend/app/core/freshness.py:7-8` tapi **tidak dipakai** worker | D + TOOL | `GET /batches` (paginasi, `agent/api_client.py:68-97`) | API backend |
| 5 | **Safety Guardian** | **IMPLEMENTED (veto tidak di-scope)** | `agent/workers/safety.py:12-147` | D + TOOL | `GET /batches`, `GET /supplier-exclusions` (**bukan** `/supplier-exclusions/context/{decision_id}` yang dideklarasikan `agent/hierarchy.json:47`) | API backend |
| 6 | **Price Agent** | **IMPLEMENTED (degraded di runtime)** | `agent/workers/price.py:17-224` | D + TOOL | `GET /price/quotes/*`, `GET /price/*`, `POST /price/deviation`, `GET /decisions/{id}/approval-summary` | API backend; `POST` kena gerbang sesi demo → **409** |
| 7 | **Logistics Agent** | **IMPLEMENTED** | `agent/workers/logistics.py:13-255` | D + TOOL | `GET /supplier-routes`; `POST /logistics/estimate` hanya bila tidak ada rute | API backend; `POST /logistics/estimate` butuh role mutasi (`backend/app/api/logistics.py:23`) |
| 8 | **Evidence Fusion Agent** | **IMPLEMENTED** | `agent/workers/evidence.py:13-222` | D + TOOL | `GET /decisions/{id}/dossier`, `/compliance`, `/chain`, `/approval-summary`, `GET /ledger/verify` (**tidak** `/traces`, padahal dideklarasikan `agent/hierarchy.json:84`) | API backend; ledger global 2.034 blok |
| 9 | **Independent Verifier** | **PARTIAL (klaim independensi FAIL)** | (a) auditor deterministik: `agent/workers/verifier.py:71-124`; (b) gerbang: `agent/verify.py:18-65`; (c) **Verifier LLM**: `backend/app/ai_providers/verifier_client.py:105-196` | D (a,b) + LLM (c) | (a) tidak membaca API (menilai `AgentRun` di memori); (c) chain env → **AgentCore Runtime yang sama dengan Supervisor** | Runtime sama + model sama + *system prompt supervisor* (`agent/runtime_server.py:49-51`) → bukan penilai independen |

Keterangan status: `IMPLEMENTED` = kode nyata, dipanggil runtime, hasil terverifikasi;
`PARTIAL` = ada, tetapi salah satu klaim intinya tidak terpenuhi;
`MOCK`/`STUB`/`MISSING` = tidak dipakai pada tabel ini (lihat §4).

---

## 2. Jumlah aktual vs angka "9"

| Ukuran | Angka | Bukti |
|---|---|---|
| Peran yang dinamai di dokumen/UI | 9 | `docs/MEALCHAIN_GUARDIAN_LENGKAP.md` §8; `frontend/components/AgentSwarmPanel.tsx:1` menyebut "review 8 agen… tujuh analitik + verifier" |
| Kelas agent terdaftar di runtime | **8** | `agent/registry.py:114` memuat `AGENTS` dari `agent/hierarchy.json`; dijalankan: `python -c "from agent.registry import AGENTS; print(len(AGENTS))"` → **8** |
| Worker yang benar-benar dieksekusi per putaran | **7 analitik + 1 auditor** | `agent/orchestrator.py:253-260` (wajib 8 nama unik), `agent/contracts.py:194` (`findings` tepat 7) |
| Baris trace per putaran review | **9** | `agent/telemetry.py:13-110` (7 worker + verifier + SUPERVISE); diterima backend: `backend/app/services/trace_persistence.py:90` (`len in (8, 9)`) |
| Agent yang memanggil LLM | **1** (Supervisor narasi; verifier worker `model=None`) | `agent/workers/verifier.py:38`; tidak ada impor `strands`/`boto3` di `agent/workers/*` |
| Peran tanpa kelas agent (hanya subrutin/klien) | **1** (Supervisor) | Supervisor tidak ada di `AgentName` (`agent/contracts.py:18-28`); baris SUPERVISE dibuat `agent/orchestrator.py:190-212` |

**Kesimpulan angka:** "9 agent" = **8 agent + 1 baris ringkasan Supervisor**, bukan 9 agent.
Kalau yang dimaksud "agent" adalah *proses otonom yang memutuskan sendiri*, angkanya **0**:
tidak ada loop, scheduler, atau inisiatif mandiri — semua worker dipanggil satu orkestrator
dalam satu request (`docs/MEALCHAIN_GUARDIAN_LENGKAP.md:617-619` sudah menyatakan ini).

---

## 3. Bukti runtime satu putaran (bukan asumsi)

Perintah (read-only; dijalankan di dalam `mealchain-backend`, tidak menulis DB):

```python
from app.services.agent_review_client import review_decision
review_decision("a693308f-f4e7-4e46-87ea-449a17efacea", timeout_seconds=90)
```

Hasil nyata — **`status=partial`, `run_id=e9d7e784-…`, 9 baris trace, 3,9–7,1 detik**:

| Baris | Agent | Status | Ringkasan (kutipan) |
|---|---|---|---|
| DETECT | supply | ok | "Pasokan 300.0 kg; permintaan 1080.0 kg; status shortage." |
| PREDICT | demand | ok | "Permintaan 1074.11 kg; forecast 7 hari 7509.76 kg." |
| VERIFY | freshness | ok | "3 batch; 0 kedaluwarsa; skor kesegaran terburuk 0.82." |
| VERIFY | safety | ok (**blocking=True**) | "3 batch: 3 pass, 0 pending, 0 fail; exclusion aktif 1." |
| OPTIMIZE | price | **degraded** | "…deviasi tidak tersedia (tidak diketahui)…" (HTTP 409 dari `/price/deviation`) |
| OPTIMIZE | logistics | ok | "3 rute aktif; 3 punya geometri jalan; jarak 22.0–23.1 km." |
| TRACE | evidence | ok (**blocking=True**) | "evidence 1, approval 0, trace 2, chain 1; ledger valid; tanda tangan signed." |
| VERIFY | verifier | degraded | "Audit menandai putaran ini: narasi_tidak_menyebut_penurunan…" |
| SUPERVISE | supervisor | partial | "Review 7 agen menemukan guardian yang memblokir…" (**template**) |

Bukti pendukung lain:

| Butir | Hasil | Perintah |
|---|---|---|
| Runtime AgentCore | **READY**, versi 30, `lastUpdatedAt 2026-10-26T03:30Z` | `boto3.client("bedrock-agentcore-control").get_agent_runtime(...)` |
| Model di runtime | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | `environmentVariables` runtime |
| API yang dipakai runtime | URL quick tunnel Cloudflare (`age-debian-…trycloudflare.com`), bukan `http://backend:8000` | `environmentVariables.MEALCHAIN_API_URL` |
| Narasi supervisor LIVE | `narrated`, `provider=primary:agentcore`, 6,7 s, 1 attempt sukses | `run_supervisor(ctx, timeout_seconds=90)` |
| Verifier LLM LIVE | `CONSISTENT`, `provider=primary:agentcore`, 5,6 s (untuk freshness 0,82) | `run_verifier(ctx, timeout_seconds=90)` |
| Trace di DB demo | 85 baris; **0 baris ber-`run_id`**, **0 baris `SUPERVISE`**; `agent_name` berisi label template (`detection_agent`, `supervisor_agent`, `sap_agent`, `orchestrator`) | `select step_name, agent_name, count(*), count(run_id) from agent_traces group by 1,2` |

Implikasi jujur: **jalur 8 agent terbukti hidup**, tetapi **belum pernah tersimpan** ke
`agent_traces` di DB demo (tidak ada satu pun baris hasil review; lihat AUD-9A-01).

---

## 4. Komponen MISSING / STUB / MOCK (apa adanya)

| Komponen | Status | Bukti |
|---|---|---|
| Supervisor sebagai *worker* dalam registry | **MISSING** | `agent/hierarchy.json` hanya 8 nama; `agent/contracts.py:18-28` tidak punya `SUPERVISOR` |
| `StubWorker` (P1) masih diekspor & dipakai tes | **STUB** | `agent/workers/base.py:32-166`, `agent/workers/__init__.py:32-44`, dipakai `backend/tests/test_agent_runtime_task.py:70` |
| Model pada Verifier worker | **MISSING (by design)** | `agent/workers/verifier.py:38` — `model=None` di produksi; tidak ada provider yang dipasang di `agent/orchestrator.py:295-304` |
| Verifier yang benar-benar independen dari Supervisor | **MISSING** | rantai verifier & supervisor sama-sama `primary:agentcore` (`backend/app/ai_providers/model_registry.py:123-125`), runtime yang sama, system prompt supervisor (`agent/runtime_server.py:49-51`) |
| Workforce untuk stage ACT/LEARN | **MISSING** | tidak ada agent; ACT/LEARN adalah endpoint manusia (`docs/audit/AGENT_WORKFLOW_AUDIT.md:22-23`) |
| Tool-call telemetry Supervisor | **MISSING** | `agent/tools.py` tidak menulis jejak; `run_supervisor` hanya mencatat provider (`backend/app/services/supervisor_client.py:119-125`) |
| `GET /supplier-exclusions/context/{decision_id}` dipakai worker | **MISSING** (dideklarasikan) | `agent/hierarchy.json:47` vs `agent/workers/safety.py:75` |
| `GET /decisions/{id}/traces` dipakai Evidence/Verifier | **MISSING** (dideklarasikan) | `agent/hierarchy.json:84,97` vs `agent/workers/evidence.py:25-29` |
| Persist hasil review di luar `/demo/event1` & `/demo/agent/run` | **MISSING** | hanya `backend/app/api/demo.py:1021,1228` memanggil `persist_agent_review` |

---

## 5. Peta dependency (siapa butuh siapa)

```
request /demo/event1 | /demo/agent/run
        │
        ├── run_event1 (backend, deterministik)  → DETECT/PREDICT/DECIDE/SUPERVISE/…(tulis DB)
        │        ├── run_verifier  ── LLM ──► AgentCore Runtime (model haiku-4-5)
        │        ├── run_forecast  ── SAP AI Core RPT (bila env lengkap)
        │        └── run_supervisor ─ LLM ──► AgentCore Runtime (Strands + 4 tool HTTP)
        │
        └── review_decision → AgentCore Runtime (invoke) → run_review (8 agent)
                 ├── 7 worker read-only ──HTTP(Bearer bgn_monitor)──► backend API
                 │        (URL = quick tunnel Cloudflare, bukan jaringan docker)
                 ├── verify_run (deterministik, tanpa model)
                 └── VerifierWorker.audit (deterministik, tanpa model)
                          └── hasil 9 baris → persist_agent_review (hanya via endpoint demo)
```

Titik tunggal kegagalan: (1) runtime AgentCore, (2) URL tunnel, (3) JWT agen exp 2026-11-17,
(4) sesi demo aktif (untuk tool POST). Lihat AUD-9A-06/07.

---

## 6. Yang TIDAK bisa disimpulkan dari inventarisasi ini

| Klaim | Status |
|---|---|
| "9 agen berjalan otonom" | **Tidak didukung** — 8 agent dipanggil satu orkestrator per request |
| "9 baris trace tersimpan untuk tiap keputusan" | **Tidak didukung** — 0 baris review tersimpan di DB demo |
| "Verifier menilai ulang secara independen" | **Tidak didukung** — lihat AUD-9A-03 |
| Kualitas penalaran model (apakah verdict tepat) | **NOT TESTED** (di luar lingkup; audit menilai struktur & perilaku) |
| Persist 9 baris via UI (`/demo/agent/run`) | **NOT TESTED** (butuh POST/tulis — tidak dijalankan audit ini) |
