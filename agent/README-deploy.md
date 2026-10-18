# Deploy Supervisor Agent ke AWS Bedrock AgentCore Runtime

Status 2026-10-16: **artefak siap, deploy tertahan izin IAM.** Rinciannya di bawah.

## Apa yang sudah ada di folder ini

| Berkas | Fungsi |
|---|---|
| `supervisor_agent.py` | Agent Strands (system prompt + BedrockModel + `run_hello_world`) |
| `prompts/supervisor_system_prompt.md` | Prompt pengawas (aturan tool deterministik, tanpa auto-execute) |
| `runtime_server.py` | Server HTTP AgentCore: `GET /ping` + `POST /invocations` `{"prompt": …}` → `{"response": …}` |
| `Dockerfile` + `requirements-runtime.txt` | Image runtime (python 3.12-slim, user non-root, port 8080) |
| `deploy_agentcore.py` | Deploy otomatis: preflight izin → ECR → build+push → CreateAgentRuntime → tunggu READY → isi `.env` |

## Kontrak yang harus cocok (jangan diubah sepihak)

`backend/app/ai_providers/agentcore_caller.py` memanggil runtime lewat **data plane**
`bedrock-agentcore.invoke_agent_runtime` dengan `payload=json.dumps({"prompt": "<teks>"})`, lalu membaca
teks dari JSON `response`/`output`/`completion`/`text` (atau teks polos). Karena itu `runtime_server.py`
mengembalikan `{"response": "<narasi>"}`. Port **8080** dan path **/invocations** + **/ping** adalah
kontrak AgentCore Runtime, bukan pilihan kita.

Setelah `AGENTCORE_RUNTIME_ARN` terisi, `backend/app/ai_providers/model_registry.py` otomatis
menaruh AgentCore sebagai **slot primary** setiap rantai agent (slot env bergeser satu) — jadi
orkestrator TIDAK perlu diubah lagi; cukup ARN-nya.

## Mode review 7 worker agent (orkestrasi P4 ada; flag tetap default mati)

P0–P4 menambahkan kontrak, registry, tujuh worker baca, validator, dan orkestrasi
review. **Flag tetap default `false`**, jadi perilaku aplikasi sekarang masih satu
supervisor Strands + empat tool baca. Panel trace/UI 7 agen menyusul di P5.

| Env | Default | Arti |
|---|---|---|
| `MULTI_AGENT_REVIEW` | `false` | `true` menyalakan review 7 worker setelah keputusan dibuat. |
| `AGENT_REVIEW_MODE` | `advisory` | Agen hanya meninjau; tidak menghitung ulang SDC/safety dan tidak mengeksekusi. |
| `AGENT_REVIEW_TIMEOUT_SECONDS` | `75` | Batas total review; lewat batas → status `timeout`, bukan angka karangan. Backend membatasi panggilan runtime ke 45 detik agar request Event 1 tidak menggantung. |

Jangan menyalakan flag ini sebelum panel trace/UI P5 selesai. Saat runtime cloud dipakai,
`MEALCHAIN_API_URL` **wajib** bisa dijangkau dari AgentCore (bukan `http://backend:8000`,
yang hanya ada di jaringan Compose). Kalau backend masih lokal, jalankan runtime secara
lokal dan sebut “runtime lokal” di UI — jangan mengklaim AgentCore live.

## Kontrak P1 (sudah ada, belum aktif)

- `contracts.py` — `AgentFinding`, `AgentRun`, `Citation`, dan validator angka wajib sitasi.
- `hierarchy.json` — tujuh role, stage, endpoint allowlist, dan lane paralel.
- `registry.py` — memuat dan memvalidasi konfigurasi di atas.
- `workers/` — tujuh worker baca nyata: Supply, Demand, Safety, Freshness,
  Price, Logistics, Evidence. Belum ada panggilan model.

Tes kontrak (host-only, butuh repo root di `PYTHONPATH`):

```bash
docker compose run --rm -e PYTHONPATH=/repo -v "$PWD:/repo" -w /repo backend \
  pytest -q backend/tests/test_agent_contracts.py
```

## Worker baca P2–P3 (7/7 — Supply, Demand, Safety, Freshness, Price, Logistics, Evidence)

