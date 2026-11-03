# AUDIT_11 — Checklist Final & Kesimpulan Readiness

## A. Ringkasan audit

| Item | Nilai |
|---|---|
| Proyek | MealChain Guardian (`E:\hackathon\HackathonAWS\mealchain-guardian`) |
| Branch / commit | `feature/db-modes-demo-coverage` @ `d414957` + 104 perubahan lokal (dipertahankan) |
| Tanggal audit | 26 Oktober 2026, 07:00–09:10 WIB |
| Environment | Docker Compose: backend `:8000`, frontend `:3010`, postgres `:15432`, mock-sap `:8001` |
| Versi backend | FastAPI + Python 3.12.15, alembic 1.13.2, ruff 0.6.9, pytest 8.3.3 |
| Versi frontend | Next 14.2.14, React 18.3.1, TypeScript 5.6.2, vitest 2.1.9, MapLibre 4.7.1 |
| Database | PostgreSQL 16.15, 24 tabel, head `033_indeks_fk_hilang` |
| Alat uji | `verify_stack.py` + Playwright, pytest, vitest, tsc, ESLint, ruff, alembic, psql, npm audit |
| Tes ditemukan | backend 1487, frontend 1793, gate 79 pemeriksaan |
| Tes dijalankan | backend 1487 (+57 isolasi +18 pengelompokan ulang), frontend 1793, gate 79 |
| PASS | backend 1450+54+18, frontend 1793, gate 76 + 3 flow UI |
| FAIL | backend 13 (semua terbukti bergantung urutan/state), gate 0 |
| BLOCKED | pip-audit/bandit/semgrep/trivy/k6/axe, AgentCore & SAP live, login password |
| NOT TESTED | fault injection backend, race approval paralel, reset bersamaan, responsive, keyboard/contrast |
| Bug ditemukan | 21 |
| Bug diperbaiki | 6 (BUG-001…BUG-006) |
| Bug tersisa | 15 (3 P1, 7 P2, 5 P3) |

## B. Ringkasan arsitektur aktual

- **Frontend**: satu halaman Next.js App Router dengan 11 tab (10 untuk approver, 9 untuk monitor), React Query sebagai lapisan data (`identityScope = peran:lokasi`), tanpa mock data pada alur utama.
- **Backend**: FastAPI 77 operasi; otorisasi per peran + scope lokasi di server; gerbang keselamatan deterministik (`safety_gate.py`); middleware sesi demo; tidak ada queue/worker — semua dalam request path.
- **Database**: 24 tabel; status dijaga CHECK constraint; empat mata dijaga unique index; satu sesi demo aktif dijaga partial unique index; ledger blok (`ledger_blocks` + `ledger_meta`).
- **Agent/AI**: Supervisor & Verifier Agent lewat AgentCore (kredensial ada, panggilan berbayar tidak dijalankan pada audit ini).
- **Observability**: log uvicorn + `docker events`; tidak ada APM.

## C. Checklist utama

