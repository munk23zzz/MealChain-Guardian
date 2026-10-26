# Fase 11 — Supervisor Agent Strands + Event 1 penuh dari UI

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal: 2026-10-16 · Assignee: Hermes · Repo: `E:\hackathon\HackathonAWS\mealchain-guardian`
Branch: `feature/sprint2-decision-intelligence` (belum ada commit/push)

## Permintaan pemilik (kutip apa adanya)

> "wait, gua mau tanya apakah supervisor agent sudah terimplementasi??"

lalu, setelah audit dijawab:

> "kerjakan saja berurutan, namun tetap di cek bahwa semua berjalan di frontend maupun backend dll"

Urutan yang diminta = (a) implementasi `agent/supervisor_agent.py`, (b) sambungkan `run_event1` ke
aplikasi supaya langkah SUPERVISE benar-benar jalan, (c) selaraskan klaim dokumen.

## 1. Temuan audit SEBELUM perubahan

| # | Temuan | Bukti |
|---|---|---|
| 1 | **`agent/supervisor_agent.py` TIDAK ADA.** `agent/` hanya berisi dua `__init__.py` (28 & 32 byte). | `find agent -type f`; `git log --all -- agent/supervisor_agent.py` kosong — tak pernah ada di riwayat repo mana pun |
| 2 | **Tesnya ada dan merah, tapi tersembunyi.** `tests/test_supervisor_agent.py` mengimpor `supervisor_agent` → `ModuleNotFoundError`. Karena `agent/` tidak ada di kontainer, berkas itu masuk `collect_ignore` HOST_ONLY (`backend/tests/conftest.py:17-24`) → suite kontainer tetap hijau. | `pytest -q tests/test_supervisor_agent.py` → 1 error |
| 3 | **Klaim dokumen tidak cocok kode**: `docs/verification/sprint-3.md` menulis "Strands Agent `agent/supervisor_agent.py` (root) — BLOCKED live", padahal berkasnya tidak pernah ada. `TODO.md` S0-06 "Strands SDK hello-world agent" = **Not Started**. | `grep -rn "supervisor_agent" docs/` |
| 4 | **`run_event1` hanya dipanggil berkas tes.** Tidak ada endpoint/UI yang memicunya, sehingga langkah SUPERVISE (narasi supervisor) tidak pernah muncul di aplikasi yang dilihat juri. | `grep -rn "run_event1" backend --include=*.py \| grep -v /tests/` → hanya definisi |
| 5 | **Jejak SUPERVISE hampir kosong di DB**: 1 baris (6 Okt 19:37 UTC) vs DETECT 83 / OPTIMIZE 80 / LEARN 80. Keputusan demo lahir dari `_seed_demo_cases` (`app/api/demo.py`) yang menulis jejak sintetis, bukan dari orkestrator. | `SELECT step_name, count(*) FROM agent_traces GROUP BY 1` |
| 6 | **Proxy dev Next memutus koneksi di 30 detik.** `node_modules/next/dist/server/lib/router-utils/proxy-request.js:31` → `proxyTimeout || 30000`, dibaca dari `config.experimental.proxyTimeout`. | lihat §4.3 |

## 2. Perubahan

### (a) Supervisor Agent Strands — dibuat
- `agent/supervisor_agent.py` — `load_system_prompt()`, `build_agent(model_id)`, `run_hello_world()`.
  Atribut Strands diakses lewat modul (`strands.Agent`, `strands.models.BedrockModel`) supaya kontrak
  mock tes S0-07 (`patch("strands.Agent")`) benar-benar berpengaruh — impor `from strands import Agent`
  akan mengikat nama saat impor dan membuat mock tidak terpakai.
- `agent/prompts/supervisor_system_prompt.md` — prompt pengawas: angka **safety-critical** hanya dari tool
  **deterministik**, safety status tidak pernah di-override, tidak ada auto-execute aksi berisiko tinggi,
  jawaban JSON `{"ringkasan": ...}`.
- `agent/requirements.txt` — `strands-agents`, `boto3>=1.42.89` (jalur AgentCore Runtime dipisah dari
  `backend/requirements.txt`).

