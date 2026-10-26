# SIKLUS-2 PLAN — temuan lanjutan + sisa merah

**Dasar:** `FINAL_VERIFICATION_REPORT.md` §15, laporan reviewer `V3-access`, `V4-infra`, `R-diffreview`.
**Aturan:** TDD (tes gagal dulu, baru patch), satu item satu laporan terverifikasi, tidak menyentuh 46 entri working-tree milik pemilik, tidak commit/merge/deploy.

## A. Boleh dieksekusi tanpa keputusan pemilik

| # | Item | Bukti | Kriteria terima |
|---|---|---|---|
| S1 | Token agen: `buat_token_agen.py` menerbitkan JWT `bgn_monitor` 30 hari melewati clamp `auth.py:54-78` | V3-access | umur token ≤ clamp yang sama; tes menolak `--hari 30` |
| S2 | `/demo/template/rebuild` tanpa gate sesi (`demo_session.py:208-212`) | V3 | tanpa sesi aktif → 409; dengan sesi → 200 |
| S3 | Rate limit login: kunci per akun, bukan hanya `client.host` (`auth.py:137-140`); prod `--forwarded-allow-ips="*"` | V3 | IP berganti tetap terkunci per akun; allow-ips dipersempit |
| S4 | Karantina `pass` bisa masuk stok (`receipts.py:223` tak mengoper `quarantine_status`) | R-diffreview #5 | batch `quarantined` ditolak walau `safety_status=pass` |
| S5 | Diagnosa urutan langkah trace (`DETECT…DECIDE` vs `VERIFY/DECIDE/OPTIMIZE`) | E8 | akar masalah ditemukan sebelum patch; bukan tebakan |
| S6 | 2 tes `test_recommendation_snapshot`: ekspektasi freshness 1,0 vs kontrak F-02 | E8 | ekspektasi diperbarui, aturan keselamatan tidak dilonggarkan |
| S7 | `openapi.json` 26 dari 75 path | V4 | artefak dihapus atau dijaga tes drift |

## B. DITAHAN — butuh keputusan pemilik

| # | Item | Pertanyaan yang harus dijawab pemilik |
|---|---|---|
| T1 | F-03 rentang suhu per komoditas (masih 0–8 °C di 4 tempat) | angka °C sah untuk ayam/telur/wortel/beras + sumber standar |
| T2 | F-08 `bgn_monitor` bisa mengelola pengguna & lokasi | peran `admin` terpisah, atau `bgn_monitor` memang pemegang wewenang itu |
| T3 | `GET /receipts?batch_id` lintas lokasi | boleh nasional (pengawas) atau wajib per-lokasi |
| T4 | `execute` menerbitkan PO walau `dikirim=[]`; `ditahan` tak tampil di UI | PO tetap terbit (dengan penanda) atau ditahan seluruhnya |

## C. Urutan kerja

S5 (diagnosa, tanpa patch) → S1 → S2 → S4 → S3 → S6 → S7 → T1–T4 setelah keputusan.

## D. Gate per item

`pytest <tes terkait>` RED→GREEN, lalu `ruff check .`, lalu regresi grup terdampak. Bila satu item menyentuh jalur eksekusi/penerimaan, jalankan juga `test_can_execute_parity.py` dan `test_receipts_approval.py`.

## Status (25 Okt 2026)

- **S1 SELESAI** — `umur_token_detik()` + `MASA_BERLAKU_MAKS_DETIK` di
  `backend/scripts/buat_token_agen.py`; `tests/test_token_agen_clamp.py`
  RED→GREEN (3 gagal → 10 lulus bersama 2 tes demo); `ruff` bersih.