Tujuh worker membaca API lewat `agent/api_client.py`. Hanya GET, ditambah dua
endpoint komputasi murni yang di-allowlist (`POST /price/deviation`,
`POST /logistics/estimate`); tidak ada endpoint mutasi.

- Supply: `GET /balance/{location}/{commodity}`; nilai yang tidak terukur
  dikosongkan (`null`), bukan diubah menjadi 0.
- Demand: `GET /demand/...` dan `GET /demand/forecast/...?horizon_days=7`.
- Safety: `GET /batches` dan `GET /supplier-exclusions`; tidak memanggil
  `POST /safety/evaluate` yang menulis DB.
- Freshness: `GET /batches`; tidak memanggil `POST /freshness/evaluate` yang menulis DB.
- Price: `GET /price/quotes/...`, `GET /price/...`, `GET /decisions/{id}/approval-summary`,
  dan `POST /price/deviation` (komputasi murni).
- Logistics: `GET /supplier-routes`; fallback `POST /logistics/estimate` hanya bila
  sumber/kuantitas tersedia dan tidak ada rute aktif.
- Evidence: `GET /decisions/{id}/dossier|compliance|chain|approval-summary` dan
  `GET /ledger/verify`; tidak memanggil `/evidence/fuse`.

`agent/validation.py` mendeteksi worker hilang/ganda, kontradiksi fakta, dan
menentukan `completed|partial|failed`. Sepuluh golden case ada di
`backend/tests/test_agent_golden_cases.py`.

## Orkestrasi P4 — tujuh worker + trace delapan baris

`agent/orchestrator.py` menjalankan satu putaran review advisory:

- Lane 1 Supply+Demand, lane 2 Safety+Freshness, lane 3 Price+Logistics (paralel);
  Evidence Fusi setelah lane selesai.
- Setiap worker mendapat `run_id` + decision context dari
  `GET /decisions/{id}/approval-summary`.
- Hasil tujuh finding divalidasi `agent/validation.py`; kegagalan satu worker
  menjadi `partial`, bukan angka palsu.
- `agent/telemetry.py` menghasilkan **7 baris worker + 1 baris SUPERVISE** (8 baris)
  yang siap dipersist ke `agent_traces` pada P5.
- `agent/runtime_server.py` menerima task
  `{"task":"review_decision","decision_id":"…"}` dan mengembalikan JSON `AgentRun`.
- Backend memanggilnya lewat `backend/app/services/agent_review_client.py`; tanpa
  `AGENTCORE_RUNTIME_ARN` hasilnya `unavailable` (Event 1 tetap 201), bukan 7 temuan palsu.
- `Dockerfile` menyalin seluruh paket `agent/` dan menjalankan
  `python -m agent.runtime_server`, supaya import relatif orchestrator/worker valid.

Tes P4:

```bash
docker compose run --rm -e PYTHONPATH=/repo -v "$PWD:/repo" -w /repo backend \
  pytest -q backend/tests/test_agent_orchestrator.py \
  backend/tests/test_agent_runtime_task.py backend/tests/test_agent_review_client.py
```

Live probe read-only (butuh stack Docker dan database berisi keputusan):

```bash
docker compose run --rm -e PYTHONPATH=/repo:/repo/backend \
  -v "$PWD:/repo" -v "path/ke/_qa:/work" -w /repo backend \
  python /work/probe_p4_review.py
```

Tes mock transport:

```bash
docker compose run --rm -e PYTHONPATH=/repo -v "$PWD:/repo" -w /repo backend \
  pytest -q backend/tests/test_agent_workers.py backend/tests/test_agent_workers_p3.py \
  backend/tests/test_agent_validation.py backend/tests/test_agent_golden_cases.py
```

## Blocker saat ini (terukur, bukan dugaan)

`python agent/deploy_agentcore.py` → berhenti di preflight dengan:

```
TOLAK ecr:CreateRepository      TOLAK iam:PassRole
TOLAK ecr:InitiateLayerUpload   ok    bedrock-agentcore:CreateAgentRuntime
TOLAK ecr:UploadLayerPart       ok    bedrock-agentcore:UpdateAgentRuntime
TOLAK ecr:CompleteLayerUpload   ok    bedrock-agentcore:GetAgentRuntime
TOLAK ecr:PutImage
```

