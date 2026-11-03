# Deploy Supervisor Agent ke AgentCore Runtime — 2026-10-19

> **Snapshot 19 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Status: **berhasil**. Runtime `mealchain_supervisor_agent` versi **18**, status
`READY`, dan backend memakainya sebagai **primary** di rantai agent.

## Akar masalah sebelumnya

Dua hal yang dulu membuat deploy terlihat mustahil:

1. **Peran yang disimulasikan salah nama.** `iam:SimulatePrincipalPolicy` untuk
   `iam:PassRole` dijalankan terhadap `arn:...:role/mealchain-agentcore-runtime`
   — nama tebakan. Hasilnya `implicitDeny`, lalu disimpulkan "IAM menolak deploy".
   Peran yang sebenarnya ada adalah `BedrockAgentCoreRuntimeRole`.
2. **`GetAgentRuntime` dipanggil dengan ARN, bukan runtime id.** Memakai
   `agentRuntimeId=<ARN penuh>` menghasilkan `AccessDenied`, yang mudah dibaca
   sebagai "izin baca dicabut". Dengan `agentRuntimeId=mealchain_supervisor_agent-1tWqipEGjw`
   panggilan berhasil.

Keduanya kesalahan pemanggilan, bukan kebijakan AWS. Setelah diperbaiki,
preflight `deploy_agentcore.py --preflight-saja` melaporkan **semua izin ok**,
termasuk `iam:PassRole` ke `BedrockAgentCoreRuntimeRole`.

## Langkah yang dijalankan

```bash
uv run --with boto3 python agent/deploy_agentcore.py \
  --role-arn arn:aws:iam::624606539664:role/BedrockAgentCoreRuntimeRole \
  --write-env
```

Hasil per tahap:

| Tahap | Hasil |
|---|---|
| 1/5 preflight izin | 22 aksi `ok` (ECR, control plane, endpoint, invoke, PassRole, SLR) |
| 2/5 periksa peran | `BedrockAgentCoreRuntimeRole` ada, inline policy `MealChainAgentCoreRuntimePolicy` |
| 3/5 ECR build/push | image `mealchain/supervisor-agent:v1` (linux/arm64) ter-push |
| 4/5 create/update | runtime sudah ada → `UpdateAgentRuntime` (env 3 kunci dikirim) |
| 5/5 tunggu READY | `UPDATING` → `READY` dalam 11 detik |

`DEPLOY_EXIT=0`; `.env` diisi `AGENTCORE_RUNTIME_ARN` (94 karakter, cocok dengan
ARN runtime yang ada).

## Bukti live

Identitas: `arn:aws:iam::624606539664:user/megu`, region `us-west-2`.

1. **Runtime**: `version 18`, `status READY`, container
   `624606539664.dkr.ecr.us-west-2.amazonaws.com/mealchain/supervisor-agent:v1`,
   role `BedrockAgentCoreRuntimeRole`, env keys `MEALCHAIN_API_TOKEN`,
   `MEALCHAIN_API_URL`, `SUPERVISOR_AGENT_MODEL`.
2. **Invoke langsung (boto3)**: `invoke_agent_runtime` → 184 byte,
   `{"response": "{\"ringkasan\": \"Halo dari MealChain Guardian Supervisor — siap mengawasi alur distribusi pangan ...\"}"}`.
3. **Jalur aplikasi**: backend di-recreate, `/health` 200. Di dalam kontainer,
   `build_default_callers("supervisor")` menghasilkan
   `primary:agentcore` di depan 10 fallback (sap_ai_core, bedrock, inferhub ×8),
   dan pemanggilan caller primary mengembalikan ringkasan supervisor — artinya
   env, caller, dan runtime tersambung lewat kode aplikasi, bukan hanya boto3.

## Yang belum

- `AGENTCORE_GATEWAY_URL` masih kosong (0 karakter). Runtime supervisor hidup
  tanpa Gateway; tool-tool Gateway belum tersambung ke jalur ini.
- Verifikasi produk (verdict verifier yang tercatat dengan provider `agentcore`)
  belum dijalankan ulang di sesi ini karena akan menulis verdict final ke
  keputusan demo.