- **S5 SEBAGIAN (diagnosa, belum ada patch)** — mekanismenya ditemukan, akar
  masalah BELUM terbukti:
  - `app/services/event1_orchestrator.py` menulis trace DUA FASE: `DETECT`
    (:126-131) dan `VERIFY` (:172) terjadi SEBELUM Decision dibuat (`:183`),
    sedangkan `TRACE` (:240), `PREDICT` (:250), `OPTIMIZE` (:300), `DECIDE`
    (:315) ditulis setelah `flush`.
  - Pembacaan mengurutkan `AgentTrace.step_at ASC, id ASC` (`decisions.py:465`),
    jadi urutan akhir bergantung pada `step_at` yang disintesis untuk langkah
    fase-1, bukan pada urutan eksekusi.
  - Fakta uji: pada DB BARU (`mealchain_gate3`, migrasi 000→031 + seed kanonik)
    hasilnya hanya 3 baris (`VERIFY`, `DECIDE`, `OPTIMIZE`) — `DETECT`, `TRACE`,
    `PREDICT` tidak ada; sama saat `DEMO_MODE=false`.
  - Kesimpulan sementara: baris `DETECT` hanya ditulis bila kondisi tertentu
    terpenuhi (kandidat/`ok`), dan tes mengunci 6 langkah. Perlu satu sesi
    diagnosa lagi (baca `:110-200` orchestrator + cara buffer fase-1 ditulis)
    SEBELUM patch. Tidak ada perubahan kode untuk S5.

### S5 — lanjutan diagnosa (25 Okt, sesi 2)

Ditemukan: `DETECT` **memang** dibuffer — `traces.append(_TraceStep("DETECT", …))`
di `event1_orchestrator.py:126-132`, sama seperti langkah lain. Jadi absennya
`DETECT/TRACE/PREDICT` di DB bukan karena kondisional di titik itu, melainkan di
**penulisan buffer** (fase-1 belum punya `decision_id`, jadi bergantung pada cara
buffer di-flush setelah `flush()` Decision di `:183`).

Langkah diagnosa berikutnya (belum dijalankan): periksa baris nyata di DB
(`SELECT step_name, step_at FROM agent_traces WHERE decision_id = …`) untuk satu
hasil `run_event1`, lalu baca loop penulisan buffer (setelah `:315`). Patch
ditunggu sampai itu terlihat — belum ada perubahan kode untuk S5.

**Reproduksi ulang (25 Okt, sesi 3):** dua tes yang dulu merah kini **HIJAU** di
HEAD ini — `test_event1_e2e_acceptance.py::test_event1_e2e_propose_approve_execute_mock_sap`
(1 passed) dan `test_decision_read_endpoints.py::test_get_decision_traces_returns_ordered_actual_steps`
(1 passed). Karena gejala aktif tidak dapat direproduksi, S5 **tidak dipatch**:
mekanisme yang mencurigakan tetap terdokumentasi (`persist_trace_steps` dipanggil
per langkah sehingga `step_at` disintesis terpisah), tetapi belum ada bukti
bahwa ia menyebabkan kegagalan.

## Status siklus-2 lanjutan (25 Okt 2026, sesi 3)

| # | Status | Bukti |
|---|---|---|
| S2 | SELESAI | `demo_session.py` `/demo/template/rebuild` kini `Depends(butuh_sesi_aktif)`. RED: handler jalan tanpa sesi (DID NOT RAISE). GREEN: `tests/test_siklus2_sesi_rebuild.py` 2 lulus (409 tanpa sesi + kontrak dependency route) + regresi `test_demo_template_reset::test_hanya_kepala_yang_boleh_dan_sibuk_ditolak_409` → 3 passed |
| S3 | SELESAI (config) | `docker-compose.prod.yml`: `--forwarded-allow-ips="*"` → `${FORWARDED_ALLOW_IPS:-127.0.0.1}`; `docker compose config` menunjukkan `--forwarded-allow-ips=127.0.0.1`. Tes kontrak `tests/test_proxy_trust_config.py` RED di host (gap nyata) → GREEN 1 passed; di dalam kontainer ia **skip** (berkas compose tidak ada di image). Rate-limit per akun sudah ada & tetap hijau: `tests/test_auth_keamanan.py` **8 passed** |
| S4 | SELESAI | `receipt_blokir_alasan()` menerima `quarantine_status`; `receipts.py` meneruskan `batch.quarantine_status` + pesan 409 khusus. RED: `TypeError` (argumen belum ada). GREEN: `test_receipts_quarantine_gate.py` 2 + gate murni + endpoint receipt → **25 passed** |
| S6 | SELESAI | Akar masalah di TES, bukan produk: baris DB diberi log suhu lengkap, nilai harapan dihitung dengan log kosong → 0,964286 vs 0,664286. `_log_suhu()` sekarang dipakai untuk keduanya; F-02 tidak dilonggarkan (penjaga `test_freshness_evidence_integrity.py` tetap: log kosong ≠ pass, log bersih 0,90). GREEN: `test_recommendation_snapshot.py` 2 passed; grup freshness **34 passed** |
| S7 | SELESAI | `backend/openapi.json` diregenerasi dari `app.main:app`: 26 → **75 path / 77 operasi** (129.116 byte, sort_keys+indent 2). Tes drift baru `tests/test_openapi_artifact_drift.py` (RED dulu: artefak kurang 49 operasi) → GREEN 1 passed |

