# Sprint 4 — Event 2 & 3, KPI, polish, rehearsal

## 1. Executive Summary

Dokumen ini adalah rencana implementasi untuk review Roy, bukan izin eksekusi. Judul mengikuti `Roadmap.md:84`. Scope resmi terdapat pada `Roadmap.md:84-96` dan tabel Sprint 4 di `TODO.md`: Event 2 interaktif, Event 3 interaktif, tujuh KPI dari records aplikasi, ringkasan approval, rehearsal, dan video fallback. AgentCore Identity serta App Runner tetap stretch, bukan prerequisite MVP.

Sprint 3 tetap berstatus DONE sesuai keputusan Owner. Pemeriksaan dependency menemukan perbedaan antara status historis tersebut dan kemampuan jalur aplikasi pada HEAD sekarang. Perbedaan tidak disembunyikan dan tidak otomatis dibawa menjadi proyek remediasi lintas-sprint.

**Status rencana: siap untuk review Owner, belum release-ready untuk implementasi.** S4-00 wajib menyelesaikan disposition blocker terlebih dahulu. Bagian yang memerlukan definisi bisnis atau schema baru diberi batas STOP; plan ini tidak berpura-pura memiliki kontrak yang belum diputuskan.

Temuan utama:

- Backend berhasil mengoleksi 463 tests; frontend mengoleksi 55 tests dalam 7 file. Ini collection, bukan hasil test PASS baru.
- Alembic live current dan heads adalah `008_rejection_loop`. OpenAPI file identik dengan live, 26 paths, tetapi kesamaan itu tidak membuktikan seluruh endpoint terlindungi.
- Terdapat handler tanpa auth pada `POST /decisions`, `GET /decisions/{decision_id}`, dan `POST /actions/repropose`. GET detail tanpa token mencapai lookup dan mengembalikan 404, bukan 401.
- Runtime caller, Memory backend, dan Observability sink aplikasi masih memiliki jalur yang selalu melempar unavailable. Resource AWS yang pernah READY/ACTIVE serta invoke PONG historis tidak membuktikan aplikasi melewati ketiga integrasi tersebut.
- Meal Continuity dan Avoidable Food Loss tidak memiliki facts bisnis yang cukup. Tabel `kpi_snapshots` di dokumen juga belum menjadi model/migration/live table. Tidak boleh mengganti menu dengan kg demand atau menganggap expired sebagai food loss.
- Ada drift live `seed_key`, perbedaan constraint SUPERVISE, dan ketidakjelasan event execution/approval timestamps untuk KPI. Disposition Owner harus eksplisit.

Satu-satunya file yang ditulis dalam planning adalah dokumen ini. Tidak ada production code, migration, DB, konfigurasi, frontend, prompt, AWS, atau status sprint yang diubah. Tidak ada commit.

## 2. Current State After Sprint 3

### Bukti repository dan runtime

Cut-off pemeriksaan: 8 Oktober 2026, zona +07:00. Root `D:/Projects/Mealchain`.

| Pemeriksaan | Observasi | Arti/batas bukti |
|---|---|---|
| Branch | `feature/sprint2-decision-intelligence` | Nama aktual, bukan asumsi snapshot |
| HEAD | `7089bcfe4bee7a3543709c42456742292e93ab26` | Baseline plan |
| Git status sebelum penulisan plan | Bersih, termasuk tidak ada untracked pada output `git status --short` | Tidak ada implementasi S4 |
| Recent commits | `7089bcf`, `1ec8a6b`, `a9eba93`, `ea16cde` | Closure S3 tidak hanya berada di working tree |
| Backend collection | 463 tests collected, exit 0 | Full suite belum dijalankan saat planning; percobaan awal timeout, retry collection berhasil |
| Frontend collection | 55 tests, 7 files, exit 0 | Bukan browser E2E atau test PASS |
| Docker | backend, frontend, mock-sap Up; postgres healthy | Availability saat inspeksi, bukan reliability certification |
| HTTP | backend `/health`, mock-sap `/health`, frontend `/` = 200 | Bukan bukti workflow |
| Alembic | current = heads = `008_rejection_loop` | Tidak membuktikan bebas drift |
| OpenAPI | File = live; 26 paths | Security metadata masih menunjukkan handler terbuka |
| Unauth probes | `/decisions`, `/supply/Jakarta/telur`, `/auth/me` = 401 | Tiga route ini terproteksi |
| Unauth detail probe | `/decisions/00000000-0000-0000-0000-000000000000` = 404 | Lookup berjalan tanpa JWT; tidak melakukan mutasi |
| Config presence | Runtime ARN, Gateway URL, Memory ID, primary Supervisor/Verifier/Forecast, Inferhub URL terisi | Hanya boolean keberadaan; nilai rahasia tidak dicetak |
| Container SDK | Strands tidak terpasang; service `bedrock-agentcore` tidak dikenali SDK | Bukan bukti bahwa deployed AWS Runtime tidak berfungsi |
| Demo flag | `DEMO_MODE=false` | Dipertahankan, bukan diubah agar demo lolos |

Bukti historis `docs/verification/sprint-3.md` mencatat backend 463 PASS, frontend 55 PASS, Ruff/lint/tsc/build PASS, auth 10/10, genuine host Runtime invoke HTTP 200/PONG, Memory ACTIVE, Gateway READY, dan Mock SAP E2E. Angka dan status tersebut **tidak dipromosikan menjadi hasil fresh pada HEAD ini**.

### As-built yang diperiksa

- Domain reusable berada pada `backend/app/core/`: scoring, constraints, freshness, safety, price, logistics, safe_delivered_cost, reliability, decision_validity. Balancing menggunakan `backend/app/services/recommendation_service.py` dan `fetch_operational_facts`.
- Auth `backend/app/api/auth.py` memakai JWT dan user DB. `require_roles` memeriksa role, tidak memeriksa location scope.
- `backend/app/api/actions.py` memiliki propose/verify/approve/execute/repropose. Execute memeriksa expiry, rejected, verifier presence, approval matrix, lalu menulis Mock PO. Source belum membuktikan revalidation batch safety pada waktu execute.
- `backend/app/services/event1_orchestrator.py` melakukan pipeline deterministik dan memanggil verifier/forecast/supervisor narration. Tidak ditemukan API yang menghubungkan `run_event1` ke OpsConsole. `POST /balance/analyze` memanggil recommendation service, bukan otomatis bukti Supervisor→Runtime→Gateway.
- `agent/` yang terinventaris pada HEAD hanya memuat `__init__.py` dan `prompts/__init__.py`. `test_supervisor_agent.py` mengimpor `supervisor_agent` yang tidak ditemukan di direktori tersebut. Host collection harus memeriksa ini, bukan menganggap container suite mencakupnya.
- `ai_provider_chain.py:24-54`: slot AgentCore mengembalikan callable stub yang melempar `NotImplementedError`. `agent_memory.py:74-84` dan `agent_observability.py:117-121` juga selalu melempar unavailable.
- `frontend/app/page.tsx` adalah shell aktual. Reuse `OpsConsole`, `RecommendationCard`, `DecisionActions`, `DecisionChain`, `ApprovalModal`, `AgentTraceViewer`, `ProviderPanel`, `RoleHero`, dan `lib/api.ts`. Jangan membangun ulang login/feed/detail hanya karena dokumen lama menyebut route yang berbeda.
- `ApprovalModal.tsx:25-33` saat ini menampilkan jumlah, biaya, verdict, dan pesan Mock SAP. Evidence utama, identitas source/target/supplier, expiry, approval progress belum menjadi ringkasan lengkap.
- `DecisionActions.tsx:128` mengirim verdict literal `consistent` melalui tombol Verifikasi. Ini bukan hasil independent Verifier dan perlu disposition sebelum approval summary diklaim terpercaya.
- Demo seeder memiliki empat case dengan trace yang disusun dari fixture. Fixture tersimpan di DB tetap fixture, bukan genuine external-provider activity.

### Rekonsiliasi data

Live DB memiliki tabel aplikasi sesuai model yang terdaftar, ditambah `alembic_version`. Domain tabelnya meliputi users, locations, commodities, suppliers, supply_records, demand_records, price_signals, batches, decisions, decision_evidence, approvals, agent_traces, sap_mock_material_stock, sap_mock_purchase_orders.

Tidak ditemukan receiving inspection, decision outcome, menu plan/fulfilment, disposal ledger, atau `kpi_snapshots` sebagai tabel live. `decisions.expires_at` tersedia dan NOT NULL. Rejection fields `rejection_reason`, `iteration`, `supersedes_id`, `demo_case` tersedia.

Live mempunyai kolom nullable varchar `seed_key` pada `supply_records`, `demand_records`, `sap_mock_purchase_orders`, beserta partial unique indexes `uq_seed_supply`, `uq_seed_demand`, `uq_seed_sap_po`. Kolom ini tidak terdapat dalam ORM dan tidak ditemukan sebagai creation migration di git. Jangan menghapus atau mengadopsinya otomatis.

Migration `007_supervise_step` dan live CHECK memasukkan SUPERVISE; ORM `AgentTrace` CHECK masih tidak memasukkannya. Fresh schema via ORM bukan ekuivalen migration schema.

## 3. Sprint 4 Objective

Menyelesaikan demo interaktif yang memperlihatkan dua kejadian bisnis tambahan dengan keputusan grounded, human approval, koreksi yang transparan, dan pengukuran hasil yang jujur. Existing Event 1 dan empat demo tambahan menjadi regression coverage, bukan fitur baru.

Target akhir mengikuti dokumen: Event 1/2/3 dapat dioperasikan dari UI, seluruh KPI memiliki kontrak dan provenance yang disetujui, approval menampilkan konsekuensi nyata, tiga putaran rehearsal berurutan berhasil, dan video fallback dapat diputar.

Jika Owner belum memutuskan sumber facts KPI atau prerequisite agent/security, target penuh tersebut belum dapat dinyatakan terpenuhi. Dashboard dengan kartu unavailable tidak otomatis memenuhi “7 KPI terhitung”.

## 4. Business / Competition Value

- Event 2 mengarahkan harga janggal ke review berbukti, tanpa menuduh fraud dan tanpa membuat PO otomatis.
- Event 3 menunjukkan bahwa sumber murah sekalipun gugur ketika safety FAIL; kebutuhan Jakarta dapat dipenuhi dari Bogor hanya jika tool deterministik menyatakan eligible.
- Ringkasan approval membantu kepala SPPG dan nutritionist memahami jumlah, tujuan, evidence, biaya, risiko, dan kebutuhan persetujuan sebelum bertindak.
- KPI membedakan keberhasilan keputusan dari keberhasilan pengiriman/menu. Ini mencegah angka dampak kompetisi yang tidak memiliki data.
- Trace, provenance Mock SAP, hasil provider sebenarnya, dan video fallback membuat demo dapat dijelaskan tanpa klaim AWS/SAP yang berlebihan.

## 5. Scope

### In Scope

