# Migrasi AWS ke akun 624606539664 — 2026-10-11

> **Snapshot 11 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

## Masalah yang dipecahkan

Kredensial di `.env` milik akun **679583588036** (user IAM `mealchain`), tetapi **tidak ada
akses konsol ke akun itu** dan user tersebut tidak punya izin IAM apa pun
(`iam:ListAttachedUserPolicies` → AccessDenied), sehingga blokir Bedrock tidak mungkin
diselesaikan dari dalam akun itu. Konsol yang user kuasai adalah akun **624606539664**.

Keputusan user: **memindahkan dependency AWS aplikasi ke akun 624606539664**
(konsekuensi diterima: resource AgentCore di akun lama — runtime `mealchain-5iQ9raHpis`,
2 gateway, 2 memory — tidak dapat dipakai lagi).

## Yang diubah

| Berkas | Perubahan |
|---|---|
| `secrets/aws-app.env` (**baru**, terabaikan git) | Kunci akses akun baru (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) + `AWS_REGION=us-west-2` |
| `docker-compose.yml` | `env_file: [.env, secrets/aws-app.env]` (berkas belakangan menang); entri `AWS_*` + `AGENTCORE_*` **dihapus** dari blok `environment:` |
| `.env` | Kunci AWS akun lama dikosongkan; `AWS_BEARER_TOKEN_BEDROCK` **dihapus**; `AWS_PROFILE=` **dihapus**; `AGENTCORE_RUNTIME_ARN`/`AGENTCORE_GATEWAY_URL`/`AGENTCORE_MEMORY_ID` dikosongkan; topologi model disesuaikan |
| `.gitignore` | Entri `secrets/` ditambahkan (sebelumnya **tidak ada** — klaim lama "sudah diabaikan" ternyata salah) |

Topologi model setelah migrasi (`MAX_FALLBACK_SLOTS = 12`, slot diisi sekuensial tanpa gap):

- **supervisor**: `primary` = `sap-ai-core:llm` → `fallback_1` = `us.anthropic.claude-sonnet-4-20250514-v1:0` (Bedrock) → sisanya Inferhub
- **verifier / forecast**: `primary` = `sap-ai-core:llm` / `sap-ai-core:rpt` → Inferhub → `fallback_10` = Bedrock `us.anthropic.claude-haiku-4-5-20251001-v1:0`

## Bukti terukur (bukan klaim)

- STS **dari dalam kontainer**: `Account: 624606539664` (kunci akun baru benar-benar terpakai).
- Rantai model nyata: `supervisor` primary `sap_ai_core` menjawab `'**Ping**'`; `verifier` menjawab `'**Ping!**'`.
- Bedrock akun baru: `list_inference_profiles` ACTIVE memuat `us.anthropic.claude-sonnet-4-20250514-v1:0`,
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `global.*`, dan `us.anthropic.claude-opus-4-6-v1`.
  `get_use_case_for_model_access` → formData terisi (836 char, jadi formulir use-case tidak menghambat).
- Invoke nyata: **`ThrottlingException: Too many tokens per day`** untuk sonnet-4, haiku-4.5,
  sonnet-4-5, opus-4-6, qwen, gpt-oss, deepseek. Service Quotas: kuota
  *cross-region tokens per minute* Anthropic bernilai **0.0** (adjustable) → kapasitas belum
  diprovisikan untuk akun ini. Model `claude-sonnet-5`/`claude-haiku-5-5`/`gpt-6-astra` →
  `AccessDeniedException` (butuh persetujuan AWS Sales).
- Suite backend: **630 passed, 3 skipped**; tes live SAP AI Core: **3 passed**.

## Blocker tersisa (aksi user, satu-satunya)

1. Konsol AWS (akun 624606539664) → **Service Quotas** → Service = *Amazon Bedrock* →
   cari kuota **"…tokens per minute…"** untuk **Anthropic Claude Sonnet 4** (cross-region) →
   **Request increase** (mis. 400.000) → ulangi untuk **Claude Haiku 4.5**.
