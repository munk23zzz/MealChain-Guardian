# PROJECT AUDIT REPORT — MealChain Guardian

> **Snapshot 25 Oktober 2026 (dari waktu berkas)** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

**Tanggal audit:** 2026-10-25 (Asia/Jakarta), sesi lanjutan setelah `INDEPENDENT_PROJECT_REVIEW.md`
**Auditor:** Hermes Agent (lead reviewer) + 2 reviewer independen (access/secrets, infra/docs) yang berjalan paralel
**Sifat dokumen:** baseline temuan **sebelum** perubahan. Tidak ada file proyek yang diubah saat audit ini disusun.

---

## 1. Identitas repository

| Item | Nilai |
|---|---|
| Path | `E:\hackathon\HackathonAWS\mealchain-guardian` |
| Branch | `feature/db-modes-demo-coverage` |
| HEAD | `d414957` — *deploy: verifikasi stack produksi penuh + perbaiki dua bug yang terbongkar* |
| Working tree | **DIRTY**: 7 modified, 38 deleted, 1 untracked (sebelum task ini). Semua dipertahankan. |
| Remote | `origin` = RGjordien/mealchain-guardian; `mirror` = munk23zzz/MealChainGuardian (publik) |
| Stack | FastAPI + SQLAlchemy async + Alembic (head `031`, 23 tabel) · Next.js 14 + TypeScript · PostgreSQL 16 · Docker Compose · agent Python terpisah (`agent/`) |

**File pengguna yang sudah berubah (tidak boleh ditimpa sembarangan):**

```
M backend/alembic/versions/018_agent_trace_worker_fields.py
M backend/app/seed/demo_template.py
M frontend/app/supply-adequacy.css
M frontend/components/SupplyAdequacyChart.tsx
M frontend/next.config.js
M frontend/tests/supply-adequacy-chart.test.tsx
M memory/global/decisions.md
D 38 file (docs/verification/*, docs/qa/*, .hermes/*, backend/calc2.py, docs/superpowers/plans/*)
?? backend/tests/test_demo_template_kesegaran.py
```

Aturan yang diterapkan: tidak ada `git reset/clean/checkout/restore`, tidak ada commit/merge/deploy, tidak ada migrasi atau seed yang dijalankan pada database apa pun.

---

## 2. Skill dan tool — status sebenarnya

| Skill/tool | Sumber | Status | Dipakai untuk |
|---|---|---|---|
| `project-audit`, `codebase-inspection` | skill Hermes terpasang (profil `default`, 142 skill) | **dibaca + dijalankan** | inventaris kode, urutan audit, pygount |
| `test-driven-development` | skill Hermes terpasang | **dibaca** | siklus RED → FIX → GREEN pada §9 prompt |
| `.claude/skills/demo-data-builder`, `.claude/skills/db-mode` | skill lokal repo | **dibaca (inventaris)**, tidak dijalankan | konteks domain demo |
| `npx skills` (Skills CLI, skills.sh/vercel-labs) | terpasang di host | **diperiksa (`--help`)**, tidak dipakai untuk install | discovery; tidak ada skill eksternal yang dipasang |
| `INDEPENDENT_PROJECT_REVIEW.md` (2026-10-25) | dokumen repo | **dibaca sebagai hipotesis**, bukan bukti | daftar temuan awal §7 prompt |
| Reviewer independen V3 (access/secrets), V4 (infra/docs) | subagent terpisah | **dijalankan** (paralel, sesi ini) | verifikasi ulang D-01…D-08, A-09, R-01, lanes, dependency, docs |
| Semgrep | tidak terpasang | **NOT RUN** | — (disebut sebagai keterbatasan) |
| markdownlint-cli2 | tidak terpasang | **NOT RUN** | validasi Markdown dilakukan manual (tabel/fence/anchor) |

Tidak ada skill eksternal yang dipasang: seluruh kebutuhan review sudah tercakup skill lokal + toolchain asli repo. Keputusan ini dicatat agar klaim "skill dipakai" dapat diverifikasi.

---

## 3. Metode

1. **Pass A — discovery:** struktur repo, 33 router (`backend/app/api/*`), 23 model ORM, 30 migrasi (head `031`), `agent/` (7 worker + orchestrator), `frontend/app` + `components`, `docker-compose.yml`/`.prod.yml`, `.github/workflows/ci.yml`, 20 file Markdown proyek.
2. **Pass B — baseline (read-only):** ruff, `tsc --noEmit`, `next lint`, vitest, pytest subset domain, hitungan path/operasi API vs `backend/openapi.json`, hash file yang akan disentuh.
3. **Pass C — reviewer terpisah:** lead reviewer memverifikasi sendiri seluruh item P0/P1 keamanan-keselamatan; dua reviewer independen memverifikasi klaster access/secrets dan infra/docs.
4. **Pass D — laporan ini** + `REPAIR_PLAN.md`.

Setiap temuan diberi status: **CONFIRMED** (dibuktikan di source saat ini), **PARTIAL**, **FALSE POSITIVE**, **NOT PRESENT** (sudah tidak ada), **BLOCKED** (butuh runtime/DB/kredensial).