- S4-00: preflight dan keputusan atas prerequisite yang benar-benar dipakai Sprint 4.
- S4-01: menyambungkan kemampuan price anomaly yang ada menjadi Event 2 interaktif, tersimpan, terverifikasi, dan dapat direview.
- S4-02: menyambungkan safety evaluation dan balancing yang ada menjadi Event 3, mempertahankan riwayat keputusan lama dan menghalangi penggunaan kandidat unsafe.
- S4-03: tujuh KPI sesuai `docs/Skill.md:64-74`, hanya sesudah definisi dan sources disetujui. Tidak mengganti definisi agar cocok dengan tabel yang tersedia.
- S4-04: ringkasan approval lengkap berbasis backend dan polish yang diperlukan bagi alur di atas.
- S4-05: rehearsal Event 1/2/3 tiga putaran berurutan serta regression demo tambahan.
- S4-06: video fallback, runbook, dan evidence acceptance Sprint 4.

### Out of Scope

Final S0→S4 audit; penutupan seluruh historical debt; perubahan formula; real SAP; auto-procurement; ML/retraining; full agent tambahan; role baru; redesign dashboard/peta; admin/settings; notification platform; framework orkestrasi baru; broad refactor; dependency installation pada fase planning; deployment AWS dan Identity tanpa approval stretch tersendiri.

ID `S4-07` dan `S4-08` tetap milik stretch Identity/App Runner pada TODO. Tidak dialihkan ke pekerjaan lain. Keduanya tidak dieksekusi dalam baseline plan ini.

## 6. Dependency Matrix

Klasifikasi PASS / available di bawah berarti tersedia untuk reuse pada tingkat source/bukti yang disebut, bukan fresh full certification.

| Dependency | Classification | Evidence | Disposition untuk S4 |
|---|---|---|---|
| Supply/demand dan deterministic engine | PASS / available | core, recommendation_service, domain tests | Reuse; regression S4-00 |
| JWT dan tiga role | PASS / available | auth.py, live 401 pada tiga probe | Jangan membangun ulang auth |
| Semua entry point S4 terlindungi + scope lokasi | BLOCKED | decisions/repropose tanpa guard; role guard tanpa scope | Owner menyetujui prerequisite remediation, lalu fresh probes |
| Independent verifier ke approval | BLOCKED | tombol mengirim literal consistent; API menerima verdict dari caller | Tidak boleh dipakai sebagai bukti independent verification |
| Runtime/Gateway/Memory/Observability aplikasi | BLOCKED | stub lokal, SDK container, tidak ada composed proof | Verifikasi resource terpisah; Owner menentukan prerequisite integrasi, bukan local-mock substitution |
| Event 1 dari UI melalui Supervisor asli | PARTIAL | service tersedia; OpsConsole memakai analyze deterministik | Buktikan composed path sebelum rehearsal |
| Price/freshness/safety/logistics tools | PASS / available | API/core dan tests existing | Reuse tanpa perubahan thresholds |
| Decision persistence, expiry, rejection loop | PARTIAL | schema 008 + source tersedia; expiry guard tidak setara receiving/outcome | Gunakan dengan safety/action prerequisite |
| Complete approval context | PARTIAL | modal minimum; evidence/verdict context belum lengkap | S4-04 |
| Tujuh KPI dan business facts | OWNER DECISION REQUIRED | Skill §4 vs schema/as-built | O-KPI di §18; tidak membuat fake denominator |
| Live seed_key drift + SUPERVISE CHECK | OWNER DECISION REQUIRED | DB metadata vs migrations/ORM | Catat disposition sebelum schema-backed task |
| Receiving/ML/full reliability learning | NOT REQUIRED | Tidak ditetapkan sebagai goal S4 | Menjadi dependency hanya jika Owner memilih full KPI facts yang memerlukannya |
| Semua frontier Bedrock models | NOT REQUIRED | Capability acceptance cukup satu model tersedia + fallback | Sales-gated bukan blocker default |
| Identity/App Runner/real SAP | NOT REQUIRED | Roadmap stretch/S5 on-demand | Approval terpisah |
| Test host/agent tooling | PARTIAL | container mengabaikan host-only modules | S4-00 harus melaporkan hasil host, jangan gabungkan tanpa dedupe |

## 7. Completed vs Remaining Capability Matrix

| Capability | Sprint 0–3 Status | Sprint 4 Needed? | Reason |
|---|---|---|---|
| Supply monitoring | Tersedia pada source dan bukti S1 | Reuse | Facts Event 1/3 |
| Demand monitoring | Tersedia | Reuse | Kebutuhan tujuan, bukan menu fulfilment |
| Freshness | Engine/API tersedia | Regression | Band terkunci |
| Safety | Engine/API tersedia | Integrasi Event 3 | Persist evaluation bukan revalidation semua action |
| Price anomaly | Core deviation dan analyze flags tersedia | Integrasi Event 2 | Flag belum sama dengan interactive event lifecycle |
| Logistics | Engine/API tersedia | Reuse | Kelayakan alternatif Bogor |
| Evidence fusion | Snapshot tool tersedia | Persistence/provenance yang diperlukan | Snapshot bukan otomatis row decision_evidence |
| Cost | SDC tersedia | Reuse, ruling rounding | Tidak mengganti Opsi A |
| Balancing | Ranking/recommendation tersedia | Reuse | Jangan membuat optimizer kedua |
| Supervisor | Service/narration tersedia; composed Runtime path belum terbukti | Hard prerequisite | Demo agentic tidak boleh berupa label UI semata |
| Verifier | REST client/resilience tersedia | Reuse setelah action trust boundary selesai | Caller verdict bukan audit independen |
| Forecast | Provider/fallback tersedia | Reuse | SAP label hanya saat benar-benar berhasil |
| Resilience | Shared chain tersedia | Regression | Tidak ada fallback kedua |
| AgentCore Runtime | Invoke historis genuine; caller aplikasi stub | Hard prerequisite | PONG tidak membuktikan event routing |
| AgentCore Gateway | READY historis; backend OpenAPI tersedia | Composed tool-call proof | Listing bukan tool execution |
| AgentCore Memory | ACTIVE historis; adapter read/write unavailable | Hard prerequisite untuk claim memory | Tidak mengklaim ID presence sebagai read/write |
| Observability | Local recorder + unavailable external sink | Hard prerequisite untuk claim AWS trace | DB timeline berbeda dari AgentCore trace |
| Authentication | JWT DB-backed tersedia | Reuse | Guard gap bukan alasan rewrite |
| RBAC | Legacy subset ditutup; gaps decision/demo/location | Prerequisite | Monitor tetap read-only |
| Approval | OR/AND matrix dan rows tersedia | Summary + boundary proof | Dua role berbeda, bukan dua klik satu role |
| Action execution | Mock PO write tersedia | Regression + safety/snapshot prerequisite | No auto-execute |
| Mock SAP | Tabel/provider/contracts tersedia | Reuse | Tetap MOCK, bukan SAP nyata |
| Trace | AgentTrace persistence tersedia | Actual event/ACT/provenance | Fixture timeline tidak live |
| Frontend | Login/feed/detail inline/console/components tersedia | Extension sempit | Tidak rebuild shell |
| Rejection loop | Reason, repropose, chain tersedia | Regression | Child tidak otomatis mendapat approval |
| LEARN | Trace alasan penolakan; child menyalin substansi parent | Tidak diperluas default | Bukan ML atau outcome learning |
| Demo scenarios | Empat case seeder dan Event 1 service tersedia | Preserve + extend Event 2/3 | Scenario label bukan bukti interactive workflow |
| KPI | Definisi dokumen tersedia; implementasi/facts belum lengkap | S4-03, gated | Tujuh nilai tidak boleh diciptakan |
| Event scenarios | Event 2/3 tools tersedia, end-to-end belum terbukti | S4-01/02 | Goal resmi Sprint 4 |
| Remaining project acceptance criteria | Rehearsal/video/full approval summary belum terbukti | S4-04/05/06 | Dibuktikan sesudah implementasi, bukan final cross-sprint audit |

## 8. S4-00 Preflight

- **Objective:** membekukan baseline eksekusi dan memperoleh keputusan atas blocker sebelum production-code task.
- **Why:** source/live sekarang menunjukkan dependency gaps yang tidak tertutup oleh angka historis.
- **Scope:** hanya kontrak dan jalur yang dipakai Event 1/2/3, KPI, approval, rehearsal.
- **Technical changes:** tidak ada sebelum approval. Jika ditemukan blocker, buat brief prerequisite terpisah dengan failing-test target, diff scope, acceptance, dan Owner approval. S4-00 bukan izin terselubung untuk memperbaiki semua audit debt.
- **Files/modules:** dokumen ini; setelah approval `docs/verification/sprint-4.md` baru; `TODO.md` hanya diperbarui saat eksekusi benar-benar dimulai. Read source yang disebut §2/18.
- **Database:** metadata read-only dahulu; full tests memerlukan DB test terisolasi yang disetujui, bukan otomatis DB demo. Rekonsiliasi columns, types, nullability, defaults, FK/CHECK/indexes dan head host/container.
- **API:** inventaris per method, bukan per path saja. Periksa auth pada create/detail/repropose/demo dan scoped read/action. Jangan menjalankan mutation probe pada DB utama saat belum mendapat izin.
- **Frontend:** collect lalu test/tsc/lint/build pada environment eksekusi; confirm app bundle aktual. Audit state dan API seam, bukan hanya SSR snapshot.
- **Agent/provider:** presence boolean saja untuk config; fresh control-plane read dan genuine application invocation setelah approval. Catat actual provider/model, fallback attempts, tool calls, Memory round-trip dan Observability correlation.
- **Security:** tidak mencetak `.env`, JWT, password, connection string, atau raw provider payload. Gunakan akun/records test berizin dan cleanup berbasis ID milik run.
- **Tests:** canonical commands §15; host-only collection; historical comparison; actual source→API→approval→PO seam. Default pytest menghapus model env, jadi tidak live provider proof.
- **Acceptance criteria:** semua prerequisite memiliki PASS atau ruling eksplisit; full baseline fresh tercatat; schema disposition disetujui; Event 1 composed acceptance valid; Owner menyetujui kontrak Event 2/3/KPI/API sebelum downstream.
- **Dependencies:** akses repo/container; DB test; AWS credentials yang sudah ada tanpa perubahan; Owner ruling §18.
- **Risks:** false green karena collection, fixture, host exclusion, atau SDK berbeda.
- **STOP conditions:** auth/action bypass, missing real agent integration yang diperlukan, unresolved numeric/schema contract, KPI source tidak disetujui, failed mandatory baseline. Tidak lanjut S4-01 hanya karena task lain tidak menyentuh blocker.

Checklist eksekusi S4-00:

