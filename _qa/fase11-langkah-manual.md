# Fase 11 butir 4 — langkah yang hanya bisa dijalankan admin AWS

Status per 28 Okt 2026 01:0x WIB: **BLOCKED oleh IAM akun**, bukan oleh kode.
Semua yang bisa dikerjakan tanpa menambah izin sudah selesai (skrip provisioning +
preflight + runbook ini). Sisa dua perintah dijalankan sekali oleh pemilik akun,
lalu butir 4 ditutup dengan satu perintah dari saya.

## Bukti pemblokir (bukan dugaan)

```
aws sts get-caller-identity  ->  arn:aws:iam::624606539664:user/megu
iam:SimulatePrincipalPolicy  ->  implicitDeny untuk:
    bedrock-agentcore:CreateGatewayTarget
    bedrock-agentcore:InvokeGateway
    bedrock-agentcore:CreateEvent        (butir 5: tulis Memory)
    bedrock-agentcore:DeleteEvent
    iam:CreateRole / iam:PutRolePolicy / iam:PassRole
```

Yang sudah `allowed`: `ListGateways`, `GetGateway`, `CreateGateway`,
`ListGatewayTargets`, `GetMemory`, `ListEvents`, `iam:GetRole`.

Artinya: gateway boleh dibuat, tetapi **target tidak boleh didaftarkan** dan
**tool tidak boleh dipanggil** — jadi `target_ready` dan `tool_invoked` tidak
mungkin dibuktikan dari mesin ini. Menandainya DONE hanya dari konfigurasi akan
melanggar aturan bukti (lihat `scripts/probe_agentcore_gateway.py`).

`iam:CreateRole` ditolak juga, padahal `CreateGateway` mewajibkan `roleArn`.
Karena itu langkah 1 di bawah membuat service role gateway.

## Langkah 1 — admin membuat service role gateway

Jalankan di CloudShell (akun 624606539664, region us-west-2):

```bash
ACC=624606539664
aws iam create-role \
  --role-name MealChainAgentCoreGatewayRole \
  --assume-role-policy-document file://infra/aws/gateway-trust-policy.json \
  --description "Service role AgentCore Gateway MealChain Guardian"

sed "s/\${AWS_ACCOUNT_ID}/$ACC/" infra/aws/gateway-role-policy.json > /tmp/gw-role.json
aws iam put-role-policy \
  --role-name MealChainAgentCoreGatewayRole \
  --policy-name MealChainGatewayLogs \
  --policy-document file:///tmp/gw-role.json

aws iam get-role --role-name MealChainAgentCoreGatewayRole --query Role.Arn --output text
```

Catat ARN hasil perintah terakhir, bentuknya:
`arn:aws:iam::624606539664:role/MealChainAgentCoreGatewayRole`.

## Langkah 2 — admin melampirkan izin ke user deployment (`megu`)

```bash
ACC=624606539664
MEM=$(grep -E '^AGENTCORE_MEMORY_ID=' .env | cut -d= -f2)
sed -e "s/\${AWS_ACCOUNT_ID}/$ACC/g" -e "s/\${MEMORY_ID}/$MEM/g" \
  infra/aws/iam-mealchain-fase11.json > /tmp/mealchain-fase11.json

aws iam put-user-policy \
  --user-name megu \
  --policy-name MealChainFase11AgentCore \
  --policy-document file:///tmp/mealchain-fase11.json
```

Isi policy (dua statement): Memory data plane (`CreateEvent`, `GetEvent`,
`ListEvents`, `DeleteEvent` pada ARN memory) dan Gateway (`CreateGatewayTarget`,
`GetGatewayTarget`, `ListGatewayTargets`, `UpdateGatewayTarget`,
`DeleteGatewayTarget`, `InvokeGateway` pada `gateway/*`). Tidak ada `*` untuk
Resource.

## Langkah 3 — verifikasi izin (harus kosong)

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::624606539664:user/megu \
  --action-names bedrock-agentcore:CreateGatewayTarget bedrock-agentcore:InvokeGateway \
                 bedrock-agentcore:CreateEvent bedrock-agentcore:DeleteEvent \
  --resource-arns '*' \
  --query 'EvaluationResults[?EvalDecision!=`allowed`].[EvalActionName,EvalDecision]' \
  --output text
```

Output kosong = siap. Masih ada baris = policy belum menempel.

## Langkah 4 — saya menutup butir 4 (satu perintah)

Setelah langkah 1–3 selesai, beri tahu saya ARN role (atau isi sendiri di `.env`):

```bash
echo 'AGENTCORE_GATEWAY_ROLE_ARN=arn:aws:iam::624606539664:role/MealChainAgentCoreGatewayRole' >> .env
```

Lalu saya jalankan:

```bash
uv run --with boto3 python scripts/provision_agentcore_gateway.py
uv run --with boto3 python scripts/probe_agentcore_gateway.py | tee _qa/fase11/probe-gateway-$(date +%Y%m%d-%H%M).json
```

Yang dilakukan provisioner (idempoten, aman diulang):

1. preflight simulasi lima aksi — berhenti `BLOCKED` (exit 3) bila masih kurang;
2. `mealchain-gateway` (MCP, authorizer NONE) dipakai bila ada, dibuat bila belum;
3. target `mealchain-tools` berisi 10 tool dari `backend/app/agent_tools/gateway_config.json`
   sebagai OpenAPI inline, ditunggu sampai `READY`;
4. satu tool dipanggil lewat MCP (`initialize` → `tools/list` → `tools/call`) dan
   hasilnya dicetak — inilah bukti `tool_invoked`;
5. `AGENTCORE_GATEWAY_URL` ditulis ke `.env` (backup `.env.bak-gateway`) sehingga
   aplikasi memakai gateway, bukan hanya konfigurasi.

Untuk butir 5 (Memory tulis-baca) perintahnya terpisah dan sudah ada:
`RUN_LIVE_AGENTCORE=1 pytest backend/tests/test_agent_memory_live.py`.

## Yang TIDAK boleh dilakukan

- Mencentang butir 4/5 dengan alasan "kode sudah ada" saat izin belum ada.
- Memakai `Resource: "*"` supaya cepat lolos.
- Menempelkan kredensial AWS ke dalam berkas repo atau laporan.
