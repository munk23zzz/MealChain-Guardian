# Location Network — halaman gabungan pasokan & kebutuhan (dokumen 03 §3, §6.3, §6.5)

Tanggal: 28 Oktober 2026. Spesifikasi: `D:\Downloads\03-location-network-supply-demand.md`.
Repo: `E:\hackathon\HackathonAWS\mealchain-guardian` (belum di-commit).

Bentuk halaman ini ditentukan oleh dua subagent: satu audit UI/UX (menimbang tiga bentuk,
memilih satu dengan bukti terukur) dan satu verifikasi fullstack (memeriksa tiap angka
sampai ke endpoint). Dokumen ini mencatat bentuk yang **berjalan di kode** saat verifikasi.

## Bentuk yang berlaku

| Bagian | Wujud |
|---|---|
| Ringkasan | Satu kartu: kalimat §6.3 (nada lewat `data-tone`), baris angka (kekurangan/kelebihan/seimbang/tanpa koordinat), dan kelengkapan §6.5 sebagai kaki kartu. |
| Daftar lokasi | Tabel `location-table` empat kolom: Lokasi · Wilayah · Selisih · Catatan. Urut dari yang paling parah (`sortBySeverity`). |
| Rincian | Baris yang dibuka memuat `SupplyDemandPanel` **di dalam tabel** (`aria-expanded`/`aria-controls`, accordion eksklusif). Empat kartu: pasokan, kebutuhan, selisih, perkiraan 7 hari — lalu tabel batch. |
| Pemilihan | Satu lokasi terparah dibuka otomatis **sekali** per kunjungan tab; menutup baris tetap bisa (`autoPilihRef`). |
| Tanpa | Peta, garis koridor, chip lokasi, kartu "Rincian per lokasi", dan popup. |

Keputusan bentuk diambil setelah mengukur bentuk sebelumnya: popup 640 px memaksa empat kartu
jadi 3+1 (tiga kartu 195 px di y=175, kartu keempat sendirian di y=292) dan badan popup
368 px dari isi 670 px membuat tabel batch mulai di y=491 sementara tepi panel di y=488 —
tabel batch tidak terlihat saat jendela dibuka.

## Cacat yang diperbaiki pada putaran ini

1. `TONE_CLASS` menempelkan kelas global (`is-danger`) ke elemen ber-CSS-module. Kelas modul
   di-hash, jadi selektor `.headline.is-danger` tidak pernah cocok: penekanan bahaya hilang
   tanpa error. Diganti selektor atribut `.summary[data-tone="danger"]`.
2. `ageLabel()` memetakan umur negatif ke "baru saja", sehingga catatan bertanggal 4 Nov
   (jam sistem 28 Okt) terbaca sebagai kondisi sekarang. Kini "waktu catatan di depan jam sistem".
3. Total lokasi 0 dibunyikan sebagai "tidak ada lokasi kekurangan" — kabar baik untuk data
   yang belum masuk. Kini "Belum ada lokasi … datanya belum masuk" dengan nada `unknown`.
4. Hitungan 0 dicetak dengan "· 0 kg", sehingga 0 terbaca sebagai hasil pengukuran. Kini kg
   hanya dicetak bila hitungan > 0.
5. Galat dan kesimpulan bisa tampil bersamaan ("gagal dimuat" + "tidak ada kekurangan") dan
   selama memuat kalimat kesimpulan sempat dirender. Kini saat galat hanya pesan + tombol
   "Coba lagi"; saat memuat hanya "Memuat saldo lokasi…" + rangka tabel.
6. Baris tidak bisa ditutup: efek "pilih otomatis" memilih ulang begitu `selected` jadi `null`
   (terukur di browser). Kini pemilihan otomatis hanya sekali per kunjungan tab.
7. Batch ber-`quarantine_status="quarantined"` tampil seperti stok biasa ("Aman") dan ikut
   dihitung "lolos uji", padahal `backend/app/api/batches.py` menyatakan batch ditahan bukan
   stok layak pakai. Kini badge "Ditahan" + dihitung terpisah.
8. "Aman | Aman" diulang di dua kolom tiap baris batch. Kolom masa layak kini hanya durasi.
9. Nilai mentah `mock SAP` dan format mesin "dibutuhkan 9 hari 7 jam lagi" diganti
   "catatan simulasi" dan "dibutuhkan 31 Okt 2026 (3 hari lagi)".
10. Hex di luar palet (`#fff7f6`, `#fef2f2`, `#eff6ff`, `#fca5a5`) dan `.page{gap:14px}` yang
    menimpa `board-page`; grid kartu `auto-fit` (penyebab kartu yatim) diganti eksplisit 4/2/1.