### (b) Event 1 penuh bisa dijalankan dari aplikasi
- `POST /demo/event1` (`backend/app/api/demo.py`): body `{commodity, target_location, ttl_minutes}`.
  Guard `require_roles("sppg_head","sppg_nutritionist")` + `assert_in_scope` atas **lokasi tujuan**
  (Ruling 2026-10-14); lokasi tak dikenal → 404; tak ada kandidat eligible → **409** (keadaan domain,
  bukan 500). Orkestrator dijalankan lewat `run_in_threadpool` karena `run_event1` sinkron dan membuka
  loop sendiri. **Tidak** meng-approve/mengeksekusi apa pun.
- `frontend/lib/api.ts` → `runEvent1(commodity, targetLocation, token, ttlMinutes=30)`.
- `frontend/components/OpsConsole.tsx` → tombol **"Jalankan Event 1 penuh"** (peran penulis saja) +
  blok hasil yang menampilkan decision id, verdict verifier, forecast, status & provider supervisor,
  rantai langkah, dan **narasi supervisor**.
- `frontend/app/page.tsx` → prop baru `onDecisionCreated` yang menyegarkan feed **tanpa memindah tab**;
  kalau memakai `onSubmitted` (perilaku lama untuk "Ajukan"), halaman langsung lompat ke tab
  Recommendations dan blok hasil + narasinya hilang sebelum terbaca (terbukti di layar saat uji pertama).
- `frontend/app/globals.css` → `.ops-event1`, `.ops-event1-result` (token yang sudah ada, tanpa warna baru).

### (b2) `next.config.js` — `experimental.proxyTimeout: 180000`
Proxy dev bawaan memutus di 30 detik; pipeline Event 1 terukur **26,2–27,9 detik** di stack lokal, jadi
klien menerima `socket hang up` **walaupun keputusan sudah ditulis** di backend (pernah terjadi: keputusan
`5ea17278` lahir, klien melihat 500 "Internal Server Error" dari Next).

## 3. Bukti jalur nyata

Catatan penomoran: berkas tes menyebut dirinya kontrak **S0-07** ("Unit test Supervisor Agent (S0-07)"),
sedangkan tabel `TODO.md` menaruh Strands hello-world di **S0-06** dan S0-07 = berkas `.env`. Selisih ini
ada di dokumen, bukan di kode; baris S0-06 di TODO.md sudah diperbarui ke `Done`.

### 3.1 Tes kontrak lulus (host, bukan kontainer)
```
venv scratch + strands-agents 1.61.1 + Python 3.12.3:
python -m pytest -q tests/test_supervisor_agent.py   →  4 passed  (EXIT=0)
ruff check agent/  →  All checks passed
ruff format --check agent/  →  4 files already formatted
```

### 3.2 Agent Strands LIVE ke Bedrock (akun 624606539664)
```
prompt termuat: 1870 char | "safety-critical": True | "deterministik": True
tanpa model id -> RuntimeError berisi "missing_config"   (jujur, tanpa panggilan jaringan)
hello-world LIVE model us.anthropic.claude-haiku-4-5-20251001-v1:0 -> OK 3,4 dtk
balasan: {"ringkasan": "Supervisor MealChain Guardian siap bertugas. … semua angka
          safety-critical dipanggil dari tool deterministik … menunggu approval manusia. …"}
```
Catatan jujur: echo literal `MEALCHAIN_STRANDS_OK` hanya berlaku di bawah MOCK (kontrak S0-06); saat live
agent menjawab mengikuti system prompt. Sudah ditulis di docstring modul.

### 3.3 Endpoint — guard dan jalur sukses (dari DALAM kontainer)
```
login sppg_head / bgn_monitor                    -> 200
kepala SPPG Jakarta -> Cianjur                   -> 403 "lokasi tujuan di cakupan lokasi di luar SPPG Anda"
bgn_monitor (read-only)                          -> 403 "role tidak diizinkan"
lokasi tidak dikenal                             -> 404
tanpa token                                      -> 401
ttl_minutes = 0                                  -> 422
POST http://frontend:3000/demo/event1 (rewrite)  -> 201 dalam 26,2 dtk
  status keputusan: proposed | verifier: FLAGGED | forecast: 7257,77 kg (sap_rpt_1_6)
  supervisor: narrated | provider=primary:sap_ai_core | fallback_used=False
  langkah trace: DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → SUPERVISE
```

