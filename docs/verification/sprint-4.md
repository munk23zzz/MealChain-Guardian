# Sprint 4 Verification — Event 2 & 3, KPI, Rulings, Polish (S4-01..S4-06)

> **Snapshot 10 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

> **ADDENDUM 2026-10-09 (state terbaru, supersede angka di bawah bila
> berbeda):** pasca-final-gate + overhaul visual, angka kini: backend
> **551 passed EXIT=0** (full, 390s, pasca-polish — laporan
> `sprint-4-final-gate.md`), OpenAPI **32 paths** (+`GET /balance/map`),
> FE **95 passed (15 files)** + tsc 0 + lint 0 + build EXIT=0.
> Perubahan visual & peta (arah Roy 2026-10-09): (1) overhaul visual
> menyeluruh — latar abu halus, kartu ber-depth, badge dot-status,
> **filter chip status + count di feed** (EXPIRED tetap tampil —
> traceable, tidak disembunyikan), peta & chart dibingkai panel, angka
> tabular; (2) **peta diganti MapLibre GL sungguhan** (tile raster OSM
> tanpa API key, marker berwarna per status, popup per lokasi) — sesuai
> `docs/design.md` §5, menggantikan versi sementara SVG skematik;
> test `supply-map.test.tsx` diperbarui RED→GREEN (7/7). Semua keputusan
> data lama tetap: 63 keputusan rehearsal DIBIARKAN, EXPIRED tampil.

> Semua angka di bawah adalah hasil eksekusi aktual (fresh run dari working
> tree HEAD `7089bcf`, branch `feature/sprint2-decision-intelligence`,
> 2026-10-08, container mealchain). Tidak ada klaim sukses provider eksternal
> tanpa evidence live; hop yang tidak tersedia dilaporkan jujur sebagai
> UNAVAILABLE/BLOCKED. Status keseluruhan sprint tetap **IN PROGRESS** —
> penandaan selesai oleh Roy (TODO.md).

## Ringkasan gate

| Gate | Hasil | Evidence |
|---|---|---|
| Backend pytest (FULL) | PASS | **546 passed**, 1 warning (pytest-asyncio deprecation, pre-existing) — `/tmp/s4_full_be2.txt` |
| Backend ruff | PASS | `All checks passed!` |
| Frontend vitest | PASS | **80 passed** (12 files) |
| Frontend tsc --noEmit | PASS | exit 0 |
| Frontend lint | PASS | exit 0 |
| docker compose ps | PASS | backend/frontend/mock-sap Up, postgres healthy |
| `/health` unauth | PASS | 200 |
| `/decisions` unauth | PASS (diproteksi) | **401** |
| OpenAPI vs routes | PASS | **31 paths** (dari 26 baseline; +Event 3, +KPI, +approval-summary) |
| Secrets scan | PASS | 0 secret pada tracked files (demo creds by-design; `.env` ignored; **`.env.example` dihapus** sesuai aturan Roy) |
| DB residu test | PASS | suppliers `supplier-*` 0, locations `EV2-*` 0, commodities `komoditas-*` 0, price_signals EV2 0 |
| Migration chain | PASS | 001→008 utuh (`008_rejection_loop` head, tidak berubah di sprint ini) |

## Ruang lingkup Sprint 4 (kontrak plan, arah Roy verbatim)

- **(a) Ruling Owner eksekusi** — dua temuan rehearsal dijadikan kontrak baru:
  1. *Approval summary lintas lokasi untuk approver ke-2*: `GET
     /decisions/{id}/approval-summary` oleh role `VERIFIER_ROLES`
     (sppg_head/sppg_nutritionist) **tidak lagi dibatasi scope lokasi** —
     selaras write path `POST /actions/approve` (yang memang tanpa scope).
     bgn_monitor tetap read-only global. Detail keputusan mengikuti aturan
     yang sama (endpoint lain pada router decisions).
  2. *Pipeline rekomendasi per komoditas*: `POST /balance/analyze` menerima
     body opsional `{"commodity": "..."}` (extra=forbid); pipeline
     (`build_recommendations` → `generate_candidates`) memfilter facts ke
     komoditas tersebut **sebelum** scoring/ranking. Tanpa body = perilaku
     lama (global). FE selalu mengirim komoditas panel.
