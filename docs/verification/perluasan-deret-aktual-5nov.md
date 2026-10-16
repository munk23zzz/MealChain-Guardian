# Perluasan deret aktual sampai 5 November

Tanggal: 2026-10-16 (malam) – 2026-10-17.

## Masalah yang diperbaiki

Deret AKTUAL (pasokan & harga) berhenti di **8 Oktober 2026**, sehingga:

- tab KPI hanya berisi "belum ada data" untuk jendela 24 jam dan 7 hari;
- kalender "Hari Ini" menulis "tidak ada catatan" untuk hari-hari setelah 8 Okt;
- demo untuk juri kehilangan 4 minggu terakhir data operasional.

Akar: `ACTUAL_HORIZON_MARGIN = timedelta(days=1)` di `app/seed/timeseries.py`
dihitung relatif ke `CANONICAL_REF` (8 Okt), jadi baris aktual sengaja berhenti
≥24 jam sebelum jangkar itu.

## Yang diubah

1. **`ACTUAL_REF` dipisahkan dari `CANONICAL_REF`** (`app/seed/timeseries.py`).
   - `CANONICAL_REF` = 8 Okt: TIDAK digeser — ia jangkar `stable_uuid` kasus,
     snapshot "Segarkan ke hari ini", dan 26 berkas tes.
   - `ACTUAL_REF` = 5 Nov (= `DEFAULT_END`): batas baris aktual.
   - `actual_cutoff`, `actual_timestamps`, `preview_timeseries`,
     `generate_timeseries`, `pastikan_deret_demo` kini memakai `ACTUAL_REF`
     sebagai default `ref`.
   - `ACTUAL_HORIZON_MARGIN` tetap ada, sekarang relatif ke `ACTUAL_REF`
     (baris terakhir = 4 Nov 12:00, bukan lagi 8 Okt 12:00).
2. **Jaring keamanan `pastikan_deret_demo()`** + fixture sesi
   `jaring_deret_demo` (`tests/conftest.py`) + berkas tes
   `tests/test_deret_demo_aman.py`.
3. **Isolasi tes penerimaan barang**: `tests/test_receipts_api.py` dulu
   membersihkan `DELETE FROM batch_receipts WHERE batch_id = <Jakarta>` — yaitu
   menghapus SELURUH riwayat penerimaan batch itu, bukan hanya baris buatannya.
   Kini teardown menghapus **per id** (`_bersihkan(*ids)`) dan asersi tidak lagi
   memakai `len(items) == 1` (yang justru benar hanya bila tak ada catatan lain).
4. **Laporan seeder** (`app/seed/seed_data.py`): penyisipan
   `sap_mock_material_stock` dan `sap_mock_purchase_orders` kini ikut dihitung
   (`counts[...]`), sebab sebelumnya seeder menulis "Row baru: {}" padahal baris
   baru benar-benar masuk.

## Angka resmi (bukan taksiran)

Satu cap waktu tiap 12 jam × 30 pasangan lokasi–komoditas:

| Tabel | Rencana generator | Terisi (demo) | Kanonik (seed) | Total |
|---|---|---|---|---|
| `supply_records` | 3.900 | 3.870 | 30 | **3.900** |
| `price_signals` | 4.040 | 4.010 | 44 | **4.054** |
| `menu_plans` | 660 | 590 | 70 | **660** |

- Rentang: **1 Sep 00:00 → 4 Nov 12:00 UTC**; rencana menu sampai **5 Nov**.
- Selisih 30 baris supply & harga: stamp `8 Okt 12:00` sudah dipegang baris
  kanonik (`origin='seed'`); generator sengaja TIDAK menimpanya. Karena itu
  `pastikan_deret_demo()` mengukur kelengkapan **agnostik-origin** (jumlah baris
  di dalam rentang dari semua origin), bukan "baris demo == rencana".

## Dampak ke fitur

| Fitur | Sebelum | Sesudah |
|---|---|---|
| KPI jendela 24 jam | praktis kosong | 5 dari 7 kartu `available` |
| KPI jendela 7 hari | 1 kartu | 6 dari 7 kartu |
| KPI jendela 30 hari | 7 kartu | 7 dari 7 kartu |
| Kalender "Hari Ini" | "tidak ada catatan" setelah 8 Okt | pasokan, harga, rencana terisi |

