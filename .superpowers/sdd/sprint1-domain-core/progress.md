# SDD ledger — plan: .hermes/plans/2026-10-01-sprint1-domain-core.md

## Konteks
- Branch: feature/sprint1-domain-core (dari master @ 7c5c1d5)
- Rencana: plan Rewrite v2 (534 baris), source of truth.
- Konteks eksekusi: prior session left UNCOMMITTED Task 1-9 partial artifacts (core engines, migration 002, SAP integration) + DB already seeded (26 locations dirty). Roy memutuskan: review semua dari awal sampai commit terakhir, perbaiki yang salah, mulai dari task yang butuh perbaikan.

## Ruling awal (pra-dispatch)
- Ruling: .env.example modified berisi secrets asli → git checkout -- .env.example (restore HEAD). Secrets hanya .env. — Risk: none, .env asli tetap ada.
- Ruling: file Task 1-8 uncommitted DIPERTAHANKAN sebagai baseline (aturan Roy "review semua, perbaiki yang salah"), tapi WAJIB lolos verifikasi per-task sebelum dicommit. TDD RED tidak bisa direproduksi untuk kode yang sudah ada → ekivalensinya: spec-review + full test + ruff, dan task 9-13 tetap full TDD RED-GREEN. — Risk: jika review menemukan cacat, perbaiki via TDD cycle.

## Pre-flight scan (konflik plan vs state)
| Item | Temuan | Ruling |
|---|---|---|
| seed JSON vs plan Task 10 | 10 lokasi SALAH (Depok/Tangerang/Bekasi/Sukabumi/Karawang/Subang, tanpa Semarang/Yogyakarta/Surabaya/Malang/Palembang/Medan yang wajib); shelf_life wortel 30 (plan: 21) | Task 10 wajib rewrite JSON + loader per kontrak plan |
| DB sudah terisi | locations=26 (14 test-rows TEST-LOC/S-BOUND dari test_master_data_schema + 10 seed lokasi lama), supply=14, dsb | Loader idempotent Task 10 wajib menangani reseed: upsert by natural key. Test-rows dibiarkan (dibuat test, bukan seed). Verifikasi "10×3" via payload seed, bukan counts tabel mentah |
| db.py get_db() | masih bikin engine per-request (plan Task 11 lakukan refactor lifespan) | Task 11 scope |
| ruff | 8 error (I001 alembic/env.py, E501 migration 002) | Diperbaiki di task terkait; gate akhir = ruff clean |
| TODO.md S1-01..S1-11 | masih Not Started | Task 0 set In Progress (assignee Hermes) |
| CR/LF | docker-compose.yml warning 'version' obsolete | tidak termasuk scope Task 1-13; biarkan |

## Task 0: complete (commit 183da70, docs sync + S1 In Progress + PRD/Architecture role fix)
- Ruling: Schema.md:34 masih role lama (sppg_staff/dinas_admin) = konflik kontrak genuine → DILAPORKAN ke Roy, TIDAK diubah (plan melarang redesign Schema.md).
- Ruling: Roadmap/PRD/Architecture/TODO hit role lama diperbaiki (bukan redesign, wording aktif yang membingungkan implementer).

## Task 1-7 (core engines): complete — verifikasi parent mandiri
- Catatan: reviewer subagent pertama (sa-0-1bb2733c) mati karena 502 provider berulang + max_iterations; TANPA laporan. Ruling: parent verifikasi sendiri (sesuai kontrak plan: laporan subagent bukan bukti final).
- Bukti: 80 test core PASS (temperature 7, freshness 8, safety 11, price 14, logistics 14, constraints 14, forecasting_fallback 12) di container py3.12. Ruff app/core/ = All checks passed. Import fastapi/sqlalchemy/boto3/httpx/random = tidak ada. Matriks wajib plan tercover penuh (45 pasangan logistics, boundary 0.85/0.60/30min/5%/15%, 700kg forecast, usable_until, dsb).
- File sudah masuk git via commit restore 40415ce.

## Task 8 (migration 002 + ORM): complete — verifikasi parent mandiri
- 12 test schema PASS (master + operational). Upgrade→downgrade 001→upgrade head roundtrip OK di DB test terisolasi mealchain_mig_test (lalu di-drop). Check constraints & indeks diverifikasi di pg_catalog. Sudah di git via 40415ce/7c5c1d5.

## Task 9: complete (commit 2e6cbc9) — parent verification
- Gap spec ditemukan & diperbaiki via TDD: kontrak 5 method wajib (get_business_partner, get_product_master ditambahkan), field stock sesuai Skill.md §6 (MatlStkQty/BaseUnit/Batch), unknown plant → list kosong, test string rusak dibersihkan.

## Task 10: complete (commits 7035601 + 81714c7) — parent TDD
- RED terbukti (ModuleNotFoundError app.seed; 8 failed compose contract), GREEN terbukti, idempotency 2× load = identik.
- Ruling Roy: price_signals source = 'supplier_quote' × 3 (kontrak Schema.md menang atas plan).
- Temuan: docker-compose.yml di-disk korup sejak restore 40415ce (3 service, port 5432, mock-sap hilang) — diperbaiki (commit 7035601).
- DB dibersihkan dari data sintetis lama (loader lama + test-rows TEST-LOC); test_master_data_schema dibuat self-cleaning.
- Bug: AsyncSession.merge tidak di-await (diam-diam no-op) — ditemukan via RuntimeWarning, diperbaiki.

## Task 11: complete (commits 3fcd920 + a11c3df) — parent TDD
- Lifespan engine tunggal + get_db dependency (engine per-request dihapus); forecast router sebelum demand generik; source precedence via SQL CASE; 13 test.

## Task 12: complete (commits edbe5a9 + eb207ff) — parent TDD
- Ruling: shelf life = config demo (28/5/21), bukan kolom DB (Schema.md commodities tidak punya kolom itu).
- Ruling: freshness_status bukan kolom DB; persist freshness_score + usable_until, status diturunkan deterministik.
- Loader konversi timestamp_offset_hours → timestamp absolut (deterministik).
- Drift DB dibersihkan: kolom seed_key ada di DB live tapi tidak di git → di-drop.

## Task 13: complete (commits 5abb01f + dedc2ba)
- Acceptance 12 test PASS; fresh verification Task 13 semua exit code tercatat di docs/verification/sprint-1.md.
- 158 passed backend, ruff clean, frontend lint clean, 4 service Up (postgres healthy).
- Blocker terdokumentasi: frontend npm run test (script tidak ada) — lint-only regression cover.

## Final whole-branch review: complete — parent adjudication (breaker)
- Reviewer final (sa-0-968309c9) mati 502 provider ke-4 kali; sempat jalankan pytest+ruff tanpa temuan sebelum mati, tanpa laporan. Sesuai breaker, parent review sendiri: import legacy get_db tidak dipakai (5 router semua pakai dependencies.get_db), tanpa print/TODO/debug di app (print hanya CLI seed output — sesuai kontrak CLI), tanpa secrets di committed files (hit test_environment_contract = SECRET_PATTERNS kontrak, bukan secret), frontend untouched kecuali .eslintrc.json (baru, untuk npm run lint non-interaktif), API surface persis 8 endpoint Sprint 1 + health, live smoke health backend + mock-sap X-Data-Source: MOCK OK.
- catatan minor: frontend/next-env.d.ts auto-generated untracked (biarkan, build artifact).

## SPRINT 1 STOP — menunggu review Roy. Sprint 2 TIDAK dimulai.