### 3.4 Bukti layar (:3010, akun demo SPPG Head, tab Demo Control)
Klik "Jalankan Event 1 penuh" → halaman **tetap di Demo Control**, muncul pesan
`Event 1 penuh selesai — keputusan 90bcb648… masuk feed (menunggu persetujuan).` dan blok hasil:
```
Event 1 penuh — telur → Jakarta   PROPOSED
Keputusan 90bcb648-12b7-418a-aeb7-1b2df503d0a2 | Verifier FLAGGED | Forecast 7257.77 kg
Supervisor narrated (primary:sap_ai_core)
Langkah DETECT → VERIFY → TRACE → PREDICT → OPTIMIZE → DECIDE → SUPERVISE
# Ringkasan Keputusan Distribusi — Untuk Tinjauan Manusia … STATUS: DITANDAI (FLAGGED) …
```

### 3.5 Jejak di DB
Keputusan hasil tombol punya **7 jejak, satu di antaranya SUPERVISE** (`output_summary.status =
"narrated"`, `provider = primary:sap_ai_core`).

### 3.6 Bersih-bersih DB demo
5 keputusan yang saya buat untuk pengujian dihapus berdasarkan id (`DELETE 5`, 0 baris `approvals`
menempel). Sisa baris terbaru di tabel adalah residu run pytest 15:13 UTC (bukan dari fitur ini).

### 3.7 Cek hidup lapisan AI — 2026-10-16 15:32-15:34 UTC, dijalankan DI DALAM kontainer

```
OK    SAP AI Core LLM                    7,2 dtk  "OK"
OK    SAP AI Core RPT (forecast)         4,2 dtk  {"forecast_qty_kg": 2143.21, "confidence": 0.967}
OK    Bedrock us.anthropic.claude-haiku-4-5-20251001-v1:0   1,7 dtk
GAGAL Bedrock us.anthropic.claude-sonnet-4-20250514-v1:0 (nilai SUPERVISOR_MODEL_FALLBACK_1)
      ResourceNotFoundException ... "Access denied. This Model is marked by provider as Legacy"
GAGAL Inferhub POST ke INFERHUB_URL apa adanya            HTTP 404
OK    Inferhub POST ke INFERHUB_URL + "/chat/completions"  HTTP 200 dalam 5,0 dtk
```

Artinya: **2 provider hidup penuh (SAP AI Core LLM + RPT, Bedrock haiku-4-5), Inferhub hidup tapi kode
memanggil URL yang salah** (`INFERHUB_URL` berakhir di `/v1` dan `inferhub_caller.py` mem-POST nilai itu
apa adanya → 404; 25 slot inferhub di rantai agent karenanya mati), dan **AgentCore tetap kosong** (ARN
0 char). Rantai per agent terbaca apa adanya: supervisor 10 slot, verifier & forecast masing-masing
11 slot — mayoritas slotnya Inferhub, jadi "banyak slot" bukan berarti "banyak provider hidup".

### 3.8 Satu kegagalan tes yang TIDAK berasal dari kode ini (penting untuk sesi berikutnya)
`pytest -q tests/test_demo_event1_api.py` pernah sekali merah pada
`test_sukses_meneruskan_hasil_orkestrator_dan_parameter` lalu **hijau 7/7 dua kali berturut-turut**
(`EXIT=0`) tanpa perubahan kode apa pun. Penyebab yang paling masuk akal — dan struktural, bukan
kebetulan: fixture autouse `_sapu_sisa_test()` di `backend/tests/conftest.py` menghapus SEMUA user
`%@test.local` pada **awal dan akhir setiap sesi pytest**, di **DB yang sama** dengan aplikasi. Saat dua
sesi pytest berjalan bersamaan (terbukti: 16 user `@test.local` lahir 15:27-15:28 UTC, di luar sesi ini),
sapuan milik sesi yang baru mulai menghapus user yang baru dibuat sesi lain → tes yang bergantung login
gagal sesaat. **Kesimpulan untuk sesi berikutnya: jangan jalankan suite backend bersamaan dengan sesi
lain di DB demo yang sama, dan jangan membaca satu kegagalan acak sebagai regresi kode** — ulangi dulu
tanpa kompetisi. (Klaim "paling masuk akal" ini belum diuji dengan reproduksi terkendali.)

## 4. Gerbang