| ID | Area | Kriteria | Status | Bukti | Masalah |
|---|---|---|---|---|---|
| AUD-001 | Requirements | 7 fitur inti PRD tertaut ke kode | PASS | AUDIT_02 §2.1 | — |
| AUD-002 | Requirements | 4/7 KPI sesuai dokumen, 3 selisih terdokumentasi | PARTIAL | AUDIT_02 §2.3 | AUD-API-02 |
| AUD-003 | Frontend | Semua tab berfungsi per peran | PASS | matriks tab 3/3 | — |
| AUD-004 | Frontend | Tes, lint, tipe bersih | PASS | 1793 vitest, tsc 0, lint bersih | — |
| AUD-005 | Frontend | Tidak ada mock yang menyamarkan kegagalan | PARTIAL | `.catch(()=>null)` di detail | FE-01 |
| AUD-006 | API | Kontrak & kode status benar | PASS | 76 gate checks | — |
| AUD-007 | API | Authz di backend, bukan UI | PASS | roles.spec 16/16 | — |
| AUD-008 | API | Error tidak membocorkan internal | PASS | 404/409/422 terukur | — |
| AUD-009 | Database | Invarian data (orphan, duplikat, status) | PASS | 19 pemeriksaan DB | — |
| AUD-010 | Database | Migrasi dari kosong & tidak ada drift | PASS (setelah perbaikan) | 24 tabel, `alembic check` bersih | BUG-001 (fixed) |
| AUD-011 | Demo Control | Sesi 2 jam absolut + plafon | PASS | start 120,0'; extend 240 ditolak | — |
| AUD-012 | Demo Control | Satu sesi aktif dijamin DB | PASS | index + tes atomik | — |
| AUD-013 | Demo Control | Enforcement mutasi tanpa sesi | PASS | 409 pada 3 endpoint | — |
| AUD-014 | Demo Control | Reset idempoten & tidak menghapus non-demo | PASS | 3× rebuild, invarian 0 | — |
| AUD-015 | Demo Control | Reset bersamaan / DB gagal | NOT TESTED | — | — |
| AUD-016 | Rekomendasi | 5 rekomendasi Jakarta | PARTIAL | 11 kartu / 5 skenario | WF-02 |
| AUD-017 | Rekomendasi | Tidak duplikat saat refresh | PASS | rebuild 3× | — |
| AUD-018 | KPI | Periode today/7d/1bulan server-side | PASS | 422 untuk input salah | — |
| AUD-019 | KPI | Angka bergerak karena aksi | PASS | 4 metrik berubah | — |
| AUD-020 | KPI | Angka tidak bergerak karena refresh | PASS | tes idempoten | — |
| AUD-021 | KPI | Regional Imbalance dari kartu demo | FAIL (by design) | `demo_case` dikecualikan | WF-04 |
| AUD-022 | Approval | Empat mata, akun berbeda | PASS | 409 akun sama | — |
| AUD-023 | Approval | Satu approval tidak final | PASS | status & execute 409 | — |
| AUD-024 | Approval | Race dua approval | NOT TESTED | — | — |
| AUD-025 | Delivery | Animasi hanya setelah execute | PASS | `dispatched_at`, 12 rute | — |
| AUD-026 | Delivery | Progress bergerak nyata | PASS | naik 6/6 dalam 8 dtk | — |
| AUD-027 | Delivery | Refresh tidak memicu kirim ulang | PASS | penulisan hanya di execute | — |
| AUD-028 | Notifikasi | Badge & isi konsisten | PASS | 12 → 9 | WF-03 (tanpa read-state) |
| AUD-029 | E2E | Alur utama dari UI | PASS | matriks tab + probe API | — |
| AUD-030 | E2E | Kegagalan backend saat aksi | NOT TESTED | — | E2E-13 |
| AUD-031 | Security | 401/403/scope | PASS | roles.spec | — |
| AUD-032 | Security | Header & CORS | PASS | curl | — |
| AUD-033 | Security | Rahasia tidak di repo saat ini | PARTIAL | `.env` tak dilacak, ada di riwayat | SEC-01 |
| AUD-034 | Security | Kredensial demo tidak terekspos | FAIL | password di bundel klien | SEC-02 |
| AUD-035 | Security | Dependensi tanpa CVE | FAIL | next/maplibre critical | SEC-04 |
| AUD-036 | Security | Dependensi Python dipindai | BLOCKED | pip-audit tidak ada | — |
| AUD-037 | Performance | Latensi baseline diukur | PASS | /kpi 121 ms, /decisions 27 ms | — |
| AUD-038 | Performance | Uji beban/SLA | BLOCKED | k6/locust tidak ada | — |
| AUD-039 | Accessibility | ARIA dasar | PARTIAL | aria-current, role=alert | — |
| AUD-040 | Accessibility | axe/keyboard/kontras | BLOCKED / NOT TESTED | — | A11Y-01 |
| AUD-041 | Regression | Perubahan audit tidak merusak | PASS | gate 79, vitest 1793, alembic bersih | — |
| AUD-042 | Test hygiene | Suite deterministik | FAIL | 13 gagal bergantung urutan | AUD-TEST-01 |
| AUD-043 | Test hygiene | Suite tidak merusak data demo | FAIL | data demo terhapus oleh run penuh | AUD-TEST-02 |
| AUD-044 | Docs | Kamus KPI & state machine | PASS | `docs/kamus-kpi-dan-state-machine.md` | — |
| AUD-045 | Docs | Nama tabel di dokumen benar | PARTIAL | `ledger` vs `ledger_blocks` | AUD-DB-01 |

