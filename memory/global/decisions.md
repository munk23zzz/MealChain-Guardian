# Decisions — MealChain Guardian (log ADR ringkas)

> Format: `[YYYY-MM-DD] Keputusan — alasan — dampak`. Append ke bawah, jangan edit baris lama.
> Keputusan permanen; kondisi kerja harian ada di [[active-context]].

---

- [2026-10-05] Sprint 2 dieksekusi via plan terkunci `.hermes/plans/2026-10-05-sprint2-decision-intelligence.md` — item Roadmap di luar plan = carry-over eksplisit, bukan kegagalan. — diperjaskan ruang lingkup sprint.
- [2026-10-06] Opsi A SDC dikunci — endpoint `/cost/safe-delivered` standalone jadi carry-over plan-binding. — mengunci desain balancing engine.
- [2026-10-06] Kode agent ditaruh di `app/services/` & `app/ai_providers/`, BUKAN `agent/` root — `agent/` di luar bind-mount container. — lokasi file agent layer.
- [2026-10-06] Chain model frontier-first: Bedrock Claude → Astra → Claude-5.5 → Claude-5 → kimi-k3 → qwen TERAKHIR; AgentCore Runtime (ARN terisi) jadi primary, chain total 7. — Revisi 2 arah Roy.
- [2026-10-07] Verifier REST client (bukan agent Strands kedua); UNAVAILABLE → syarat dual approval (fail-closed). — desain verifier.
- [2026-10-07] Rejection WAJIB alasan (422 bila kosong) → re-propose via `supersedes_id` + trace LEARN; chain v1→v2→v3 via `GET /decisions/{id}/chain`. — Revisi 8.
- [2026-10-07] CORS allow-list eksplisit localhost:3000/127.0.0.1:3000 — fix "Failed to fetch". — Revisi 7.
- [2026-10-07] AgentCore Gateway LIVE (gateway READY; verifikasi via get_gateway by ID — quirk `list_gateways` count=0). — Revisi 6.
- [2026-10-08] RBAC guard di SEMUA endpoint incl. 13 endpoint legacy Sprint 1/2 (Revisi 10, TDD); final gate Sprint 3 PASS → Sprint 3 DONE. — penutupan Sprint 3.
- [2026-10-09] Overhaul visual: latar abu + kartu depth + filter chip status; MapLibre GL (tile OSM raster, tanpa API key) menggantikan peta SVG skematik. — keputusan Roy.
- [2026-10-09] Navigasi direstrukturisasi ke 5 tab PRD 2.4 (Overview/KPI/Recommendations/Agent Log/Demo Control approver-only); persona label = judul resmi PRD §2. — keputusan Roy.
- [2026-10-09] Komponen kripto PRD (Polygon/IPFS/Merkle/FIDO2 versi PRD) & chaos sliders backend TIDAK dibuat — arsitektur & backend tetap keputusan terakhir. — boundary PRD vs implementasi.
- [2026-10-09] Paket integrity & KPI disetujui Roy: P1 Merkle ledger append-only + `GET /ledger/verify`; P2 dossier SHA-256 `mc1-`; P3 ECDSA secp256k1 per approval (`SIGNING_KEY_HEX`, tanpa kunci = `unsigned` jujur); P4 chaos sliders via API resmi; P5 telemetry banner jujur; P6 tabel facts KPI (Meal Continuity & Avoidable Food Loss LIVE). — Sprint 4.
- [2026-10-09] REF seed canonical = 2026-10-08 12:00 UTC (ruling Roy) — dataset demo ter-anchor di situ; REF lain menduplikasi baris. — penting untuk seed/test.
- [2026-10-09] Video fallback DIBATALKAN (waived Owner) — evidence dokumen saja. — S4-06 tanpa video.
- [2026-10-10] Desain Stitch (7 layar) diadaptasi VISUAL-ONLY via token CSS `globals.css` (palet teal #005c55/#0f766e/#0F172A/#2DD4BF) — struktur komponen & kontrak API TIDAK diubah. — S4-09.
- [2026-10-10] Paket akses SAP diterima (RPT-1.6, general 40+, Joule, AI Launchpad) → S4-10 dibuat. SAP AI Core = jalur "real SAP" yang murah & independen; S/4HANA cloud (mahal) dikeluarkan dari rencana. "Real SAP" = model AI nyata (RPT-1.6 forecast + LLM AI Core verifier primary), data tetap mock. Joule = talking point saja. — arah Roy via diskusi sesi ini.
- [2026-10-10] BL-01 (Settings/Admin screen) naik ke Sprint 4 sebagai S4-11. — arah Roy.
- [2026-10-10] Vault Obsidian MealChain dibuat di `memory/` (pola sama dgn AI-TIOS) sebagai memory build lintas sesi; TODO.md tetap primary untuk status task. — keputusan sesi ini.
- [2026-10-10] Supplier exclusion lokal per SPPG, aktif sampai dicabut melalui keputusan pemulihan berbukti dan approval baru; batch safety `FAIL` tetap tidak eligible. — scope administratif tidak melemahkan safety.
- [2026-10-10] Adopsi selektif Nabil selesai untuk A/B/C/D1/D2 tanpa transplant frontend: Overview mempertahankan desain MealChain/Stitch, SAP mock tetap default dan mode real unsupported fail-closed, evidence/export memakai dossier tersimpan dan authorization. — S4-09d.
