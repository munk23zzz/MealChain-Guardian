# 9 Agent — Final Readiness

Tanggal: 27 Oktober 2026 · Basis: `57db099` + patch kerja (lihat `9_AGENT_REPAIR_LOG.md`)
Dokumen pendamping: `9_AGENT_INVENTORY.md`, `9_AGENT_DEEP_AUDIT.md`,
`9_AGENT_DATA_AND_MATH_AUDIT.md`, `9_AGENT_ORCHESTRATION_AUDIT.md`,
`9_AGENT_TEST_RESULTS.md`, `9_AGENT_REPAIR_LOG.md`.

## 1. Ringkasan

Rantai "9 agent" (= **7 worker + 1 verifier + 1 ringkasan supervisor**, sesuai AUD-9A-19)
**berjalan** di jalur Event 1 dan review, dengan angka yang bersumber dari mesin deterministik,
dan gerbang tulis (verify → propose → approval 4 mata → execute → PO → ledger) **terbukti
menolak setiap jalur yang belum memenuhi syarat** pada DB klon:

- 8 worker benar-benar membaca API dan menghasilkan temuan ber-sitasi; 9 baris jejak tersimpan
  dengan satu `run_id` (dibuktikan; AUD-9A-02 hanya tersisa sebagai "belum pernah terjadi di
  DB demo" karena jalur AgentCore tidak dapat dijalankan di sini).
- approval kurang satu → 409; akun sama dua kali → 409; execute duplikat → 409; 4× execute
  bersamaan → tepat 1 PO; batch sumber FAIL/kedaluwarsa → 409; bukti dihapus → 409;
  verifier tanpa provider → `UNAVAILABLE` + keputusan tidak bisa dieksekusi.
- ruff 0, tsc 0, vitest 1822/1822, gate invarian PASS 59/FAIL 0, pytest 1628 lulus dari 1629
  (1 kegagalan = data demo, bukan kode) sesudah FIX-3/AUD-9B-29.

Tetapi **kualitas keputusan** agent masih jauh di bawah klaim "9 agent otonom": satu temuan P0
(AUD-9B-30) dan sekelompok P1 (data kesegaran/usable_until, angka safety dua basis, auditor
yang bisa hilang, kontradiksi antar-agent tidak diperiksa, kelengkapan bukti) tetap terbuka.
Karena itu verdict-nya berbeda per lingkungan.

Tiga cacat diperbaiki: guard verifier + gerbang certified di worker Freshness (P1, 19 tes
regresi baru) dan **AUD-9B-29 (P0)** — guardian Safety/Freshness kini menilai batch **sumber**
dan exclusion ber-cakupan pemasok+lokasi, dengan 16 tes regresi baru (repair log §8). Satu
dugaan cacat P1 (retry/duplikat → PO ganda) **tidak terbukti** dan tidak dipatch.

## 2. Temuan terbuka per severity

Status: **DIPERBAIKI** / **SEBAGIAN** / **TERBUKA** / **BLOCKED** / **KEPUTUSAN PRODUK**.

### P0

| ID | Temuan | Status | Catatan |
|---|---|---|---|
| AUD-9B-29 | Safety & Freshness memeriksa batch di **lokasi tujuan**, bukan sumber; exclusion dihitung tanpa cakupan pemasok/lokasi | **DIPERBAIKI** | Guardian memakai himpunan batch sumber (`source_batch_ids` binding / lokasi sumber) dan exclusion hanya memveto bila `supplier_id` + `scope_location_id` cocok; sumber tak teridentifikasi → fail-closed (`degraded` + `blocking`). E2E klon: `execute` batch sumber FAIL → **409**, batch sumber `pass` → 200; review Jakarta/telur tidak lagi `safety_veto` karena exclusion Jakarta pemasok lain. 16 tes regresi. **Batas:** `supplier_exclusions` tidak punya kolom komoditas (repair log §8). |
| AUD-9B-30 | Review 9 agent tidak pernah tersimpan di DB demo (0 baris `SUPERVISE`, 0 baris ber-`run_id`) | **TERBUKA (jalur AgentCore) / SEBAGIAN** | Jalur persist terbukti bekerja (9 baris, satu `run_id`, klon). Yang gagal adalah jalur runtime AgentCore di demo (`agent_review.status="unavailable"`), yaitu AUD-9A-07 + tidak adanya kredensial. |

### P1

| ID | Temuan | Status | Catatan |
|---|---|---|---|
| AUD-9A-03 | Verifier LLM berbagi runtime/model/system prompt dengan Supervisor | **SEBAGIAN** | Akibat perilakunya ditutup guard deterministik (0,82 tidak bisa `CONSISTENT` lagi). Independensi model tetap terbuka → butuh konfigurasi terpisah (keputusan owner). |
| AUD-9A-05 | Worker Freshness tidak memakai gerbang certified 0,85/0,60 | **SEBAGIAN** | Klasifikasi certified kini fakta + warning (`freshness_status`), `blocking`/veto tidak diubah (alasan data: 40/40 pasangan demo < 0,85; 30 tepat 0,82). |
| AUD-9B-01 | `freshness_score` tidak dapat direproduksi (literal 0,82 pada 39 batch demo; simpangan s.d. 28 pp) | **TERBUKA** | Data/seed. Prasyarat sebelum gerbang kesegaran boleh memveto. |
| AUD-9B-02 | `usable_until` bertentangan dengan skor (48/120 batch, maks 75,4 hari) | **TERBUKA** | Data/seed. |
| AUD-9B-03 | `safe_delivered_cost` ≠ jumlah rincian (Δ375.000) & skema `cost_breakdown` warisan | **TERBUKA** | Data demo `3e2e3cc7`. |
| AUD-9B-04 | SDC/kg < komponen beli (invarian SDC ≥ purchase dilanggar) | **TERBUKA** | Tidak ada pemeriksaan invarian di API. |
| AUD-9B-05 | Klaim verifier "harga 40% di bawah referensi" tidak cocok data (rasio 1,0000) | **TERBUKA** | Jejak audit berisi alasan yang tidak dapat direproduksi. |
| AUD-9B-06 | Jendela waktu tidak seragam (beberapa endpoint tidak membatasi `recorded_at <= now`) | **TERBUKA** | Menyebabkan "terbaru" = baris masa depan. |
| AUD-9B-16 | Tidak ada pemeriksaan kelengkapan bukti; 2 keputusan ber-SDC tanpa bukti | **TERBUKA (dibuktikan tes)** | `tests/test_bukti_dan_draf_demo.py` gagal pada klon pristine karena `3e2e3cc7` kehilangan 2 baris bukti; satu-satunya kegagalan pytest hari ini. |
| AUD-9B-19 | Angka keamanan dua basis (read model sumber vs agent tujuan) | **TERBUKA** | Berpasangan dengan AUD-9B-29. |
| AUD-9B-24 | Kegagalan auditor ditelan (`verifier_finding=None`, run tetap `completed`) | **TERBUKA** | P1 orkestrasi. |
| AUD-9B-25 | Pasokan vs permintaan antar-agent tidak pernah dibandingkan | **TERBUKA** | Terukur ulang: Supply 300,0 kg vs Demand 1074,11 kg hadir berdampingan, `completed`, 0 kontradiksi. |
| AUD-9B-26 | `verify_run` tidak memeriksa angka/kontradiksi | **TERBUKA** | Verifier menulis "Audit sepakat" untuk angka mustahil. |
| AUD-9B-35 | Prioritas "pasokan cukup tetapi terlambat" tidak ditegakkan | **TERBUKA** | `delivery_window`/`needed_by` tidak dipakai. |

### P2/P3 terbuka (ringkas, detail di dokumen asal)

AUD-9A-01/02/04/06/07/08/09/10/11/12/13/14/15/17/18, AUD-9B-07/08/09/10/11/12/13/14/15/17/18/
20/21/22/23/27/28/31/32/33/34/36. Yang perlu disebut khusus:

- **AUD-9A-06 / AUD-9B-32** — `POST /price/deviation` dan `POST /logistics/estimate` masih di
  luar allowlist gerbang sesi demo (409 saat enforcement menyala). Lapis peran sudah tidak
  menghalangi (`get_current_user`), jadi ini murni kebijakan gerbang sesi.
- **AUD-9B-31** — `POST /price/deviation` membalas **500** untuk `supplier_price ≤ 0`
  (diukur ulang hari ini: `-5` → 500, `0` → 500). Sepatutnya 422.
- **AUD-9A-08** — narasi supervisor masih menyebut "freshness pass (kesegaran terburuk 0,82)"
  pada Event 1 nyata; kontradiksi verbal yang belum tersentuh perbaikan.
- **AUD-9B-28** — `run_status` mengabaikan `blocking`: review `completed` berdampingan dengan
  "JANGAN EKSEKUSI" (terukur ulang: `status=completed`, `safety_veto=true`).
- **AUD-9A-19** — definisi resmi "9 agent" belum diputuskan tertulis; dokumen ini memakai
  "7 worker + 1 verifier + 1 ringkasan".

### BLOCKED

| ID | Alasan |
|---|---|
| AUD-9A-07 | Jalur 8 agent bergantung pada URL quick tunnel Cloudflare + JWT statis ber-`exp` 2026-11-17. Pada sesi ini runtime AgentCore menjawab `unavailable`; tidak ada kredensial/billing yang boleh dipakai. Risiko mati mendadak saat demo tetap ada. |
| Review lewat AgentCore | Butuh AWS Bedrock AgentCore (runtime `mealchain_supervisor_agent`) — tidak dapat dijalankan di sini. |

## 3. Sisa risiko (urutkan menurut dampak demo)

| # | Risiko | Dampak | Mitigasi minimum |
|---|---|---|---|
| R-01 | **Setiap `POST /actions/verify` manual kini berakhir `FLAGGED`** karena batch demo membawa 0,82 (AUD-9B-01) | Panel verifikasi menampilkan "flagged" pada jalur manual; jalur emas Event 1 tetap `CONSISTENT` (skor kandidat 0,965) | Perbaiki data kesegaran demo (AUD-9B-01/02) **atau** putuskan bahwa `needs_verification` bukan alasan menurunkan verdict; lihat repair log §5b |
| R-02 | Jalur review 8 agent di demo bergantung pada AgentCore + tunnel | `agent_review` bisa `unavailable`/`timeout` saat panggung; Agent Log kosong | Uji H-1 dengan tunnel hidup; siapkan narasi "review lokal" (jalur in-process terbukti bekerja) |
| R-03 | **Sudah tidak berlaku** (AUD-9B-29 diperbaiki): `safety_veto=True` pada hampir semua review karena exclusion global | Sebelumnya narasi "JANGAN EKSEKUSI" muncul untuk pengiriman yang read model sebut aman; kini veto hanya muncul bila batch sumber benar-benar FAIL/dikarantina/kedaluwarsa atau exclusion berlokasi+pemasok cocok | Tidak ada aksi; jaga agar exclusion yang dibuat di demo memakai pemasok & SPPG yang benar (kolom komoditas tidak ada) |
| R-04 | 1 tes invarian gagal karena data demo (AUD-9B-16) | Gate CI merah; sulit membedakan regresi kode vs data | Jalankan ulang penyemai kasus `bukti-hari-ini` (membuat tes lulus tanpa melonggarkan assertion) |
| R-05 | Kualitas angka keputusan (SDC, kesegaran, safety) menyimpang dari mesin | Juri yang menjumlahkan sendiri menemukan selisih (AUD-9B-03/04/17/18) | Perbaiki data demo + satukan basis angka; jangan mengutip SDC demo tanpa catatan |

## 4. Verdict

### DEMO_READY — **YA, dengan syarat** (R-01, R-02, R-04 ditutup lebih dulu)

Alasan:
- alur yang didemokan (surplus Cianjur → kebutuhan Jakarta → approval 4 mata → PO → ledger →
  KPI) berjalan **end-to-end pada DB klon**, dengan penolakan yang benar pada setiap jalur
  negatif (7 skenario), dan gate invarian demo PASS 59/0.
- tidak ada tes regresi yang gagal karena kode; satu kegagalan = data demo yang bisa dipulihkan
  dengan menjalankan ulang penyemai.
- syarat: (a) putuskan R-01 (data kesegaran **atau** semantik verdict) supaya panel verifikasi
  tidak mengejutkan juri; (b) uji jalur AgentCore + tunnel H-1; (c) segarkan kasus bukti demo.

### STAGING_READY — **BELUM**

Alasan: staging berarti dipakai orang di luar operator demo (data kerja nyata). AUD-9B-29
(safety/kesegaran salah sasaran) **sudah ditutup** 27 Oktober 2026, tetapi tiga hal lain masih
menghalangi dan tidak bisa ditutup dengan konfigurasi: (1) AUD-9B-24/26 (auditor bisa hilang &
gerbang kualitas tidak memeriksa angka), (2) AUD-9B-16 (bukti tidak wajib), (3)
AUD-9B-01/02/03/04 (angka SDC/kesegaran tidak dapat direproduksi). Semua P0 dan empat P1 di atas
harus tertutup dulu, plus keputusan tertulis AUD-9A-19.

### PRODUCTION_READY — **TIDAK**

Alasan: seluruh alasan STAGING berlaku, ditambah dependensi yang tidak layak produksi dan
terbukti rapuh: verifier tidak independen dari penulis narasi (AUD-9A-03 bagian model), jalur
agent bergantung pada quick tunnel + JWT statis (AUD-9A-07), gerbang sesi demo memblokir
komputasi murni (AUD-9A-06), `500` untuk input tidak valid (AUD-9B-31), dan tidak ada uji beban,
aksesibilitas, maupun E2E browser pada sesi ini. Tidak ada bukti kapasitas, tidak ada rotasi
kredensial, dan observabilitas agent belum diuji di luar demo.

## 5. Yang harus dikerjakan sebelum verdict berikutnya naik

1. ~~**AUD-9B-29 (P0)**: ubah himpunan batch Safety/Freshness ke lokasi **sumber**; scope
   exclusion per keputusan.~~ **SELESAI 27 Okt 2026** (repair log §8) — guard memakai himpunan
   batch sumber + helper cakupan exclusion bersama; `execute` ikut memakai aturan yang sama dan
   fail-closed bila sumber tak teridentifikasi. Sisa batas: `supplier_exclusions` tidak punya
   kolom komoditas (butuh migrasi bila kelak diperlukan).
2. **AUD-9B-01/02 (P1, data)**: hitung ulang `freshness_score`/`usable_until` dengan
   `compute_freshness_score`; buang literal 0,82. Setelah itu R-01 hilang sendiri dan
   `blocking` untuk `needs_verification` bisa dinaikkan (repair log §5b).
3. **AUD-9B-16 (P1)**: segarkan kasus `bukti-hari-ini`, lalu tegakkan kelengkapan bukti pada
   approve/execute.
4. **AUD-9A-03 (sisa P1)**: slot model/prompt verifier terpisah dari supervisor.
5. **AUD-9B-24/25/26 (P1)**: auditor wajib menghasilkan jejak (tidak `except: pass`), kontradiksi
   supply↔demand masuk daftar pemeriksaan, `verify_run` memeriksa angka.
6. Sebelum demo: uji AgentCore + tunnel H-1 (R-02), putuskan R-01 secara tertulis, dan jalankan
   gate yang sama pada DB yang akan dipakai di panggung.
