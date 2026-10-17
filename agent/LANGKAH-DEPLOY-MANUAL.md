# LANGKAH MANUAL — Mengaktifkan AgentCore Runtime untuk Supervisor Agent

Dokumen ini untuk **pemilik akun AWS** (Anda). Semua yang bisa dikerjakan tanpa Anda sudah selesai:
artefak runtime sudah dibuat dan diuji, orkestrator sudah tersambung, skrip deploy sudah siap.
Yang tersisa hanya **izin**, dan itu hanya bisa dibuka oleh Anda.

Akun: **624606539664** · Region: **us-west-2** · User IAM yang dipakai agen: **megu**

---

## 0. Yang perlu disiapkan

- Bisa login konsol AWS akun 624606539664 (atau punya akses admin ke akun itu).
- Buka **CloudShell** (ikon `>_` di kanan atas konsol) dan pastikan region di CloudShell = **us-west-2**.
- Tidak perlu menjalankan Docker di CloudShell — image dibangun dari laptop oleh agen.

Cek identitas di CloudShell (harus akun 624606539664, dan sebaiknya bukan user `megu`):

```bash
aws sts get-caller-identity
```

---

## 1. Buat peran eksekusi runtime (WAJIB)

Peran ini yang dipakai AgentCore untuk menjalankan agent kita.

```bash
cat > /tmp/mealchain-trust.json <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Principal":{"Service":"bedrock-agentcore.amazonaws.com"},
  "Action":"sts:AssumeRole"}]}
JSON

aws iam create-role \
  --role-name BedrockAgentCoreRuntimeRole \
  --assume-role-policy-document file:///tmp/mealchain-trust.json \
  --description "Eksekusi AgentCore Runtime untuk Supervisor Agent MealChain Guardian"
```

Lalu izin minimum agar agent bisa menjawab (log + panggil Bedrock + tarik image ECR):

```bash
cat > /tmp/mealchain-perm.json <<'JSON'
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow",
   "Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
   "Resource":"*"},
  {"Effect":"Allow",
   "Action":["bedrock:InvokeModel","bedrock:InvokeModelWithResponseStream"],
   "Resource":"*"},
  {"Effect":"Allow",
   "Action":["ecr:GetAuthorizationToken","ecr:BatchCheckLayerAvailability",
             "ecr:GetDownloadUrlForLayer","ecr:BatchGetImage"],
   "Resource":"*"}]}
JSON

aws iam put-role-policy \
  --role-name BedrockAgentCoreRuntimeRole \
  --policy-name MealChainAgentCoreRuntimePolicy \
  --policy-document file:///tmp/mealchain-perm.json
```

**Lewat konsol (kalau tidak mau CLI):** IAM → Roles → *Create role* → Trusted entity: **Custom trust
policy** (tempel blok trust di atas) → Next → *Create policy* dengan JSON blok izin di atas (atau lampirkan
`AmazonBedrockFullAccess` + policy log) → nama peran `BedrockAgentCoreRuntimeRole`.

---

## 2. Izinkan user `megu` mendeploy (WAJIB untuk jalur otomatis)

Tanpa langkah ini, agen tidak bisa membangun/mengunggah image dan tidak boleh menyerahkan peran
(`iam:PassRole`) ke runtime — jadi deploy tetap berhenti walau langkah 1 selesai.

```bash
cat > /tmp/mealchain-deploy.json <<'JSON'
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow",
   "Action":["ecr:CreateRepository","ecr:GetAuthorizationToken",
             "ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload",
             "ecr:UploadLayerPart","ecr:CompleteLayerUpload","ecr:PutImage"],
   "Resource":"*"},
  {"Effect":"Allow",
   "Action":["iam:PassRole"],
   "Resource":"arn:aws:iam::624606539664:role/BedrockAgentCoreRuntimeRole"},
  {"Effect":"Allow",
   "Action":["bedrock-agentcore:CreateAgentRuntime",
             "bedrock-agentcore:UpdateAgentRuntime",
             "bedrock-agentcore:GetAgentRuntime",
             "bedrock-agentcore:CreateAgentRuntimeEndpoint",
             "bedrock-agentcore:DeleteAgentRuntime"],
   "Resource":"*"}]}
JSON

aws iam put-user-policy \
  --user-name megu \
  --policy-name MealChainAgentCoreDeploy \
  --policy-document file:///tmp/mealchain-deploy.json
```

**Lewat konsol:** IAM → Users → `megu` → *Add permissions* → *Create inline policy* → tab **JSON** →
tempel blok di atas → nama `MealChainAgentCoreDeploy`.

Catatan keamanan: izin ini dibatasi — `iam:PassRole` **hanya** untuk peran
`BedrockAgentCoreRuntimeRole`, dan ECR dibatasi ke aksi yang diperlukan untuk satu repo. Tidak ada izin
menghapus atau mengubah resource lain. Kalau demo selesai, cabut lagi:
`aws iam delete-user-policy --user-name megu --policy-name MealChainAgentCoreDeploy`.

---

## 3. Verifikasi cepat bahwa izin sudah terbuka (opsional, di CloudShell)

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::624606539664:user/megu \
  --action-names iam:PassRole ecr:CreateRepository ecr:PutImage \
                  bedrock-agentcore:CreateAgentRuntime \
  --query 'EvaluationResults[].{aksi:EvalActionName,hasil:EvalDecision}' --output table
