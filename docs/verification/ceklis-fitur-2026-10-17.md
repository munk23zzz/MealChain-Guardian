# Ceklis fitur MealChain Guardian — yang sudah dan belum terimplementasi

**Tanggal pengukuran:** 2026-10-17 00:52 WIB (16 Okt 17:52 UTC)
**Repo:** `E:\hackathon\HackathonAWS\mealchain-guardian`
**Branch:** `feature/sprint2-decision-intelligence` · komit terakhir `af2cf6f` (2026-10-17 00:23)
**Disusun oleh:** Hermes (sesi ceklis, tanpa mengubah kode aplikasi)

Legenda status:

| Tanda | Arti |
|---|---|
| `[x]` | Terbukti ada **dan** jalan — ada artefak + bukti jalur data (probe/kode/test) |
| `[~]` | Ada tapi belum lengkap, atau belum terbukti pada sesi ini |
| `[ ]` | Belum ada |

**Metode yang dipakai.** `git status/log`, tabel status `TODO.md`, pembacaan guard `require_roles(...)` per endpoint,
skema `GET /openapi.json`, probe API **read-only** dengan tiga akun demo (SPPG Head, Nutritionist, BGN Monitor),
suite frontend via kontainer, dan `psql` langsung ke DB compose.
**Yang sengaja TIDAK dijalankan:** suite backend penuh, `next build`, dan probe endpoint mutasi
(DB compose adalah DB demo yang dilihat juri).

---

## 0. Keadaan mesin saat pengukuran

| Pemeriksaan | Hasil terukur |
|---|---|
| Docker | server 29.4.3; 4 service Up — backend, frontend, mock-sap, postgres (healthy) |
| `GET /health` backend | 200 |
| Frontend | `http://127.0.0.1:3010` → 200 (port 3000 tidak dipakai) |
| `GET /decisions` tanpa bearer | 401 |
| Alembic | `current` = `heads` = **016_batch_receipts** |
| OpenAPI | **54 path** |
| Suite frontend (kontainer) | **887 lulus / 75 berkas** (run ke-2; run ke-1 2 gagal — lihat §8.4) |
| DB | users **19** (16 residu tes), locations 10, suppliers 35, batches 7, decisions 204, agent_traces 297 |
| Status keputusan di DB | 184 `proposed` · 12 `pending_approval` · 5 `rejected` · 2 `executed` · 1 `verifier_flagged` |

---

## 1. Domain & safety (backend deterministik)

- [x] Freshness satu kontrak: `PASS_THRESHOLD = 0.85`, `VERIFY_THRESHOLD = 0.60` (`backend/app/core/freshness.py:7-8`)
- [x] `POST /safety/evaluate` + batas suhu 30 menit
- [x] Scoring kandidat (demand fit, supply, freshness, safety, supplier reliability, logistik); safety `fail` → skor 0, `eligible=False`
- [x] `constraints.py` memblokir freshness/safety `fail` di backend (bukan di frontend)
- [x] Safe Delivered Cost: purchase + transport + handling + expected loss + freshness risk + safety risk + jarak pemasok (kaki pertama, F7d)
- [x] `/balance/analyze`, `/balance/recommend`, `/balance/map` (scope-aware)
- [x] Binding batch ↔ supplier + revalidasi saat execute (safety, exclusion, expiry)
- [x] Seed 10 lokasi × 3 komoditas; 35 supplier (14 kanonik + 21 demo) di DB

## 2. Auth, RBAC, scope

- [x] JWT + tepat tiga role resmi (`sppg_head`, `sppg_nutritionist`, `bgn_monitor`); `require_roles(...)` di seluruh 27 berkas router
- [x] Cakupan per peran — **diukur live sesi ini**:
  - SPPG Head `GET /balance/map?commodity=telur` → **1 lokasi** (Jakarta saja)
  - BGN Monitor endpoint sama → **10 lokasi**
  - Head `GET /admin/users` → **403**; Monitor → **200**
- [x] `bgn_monitor` read-only pada jalur mutasi; tetap bisa membaca `/decisions` lintas lokasi
- [x] Guard mutasi konsisten (`MUTATING_ROLES`) pada demo, events, evidence fuse, supplier exclusion
- [~] Approval matrix masih generik: verdict `consistent` = **1** approval (salah satu role), `flagged`/`unavailable` = 2 role (`backend/app/core/approval_matrix.py`). Tidak ada syarat "dua user berbeda" dan tidak ada urutan Head → Nutritionist
- [ ] **Head-only** propose / penentuan purpose / execute: kode masih `VERIFIER_ROLES = ("sppg_head", "sppg_nutritionist")` di `backend/app/api/actions.py:30` (dipakai baris 111, 185, 264, 352, 545)
- [ ] Nutritionist diblokir dari propose & execute secara eksplisit (konsekuensi butir di atas)

