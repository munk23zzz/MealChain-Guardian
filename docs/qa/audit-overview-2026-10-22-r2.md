# Audit ulang halaman Overview — 22 Oktober 2026 (r2)

Tujuan: memastikan tidak ada proses yang error atau angka yang tidak sesuai di tab **Overview**,
setelah perbaikan audit menyeluruh pagi hari ini (`audit-menyeluruh-2026-10-22.md`).

Metode: aplikasi hidup di `:3010` (frontend) + `:8000` (backend), empat sesi login nyata.
Tiap sesi direkam: `console.error`, `window.onerror`, `unhandledrejection`, setiap respons
HTTP >= 400, lalu setiap angka di layar dicocokkan dengan respons API yang sama yang dipakai UI.

## 1. Sesi yang ditelusuri

| Peran (akun demo) | Tab Overview | Galat JS | HTTP >= 400 | 5xx backend |
|---|---|---|---|---|
| Kepala SPPG Jakarta (`sppg.head@demo.local`) | merender | 0 | 0 | 0 |
| Nutritionist Jakarta | merender | 0 | 0 | 0 |
| BGN Monitor (`bgn.monitor@demo.local`, 10 lokasi) | merender | 0 | 0 | 0 |
| Kepala SPPG Surabaya (lokasi non-Jakarta) | merender | 0 | 0 | 0 |

Interaksi yang diuji di Overview: ganti komoditas (telur/ayam/beras/wortel), ganti lensa
Kuantitas/Kesegaran, lima tautan "Bagian" (Ringkasan, Peta & antrean, Kecukupan, Kiriman,
Telemetri), "Tinjau rekomendasi" (pindah ke Recommendation Feed), klik penanda peta (popup),
ganti cakupan BGN (nasional -> Bandung -> nasional). Semua berjalan tanpa galat.

Catatan: satu-satunya kegagalan jaringan yang tercatat adalah `AbortError` tile OpenStreetMap
saat peta digeser/zoom — normal (permintaan dibatalkan), bukan galat aplikasi.

## 2. Angka yang dicocokkan dengan API (semua cocok)

| Yang tampil | Nilai layar | Nilai API |
|---|---|---|
| Keputusan Jakarta | 6 menunggu tindakan + 1 lewat tenggat, 13 dipantau | 6 `pending_approval` + 1 `verifier_flagged` (1 lewat tenggat), 13 baris |
| Keputusan Surabaya | 2 menunggu + 2 lewat tenggat, 9 dipantau | 3 `pending_approval` + 1 `verifier_flagged` = 4, 2 lewat tenggat, 9 baris |
| Keputusan BGN | 15 menunggu + 5 lewat tenggat, 43 dipantau | 13 `pending_approval` + 3 `approved` + 4 `verifier_flagged` = 20, 5 lewat tenggat, 43 baris |
| Neraca jaringan BGN (telur) | 4.900 kg / 4.691 kg, +209 kg (4%) | Σ`/balance/map` = 4.900 / 4.691 |
| Lokasi BGN | 2 surplus · 8 shortage · 10 terpetakan | 2 `surplus`, 8 `shortage`, 10 baris |
| Pemasok dalam jangkauan | 7/14 (150 km) | `/suppliers?...&commodity=telur&max_distance_km=150` = 7 dari 14 |
| Kiriman (Jakarta, telur) | 3 tampil + 1 lain, 4 sudah tiba | `/supplier-routes?commodity=telur&location=Jakarta` = 4, semua `sudah_tiba` |
| Kiriman (BGN, telur) | 3 tampil + 28 lain; 1 berjalan; 21 sudah tiba | 31 rute: 21 `sudah_tiba`, 1 `di_jalan`, 3 `belum_berangkat`, 6 `tidak_diketahui` |
| Cakupan per komoditas | telur 300/1.080 (28%), beras 900/3.010 (30%), ayam 80/215 (37%), wortel 360/158 (228%) | `/balance/map` + `/batches` = sama |

Regresi dua cacat pagi ini juga masih benar: `POST /freshness|safety/evaluate` dengan
`batch_id` bukan UUID -> **422** (bukan 500), UUID tak ada -> 404; Overview BGN Monitor
merender penuh (tidak ada layar kosong `Style is not done loading`).

## 3. Temuan yang belum beres

### 3.1 (P1) Dua angka "pasokan" berbeda di layar yang sama — yang terbesar menghitung stok gagal uji

Gejala terukur (Kepala SPPG Jakarta, komoditas **ayam**, satu layar):

- Tile hero: **"Selisih pasokan Jakarta −15 kg"**, "Pasokan terpantau **200 kg** dari 215 kg · **93%**",
  penanda peta "Jakarta kurang 15 kg", popup peta "Pasokan menutup **93%** kebutuhan".
- Panel Kecukupan pasokan (komoditas yang sama): **"80 kg layak · 200 kg tercatat", 37% cakupan, −135 kg**.

