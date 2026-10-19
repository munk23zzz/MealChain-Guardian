# Data demo Jakarta lengkap — 19 Okt 2026

Permintaan pemilik: *"buat data mock untuk jakarta lengkap jadi semua indikator ada datanya
tidak 0 ataupun tidak ada data dan perbanyak datanya"*.

## 1. Keadaan sebelum (diukur, bukan dikira)

Probe GET ke backend :8000 dengan akun `sppg.head@demo.local` + sapuan 10 tab di :3010:

| Indikator | Keadaan sebelum | Bukti |
|---|---|---|
| Review 7 agen (Agent Log) | **kosong** — "Belum ada review 7 agen" | `agent_traces.agent_name` **NULL untuk 100% baris** (hanya step_name terisi) |
| Integritas bukti (Decision & Evidence) | **0 dari 2.350 blok masih tertaut** | seluruh `ledger_blocks` menunjuk keputusan sisa pengujian yang sudah dihapus |
| Pemasok dieksklusi | **0 baris** | `GET /supplier-exclusions` → `count: 0` |
| Procurement Price Deviation (KPI 24 jam) | **no_data** — "tidak ada record pada periode ini" | tidak ada pasangan acuan+ kutipan bertanggal hari ini |
| Decision Time (KPI) | 2 sampel (coverage 0,09) | tidak ada trace langkah `ACT` + PO terbit |
| Evidence Completeness (KPI) | 2 sampel (coverage 0,04) | hanya 2 keputusan punya bukti konsisten |
| Batch Jakarta | 8 baris | 1 gagal uji, tanpa variasi verifikasi/pending |
| Keputusan menunggu tindakan | 6 | daftar tipis untuk dicari di pemilih |
| Pasangan surplus→kekurangan | **tidak ada** (juga karena `demand_records` hanya 13 baris) | peta jaringan: 1 lokasi terpetakan untuk akun SPPG, 0 surplus terukur di akun nasional |
| Agenda "Hari Ini" | menu/delivery/limbah/pasokan/harga ada, tetapi volume tipis (8 supply, 8 harga) | `GET /agenda` |

## 2. Yang dibuat

Modul baru: **`backend/app/seed/jakarta_lengkap.py`** (`python -m app.seed.jakarta_lengkap`).

Aturan yang dipegang:

1. **`origin='demo'`** untuk semua baris; baris kanonik `origin='seed'` tidak disentuh → tes yang
   memaku angka seed tetap sah.
2. **Id UUID5 deterministik** (`uuid5(URL, "mcg:jakarta-lengkap:…")`) → dijalankan dua kali tidak
   menggandakan apa pun (terbukti: `po: 0` pada eksekusi kedua).
3. **Relatif `now`**, jadi metrik 24 jam/jendela hari ini benar-benar berisi.
4. Nilai status mengikuti CHECK constraint DB (tidak ada kosakata karangan).

Isi per pemanggilan (diukur pada eksekusi terakhir):

| Bagian | Jumlah |
|---|---|
| `demand_records` (10 lokasi × 4 komoditas × 15 hari) | 600 |
| `supply_records` (Jakarta + 3 kota surplus × 4 komoditas × 2 slot × 21 hari) | 672 |
| `batches` Jakarta (7 kategori umur × 4 komoditas) | 40 — 6 gagal uji, 5 perlu verifikasi, 3 pending |
| `batch_receipts` | 12 |
| `price_signals` (acuan 05.30 + 2 kutipan 07.15/11.15 × 21 hari × 4 komoditas) | 252 |
| `menu_plans` + `delivery_events` | 22 + 8 |
| `disposal_events` (dengan mitra pengolahan) | 42 |
| `decisions` (6 status, 5 tipe) | 30 |
| `approvals` / `decision_evidence` (3 jenis, `is_consistent=true`) | 28 / 90 |
| `agent_traces` (8 kartu: supervisor + 7 worker; + `ACT` untuk executed/approved) | 251 |
| `sap_mock_purchase_orders` (hanya untuk keputusan `executed`, `MC-…`) | 7 |
| `supplier_exclusions` (2 aktif, 1 dicabut) | 3 |
| `ledger_blocks` | 160 (dibangun ulang, semua tertaut) |

