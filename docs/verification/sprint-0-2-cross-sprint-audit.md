# Audit Kontrak Lintas Sprint 0–2

> **Snapshot tahun 2026 (tanggal tidak tertulis)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

Tanggal audit: 2026-10-06 (WIB)
Branch: `feature/sprint2-decision-intelligence`
HEAD audit: `5deb4ef`
Metode: inspeksi source/migration/test/database terkini + final gate Docker dari HEAD.

## 1. Batas audit

Audit ini membandingkan kontrak aktual `IDEA.md`, `TODO.md`, `Rules.md`,
`workflows.md`, `Roadmap.md`, `docs/PRD.md`, `docs/Architecture.md`,
`docs/Schema.md`, `docs/Skill.md`, verification Sprint 1/2, migration, ORM,
API, test, dan database berjalan.

Unit test AWS/AgentCore/Strands yang ada adalah mock/host-only. Unit test tersebut
tidak diperlakukan sebagai bukti akses provider saat ini.

## 2. Final evidence HEAD

| Gate | Perintah | Hasil aktual |
|---|---|---|
| Migration upgrade | `docker compose exec -T backend alembic upgrade head` | exit 0 |
| Backend regression | `docker compose exec -T backend pytest -q` | **296 passed**, 1 warning eksternal, exit 0 |
| Backend lint | `docker compose exec -T backend ruff check .` | All checks passed; warning konfigurasi Ruff deprecated |
| Frontend test | `docker compose exec -T frontend npm run test` | **1 passed**, exit 0 |
| Frontend lint | `docker compose exec -T frontend npm run lint` | No ESLint warnings/errors |
| Alembic current | `docker compose exec -T backend alembic current` | `006_decision_persistence (head)` |
| Alembic heads | `docker compose exec -T backend alembic heads` | satu head: `006_decision_persistence` |
| Docker | `docker compose ps` | backend, frontend, mock-sap up; postgres healthy |
| Live health | `curl http://localhost:8000/health` | HTTP 200 |
| Live balance | `GET /balance/Jakarta/telur` | HTTP 200; supply 300, demand 1080, shortage 780 |
| Live recommendation | `POST /balance/recommend` | HTTP 200; recommendation real dari database |

## 3. Matrix kontrak Sprint 0–2

