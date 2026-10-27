# Status AgentCore — MealChain Guardian

Diperbarui: 27 Okt 2026 · Fase 11 (`MG/phase-11-ledger-agentcore.md`)
Commit terkait: `d98adec` (butir 1), `cd2271f` (butir 2), `0b1d87a` (butir 3), `b2f6b0c` (butir 4–6),
ditambah putaran kelengkapan berkas + gerbang ulang (butir 7) pada commit terakhir fase ini.

Dokumen ini memisahkan **empat bukti Gateway** dan **dua bukti Memory** yang sering dicampur
menjadi satu kata "DONE". Setiap baris punya status sendiri dan cara ukurnya; status hanya
naik kalau ada operasi nyata yang hasilnya dibaca.

Legenda status: `VERIFIED` = ada operasi nyata yang berhasil dan hasilnya dibaca ·
`UNVERIFIED` = belum bisa dibuktikan (izin/resource belum ada) · `NOT_CONFIGURED` = fitur
memang tidak diaktifkan.

## 0. Putaran ulang verifikasi — 27 Okt 2026

Dijalankan ulang sesudah berkas tes yang disebut rencana fase dilengkapi. Kosakata status kini
berasal dari **satu modul** (`backend/app/services/agentcore_evidence.py`) yang dipakai bersama
oleh `scripts/probe_agentcore_gateway.py` dan `backend/tests/test_agentcore_live_smoke.py`,
supaya tidak ada dua definisi "VERIFIED" yang bisa menyimpang.

| Operasi | Cara | Hasil terukur | Waktu (UTC) |
|---|---|---|---|
| Probe baca-saja Gateway + Memory | `scripts/probe_agentcore_gateway.py --ringkas` | `resource_exists=VERIFIED (0 gateway)`, `target_ready=UNVERIFIED`, `tool_invoked=UNVERIFIED`, `app_uses_gateway=NOT_CONFIGURED`, `integrasi_aktif=false`; Memory `GetMemory=VERIFIED/ACTIVE`, `ListEvents=VERIFIED`, `write=UNVERIFIED` | 2026-10-27T15:16:59 |
| Tulis-baca Memory live | `RUN_LIVE_AGENTCORE=1 pytest tests/test_agent_memory_live.py -m live` | **gagal sebagaimana diduga**: `AccessDeniedException … bedrock-agentcore:CreateEvent` untuk user `megu`; 0 event terbuat, 0 terhapus | 2026-10-27T15:19 |
| Kontrak Memory jalur live (tanpa AWS) | `pytest tests/test_agent_memory_live_contract.py` | **10 lulus** | 2026-10-27T15:25 |
| Kontrak 4 bukti + smoke live | `pytest tests/test_agentcore_live_smoke.py` | **10 lulus · 2 live skip** | 2026-10-27T15:25 |
| Anchor ledger (live) | `GET /ledger/verify` (token monitor, DB demo) | `valid=true`, `blocks=2916`, `anchor.match=true`, `anchor.height=2768`, `linked_ratio=1.0` | 2026-10-27T15:26 |

Kesimpulan yang **tidak berubah**: integrasi Gateway belum aktif, dan Memory belum bisa
dibuktikan tulis-baca ke AWS. Yang berubah: keduanya sekarang **dijaga tes**, bukan hanya
catatan — status `UNVERIFIED`/`NOT_CONFIGURED` tidak bisa naik karena konfigurasi terisi, dan
`integrasi_aktif` hanya `true` bila keempat bukti `VERIFIED`.

## 1. Gateway — empat bukti terpisah

Sumber: `scripts/probe_agentcore_gateway.py` (hanya operasi baca) dijalankan
`docker run --env-file secrets/aws-app.env --env-file .env …`, region `us-west-2`,
akun `624606539664`, user `megu`.

| # | Bukti | Status | Cara ukur / alasan |
|---|---|---|---|
| 1 | `resource_exists` | **VERIFIED (negatif: 0 gateway)** | `ListGateways` berhasil (izin boleh), hasil `gateways = []`. Jadi kebenarannya: **belum ada Gateway** di region ini. |
| 2 | `target_ready` | **UNVERIFIED** | Tidak ada gateway untuk diperiksa targetnya; `ListGatewayTargets` tidak dipanggil. |
| 3 | `tool_invoked` | **UNVERIFIED** | Belum ada satu tool Gateway yang dipanggil dan hasilnya dibaca aplikasi. Probe sengaja tidak memanggil tool. |
| 4 | `app_uses_gateway` | **NOT_CONFIGURED** | `AGENTCORE_GATEWAY_URL` kosong di `.env` (diukur: panjang nilai 0). Registry (`backend/app/agent_tools/registry.py`) masih artifak konfigurasi 10 tool, bukan klien aktif. |

