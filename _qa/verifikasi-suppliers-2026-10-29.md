# Verifikasi penutup — redesain halaman Pemasok (S7)

Tanggal: 29 Okt 2026 · Lingkup: tab **Suppliers** (`frontend/components/SupplierBoard.tsx` dan
komponen pendukungnya) · Rencana: `_qa/rencana-redesign-suppliers-2026-10-29.md` (S0–S7).

## 1. Keadaan kode

| Pemeriksaan | Hasil | Bukti |
|---|---|---|
| `npx tsc --noEmit` | **bersih** (0 galat) | dijalankan 29 Okt 2026 18:56 |
| Suite frontend penuh | **2905 lulus / 3 gagal / 2 dilewati / 2 todo** (270 berkas) | `npx vitest run` |
| 3 gagal itu milik siapa | `tests/agent-log-redesign-kontrak.test.tsx` — Tahap 4 Agent Log (`stageFilter`), sedang dikerjakan alur kerja lain; `components/AgentActivityPanel.tsx` berubah 18:51 | bukan berkas Suppliers |
| Tes baru sepanjang S0–S7 | 5 berkas, 47 tes | lihat §3 |

## 2. Pengukuran di peramban (bukan klaim)

Pratinjau statis `_qa/preview/suppliers.html` memuat markup hasil render server di tiga bingkai
(360 / 760 / 1440 px), disajikan lewat `python -m http.server` di `127.0.0.1:8899`, lalu **diukur
dari DOM hidup** dengan `getBoundingClientRect()`:

| Bingkai | lebar isi | `scrollWidth − clientWidth` | elemen yang melewati tepi kanan | target sentuh < 44 px | teks < 12 px |
|---|---|---|---|---|---|
| 360 px (ponsel) | 345 | **0** | **tidak ada** | **tidak ada** | **tidak ada** |
| 760 px (tablet) | 745 | **0** | tidak ada | tidak ada | tidak ada |
| 1440 px (desktop) | 1440 | **0** | tidak ada | tidak ada | tidak ada |

Catatan cara mengukur: `scrollWidth − clientWidth` menangkap gulir tingkat dokumen; pemeriksaan
kedua (setiap elemen dengan `right > clientWidth`) menangkap isi yang meluber di dalam wadah
bergulir — dua hal berbeda, keduanya nol.

Pengukuran pertama (sebelum dua perbaikan di bawah) menemukan **dua pelanggaran nyata**:
`section-jump-list` melebar sampai 557 px dan tabel register sampai 409 px di bingkai 360.
Keduanya diperbaiki, lalu diukur ulang sampai nol.

## 3. Yang diperbaiki khusus di S7 (hasil pengukuran, bukan rencana)

1. **Navigasi lima bagian** — dulu satu baris `overflow-x: auto` dengan scrollbar disembunyikan:
   dua tujuan terakhir tidak terlihat dan tidak ada tanda masih ada isi. Kini membungkus
   (`flex-wrap: wrap`) di ≤720 px; semua tujuan terlihat, tautan tetap 44 px.
2. **Tabel register eksklusi** — satu-satunya tabel Pemasok yang belum punya mode kartu; di 360 px
   ia 409 px di dalam wadah bergulir. Kini `.register-table` + `data-label` jadi kartu di ≤760 px.
3. **Tautan "Ke daftar pemasok"** di kepala papan kiriman — 102×18 px, satu-satunya target sentuh
   di bawah 44 px; kini `min-height: 44px` di perangkat sentuh.

## 4. Berkas pratinjau

- `_qa/preview/suppliers.html` — tiga bingkai 360 / 760 / 1440 px berdampingan (buka di peramban).
- `_qa/preview/suppliers-isi.html` — halaman itu sendiri (markup hasil render + tautan CSS aplikasi).
  Huruf Fira dideklarasikan ulang dengan jalur relatif karena CSS aplikasi memakai `/fonts/...`
  absolut; tanpa itu pratinjau jatuh ke huruf cadangan dan lebar teksnya tidak mewakili aplikasi.
- Data contoh berbentuk respons API demo (`distance_km`, `road.geometry`, `journey.state`,
  `ringkasan`, `excluded_at`) sehingga pratinjau menampilkan keadaan **terisi**, bukan
  "belum tersedia".

## 5. Sisa pekerjaan yang diketahui

- Tiga tes Agent Log merah dan galat tipe `stageFilter` — milik alur kerja paralel, tidak disentuh.
- Tombol "Hanya dalam jangkauan" menyaring daftar; papan kiriman dan register tidak ikut
  tersaring. Perilaku ini disengaja (angka papan adalah keadaan jaringan), tetapi belum
  dinyatakan di layar.
- Peta & grafik masih memakai biru (`--status-live`, `--route-live-*`, `--cat-*-*`) karena di sana
  biru membawa arti. Bila pemilik ingin netral juga, itu perubahan terpisah.