| Gerbang | Hasil | Catatan |
|---|---|---|
| `backend: pytest -q` (kontainer) | **863 passed, 3 skipped** (EXIT=0) | 15:09–15:15 UTC; termasuk 7 tes baru `tests/test_demo_event1_api.py` |
| `backend: ruff check .` | bersih | EXIT=0 |
| `agent: ruff check/format` | bersih | host |
| `frontend: vitest run` | **710 passed, 1 failed** dari 711 (67 berkas) | yang gagal `tests/proxy-roots.test.ts` — **bukan dari perubahan ini**, lihat §6 |
| `frontend: tsc --noEmit` | 0 baris | EXIT=0 |
| `frontend: next lint` | "No ESLint warnings or errors" | EXIT=0 |
| `next build` | **TIDAK dijalankan** | `next dev` hidup di kontainer (aturan repo) |

## 5. Tes baru
- `backend/tests/test_demo_event1_api.py` (7 tes): 401 tanpa token, 403 `bgn_monitor`, 403 lokasi lain,
  404 lokasi tak dikenal, 422 ttl, 201 + penerusan parameter + blok supervisor, 409 kandidat kosong.
  `run_event1` diganti fake di tes ini (kontrak endpoint), sehingga tes tidak memanggil provider nyata
  dan tidak menulis keputusan ke DB demo.
- `frontend/tests/ops-console-event1.test.tsx` (7 tes): tombol hanya untuk peran penulis, blok hasil
  memuat narasi supervisor, kontrak body `POST /demo/event1`, ttl default 30, dan dua **wiring**:
  `page.tsx` meneruskan `onDecisionCreated`, serta handler Event 1 **tidak** memanggil `onSubmitted`
  (jebakan tab berpindah yang benar-benar terjadi saat pengerjaan).

## 6. Batas jujur

1. **AgentCore Runtime tetap tidak bisa dipakai**: `AGENTCORE_RUNTIME_ARN` dan `AGENTCORE_GATEWAY_URL`
   masih 0 char. Jadi agent Strands sudah ADA dan terbukti jalan ke Bedrock, tetapi **belum di-deploy**
   ke AgentCore Runtime dan belum memanggil tool lewat Gateway. Klaim yang sah sekarang: "agent Strands
   terimplementasi + hello-world live ke Bedrock", bukan "jalan di AgentCore".
2. **`run_event1` tidak memakai agent Strands** — orkestrasi masih di `backend/app/services/
   event1_orchestrator.py` + `supervisor_client.py` (klien REST). Menyambungkan keduanya adalah pekerjaan
   berikutnya, dan menunggu ARN.
3. **Tes host-only lain masih merah (SEBELUM pekerjaan ini, tidak saya sentuh):**
   `tests/test_verify_agentcore_access.py` dan `tests/test_verify_bedrock_access.py` → `ModuleNotFoundError`
   (modul `infra/aws/verify_*_access.py` tidak ada di disk maupun git); `tests/test_compose_contract.py`
   (2 gagal: mengharap literal `15432:5432` & `8001:8001`, sedangkan compose memakai
   `${POSTGRES_PORT:-15432}:5432`) dan `tests/test_environment_contract.py` (2 gagal: `.env.example`
   tanpa `AWS_PROFILE`; pemindai rahasia menandai baris placeholder `aws_access_key_id=`). Keempatnya
   lolos dari pandangan karena suite kontainer men-`collect_ignore` berkas-berkas itu.
4. **Satu gerbang frontend merah karena pekerjaan sesi lain yang sedang berjalan**: `lib/api.ts` memakai
   root `/safety/evaluate` dan `/freshness/evaluate` (dipakai `page.tsx` baris 328-329) yang **belum
   didaftarkan di `API_ROOTS`**; `tests/proxy-roots.test.ts` memaku itu, dan lewat origin aplikasi kedua
   jalur itu menjawab **404 HTML dari Next** (backend langsung: 401 tanpa token). Berkas tidak saya
   sentuh karena working tree sedang disunting bersamaan.
5. **Working tree sedang disunting sesi/editor lain** (bukti: mtime `frontend/components/SupplyMap.tsx`
   22:26, `frontend/app/globals.css` 22:27, `backend/app/services/supplier_eligibility.py`; 16 user
   `@test.local` lahir 15:27-15:28 UTC, yaitu run pytest lain setelah gerbang saya). Karena itu angka
   gerbang di §4 adalah **potret satu waktu**, bukan janji tentang tree saat ini.
6. **`SUPERVISE` hanya ditulis bila statusnya `narrated`.** Kalau seluruh provider supervisor mati,
   langkah itu tidak muncul di jejak (keputusan tetap lahir) — perilaku lama yang sengaja dipertahankan;
   jangan dibaca sebagai "narasi selalu ada".