```

Semua baris harus `allowed`.

---

## 4. Beri tahu agen "izin sudah ditambahkan"

Setelah itu sisanya otomatis (dijalankan agen, ±5–10 menit):

```bash
export MEALCHAIN_API_URL="https://<backend-publik-anda>"
export MEALCHAIN_API_TOKEN="<token-baca>"   # [REDACTED] jangan ditulis ke repo
python agent/deploy_agentcore.py \
  --role-arn arn:aws:iam::624606539664:role/BedrockAgentCoreRuntimeRole --write-env
docker compose up -d backend
```

Dua variabel `MEALCHAIN_API_*` diteruskan skrip ke environment runtime. Tanpa itu
supervisor tetap hidup, tetapi keempat tool balas `missing_config` (jujur), bukan
mengarang angka. Backend harus dapat dijangkau dari runtime (bukan `localhost`).

Skrip itu: membuat repo ECR → build image (linux/arm64) → push → `CreateAgentRuntime` →
menunggu status `READY` → menulis `AGENTCORE_RUNTIME_ARN` ke `.env`. Lalu agen memverifikasi dengan
"Jalankan Event 1 penuh" di konsol UI dan memeriksa jejak SUPERVISE harus ber-`provider`
`primary:agentcore`.

---

## 5. Alternatif: Anda yang mendeploy, tanpa memberi izin ke `megu`

Kalau Anda memilih tidak menjalankan langkah 2, deploy harus Anda lakukan sendiri. Perlu diketahui:
langkah ini tetap butuh langkah 1, DAN butuh image sudah ada di ECR (membangun + push image juga
butuh izin ECR). Dua pilihan:

a. **Anda bangun+push dari laptop ini** memakai kredensial admin Anda sendiri (Docker Desktop sudah
   terpasang di mesin ini):

```bash
aws ecr create-repository --repository-name mealchain/supervisor-agent --region us-west-2
aws ecr get-login-password --region us-west-2 | docker login --username AWS \
  --password-stdin <AKUN>.dkr.ecr.us-west-2.amazonaws.com
docker build --platform linux/arm64 -t mealchain/supervisor-agent:v1 -f agent/Dockerfile agent/
docker tag mealchain/supervisor-agent:v1 <AKUN>.dkr.ecr.us-west-2.amazonaws.com/mealchain/supervisor-agent:v1
docker push <AKUN>.dkr.ecr.us-west-2.amazonaws.com/mealchain/supervisor-agent:v1
```

b. **Buat runtime di CloudShell** (setelah image ada):

```bash
aws bedrock-agentcore-control create-agent-runtime --region us-west-2 \
  --agent-runtime-name mealchain_supervisor_agent \
  --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"<AKUN>.dkr.ecr.us-west-2.amazonaws.com/mealchain/supervisor-agent:v1"}}' \
  --role-arn arn:aws:iam::624606539664:role/BedrockAgentCoreRuntimeRole \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --protocol-configuration '{"serverProtocol":"HTTP"}'
```

Lalu kirimkan `agentRuntimeArn` hasilnya ke agen (bukan kunci AWS Anda — ARN saja tidak rahasia).

---

## 6. Kalau nanti macet (gejala → penyebab)

| Gejala | Penyebab yang paling sering |
|---|---|
| `create-agent-runtime` → `AccessDenied` | langkah 2 belum dikerjakan |
| `ValidationException` soal `roleArn` | peran belum ada, atau nama region peran ≠ region runtime |
| Runtime `CREATE_FAILED` | peran eksekusi belum bisa tarik image ECR (izin `ecr:GetDownloadUrlForLayer`/`BatchGetImage`) atau trust policy bukan `bedrock-agentcore.amazonaws.com` |
| Runtime `READY` tapi `InvokeAgentRuntime` 404 | endpoint runtime belum siap — tunggu 1–2 menit, lalu ulangi |
| Agent menjawab tapi narasi kosong | model Bedrock di runtime tidak bisa dipanggil dari peran eksekusi, atau id-nya sudah mati (mis. ditandai *Legacy*). Set `SUPERVISOR_AGENT_MODEL` ke model yang aksesnya terbukti: `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

Log runtime: CloudWatch → log group `/aws/bedrock-agentcore/runtimes/<runtime-id>`.

---

## 7. Bersih-bersih setelah demo (disarankan)

```bash
aws bedrock-agentcore-control delete-agent-runtime --region us-west-2 --agent-runtime-id <id>
aws ecr delete-repository --repository-name mealchain/supervisor-agent --region us-west-2 --force
aws iam delete-role-policy --role-name BedrockAgentCoreRuntimeRole --policy-name MealChainAgentCoreRuntimePolicy
aws iam delete-role --role-name BedrockAgentCoreRuntimeRole
aws iam delete-user-policy --user-name megu --policy-name MealChainAgentCoreDeploy
```

Runtime yang menganggur tidak ditagih seperti server 24/7, tetapi image di ECR dan log CloudWatch
menimbulkan biaya penyimpanan kecil.

---

## Checklist singkat

- [ ] CloudShell dibuka di region us-west-2, `get-caller-identity` = akun 624606539664
- [ ] Peran `BedrockAgentCoreRuntimeRole` dibuat (trust `bedrock-agentcore.amazonaws.com`)
- [ ] Policy izin peran dipasang (logs + bedrock invoke + ECR read)
- [ ] Inline policy `MealChainAgentCoreDeploy` menempel pada user `megu`
- [ ] `simulate-principal-policy` → semua `allowed`
- [ ] Kabari agen "izin sudah ditambahkan" → deploy + verifikasi dijalankan
