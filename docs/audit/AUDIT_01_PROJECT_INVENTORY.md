# AUDIT_01 — Inventaris Proyek

- Proyek: mealchain-guardian (MealChain Guardian)
- Path: `E:\hackathon\HackathonAWS\mealchain-guardian`
- Branch: `feature/db-modes-demo-coverage`
- HEAD: `d414957aa366798c09e296d358e76dfd64018c7f` — "deploy: verifikasi stack produksi penuh + perbaiki dua bug yang terbongkar" (2026-10-25 03:50 +0700)
- Working tree saat audit dimulai: **104 entri belum di-commit** (perubahan lokal dipertahankan; tidak ada `git stash`/checkout yang menghapus pekerjaan)
- Tanggal audit: 26 Oktober 2026, 07:00–09:00 WIB
- Database kerja: `mealchain` di container `mealchain-postgres` (PostgreSQL 16.15)

## 1.1 Struktur repository

| Bagian | Isi |
|---|---|
| `backend/` | FastAPI, 34 modul router (`app/api/*.py`), 33 migrasi Alembic, 237 berkas tes |
| `frontend/` | Next.js 14.2.14 App Router, satu halaman (`app/page.tsx`) dengan 10 tab, 166 berkas tes (1793 tes) |
| `agent/`, `sap-joule/`, `mockupui/` | agen, integrasi SAP/Joule, mockup |
| `data/`, `scripts/`, `infra/` | seed & data kanonik, skrip operasional, infra |
| `verify/` | suite verifikasi stack (spec JSON + artefak hasil) |
| `docs/` | PRD, Architecture, Schema, design, Skill, kamus KPI, qa, verification, security |
| `memory/` | vault Obsidian (MOC, decisions, active_context) |

## 1.2 Dokumen otoritas yang dibaca

Urutan wajib dari `AGENTS.md`: `IDEA.md` → `TODO.md` → `Rules.md` → `workflows.md` → `Roadmap.md` → `docs/{PRD,Architecture,design,Schema,Skill}.md`.

Laporan audit lama yang ditemukan dan dipakai sebagai pembanding (bukan sumber kebenaran):

- `AUDIT.md`
- `PROJECT_AUDIT_REPORT.md`
- `INDEPENDENT_PROJECT_REVIEW.md`
- `DATABASE_LINEAGE_AND_USAGE_AUDIT.md`
- `FINAL_VERIFICATION_REPORT.md`, `REPAIR_LOG.md`, `REPAIR_PLAN.md`
- `docs/qa/`, `docs/verification/`, `docs/security/`
- Laporan sesi ini: `DEMO_DATABASE_KPI_WORKFLOW_REPORT.md`, `docs/kamus-kpi-dan-state-machine.md`

## 1.3 Runtime aktual (terukur, `docker ps`)

| Container | Status | Port |
|---|---|---|
| `mealchain-backend` | Up 4 jam (healthy) | 8000 → 8000 |
| `mealchain-frontend` | Up 13 jam (healthy) | 3010 → 3000 |
| `mealchain-mock-sap` | Up 13 jam | 8001 → 8001 |
| `mealchain-postgres` | Up 13 jam (healthy) | 15432 → 5432 |

Tambahan di host (bukan bagian MealChain): `adaptiv_db` (5433), `adaptiv_redis` (6379).

Versi: Python 3.12.15 (container), Node 25.9.0 (host), Next 14.2.14, React 18.3.1, Postgres 16.15.

Dependensi utama frontend: `@tanstack/react-query` 5.56.2, `maplibre-gl` 4.7.1, `recharts` 2.12.7.

## 1.4 Permukaan API

- `backend/openapi.json`: **75 path, 77 operasi**.
- Router: 34 modul (`app/api/*.py`), antara lain `actions`, `decisions`, `kpi`, `receipts`, `batches`, `demo`, `demo_session`, `admin`, `ledger`, `supplier_routes`, `safety`, `quarantine`, `waste`, `surplus`.
- Kelompok endpoint: aksi keputusan (`/actions/{propose,verify,approve,execute,repropose}`), demo (`/demo/*` 12 endpoint), admin (4), KPI (1), ledger (1), penerimaan (4), batch (3), keputusan (6).

## 1.5 Database