## 3. Alur keputusan

- [x] `POST /actions/propose` (201) · `/verify` · `/approve` · `/execute` · `/repropose` (201)
- [x] Approval dan execution adalah dua state berbeda; execute memeriksa approval, expiry, verifier, binding, exclusion, safety
- [x] Rejection tanpa alasan → 422
- [x] PO mock SAP berlabel `MOCK` (`MC-*`)
- [x] Supplier exclusion + restore lewat alur approval (bukan jalur terpisah)
- [x] Keputusan dapat dipicu dari UI, bukan hanya API (Event 1/2/3, "Ajukan keputusan", "Ajukan ulang")
- [~] Dual approval dua user + Head-only execute (kebijakan owner §13.3) — **belum ada di kode**
- [x] Bukti hidup: 204 keputusan tersimpan dengan lima status berbeda

## 4. Evidence, audit, KPI

- [x] Evidence fuse, dossier, compliance, ledger Merkle verify (`/ledger/verify` 200)
- [x] `agent_traces` terisi (297 baris), persistence + whitelist langkah
- [x] KPI 7 metrik dengan state jujur — **diukur live**: Meal Continuity `available` · Avoidable Food Loss `no_data` · Regional Imbalance `available` · Safe Delivered Cost `available` · Price Deviation `no_data` · Decision Time `available` · Evidence Completeness `available` (tidak ada `0` palsu)
- [x] Tab "KPI & Kualitas Agen" (gabungan dua tab; Target KPI dihapus pada F8)
- [~] Evidence Consistency (baru, **belum di-commit**): `backend/app/core/evidence_consistency.py` sudah dipakai 4 service (eligibility, exclusion, event2, event3) + 2 berkas tes
- [~] Celah penulis data KPI yang pernah terukur (langkah trace `ACT`, `decision_evidence.is_consistent`) sedang ditambal; tes `test_kpi_act_trace.py` dan `test_kpi_safe_delivered_cost.py` masih berkas baru

## 5. Lapisan agen & integrasi

- [x] Orkestrator Event 1 DETECT → … → SUPERVISE; `POST /demo/event1` + tombol "Jalankan Event 1 penuh" → 201 dalam 26,2 dtk, narasi supervisor `narrated`
- [x] Verifier REST independen + provider chain dengan fallback dan label provider jujur
- [x] SAP AI Core hidup (S4-10, 11 Okt): `backend/app/ai_providers/sap_ai_core_caller.py` (LLM `/invoke` + SAP-RPT-1.6 `/predict`), token di-cache + disapu dari pesan error, 3 tes `-m live` lulus; label `SAP-RPT-1.6` hanya untuk respons asli
- [x] Mock SAP sebagai default (`SAP_MODE=mock` + service `mock-sap`)
- [x] Agent Strands sebagai artefak runtime: `agent/supervisor_agent.py`, `runtime_server.py`, `Dockerfile`, `deploy_agentcore.py` — terbukti lokal (`GET /ping` 200, `POST /invocations` 200 dalam 3,4 dtk ke Bedrock haiku-4.5)
- [ ] Deploy AgentCore Runtime: **0 runtime di AWS**. Akun aktif (624606539664, user `megu`, us-west-2): 0 runtime, 0 gateway, 1 memory (ACTIVE). Preflight `iam:SimulatePrincipalPolicy` → seluruh `ecr:*` DITOLAK dan `iam:CreateRole/AttachRolePolicy/PassRole` DITOLAK, jadi Runtime tidak dapat dibuat
- [ ] `.env`: `AGENTCORE_RUNTIME_ARN` dan `AGENTCORE_GATEWAY_URL` = **0 karakter** (diukur sesi ini)
- [ ] AgentCore Memory & Observability di level aplikasi: adapter sengaja fail-closed (`MemoryUnavailableError` bila endpoint kosong; sink observability melempar galat eksplisit)
- [ ] AWS for SAP MCP: S5-01 `Blocked` (tidak ada konfigurasi S/4HANA di repo), S5-02…S5-06 `Not Started`
- [~] Slot rantai agen yang masih mati: `INFERHUB_URL` kurang suffix `/chat/completions` (25 slot 404), model verifier `cb/gpt-6-astra`, `SUPERVISOR_MODEL_FALLBACK_1` Bedrock `claude-sonnet-4` (ditandai Legacy)

## 6. Frontend

Satu halaman `frontend/app/page.tsx` dengan **11 tab** (bukan 8 modul PLAN.md):

