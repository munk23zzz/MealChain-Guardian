# Fase 1 — baseline, isolasi, dan dump yang terbukti terbaca

Status: **selesai** (26 Oktober 2026, 19.55 WIB). Semua angka di bawah diukur
pada mesin demo, bukan disalin dari catatan lama. Bila berbeda dengan
`docs/state-snapshot.md`, snapshot yang berlaku.

## 1. Predikat baseline (terukur)

| Ukuran | Nilai |
|---|---|
| Branch / commit saat pengukuran | `feature/db-modes-demo-coverage` @ `ab47bbf` (sebelum commit bukti ini) |
| Alembic head | `033_indeks_fk_hilang` |
| Tabel | 22 |
| `decisions` | 48 — 17 `pending_approval`, 10 `rejected`, 9 `executed`, 5 `verifier_flagged`, 3 `approved`, 2 `proposed`, 2 `review_only` |
| `batches` | 125 (wortel 32, beras 32, telur 31, ayam 30) |
| `approvals` | 28 |
| `suppliers` | 61 (36 hygiene, 17 HACCP, 8 tanpa sertifikat) |
| `users` | 8 — 7 akun peran + 1 akun uji dinonaktifkan |
| `supply_records` | 5.240 (deret 1 Sep – 4 Nov 2026) |
| `menu_plans` | 660 |
| `ledger_blocks` | 1.598 (1.526 arsip, 0 yatim), `valid=true` |
| `agent_traces` | 118 |
| Rute kiriman Jakarta | 15 (14 berjalur, 1 tanpa geometri) |
| Kartu 24 jam (Jakarta) | 14 (10 menunggu + 2 ditandai verifier + 2 dieksekusi) |
| KPI hari ini | 6/7 tersedia; kontinuitas `no_data` |
| Akun residu `@test.local` | 1 (dinonaktifkan, memegang 2 approval historis) |

**Penyimpangan dari angka rencana, dan sebabnya.** `phase-01-baseline.md`
menulis harapan "nol akun `@test.local`, ledger 1.382, keputusan 36, batch 120".
Angka 36/120/1.382 itu berasal dari DB yang sudah ter-purge sebagian oleh suite
tes (AUD-TEST-02), bukan keluaran builder. Builder menghasilkan 48 keputusan,
125 batch, 28 approval; itu yang kini dipakai sebagai baseline. Rincian bukti
dan koreksi diagnosis ada di `MG/audit-rencana-vs-kode.md` §8.

Akun `@test.local`: tiga dihapus (nol referensi), satu dinonaktifkan karena
memegang 2 approval pada keputusan `executed` yang menjadi sampel KPI SDC.
Menghapusnya berarti menjebol kuorum atau memalsukan atribusi.

## 2. Verifikasi lingkungan sebelum mutasi

- `GET /health` backend → `{"status":"healthy","service":"mealchain-backend"}`
- Frontend `:3010` → HTTP 200
- Empat container hidup: `mealchain-backend`, `mealchain-frontend`,
  `mealchain-mock-sap`, `mealchain-postgres`
- `GET /ledger/verify` → `valid=true`, 0 yatim

## 3. Dump dan bukti terbaca

| Artefak | Lokasi | Bukti |
|---|---|---|
| Dump pra-mutasi (plain SQL, gzip) | `%LOCALAPPDATA%\hermes\cache\scratch\mealchain-backup-20261026-1828.sql.gz` (di luar repo) | Dipulihkan penuh ke DB demo 19.0x WIB; jumlah tabel cocok (36/21/1.382/11 saat itu) |
| Klon pembanding #1 | `mealchain_idem` | `pg_dump | psql` → 36 keputusan |
| Klon pembanding #2 | `mealchain_idem2` | Dipakai tes build kanonik dan gate; 48 keputusan setelah build |

Restore penuh diuji, bukan diasumsikan: `DROP SCHEMA public CASCADE` +
`psql < dump` pada DB demo, lalu `alembic_version` = `033`, seluruh hitungan
kembali ke baseline pra-mutasi sebelum DB dibangun ulang secara kanonik.

## 4. Isolasi tes dari DB demo

- Skrip gerbang: `scripts/gerbang-db-terpisah.sh` (DB `mealchain_gate`).
- Bukti kontaminasi lama tetap dicatat: menjalankan `pytest` di DB kerja
  mem-purge baris demo (keputusan 48 → 9, pasokan 5.240 → 40).
- Seluruh tes berat pada putaran ini dijalankan di `mealchain_idem2`, bukan DB
  demo. Tidak ada perintah `pytest` yang dijalankan terhadap DB demo.

## 5. Hasil pengujian yang dijalankan

| Pemeriksaan | Perintah | Hasil |
|---|---|---|
| Gate invariant | `verify_stack.py verify/invariants.spec.json` | **PASS 52 / FAIL 0 / SKIP 1** |
| Tes integrasi build | `MCG_BUILD_IT=1 pytest tests/test_demo_template_reset_laporan.py` (DB klon) | **3 passed** (167,7 dtk) |
| Tes unit/target | `pytest tests/test_demo_template_reset.py test_openapi_artifact_drift.py test_safety_gate_rules.py test_config_tanpa_dsn.py` (DB klon) | **32 passed** (7,6 dtk) |
| Frontend | `npx vitest run` | **1.818 passed / 166 berkas** |
| Lint backend | `ruff check app tests` | **All checks passed** |
| Lint + tipe frontend | `tsc --noEmit`, `npm run lint` | bersih (putaran 19.42 WIB) |

## 6. Keputusan yang diambil pada fase ini

1. Baseline = keluaran builder (48/125/28/1.598), bukan keadaan DB pasca-suite.
2. Rebuild **idempoten**; yang diperbaiki adalah laporan `hitung` yang dibaca
   sebelum langkah pelengkap (F7) dan 11 keputusan tanpa jejak (F7b).
3. Akun uji: 3 dihapus, 1 dinonaktifkan (password dirotasi ke nilai acak).
4. Ledger bertambah 72 blok setiap build/rebuild (arsip generasi) — angka blok
   mengikuti snapshot, bukan konstanta.

## 7. Gerbang keluar

- [x] Baseline terukur dan dapat diulang (`scripts/snapshot_state.py`).
- [x] Dump terbukti dapat dipulihkan.
- [x] Isolasi tes tersedia dan dipakai.
- [x] Gate invariant hijau (52 PASS).
- [ ] **Fase 2 belum boleh mulai**: 7 butir kontrak bisnis masih menunggu
  keputusan pemilik (lihat `MG/overview.md` dan `MG/audit-rencana-vs-kode.md`).
