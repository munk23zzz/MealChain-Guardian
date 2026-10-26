# AgentCore Runtime — artefak siap, deploy tertahan IZIN IAM

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal: 2026-10-16 · Assignee: Hermes · Repo: `E:\hackathon\HackathonAWS\mealchain-guardian`

Catatan nama berkas: `docs/verification/fase-12.md` sudah dipakai pekerjaan peta (sesi lain), jadi
dokumen ini memakai nama deskriptif agar dua sesi tidak saling menimpa.

Permintaan pemilik (kutip apa adanya):

> "saya mau jalan semuanya baik orkestrator maupun agent core. tolong kerjakan"

## 1. Kondisi AWS yang diukur (bukan disimpulkan)

`sts get_caller_identity` → **akun 624606539664**, identitas `arn:aws:iam::624606539664:user/megu`,
region **us-west-2**.

| Resource AgentCore | Jumlah | Catatan |
|---|---|---|
| Agent Runtime | **0** | belum ada satu pun |
| Gateway | **0** | belum ada |
| Memory | **1** | `mealchain_memory_01-soAIdH8viw` (ACTIVE, dibuat 2026-10-11) |

Region lain diperiksa: us-east-1, ap-southeast-1, ap-southeast-2 → semuanya 0 runtime.
Kesimpulan: bukan "runtime ada tapi salah ARN" — **memang belum pernah dibuat**.

## 2. Kenapa deploy mustahil dengan kredensial sekarang (bukti per-izin)

Preflight `agent/deploy_agentcore.py` memakai `iam:SimulatePrincipalPolicy` (tanpa efek samping):

```
TOLAK ecr:CreateRepository      ok    bedrock-agentcore:CreateAgentRuntime
TOLAK ecr:InitiateLayerUpload   ok    bedrock-agentcore:UpdateAgentRuntime
TOLAK ecr:UploadLayerPart       ok    bedrock-agentcore:GetAgentRuntime
TOLAK ecr:CompleteLayerUpload   ok    bedrock:InvokeModel
TOLAK ecr:PutImage              TOLAK iam:CreateRole / AttachRolePolicy / PassRole
```

Pelajaran metodologis penting: percobaan pertama memakai payload kosong dan menghasilkan
`ParamValidationError` — itu **validasi di sisi klien (botocore)**, jadi tidak membuktikan apa pun
tentang izin. Yang sah adalah `simulate_principal_policy`; percobaan berikutnya dengan payload "valid
tapi mustahil" juga berbahaya (bisa benar-benar membuat resource). Pakai simulate.

Efeknya ke bentuk API: `CreateAgentRuntimeRequest` **mensyaratkan** `agentRuntimeName`,
`agentRuntimeArtifact`, `roleArn`, `networkConfiguration`. Artifact hanya dua bentuk —
`containerConfiguration.containerUri` (ECR) atau `codeConfiguration.code.s3` (S3, bucket+prefix).
Keduanya butuh izin tulis yang ditolak, dan `roleArn` butuh `iam:PassRole` yang juga ditolak.
Jadi: **tanpa peran eksekusi, AgentCore Runtime tidak bisa dibuat walau izin runtime-nya ada.**

Peran yang ada di akun sekarang hanya 4 service-linked role (Resource Explorer, Service Quotas, Support,
Trusted Advisor) — tidak ada yang bisa dipakai runtime.

## 3. Yang SUDAH selesai dan terbukti (tidak menunggu izin)

### 3.1 Orkestrator sudah tersambung ke AgentCore — tanpa ubah kode orkestrator
`model_registry.get_agent_chain` menaruh `AGENTCORE_RUNTIME_ARN` sebagai **primary** begitu env terisi.
Diuji dengan ARN palsu (hanya di proses probe, `.env` tidak disentuh):

```
tanpa ARN: primary:sap_ai_core → fallback_1:bedrock → fallback_2:inferhub
dengan ARN: primary:agentcore  → fallback_1:sap_ai_core → fallback_2:bedrock
run_supervisor(ARN palsu) → status=narrated, provider=fallback_1:sap_ai_core, fallback_used=True
  attempt primary  : failed, category=http_404,
                     "ResourceNotFoundException ... when calling the InvokeAgentRuntime operation"
  attempt fallback1: succeeded dalam 8,4 dtk
```

Tiga hal terbukti sekaligus: (1) slot AgentCore benar-benar memanggil **data plane AWS**
(galatnya dari AWS, bukan dari kode kita yang menolak lebih dulu), (2) kegagalan slot itu tidak
mematikan narasi, (3) tidak ada regresi perilaku sekarang.