---

## 4. Baseline gates (sebelum perubahan)

| Gate | Command | Exit | Hasil | Status |
|---|---|---:|---|---|
| Lint backend | `ruff check .` (ruff 0.6.9) | 1 | `alembic/versions/022_disposal_partner.py:17:1 I001` | **FAIL** (1 error) |
| Typecheck FE | `./node_modules/.bin/tsc --noEmit` | 0 | bersih | **PASS** |
| Lint FE | `./node_modules/.bin/next lint` | 0 | `✔ No ESLint warnings or errors` | **PASS** |
| Test FE | `vitest run` | 0 | 166 file / **1794 test lulus**, 38,7 dtk | **PASS** |
| Unit domain BE | `pytest tests/test_freshness.py tests/test_safety.py …` | 0 | **62 passed**, 33,61 dtk | **PASS** |
| Unit domain BE (batch 2) | 11 file core-logic | 1 | **102 passed**, 3 gagal karena `ConnectionRefusedError` (DSN uji sengaja tidak valid) | **PASS (logic) / BLOCKED (3)** |
| Integration DB BE | `pytest tests/test_quarantine_api.py` dll | 1 | `sqlalchemy.exc` — host Postgres tidak terjangkau | **BLOCKED** |
| Suite penuh BE (1496 test) | `pytest -q` | — | menggantung >6 menit (butuh DB); dihentikan | **BLOCKED** |
| Kontrak OpenAPI | hitung route vs `backend/openapi.json` | — | 75 path/77 operasi vs 26/27 → **49 path tak terdokumentasi** | **FAIL** |
| Migration fresh DB | `alembic upgrade head` | — | Docker daemon mati, tidak ada DB disposable | **BLOCKED** |

Keterbatasan environment: Docker daemon **DOWN** dan tidak ada PostgreSQL uji. Semua klaim runtime DB (constraint, migrasi, transaksi, endpoint ber-DB) belum dapat diverifikasi pada audit ini.

---

## 5. Finding register — hasil verifikasi ulang di kode terkini

### 5.1 Critical — keselamatan pangan (diverifikasi lead reviewer)

**F-01 — Penerimaan barang meloloskan status selain `fail`. CONFIRMED**
- Bukti: `backend/app/api/receipts.py:201` → `if str(batch.safety_status).lower() == "fail": raise 409`; tidak ada cabang untuk `pending`, `needs_verification`, `null`.
- Dampak: batch yang belum terverifikasi atau verdict-nya meragukan tetap dapat disetujui → masuk `supply_records`/stok seolah aman.
- Uji hilang: tidak ada test yang menegaskan `needs_verification`/`pending` ditolak pada `POST /receipts/{id}/approve`.

**F-02 — Bukti suhu kosong/tidak lengkap tidak menurunkan skor freshness. CONFIRMED**
- Bukti: `backend/app/core/freshness.py:29-32` → `if summary.observed_minutes > 0 and summary.complete: outside_fraction = ... else: outside_fraction = 0.0`; penalti `TEMP_PENALTY_WEIGHT` menjadi 0 untuk log kosong, sedangkan `backend/app/core/safety.py:22-27` mengembalikan `needs_verification` untuk input yang sama.
- Dampak: dua verdict untuk satu bukti; skor freshness bisa `pass` (≥0.85) tanpa bukti suhu apa pun.
- Uji hilang: `tests/test_freshness.py` tidak memuat kasus log kosong/`complete=False`.

**F-03 — Rentang suhu aman hard-coded 0–8 °C untuk semua komoditas dan menimpa verdict batch. CONFIRMED**
- Bukti: `backend/app/services/event3_service.py:59-60,153-155,269-272` (`safe_min_c=0.0, safe_max_c=8.0` di empat tempat) dan `:157` `batch.safety_status = temp_result["safety_status"]`.
- Tidak ada master data rentang suhu: `grep -rnE "safe_min|safe_max" app/models app/seed` tidak menemukan kolom/seed apa pun.
- Dampak: komoditas kering (beras) dan produk non-chilled dinilai dengan aturan chilled; sebaliknya produk beku dinilai terlalu longgar.

### 5.2 High — integritas gate eksekusi & otoritas angka

**A-01 / F-06 — Gate safety eksekusi terlalu longgar, quarantine diabaikan, expiry ditulis ulang. CONFIRMED**
- Bukti: `backend/app/api/actions.py:327-353` → `_source_batches_still_safe` mengembalikan `True` bila `any((b.safety_status or "pending") != "fail" ...)`, juga `True` bila tidak ada batch sama sekali; tidak memeriksa quarantine/`usable_until`.
- Bukti expiry: `actions.py:321-322` → `if b.usable_until is None or b.usable_until < sekarang: b.usable_until = sekarang + timedelta(hours=6)` (memperpanjang barang kedaluwarsa saat dispatch).
- Dampak: satu batch `pending` di antara banyak batch `fail` cukup untuk meloloskan eksekusi; barang kedaluwarsa "dihidupkan" 6 jam.