- **(b) S4-06 tanpa video fallback** — dokumen evidence ini + redaksi secrets.
- **(c) Polish UI/UX per role** — pengerjaan setelah dokumen ini; tidak
  di-cover angka di bawah kecuali disebut eksplisit.

## Bukti per slice (hasil aktual, bukan narasi)

- **S4-01 Event 2 (price anomaly) E2E**: service + API + panel live. Live
  rehearsal: telur Jakarta −0,98% normal (review-only, **tanpa decision
  row**); ayam Bogor +0,79% normal (tanpa decision row); TTL keputusan
  EXPIRED tampil di feed. Test: `test_event2_service.py` (5) +
  `test_event2_api.py` (7) — kini dengan cleanup fixture FK-safe (lihat
  "Temuan higienitas").
- **S4-02 Event 3 (safety disruption → reroute)**: `POST
  /events/safety-disruption` live: batch Surabaya 90 menit excursion → FAIL →
  revised 201 (4 keputusan PROPOSED); batch ayam Semarang 3,8–4,0°C tanpa
  excursion → `no_disruption` 200 deterministik (tanpa decision). UI trigger
  menunggu ruling boundary (rehearsal via API resmi — tidak dibuat diam-diam).
- **S4-03 KPI Dashboard 7 KPI**: `compute_kpis` core deterministik + API
  envelope + `KPIDashboard` FE. Backend test KPI 20/20; FE 7/7. Live probe:
  7 metrik jujur (2 unavailable dengan alasan + 4 belum ada data; tidak ada
  fake 0). OpenAPI 31 paths.
- **S4-04 Approval Modal ringkasan lengkap**: read model server-side
  (approval_summary), `can_execute` + `blocking_reasons` server, `can_approve`
  independen (fix p10: gate tombol Setuju = `can_approve`, TDD 8/8), format
  id-ID. FE suite penuh 80/80 setelah invariant update (Trap 7.4: test lama
  mem-pin bug gate `can_execute`).
- **S4-05 Rehearsal 3 putaran + putaran 4 (ruling)**: browser nyata
  localhost:3000, DEMO_MODE=true selama rehearsal:
  - Putaran 1 (sppg_head · telur · Jakarta): SHORTAGE 780 kg → 14 kandidat →
    propose 492 kg PENDING APPROVAL; bug approval modal ditemukan + fixed
    TDD; retest UI POST approve 200; matrix AND satisfied; execute
    fail-closed 409 (verifier UNAVAILABLE).
  - Putaran 2 (ayam · Bogor): Event 2 +0,79% normal tanpa decision row;
    Event 3 batch aman → `no_disruption`.
  - Putaran 3 (per-role): nutritionist approve cross-region tercatat (sebelum
    ruling: API 200 tapi summary 403 — dipicu ruling); bgn_monitor
    read-only (tombol mutasi tidak dirender, KPI scope global).
  - **Putaran 4 (bersih, ruling aktif)**: panel **ayam** + "Jalankan analisis
    agent" → "Agent menemukan **0 kandidat**" (sebelum ruling: 14 kandidat
    telur global — bug komoditas); panel telur → 14 kandidat telur; Ajukan →
    decision `4121eb7b` **commodity=telur, 492 kg** (konsisten panel).
    Approve 1 (sppg_head, UI) → approve 2 (sppg_nutritionist, UI, **baca
    summary + setuju lintas lokasi Bogor→Jakarta LOLOS**) → DB: 2 rows
    `approved=true` (`ba9dea0d` sppg_head, `54c215d8` sppg_nutritionist).
- **Ruling TDD**: `test_s4_rulings_tdd.py` 6 test — RED fresh terobservasi
  (5 FAILED = 2×403 scope lama + 3×TypeError `commodity`; 1 guard lama
  PASSED) → GREEN. Test invariant lama yang mem-pin kontrak pra-ruling
  diperbarui (Trap 7.4, RED fresh masing-masing): `test_s4_sec_guards.py`
  (detail read lintas lokasi kini 200 untuk VERIFIER_ROLES; monitor 403
  tetap) + `test_approval_summary.py` (summary lintas lokasi kini 200).