### 3.2 Artefak runtime dibuat + diuji kontraknya secara lokal
Berkas baru: `agent/runtime_server.py`, `agent/Dockerfile`, `agent/requirements-runtime.txt`,
`agent/deploy_agentcore.py`, `agent/README-deploy.md`.

- `docker build --platform linux/amd64 -t mealchain-supervisor-agent:local -f agent/Dockerfile agent/`
  → sukses (71 dtk), image non-root, port 8080.
- Container dijalankan dengan kredensial asli; log start: `[runtime] system prompt: 1870 char`,
  `[runtime] model: us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- `GET /ping` → `200 {"status":"Healthy", ...}` (kontrak health AgentCore).
- `POST /invocations` body `{"prompt": "<prompt supervisor JSON>"}` → **200 dalam 3,4 dtk**, balasan
  `{"response": "…{\"ringkasan\": \"Event distribusi telur: deteksi surplus 300 kg dari Cianjur …\"}…"}`
  → **panggilan Bedrock nyata lewat agent Strands**.
- Balasan itu diumpankan ke kode orkestrator yang sesungguhnya
  (`agentcore_caller._extract_text` → `supervisor_client._extract_summary`): **LOLOS**, menghasilkan
  ringkasan narasi yang sah. Artinya kontrak runtime ↔ caller cocok, bukan cuma "mirip".

Kontrak yang dikunci: port **8080**, `GET /ping`, `POST /invocations`, payload masuk
`{"prompt": …}`, keluar `{"response": …}` — sama dengan yang dikirim/dibaca
`backend/app/ai_providers/agentcore_caller.py`.

### 3.3 Deploy otomatis siap satu perintah
`python agent/deploy_agentcore.py --role-arn <ARN peran> --write-env` melakukan: preflight izin →
buat ECR repo → `docker login` (password lewat stdin, tidak pernah di argv) → build+push → CreateAgentRuntime
(idempoten: konflik nama → `update_agent_runtime`) → menunggu `READY` → menulis
`AGENTCORE_RUNTIME_ARN` ke `.env`. Kalau izin kurang, ia berhenti di langkah 1 dengan daftar izin yang
hilang + langkah perbaikannya, **tanpa mengubah apa pun di AWS** (`EXIT=2`).

### 3.4 Tes struktur tidak rusak
`pytest -q backend/tests/test_structure.py backend/tests/test_supervisor_agent.py` → **5 passed**
(berkas baru di `agent/` tidak melanggar kontrak struktur repo).

## 4. Yang dibutuhkan dari pemilik akun (blocker tunggal)

1. Peran eksekusi `BedrockAgentCoreRuntimeRole` (trust = `bedrock-agentcore.amazonaws.com`;
   izin logs + `bedrock:InvokeModel` + ECR read).
2. Inline policy pada user `megu`: ECR push/create + `iam:PassRole` **hanya** untuk peran di atas +
   `bedrock-agentcore:Create/Update/GetAgentRuntime`.
3. Beri tahu "izin sudah ditambahkan".

Langkah lengkap (JSON siap tempel) ada di `agent/README-deploy.md`; skrip deploy juga mencetaknya
otomatis. Setelah itu: deploy → `docker compose up -d backend` → klik "Jalankan Event 1 penuh" →
jejak SUPERVISE harus ber-`provider` `primary:agentcore`.

## 5. Batas jujur

- **Belum ada runtime di AWS.** Yang terbukti: artefaknya jalan (diuji lokal) dan orkestrator siap
  memakainya. Klaim yang sah "AgentCore-ready, terverifikasi kontraknya lokal", BUKAN "sudah jalan di AgentCore".
- Uji lokal memakai `linux/amd64` (mengikuti mesin Docker di laptop); deploy memakai default
  `--platform linux/arm64` sesuai anjuran AgentCore Runtime — perbedaan platform ini **belum diuji
  ke AWS**, hanya build-nya yang akan dijalankan skrip deploy.
- Rantai agent juga masih punya slot mati yang tidak ada hubungannya dengan AgentCore:
  `INFERHUB_URL` kurang `/chat/completions` (25 slot 404) dan `SUPERVISOR_MODEL_FALLBACK_1`
  = Bedrock `claude-sonnet-4` yang ditandai *Legacy*.
- Biaya: runtime idle tidak ditagih seperti server 24/7, tetapi image di ECR dan log CloudWatch
  menimbulkan biaya kecil; hapus runtime/repo setelah demo selesai.
