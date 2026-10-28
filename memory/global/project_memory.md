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

## Status per 27 Okt 2026 (Fase 12 MG — dokumentasi & geladi)
- Sprint 0–3: DONE. Sprint 4–5 dikerjakan ulang lewat rencana MG (`MG/overview.md`, 12 fase);
  status per-butir ada di `MG/phase-*-*.md`, bukan di berkas ini.
- Fase 1–12 MG: kode + tes per butir sudah ada dan dijalankan; bukti geladi dua jalur demo
  (replay / realtime / operasional) ada di `MG/phase-12-docs-rehearsal.md`.
- Status kerja memakai `OPEN` / `IN PROGRESS` (bukan `BLOCKED`); yang belum terbukti ditulis
  apa adanya, mis. integrasi Gateway AgentCore dan tenant SAP S/4HANA.
- Yang **belum** aktif dan tidak boleh diklaim: Gateway AgentCore (`integrasi_aktif=false`),
  tulis-baca Memory ke AWS (AccessDenied), tenant S/4HANA/ECC, Joule sebagai kanal transaksi.

## Joule — status jujur
- Joule membaca **backend MealChain** lewat jembatan A2A `sap-joule/a2a_server` (13 skill);
  ia **bukan** kanal transaksi ERP dan **tidak** menyetujui keputusan (permintaan approval
  dijawab dengan arahan ke cockpit).
- Jembatan CF `mealchain-joule-bridge-4sehat3trio` hidup dan `/health` menjawab, tetapi
  `backend.reachable=false` (host backend AWS lama tidak resolve). Uji fungsional dilakukan
  pada jembatan lokal yang menunjuk backend sesi — lihat `MG/phase-12-docs-rehearsal.md`.
- Tenant SAP/Joule (BTP destination, `joule list`) — `INCONCLUSIVE`, bukan sukses.

## Paket akses SAP yang diterima (2026-10-10)
- SAP AI Core — Access to RPT 1.6 (model forecast terstruktur, butuh plan extended).
- SAP AI Core — Access to general 40+ (LLM untuk slot primary Verifier).
- SAP Joule Orchestrator chat UI → **dipakai lewat jembatan A2A** `sap-joule/a2a_server` (13 skill,
  baca-saja ke backend MealChain). Bukan kanal transaksi ERP; tenant/destination BTP belum
  diverifikasi ulang (INCONCLUSIVE per 27 Okt 2026).
- SAP AI Launchpad → console admin: deployment RPT-1.6, monitor usage token.
- Kredensial `SAP_AI_CORE_*` di `.env` masih kosong → verifier/forecast jalan via fallback (by design).

## Pintasan ke catatan lain
- [[architecture]] — peta arsitektur & keputusan teknis
- [[decisions]] — log keputusan bertanggal (ADR ringkas)
- [[active-context]] — kondisi kerja saat ini & next step