Kesimpulan jujur: **integrasi Gateway belum aktif**. Tidak ada klaim "Gateway jalan".

Dijaga tes (`tests/test_agentcore_live_smoke.py`): `integrasi_aktif` ditolak `true` bila satu bukti
saja belum `VERIFIED`; status di luar kosakata (`DONE`, `WORKING`, `FAIL`) dilaporkan sebagai
galat; `AGENTCORE_GATEWAY_URL` terisi **tidak** menaikkan status apa pun; `AccessDenied` dipetakan
ke `UNVERIFIED`.

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
| 3 | `write_allowed` (CreateEvent) | **UNVERIFIED** | `CreateEvent` **ditolak IAM** (diukur ulang 2026-10-27T15:19Z): `AccessDeniedException … no identity-based policy allows bedrock-agentcore:CreateEvent`. |
| 4 | `namespace` desain | **VERIFIED (kode + tes)** | Namespace = `actorId` + `sessionId`, sesi = `"<demo_session_id>:<decision_id>"`. Diuji `test_agentcore_backend_namespace_isolates_sessions` (isolasi) dan `test_create_event_mengirim_actor_session_dan_payload_tersanitasi` (pasangan actor+session yang benar-benar dikirim ke API). |
| 5 | `sanitasi` | **VERIFIED (kode + tes)** | `sanitize_memory_payload` membuang key berbau secret (rekursif); tes memastikan `password`/`api_key` tidak ada di teks JSON yang dikirim ke AWS. |
| 6 | `tulis-baca nyata di AWS` | **UNVERIFIED** | `tests/test_agent_memory_live.py` (`RUN_LIVE_AGENTCORE=1`, `-m live`) berhenti di `CreateEvent` = AccessDenied. Bukan lulus, bukan pula klaim bekerja. |
| 7 | `gagal tulis tidak mengubah angka` | **VERIFIED** | `tests/test_event1_supervisor_flow.py::test_memory_gagal_tidak_mengubah_angka_keputusan` — verdict, kandidat, dan angka identik; langkah `LEARN` mencatat `status=unavailable`. |

Kode konsumen: `catat_learn()` dipanggil `event1_orchestrator` pada langkah **LEARN**,
**default MATI** (`AGENT_MEMORY_WRITE=0`) — dijaga `test_default_demo_tidak_menulis_memory`.
Nyalakan hanya setelah izin tulis ada.

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

## 4. Berkas bukti (semua ada di repo)

| Berkas | Fungsi | Hasil |
|---|---|---|
| `backend/app/services/agentcore_evidence.py` | kosakata status + `ringkas()`/`integrasi_aktif` (sumber tunggal) | dipakai probe + tes |
| `scripts/probe_agentcore_gateway.py` | probe baca-saja Gateway & Memory, cetak 4 bukti terpisah | dijalankan 27 Okt (exit 0) |
| `backend/tests/test_agent_memory_live_contract.py` | kontrak jalur live Memory tanpa AWS (namespace, payload, AccessDenied→unavailable, opt-in) | 10 lulus |
| `backend/tests/test_agent_memory_live.py` | tulis-baca NYATA di AWS (opt-in) | 1 live (AccessDenied 27 Okt) |
| `backend/tests/test_agentcore_live_smoke.py` | kontrak 4 bukti + smoke live baca-saja | 10 lulus · 2 live skip |
| `infra/aws/iam-mealchain-fase11.json` | policy yang belum dilampirkan | — |

## 5. Ringkasan keputusan pemilik

| Keputusan | Dampak | Perintah |
|---|---|---|
| Lampirkan policy Fase 11 | Memory tulis-baca bisa dibuktikan; target Gateway bisa dibuat | `aws iam put-user-policy --user-name <user> --policy-name MealChainFase11 --policy-document file://infra/aws/iam-mealchain-fase11.json` (ganti `${AWS_ACCOUNT_ID}` dan `${MEMORY_ID}` lebih dulu) |
| Buat Gateway + target | Butir 4 bisa naik ke VERIFIED | butuh izin di atas; biaya resource AgentCore berlaku |
| Nyalakan `AGENT_MEMORY_WRITE=1` | Langkah LEARN benar-benar menulis Memory | setelah izin tulis ada dan tes live lulus |