Regresi grup terdampak: `test_receipts_approval`, `test_receipts_safety_gate`,
`test_receipts_quarantine_gate`, `test_safety_gate_rules`, `test_can_execute_parity`,
`test_demo_template_reset`, `test_demo_session`, `test_demo_session_mulai_atomik`,
`test_execute_safety_wiring`, `test_actions` → **68 passed, 12 skipped**
(12 skip = tes lifecycle `test_demo_session.py` yang sengaja hanya jalan dengan
`DEMO_SESSION_ENFORCE=true`; bukan tes hilang).

Gate berikutnya yang belum dijalankan: suite backend penuh + `tsc`/`vitest`, lalu
T1–T4 menunggu keputusan pemilik.

## Status siklus-3 (26 Okt 2026) — gate penuh + F-07/F-08

**Gate backend penuh** (klon DB, 1.581 tes terkumpul setelah 5 tes baru):

| Run | DB | Cara siapkan | Lulus | Gagal | Dilewati | Durasi |
|---|---|---|---|---|---|---|
| 1 | `mealchain_sim` | klon DB demo apa adanya | 1.547 | 8 | 22 | 549 s |
| 2 | `mealchain_sim4` | klon DB demo apa adanya | 1.552 | 7 | 22 | 661 s |
| 3 | `mealchain_gate4` | **migrate + `scripts/semai-demo.sh`** (kanonik 8 Okt + deret demo + kasus) | **1.556** | **3** | 24 | 593 s |
| 4 | `mealchain_gate4` | resep yang sama, sesudah perbaikan isolasi | **1.558** | **3** | 22 | 582 s |

**Resep gerbang yang sah** (dari run 3): DB baru → `alembic upgrade head` →
`DATABASE_URL=.../mealchain_gate4 bash scripts/semai-demo.sh` → jalankan suite dengan
`DATABASE_URL` yang sama. Klon DB demo **tidak** setara: setelah "Segarkan ke hari ini",
snapshot kanonik menempati seluruh rentang deret sehingga generator demo tidak bisa menulis
baris apa pun (bentrok kunci bisnis; `added=0`) dan tes yang menuntut baris demo gagal —
bukan karena kode berubah.

Kegagalan run 1 (semuanya ditriase):

| Berkas | Penyebab | Status |
|---|---|---|
| `test_semai_demo_script.py` (2) | path `parents[2]` menunjuk `/scripts` di image backend | **diperbaiki**: telusuri ke atas + `pytest.skip` bila berkas tidak ada → 2 skipped di kontainer, lulus di host (2 passed) |
| `test_demo_sesi_batas_dan_enforcement.py` (2) | DB punya sesi demo AKTIF milik layar; tes menyisipkan baris `active` kedua (unique index 032) dan menuntut `active=false` | **diperbaiki**: tes melewati diri bila ada sesi aktif (tidak menutup sesi orang lain); pada DB tanpa sesi → **6 passed** |
| `test_demo_completed_decisions_konsisten.py` (2) | binding menunjuk batch yang jadi `fail` karena suite sebelumnya mengubah batch | **bukan regresi**: 29 tes terkait lulus bersama di klon bersih |
| `test_tool_contracts.py` (2) | `/balance/recommend` kosong karena data demo tersapu tes sebelumnya | **bukan regresi**: lulus di klon bersih |

