# Active Context — MealChain Guardian

> Satu file yang dibaca PALING AWAL tiap sesi build. Update tiap akhir sesi / tiap perubahan arah.
> File ini menjawab: "sekarang lagi di mana, next step apa, jangan sentuh apa."

## Kondisi saat ini (2026-10-10)
- Sprint 4 IN PROGRESS — Roy yang menandai DONE, jangan ditandai agent.
- Final gate Sprint 4 sudah LOLOS; sisa kerja: S4-10 (SAP AI Core) & S4-11 (Settings/Admin).
- S4-09d execution complete for A/B/C/D1/D2: Overview location breakdown and SAP adapter contract; supplier exclusion migration/eligibility/approval/restoration guards; evidence read-only panel and authorized JSON/CSV export. Final verification evidence is recorded below.

## Next step (urutan eksekusi)

➡️ **Onboarding dev2 (Nabil): mulai dari `ONBOARDING.md` di root repo** — panduan lengkap
clone → restore dump → verifikasi → akun demo → aturan → task → alur git.

1. **S4-10** — Hidupkan SAP AI Core:
   - Isi `SAP_AI_CORE_AUTH_URL/API_URL/CLIENT_ID/SECRET` dari service key paket.
   - Cek plan AI Core = **extended** (syarat RPT-1.6, varian rilis 7 Sep 2026).
   - Di AI Launchpad → generative AI hub → Model Library → deploy SAP-RPT-1.6.
   - Isi HTTP client stub di `backend/app/ai_providers/forecast_client.py` + `verifier_client.py`
     (OAuth token → endpoint deployment).
   - Probe "pong" → jalankan `test_forecast_client.py` + `test_verifier_client.py` + contract test.
   - Chain Verifier: sap_ai_core_primary → sap_ai_core_fallback → bedrock_final (SUDAH dites, tinggal hidupkan).
   - Data TETAP mock (MockSAPProvider); label `SAP-RPT-1.6` hanya utk response asli.
2. **S4-11** — Settings/Admin screen (eks BL-01): desain bisa dari mockup Stitch, visual-only.

## Jangan disentuh / jangan dilakukan
- Jangan tandai Sprint 4 selesai — milik Roy.
- Jangan buat `.env.example` (sudah dihapus permanen, aturan secrets).
- Jangan stop/restart container tanpa cek bind-mount dulu (app bind-mounted → restart cukup).
- Jangan ubah angka/label safety-critical di UI tanpa jalur core deterministik.

## Keputusan terakhir yang mengubah arah
- 2026-10-10: paket akses SAP diterima → S4-10 dibuat; SAP AI Core = jalur murah tanpa
  sewa S/4HANA (cloud ERP mahal, dikeluarkan dari rencana — "real SAP" = model AI nyata,
  data tetap mock sampai Sprint 5 ON-DEMAND).
- 2026-10-10: BL-01 naik ke Sprint 4 sebagai S4-11.
- 2026-10-09: navigasi 5 tab PRD 2.4 + MapLibre GL + paket integrity 1–6.

## Vault map
- [[project-memory]] — fakta proyek & aturan hidup-mati
- [[decisions]] — log keputusan bertanggal
- [[architecture]] — peta arsitektur & struktur folder

## Verifikasi S4-09d (2026-10-10)
- Frontend: Vitest 138 passed; TypeScript, lint, dan production build exit 0.
- Backend: pytest 595 passed; Ruff clean; Alembic current/head `011_supplier_exclusions`.
- Approval summary now shares authoritative batch→supplier binding with execute; unbound legacy decisions remain blocked. Harvests newer than captured `as_of` are excluded at the SQL boundary.
- Runtime: `/health` 200; unauthenticated compliance probe 401.
- Browser Playwright fresh: tiga role × 375/768/1440 px, 10 location rows, document width sama viewport; late commodity response tetap menampilkan wortel.
- SAP real tidak diaktifkan; mock default dan unsupported mode fail-closed.
