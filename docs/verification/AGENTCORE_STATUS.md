# Status AgentCore — MealChain Guardian

Diperbarui: 27 Okt 2026 · Fase 11 (`MG/phase-11-ledger-agentcore.md`)
Commit terkait: `d98adec` (butir 1), `cd2271f` (butir 2), `0b1d87a` (butir 3), `b2f6b0c` (butir 4–6).

Dokumen ini memisahkan **empat bukti Gateway** dan **dua bukti Memory** yang sering dicampur
menjadi satu kata "DONE". Setiap baris punya status sendiri dan cara ukurnya; status hanya
naik kalau ada operasi nyata yang hasilnya dibaca.

Legenda status: `VERIFIED` = ada operasi nyata yang berhasil dan hasilnya dibaca ·
`UNVERIFIED` = belum bisa dibuktikan (izin/resource belum ada) · `NOT_CONFIGURED` = fitur
memang tidak diaktifkan.

## 1. Gateway — empat bukti terpisah

Sumber: `scripts/probe_agentcore_gateway.py` (hanya operasi baca) dijalankan
`docker run --env-file secrets/aws-app.env --env-file .env …`, region `us-west-2`,
akun `624606539664`, user `megu`.

| # | Bukti | Status | Cara ukur / alasan |
|---|---|---|---|
| 1 | `resource_exists` | **VERIFIED (negatif: 0 gateway)** | `ListGateways` berhasil (izin boleh), hasil `gateways = []`. Jadi kebenarannya: **belum ada Gateway** di region ini. |
| 2 | `target_ready` | **UNVERIFIED** | Tidak ada gateway untuk diperiksa targetnya; `ListGatewayTargets` tidak dipanggil. |
| 3 | `tool_invoked` | **UNVERIFIED** | Belum ada satu tool Gateway yang dipanggil dan hasilnya dibaca aplikasi. Probe sengaja tidak memanggil tool. |
| 4 | `app_uses_gateway` | **NOT_CONFIGURED** | `AGENTCORE_GATEWAY_URL` kosong di `.env`. Registry (`backend/app/agent_tools/registry.py`) masih artifak konfigurasi, bukan klien aktif. |

Kesimpulan jujur: **integrasi Gateway belum aktif**. Tidak ada klaim "Gateway jalan".

Blokir + tindakan owner (satu kali):

1. `bedrock-agentcore:CreateGateway` **sudah** dimiliki (inline `mealchain-app-policy`).
2. `bedrock-agentcore:CreateGatewayTarget` **belum** dimiliki → dilampirkan dari
   `infra/aws/iam-mealchain-fase11.json`.
3. Sesudah izin ada: buat Gateway + target MCP ke backend deterministik, lalu panggil satu tool
   lewat Gateway, isi `AGENTCORE_GATEWAY_URL`, dan ulangi probe. Baru bukti #3 dan #4 boleh naik
   ke `VERIFIED`.

## 2. Memory — resource, izin, dan tulis-baca

| # | Bukti | Status | Cara ukur / alasan |
|---|---|---|---|
| 1 | `resource_exists` | **VERIFIED** | `GetMemory` berhasil pada `AGENTCORE_MEMORY_ID` (`mealchain_memory_01-…`), `resource_status = ACTIVE`, region `us-west-2`. |
| 2 | `read_allowed` (ListEvents) | **VERIFIED** | `ListEvents` pada sesi probe kosong diizinkan (ReadOnlyAccess). |
| 3 | `write_allowed` (CreateEvent) | **UNVERIFIED** | `CreateEvent` **ditolak IAM**: `AccessDeniedException … no identity-based policy allows bedrock-agentcore:CreateEvent`. |
| 4 | `namespace` desain | **VERIFIED (kode + tes unit)** | Namespace = `actorId` + `sessionId`, sesi = `"<demo_session_id>:<decision_id>"`. Diuji `test_agentcore_backend_namespace_isolates_sessions`: sesi A tidak terbaca dari sesi B. |
| 5 | `sanitasi` | **VERIFIED (kode + tes)** | `sanitize_memory_payload` membuang key berbau secret; tes memastikan `password` tidak ada di payload yang dikirim ke AWS. |
| 6 | `tulis-baca nyata di AWS` | **UNVERIFIED** | `tests/test_agent_memory_live.py` (`RUN_LIVE_AGENTCORE=1`, `-m live`) berhenti di `CreateEvent` = AccessDenied. Bukan lulus, bukan pula klaim bekerja. |

Kode konsumen: `catat_learn()` dipanggil `event1_orchestrator` pada langkah **LEARN**,
**default MATI** (`AGENT_MEMORY_WRITE=0`). Nyalakan hanya setelah izin tulis ada.

Tindakan owner (satu kali): lampirkan `infra/aws/iam-mealchain-fase11.json` ke user/role
deployment (butir `AgentCoreMemoryDataPlane`), lalu:

```bash
docker run --rm --network mealchain-guardian_mealchain-network \
  --env-file secrets/aws-app.env --env-file .env -e RUN_LIVE_AGENTCORE=1 \
  -v "E:/hackathon/HackathonAWS/mealchain-guardian/backend:/app" -w /app \
  mealchain-guardian-backend python -m pytest tests/test_agent_memory_live.py -m live -v
```

Tes itu menulis satu event di namespace uji (`uji-fase11-<acak>`), membaca ulang, memastikan
sesi lain tidak bisa membaca, lalu **menghapus** event tersebut.

## 3. Observability

| Aspek | Status | Bukti |
|---|---|---|
| Trace sintetis diberi label | **VERIFIED** | `TraceRecorder` menandai `synthetic: true`; `assert_production_ready()` menolak promosi. Tes: `tests/test_observability_trace_contract.py` (6 lulus). |
| Sink AgentCore tanpa endpoint | **VERIFIED (error eksplisit)** | `create_observability_sink(provider="agentcore", endpoint=None)` melempar `ObservabilityUnavailableError`. |
| Klaim trace AWS | **tidak ada** | Aplikasi memakai sink lokal; tidak ada klaim X-Ray/CloudWatch di dokumen ini. |

## 4. Ringkasan keputusan pemilik

| Keputusan | Dampak | Perintah |
|---|---|---|
| Lampirkan policy Fase 11 | Memory tulis-baca bisa dibuktikan; target Gateway bisa dibuat | `aws iam put-user-policy --user-name <user> --policy-name MealChainFase11 --policy-document file://infra/aws/iam-mealchain-fase11.json` (ganti `${AWS_ACCOUNT_ID}` dan `${MEMORY_ID}` lebih dulu) |
| Buat Gateway + target | Butir 4 bisa naik ke VERIFIED | butuh izin di atas; biaya resource AgentCore berlaku |
| Nyalakan `AGENT_MEMORY_WRITE=1` | Langkah LEARN benar-benar menulis Memory | setelah izin tulis ada dan tes live lulus |