**F-09 / A-02 — Angka `quantity_kg`/`safe_delivered_cost` berasal dari caller. CONFIRMED (pada jalur create)**
- Bukti: `backend/app/api/decisions.py:151-152` menyimpan `fields["quantity_kg"]`/`fields["safe_delivered_cost"]` hasil `_extract(payload.recommendation)` langsung ke `Decision`, tanpa recompute/validasi numerik server-side; guard role memakai `DECISION_MUTATING_ROLES` (`:129-131`), bukan `require_roles`.
- Belum terbukti: pemakaian angka tersebut saat pembentukan purchase order (jalur `execute` baris 780+) — **status: OPEN, akan diverifikasi sebelum patch**.

**F-07 — Tidak ada test regresi untuk verifier safety guard. FALSE POSITIVE / NOT PRESENT**
- Bukti: `backend/tests/test_verifier_safety_guard.py` **ada** (tracked) dengan 4 test, termasuk `test_cannot_resurrect_safety_fail`; implementasi guard `backend/app/ai_providers/verifier_client.py:86-102`.
- Konsekuensi: temuan ini dicoret dari rencana perbaikan; tidak ada pekerjaan yang dikarang untuk "memperbaikinya".

### 5.3 Prioritas P0/P1 lainnya — status verifikasi

D-01 (password demo di seed + seed produksi), D-02/F-10 (`/demo/*` destruktif), F-08/D-04 (`bgn_monitor` bisa menulis `/admin/*`), D-08/B-02 (scope `GET /batches`, `GET /receipts?batch_id`), D-03 (rate limit `X-Forwarded-For`), D-06 (port prod terbuka), C-05 (provider exhaustion → 500), C-09 (`safety_veto` vs status `completed`), C-12 (model id tidak tercatat), A-09 (migrasi tidak dijalankan saat start), R-01 (drift OpenAPI), lane topology (`agent/hierarchy.json` vs `LANES` hard-code), advisory dependency, dan drift dokumentasi.

**Koreksi penting setelah membaca kode lebih lengkap (bukan sekadar menyalin review sebelumnya):**

- **D-08/B-02 → turun ke risiko desain yang didokumentasikan.** `backend/app/api/batches.py:48-57` menyatakan eksplisit bahwa daftar batch **sengaja** lintas lokasi (panel chaos Event 3) dan bahwa memfilter per lokasi akan mengosongkan panel untuk SPPG Jakarta. Filter di UI (`FoodSafetyBoard.tsx`) tetap bukan kontrol akses — tetapi mengubahnya adalah keputusan produk, bukan bug yang boleh saya perbaiki diam-diam.
- **F-08/D-04 → risiko diterima + catatan least-privilege.** `backend/app/api/admin.py:105-125` menyatakan `bgn_monitor` memegang pengelolaan pengguna **karena skema tidak punya peran `admin`** (keputusan owner 2026-10-17), dengan dua pagar: peran sendiri tidak boleh diubah, dan setiap mutasi meninggalkan jejak ledger. Sisa risiko nyata: token operasional agen memegang kemampuan tulis yang tidak dibutuhkannya.
- **D-04 (token panjang) → tidak dapat dibuktikan.** `MEALCHAIN_API_TOKEN` **tidak** dibaca oleh backend mana pun (`grep -rn MEALCHAIN_API_TOKEN backend/app` = kosong); ia dipakai klien agen (`agent/api_client.py`, `agent/tools.py`) sebagai Bearer yang harus berupa JWT hasil `/auth/login`, sehingga tunduk pada penjepitan umur token. Klaim "token panjang tanpa clamp" tidak terbukti pada kode saat ini.

Status rinci tiap butir ada di `REPAIR_PLAN.md` §1b dan `FINAL_VERIFICATION_REPORT.md` §5.

---

## 6. Hal yang **tidak** dapat diklaim dari audit ini

- Tidak ada bukti runtime: endpoint hidup, constraint DB nyata, migrasi, PO/ledger, quarantine, maupun trace agent dijalankan.
- Tidak ada verifikasi live SAP AI Core, AWS Bedrock/AgentCore, Joule, atau OSRM.
- Tidak ada pemeriksaan advisory dependency kecuali yang benar-benar dibuka reviewer (dicatat di laporan reviewer).
- Tidak ada secret scan menyeluruh atas seluruh history; hanya pemeriksaan terarah (`.env` historis vs sekarang) dengan output ter-redaksi.

---

## 7. Catatan kepatuhan

- Tidak ada file proyek yang dimodifikasi saat audit; hash baseline dicatat untuk `freshness.py`, `receipts.py`, `event3_service.py`, `actions.py`, `decisions.py`, `verifier_client.py`.
- Tidak ada nilai secret yang ditulis ke laporan ini: hanya nama key dan lokasi file.
- Temuan F-07 dicatat sebagai **false positive** meski berasal dari review sebelumnya — konflik antar-sumber dilaporkan, bukan dipilih yang paling nyaman.
