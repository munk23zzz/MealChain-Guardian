# Audit menyeluruh MealChain Guardian — 22 Oktober 2026

Tujuan: memastikan semua proses yang dipakai user berjalan, bukan hanya layar yang tampak.
Metode: tiga lapis — (1) sapu seluruh endpoint dengan tiga peran, (2) jalankan alur tulis
end-to-end seperti yang dilakukan UI, (3) telusuri semua layar per peran lewat browser sambil
merekam `console.error`, `window.onerror`, dan setiap respons HTTP >= 400.

## 1. Cakupan yang diuji

| Lapis | Cakupan | Hasil |
|---|---|---|
| Endpoint GET | 40 path × 3 peran × kombinasi parameter = **156 panggilan** | **0 gagal** (tanpa 5xx/timeout) |
| Alur tulis | keputusan (analyze → fuse → create → propose → verify → approve → execute), penerimaan (buat → setujui), karantina (tahan → lepas), eksklusi pemasok (usul → pulihkan), sesi demo (mulai → perpanjang → akhiri), agent run, event1, refresh | semua 2xx sesuai kontrak (201/200/409) |
| Layar per peran | SPPG Head 10 tab, Nutritionist 10 tab, BGN Monitor 9 tab (termasuk Pengaturan) | semua merender, **0 galat konsol**, **0 HTTP >= 400** setelah perbaikan |
| Proses lewat UI | login 3 peran, jalankan agent (selesai · primary:agentcore), setujui keputusan (dual approval 1 dari 2), setujui penerimaan + masukkan stok, pencarian pemasok tanpa hasil, paginasi tabel | berhasil |
| Ketahanan parameter | `limit=0`, `limit=99999`, `limit=-5`, tanggal terbalik, tanggal ngawur, komoditas kosong, `as_of` ngawur, `limit=abc` | semuanya 4xx (422/404), tidak ada 5xx |
| Autentikasi/otorisasi | tanpa token (401), peran salah (403), login salah (401 dengan pesan Indonesia), field kurang (422) | sesuai |

## 2. Cacat yang ditemukan dan diperbaiki

### 2.1 Layar BGN Monitor kosong total saat membuka Overview (kritis)

Gejala: peran BGN Monitor menekan Overview → layar putih. Konsol:
`Uncaught Error: Style is not done loading.` berulang, lalu
`The above error occurred in the <NotFoundErrorBoundary> component: at SupplyMap`.

Sebab: `syncTruk` menambah `source`/`layer` GeoJSON ke peta tanpa menunggu gaya peta siap.
Data BGN (10 lokasi + 105 kiriman) tiba lebih dulu daripada event `load` MapLibre, sehingga
MapLibre melempar galat; error boundary menangkapnya dan mengosongkan seluruh halaman.

Perbaikan (`frontend/components/SupplyMap.tsx`):
- penjaga `if (!map.isStyleLoaded()) return;` sebelum `addSource` layer ekor truk;
- sinkronisasi ulang didaftarkan pada event `load` (`peta.on("load", syncTruk)`);
- `setPaintProperty` pada penyorotan jalur dibungkus `try/catch` agar gaya yang sedang dimuat
  ulang tidak menjatuhkan halaman.

Bukti sesudah: 9 tab BGN (termasuk Overview) merender, 0 galat konsol, 0 respons >= 400.

### 2.2 Endpoint evaluasi kesegaran/keamanan membalas 500 untuk `batch_id` tidak valid

Gejala: `POST /freshness/evaluate` dan `POST /safety/evaluate` dengan `batch_id` kosong atau
bukan UUID membalas **500** (`asyncpg DataError: invalid UUID`), bukan 422.

Sebab: `batch_id` dideklarasikan `str` di model Pydantic lalu diteruskan apa adanya ke query.

Perbaikan: tipe diubah menjadi `UUID` (`backend/app/api/freshness.py`, `safety.py`).
Bukti sesudah: `""` → 422, `"bukan-uuid"` → 422, UUID tak ada → 404, UUID sah → 200.

## 3. Catatan (bukan cacat, tapi perlu diketahui)

1. `PATCH /admin/users` hanya menerima `role` dan `location_id`; field lain diabaikan tanpa
   pesan (Pydantic tidak `extra="forbid"`). UI hanya mengirim dua field itu, jadi tidak
   memengaruhi pemakaian — tetapi integrasi lain yang salah nama field tidak akan tahu.
2. Peta menampilkan satu komoditas pada satu waktu; tidak ada mode "semua komoditas".
3. Kiriman "di jalan" hanya bertahan 5–9 menit setelah penyemaian (semua rute demo dalam kota).
   Untuk segmen peta, tekan "Siapkan data demo" tepat sebelum menampilkan peta.
4. Tab Surplus & Limbah dan Agent Log bersifat baca-saja (tidak ada aksi tulis) — sesuai desain.
5. `demo/template/rebuild` butuh 33 detik; UI menonaktifkan tombol selama proses, tidak ada
   permintaan ganda.

## 4. Verifikasi

| Pemeriksaan | Hasil |
|---|---|
| `tsc -p tsconfig.json --noEmit` | bersih |
| `vitest run` (frontend) | **1761 lulus / 0 gagal** (62,8 detik) |
| Gerbang backend terpisah (`scripts/gerbang-db-terpisah.sh`) | **1283 lulus / 18 skip / 0 gagal** (784,2 detik), termasuk tes regresi `batch_id` |
| Joule (bridge A2A, mode DEMO) | **14/14 lulus**, agent card 1.4.0 / 13 skill |
| Sapu endpoint | 156 panggilan, 0 gagal |
| Telusur layar | 29 tab lintas 3 peran, 0 galat konsol |

## 5. Tidak diuji (jujur)

- Perangkat mobile fisik dan pembaca layar (audit aksesibilitas mendalam terpisah).
- Beban/kinerja (mis. 100 pengguna serentak) dan uji tekanan.
- Integrasi Joule asli (butuh tenant BTP); yang diuji hanya kontrak A2A dengan bridge lokal.
- SAP S/4HANA nyata (butuh kredensial destination).