## 3. Tiga jebakan yang ditemukan saat mengerjakan ini

1. **`agent_name` harus kunci worker apa adanya** — `"supply"`, bukan `"supply_agent"`.
   `lib/agent-swarm.ts` mencocokkan delapan nama itu persis; dengan akhiran `_agent` panel tetap
   berkata "Belum ada review 7 agen" walau 8 baris trace ada di DB. Dikunci oleh
   `tests/test_jakarta_lengkap.py`.
2. **`menu_plans` ber-kunci alami `(location_id, plan_date)`** — menulis dengan id UUID5 sendiri
   langsung melanggar `uq_menu_plans_loc_date` karena seed kanonik sudah punya baris untuk sebagian
   tanggal. Seeder mencari baris yang ada dulu, baru memakai id-nya.
3. **`pytest` menghapus baris `origin='demo'`** (fixture membersihkan). Sesudah menjalankan suite,
   batch demo hilang dan papan keamanan kembali kosong → **seed ulang setelah tes**, jangan
   menyimpulkan regresi.

## 4. Keadaan sesudah (terukur di :3010, akun SPPG Head)

| Indikator | Sesudah |
|---|---|
| Agent Log — review 7 agen | 8 kartu tampil: supervisor + Pasokan, Permintaan, Kesegaran, Keamanan, Harga, Logistik, Bukti |
| Integritas bukti | **160 dari 160 blok tertaut** (rasio 1,00), `valid: true`, tanpa `coverage_warning` |
| Pemasok dieksklusi | 3 baris (2 `active`, 1 `revoked`) |
| KPI 24 jam | **7 dari 7 metrik `available`**: deviasi harga 0,89% (8 sampel), Decision Time 17,1 mnt (7 sampel), Evidence Completeness 100% (10 sampel) |
| Keamanan Pangan | 43 batch diperiksa · 29 aman · **6 gagal uji** (1.011 kg) · 5 perlu verifikasi · 9 kedaluwarsa |
| Purchase order | 9 PO (sebelumnya 2) |
| Agenda hari ini | menu 1 · kiriman 2 · limbah 5 · pasokan 16 · harga 20 · batch kedaluwarsa 10 · keputusan 64 |
| Rekomendasi menunggu tindakan | 26 (sebelumnya 6) |
| Rute jalan kiriman | 34 rute baru disinkronkan dari OSRM, 0 gagal — "estimasi tiba belum ada" hilang |

## 5. Batas yang jujur (bukan bug data)

- **Pasangan surplus→kekurangan hanya terlihat di akun nasional (BGN Monitor).** Akun SPPG Head
  cakupannya satu lokasi (`/balance/map` sengaja mengirim 1 lokasi), jadi tidak ada pasangan
  untuk dialokasikan. Dengan akun BGN: telur 3 surplus/7 kurang, ayam 2/8, wortel 2/8, beras 3/7.
- **"Tidak tersedia" pada komposisi putusan verifikator** bukan data kosong: sebagian run memang
  belum dinilai (3 setuju · 1 tidak setuju · 4 belum dinilai). Mengisinya berarti mengarang putusan.
- **Status integrasi AWS** ("belum dimulai", "gagal-tertutup") berasal dari probe lingkungan, bukan
  seed — tidak diubah.
- Data ini **hilang lagi setelah `pytest`**; jalankan ulang `python -m app.seed.jakarta_lengkap`
  sebelum demo.

## 6. Gerbang

- `ruff check` bersih untuk modul + tes baru.
- `pytest tests/test_jakarta_lengkap.py tests/test_demo_activity.py tests/test_sap_orders_api.py`
  → 14 lulus, 2 gagal karena `commodity_name` hilang dari `app/api/sap_orders.py` (berkas itu
  dikembalikan ke HEAD oleh sesi lain); setelah field itu dipulihkan → **12 passed** untuk
  `test_sap_orders_api.py`, dan seluruh 3 berkas lulus.
- Frontend tidak diubah pada langkah ini.