| Contract | Sprint 0 | Sprint 1 | Sprint 2 | Status | Evidence |
|---|---|---|---|---|---|
| Repository/Docker/Postgres/FastAPI | selesai | dipakai | dipakai | PASS | `docker-compose.yml`, `backend/app/main.py`, Docker health |
| Python canonical 3.12 | ditetapkan | dipakai | dipakai | PASS | `docs/Architecture.md`, container pytest Python 3.12 |
| 10 lokasi × 3 komoditas | belum | selesai | dipakai | PASS | seed, `test_seed_data.py`, live DB |
| Supply/demand latest record | belum | selesai | dipakai | PASS | API, `recommendation_service.py`, live Jakarta 300/1080 |
| Freshness thresholds | kontrak | selesai | dipakai | PASS | `freshness.py`, tests boundary |
| Safety excursion hard constraint | kontrak | selesai | diperketat | PASS | `safety.py`, candidate generator, SDC rejection, scenario alternative |
| Price threshold 5%/15% | kontrak | selesai | dipakai ulang | PASS | `price.py`, service anomaly output |
| Logistics/capacity/window | kontrak | selesai | dipakai generator | PASS | `logistics.py`, generator tests |
| Forecast fallback | direncanakan | selesai | tidak diubah | PASS | demand forecast tests, `statistical_fallback` |
| Mock SAP | direncanakan | seed + adapter/mock | tetap MOCK | PASS | mock service/tables, no real SAP claim |
| Supplier quote + supplier_id | belum | migration 004 + seed | dipakai SDC | PASS | migration 004, ORM, seed, tests |
| Exactly three roles | kontrak final | schema/model guard | belum auth runtime | **PARTIAL** | `users.py`, DB checks, no login/RBAC middleware |
| JWT login | TODO carry-over | belum | belum | **CARRY-OVER / S3 PREREQUISITE** | tidak ada auth router/implementation |
| RBAC endpoint | kontrak arsitektur | belum | belum | **CARRY-OVER / S3 PREREQUISITE** | router hanya `get_db`, tanpa current-user dependency |
| Approval matrix | PRD/Architecture | schema approvals ada | enforcement belum ada | **CARRY-OVER / S3 PREREQUISITE** | `approvals` table ada; actions API belum ada |
| Decision persistence | belum | belum | migration 006 + API create/read | PASS untuk persistence saja | ORM/migration/API/tests |
| `expires_at` | belum | belum | mandatory + validity predicate | PASS | migration, model, validity tests |
| Evidence fusion | PRD/Architecture | belum | context evidence assembler saja | **CARRY-OVER** | `/evidence/fuse` belum ada |
| `decisions.outcome` | Schema/roadmap lama belum tersedia | belum | belum | **CARRY-OVER / dependency review** | tidak ada kolom/model/migration |
| Receiving inspection | PRD/roadmap dependency | belum | belum | **CARRY-OVER / S3 Learn dependency** | evidence type ada, workflow/table belum |
| Expiry status/job | kontrak expiry | belum | predicate/API validity | **CARRY-OVER** | tidak ada scheduler/status transition job |
| Frontend test infrastructure | belum | blocker | Vitest ditambahkan | PASS infrastructure only | Vitest smoke 1 passed |
| Frontend login/dashboard | PRD/design | belum | belum | **CARRY-OVER / S3 prerequisite for UI E2E** | hanya shell/test smoke |
| OpenAPI artifact | arsitektur | belum | belum | **CRITICAL BLOCKER S3** | `backend/openapi.json` tidak ada |
| Bedrock current access | wajib diverifikasi | historical/mock only | belum | **CRITICAL BLOCKER S3** | AWS CLI STS exit 253: credentials unavailable |
| AgentCore current access | wajib diverifikasi | historical/mock only | belum | **CRITICAL BLOCKER S3** | runtime env unset; live probe source missing |
| Strands hello-world | wajib diverifikasi | host-only mock test | belum | **HIGH BLOCKER S3** | `agent/` hanya `__init__.py` + prompts init; implementation missing |
| AgentCore Gateway | belum | belum | belum | **S3 task** | no gateway config/registration |
| AgentCore Memory/Observability | belum | schema trace only | belum | **S3 task** | `agent_traces` schema exists, actual trace absent |
| Actions propose/approve/execute | Architecture/PRD | belum | belum | **CRITICAL CARRY-OVER** | no router/service implementation |
| No secrets in Git | kontrak | test template | current repo checked | PASS with caveat | only `.env.example` tracked; no real `.env` tracked |
| No obsolete roles in active DB contract | final ruling | DB checks | unchanged | PASS | model/migration checks; historical docs only in ledger |

## 4. Safety and SDC correction

Ruling Roy 2026-10-06: **Opsi A**.

```text
Expected Loss = 0.2 × (1 − freshness) × Purchase Cost
Freshness Risk Penalty = 0.50 × Purchase Cost jika freshness < 0.60
```

Untuk `600 kg × Rp26.200`, freshness `0.50`:

| Komponen | Nilai |
|---|---:|
| Purchase | Rp15.720.000 |
| Transport | Rp21.600 |
| Handling | Rp150.000 |
| Expected loss | Rp1.572.000 |
| Freshness risk | Rp7.860.000 |
| Safety risk | Rp0 |
| Total | **Rp25.323.600** |

Freshness `0.50` adalah `fail`, sehingga angka tersebut hanya uji aritmetika;
kandidat tidak boleh dihitung sebagai kandidat eligible atau diranking.

Scenario synthetic juga sudah memeriksa dua sisi:

- kandidat Cianjur `safety=fail`: excluded sebelum cost/ranking;
- kandidat Bogor telur `safety=pass`, freshness pass, quote/supplier valid,
  surplus, shortage, dan logistics feasible: tetap eligible dan muncul.

## 5. Synthetic versus seeded/live

Keduanya tidak boleh digabung sebagai satu bukti:

- **Contract/synthetic:** Cianjur `1400/500 → surplus 900`, Jakarta
  `300/1000 → shortage 700`.
- **Seeded/live database:** latest Jakarta supply `300`, demand `1080`,
  shortage `780`; live `/balance/Jakarta/telur` mengembalikan angka tersebut.

Perbedaan ini bukan defect otomatis; contract fixture menguji formula dan
pipeline, sedangkan live probe menguji latest-record database.