## D. Checklist E2E

| ID | Skenario | Status |
|---|---|---|
| E2E-01 | Startup | PASS |
| E2E-02 | Data demo dari DB | PASS |
| E2E-03 | Batas sesi 2 jam (fake clock) | PASS |
| E2E-04 | Reset demo | PASS |
| E2E-05 | 5 rekomendasi Jakarta | PARTIAL |
| E2E-06 | KPI today bergerak | PASS |
| E2E-07 | KPI 7d & 1bulan | PASS |
| E2E-08 | Approval pihak 1 | PASS |
| E2E-09 | Approval pihak 2 | PASS |
| E2E-10 | Approval tidak valid | PASS |
| E2E-11 | Animasi pengiriman | PASS |
| E2E-12 | Notifikasi | PASS |
| E2E-13 | Backend gagal saat aksi | NOT TESTED |
| E2E-14 | Hak akses | PASS |
| E2E-15 | Isolasi & regresi | PARTIAL (AUD-TEST-02) |

## E. Daftar bug

### Diperbaiki (5)

| ID | Judul | P |
|---|---|---|
| BUG-001 | 22 indeks FK tidak dideklarasikan di model → `alembic check` gagal | P2 |
| BUG-002 | Spec gate memaku head migrasi basi → gate merah palsu | P2 |
| BUG-003 | Lint `I001` di berkas tes | P3 |
| BUG-004 | Tes bergantung data mutlak (`kg_awal == 1400`) | P3 |
| BUG-005 | Asersi pesan gerbang keselamatan terlalu sempit | P3 |
| BUG-006 | "Siapkan data demo" menghasilkan 2 keputusan `executed` tanpa approval (invarian merah) | P2 |

### Tersisa (15)

| ID | Judul | P | Catatan |
|---|---|---|---|
| SEC-01 | Kredensial di riwayat git, rotasi belum | P1 | butuh tindakan owner |
| SEC-04 | 3 CVE dependensi (next & maplibre critical) | P1 | upgrade mayor |
| AUD-TEST-02 | Suite pytest menghapus data demo & meninggalkan 15 user uji | P1 | prosedur `AGENTS.md` menjalankan pytest pada DB demo |
| AUD-TEST-01 | 13 tes gagal bergantung urutan | P2 | tidak ada isolasi transaksi |
| SEC-02 | Password 7 akun demo di bundel klien | P2 | demo |
| SEC-03 | Tidak ada pemisahan env demo/produksi | P2 | deployment |
| FE-02 / WF-01 | Poll detail untuk id yang hilang → 404 berulang | P2 | terbukti race lingkungan, kerapuhan nyata |
| WF-04 | Regional Imbalance tidak menghitung kartu demo | P2 | keputusan produk |
| AUD-API-02 | 3 definisi KPI beda dari `Skill.md` | P2 | keputusan owner |
| AUD-DB-02 | Deret harga/pasokan sintetis menopang KPI 7d/1bln | P2 | harus dinyatakan saat demo |
| FE-01 | `.catch(()=>null)` menyamarkan galat API | P3 | — |
| FE-03 | Tipe respons API sebagian `any` | P3 | — |
| WF-02 | "5 rekomendasi" vs 11 kartu | P3 | definisi produk |
| WF-03 | Notifikasi tanpa read-state | P3 | keputusan produk |
| AUD-DB-01 | Dokumen menyebut tabel `ledger` | P3 | nama aktual `ledger_blocks` |

## F. Perubahan file selama audit

| Berkas | Perubahan | Alasan |
|---|---|---|
| `backend/app/models/{batches,decisions,receipts,supplier_exclusions,demo_sessions,kpi_facts,price_signals,sap_mock,supply_records,demand_records}.py` | +22 `Index(...)` di `__table_args__` | BUG-001 — metadata setara DB |
| `verify/stack.spec.json`, `verify/invariants.spec.json` | `expect` head → `033_indeks_fk_hilang` | BUG-002 |
| `backend/tests/test_gate_anchor_canonical.py` | urutan import (ruff --fix) | BUG-003 |
| `backend/tests/test_demo_timeseries_api.py` | asersi `kg_awal > 0` | BUG-004 (dengan catatan) |
| `backend/tests/test_receipts_safety_gate.py` | asersi pesan → daftar alasan sah | BUG-005 |
| `docs/audit/AUDIT_01…11` | 11 laporan baru | deliverable audit |