## Temuan & tindakan (S4-06 scope)

- **Temuan higienitas test (akar 6 failure full-suite)**:
  `test_event2_service.py` / `test_event2_api.py` seed lokasi/komoditas/
  supplier/price_signals **tanpa cleanup** sejak p4 — residu mematahkan test
  kontrak dataset lain saat full suite (price_regional_seed, supplier FK,
  sprint1 acceptance). Fix akar: `_cleanup_pair` FK-safe (agent_traces →
  decision_evidence → approvals → sap_mock_purchase_orders → decisions →
  price_signals → suppliers → locations → commodities, dikunci nama unik
  op_key) + fixture `event2_pair` + helper `mk_pair(request, df)`; 8 call
  site + 7 signature test API di-update. Verifikasi: 10/10 passed + residu
  **0** di 4 tabel; full suite 6 failure → **546 passed**.
  Residu historis (27 suppliers + 54 price_signals + 6 decisions komoditas
  test) dihapus via SQL tercatat (BEGIN…COMMIT, FK-safe, count verifikasi 0).
- **DEMO_MODE lifecycle**: `true` selama rehearsal (ruling Owner) →
  dikembalikan **`False`** byte-presisi (python replace 1 hit, verifikasi
  panjang) → `docker compose up -d --force-recreate backend` → `printenv
  DEMO_MODE` = `False`, health 200. Efek samping test yang mem-pin
  DEMO_MODE=false (`test_api_domain_tools.py::freshness_as_of`) kembali
  hijau tanpa perubahan test.
- **Redaksi secrets**:
  - `.env` tetap git-ignored; `.env.example` **dihapus dari repo** (aturan
    Roy: "secrets hanya di .env, tanpa .env.example") + `.gitignore` kini
    juga menolak `.env.example`. Isi file sebelumnya placeholder-only
    (0 secret) — dihapus untuk kepatuhan aturan, bukan karena bocor.
  - Scan tracked files: pola `Demo#…`, `AKIA…`, private key, `Bearer eyJ`,
    `postgresql+psycopg://…:…@`, `sk-…` → hanya demo creds by-design
    (`seed_data.py`, test files, quick-login UI `page.tsx` — dataset
    kompetisi publik, bukan secret produksi) dan conftest (password demo
    untuk login JWT fixture asli). 0 secret produksi.
  - Kredensial demo di dokumen ini **tidak dicetak** (lihat seed_data.py).

## Konfigurasi provider (state aktual, semua nilai [REDACTED])

- Bedrock: LIVE via profile inference (dibuktikan S3-00; AgentCore Runtime
  invoke PONG 200 dari host — bukti penuh di sprint-3.md).
- AgentCore Memory: **AccessDenied** pada rehearsal → verifier UNAVAILABLE →
  matrix AND aktif (fail-closed benar, dikonfirmasi 409 execute).
- SAP AI Core: partial (mock berlabel `MOCK`).
- DEMO_MODE: `False` (state final; hanya membuka override freshness `as_of`).

## Blockers (jujur)

- UI trigger Event 3 + policy "siapa boleh trigger" menunggu ruling boundary
  (rehearsal memakai API resmi).
- KPI Meal Continuity & Avoidable Food Loss: unavailable/belum ada data
  (disposal event tidak ada di schema) — ditampilkan jujur, tanpa fake 0.

## Residual debt (terbarui 2026-10-08)

- pytest-asyncio deprecation warning (pre-existing, non-blocking).
- `s4_*` artifact di `/tmp` host (bukan repo).
- Perubahan sprint 4 belum di-commit (Roy yang memutuskan commit; working
  tree berisi perubahan S4 penuh + rulings + polish berikutnya).

## Catatan repro (angka di atas)

```bash
docker compose exec -T backend python -m pytest -q --no-header   # 546 passed
docker compose exec -T backend ruff check .                      # All checks passed!
docker compose exec -T frontend npx vitest run                   # 80 passed (12 files)
docker compose exec -T frontend npx tsc -p tsconfig.json --noEmit  # exit 0
docker compose exec -T frontend npm run lint                     # exit 0
curl -s http://localhost:8000/openapi.json | jq '.paths | length'  # 31
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/decisions  # 401
```
