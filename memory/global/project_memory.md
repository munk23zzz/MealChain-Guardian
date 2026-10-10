# MealChain Guardian — Project Memory

> Sumber kebenaran kedua setelah `TODO.md`. Baca file ini sebelum eksekusi build apapun
> agar tidak bingung lintas sesi. Update setiap ada keputusan/temuan baru.

## Identitas proyek
- MealChain Guardian — agentic AI untuk cross-regional food supply balancing.
- Kompetisi: Sokrates x SAP x AWS (finalist).
- Stack: Python 3.12 + FastAPI + SQLAlchemy/Alembic + PostgreSQL 16; Next.js 14 + TypeScript + Vitest; Docker Compose.
- Agent layer: Strands SDK + Amazon Bedrock AgentCore (Runtime/Gateway/Memory/Observability).

## Aturan hidup & mati (lihat Rules.md untuk detail)
- LLM TIDAK PERNAH menghitung angka safety-critical — selalu lewat tool deterministik.
- Tidak ada auto-execute aksi berisiko tinggi tanpa human approval (4-eyes).
- Safety status PASS/FAIL/NEEDS_VERIFICATION tidak pernah di-override.
- Label `SAP-RPT-1.6` / `MOCK` hanya untuk response asli — anti-fabricate bukti.
- Secrets hanya di `.env` (TANPA `.env.example` — sudah dihapus & digitignore).
- `TODO.md` diupdate SETIAP status berubah; sprint ditandai Done oleh Roy.

## Fakta environment (terverifikasi)
- `POSTGRES_PORT=15432` (bukan default 5432).
- Docker compose 4 service: backend, frontend, postgres, + health check.
- Freshness bands: fresh ≥ 0.85 / 0.60; price deviation 5% / 15%; safety TTL 30 mnt.
- Harga: source `pihps_reference|supplier_quote` + `supplier_id` FK; supplier lokal 10 kota.
- 3 role: `sppg_head`, `nutritionist` (sppg_nutritionist), `bgn_monitor` (read-only 403).
- RBAC legacy Sprint 1/2 ditutup: baca=JWT valid, mutasi=sppg_head/nutritionist.
- Password akun demo: lihat `seed_data.py` (jangan ditulis di sini).
- boto3 di container tidak kenal `bedrock-agentcore` → probe AgentCore dari HOST.
- `agent/` root DI LUAR bind-mount container → kode agent ditaruh di `app/services/` & `app/ai_providers/`.
- Patch only (jangan write_file wipe) untuk file yang rawan: security.py, MANUAL_SETUP.

## Status per 2026-10-10
- Sprint 0–3: DONE (final gate PASS, lihat `docs/verification/sprint-3.md`).
- Sprint 4: IN PROGRESS — final gate LOLOS (backend 567, FE 107, map MapLibre, KPI live,
  paket integrity 1–6: Merkle ledger, dossier, ECDSA signing, chaos sliders, telemetry banner, KPI facts).
- Sprint 5 (Real SAP via AWS for SAP MCP Server): ON-DEMAND, semua Not Started.
- Baru ditambahkan: S4-10 (SAP AI Core: RPT-1.6 + Verifier primary), S4-11 (Settings/Admin, eks BL-01).

## Paket akses SAP yang diterima (2026-10-10)
- SAP AI Core — Access to RPT 1.6 (model forecast terstruktur, butuh plan extended).
- SAP AI Core — Access to general 40+ (LLM untuk slot primary Verifier).
- SAP Joule Orchestrator chat UI → talking point SAJA, bukan integrasi.
- SAP AI Launchpad → console admin: deployment RPT-1.6, monitor usage token.
- Kredensial `SAP_AI_CORE_*` di `.env` masih kosong → verifier/forecast jalan via fallback (by design).

## Pintasan ke catatan lain
- [[architecture]] — peta arsitektur & keputusan teknis
- [[decisions]] — log keputusan bertanggal (ADR ringkas)
- [[active-context]] — kondisi kerja saat ini & next step