Sama di Surabaya, komoditas telur: hero **−12 kg / 98%** vs panel **240 kg layak · 600 kg tercatat,
39% cakupan, −372 kg**.

Sebab: hero, peta, dan popup memakai `supply_kg` dari `GET /balance/map`, yaitu **snapshot terakhir
tabel `supply_records`** (pembukuan), sedangkan panel Kecukupan memakai **stok batch yang layak**
(`safety_status = pass`, tidak ditahan, belum kedaluwarsa). Pada ayam Jakarta, 200 kg itu berisi
80 kg `pass` + 120 kg `fail`; di Surabaya telur, 600 kg berisi 240 kg layak + 360 kg `fail`.

Kenapa ini penting: halaman ini menjanjikan "safety status tidak pernah di-override". Angka
terbesar di layar menyatakan Jakarta hanya kurang 15 kg ayam, padahal 120 kg dari pasokan yang
dihitung itu **gagal uji keamanan**. Juri yang membandingkan dua angka di satu layar akan
bertanya mana yang benar. Kedua angka benar untuk definisinya masing-masing, tetapi labelnya
tidak membedakan.

Pilihan perbaikan (perlu keputusan pemilik):
1. Hero/peta/popup memakai stok layak (satu definisi dengan panel) — paling konsisten, tetapi
   peta menjadi bergantung pada `/batches` untuk semua titik.
2. Hero tetap `supply_records`, labelnya diperjelas ("pasokan tercatat") + baris kecil
   "dari itu N kg gagal uji / belum terverifikasi" supaya tidak ada klaim yang menyesatkan.
3. Panel Kecukupan yang diberi label eksplisit "stok layak" (sudah ada) dan hero diberi
   tautan "lihat stok layak" — paling murah, tetapi dua angka tetap hidup berdampingan.

### 3.2 (P2) Cakupan BGN hanya menggeser hero + Kecukupan, bukan seluruh halaman

Pilih **Bandung** di dropdown "Cakupan lokasi yang ditampilkan" (BGN Monitor):

| Elemen | Ikut cakupan? |
|---|---|
| Tile hero | ya — "Selisih pasokan **Bandung** −138 kg, kurang 26%" |
| Panel Kecukupan | ya — "**Bandung** · 4 komoditas" |
| Subjudul peta | tidak — tetap "Peta **10 lokasi** SPPG" |
| Tile "Pasokan terpantau" | tidak — tetap 4.900 kg / 4.691 kg "kebutuhan **jaringan**" 104% |
| Baris "2 lokasi surplus · 8 shortage · 10 terpetakan" | tidak — tetap nasional |
| Alert | tidak — tetap "**8 lokasi** shortage pada telur — Bandung, Jakarta, …" |
| Peta + penanda | tidak — 10 penanda, 14 pemasok nasional |
| "Perlu keputusan" | tidak — 15 (nasional) |

Tidak ada galat; ini soal janji label. Dua jalan keluar: (a) ganti label dropdown menjadi
"Lokasi untuk angka ringkasan" dan tambahkan keterangan "peta & antrean tetap nasional", atau
(b) benar-benar menyaring peta/alert/antrean ke lokasi terpilih.

### 3.3 (P3) Sepuluh pemasok diletakkan tepat di koordinat SPPG tujuannya

`suppliers.latitude/longitude` untuk 10 pemasok (satu per kota) **persis sama** dengan koordinat
lokasi SPPG kotanya, sehingga 20 dari 125 batch berjarak lurus 0,0 km dan OSRM tidak bisa
menghasilkan rute (titik asal = titik tujuan). Yang tampil di Overview Kepala SPPG Surabaya:

> UD Surabaya Telur Jaya → SBY · "Perjalanan belum bisa dipastikan" · "Jalur jalan rute jalan
> belum disinkronkan dari OSRM — jarak tempuh & estimasi tiba belum bisa dipastikan" ·
> "**0,0 km lurus (jarak udara)**" · 360 kg telur

Terlihat seperti proses gagal padahal datanya yang mustahil. Perbaikan: geser koordinat 10
pemasok itu beberapa ratus meter, atau sembunyikan baris "0,0 km lurus" bila jarak = 0.

### 3.4 (P3, kosmetik) Kata "jaringan" pada peran SPPG

Peran SPPG hanya melihat satu lokasi, tetapi tile kedua berbunyi "dari **1.080 kg kebutuhan
jaringan**" (Jakarta) / "612 kg kebutuhan jaringan" (Surabaya). Di peran SPPG sebaiknya
"kebutuhan lokasi ini".

## 4. Yang tidak diuji

- Beban/kinerja (Overview memanggil ±8 endpoint tiap 5 detik, termasuk `GET /batches?limit=500`).
- Aksesibilitas mendalam dan perangkat mobile fisik.
- Kondisi backend mati/timeout saat Overview terbuka (penanganan galat panel belum disimulasikan).