Tidak ada migrasi baru dibuat; tidak ada skema DB yang diubah oleh audit ini. Data demo dikembalikan ke baseline sesudah pengujian (36 keputusan / 12 approval / 660 menu / 5.240 pasokan / 7 user / 1 sesi aktif / 11 kartu Jakarta terbuka) dan gate invarian **37/37 PASS** pada keadaan akhir.

## F.bis Status akhir gate (keadaan setelah semua perbaikan)

| Spec | Hasil |
|---|---|
| `verify/stack.spec.json` | PASS 19/19 |
| `verify/invariants.spec.json` | PASS 37/37 |
| `verify/roles.spec.json` | PASS 20/20 |
| `verify/tabs.spec.json` (3 peran) | PASS 3/3 |
| `alembic check` | No new upgrade operations |
| migrasi dari DB kosong | 24 tabel, head `033_indeks_fk_hilang` |
| ruff | All checks passed |
| ESLint / tsc / vitest | bersih / exit 0 / 1793 PASS |

## G. Coverage

Tidak tersedia (`coverage.py`/`pytest-cov` dan coverage vitest tidak dipasang) → **BLOCKED**. Angka cakupan tidak diklaim.

## H. Risiko tersisa

1. **Data demo dapat dihancurkan oleh perintah yang didokumentasikan** (AUD-TEST-02). Mitigasi segera: jalankan pytest pada DB klon (`docker run` + `TEST_DATABASE_URL`), dan tambahkan penjaga di conftest sebelum demo.
2. **Dependensi frontend rentan** (next/maplibre critical) — dapat diterima hanya selama instance demo tertutup.
3. **Kredensial demo ada di bundel** — siapa pun yang membuka instance dapat menjadi approver.
4. **KPI 7d/1bulan bertumpu pada deret sintetis** — angka dapat disalahartikan sebagai data MBG nyata bila tidak dijelaskan.
5. **Suite tes tidak deterministik** — CI lokal bisa merah/hijau bergantung urutan.

## I. Rekomendasi tindak lanjut (urut prioritas)

1. **Sebelum demo:** jalankan pytest hanya pada DB klon (skrip `docker run` sudah tercatat di skill `mealchain-guardian-dev-loop`), lalu rebuild template sebelum panggung.
2. **Sebelum publikasi repo/instance:** rotasi kredensial (SEC-01), pindahkan login demo ke token sesi server (SEC-02), pisahkan env demo/produksi (SEC-03).
3. **Pasca-kompetisi:** upgrade Next 16 + MapLibre 6 dengan siklus regresi penuh (SEC-04); tambah `pip-audit`, `semgrep`, `axe-core`, dan uji beban.
4. **Kualitas tes:** isolasi transaksi per tes (atau DB per sesi) untuk menutup AUD-TEST-01.
5. **Produk:** putuskan definisi 3 KPI yang menyimpang dan apakah Regional Imbalance boleh menghitung `demo_case`.

## J. Kesimpulan readiness

- **Siap demo (dengan syarat):** alur inti — sesi 2 jam, rekomendasi Jakarta, approval empat mata, eksekusi, animasi kiriman, notifikasi, dan KPI periode — terbukti bekerja melalui UI, API, dan DB; gate 79 pemeriksaan hijau; tidak ada kegagalan deterministik pada kode produk.
- **Belum siap publikasi terbuka:** 2 temuan P1 (kredensial & dependensi) serta 2 cacat kualitas pengujian (suite destruktif dan tidak deterministik) harus diselesaikan lebih dulu.
- Audit ini **tidak** menyatakan sistem bebas bug. Cakupan yang diuji: 7 fitur inti, 7 KPI, Demo Control, approval, delivery, notifikasi, authz, migrasi, dan gate stack. Yang tidak tercakup disebut eksplisit di AUDIT_10 §10.4.