## 6. Carry-over matrix

| Existing task | Original sprint | Current state | Carry-over? | S3 dependency? | Decision |
|---|---:|---|---|---|---|
| S2-01 standalone `/cost/safe-delivered` | 2 | belum ada | Ya | Ya, Gateway tool contract | S3-01 prerequisite atau explicit scope gate |
| S2-02 `/balance/analyze` penuh | 2 | balance facts + recommend ada | Ya | Ya, Gateway mapping | selesaikan sebelum Gateway bila contract dibutuhkan |
| S2-03 `/evidence/fuse` | 2 | belum ada | Ya | Ya untuk VERIFY/TRACE | prerequisite sebelum Event 1 penuh |
| S2-04 JWT login | 2 | belum ada | Ya | Ya | prerequisite sebelum authenticated agent/UI flow |
| S2-05 RBAC | 2 | belum ada | Ya | Ya | prerequisite action boundary |
| S2-05b approval matrix | 2 | belum ada | Ya | Ya | prerequisite actions |
| S2-05c demo accounts | 2 | belum ada | Ya | Ya untuk UI E2E | prerequisite demo |
| S2-05d receiving inspection | 2 | belum ada | Ya | Untuk LEARN/outcome | dependency; jangan klaim LEARN penuh sebelum tersedia |
| S2-05e expiry | 2 | predicate/API validity selesai | Sebagian | Ya untuk execute gate | scheduler/status job masih carry-over |
| S2-06 frontend login | 2 | belum ada | Ya | Ya untuk UI E2E | S3-12 dependency |
| S2-07 dashboard shell/map | 2 | belum ada | Ya | Ya untuk S3-12/S3-13 | carry-over sebelum UI acceptance |
| S2-08 clean `openapi.json` | 2 | belum ada | Ya | **Ya, hard gate** | S3-01 harus menghasilkan artifact reproducible |
| S0-04 Bedrock access | 0 | current unavailable | Ya | **Ya, hard gate** | Owner/provider credential action; jangan fabricate |
| S0-05 AgentCore access | 0 | current unavailable/unverifiable | Ya | **Ya, hard gate** | Owner/provider verification |
| S0-06 Strands hello-world | 0 | implementation missing | Ya | Ya | S3-03 precondition |
| `decisions.outcome` | roadmap/schema review | belum | Ya | S3-08/S3-11/S3-14 review | add only after contract approval |
| `/actions/propose` | Architecture/PRD | belum | Ya | **Ya** | S3-11 |
| `/actions/approve` | Architecture/PRD | belum | Ya | **Ya** | S3-11 |
| `/actions/execute` | Architecture/PRD | belum | Ya | **Ya** | S3-11, human approval + MOCK only |

## 7. Contract conflicts and rulings

1. SDC numeric conflict telah diselesaikan eksplisit oleh Roy dengan Opsi A;
   tidak ada konflik terbuka pada formula.
2. `docs/PRD.md` masih memakai label historis `SPPG Staff` dan `Dinas/BGN
   Admin` pada target-user prose, sedangkan role runtime/schema final adalah
   tiga role. Ini bukan alasan menghidupkan role lama; implementasi tetap
   hanya `sppg_head`, `sppg_nutritionist`, `bgn_monitor`. Terminology PRD
   memerlukan owner ruling sebelum diselaraskan pada dokumentasi utama.
3. `Rules.md` dan historical Sprint 0 plan masih menyebut `.env.example`,
   sementara project policy saat ini melarang membuat template secrets baru.
   Tidak ada file template baru dibuat dalam audit ini; existing tracked
   `.env.example` dicatat sebagai policy debt.

## 8. Verdict cross-sprint

- Kontrak deterministik Sprint 1–2: **PASS** setelah correction.
- Migration/model/live DB alignment: **PASS** untuk current tables/migrations,
  single head 006.
- Security/action/auth contract: **BLOCKED**; belum diimplementasikan.
- AWS/Bedrock/AgentCore/Strands current-state prerequisite: **BLOCKED**;
  current provider evidence tidak tersedia dan implementation source agent
  belum ada.
- Sprint 3 implementation: **NOT STARTED**.
- Sprint 3 planning: **READY WITH EXPLICIT PREFLIGHT STOP**.