Artinya: control-plane AgentCore **boleh** (Create/Update/GetAgentRuntime), tetapi kredensial
`arn:aws:iam::624606539664:user/megu` **tidak boleh** menyiapkan dua hal yang wajib:
(1) peran eksekusi runtime (`iam:CreateRole`/`AttachRolePolicy`/`PassRole`) dan
(2) tempat image (`ecr:CreateRepository`/`PutImage`) atau kode di S3 (`s3:CreateBucket`/`PutObject`).
`CreateAgentRuntime` mensyaratkan `roleArn`, jadi ketiadaan peran = deploy mustahil walau izin runtime ada.

## Yang perlu dilakukan pemilik akun (sekali, ±5 menit)

Jalankan di **CloudShell** (atau konsol IAM) akun **624606539664**. Ganti `<AKUN>` = `624606539664`.

### 1. Peran eksekusi runtime

Nama: `BedrockAgentCoreRuntimeRole`

Trust policy:

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Principal":{"Service":"bedrock-agentcore.amazonaws.com"},
  "Action":"sts:AssumeRole"}]}
```

Permission policy (minimum agar agent bisa menjawab):

```json
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"},
  {"Effect":"Allow","Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],"Resource":"*"},
  {"Effect":"Allow","Action":["ecr:GetAuthorizationToken","ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer","ecr:BatchGetImage"],"Resource":"*"}]}
```

### 2. Izinkan user `megu` mendeploy (agar sisa pekerjaan tidak menunggu Anda)

Inline policy pada user `megu`:

```json
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["ecr:CreateRepository","ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload","ecr:PutImage"],"Resource":"*"},
  {"Effect":"Allow","Action":["iam:PassRole"],
    "Resource":"arn:aws:iam::<AKUN>:role/BedrockAgentCoreRuntimeRole"},
  {"Effect":"Allow","Action":["bedrock-agentcore:CreateAgentRuntime",
    "bedrock-agentcore:UpdateAgentRuntime","bedrock-agentcore:GetAgentRuntime",
    "bedrock-agentcore:CreateAgentRuntimeEndpoint","bedrock-agentcore:DeleteAgentRuntime"],
    "Resource":"*"}]}
```

### 3. Beri tahu agen "izin sudah ditambahkan"

Sisanya otomatis:

```bash
python agent/deploy_agentcore.py --role-arn arn:aws:iam::<AKUN>:role/BedrockAgentCoreRuntimeRole --write-env
docker compose up -d backend     # env dibaca saat create/start
```

## Alternatif kalau Anda tidak mau memberi izin deploy ke `megu`

Deploy sendiri dari CloudShell (image harus sudah ada di ECR — pembuatan repo/push juga butuh izin
yang sama, jadi jalur ini tetap menuntut langkah 1 di atas):

```bash
aws bedrock-agentcore-control create-agent-runtime --region us-west-2 \
  --agent-runtime-name mealchain_supervisor_agent \
  --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"<ECR-URI>:v1"}}' \
  --role-arn arn:aws:iam::<AKUN>:role/BedrockAgentCoreRuntimeRole \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --protocol-configuration '{"serverProtocol":"HTTP"}'
```

Lalu tempel `agentRuntimeArn` hasilnya ke `.env` sebagai `AGENTCORE_RUNTIME_ARN=…`.

## Catatan biaya & batas

- Runtime yang menganggur tidak ditagih seperti server 24/7 (tarif per pemakaian CPU/memori saat
  melayani permintaan), tetapi **image di ECR** dan **log CloudWatch** menimbulkan biaya kecil
  penyimpanan — hapus runtime/ECR kalau sudah tidak dipakai untuk demo.
- Runtime AgentCore hanya **salah satu** slot rantai. Slot Inferhub tetap mati selama
  `INFERHUB_URL` belum ditambahi `/chat/completions`, dan `SUPERVISOR_MODEL_FALLBACK_1`
  (Bedrock `claude-sonnet-4`) masih ditolak karena ditandai *Legacy* oleh provider.
