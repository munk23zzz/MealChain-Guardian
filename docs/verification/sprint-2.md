# Verifikasi Sprint 2 — Decision Intelligence + Balancing

Tanggal: 2026-10-05/06 · Branch: `feature/sprint2-decision-intelligence` · BASE: `b6d85c8` (plan `03bdf7d`)
Metode: subagent-driven-development (plan `.hermes/plans/2026-10-05-sprint2-decision-intelligence.md`), TDD ketat RED→GREEN→REFACTOR per task, ledger `.superpowers/sdd/2026-10-05-sprint2-decision-intelligence/progress.md`.

## Hasil akhir

| Gate | Perintah (aktual) | Hasil |
|---|---|---|
| Migration | `docker compose exec -T backend alembic upgrade head` | exit 0, head `006_decision_persistence` |
| Backend test | `docker compose exec -T backend pytest -q` | **294 passed**, 1 warning (deprecation asyncio), exit 0 |
| Lint backend | `docker compose exec -T backend ruff check .` | All checks passed, exit 0 |
| Frontend test | `docker compose exec -T frontend npm run test` | 1 passed (vitest run), exit 0 |
| Frontend lint | `docker compose exec -T frontend npm run lint` | No ESLint warnings or errors, exit 0 |
| Docker | `docker compose ps` | 4 services Up: backend, frontend, mock-sap, postgres (healthy) |

## Task 0 — rekonsiliasi kontrak (keputusan Roy 2026-10-05, disetujui)

- **`price_signals.seed_key`**: terbukti drift murni (ada di DB live, absen dari migration/ORM/seed/API/docs). Dihapus via migration `005_reconcile_sprint1_schema` (idempoten: cek information_schema sebelum DROP). Test guard: 3 test rekonsiliasi.
- **`decisions.expires_at`**: keputusan A1 — TIMESTAMPTZ NOT NULL, didokumentasikan di `docs/Schema.md` §3.2, diimplementasikan migration 006 + ORM.
- **Frontend test runner**: `npm run test` = `vitest run`; `vitest 2.1.9` devDependency + lockfile ter-commit; smoke test shell page. Reproducibility terverifikasi lewat `npm ci` clean-install (549 packages) → test pass.

## Chain migration

`001_master_data → 002_operational_data → 004_supplier_quote_design → 005_reconcile_sprint1_schema (drop seed_key) → 006_decision_persistence (decisions, decision_evidence, approvals, agent_traces, FK sap_mock_purchase_orders.decision_id ON DELETE SET NULL)`

Roundtrip 004→005→006→downgrade→upgrade terverifikasi di DB terisolasi `mealchain_mig_test` (dihapus setelah uji).

## Engine deterministik (Task 1–7, tanpa LLM)

- **Candidate model** (immutable, validasi ketat) + **gap engine**: surplus = max(s−d,0), shortage = max(d−s,0).
- **Generator**: quantity = min(surplus, shortage, available_eligible); exclude shortage-source/surplus-dest/logistics infeasible; deterministik (urut lexical).
- **Candidate Score** = Demand Fit × Supply Availability × Freshness × Safety Eligibility × Supplier Reliability × Logistics Feasibility (bukan formula baru).
- **Safe Delivered Cost** = Purchase + Transport + Handling + Expected Loss + Freshness Risk + Safety Risk; Expected Loss = 0.2 × (1−freshness) × purchase; freshness <0.60 → factor 0.50; safety penalty 10%; safety FAIL tidak pernah dicost (ditolak sebelum ranking). Untuk jalur rekomendasi utama (freshness 0.90): 600 kg × 26.200 = 15.720.000 + transport 21.600 + handling 150.000 + expected loss 314.400 + freshness risk 0 + safety risk 0 = **16.206.000**. Untuk contoh audit freshness 0.50: expected loss 1.572.000 + freshness risk 7.860.000, sehingga total **25.323.600**; status freshness 0.50 adalah `fail`, jadi contoh ini hanya verifikasi aritmetika dan tidak boleh menjadi kandidat.
- **Ranking**: score DESC → SDC ASC → tie lexical; output rank 1..N deterministik.

## Service, API, expiry, context (Task 9–12)