2. Setelah kuota > 0: uji `aws bedrock-runtime invoke-model` atau lewat aplikasi; bila sudah
   menjawab, tukar satu baris `.env` (`SUPERVISOR_MODEL_PRIMARY=us.anthropic.claude-sonnet-4-20250514-v1:0`)
   agar Bedrock menjadi primary.

## Jebakan yang terbukti mahal (jangan diulang)

1. `AWS_BEARER_TOKEN_BEDROCK` **ada tetapi kosong** → botocore menempuh jalur Bearer dan Bedrock
   membalas `IncompleteSignatureException`. **Hapus** variabelnya; jangan dikosongkan.
2. `AWS_PROFILE=` (kosong) → botocore gagal `ProfileNotFound: The config profile () could not be found`,
   mematikan seluruh akses AWS aplikasi.
3. Di compose, blok **`environment:` menang atas `env_file`** → override kunci AWS lewat env_file
   kedua hanya bekerja setelah entri `AWS_*` dihapus dari `environment:`.
4. Slot **legacy `SUPERVISOR_MODEL_FALLBACK`** diabaikan bila ada slot bernomor
   (`*_MODEL_FALLBACK_1..9`) — nilai Bedrock di slot legacy tidak pernah masuk rantai.
   Slot dikumpulkan sekuensial dan **gap pertama menghentikan koleksi**.
5. Halaman **Model access sudah pensiun**: model serverless aktif otomatis saat invoke pertama,
   kontrolnya lewat IAM/SCP — jadi "AccessDenied" di akun lama adalah soal izin, bukan tombol.
6. `freetier:GetAccountPlanState` tidak diizinkan untuk user `megu`, jadi status free-plan tidak
   dapat dibaca lewat API; kuota Bedrock dibaca lewat `service-quotas` (nama service di SDK:
   `service-quotas`, bukan `servicequotas`).

## AgentCore di akun baru (2026-10-11)

- **Memory DIBUAT**: `mealchain_memory_01-soAIdH8viw`
  (`arn:aws:bedrock-agentcore:us-west-2:624606539664:memory/mealchain_memory_01-soAIdH8viw`),
  status saat dibuat `CREATING` — provisioning berjalan di sisi AWS. ID dicatat di `.env`
  sebagai `AGENTCORE_MEMORY_ID`.
- **Gateway TERBLOKIR IZIN**: `CreateGateway` mewajibkan `roleArn`, dan user `megu` ditolak
  `iam:CreateRole`. Perlu sekali dibuat oleh pemilik akun (root): role
  `mealchain-agentcore-gateway-role` dengan trust policy ke `bedrock-agentcore.amazonaws.com`.
  Setelah ada, Gateway (`AWS_IAM`, protokol MCP) + GatewayTarget berisi 10 tool dari
  `backend/agent_tools/gateway_config.json` dapat dibuat.
- **Fakta jujur yang harus diingat**: `AGENTCORE_GATEWAY_URL` **tidak dibaca kode mana pun**
  (grep `backend/app` dan `frontend/` nihil), dan frontend tidak pernah menyebut "AgentCore" —
  jadi mengisi nilai itu baru bersifat dokumentasi sampai ada kode yang mengonsumsinya.
- **Adapter data-plane Memory belum ada**: `AgentCoreMemoryBackend.write/read` sengaja melempar
  `MemoryUnavailableError` (tanpa fallback diam). Akibatnya `AGENTCORE_MEMORY_ID` yang terisi
  membuat `memory_provider_from_env()` melaporkan `agentcore`, sedangkan jalur runtime aplikasi
  tetap memakai provider `local`. Suite tetap **630 passed / 3 skipped**. Item lanjutan:
  implementasi adapter data-plane (`CreateEvent`/`ListEvents`/`RetrieveMemoryRecords`) + tes.