Kegagalan run 2: `test_demo_timeseries_api.py` (4), `test_demo_kpi_riwayat.py` (1),
`test_tool_contracts.py` (2). Ketujuhnya **lulus bersama (36 passed) di DB gerbang yang
disemai lengkap** (`mealchain_gate4`: kanonik 8 Okt + deret demo + aktivitas + kasus) —
penyebabnya dataset, bukan urutan: klon DB demo sudah digeser "ke hari ini" sehingga
baris kanonik menempati seluruh stempel dan deret demo tidak bisa ditulis.

**Perbaikan isolasi yang dikerjakan:**
1. `tests/conftest.py` — penjaga modul kini memeriksa **semua** tabel deret demo, bukan hanya
   `supply_records`; modul yang menemukan salah satu tabel kosong membangun ulang deret
   (sebelumnya `menu_plans`/`delivery_events` kosong lolos tanpa pemulihan).
2. `tests/test_tool_contracts.py` — fixture modul memanggil `pastikan_deret_demo()` supaya
   `/balance/recommend` tidak diuji di atas DB yang baru dipurge.
3. `tests/test_gate_anchor_canonical.py` (baru) — gagal dengan pesan jelas bila snapshot
   kanonik tidak berada di jangkar `CANONICAL_REF`, sehingga "DB ini bukan DB gerbang"
   tidak lagi muncul sebagai tujuh kegagalan yang tampak seperti bug produk.

**Sisa 3 kegagalan run 3–4** (semua di jalur data demo, bukan kode aplikasi):
`test_demo_completed_decisions_konsisten::test_ringkasan_hanya_menyisakan_alasan_yang_nyata`
(mengeluh `batch sumber kini FAIL`), `test_tool_contracts` (2: `/balance/recommend` kosong).
Bukti tambahan: sesudah run 4, `test_tool_contracts.py` **lulus sendiri (9 passed)**,
sedangkan tes konsisten **gagal sendiri** — artinya suite meninggalkan batch demo berstatus
`fail` pada binding keputusan demo, dan tidak ada yang memulihkannya. Akar: tes jalur
keselamatan mengubah `safety_status` batch demo tanpa restore. Perbaikan yang diusulkan
(butuh keputusan, belum dikerjakan): pulihkan status batch di `finally` pada tes tersebut,
atau jalankan modul pem-purge/pengubah status di DB sendiri.

**Gate frontend:** `tsc --noEmit` exit 0, `next lint` exit 0, `vitest run` **166 berkas /
1.793 tes lulus**, exit 0.

**F-08 ditambal (TDD).** `app/core/config.py` tidak lagi punya default DSN berkredensial;
`database_url` wajib dari env. RED: 3 gagal (`tests/test_config_tanpa_dsn.py`) → GREEN:
3 lulus. `tests/test_agent_review_config.py` diberi `DATABASE_URL` sekali-pakai supaya
tidak bergantung env ambient.

**F-07 ditambal (TDD).** Migrasi `033_indeks_fk_hilang` menambah 22 indeks FK satu kolom.
RED: `tests/test_fk_index_coverage.py` gagal dengan daftar 22 kolom → GREEN: 1 lulus.
Diterapkan ke DB demo (alembic `032 → 033`, `ix_%` 32 → 54) dan backend tetap `/health` 200.

**F-06 diukur dan diperbaiki di DB demo.** Indeks `supply_records` 33 MB vs heap 2,2 MB
dan `price_signals` 32 MB vs 2,7 MB — bloat, bukan definisi indeks. `REINDEX TABLE
CONCURRENTLY` pada `supply_records`, `price_signals`, `demand_records`, `menu_plans`,
`delivery_events` memulihkan ukuran DB **93 MB → 22 MB**.

**F-05 tetap keputusan pemilik.** Ledger generasi 126: 663 blok, 481 di antaranya tidak
lagi punya entitas hidup (data demo yang dihapus). Rantai hash tetap valid; menghapus
blok berarti mengubah riwayat audit. Tidak ada perubahan data.
*(Diukur ulang 26 Okt 2026: 1.382 blok total, 1.310 arsip, **0 blok yatim** —
lihat `docs/state-snapshot.md`. Angka 663/481 di atas adalah keadaan saat rencana ini ditulis.)*

**F-10 diterima dengan syarat.** Rate limiter di memori proses; produksi menjalankan
SATU proses uvicorn (tanpa `--workers`). Bila kelak worker > 1, pindahkan ke Redis.