Kartu yang tetap `no_data` menyebut alasannya apa adanya (mis. "tidak ada
disposal event pada periode ini") — aturan proyek: metrik tanpa data tidak
diganti nol atau proksi.

## Isi lewat jalur resmi (bukan INSERT langsung)

- `batch_receipts`: 4 catatan penerimaan batch Jakarta lewat `POST /receipts`
  (daftar periksa bervariasi + isian "Lainnya").
- `supplier_exclusions`: 1 usulan lewat `POST /supplier-exclusions/proposals`
  (status `proposed`, terhubung ke decision `pending_approval`).
  Usulan kedua tidak bisa dibuat: bukti harus batch milik pemasok itu, dan hanya
  ada satu batch dalam scope SPPG Head (Jakarta).
- `sap_mock_material_stock`: 6 → 9 baris (matriks 3 material × 3 plant lengkap)
  lewat penambahan di `data/seed/sprint1_seed.json` + seeder resmi (idempoten).

## Yang sengaja TIDAK diubah

- `delivery_events` (70, 1–7 Okt) dan `disposal_events` (20, 4–7 Okt): perluasan
  seri kiriman/limbah tidak dipilih. Kartu "Avoidable Food Loss" pada jendela
  pendek karena itu tetap menulis "tidak ada disposal event pada periode ini".
- `demand_records` (288, 27 Agu–8 Okt): generator deret tidak menulis demand.
- `CANONICAL_REF` dan seluruh baris kanonik `origin='seed'`.

## Cacat isolasi tes yang ikut ditemukan

1. **`tests/test_receipts_api.py`** menghapus `DELETE FROM batch_receipts WHERE
   batch_id = <Jakarta>` — yaitu SELURUH riwayat penerimaan batch itu, bukan
   hanya baris buatannya (batch Jakarta satu-satunya batch dalam scope peran
   SPPG). Kini teardown hapus **per id**; asersi tidak lagi `len(items) == 1`
   (yang justru benar hanya bila tak ada catatan lain).
2. **`tests/test_demo_timeseries_api.py::test_refresh_hari_ini_...`** menaruh
   rollback SETELAH asersi tanpa `try/finally`. Satu kegagalan di tengah
   meninggalkan baris ber-REF jam di DB kerja: residunya nyata — **120 baris
   `demand_records`** ber-`needed_by` 2026-10-19 tertinggal dan menyusup ke
   jendela "3 observasi terbaru", sehingga `/demand/forecast/Jakarta/telur`
   meleset (2.140 alih-alih 2.120). Rollback kini selalu jalan.
   Residu lama sudah dibersihkan: `demand_records` kembali 168 baris kanonik.
3. **`pastikan_deret_demo()`** + fixture `jaring_deret_demo` mengembalikan deret
   demo seandainya ada run yang mati setelah purge.

## Catatan lingkungan (penting saat menilai hasil tes)

Sesi/proses lain menjalankan pytest terhadap **DB kerja yang sama** selama
pekerjaan ini. Gejalanya khas dan sudah terverifikasi:

- `401`/`{"detail":"token tidak valid"}` di berkas yang tidak bersangkutan —
  sapuan user `%@test.local` milik conftest sesi lain;
- deret demo tampak kosong sesaat (purge sesi lain di tengah run);
- `ForeignKeyViolationError` pada `menu_plans`/`supply_records` — lokasi
  sementara milik tes sesi lain dibuat lalu dihapus saat generator membaca
  pasangan seed.

Gerbang penuh sebaiknya dijalankan saat DB sepi (`SELECT count(*) FROM
pg_stat_activity WHERE datname='mealchain' AND state <> 'idle'`), dan sebaiknya
tidak dua suite sekaligus terhadap DB yang sama.

## Cara memulihkan bila DB kerja ter-purge

```bash
docker compose exec -T backend python -c "
import asyncio
from app.seed.timeseries import pastikan_deret_demo
print(asyncio.run(pastikan_deret_demo()))
"
```

Idempoten: bila deret lengkap, `{"dipulihkan": false, "kurang": {}}`.