## 6. Pembaruan 28 Okt 2026 01.0x WIB — sebab tepat butir 4 belum bisa DONE

Pengukuran ulang dengan kredensial termuat (probe kini membaca `.env` lalu
`secrets/aws-app.env`; sebelumnya gagal `NoCredentialsError` dan itu sempat
terbaca seolah masalah IAM):

| Bukti | Status | Detail |
|---|---|---|
| `resource_exists` | VERIFIED | 0 gateway di us-west-2 (`ListGateways` diizinkan) |
| `target_ready` | UNVERIFIED | belum ada gateway; `CreateGateway` diizinkan tetapi wajib `roleArn`, sedangkan `iam:CreateRole`/`iam:PassRole` **implicitDeny** |
| `tool_invoked` | UNVERIFIED | `bedrock-agentcore:InvokeGateway` + `CreateGatewayTarget` **implicitDeny** |
| `app_uses_gateway` | NOT_CONFIGURED | `AGENTCORE_GATEWAY_URL` kosong |

`iam:SimulatePrincipalPolicy` untuk `arn:aws:iam::624606539664:user/megu`
(28 Okt 2026): allowed = `ListGateways`, `GetGateway`, `CreateGateway`,
`ListGatewayTargets`, `GetMemory`, `ListEvents`, `iam:GetRole`;
implicitDeny = `CreateGatewayTarget`, `InvokeGateway`, `DeleteGatewayTarget`,
`CreateEvent`, `DeleteEvent`, `iam:CreateRole`, `iam:PutRolePolicy`,
`iam:PassRole`, `iam:AttachUserPolicy`.

Artefak baru supaya penutupan hanya butuh satu perintah setelah izin ada:

- `scripts/provision_agentcore_gateway.py` — idempoten: preflight simulasi →
  buat/pakai `mealchain-gateway` (MCP) → daftarkan target `mealchain-tools`
  (10 tool dari `gateway_config.json`) → tunggu `READY` → panggil satu tool lewat
  MCP (`initialize`/`tools/list`/`tools/call`) → catat `AGENTCORE_GATEWAY_URL`
  ke `.env`. Exit 3 = BLOCKED izin (tidak membuat resource apa pun).
- `_qa/fase11-langkah-manual.md` — dua perintah admin (role gateway + policy user)
  dan perintah verifikasi `simulate-principal-policy` yang harus keluar kosong.
- `infra/aws/gateway-trust-policy.json`, `infra/aws/gateway-role-policy.json` —
  trust policy + izin minimum untuk service role gateway.
- `_qa/fase11/probe-20261028.{json,txt}` — bukti probe terbaru.

Status butir 4 tetap **UNVERIFIED**; yang berubah: penyebabnya kini tertulis
aksi-per-aksi dan jalur penutupnya sudah siap jalan.

## 7. Hasil akhir butir 4 — 28 Okt 2026 (integrasi aktif)

| Bukti | Status | Sumber |
|---|---|---|
| resource_exists | VERIFIED | `scripts/probe_agentcore_gateway.py --panggil` → 1 gateway READY |
| target_ready | VERIFIED | target `mealchain-tools` READY, 10 tool |
| tool_invoked | VERIFIED | `supply_get` → `quantity_kg=902.85` dibaca aplikasi |
| app_uses_gateway | VERIFIED | `app/services/agentcore_gateway.py` + tes live |

`integrasi_aktif=true`. Izin yang ditambahkan: role `MealChainAgentCoreGatewayRole`,
managed policy `MealChainFase11AgentCore`, managed policy `MealChainPassRoleAgentCore`
(lihat `MG/phase-11-ledger-agentcore.md`).

Catatan arsitektur: target Gateway tidak boleh meneruskan header `authorization`
(dibatasi AWS), sedangkan backend menuntut Bearer. Karena itu jalur Gateway →
`infra/gateway-shim/shim.py` → backend; shim hanya menambahkan token, tanpa logika.

Memory tulis-baca tetap **UNVERIFIED**: `CreateEvent` masih AccessDenied meski
simulasi ARN memory lulus.