- Service async (AsyncSession), facts = latest-record per kunci; **harga latest per (location, commodity, SOURCE)** — pihps & quote berdampingan (disiplin dua lapis terjaga).
- API: `GET /balance/{location}/{commodity}`, `POST /balance/recommend`, `POST /decisions`, `GET /decisions/{id}` (validity: now < expires_at). Persist memetakan snapshot ke kolom terstruktur Schema.md §3.2 (tanpa kolom `payload` — tidak ada di kontrak). Status awal `proposed`.
- `is_decision_valid(now, expires_at)`: wajib tz-aware, exact expiry = expired, naive ditolak.
- Supervisor context: assembler murni allowlist — unknown keys dibuang (anti-secret), required ditolak ValueError, canonical JSON deterministik; `price_anomaly` reuse engine Sprint 1 (5%/15%) tanpa formula baru; `evidence` = batch_ids + price_sources.

## Skenario demo (Task 14) — hasil aktual

1. **Contract/synthetic fixture:** Cianjur 1400/500 → surplus **900**; Jakarta 300/1000 → shortage **700**; kandidat Cianjur→Jakarta telur **ada** (qty 600 = min dengan batch eligible). ✅
2. Ref 26.500 vs Supplier C 32.000 → **anomalous + flagged** (+20,75%). A 26.200 normal (−1,13%), B 27.000 normal (+1,89%), D 25.400 normal (−4,15%). ✅
3. **Contract/synthetic fixture:** Cianjur candidate dengan temperature excursion (`safety FAIL`) → **eliminated sebelum cost/ranking**, sementara alternative Bogor telur yang valid (`safety PASS`) tetap eligible dan muncul di recommendation. ✅
4. Identitas supplier di `supplier_id`, `source` tetap `'supplier_quote'` — terverifikasi di DB seed Cianjur/telur. ✅
5. Freshness 0.70 → **needs_verification**, bukan PASS. ✅
6. **10× repetisi**: canonical JSON 10 eksekusi identik bit-per-bit (1 set). ≥9/10 target terpenuhi (10/10). ✅

## Deviasi & ruling (tercatat di ledger)

- **Delegation infra gagal ke-5** (subagent Task 0: HTTP 502 provider + max_iterations, tanpa file tertulis) → parent self-execute seluruh task dengan TDD ketat + parent review per task (preseden disetujui Roy di Sprint 1).
- **Pemisahan acceptance:** angka Cianjur 1400/500 dan Jakarta 300/1000 adalah contract/synthetic fixture Task 14 (supply telur + demand yang disiapkan fixture), bukan klaim hasil seeded/live API. Pada database seeded/live saat ini, latest-record Jakarta adalah supply 300 dan demand 1080, sehingga shortage **780**; perbedaan itu bukan defect otomatis dan dilaporkan terpisah dari contract fixture.
- Task 13 = verifikasi reproducibility (runner sudah di-commit Task 0) — tanpa commit duplikat.
- Guard Sprint 1 yang usang-by-design (decisions absen; PO tanpa FK) di-retire dengan pointer ke test baru.

## Technical debt (tidak menyembunyikan defect perilaku)

- Ruff: deprecation warning top-level `select` → pindah ke `[lint]` section pyproject (kosmetik).
- pytest: 1 warning deprecation `asyncio_default_fixture_loop_scope` (kosmetik).
- npm: deprecation recharts 2.x (upstream, di luar scope sprint).
- `evidence.batch_ids` di API live berasal dari dict batches service (batch id riil); belum ada tabel trace terpisah — cukup untuk demo, bisa diperkuat Sprint 3 bila diagregasi audit.
- Test supervisor agent bersifat host-only (conftest) — pola lama Sprint 1, tidak diubah.

## Lampiran: Review Terpisah (Task 16)

- Reviewer terpisah (subagent `deleg_586e9481`, sesi terisolasi) menjalankan audit
  statis + reproduksi roundtrip migration 006 di DB terisolasi sendiri; konfirmasi
  reviewer: secrets tidak ada di git, DB live utuh (44 prices, 14 suppliers,
  10 kota quote, FK `sap_po_decision_fk` ada, head 006, 0 baris decisions).
- **Temuan behavioral defect reviewer**: `evidence.batch_ids = []` pada jalur live
  (API). Ditindaklanjuti TDD penuh: RED (test live gagal — batch_ids kosong) → fix
  `batch_id` di fetch facts service → GREEN (295 passed, ruff bersih). Commit
  `732d532`. Verifikasi temuan + fix diulang dan dikonfirmasi parent (transkrip
  reviewer terpotong oleh batas iterasi + 502 provider).
- Keterbatasan proses: reviewer sendiri berhenti karena batas iterasi; laporan
  final reviewer tidak lengkap — bukti akhir = perbaikan terverifikasi parent.

## Status dokumen

`TODO.md` + `Roadmap.md`: status Sprint 2 menunggu penilaian Roy sebelum ditandai selesai (konvensi: user yang menandai). **Sprint 3 TIDAK dimulai.**