- [ ] Catat `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, `git log -5 --oneline`; jika HEAD berubah, revalidasi referensi plan.
- [ ] Jalankan `docker compose ps`, Alembic current/heads; bandingkan migration files host/container dan DB metadata.
- [ ] Tentukan DB test dan cleanup. Full pytest menulis user/decision/approval, sehingga read-only planning tidak cukup untuk certification.
- [ ] Jalankan canonical backend/frontend gates §15, laporkan collected/passed/failed/skipped/ignored terpisah.
- [ ] Bandingkan OpenAPI artifacts, method-level auth, payload dan source code. Semua protected unauth requests harus 401 sebelum lookup.
- [ ] Periksa tiga role dan location assignment tanpa mencetak PII; login fixtures nyata, monitor mutation 403, foreign-location denied.
- [ ] Bedakan persisted demo fixture dari run aktual; inspeksi ulang TTL tanpa memperpanjang keputusan historis diam-diam.
- [ ] Jalankan fresh capability proof AgentCore/Supervisor/tools/Memory/Observability; fallback tidak dihitung sebagai keberhasilan provider primary.
- [ ] Putuskan O-SEC, O-AI, O-KPI, O-DATA, O-EVENT, O-NUM, O-PO pada §18. Prerequisite fixes memerlukan approval scope tersendiri.
- [ ] Catat verdict S4-00. Hanya PASS membuka urutan task berikut.

## 9. Sprint 4 Tasks

Semua langkah berikut adalah instruksi untuk fase setelah approval. Tidak ada langkah yang dijalankan saat dokumen ini dibuat. Untuk setiap perubahan kode: satu perilaku → failing test yang benar → implementasi minimum → focused PASS → regression → evidence. Commit tetap hanya jika Owner mengizinkan, bukan otomatis karena plan menyebut TDD.

### S4-01

- **Objective:** Event 2 price anomaly dapat dijalankan dari OpsConsole dan menghasilkan keputusan review yang grounded.
- **Why:** `Roadmap.md:86`; tool harga sudah ada, tetapi interactive event lifecycle belum tersedia sebagai composed proof.
- **Scope:** pilih supplier quote aktual, bandingkan PIHPS reference pada lokasi/komoditas yang sesuai, kumpulkan evidence, Verifier, persist price_anomaly decision/trace, tampilkan review queue.
- **Technical changes:** service event tipis menggunakan core price dan shared provider chain; backend membaca quote/reference, bukan mempercayai angka dari browser. Tidak membuat price engine baru. Jangan otomatis memanggil execute untuk review-only anomaly.
- **Files/modules:** reuse `backend/app/core/price.py`, `backend/app/api/price.py`, `backend/app/api/evidence.py`, `backend/app/services/recommendation_service.py`, provider clients; proposed new `backend/app/services/event2_service.py`, `backend/app/api/events.py`, `backend/tests/test_event2_flow.py`; modify `backend/app/main.py`, `frontend/components/OpsConsole.tsx`, `frontend/lib/api.ts`; proposed `frontend/tests/event-scenarios.test.tsx`.
- **Database:** existing PriceSignal/Decision/DecisionEvidence/AgentTrace. Simpan sumber quote/reference ID dan recorded_at sebagai evidence dengan schema payload disetujui §10. Tidak ada migration default.
- **API:** proposed `POST /events/price-anomaly`, §11. Existing `/price/deviation` tetap kompatibel.
- **Frontend:** approver dapat run; monitor hanya membaca hasil. Loading, reference missing, non-anomalous, unavailable verifier, pending review, retry seperti §13.
- **Agent/provider:** Supervisor satu-satunya full agent; Verifier independent REST; actual calls saja menjadi trace. Forecast tidak dipanggil hanya untuk menambah langkah demo.
- **Security:** profile §14 berlaku; supplier quote tidak dianggap instruksi; validasi FK/scope dan positif/finite; approval tidak boleh menurunkan FLAGGED ke CONSISTENT dari browser.
- **Tests:** price threshold existing termasuk 5%/15%; source pairing; missing reference/quote; duplicate retry; 401/403/location; injection dalam supplier/evidence text; actual service→decision→feed; zero PO sebelum/selesai review-only sesuai ruling.
- **Acceptance criteria:** persisted decision_type `price_anomaly`; hasil sama dengan deterministic tool; dua source records dapat ditelusuri; wording `Procurement price deviation detected — review required`; no fraud accusation; approval policy sesuai verifier; tidak ada auto-PO.
- **Dependencies:** S4-00 PASS; O-EVENT Event 2 semantics; O-SEC/O-AI/O-PO jika action menyentuh procurement.
- **Risks:** supplier-janggal fixture disalahartikan sebagai live Event 2; harga lintas lokasi/period dicampur.
- **STOP conditions:** reference tidak tersedia tidak boleh diganti angka tetap; keputusan review-only dipaksa menjadi PO; unknown source atau provider hasilnya tidak tervalidasi.

Langkah:
- [ ] RED satu quote/reference pair menghasilkan anomaly dan provenance yang diharapkan.
- [ ] GREEN service dan API minimum menggunakan core existing.
- [ ] RED→GREEN non-anomaly/missing data/role/scope/retry tanpa duplicate decision.
- [ ] RED→GREEN UI memakai response backend, bukan fixture activity.
- [ ] E2E review melalui dua role bila FLAGGED/UNAVAILABLE; DB readback dan no-PO assertion; dokumentasikan evidence.

### S4-02

- **Objective:** Event 3 temperature excursion mengecualikan batch Cianjur, menghitung ulang alternatif Bogor, dan mempertahankan keputusan lama untuk audit.
- **Why:** `Roadmap.md:87`, `Architecture.md` alur Event 3.
- **Scope:** evaluator memakai persisted temperature log. Pilihan input adalah batch fixture sensor yang jelas simulasi, bukan browser menyuplai safety_status. Tidak menambah generic public sensor ingestion platform.
- **Technical changes:** panggil existing safety/freshness/constraints/balancing; persist hasil actual evaluation; rekomendasi hanya eligible. Old pending decision yang terkait batch FAIL harus tidak bisa approve/execute. Gunakan pemeriksaan server-side hubungan decision→batch dan facts terkini sesuai ruling; jangan mengubah expiry agar seolah safety aman.
- **Files/modules:** reuse `backend/app/api/safety.py`, `backend/app/core/safety.py`, `backend/app/core/constraints.py`, `backend/app/services/recommendation_service.py`; proposed `backend/app/services/event3_service.py`, `backend/tests/test_event3_flow.py`; proposed shared `backend/app/api/events.py`; affected `backend/app/api/actions.py`, `backend/app/api/decisions.py`, `frontend/components/OpsConsole.tsx`, `DecisionChain.tsx`, `DecisionActions.tsx`, `frontend/tests/event-scenarios.test.tsx` setelah boundary ruling.
- **Database:** Batch safety update dan Decision/Evidence/Trace baru; relationship ke old decision perlu O-EVENT karena `supersedes_id` existing didesain untuk rejected parent. Tidak merombak old status/rejection reason untuk menyamar sebagai rejection manusia. Tidak ada migration sampai ruling.
- **API:** proposed `POST /events/safety-disruption`, §11; existing `/safety/evaluate` dipertahankan.
- **Frontend:** tampilkan before/after, batch FAIL dan alasan, Bogor eligible, biaya dari backend, hubungan ke decision lama; kasus tanpa alternatif adalah blocked, bukan empty success.
- **Agent/provider:** tool safety adalah otoritas. Supervisor/Verifier tidak dapat mengubah FAIL; persist provider attempts dan actual steps. Fallback tidak membuka candidate yang sudah excluded.
- **Security:** profile §14; target location berasal dari user scope; backend memeriksa kewenangan cross-regional source evaluation sesuai ruling; invalid/foreign batch tidak dimutasi; recheck sebelum action/PO.
- **Tests:** sustained excursion vs threshold; freshness 0.60/0.85 boundaries; FAIL score nol dan exclusion sebelum SDC; safe Bogor alternative fixture; no-safe-alternative; stale approval; rejection/expiry; duplicate/concurrent event; no PO untuk old unsafe decision; existing rejection loop regression.
- **Acceptance criteria:** persisted Cianjur batch FAIL; tidak pernah recommended; alternatif Bogor dipilih karena facts/rank, bukan hardcoded winner; old log tidak hilang; approve/execute old unsafe decision ditolak; revised decision harus verifikasi dan approval baru; Mock PO hanya untuk snapshot aman yang disetujui.
- **Dependencies:** S4-00 PASS, O-EVENT linkage/source authority, O-SEC safety/action integrity, O-PO snapshot.
- **Risks:** seed yang sudah basi, snapshot decision tanpa batch link, inherited approval, dua action request bersamaan.
- **STOP conditions:** hubungan batch tidak dapat dibuktikan; safe alternative tidak ada; diminta menurunkan FAIL; contract supersedes tidak diputuskan. No alternative adalah hasil bisnis valid tetapi fixture demo Bogor harus diperbaiki secara sah sebelum rehearsal PASS.

Langkah:
- [ ] RED persisted sensor facts mengubah eligibility tanpa safety override input.
- [ ] GREEN reuse evaluator dan ranking; assert excluded batch tidak masuk cost path.
- [ ] RED→GREEN stale decision/action guard dan lineage yang sudah disetujui.
- [ ] RED→GREEN UI correction timeline dan no-safe-alternative state.
- [ ] Jalankan composed revised decision→human approval→Mock PO; buktikan old decision tetap tersimpan dan tidak executable.

### S4-03

- **Objective:** KPI Dashboard menampilkan tujuh KPI dengan formula, periode, coverage, source, dan unavailable state yang benar.
- **Why:** `Roadmap.md:88`, `Skill.md:64-74`, `design.md:82-86`.
- **Scope:** aggregation deterministik dari records aplikasi; backend menjadi sumber angka; historical synthetic business data tetap berlabel simulasi.
- **Technical changes:** proposed pure KPI computation + query service, GET API, cards. Tidak ada LLM arithmetic. Implementasi penuh diblokir O-KPI; tabel §10 adalah mapping acceptance, bukan izin membuat facts baru.
- **Files/modules:** proposed `backend/app/core/kpi.py`, `backend/app/services/kpi_service.py`, `backend/app/api/kpi.py`, `backend/tests/test_kpi.py`, `backend/tests/test_kpi_api.py`, `frontend/components/KPIDashboard.tsx`, `frontend/components/KPICard.tsx`, `frontend/tests/kpi.test.tsx`; modify `backend/app/main.py`, `frontend/lib/api.ts`, `frontend/app/page.tsx`; schema/model/migration hanya setelah schema annex Owner disetujui.
- **Database:** default no migration, query existing records. Full Meal Continuity/Food Loss membutuhkan kontrak facts tambahan; `kpi_snapshots` sendiri tidak menyelesaikannya. Nomor migration dan schema tidak boleh dipilih sebelum O-KPI/O-DATA.
- **API:** proposed `GET /kpi`, §11; real aggregate atau null dengan reason, bukan dummy zero.
- **Frontend:** tujuh card, period/scope/source/coverage; trend hanya bila kedua periode comparable; monitor cross-location, SPPG own location.
- **Agent/provider:** tidak memanggil provider untuk hitung atau mengisi missing data. Nilai KPI bukan output LLM.
- **Security:** profile §14; filter scope sebelum aggregate; no PII/raw evidence; range valid dan bounded sesuai kontrak §11; arbitrary SQL/filter tidak diterima.
- **Tests:** setiap formula, zero denominator, no data, null missing timestamp, dedupe repeated detection, `[start,end)`, foreign scope, prior-period comparison, rounding approved, source mixing, malformed date/UUID, no fake zero.
- **Acceptance criteria:** ketujuh definisi §10 terpenuhi terhadap owned test records dengan expected components; API/UI sama; DB readback membuktikan provenance. Jika Owner mengizinkan partial dashboard, status task tetap PARTIAL terhadap requirement awal sampai scope resmi dirulingkan.
- **Dependencies:** S4-00, O-KPI, O-DATA, O-NUM, action timestamps/evidence producers dari prerequisite/S4-01/02.
- **Risks:** PO dieksekusi dianggap menu terpenuhi; freshness decay dianggap disposal; repeated detect menggandakan denominator; approval timestamp tidak punya makna transisi.
- **STOP conditions:** belum ada source/menu definition/period/denominator yang disetujui; proxy metric mengganti original KPI; tujuh card diklaim tujuh KPI lengkap meski beberapa unavailable.

Langkah:
- [ ] Dapatkan signed metric worksheet §10; bila belum lengkap, STOP sebelum schema/query implementation.
- [ ] RED→GREEN satu KPI per vertical slice menggunakan owned records dan oracle deterministik terpisah.
- [ ] RED→GREEN period/scope/provenance/null semantics pada API.
- [ ] RED→GREEN card/state/trend tanpa frontend arithmetic.
- [ ] Compare SQL inputs→backend aggregate→UI untuk semua KPI; catat yang blocked, jangan mengubah denominator diam-diam.

### S4-04

- **Objective:** approval menampilkan ringkasan lengkap, immutable decision identity, dan action readiness aktual sebelum pengguna menyetujui.
- **Why:** `Roadmap.md:89`, `design.md:77-80`; modal saat ini belum menampilkan evidence lengkap.
- **Scope:** extension modal/feed/detail yang ada, tanpa redesign. Perbedaan approve dan execute tetap jelas.
- **Technical changes:** read model summary berasal dari Decision/Evidence/Approval dan persisted verifier result, dihitung server-side dengan approval matrix existing. UI tidak mengirim verdict sebagai hasil audit. Refresh summary sebelum confirm; server tetap revalidasi setelah race/stale change.
- **Files/modules:** modify `backend/app/api/decisions.py`, `backend/app/api/actions.py` setelah prerequisite approval; proposed `backend/app/services/approval_summary.py`, `backend/tests/test_approval_summary.py`; modify `frontend/components/ApprovalModal.tsx`, `DecisionActions.tsx`, `RecommendationCard.tsx`, `frontend/lib/api.ts`, `frontend/tests/approval-modal.test.tsx`.
- **Database:** read existing records dan canonical action snapshot. Jangan membuat shadow approvals; missing immutable supplier/batch/price linkage adalah blocker O-PO, bukan diisi dari default supplier saat render.
- **API:** proposed `GET /decisions/{decision_id}/approval-summary`, §11. Existing approve/execute payload tidak berubah tanpa contract change yang eksplisit.
- **Frontend:** lokasi asal/tujuan, komoditas, supplier, quantity, cost breakdown, safety/freshness, evidence source/time, verifier outcome/reason, current approval/missing roles, expiry, action target MOCK, decision ID/version. Missing fields tampil unavailable dan actionable controls disabled sesuai server readiness.
- **Agent/provider:** tidak memanggil model ketika membuka modal. Hanya menampilkan hasil tersimpan dengan actual provenance.
- **Security:** profile §14; authorization pada summary dan mutation; sanitized evidence; no raw user email; no hardcoded CONSISTENT; HTML text escaped; backend mencegah unsafe/expired/unverified action.
- **Tests:** summary parity vs execution snapshot; one OR vs dual AND; same role twice tidak memenuhi dual; unavailable; empty evidence; expiry saat modal terbuka; approve/reject conflict; duplicate click; monitor/foreign location; keyboard focus/Escape/return focus; refresh after action.
- **Acceptance criteria:** pengguna melihat apa yang disetujui dan apa yang belum; confirm bukan execute; actual provider verdict tidak dapat dipalsukan oleh client; missing approval mencegah execute; verified Mock PO matches approved supplier/material/quantity/purchase component sesuai ruling.
- **Dependencies:** S4-00, O-SEC/O-PO/O-KPI approval time, S4-01/02 evidence contract.
- **Risks:** summary benar tetapi execute memilih supplier/harga berbeda; stale modal; fixtures SSR tidak mengetes klik.
- **STOP conditions:** belum ada trustworthy verifier/decision snapshot; summary memakai default palsu; action identity berbeda; mandatory context tidak tersedia.

Langkah:
- [ ] RED summary berasal dari producer nyata dan cocok dengan target action, bukan fixture hand-built pada seam.
- [ ] GREEN read model/API memakai matrix existing.
- [ ] RED→GREEN typed UI/state, keyboard dan double-submit behavior.
- [ ] RED→GREEN expiry/unsafe/stale race rejection di backend.
- [ ] E2E approve OR, approve AND, reject/repropose, execute/readback; no fake verification button.

### S4-05

- **Objective:** rehearsal Event 1/2/3 berhasil tiga putaran berturut-turut dari UI dengan bukti yang dapat diputar ulang.
- **Why:** `Roadmap.md:95-96`, `workflows.md` §6.
- **Scope:** login tiga role, facts→event→trace→review→action yang relevan→KPI; regression empat demo existing. Ini Sprint 4 acceptance, bukan final cross-sprint audit.
- **Technical changes:** test/runbook saja sebagai default. Bug produksi yang muncul harus dicatat, direproduksi RED, lalu diperbaiki hanya dalam scope yang sudah disetujui; rerun seluruh putaran setelah fix relevan.
- **Files/modules:** proposed `docs/verification/sprint-4.md`, `docs/verification/sprint-4-rehearsal.md`; extend `backend/tests/test_event1_e2e_acceptance.py`, proposed Event2/3 tests dan frontend scenario tests. Browser automation menggunakan tooling berizin yang tersedia; jangan menganggap Playwright terinstal di package.json.
- **Database:** gunakan owned scenario records dengan waktu relatif; restore hanya records milik run; jangan force-reset semua demo atau delete approvals historis tanpa izin.
- **API:** tidak ada API bisnis baru; exercise kontrak approved §11 dan existing actions.
- **Frontend:** real browser clicking; monitor no mutating controls; refresh/resume; offline/error state; keyboard usability.
- **Agent/provider:** genuine required capabilities; deterministic failure injection dipisah dari live acceptance; observed successful provider/model dicatat.
- **Security:** profile §14; video/log redaction; demo accounts tidak mendapat privilege tambahan; test global monitor tidak memutasi.
- **Tests:** canonical gate §17; matrix §16; denied action assertions lewat HTTP dan DB no-side-effect readback.
- **Acceptance criteria:** setiap putaran menjalankan Event 1 lalu 2 lalu 3 tanpa kegagalan mandatory; tiga putaran consecutive setelah perubahan kode terakhir; IDs/times/provider outcomes/trace/PO-or-no-PO/KPI captured; tidak ada manual DB patch agar lolos.
- **Dependencies:** S4-01..04 accepted, S4-00 capabilities tetap valid, fixtures dan recorder siap.
- **Risks:** latency external, wall-clock expiry, contaminated seed, dev server stale.
- **STOP conditions:** salah satu mandatory scenario gagal, unavailable external capability wajib, data/secret bocor, false live trace. Count consecutive diulang setelah remediasi.

Langkah:
- [ ] Freeze build/HEAD dan checklist, jalankan failure injection terisolasi.
- [ ] Putaran 1: Event 1→2→3, simpan evidence.
- [ ] Putaran 2: reset owned fixtures secara sah lalu ulang seluruh alur.
- [ ] Putaran 3: ulang tanpa patch/manual bypass; reviewer mengecek DB/trace/UI.
- [ ] Regression rejection loop, shortage darurat, supplier janggal, gangguan logistik; catat label fixture/live dengan benar.

### S4-06

- **Objective:** menghasilkan video fallback yang menunjukkan alur yang benar-benar berjalan dan paket evidence Sprint 4.
- **Why:** `Roadmap.md:91,95-96`; mitigasi jaringan saat kompetisi.
- **Scope:** rekaman hasil build yang lolos rehearsal; runbook presentasi dan batas mock/live; tidak membuat animasi pura-pura sebagai bukti aplikasi.
- **Technical changes:** tidak ada default production change. Video direkam dari UI aktual; jika ada edit/cut, jangan menyamarkan kegagalan sebagai continuous successful run.
- **Files/modules:** proposed `docs/verification/sprint-4-video.md`, media output di lokasi yang Owner setujui; append evidence S4 pada `docs/verification/sprint-4.md`, update `TODO.md` setelah pelaksanaan dan `README.md` bila perlu. Tidak menulis ulang laporan S3.
- **Database:** tidak ada schema; recording dapat menghasilkan records demo yang dimiliki run, sesuai approval S4-05.
- **API:** memakai existing accepted flows.
- **Frontend:** bukan desain baru; tampilkan source MOCK, decision lineage, safety refusal, approval roles, actual trace, KPI coverage.
- **Agent/provider:** tidak melakukan dubbing yang mengklaim provider sukses bila fallback yang bekerja; video diberi tanggal/build/HEAD.
- **Security:** profile §14; tidak merekam `.env`, token, AWS console secrets, PII, atau password entry; crop/redact tanpa mengubah klaim hasil.
- **Tests:** file dapat dibuka, audio/video sinkron bila audio ada, durasi/resolusi/container terbaca oleh media probe yang tersedia, playback awal/tengah/akhir dan rehearsal narrative review.
- **Acceptance criteria:** video nyata tersedia pada path/handle terverifikasi; playback berhasil; menggambarkan Event 1/2/3 dan approval yang relevan; rekaman sesuai accepted HEAD; docs menyatakan tanggal dan batas data simulasi. Sprint tetap menunggu Roy untuk penandaan DONE.
- **Dependencies:** S4-05 PASS, kemampuan screen recording dan persetujuan lokasi media.
- **Risks:** video stale setelah fix, exposure secrets, file rusak, claim mock/live keliru.
- **STOP conditions:** tidak dapat merekam/playback, build berubah, mandatory flow belum lolos; jangan mengganti dengan fabricated footage.

Langkah:
- [ ] Setujui outline, lokasi file, dan daftar layar yang aman.
- [ ] Rekam genuine UI flow pada build accepted.
- [ ] Probe media dan playback; cocokkan IDs/timestamps dengan rehearsal evidence.
- [ ] Append walkthrough achievement, manual actions, testing; serahkan artefak, bukan sekadar klaim video tersedia.

## 10. Data / Database Plan

### Kontrak terkunci yang dipertahankan

PostgreSQL sumber kebenaran. Safety FAIL → eligibility 0 → score 0 → tidak direkomendasikan. Freshness ≥0.85 pass, 0.60–<0.85 needs_verification, <0.60 fail. Candidate Score adalah perkalian enam faktor 0–1 sesuai permintaan Owner. Expected Loss = 0.2 × (1 − freshness) × Purchase Cost; Freshness Risk Penalty = 0.50 × Purchase Cost bila freshness <0.60. SDC bukan dihitung LLM.

Source `safe_delivered_cost.py` menjumlahkan komponen, sementara format bullet pada permintaan Owner tidak menyatakan operator dengan tegas. O-NUM memerlukan konfirmasi additive, bukan perubahan diam-diam. Comment source mengklaim HALF_UP per komponen, implementasi hanya mengkuantisasi expected_loss; batas rounding juga masuk ruling.

### Worksheet tujuh KPI

| KPI | Sumber/definisi resmi | Data tersedia dan gap | Kontrak yang harus disetujui | Acceptance khusus |
|---|---|---|---|---|
| Meal Continuity Rate | menu aman terpenuhi / menu direncanakan ×100% | Demand kg dan PO tidak merepresentasikan menu/fulfilment | Identitas rencana menu, periode, jumlah menu, safe fulfilment evidence, aturan partial/cancelled | Contoh menu planned/fulfilled unsafe/fulfilled safe; tidak menghitung unsafe atau PO-only |
| Avoidable Food Loss | kg atau Rp batch dibuang karena tidak teralokasi padahal freshness lolos saat itu | Batch saat ini bukan disposal event; tidak ada discarded_at/reason/quantity/freshness-at-disposal | Pilih kg, atau valuation Rp dengan price source; event disposal, unallocated reason, freshness snapshot, correction semantics | Hanya qualifying actual disposal; expiry saja tidak menambah loss |
| Regional Imbalance Resolution Rate | detected surplus/shortage cases selesai executed dalam window | Decision/trace tersedia; detection tanpa decision dan dedupe case belum lengkap | Case identity, denominator seluruh detection, partial fulfilment, window execution, repeat/repropose dedupe | Deteksi berulang tidak memperbesar denominator; unresolved tetap dihitung |
| Safe Delivered Cost | mean SDC executed dalam periode | Decision SDC/status ada; execution time bukan persisted column di Decision | Waktu ACT committed sebagai execution anchor atau field baru; exclude missing timestamp vs coverage | Tidak filter created_at sebagai pengganti executed time; null source bukan zero |
| Procurement Price Deviation | absolute supplier/reference difference / reference ×100% | PriceSignal source/supplier_id/recorded_at tersedia | Pair reference per location/commodity/time, aggregate card mean vs selected quote, missing/ref=0, prior period | Core price reuse; source IDs dan timestamps diketahui; tidak gabung beda lokasi |
| Decision Time | mean first DETECT→last ACT per decision | Trace table ada; action execute belum menulis ACT; sebagian fixture backdated | Actual committed ACT, failed attempts excluded, incomplete decisions/negative durations | Human approval wait termasuk jika definisi DETECT→ACT dipertahankan; tidak menjumlah duration_ms sebagai proxy |
| Evidence Completeness | ≥2 consistent evidence sebelum status approved | Evidence table ada; producer persistence terbatas; action approve tidak mengubah status approved | Titik approval-complete OR/AND, immutable cutoff, distinct evidence identity, denominator, late evidence | Bukti sesudah cutoff tidak dihitung; dua salinan bukti sama bukan dua sumber |

Usulan teknis untuk review: periode `[start,end)` ber-offset timezone; UTC di storage; display Asia/Jakarta; zero denominator = null + `no_data`; missing facts = null + `unavailable`; coverage tidak disembunyikan; snapshot sintetis tetap berlabel. Unit loss dan aggregate price/denominator **belum diputuskan**, tidak boleh dipilih oleh executor.

### Reuse dan migration gate

Dua detail numerik/instrumentasi harus masuk tests S4-03. `core/price.py:35-49` menghasilkan signed deviation, sedangkan KPI resmi memakai magnitude absolut; gunakan nilai absolut pada aggregate KPI tanpa mengubah signed contract endpoint existing. `trace_persistence.py:32-52` memberi waktu persistence ditambah offset mikrodetik untuk urutan, bukan waktu kejadian tool sebenarnya. Jangan memakai rentang tersebut sebagai Decision Time. Capture actual step start/end di producer, pertahankan urutan, dan simpan ACT hanya setelah action committed; migration bukan otomatis diperlukan karena kolom trace sudah ada.

Default S4-01/02/04 memakai tabel existing. Proposed evidence payload JSONB berisi `source_record_id`, `source_kind`, `recorded_at`, `observed_at`, nilai relevan, unit, dan flag `synthetic`; type evidence mengikuti CHECK existing. Proposed trace summary menyertakan `session_id`, `event_type`, `operation_key`, `decision_id`, actor ID/role, actual provider/model/attempts; payload allowlisted, tidak menaruh rahasia. Names ini proposal kontrak baru, bukan klaim sudah tersedia.

Tidak ada migration yang otomatis disahkan plan ini. Bila O-KPI memilih full new facts atau O-EVENT/O-PO memerlukan struktur baru, **STOP**, lalu tulis schema annex untuk approval sebelum coding. Annex wajib menentukan exact table/column/type/nullability/default/FK/CHECK/index, sumber record dan actor, idempotency/uniqueness, backward compatibility, historical null/backfill policy, tests serta downgrade/recovery. Candidate nomor berikut setelah HEAD sekarang adalah `009`; harus dicek ulang agar tidak bentrok. Jangan membuat migration bernama 009 tanpa approved body.

Untuk `kpi_snapshots`, jangan membuat tabel hanya untuk menampung tujuh angka dummy. Jika Owner mensyaratkan persisted snapshots seperti Schema.md, annex harus menyelesaikan period_start/end, scope, provenance/definition version, missing states dan uniqueness terlebih dahulu; schema dokumen saat ini hanya name/scope/value/computed_at tidak cukup bagi closed-period reproducibility.

Recovery: backup disetujui sebelum migration, uji upgrade dari 008 berisi data serta fresh DB, verify current=heads, uji rollback di disposable DB. Applied migration tidak diedit. Jangan destructive downgrade yang menghapus evidence; gunakan forward-fix atau restore teruji. Drift seed_key tidak dihapus hanya agar Alembic terlihat bersih.

## 11. API Contract Plan

Endpoint di bawah adalah **proposal additive**, bukan endpoint existing. Approval Owner atas plan harus mencakup kontrak ini dan ruling terkait. Tidak ada public sensor ingest atau reset API baru.

Shared rules: Bearer JWT DB-backed; baca untuk tiga role dengan scope; mutation hanya sppg_head/sppg_nutritionist dalam authority yang disetujui; monitor 403. 401 sebelum lookup, 403 foreign scope, 404 unknown owned resource, 422 malformed/domain-invalid input, 409 state conflict/stale/idempotency collision, 503 required infrastructure unavailable. No raw stack/provider credentials. Financial response values decimal strings; timestamps RFC3339; UUID tervalidasi. Existing legacy response types tidak diubah diam-diam.

| Method/path | Request | Response | DB/side effect | Retry/idempotency dan test |
|---|---|---|---|---|
| POST `/events/price-anomaly` | `quote_id: UUID`, `target_location_id: UUID`, `operation_key: UUID`; backend resolves commodity/supplier/reference | 201 `decision_id`, `event_type=price_anomaly`, `status`, `deviation_pct`, `classification`, `quote_id`, `reference_id`, `verifier`, `trace_url`; 200 no-anomaly dengan `decision_id=null`, no decision write | Baca PriceSignal; persist Decision/Evidence/Trace bila anomaly. Tidak membuat PO | Same actor/key/same payload returns same resource; collision 409; concurrent duplicate serialized via DB transaction lock keyed operation, recheck persisted operation key; no decision after no-anomaly. Test same/different actor, payload, concurrent replay, failed provider |
| POST `/events/safety-disruption` | `batch_id: UUID`, `target_location_id: UUID`, optional `previous_decision_id: UUID`, `operation_key: UUID`; tidak menerima safety status/temp override | 201 revised `decision_id`, `evaluation`, `excluded_batch_ids`, `recommended_candidate`, `previous_decision_id`, `status`, `trace_url`; no-safe-alternative 409 dengan sanitized evaluation dan `decision_id=null` | Persist safety evaluation walau tidak ada alternatif; proposed explicit commit boundary agar FAIL tidak hilang saat optimization gagal. Persist new Decision/Evidence/Trace hanya jika eligible. Lineage menunggu O-EVENT | Replay evaluation/result consistent; no duplicate revised decision; concurrency/no-safe/foreign batch tests. Policy failed-request outcome persistence wajib disetujui, bukan implicit rollback assumption |
| GET `/decisions/{decision_id}/approval-summary` | Path UUID; no user-supplied totals | 200 decision ID/iteration, action kind, target MOCK, locations/supplier/material, quantity/cost breakdown, safety/freshness/evidence/verifier, expiry, approval_requirement/current approvals/missing roles, `can_approve`, `can_execute`, `blocking_reasons` | Read canonical snapshot + related rows, no mutation/provider call | Read idempotent; no permission expansion. Test stale, missing facts, OR/AND, scope, summary→execute parity |
| GET `/kpi` | Required `start`, `end` RFC3339; optional `location_id` UUID. Omit scope = own location for SPPG, global for monitor. Proposed maximum range 366 days | 200 `period`, `scope`, `computed_at`, `data_source`, `metrics` exactly seven entries: `name`, `unit`, `state=available/no_data/unavailable`, `value` decimal string or null, `reason`, `sample_count`, `coverage`, `previous_value`, `trend` or null | Aggregate read only; snapshots only jika annex disetujui | Read idempotent relative to same DB snapshot. Invalid range/naive time 422; foreign scope 403; no-history trend null; all metric provenance tests |

Untuk mutation operation_key, transaksi lock + lookup harus mencakup semua writer endpoint tersebut dan record hasil committed. Jika existing JSON trace tidak cukup untuk replay durable/no-alternative outcome, jangan mengklaim exactly-once. STOP untuk menyetujui minimal operation persistence annex. Tidak memakai in-memory idempotency cache sebagai bukti durable.

Existing `POST /actions/approve`, `/actions/execute`, `/actions/verify`, `/actions/repropose`, `POST /decisions`, dan `POST /demo/seed` perlu prerequisite boundary review. Payload/behavior yang berubah harus didokumentasikan, tests/callers dimigrasi, dan OpenAPI diregenerasi pada commit yang sama setelah izin commit. Penutupan auth gap adalah perubahan kontrak yang disengaja, bukan silent compatibility patch.

`/actions/verify` tidak boleh terus menerima verdict caller lalu melabelinya hasil Verifier. Recommended ruling: server menjalankan independent verifier atas canonical facts; client meminta verification tanpa menentukan verdict; stale/missing facts fail closed. Ruling API compatibility dan semua callers harus ditetapkan sebelum S4-04.

## 12. Agent / Provider Plan

Arsitektur tetap frontend→FastAPI→domain/application→provider/repository→PostgreSQL/Mock SAP. Supervisor adalah satu-satunya full LLM agent; Verifier REST dan Forecast provider/statistical fallback bukan full agents tambahan.

S4 extension hanya mengorkestrasi tool existing sesuai kontrak. Numerik/safety berasal dari deterministic outputs. Input supplier, quote, evidence, rejection reason adalah untrusted data, tidak menjadi instructions. Validate structured provider response, reject invalid verdict/schema, normalize known statuses pada boundary tanpa mengubah domain.

Shared `resilience.py` dan `build_default_callers` tetap satu jalur konfigurasi/call. Pertahankan chain yang disetujui; tidak memotong fallback atau menuntut semua frontier models. Report actual successful provider/model dan setiap attempted fallback; all-unavailable tetap UNAVAILABLE dan dual approval, bukan hasil model palsu. Forecast statistical fallback diberi label statistical, bukan SAP-RPT-1.6.

Pemeriksaan lanjutan setelah hasil delegasi masuk mengonfirmasi gap client, bukan hanya adapter AWS: `verifier_client.py:151-162`, `forecast_client.py:175-189`, dan `supervisor_client.py:88-105` hanya meneruskan primary plus dua fallback meskipun registry memiliki chain lebih panjang. Jalur tersebut tidak menangkap exhaustion exception di call site; jalur SAP Forecast terpisah justru menangkapnya. Ini menambah prerequisite O-AI pada S4-00, bukan izin memperbaiki sekarang. Acceptance wajib mencakup sukses pada slot keempat atau lebih akhir, pemenang/attempts sesuai slot asli, serta exhaustion seluruh chain menghasilkan state unavailable/statistical yang disyaratkan, bukan uncaught error. Gunakan shared helper existing, jangan membuat fallback engine baru.

O-AI wajib memisahkan empat bukti: resource control-plane; direct data-plane invoke; application integration; composed business scenario. Historical PONG hanya memenuhi bukti direct invoke saat itu. S4-00 memerlukan aplikasi Supervisor→Runtime→Gateway→tool backend, Memory session A/B isolated write/read, dan trace yang dapat dikorelasikan ke Observability sesungguhnya. Missing local code tidak membuktikan remote runtime kosong, tetapi memblokir klaim integrasi aplikasi sampai diperiksa.

LEARN tidak diperluas menjadi ML. Repropose existing menyalin quantity/cost/location parent dan menambahkan alasan ke trace; jangan berkata sistem telah menyesuaikan rekomendasi atau memperbarui reliability bila tidak terjadi. Outcome feedback/receiving hanya melalui O-KPI dengan scope tambahan disetujui.

Observability untuk actual event: step_name/tool, decision/session/operation identity, started/finished timestamp, duration, actual provider/model, attempted fallback, sanitized error category, actor ID/role untuk human action. ACT hanya setelah Mock PO/action committed; failed execute bukan successful ACT. Jangan mengarang DETECT/ACT timestamps untuk backfill KPI. `synthetic=true` membedakan injected fixtures dari actual execution; label source local vs AgentCore tidak boleh disatukan.

## 13. Frontend Plan

Reuse bahasa visual existing navy/grey dan semantic safety colors `docs/design.md:88-101`. Tidak mengubah font/brand/peta sebagai proyek baru. Pilihan extension yang dibandingkan: panel di OpsConsole versus route demo baru. Pilih panel existing karena alur operator dan data client sudah tersedia; bukan dashboard kedua. KPI dapat ditambahkan sebagai section shell existing; route `/kpi` bukan kewajiban jika Owner menerima screen dalam shell.

| Screen/component | Role/data/API | State wajib | Acceptance browser |
|---|---|---|---|
| OpsConsole Event 2 | Approver run event API; monitor read feed | idle/loading/success/non-anomaly/missing reference/provider unavailable/error+retry | Tidak ada injected live activity; quote/ref dan result sesuai backend |
| OpsConsole Event 3 | Approver sesuai scoped authority; monitor read | evaluating/unsafe/excluded/revised/no-safe-alternative/error | FAIL jelas dengan teks, bukan warna saja; old decision tidak actionable |
| Feed/detail/DecisionChain | Scoped decisions/traces/evidence | loading/empty/stale/error/rejected/revised/expired | Riwayat dapat dibaca; tidak menulis rejection reason sintetis |
| ApprovalModal | Summary endpoint, roles approver | loading/incomplete/ready/submitting/conflict/expired | Focus trap, Escape, focus kembali, disable duplicate submit, summary read sebelum confirm |
| AgentTraceViewer/ProviderPanel | Actual trace dan persisted provider results | running/completed/unavailable/synthetic/local | Provider yang berhasil benar; no fake progress/timestamps |
| KPI Dashboard | GET kpi; monitor global, SPPG own | loading/seven available/no_data/unavailable/partial history/error | Null bukan 0; trend hanya data comparable; scope change tidak membocorkan cached lokasi lain |

React Query untuk server state seperti Rules.md; jangan menambah manual fetch di component. Existing `lib/api.ts` tetap boundary HTTP. Validasi external unknown sebelum typed state; gunakan discriminated state untuk ready/unavailable/loading, bukan memperluas `any`. Tidak perlu menambah UI library untuk memenuhi modal ini. Existing tests memakai Vitest dan SSR/static markup; behavioral browser test terpisah wajib untuk klik, focus, stale state, permission dan real network.

Regression producer→summary wajib menguji response feed sebenarnya: feed memakai `verifier_note`/`verified_by`, sedangkan modal lama membaca `summary.verdict`. Jangan membuat fixture dengan field `verdict` lalu menyebut seam live terverifikasi. S4-04 harus memetakan canonical verifier result secara eksplisit. Browser acceptance juga harus mengganti selected decision dan logout/login akun lain saat request trace masih berjalan; evidence akun/decision sebelumnya tidak boleh muncul pada konteks baru atau setelah error.

OpsConsole list komoditas sekarang mencantumkan beras sedangkan kontrak telur/ayam/wortel. Jangan memperluas domain menjadi beras; O-UI menentukan perbaikan selector yang relevan saja. SPPG selection harus mengikuti actual authorized location, bukan bebas memilih lalu mengandalkan UI sebagai security.

## 14. Security Plan

Profile ini berlaku pada **setiap** S4-00..06, termasuk tests/video:

1. Authentication: JWT diverifikasi server; unauth tidak mencapai decision lookup atau mutation. Jangan mengandalkan hidden button.
2. Authorization: tiga role tepat `sppg_head`, `sppg_nutritionist`, `bgn_monitor`. Monitor read-only termasuk demo seed/repropose/analysis mutation. No fourth role.
3. Location: filter sebelum list/aggregate/pagination; decision detail/chain/traces/summary dan action konsisten. Cross-regional candidate evidence untuk keputusan lokasi tujuan harus dibatasi ke konteks keputusan, bukan membuka semua lokasi. Exact source-evaluation authority diputuskan O-EVENT.
4. Validation: UUID, finite decimal/positive prices, known enums, timestamp aware, structured provider response; browser tidak berwenang memasok canonical cost/safety/verdict/supplier execution snapshot.
5. Secrets/PII: `.env` tidak dibaca/ditulis untuk plan; no templates; evidence allowlist, sanitized errors, user ID/role secukupnya. Tidak menampilkan email/password/JWT di log/video.
6. Prompt injection: supplier/evidence/rejection text dianggap data. No tool execution/approval dari instruksi yang tertanam di text. LLM tidak menentukan role atau override hard constraints.
7. Action integrity: proposal ≠ approval ≠ execute; actual verdict, expiry, current safety, canonical supplier/material/quantity, satisfied role matrix diverifikasi pada boundary. Duplicate/concurrent execute tidak menghasilkan dua PO atau partially committed success.
8. Auditability: actor, decision version, event timestamps, evidence identity, actual provider attempts, reason penolakan, transaction outcome. Keep historical rows; no synthetic success trace.

Mandatory security tests memakai JWT dari login user DB nyata dan query no-side-effect setelah denied request. Tests bearer header saja tidak membuktikan claims/location. Denial terhadap nonexistent resource harus tetap dievaluasi sesuai auth-first policy.

## 15. Testing Strategy

Perintah berikut untuk **fase eksekusi setelah approval**, dari root repo. Jangan menjalankan DB-writing tests terhadap DB demo utama tanpa isolated test environment/cleanup yang disetujui. Tidak ada expected fixed pass count; catat hasil aktual beserta ignored/skipped modules.

| Layer | Command/approach | Bukti yang diterima |
|---|---|---|
| Container backend | `docker compose exec -T backend pytest -q` | Full collected/passed/failed/skipped + exit asli |
| Ruff | `docker compose exec -T backend ruff check .` | Zero error |
| Migration | `docker compose exec -T backend alembic current` dan `docker compose exec -T backend alembic heads` | Single expected head + metadata comparison |
| Approved migration only | `docker compose exec -T backend alembic upgrade head` | Fresh/008 upgrade pada DB test; tidak saat planning |
| Frontend | `docker compose exec -T frontend npm run test` | Actual assertions PASS |
| TypeScript | `docker compose exec -T frontend ./node_modules/.bin/tsc --noEmit --incremental false` | Zero type error; hindari tsbuildinfo churn |
| Lint/build | `docker compose exec -T frontend npm run lint`; `docker compose exec -T frontend npm run build` | Keduanya exit 0, bukan lint dianggap build |
| Host-only tests | Approved host Python environment compatible `>=3.12`, `PYTHONPATH=backend`, jalankan enam file `HOST_ONLY_MODULES` secara eksplisit | Host dependency/import failures tidak disembunyikan; host Python saat planning bukan baseline yang otomatis kompatibel |
| Live providers | Test bertanda live dengan `pytest -m live`, hanya pada environment SDK/credentials yang benar | Actual external response; mocks dan skip tidak lulus live gate |
| Browser E2E | Existing available browser automation atau Owner-approved tooling | Klik/UI/network/DB readback; bukan SSR string assertion |

Focused future commands:
- `docker compose exec -T backend pytest -q tests/test_event2_flow.py`
- `docker compose exec -T backend pytest -q tests/test_event3_flow.py`
- `docker compose exec -T backend pytest -q tests/test_kpi.py tests/test_kpi_api.py`
- `docker compose exec -T backend pytest -q tests/test_approval_summary.py tests/test_approval_matrix.py tests/test_action_boundary_e2e.py`
- `docker compose exec -T frontend npm run test -- tests/event-scenarios.test.tsx tests/kpi.test.tsx tests/approval-modal.test.tsx`

File proposed belum ada dan command tersebut tidak diklaim telah dijalankan.

Unit: formula existing termasuk each component/threshold/rounding, KPI aggregates setelah ruling, approval matrix. Integration: actual migration DB, source→evidence→decision→summary→action transaction, idempotency/concurrency/rollback. Agent: tool selection/composition/safety refusal, schema validation, no independent second agent. Security: auth/role/location/injection/stale action. E2E: Event 1/2/3 plus four cases regression. Live: available Bedrock/provider, genuine AgentCore chain/Memory/Observability. Failure injection: 429/timeout/5xx/malformed response/all unavailable, DB failure sebelum/sesudah intermediate write, rejected/expired/unsafe action, duplicate operation.

Rules for evidence: no pipeline yang menyembunyikan pytest exit; no all-skipped RED; timestamps relative/injected; owned fixtures cleanup; static demo seed tidak live; producer→consumer test wajib tanpa menambal seam dengan fabricated verdict/evidence. Host/container exclusion pada conftest harus dicantumkan. Freshness test tidak bergantung fixed seed age.

## 16. Demo / E2E Scenario

| Scenario | Trigger dan jalur | Expected acceptance |
|---|---|---|
| Event 1 Regional imbalance | Facts Cianjur surplus/Jakarta shortage → existing composed Supervisor/tools → verified decision → human approval → execute | Safe rank/cost berasal dari backend; approved snapshot menghasilkan Mock PO; actual traces/Memory/Observability sesuai gate |
| Event 2 Price anomaly | Pilih persisted supplier quote dan reference → deviation/evidence/Verifier → review queue | Correct deviation/flags; review-required wording; no accusation; no auto-PO. Review terminal semantics mengikuti O-EVENT |
| Event 3 Safety disruption | Pilih persisted temperature excursion Cianjur → evaluate FAIL → exclude/reoptimize → Bogor safe alternative → new review/approval | Unsafe old decision tidak executable, history preserved, new independent approval, Mock PO hanya revised safe snapshot |
| Rejection loop | Reject dengan reason → repropose → chain | Reason wajib, no inherited approval, LEARN dilabel trace bukan ML |
| Emergency shortage | Existing shortage-darurat fixture | TTL dan emergency context jelas, no safety bypass |
| Suspicious supplier | Existing supplier-janggal fixture | FLAGGED/dual approval, source fixture jelas |
| Logistics disruption | Existing gangguan-logistik fixture | Rute infeasible tidak dipaksakan; old/revised history dipertahankan |

Rehearsal wajib tiga putaran consecutive, setiap putaran mencakup ketiga Event utama. Failure injection dilakukan sebagai cabang terpisah, tidak dihitung sebagai successful normal-flow putaran. Catat run ID, HEAD/build, time window, actual user roles, decision IDs, evidence/trace IDs, provider/model outcomes, PO IDs atau no-PO readback, dan KPI response. Jangan menaruh passwords atau JWT dalam evidence.

Initial fixture timestamps dibuat relatif terhadap run secara approved. Reset bukan memperpanjang expiry keputusan operasional. Bila data tidak memadai untuk Bogor, jangan hardcode pilihan Bogor dalam engine; perbaiki owned scenario facts dan buktikan engine memilihnya.

## 17. Final Sprint 4 Acceptance Gate

Ini gate Sprint 4 saja. Bukan final S0→S4 audit dan tidak membuka Sprint 5 otomatis.

- [ ] S4-00 PASS, seluruh ruling/prerequisite yang memengaruhi S4 selesai dan fresh diverifikasi.
- [ ] Backend full suite, focused new tests, Ruff, host-only tests relevan PASS; skips dijelaskan dan tidak menutupi required capability.
- [ ] Alembic single expected head, approved schema/index/constraint reconciliation, upgrade/recovery evidence bila migration ada.
- [ ] OpenAPI file/live/method contracts cocok, auth metadata dan actual 401/403 behavior sesuai; no stub success.
- [ ] Frontend tests/TypeScript/lint/build PASS; real browser interaction, error/loading/empty/scope/keyboard states terverifikasi.
- [ ] Docker/PostgreSQL/backend/frontend/mock-sap sehat; fresh served artifact sesuai tree. Source bind mounts cukup restart bila perlu; dependency/image COPY changes perlu rebuild, berdasarkan inspect, bukan membabi-buta.
- [ ] Genuine Supervisor/tool chain, available provider, actual fallback, Memory isolation/read-write, Observability correlation diverifikasi. Resource presence saja tidak cukup.
- [ ] Authentication/RBAC/location, secrets scan, prompt-injection boundary, stale/unsafe/expired action rejection dan duplicate execute no-side-effect PASS.
- [ ] Event 1/2/3 terpenuhi; no safety override, deterministic score/cost, independent verifier, human approval, Mock SAP provenance.
- [ ] Tujuh KPI memenuhi approved original definitions atau explicit revised scope Owner. Partial/unavailable tidak diberi label fully Done.
- [ ] Approval summary cocok dengan canonical executed snapshot; proposed/approved/executed tetap berbeda.
- [ ] Rehearsal tiga putaran consecutive setelah final relevant change; video fallback playable dan match accepted build.
- [ ] Evidence docs Bahasa Indonesia, source links/commands/HEAD/results tersedia; historical S3 tidak ditulis ulang; TODO hanya Roy yang memutuskan sprint DONE.

Kegagalan mandatory gate berarti belum accepted. Jangan memberi score production readiness global dalam plan ini.

## 18. Contract Conflicts Requiring Owner Decision

### CONTRACT CONFLICTS REQUIRING OWNER DECISION

| ID | Source A | Source B / exact conflict | Impact | Recommended resolution | Bisa proceed unresolved? |
|---|---|---|---|---|---|
| O-SEC-1 | Architecture §security: semua protected endpoint JWT; S3 report closure | `main.py:59-62` tanpa router guards; `decisions.py:61,270`, `actions.py:296` tanpa auth; live unauth detail 404; OpenAPI lists three additional unguarded operations | S4 bisa membuat/membaca/repropose tanpa expected auth | Approve focused prerequisite guards + auth-first and scoped tests, bukan rewrite auth | Tidak |
| O-SEC-2 | Exactly three roles; monitor read-only; SPPG own location | `auth.py:91-99` hanya role; list/detail/actions tidak memfilter location; `demo.py:129` hanya JWT untuk mutating seed | Data lintas lokasi dan monitor mutation | Tetapkan target-location ownership dan limited cross-region evidence access; guard demo seed; enforce server-side semua S4 call paths | Tidak |
| O-SEC-3 | Independent Verifier dan matrix CONSISTENT OR, FLAGGED/UNAVAILABLE AND | `DecisionActions.tsx:128` mengirim literal consistent; `/actions/verify` mempercayai caller lalu menulis verifier_agent | Client dapat menurunkan matrix tanpa audit independen | Verification request memicu server-side verifier atas canonical facts; simpan result/provenance; migrate callers/test | Tidak |
| O-AI | Architecture mewajibkan Runtime/Gateway/Memory/Observability; S3 resources/invoke historis PASS | `ai_provider_chain.py:24-54` stub; `agent_memory.py:74-84` unavailable; `agent_observability.py:117-121` unavailable; agent source minimal; OpsConsole analyze bukan run_event1 | Demo dapat menunjukkan local pipeline sebagai AWS agentic path | Approve bounded integration prerequisite dan verifikasi remote artifact/application routing; jangan mengganti mandatory capabilities dengan mocks | Tidak untuk S4 agentic acceptance |
| O-KPI | Skill §4 tujuh KPI, Roadmap tujuh nilai real | Menu/fulfilment/disposal/case denominator belum ada; ACT absent pada execute; approved cutoff tidak persisted; kpi_snapshots absent | Full requirement tidak dapat dihitung jujur | Pilih full facts contract + minimal annex, atau explicit partial scope revision. Rekomendasi jangan mengurangi definisi; approve smallest facts work bila full KPI wajib | Tidak untuk S4-03/full gate |
| O-DATA-1 | ORM/migrations adalah schema contract | Live-only seed_key pada tiga tables dan partial unique indexes | Upgrade/fresh DB berbeda, fixture behavior bisa tergantung drift | Owner pilih formalize atau remove melalui reviewed migration; cek penggunaan/data sebelum destructive choice | Tidak untuk schema-backed gate; read-only plan boleh |
| O-DATA-2 | Migration007/live mengizinkan SUPERVISE | ORM `models/decisions.py:153-156` tidak mengizinkan | Fresh create_all schema dan production migration berbeda | Align ORM dengan approved007 tanpa perubahan semantic step; test migrated DB dan metadata | Tidak untuk trace schema acceptance |
| O-EVENT-1 | Architecture Event2 berakhir pada review-required queue | Generic actions menghasilkan PO; decision model tidak punya terminal review-only outcome | Jangan mengeksekusi procurement hanya karena harga ditandai | Tetapkan Event2 review-only acceptance, tidak PO; bila perlu closure status/schema buat annex; default jangan auto-execute | Tidak untuk S4-01 contract |
| O-EVENT-2 | Event3 reroute dan old log retained | supersedes/repropose hanya rejected; generic decisions tidak menyimpan immutable batch FK; execute belum recheck safety | Old unsafe snapshot masih berpotensi dieksekusi | Approve safety correction lineage + batch snapshot association dan execute revalidation; jangan memalsukan human rejection | Tidak |
| O-PO | Skill SAP mapping purchase component dan supplier/source decision; Architecture provider boundary | `actions.py:248-254` unit price dari total SDC dan supplier target; direct SQL PO pada API; propose supplier/material tidak canonical persisted | Summary dapat berbeda dari actual PO; Event3 reroute tidak terwakili pada PO supplier | Owner tentukan canonical action snapshot dan provider-boundary prerequisite; preserve formula, jangan ubah SDC menjadi purchase | Tidak untuk execute acceptance |
| O-NUM-1 | Request SDC berformat Purchase Cost lalu bullet components | Skill §3/source memakai penjumlahan eksplisit | Operator tidak boleh diasumsikan multiplication atau additive tanpa penjelasan | Konfirmasi additive sebagai existing Opsi A; tidak mengubah formula | Tidak untuk sign-off angka sampai konfirmasi |
| O-NUM-2 | SDC source docstring HALF_UP 2dp per komponen | Implementation hanya quantize expected_loss; input raw purchase/transport tetap raw | UI/storage dapat membulatkan berbeda dari engine | Putuskan input precision vs per-component rounding; lakukan focused component tests setelah approval, bukan tune total | Tidak untuk financial acceptance |
| O-UI | design.md SPPG Staff/Dinas Admin approver/peta; PRD persona lama | Locked tiga role, monitor read-only; TODO rev9 mengganti peta dengan OpsConsole | Jangan membangun role/peta baru mengikuti dokumen stale | Catat ruling authoritative tiga role dan reuse OpsConsole; patch dokumen hanya setelah Owner izinkan | Bisa planning, tidak memakai persona lama |
| O-DOC | Roadmap S0/S3 unchecked, S2 sebagian In Progress | Owner menyatakan S0–3 selesai, TODO S3 DONE dan newer evidence | Drift status, bukan alasan mengulang semua sprint | Preserve history, scoped additive clarification saat execution docs; final cross-sprint audit tetap deferred | Ya, tidak reopen semua historical debt |
| O-SECRET | Dokumen lama menyebut env template | User melarang env template/secrets di luar .env | Risk exposure jika mengikuti instruksi lama | Current user policy berlaku; jangan create/read template credentials; broader doc sweep deferred | Ya dengan larangan eksplisit |

Detail O-NUM-2, synthetic precision probe dengan Python Decimal: purchase 100.005, transport 0.005, handling 0, freshness 1, safety pass menghasilkan raw additive total 100.010, sedangkan HALF_UP setiap komponen menghasilkan total 100.02. Ini demonstrasi perbedaan kontrak, **bukan** hasil seeded/live cost atau perubahan formula. Plan tidak menulis regression test/production fix karena belum diizinkan.

Keputusan Owner harus menyebut ID, pilihan, scope file/API/schema, bukti acceptance, dan apakah prerequisite dikerjakan sebelum S4 atau sebagai subgate berizin dalam S4-00. Approval umum “lanjut plan” bukan persetujuan otomatis terhadap schema atau semantic changes yang belum terdefinisi.

### 18.1 Disposition eksekusi (2026-10-08, berdasarkan prompt Owner — additive)

| ID | Disposition | Bukti |
|---|---|---|
| O-SEC-1/2 | RESOLVED — guards JWT/403-monitor/scope lokasi + seed mutating-roles (p1) | `test_s4_sec_guards.py` 9 passed; fallout suite 16 passed |
| O-SEC-3 | RESOLVED — verdict server-side, request hanya decision_id `extra="forbid"`, 409 setelah approval tercatat (p2) | `test_s4_verifier_independence.py` 5 passed; FE tsc/lint/vitest 55 passed |
| O-DATA-2 | RESOLVED — ORM CHECK +SUPERVISE, align 007, tanpa migration (p3) | `test_s4_schema_alignment.py` 3 passed |
| O-AI | RESOLVED (kode) — `agentcore_caller.py` invoke nyata, chain 4+ slot, exhaustion → UNAVAILABLE; boto3 di-`bump` karena boto3==1.35.0 tidak mengenal service `bedrock-agentcore` (root cause quirk container). Fresh evidence: control-plane READY, invoke HTTP 200 PONG. Memory UNAVAILABLE (IAM AccessDenied CreateEvent — external dependency, seperti §32). Observability UNAVAILABLE (as-built always-raise; dicatat sebagai limitasi). Composed proof dari container menyusul pasca-rebuild | `/tmp/s4_oai_probe.txt`; `test_s4_agentcore_adapter.py` + chain tests 38 passed |
| O-EVENT-1 | RESOLVED — Event 2 review-only tanpa PO, tanpa status closure baru, tanpa annex | Prompt Owner §15–17 |
| O-EVENT-2 | RESOLVED — lineage via `previous_decision_id` + evidence linkage + execute revalidation; `supersedes_id` tidak dipalsukan; tanpa migration | Prompt Owner §19–22 |
| O-PO | RESOLVED — summary & execute membaca canonical Decision yang sama (sumber tunggal), parity test wajib; tanpa tabel snapshot baru | Prompt Owner §21–22; plan S4-04 |
| O-NUM-1 | RESOLVED — SDC additive Opsi A dikonfirmasi prompt Owner §4.4 (daftar komponen dijumlahkan) | Prompt Owner §4.4 |
| O-NUM-2 | RESOLVED — pertahankan perilaku as-built (hanya expected_loss diquantize); docstring HALF_UP per-komponen dicatat drift komentar LOW, tidak tune angka | Prompt Owner §4.4 "Do NOT invent a new formula" |
| O-DATA-1 | RESOLVED — seed_key live-only dibiarkan apa adanya (tidak diformalkan, tidak dihapus); dicatat drift di gate | Prompt Owner §5 |
| O-KPI | RESOLVED — tujuh KPI diimplementasi dengan state available/unavailable/no_data + reason eksplisit, tanpa fake zero/proxy; tanpa migration (ACT via trace existing, §10) | Prompt Owner §13/§23; plan §10 |
| O-UI | RESOLVED — tiga role terkunci + reuse OpsConsole; persona lama tidak dipakai | TODO rev9; prompt Owner §3.3 |
| O-DOC / O-SECRET | RESOLVED — status historis tidak ditulis ulang; secrets hanya `.env`; tanpa env template | Prompt Owner §37–39 |

## 19. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Historis PASS dianggap fresh atau collection dianggap regression | Label evidence tier; canonical commands dan actual result per HEAD |
| Scope melebar menjadi final audit/remediation semua debt | Batasi ke dependency matrix; Owner-approved prerequisite brief; no global audit score |
| Full KPI dipaksakan dengan proxy | Metric worksheet, source facts, null availability; no silent scope reduction |
| Synthetic seed/trace mengaku live | Provenance flags/UI copy dan genuine provider evidence terpisah |
| Provider latency/outage | Shared bounded resilience, actual fallback identity, UNAVAILABLE; video fallback |
| Safety berubah sesudah approval | Canonical batch linkage dan server revalidation, blocked old action |
| PO berbeda dari approved summary | Snapshot parity test dan immutable identity; O-PO sebelum S4-04 |
| Drift DB ditutup dengan create_all atau destructive cleanup | Migration-reviewed ruling, disposable DB upgrade test, no auto-delete |
| Test fixture umur lama/DB contamination | Owned relative-time fixtures dan explicit cleanup by run IDs |
| Browser/server menyajikan bundle lama | Verify mounted vs baked, restart/rebuild sesuai changes, fresh artifact inspection |
| Plan bertentangan dengan HEAD baru | Re-run S4-00 dan rebase plan contracts sebelum implementation |
| Video direkam sebelum final fix | Build stamp, replay validation, rerecord affected scenes dengan disclosure |

## 20. Definition of Done

Task hanya DONE bila implementation ada, tests ada dan PASS, API/security/database migration/live infrastructure yang relevan terverifikasi, docs/evidence tersedia, serta seluruh acceptance task PASS. Adanya kode atau kartu UI bukan DONE.

Untuk NO-CHANGE tasks seperti rehearsal/video, deliverable nyata, test/playback/checklist results dan evidence tetap wajib. Tidak perlu membuat production code hanya untuk memenuhi wording DoD.

Tidak ada blocker tersembunyi dalam status Done. Missing mandatory AWS path, partial KPI, skipped test, simulated provider, unverified migration, atau incomplete browser flow harus ditulis sebagai blocked/partial. Sprint 4 tetap menunggu keputusan Roy untuk ditandai DONE. Sprint 3 historical status tidak diubah oleh plan ini.

## 21. Execution Order

1. Owner review plan dan disposition §18. Pisahkan persetujuan plan dari izin prerequisite edits.
2. S4-00 baseline read-only dahulu, then approved isolated full gates/live capability tests. Jika blocker terbukti, STOP, brief remediasi, Owner approval, focused RED→GREEN, fresh prerequisite gate. Tidak dispatch downstream saat subgate belum PASS.
3. S4-01 Event2 vertical slice hingga review queue, kemudian S4-02 Event3 safety correction. Shared files dikerjakan serial agar event/action contracts tidak bertabrakan.
4. S4-04 approval summary setelah canonical snapshot/evidence/verification producer accepted.
5. S4-03 KPI setelah metric worksheet dan facts production disetujui serta event/action timestamps valid. Jika kontrak KPI belum ada, jangan mengganti pekerjaan ini dengan dummy dashboard.
6. S4-05 fresh canonical gate + tiga consecutive rehearsal rounds.
7. S4-06 rekaman fallback, playback, evidence/doc sign-off, serahkan ke Roy.

S4-07 Identity dan S4-08 App Runner hanya melalui review scope stretch tersendiri setelah mandatory work; bukan alasan mengubah arsitektur atau credentials sekarang.

## 22. Explicit Exclusions

Tidak dilakukan atau diotorisasi oleh dokumen ini: final cross-sprint audit S0→S4, production readiness score global, real SAP/real procurement, autonomous approval/execute, LLM numeric safety logic, formula/rank threshold changes, ML/retraining/reliability learning baru, full agent tambahan, role tambahan, redesign visual/peta/admin, generic sensor ingestion platform, blanket security rewrite, broad dependency upgrades, all-model frontier access, AWS provision/Identity/App Runner, `.env`/template edits, migration creation/execution, data cleanup/reset, dependency installation, commit/push.

Hanya plan Markdown ditulis. Proposed filenames/endpoints/schema annexes belum diimplementasikan. Rencana yang terblokir menunggu keputusan bukan fitur yang selesai.

## OWNER REVIEW REQUIRED

**This document is a PLAN ONLY. No Sprint 4 implementation has been performed.**

### Recommended execution order

Owner rulings → S4-00 PASS → S4-01 → S4-02 → S4-04 → S4-03 → S4-05 → S4-06. Scope ini mempertahankan ID resmi TODO dan tidak mengaktifkan stretch.

### Hard blockers

- Auth/location/monitor gaps pada entry point yang akan dipakai Sprint 4.
- Client-supplied verifier verdict dan action snapshot/safety integrity belum memenuhi trustworthy approval requirement.
- Genuine composed AgentCore application integration belum terbukti; adapter source masih unavailable stubs.
- Full KPI facts, denominator, period/approval/execution timing belum ditetapkan.
- Live schema drift dan numeric precision/operator ambiguity belum memperoleh disposition.
- Fresh full backend/frontend/host/live acceptance belum dijalankan dalam planning. Collection sukses bukan pengganti.

### Owner decisions required

Putuskan O-SEC, O-AI, O-KPI, O-DATA, O-EVENT, O-PO, O-NUM; ratifikasi reuse OpsConsole/tiga role sebagai pengganti persona/peta dokumen lama. Untuk fakta/schema baru, setujui annex rinci terlebih dahulu. Pilihan partial KPI harus dinyatakan sebagai perubahan scope, bukan pemenuhan original requirement.

### First task to execute after approval

S4-00: freeze HEAD dan environment test, verifikasi prerequisite dengan bukti fresh, lalu hentikan implementation bila hard blocker belum diputuskan. **Tidak mulai S4-01 atau mengubah production code hanya karena plan ini telah diserahkan.**

## 23. Addendum eksekusi — bukti prerequisite S4-00 (2026-10-08, HEAD 7089bcf)

Pemenuhan ruling, additive terhadap plan ini (tidak mengubah kontrak §1–§22):

- **O-SEC-1/2 (p1)** — guards JWT+role+scope: `test_s4_sec_guards.py` 9 passed.
- **O-SEC-3 (p2)** — verifier server-side, request `decision_id` saja (`extra="forbid"`), ctx kanonik dari DB: `test_s4_verifier_independence.py` 5 passed.
- **O-DATA-2 (p3)** — ORM CHECK AgentTrace memuat SUPERVISE (align migration 007): `test_s4_schema_alignment.py` 3 passed.
- **O-AI (p4)** — adapter `agentcore_caller.py` invoke runtime nyata; chain penuh (12 slot, tidak terpotong 3); exhaustion → UNAVAILABLE (bukan 500): 38 passed (adapter+chain+resilience+sprint3 acceptance).
- **O-AI bukti AWS fresh (host boto3 1.42.89)**: control-plane `get_agent_runtime` READY; data-plane `invoke_agent_runtime` HTTP 200 PONG (runtime mealchain-5iQ9raHpis); **Memory UNAVAILABLE — IAM AccessDenied `bedrock-agentcore::CreateEvent`** (external dependency, paralel §32; tidak difake).
- **O-AI container gap**: `boto3==1.35.0` baked COPY tidak mengenal service `bedrock-agentcore` (botocore <1.39) → bump `requirements.txt` ke 1.42.89 (bagian prerequisite §18), rebuild image berjalan; composed proof Supervisor→AgentCore dari container menyusul setelah rebuild.
- **O-EVENT** — reuse pipeline rekomendasi deterministik eksisting (Event 1) untuk Event 2; tidak ada engine baru.
- **O-PO** — Event 2 review-only, tanpa auto-PO (§15–17).
- **O-NUM** — angka deterministik `app/core/price.py` (5%/15%) + SDC Opsi A eksisting dipertahankan; tidak ada tuning test/doc agar angka lama lulus.
- **O-DATA-1** — drift `seed_key` live-only TIDAK diubah (O-Owner); tidak dibersihkan diam-diam.
- **O-KPI** — KPI dengan state `available/unavailable/insufficient_data` + reason eksplisit; tanpa fake 0/proxy (§13/§23).