- [x] **Hari Ini** — rekap live (keputusan actionable, batch kedaluwarsa, shortage, KPI, ledger) + kalender agenda harian dari `GET /agenda` (live: `period` + `scope` + `days` terisi)
- [x] **Overview** — strip KPI dari data peta asli + peta MapLibre 10 lokasi + tabel breakdown
- [x] **Recommendations** — status enum backend apa adanya, tenggat dari server, badge "perlu tindakan" + "lewat tenggat"
- [x] **Decision & Evidence** — biaya, keamanan, governance, riwayat iterasi, bukti/ledger/ttd, ekspor
- [x] **Keamanan Pangan** — cakupan "Lokasi saya" default, kartu pasokan masuk + kekurangan dari `/balance/map`, periksa/uji ulang kiriman (menulis ke DB), penerimaan barang 5 titik + opsi "Lainnya" (migrasi 016)
- [x] **Surplus & Limbah** (khusus peran SPPG)
- [x] **Pemasok** — dari `GET /suppliers` nyata + pin pemasok di peta + kolom Jalur kirim + kartu ringkasan
- [x] **Agent Log** — timeline trace + panel provider
- [x] **KPI & Kualitas Agen**
- [x] **Pengaturan** — hanya `bgn_monitor` (200 terbukti; SPPG Head 403)
- [x] **Demo Control** — hanya approver: Event 1/2/3, panel data & rentang waktu, segarkan ke hari ini, bersihkan
- [x] Top bar (cakupan lokasi untuk monitor, notifikasi actionable, chip peran) + side nav dapat dilipat
- [x] Jalur kiriman di peta + ETA nyata dari DB: migrasi `015_batch_dispatch` (`batches.dispatched_at`), blok `journey` (`state`, `eta_at`, `remaining_min`, `progress`), kotak "Info map" — live: 1 rute dalam cakupan, 1 `sudah_tiba`, sumber OSRM
- [~] Delapan modul kanonik PLAN.md (PLAN-016…019): tidak diadopsi; nama modul di repo berbeda
- [ ] `trace-normalizer.ts` + empat status typed terpisah (PLAN-003): tidak ada dalam bentuk itu (label "Selesai tanpa anomali" sudah tidak ditemukan di kode)

## 7. Infra & gerbang verifikasi

- [x] Compose 4 service; postgres healthy; port host 15432
- [x] Migrasi berurutan 011 → 016; `current` = `heads`
- [x] 54 path OpenAPI; probe unauth 401
- [x] Suite frontend **diukur sesi ini**: 887 lulus / 75 berkas
- [x] Dokumen verifikasi terjaga: `fase-6` … `fase-12`, `fase-11`, `kalender-agenda-harian`, `kpi-penulis-data`, `agentcore-deploy`
- [~] Catatan hasil terakhir yang dikutip apa adanya: 800 lulus / 68 berkas (17 Okt) · backend 900 lulus / 3 skip / 2 gagal (16–17 Okt)
- [~] Suite backend **tidak** dijalankan ulang sesi ini — disengaja: DB compose adalah DB demo, dan dua berkas tes `/demo/timeseries` mem-purge seluruh deret demo bila gagal di tengah
- [ ] Tidak ada artefak deploy server di repo (hanya `infra/aws/*.json` + `agent/Dockerfile`); yang jalan sekarang adalah compose lokal

---

## 8. Yang menghambat / perlu keputusan pemilik

| # | Item | Bukti | Pemilik |
|---|---|---|---|
| 8.1 | 137 entri working tree belum di-commit (83 modified + 55 untracked): Fase 11 & 12, receipts, agenda, evidence-consistency | `git status --short`, `git diff --stat` 83 berkas / +7797 −1363 | Hermes (perlu izin commit) |
| 8.2 | Residu tes di DB demo: **19 user** (seharusnya 3); 16 akun `%@test.local` (mis. `pytest-far-nutritionist@test.local`) | `select role, count(*) from users group by role` | Hermes (mekanis) |
| 8.3 | Residu keputusan demo: 2 baris `status='executed'` membuat 2 tes KPI merah padahal kode benar | catatan `fase-12.md` §3 | Pemilik (tombol "Bersihkan data demo") |
| 8.4 | Satu tes **flaky**: run ke-1 `2 failed / 885 passed` pada `tests/shipment-timeline.test.ts` ("3 kejadian tercatat" vs "2"), run ke-2 887 lulus penuh | dua kali `npm run test` dalam 3 menit | Hermes (butuh jam deterministik) |
| 8.5 | Sesi lain tampaknya sedang bekerja di repo: berkas berubah < 20 menit sebelum pemeriksaan (`agent/LANGKAH-DEPLOY-MANUAL.md`, `backend/app/seed/timeseries.py`, `frontend/app/globals.css`, `DecisionEvidence.tsx`) | `find -mmin -20` | Pemilik (koordinasi sesi) |
| 8.6 | Blocker eksternal: izin IAM (peran eksekusi + ECR push + `iam:PassRole`) untuk AgentCore; akses S/4HANA + tenant SAP untuk AWS for SAP MCP | `docs/verification/agentcore-deploy.md` §2, §4 | Pemilik akun |
| 8.7 | Perbaikan `.env` yang belum dieksekusi: `INFERHUB_URL`, model id verifier, fallback supervisor Legacy, 4 tes host-only merah | `memory/global/active_context.md` (blok "Menunggu pemilik") | Pemilik |
| 8.8 | Kebijakan RBAC final (Head-only propose/execute, dual approval dua user) belum ditegakkan di kode | `backend/app/api/actions.py:30`, `core/approval_matrix.py` | Keputusan pemilik dulu — ini perubahan desain |