11. Copy aturan internal repo di layar operator ("Kalau suatu saat kosong, di sini akan
    tertulis … bukan 0 kg") dihapus; stempel "Data per 28 Okt 2026" (`snapshotNote`) ditambahkan
    supaya tanggal catatan terlihat, bukan hanya jam pengambilan.

## Perintah verifikasi

```
cd frontend && npx tsc --noEmit     # 0 error
cd frontend && npx next lint        # ✔ No ESLint warnings or errors
cd frontend && npx vitest run       # 202 berkas / 2.362 tes lulus (lihat catatan di bawah)
cd frontend && npm run build        # BUILD_ID GP2D05hcnICD2cJ5206ct, 4 halaman statis
```

Satu tes gagal di suite penuh: `tests/decision-drawer.test.tsx` ("mencetak status PO dalam
bahasa Indonesia") mencetak `submitted`. Itu berkas sesi lain yang sedang dikerjakan
(`Decision & Evidence`), bukan modul ini.

## Bukti UI (browser, dev server same-origin)

- **SPPG Head** (`sppg.head@demo.local`, `telur`): 1 baris (Jakarta) terbuka; kartu
  300 kg / 1.080 kg / kurang 780 kg / perkiraan 7.530,29 kg; tabel 5 batch (5 lolos uji);
  `document.querySelector("canvas") === null`; `[role="dialog"]` tidak ada.
- **Tutup/buka baris**: `aria-expanded` `true → false → true`, panel ikut hilang/muncul.
- **BGN Monitor** (`bgn.monitor@demo.local`): 10 baris, membuka baris kedua menutup baris
  pertama (1 terbuka dari 10), headline "8 lokasi kekurangan 968 kg; kelebihan 2 lokasi
  (1.177 kg) menutup seluruhnya dan menyisakan 209 kg".
- Pills: `telur` · `10 lokasi` · `Data per 28 Okt 2026` · `Sinkron HH.MM.SS WIB`.

## Batas — yang BELUM diperbaiki, dengan bukti

- **Dua snapshot dalam satu panel.** `/supply`, `/demand`, dan `/demand/forecast` membaca
  baris terakhir tanpa batas waktu, sedangkan `/balance` memotong `recorded_at <= now`.
  Terukur untuk Jakarta/telur: kartu 300 kg & 1.080 kg (baris 28 Okt) vs `/supply` 299,09 kg &
  `/demand` 1.087,22 kg (baris 4 Nov); selisih server 780 kg vs 788,13 kg bila dikurangi
  sendiri. Perbaikan menuntut parameter `as_of` di tiga endpoint itu (pola `_batas_waktu()`
  yang sudah dipakai `balance.py`) plus hook meneruskan `mapData.as_of`. Belum dikerjakan
  untuk putaran ini karena menyentuh endpoint yang dipakai panel lain.
- **`/batches` lintas lokasi** untuk peran SPPG (144 baris, 10 lokasi) — disengaja menurut
  `app/core/scope.py`; halaman ini menyaring sendiri. Risiko: jika total > 500 baris, batch
  lama satu lokasi keluar jendela dan rekap bisa berbunyi "tidak ada batch". Hari ini 144.
- **Ambang "catatan basi" 24 jam** adalah konstanta klien; server tidak mengirim ambang.
- **Komoditas** (`ayam`, `beras`, `wortel`) belum dibuka di browser untuk halaman ini;
  jalur datanya sama.
- **Bentrok sesi.** Sesi Hermes lain menulis berkas yang sama pada saat yang sama (S4-61
  mencatat bentuk "popup"). Bentuk yang berjalan di kode adalah tabel + rincian sebaris;
  pemilik perlu memilih satu dan menandai yang kalah sebagai dibatalkan.

## Putaran kedua — informasi berulang dihapus (28 Okt 2026)

Setiap fakta kini ditulis sekali:

| Sebelum | Sesudah |
|---|---|
| Kalimat ringkasan **dan** baris angka ("1 kekurangan · 780 kg") | Hanya kalimat ringkasan |
| Pil "N lokasi" + "Sinkron HH.MM.SS" (jam pengambilan) | Hanya "Data per 28 Okt 2026" (tanggal catatan) |
| Kotak kelengkapan selalu tampil, termasuk "semua aman" | Muncul hanya bila ada catatan kurang atau basi |
| Kolom "Catatan" berisi "lengkap" di semua baris | Kolom "Perlu dibaca" hanya dipasang bila ada baris bertanda |
| Caption tabel + keterangan tabel batch + rekap "0 gagal" | Rekap tanpa suku nol; caption dihapus |
| Pil komoditas statis yang menyerupai kontrol | Chips komoditas yang benar-benar bisa ditekan |

Cacat tata letak yang ikut diperbaiki: panel rincian (berisi tabel batch) diletakkan di dalam
`<td>`, sehingga tabel bersarang merusak lebar kolom tabel luar — di browser kolom "Selisih"
terdorong ke tepi kanan. Diganti daftar disclosure (grid 3–4 kolom, rincian sebagai blok di
bawah baris). Terukur: `document.documentElement.scrollWidth === clientWidth` (tidak ada gulir
horizontal) pada 1247 px.

Gerbang putaran ini: `tsc` 0 · `next lint` 0 · vitest **203 berkas / 2.367 tes** lulus ·
`npm run build` `BUILD_ID cidkYdagb5FLBY_2ljV0n`.

## Putaran ketiga — disamakan dengan bahasa desain konsol (29 Okt 2026)

Halaman ini dulu memakai CSS modul sendiri untuk grid, radius, warna, dan chevron,
sehingga terbaca sebagai aplikasi lain di dalam aplikasi. Sekarang memakai primitif
yang sama dengan tab lain: `board-page` → `PageHeader` (`page-header-pills`) → kartu
`card` berjudul (`board-card-head`) → tabel `location-table` di `board-table-wrap` →
filter `commodity-filters`/`commodity-pill`; tombol `button button-secondary|quiet`;
keterangan `evidence-note`. CSS modul yang tersisa hanya kalimat ringkasan, tombol
baris, dan angka rata kanan.

Teks yang dibuang karena mengulang:

| Dibuang | Karena |
|---|---|
| "dihitung server dari pasokan dan kebutuhan" | Keterangan proses, bukan data |
| "catatan simulasi" (sumber) | Umur catatan sudah menyatakan kesegarannya |
| "≥ 3 catatan permintaan" pada keyakinan perkiraan | Angka metode, bukan yang dibaca operator |
| Catatan "Perkiraan kebutuhan tidak tersedia" | Kartu perkiraan sudah menulis "—" + "belum ada perkiraan" |
| Badge "Aman" + "Ditahan" pada satu batch | Dua label berlawanan di satu baris; Ditahan kini mengalahkan Aman |
| "≤ 7 hari" bersama "4 hari 6 jam lagi" | Satu fakta dua kali; tinggal angka pastinya |
| "3 lolos uji" saat semua baris berbadge "Aman" | Sama dengan isi tabelnya |

Rincian lokasi keluar dari tabel: panel berisi tabel batch di dalam `<td>` merusak
lebar kolom tabel luar. Rincian kini kartu sendiri di bawah tabel (`id="rincian-lokasi"`),
baris memakai `aria-pressed` dengan penanda ▸/▾.

Gerbang: `tsc` 0 · `next lint` 0 · vitest 205 berkas / 2.417 tes lulus (1 gagal di
`tests/prd-nav.test.tsx`, milik pekerjaan sesi lain di `app/page.tsx`).

## Putaran keempat — copy & keadaan (29 Okt 2026, Langkah 3 rencana)

Rencana: `docs/plans/location-network-page-plan.md` §8 (aturan copy) dan §9 (keadaan khusus).

Yang berubah di layar:

| Keadaan | Sebelum | Sesudah |
|---|---|---|
| Kepala halaman | "Siapa kekurangan, siapa berlebih, dan isi catatan tiap lokasi." | "Siapa kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang." (satu sumber teks: `page.tsx` hanya mengirim kalimat nutritionist) |
| Memuat | `<p>Memuat…</p>` + pil "0 lokasi" | kepala tabel + 3 baris kerangka, pil jumlah disembunyikan ("0 lokasi" terbaca sebagai hasil pengukuran) |
| Gagal total | pil "0 lokasi" tetap tercetak | hanya kartu galat + "Coba lagi", tanpa angka |
| Kosong | dua kalimat untuk satu keadaan | satu kalimat di kartu "Keadaan jaringan"; kartu tabel tidak dirender |
| Cakupan 1 lokasi | tanpa penanda | satu baris kaki "Akun ini hanya mencakup satu lokasi." |
| Kelengkapan | "catatan > 24 jam" | "1 catatan lebih dari 24 jam" |
| Kaki "Rencana alih" | dua kalimat termasuk rumus biaya | satu kalimat ("Hanya surplus ≥ 150 kg per lokasi."); rumus biaya jadi `title` judul kolom "Biaya" |
| Judul limbah | "Limbah · 30 hari" | "Limbah · 30 hari terakhir" |

Gerbang otomatis baru — `frontend/tests/location-network-langkah3.test.tsx` (14 tes): satu baris
filter + satu pil tanggal, tidak ada paragraf > 120 karakter, keadaan memuat/kosong/gagal,
kegagalan sebagian, catatan kaki cakupan, alasan rencana kosong, jumlah catatan basi, kaki
rencana alih, judul limbah — plus dua tes layar sempit (kepala kolom Wilayah dan petunjuk geser)
yang ditambahkan setelah pengukuran di §"Lebar 390 px".

Bukti browser (dev :3010, 1247 px):

- **BGN Monitor** — kartu `Keadaan jaringan`, `Lokasi`, `Jakarta · telur`, `Rencana alih`,
  `Limbah · 30 hari terakhir`; pil `Data per 29 Okt 2026` + `10 lokasi`; 1 baris filter;
  kolom `Lokasi · Wilayah · Selisih · Batch ≤7h · Rekomendasi`; 10 baris; 0 paragraf
  > 120 karakter; `scrollWidth == clientWidth` (1247).
- **SPPG Head** — 1 baris, pil `1 lokasi`, catatan kaki "Akun ini hanya mencakup satu lokasi.".
- **Nutritionist** — judul "Pasokan & Kebutuhan", kalimat "Pasokan, kebutuhan, selisih,
  perkiraan, dan batch satu lokasi.", 1 baris + catatan kaki cakupan.

### Lebar 390 px — diukur, bukan disimpulkan dari CSS

Alat: `_qa/ukur-viewport.cjs` (CDP + Edge headless; memakai `ws` yang sudah ada di
`frontend/node_modules`, tanpa dependensi baru). Skrip masuk lewat akun demo, memaksa viewport
390×844 (`Emulation.setDeviceMetricsOverride`), membuka tab, lalu mengukur DOM.

| Yang diukur | 1247 px | 390 px |
|---|---|---|
| `documentElement.scrollWidth / clientWidth` | 1247/1247 | 390/390 — halaman TIDAK bergulir ke samping |
| Kepala tabel | Lokasi · Wilayah · Selisih · Batch ≤7h · Rekomendasi | Lokasi · Selisih · Batch ≤7h · Rekomendasi |
| Sel baris pertama | ▾Jakarta · DKI Jakarta · kurang 780 kg · 1 · 15 | ▾Jakarta · kurang 780 kg · 1 · 15 |
| Wadah tabel (`scrollWidth/clientWidth`) | 917/917 (muat) | 389/316 (geser di dalam kartu) |
| Petunjuk geser (`data-tampil`) | tiga-tiganya `false` | tabel lokasi `true`, tabel batch `true`, rencana alih `false` |
| Paragraf > 120 karakter | 0 | 0 |
| Tinggi halaman (BGN) | — (tidak diukur pada putaran ini) | 2.308 px → 2.332 px setelah petunjuk geser muncul |

Dua cacat DITEMUKAN dari pengukuran ini (bukan dugaan) dan diperbaiki:

1. Media query `≤640 px` hanya menyembunyikan `<td class=region>`, bukan `<th>`-nya. Di 390 px
   judul "WILAYAH" tetap tercetak sementara selnya hilang, sehingga SELURUH angka bergeser satu
   kolom: "kurang 780 kg" duduk di bawah judul "Wilayah". Kini `<th>` memakai kelas yang sama
   dan hilang bersama selnya (dijaga tes).
2. Tabel batch di kartu rincian terpotong di tengah ("26 hari 22 ja…") tanpa petunjuk karena
   wadahnya bergulir sendiri. `ScrollHint` kini menerima `kelasWadah`, jadi panel memakai
   pengukur yang sama; petunjuk hanya tampil bila wadah benar-benar meluap.

Sisa yang jujur: tabel lokasi MEMANG masih perlu digeser di dalam kartunya pada 390 px
(389 px isi vs 316 px wadah — turun dari 450 px sebelum kepala "Wilayah" ikut disembunyikan);
itu dinyatakan lewat petunjuk geser, bukan disembunyikan. Keadaan memuat/galat tidak dipaksa
muncul di browser — keduanya dibuktikan lewat render statis di tes.

Gerbang: `tsc` 0 · `next lint` 0 · vitest **217 berkas / 2.528 tes lulus** · `npm run build`
`BUILD_ID YZRmCQjqXtfsWB-9rnFUA` (4 halaman statis). Tangkapan layar lokal:
`_qa/location-network-390-29okt.png` dan `_qa/location-network-sppg-390-29okt.png`.
