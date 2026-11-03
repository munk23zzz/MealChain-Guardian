# Architecture — MealChain Guardian (ringkasan working memory)

> Ringkasan praktis untuk agent yang build. Sumber lengkap: `docs/Architecture.md`, `docs/Schema.md`, `docs/Skill.md`.

## Alur data
```
Frontend (Next.js :3000) → FastAPI (:8000, JWT+RBAC)
  → deterministic core (freshness/safety/cost/logistics — angka safety-critical DI SINI)
  → SAPDataProvider (factory.py baca SAP_MODE=mock|aws_mcp)
      ├─ MockSAPProvider → tabel sap_mock_* (Postgres)
      └─ AwsMcpSapProvider → AWS for SAP MCP Server → S/4HANA (Sprint 5 ON-DEMAND, stub)
  → Agent layer: Supervisor (satu-satunya full LLM, AgentCore Runtime via Strands)
      chain: agentcore primary → Bedrock Claude → Inferhub fallbacks (6 slot env/agent)
      Verifier = REST model call: sap_ai_core_primary → sap_ai_core_fallback → bedrock_final
      Forecast = SAP-RPT-1.6 → statistical_fallback 0.5/0.3/0.2
  → Approval flow 4-eyes: PROPOSED → PENDING_APPROVAL → (verify) → execute → PO mock SAP
  → Persistence: decisions, agent_traces, ledger_blocks (Merkle), dossier SHA-256
```

## Struktur folder penting
- `backend/app/core/` — deterministic core (JANGAN lewati dari LLM)
- `backend/app/sap_integration/` — provider_interface (kontrak 5 method), mock_provider, aws_mcp_provider (stub NotImplementedError)
- `backend/app/services/` — event1_orchestrator, event2/3_service, kpi, ledger_service, trace_persistence
- `backend/app/ai_providers/` — verifier_client, forecast_client, resilience (`with_fallback_chain`), prompts/
- `backend/app/api/` — router; openapi.json auto-generate (siap register ke Gateway)
- `frontend/` — Next.js; token visual di `globals.css` (palet teal Stitch); 11 item navigasi konsol (2 di antaranya bersyarat peran), bukan lagi 5 tab PRD.

## Database (Schema.md)
- Alembic head per 27 Okt 2026: **`043_least_privilege_app`** (43 migrasi). Rincian kolom/tabel ada di `docs/Schema.md`; angka operasional di `docs/state-snapshot.md`.
- Ledger **append-only ditegakkan database**: role aplikasi hanya `INSERT`/`SELECT`, trigger `prevent_ledger_mutation()` menolak UPDATE/DELETE (migrasi `042`).
- REF seed canonical: 2026-10-08 12:00 UTC (stable_uuid bergantung REF) = jangkar mode **replay**.
- Tiga mode waktu: `replay` (jangkar kanon), `realtime` (jangkar sesi), `operasional` (`DEMO_MODE=false`, seluruh `/demo/*` 404).

## Endpoint utama (81 path / 83 operasi di `backend/openapi.json`)
- `/supply/*`, `/demand/*`, `/freshness/evaluate`, `/safety/evaluate`, `/price/*`, `/logistics/estimate`
- `/cost/safe-delivered`, `/balance/analyze|recommend|map`, `/evidence/fuse`
- `/actions/*` (propose/verify/approve/execute), `/decisions/*` (+packet, chain, dossier, traces, approval-summary)
- `/kpi`, `/ledger/verify`, `/sap/purchase-orders*`, `/supplier-routes`, `/receipts*`, `/procurement/summary`
- `/demo/*` (seed, session start/extend/end, template/rebuild, data-status) — tertutup bila `DEMO_MODE=false`
- `/auth/*`, `/admin/*`, `/health`

## Quirk teknis yang sudah membakar waktu (jangan ulangi)
- `agent/` root DI LUAR bind-mount → jangan taruh kode baru di sana.
- boto3 container tidak kenal `bedrock-agentcore` → probe AgentCore dari HOST.
- `list_gateways` AgentCore quirk count=0 → verifikasi gateway via get_gateway by ID.
- CRLF `.env` di Windows — hati-hati append.
- Inferhub prefix valid: `cb/`, `cx/`, `cc/`, `cbcn/`, `ali/` (503 ronde-1 bisa transien).