---

## 9. Delta terhadap `D:\Downloads\PLAN.md` (audit 11 Okt 2026)

PLAN.md mengaudit repo yang sama, tetapi sebagian isinya sudah tidak berlaku. Artefak yang dirujuknya
tidak ada lagi di repo ini maupun di klon demo `HackathonBil\MealChainGuardian`:
`frontend/components/AgentRunSummary.tsx`, `OverviewLocationBreakdown.tsx`, `KpiTargets.tsx`,
`frontend/lib/trace-normalizer.ts`. Ia juga menyebut Alembic head `011_supplier_exclusions`, padahal sekarang `016_batch_receipts`.

| Klaim PLAN.md | Kenyataan repo (diukur 17 Okt) |
|---|---|
| PLAN-011 SAP AI Core `Blocked`; caller masih `RuntimeError: belum terimplementasi` | **Salah untuk sekarang** — `sap_ai_core_caller.py` nyata dan terbukti live (S4-10, 11 Okt); `grep "belum terimplementasi"` di `backend/app` = kosong |
| PLAN-012 "Gateway READY, Memory ACTIVE" | Itu bukti akun AWS **lama** (679583588036). Akun yang dipakai sekarang: 0 gateway, 0 runtime, 1 memory |
| PLAN-002 / PLAN-021 berlabel `Done` (RBAC final + dual approval) | **Tidak sesuai kode**: `VERIFIER_ROLES` masih dipakai untuk propose/verify/approve/execute dan matrix approval masih generik |
| PLAN-004 gate `happy-dom` container (P0) | **Tidak berlaku**: `frontend/vitest.config.ts` memakai `environment: "node"`; `happy-dom` tidak ada di `package.json` maupun `node_modules` kontainer |
| PLAN-001 `PLAN-001 tidak lagi memblokir roadmap` (freshness 0.85/0.60) | Sesuai: `core/freshness.py:7-8` memakai 0.85/0.60 |
| PLAN-020 audit 10 lokasi, `users.location_id` satu assignment | Sesuai dan sudah ditegakkan: scope per peran terbukti live (Head 1 lokasi, Monitor 10 lokasi) |
| PLAN-015 Settings/Admin "out of scope" | Di repo justru **selesai** sebagai S4-11 (tab Pengaturan, hanya `bgn_monitor`) |

---

## 10. Yang TIDAK diverifikasi di sesi ini

- Suite backend penuh, `ruff`, `tsc`, `next lint`, `next build` — tidak dijalankan (angka di §7 dikutip dengan tanggalnya).
- Probe endpoint mutasi (propose/approve/execute/demo) — sengaja dihindari agar DB demo tidak berubah.
- Inferensi SAP AI Core live dan koneksi AgentCore ke AWS — tidak diprobe ulang; statusnya dikutip dari artefak tim (11–16 Okt).
- Akses AWS for SAP MCP dan tenant SAP — belum ada buktinya sama sekali.
- Review screenshot browser dan audit aksesibilitas di semua ukuran viewport.
- Klon demo `E:\hackathon\HackathonBil\MealChainGuardian` (hanya diperiksa keberadaan empat komponen PLAN.md — tidak ada).

---

## 11. Langkah berikutnya yang diusulkan (berurutan)

1. **Mekanis, aman, bisa dibuktikan:** sapu 16 residu user `%@test.local` (§8.2), lalu ukur ulang suite backend di kontainer dalam keadaan bersih dan catat angkanya.
2. **Mekanis:** buat tes `shipment-timeline` deterministik terhadap jam (inject `now`) supaya tidak flaky (§8.4).
3. **Menunggu pemilik:** bersihkan residu keputusan demo sebelum presentasi (§8.3), lengkapi izin IAM (§8.6), dan putuskan apakah kebijakan RBAC final Head-only + dual approval dikerjakan (§8.8 — perubahan desain, bukan perbaikan).
4. **Menunggu izin:** commit/push Fase 11 & 12 beserta pekerjaan receipts/agenda/evidence-consistency (§8.1).
