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
menaruh AgentCore sebagai **slot primary** setiap rantai agent (slot env bergeser satu) — jadi orkestrator
TIDAK perlu diubah lagi; cukup ARN-nya.

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