- 24 tabel: `agent_traces, alembic_version, approvals, batch_receipts, batches, commodities, decision_evidence, decisions, delivery_events, demand_records, demo_sessions, disposal_events, ledger_blocks, ledger_meta, locations, menu_plans, price_signals, road_routes, sap_mock_material_stock, sap_mock_purchase_orders, supplier_exclusions, suppliers, supply_records, users`.
- Migrasi: 33 revisi, head **`033_indeks_fk_hilang`** (terverifikasi `alembic current`).
- Data kerja (26 Okt 07:21 WIB): decisions 36, approvals 12, PO 16, batches 120, receipts 2, demo_sessions 1 (aktif), traces 85, ledger_blocks 805, users 7, menu_plans 660, delivery_events 180.

## 1.6 Konfigurasi environment

`.env` memuat 43 kunci (nama saja, nilai tidak dilaporkan): kredensial Postgres, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, kunci AWS/AgentCore, kredensial SAP AI Core, `VERIFIER_MODEL_PRIMARY`, `DEMO_MODE`, `DEMO_SESSION_{ENFORCE,MINUTES,MAX_MINUTES}`, `DB_MODE`, `SIGNING_KEY_HEX`, `MEALCHAIN_API_TOKEN`.

`.env` **tidak dilacak git saat ini** (`git ls-files .env` = 0), tetapi pernah masuk riwayat (commit `8f95c98` "keluarkan .env & artefak lokal dari git") → rotasi kredensial masih wajib (lihat AUDIT_08).

## 1.7 Tes & CI

| Kategori | Jumlah | Catatan |
|---|---|---|
| Backend pytest | 237 berkas | `pytest` dijalankan di container `mealchain-guardian-backend` dengan bind mount |
| Frontend vitest | 166 berkas / 1793 tes | dijalankan di host |
| CI | `.github/workflows/ci.yml` | backend (ruff + pytest di Postgres bersih) dan frontend (lint/tsc/vitest) |
| Gate stack | `verify/*.spec.json` | stack, roles, invariants, tabs, decisions (write-flow) |

Penanda yang ditemukan: 26 `TODO/FIXME` di kode aplikasi, 6 `pytest.mark.skip/xfail` di backend, 0 `test.skip` di frontend.

## 1.8 Alur autentikasi & otorisasi

- `POST /auth/login` (JWT), `GET /auth/me`.
- Peran: `sppg_head`, `sppg_nutritionist`, `bgn_monitor`, plus peran admin/pengawasan (`MANAGE_ROLES`) dan `SURPLUS_ROLES`.
- Scope lokasi ditegakkan di backend (`app/core/scope.py`, `apply_location_scope`), bukan hanya UI.
- Middleware sesi demo (`app/main.py`) menolak mutasi tanpa sesi aktif saat `DEMO_SESSION_ENFORCE=true`.

## 1.9 Background job / event

- Tidak ada message queue atau worker terpisah. Pemrosesan terjadi di request path.
- Notifikasi adalah **daftar turunan** dari `GET /decisions` (`frontend/lib/topbar.ts`), tanpa tabel notifikasi dan tanpa read-state.
- Tidak ada scheduler; sesi demo kedaluwarsa dinilai saat request (bukan oleh timer proses).

## 1.10 Celah dokumentasi yang dicatat

1. `docs/Skill.md` dan kode berbeda pada definisi beberapa KPI (Meal Continuity "terpenuhi aman", Avoidable Food Loss, Safe Delivered Cost) — dirinci di AUDIT_02 dan `docs/kamus-kpi-dan-state-machine.md`.
2. Dokumen lama menyebut tabel `ledger`; nama aktual `ledger_blocks` + `ledger_meta`.
3. Proposal kompetisi tidak ada di repo (hanya `IDEA.md` + `docs/PRD.md`); requirement bisnis diambil dari keduanya.
4. Tidak ada dokumen SLA performa resmi → baseline diukur, bukan dibandingkan target.

## 1.11 Git status (ringkas)

104 entri berubah/tak terlacak, mencakup pekerjaan sesi ini (KPI periode, sesi demo 2 jam, migrasi 032/033, tes baru, dokumen kamus KPI) dan pekerjaan sebelumnya (refactor `safety_gate`, panel demo). Tidak ada perubahan yang dibuang.
