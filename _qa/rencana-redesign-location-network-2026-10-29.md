# Rencana redesain halaman "Location Network" — tahapan L0–L7

Tanggal: 29 Okt 2026 · Lingkup: satu tab konsol (`location-network`), semua peran.
Repo: `E:\hackathon\HackathonAWS\mealchain-guardian` (frontend Next.js 14 + backend FastAPI).
Rencana isi yang sudah selesai: `docs/plans/location-network-page-plan.md` (Langkah 1–3, build
`YZRmCQjqXtfsWB-9rnFUA`). **Dokumen ini tidak mengulang pekerjaan itu** — ia merapikan bentuk.

## 1. Tugas halaman ini, satu kalimat

> Lokasi mana yang kurang, mana yang lebih, apa yang dialihkan, dan apa yang terbuang — dalam
> satu layar, tanpa penjelasan panjang.

## 2. Keadaan sekarang (dari kode dan rencana isi, bukan dugaan)

Susunan yang dirender `LocationNetworkBoard`, semua peran:

| # | Bagian | Komponen | Isi sekarang |
|---|---|---|---|
| 0 | Kepala | `PageShell` | judul · 1 kalimat deskripsi · pil tanggal catatan · pil `N lokasi` |
| 0b | Filter | `commodity-filters` | satu baris pil komoditas (`telur · ayam · beras · wortel`) |
| 1 | Keadaan jaringan | `LocationNetworkBoard` | satu kalimat `networkHeadline` + daftar isu kelengkapan (0–2 butir) |
| 2 | Lokasi | tabel `location-table` | `Lokasi · Wilayah · Selisih · [Batch ≤7h] · [Rekomendasi]`; dua kolom terakhir **kondisional**; baris bisa diklik |
| 3 | Rincian lokasi | `SupplyDemandPanel` | 4 kartu angka (Pasokan · Kebutuhan · Selisih · Perkiraan 7 hari) + daftar batch 4 kolom; hanya saat baris dibuka |
| 4 | Rencana alih | `AllocationTable` | tabel `Dari · Tujuan · Jumlah · Jarak · Biaya` + kaki satu baris ambang |
| 5 | Limbah | `FactList` | 3 baris fakta (tercatat · dialihkan · tanpa mitra) |

Navigasi bagian: 4 tujuan (`Keadaan jaringan · Lokasi · Rencana alih · Limbah`), batas
design.md §24 = 5.

Yang **sudah** baik dan tidak akan diubah: satu filter, satu pil tanggal, angka jaringan
muncul sekali (gerbang §10.2 rencana lama), tidak ada paragraf > 120 karakter, keadaan
memuat/kosong/gagal sudah dibedakan (`tests/location-network-langkah3.test.tsx`, 14 tes).

Cacat bentuk yang tersisa — semuanya terukur atau terbaca dari kode:

1. **Ponsel masih menggeser tabel.** Di 390 px tabel lokasi 389 px di dalam wadah 316 px;
   yang ada baru `ScrollHint` (dokumentasi Langkah 3). Aturan layout skill: tabel lebar →
   kartu atau geser, dan geser hanya boleh jadi pilihan terakhir.
2. **Empat kartu bertumpuk tanpa penanda tingkat.** Semua `article.card` sama tinggi
   visualnya: "Keadaan jaringan" (1 kalimat) terlihat sepenting tabel 10 baris.
3. **Rincian lokasi muncul sebagai kartu ke-3 di antara tabel dan rencana alih** — saat
   dibuka, halaman melompat 400+ px dan konteks baris yang diklik hilang dari layar.
4. **Bahasa teknis masih bocor di satu tempat:** `SupplyDemandPanel.tsx:207`
   "…dibatasi {N} baris terbaru **dari server**".
5. **Limbah memakai `FactList`** sementara bagian lain memakai tabel/kartu angka — satu
   halaman, dua bahasa penyajian untuk tiga angka sederhana.
6. **Tanda baris memakai karakter `▸/▾`** di dalam tombol; `aria-pressed` ada, tetapi
   `aria-expanded`/`aria-controls` belum berpasangan benar untuk pembaca layar.
7. **Target sentuh belum seragam:** pil komoditas dan tombol baris belum tentu 44 px di
   perangkat sentuh (halaman Pemasok sudah dipatok 44 px di S6).

## 3. Aturan yang mengikat (dari skill + repo)

- Peta & garis koridor **tidak** ditambahkan (keputusan pemilik 28 Okt 2026).
- Angka jaringan tetap muncul **sekali**; dua kolom kondisional tetap kondisional.
- Lantai teks 12 px (`--fs-1`), radius/ukuran dari token, `border-radius` mentah dilarang
  (`tests/design-tokens-kontrak.test.ts`, `tests/radius-scale-css.test.ts`).
- Warna status tidak boleh sendirian: teks + bentuk (`Color Only` di panduan UX: "use
  icons/text in addition to color").
- Kultur token: aksen biru sudah dilepas 29 Okt 2026 (`--accent-strong` = `--ink`).
- Pencarian katalog skill, apa adanya:
  - `"dense table scanning rows"` → 1 hasil relevan: *Table Handling — use horizontal
    scroll or card layout, don't let wide tables break layout*. Dipakai di L3.
  - `"row expansion detail disclosure"` → **0 hasil** (`expandable row detail panel` juga 0).
    Tidak ada rujukan katalog untuk pola buka-baris; L4 memakai aturan umum prioritas 9
    (navigasi dapat diprediksi) dan kebiasaan repo (dossier satu entitas).
  - `"status badge not color alone"` → 3 hasil, dipakai di L3/L5.
  - `--design-system` mengembalikan pola *Real-Time / Operations Landing* (pola landing,
    tidak dipakai) + gaya *Minimalism & Swiss* (cocok untuk konsol) + palet biru `#2563EB`
    (**ditolak**: repo punya token sendiri dan aksen biru baru saja dihapus).

## 4. Tahapan

### L0 — Kunci kontrak teks (tanpa perubahan visual) — **SELESAI 29 Okt 2026**
- Tes baru `tests/location-network-teks-kontrak.test.tsx`: markup halaman (5 keadaan: normal,
  memuat, kosong, galat, satu lokasi) dilarang memuat `backend`, `server`, `database`,
  `payload`, `schema`, `endpoint`, `historical_seed`.
- Perbaiki satu pelanggaran nyata: `SupplyDemandPanel.tsx:207` → "Daftar batch dibatasi {N}
  baris terbaru; batch yang lebih lama tidak ikut di tabel ini."
- Berkas: `tests/location-network-teks-kontrak.test.tsx` (baru), `components/SupplyDemandPanel.tsx`.

**Hasil L0 (29 Okt 2026):** tes baru 7 butir; run pertama **merah 1** — `SupplyDemandPanel.tsx:207`
memang mencetak "…baris terbaru **dari server**" saat `batchesTruncated` benar. Diperbaiki menjadi
"Daftar batch dibatasi {N} baris terbaru; batch yang lebih lama tidak ikut di tabel ini."
Empat pelanggaran dugaan lain ternyata **komentar kode**, bukan teks tampil (`/surplus/allocations`,
"ambang yang dipakai server", "kebocoran backend") — tidak diubah, tetap sebagai jejak. Setelah
perbaikan: 7/7 hijau; berkas sekitar (langkah3, board, forecast-source) 48 hijau; suite penuh
**273 berkas / 2.948 lulus / 2 dilewati**; `tsc --noEmit` bersih.

### L1 — Kepala halaman & navigasi bagian — **SELESAI 29 Okt 2026**
- Pil jumlah diberi satuan yang benar (`10 lokasi` sudah; tambah nada "sebagian" bila ada
  isu kelengkapan — teks, bukan warna saja).
- Baris filter komoditas duduk **di dalam** blok kepala (satu pita, bukan dua), tanpa
  menambah baris filter kedua (gerbang §10.1 dijaga).
- Nav bagian: tetap 4; `Rincian lokasi` **tidak** dijadikan tujuan kelima — ia bagian dari
  baris yang sedang dibuka, dan target lompatan yang berubah-ubah membuat nav tak terduga.
- Berkas: `components/LocationNetworkBoard.tsx`, `lib/section-jump.ts` (bila label berubah),
  tes `tests/location-network-langkah3.test.tsx` disesuaikan, tes baru
  `tests/location-network-kepala.test.tsx`.

**Hasil L1 (29 Okt 2026).** Tiga perubahan, semuanya aditif terhadap halaman lain:

1. `PageHeader` + `PageShell` mendapat slot opsional `filters` yang dirender **di dalam**
   `<header class="page-header">` sebagai `.page-header-filters` (`flex-basis: 100%`). Halaman
   yang tidak mengirimnya tidak berubah — 273 berkas tes lain tetap hijau.
2. Filter komoditas Location Network pindah ke slot itu; blok lamanya di badan halaman dihapus.
   Jumlah baris filter tetap **satu** (`role="group" aria-label="Komoditas"` = 1), judul `h1` = 1.
3. Pil keadaan baru `catatan belum lengkap` (`data-state="sebagian"`) muncul hanya saat ada isu
   kelengkapan — **teks, bukan warna saja** — dan tidak membawa angka, karena rinciannya satu
   tempat di daftar isu kartu keadaan jaringan.

Diukur di pratinjau statis (`_qa/preview/location-network-kepala.html`, bingkai 390 & 1280):

| Ukuran | Sebelum | Sesudah |
|---|---|---|
| Pita filter (`Komoditas:` + 4 pil) di 375 px | 72 px, dua baris | **32 px, satu baris** |
| Tinggi kepala halaman di 375 px | 213 px | **173 px** |
| Meluap mendatar di 375 px | 0 | 0 |
| `filters` benar-benar di dalam `<header>` | tidak (pita terpisah) | **ya** (diperiksa `contains()`) |

Label "Komoditas:" tidak dihapus, hanya disembunyikan secara visual di ≤560 px — nama grupnya
tetap terbaca pembaca layar lewat `aria-label`. Tes: `tests/location-network-kepala.test.tsx`
(9 butir, 2 di antaranya membaca `globals.css`). Suite penuh **273 berkas / 2.956 lulus /
2 dilewati**; `tsc` bersih.

**Catatan untuk L6:** di 375 px kepala (173 px) + nav bagian (132 px, membungkus jadi dua baris
sejak perbaikan nav 29 Okt) menghabiskan 305 px layar sebelum kartu pertama. L6 perlu memangkas
label `BAGIAN` dan jarak baris nav di layar sempit.

### L2 — Neraca jaringan: satu kalimat, satu penanda — **SELESAI 29 Okt 2026**
- Kartu "Keadaan jaringan" jadi **kartu utama** halaman: kalimat lebih besar (`--fs-5`),
  penanda nada (teks seperti "jaringan kurang" + bentuk garis tepi), isu kelengkapan
  diringkas menjadi **satu baris** (`2 tanpa catatan · 1 catatan lebih dari 24 jam`).
- Tidak menambah angka baru: gerbang "satu angka satu tempat" tetap diuji.
- Berkas: `components/LocationNetworkBoard.tsx`, `LocationNetworkBoard.module.css`,
  `app/globals.css` (kelas `.network-lead`).

**Hasil L2 (29 Okt 2026).**

- Kartu keadaan jaringan sekarang `.network-lead`: garis tepi kiri 3 px bernada (danger / safe /
  netral), **tanpa** latar berwarna — nada dibaca dari kata, warna hanya penguat.
- Penanda nada baru `[data-testid="network-lead-state"]` menulis **kata**, bukan angka:
  `ada kekurangan` · `kebutuhan tertutup` · `tidak ada selisih` · `belum terbaca`. Saat memuat,
  penanda tidak dirender (halaman belum menyimpulkan apa pun).
- Isu kelengkapan: `<ul>` dua `<li>` → **satu** `<p>` dengan pemisah `·`; jejak audit tetap
  menempel sebagai `data-kind="missing"` / `"stale"`.
- Ukuran: kalimat neraca `--fs-5`, turun ke `--fs-4` di ≤640 px (bukan ke ukuran catatan).

Diukur di pratinjau (`_qa/preview/location-network-neraca.html`, bingkai 390 & 1280):

| Ukuran | 1280 px | 375 px |
|---|---|---|
| Kalimat neraca | **18 px** (`--fs-5`) | **17 px** (`--fs-4` di ≤640) |
| Judul kartu (`h2`) sebagai pembanding | 14 px | 15 px |
| Penanda nada | 13 px, merah nada | 14 px |
| Isu kelengkapan | satu baris (20 px) | dua baris terbungkus (42 px) |
| Garis tepi kartu | 3 px `--danger` | 3 px `--danger` |
| Meluap mendatar | 0 | 0 |

**Satu perubahan arsitektur kecil, dengan alasan terukur:** aturan `.headline` dan `.issues`
dipindah dari CSS modul ke `globals.css` sebagai `.network-lead-text` / `.network-lead-issues`.
Sebabnya bukan selera — kelas CSS modul diberi hash saat dibangun, sehingga pratinjau statis
(dan siapa pun yang membaca CSS tanpa `next build`) tidak melihat aturannya sama sekali; ukuran
"18 px" di atas baru bisa diukur setelah aturan itu satu tempat dengan `.network-lead`.

Tes: `tests/location-network-neraca.test.tsx` (11 butir: kelas lead + nada teks untuk 4 nada,
larangan angka di penanda, keadaan memuat, isu satu paragraf + data-kind, ketiadaan isu saat
lengkap, `--fs-5`/`--fs-4`, gaya per nada, garis tepi, kelas modul tidak lagi ada).
Suite penuh **275 berkas / 2.975 lulus / 2 dilewati**; `tsc` bersih. Satu kegagalan sempat
muncul dari `tests/design-tokens-kontrak.test.ts` ("token hantu `--ok`") — fallback
`var(--ok, …)` diganti token nyata `--ok-ink` / `--line-strong`.

### L3 — Tabel lokasi: papan yang dipindai, bukan dinding — **SELESAI 29 Okt 2026**
- **≤760 px: kartu per lokasi** (`data-label`), pola yang sudah dipakai daftar pemasok, papan
  kiriman, dan riwayat penerimaan — ini yang menghapus geseran mendatar di ponsel.
- Tombol baris: `aria-expanded` + `aria-controls` berpasangan, penanda ▸/▾ tetap, tetapi
  status selisih ditulis teks + bentuk ("kurang 780 kg" + garis/nada), bukan warna saja.
- Kolom "Wilayah" disembunyikan di sempit (sudah) — pindah ke baris kedua kartu bersama
  penanda kelengkapan.
- Kaki tabel: cakupan satu lokasi (sudah) + petunjuk geser hanya bila benar-benar perlu.
- **Tidak** menambah sortir (repo: tabel urutan tetap; katalog hanya 1 hasil lemah).
- Berkas: `LocationNetworkBoard.tsx`, CSS, tes `tests/location-network-board.test.tsx`,
  `tests/location-network-langkah3.test.tsx`, tes baru `tests/location-network-kartu.test.tsx`.

**Hasil L3 (29 Okt 2026).**

- Kelas papan sendiri `.network-table` + `.network-table-wrap` (bukan `.location-table`, yang
  dipakai sebelas tabel lain).
- Setiap sel membawa `data-label` yang **sama dengan judul kolomnya** (`Lokasi · Wilayah ·
  Selisih · Batch ≤7h · Rekomendasi`); sel pertama tanpa label karena ia judul kartunya.
- Pola disclosure: `aria-expanded` (bukan `aria-pressed`) + `aria-controls="rincian-lokasi"`.
  Empat assertion lama di `location-network-board.test.tsx` disesuaikan; assertion pil komoditas
  (yang memang `aria-pressed`) tidak disentuh.
- Selisih ditandai bentuk + kata: `−` kurang · `+` lebih · `=` seimbang (`aria-hidden`, kata di
  sebelahnya sudah menyebut hal yang sama).

Diukur di pratinjau (`_qa/preview/location-network-kartu.html`, bingkai 390 / 760 / 1280):

| Ukuran | 390 px | 760 px | 1280 px |
|---|---|---|---|
| `thead` | `none` | `none` | `table-header-group` |
| Tabel | `block` (kartu) | `block` (kartu) | `table` |
| Tinggi baris pertama | 174 px | 150 px | 41 px |
| `overflow-x` wadah | `visible` | `visible` | `auto` |
| Geseran wadah (`scrollWidth − clientWidth`) | **0** | **0** | **0** |
| Meluap halaman | 0 | 0 | 0 |
| Label `::before` sel 2–5 | `"Wilayah"`, `"Selisih"`, `"Batch ≤7h"`, `"Rekomendasi"` | sama | (tidak dipakai) |
| Tinggi tombol baris | 44 px | **26 px** | **26 px** |

**Tiga cacat yang ketahuan saat mengukur (bukan saat menulis):**

1. `.network-table-wrap { overflow: visible }` kalah oleh `.board-table-wrap { overflow-x: auto }`
   yang didefinisikan lebih bawah di berkas — `overflow-x` terukur masih `auto`. Diperbaiki jadi
   selektor dua kelas, dan tesnya mengunci bentuk dua kelas itu.
2. `border-radius: var(--radius-card)` — token itu tidak ada; `tests/radius-scale-css.test.ts`
   menangkapnya. Diganti `var(--radius-control)`.
3. Helper `blokMedia()` di `tests/shipment-board-mobile-css.test.ts` (warisan S3) melompati dua blok
   `@media (max-width: 760px)` sekali jalan; begitu L3 menambah blok 760 px di atasnya, blok papan
   kiriman ikut terlewat dan berkas itu gagal **sebelum satu tes pun berjalan**. Helper diperbaiki
   (`dari = tutup + 1`) dan papan kiriman kembali hijau.

Tes: `tests/location-network-kartu.test.tsx` (9 butir). Suite penuh **279 berkas / 2.998 lulus /
2 dilewati**; satu kegagalan tersisa di `tests/evidence-tahap1-kepala.test.tsx` (nav Evidence saat
isi dibangun ulang) — `DecisionEvidence.tsx` dan `evidence-dossier.css` sedang disunting alur kerja
paralel, bukan berkas alur ini. `tsc` bersih.

### L4 — Rincian lokasi jadi dossier satu entitas — **SELESAI 29 Okt 2026**
- Rincian **pindah tepat di bawah barisnya** (dalam kartu tabel, sebagai baris penuh), bukan
  kartu ke-3 yang menggeser seluruh halaman; saat dibuka, konteks baris tetap terlihat.
- Empat angka memakai pola strip ringkasan S2 (`--fs-8` untuk angka utama, label bersatuan,
  read-only), konsisten dengan halaman Pemasok.
- Tabel batch: kartu berlabel `data-label` di ≤760 px; badge keamanan teks + bentuk.
- Kalimat "dari server" (L0) tidak kembali.
- Berkas: `LocationNetworkBoard.tsx`, `SupplyDemandPanel.tsx` (+ CSS modul), tes
  `tests/location-network-board.test.tsx`, `tests/supply-demand-*`.

**Hasil L4 (29 Okt 2026).**

- Rincian sekarang **baris penuh di dalam tabel** (`<tr class="network-detail-row" id="rincian-lokasi">`
  + `<td colSpan>`), duduk tepat setelah baris lokasi yang dibuka. Kartu rincian terpisah di bawah
  tabel dihapus. `colSpan` dihitung dari kolom yang benar-benar dipasang: 3 / 4 / 5.
- Kepala dossier: `h3` "`{lokasi} · {komoditas}`" + tombol tutup bundar yang sama dengan penutup lain.
- Angka: "Selisih" dipromosikan (`data-lead`) ke `--fs-5`; tiga angka lain tetap. Atribut dipakai
  (bukan kelas modul) supaya ukurannya bisa ditata dari `globals.css` dan diverifikasi pratinjau.
- Tabel batch di dalam dossier: sel membawa `data-label` (`Jumlah · Keamanan · Masa layak`) dan di
  ≤760 px ikut jadi kartu berlabel.

Diukur di pratinjau (`_qa/preview/location-network-dossier.html`, 390 + 1280 terbuka + 1280 tertutup):

| Ukuran | Hasil |
|---|---|
| Kolom tabel lokasi, 1280 px, scrollbar disamakan | **368 · 226 · 227 · 170 · 212** — identik terbuka vs tertutup |
| `colSpan` | 3 tanpa kolom kondisional · 4 dengan Batch ≤7h · 5 dengan keduanya |
| Dossier di 390 px | lebar 313 px, tinggi 725 px, tabel batch 289 px |
| `thead` tabel batch di 390 px | `none`; label `::before` = `"Jumlah"` dst. |
| Meluap mendatar | 0 di 390 px dan 1280 px |

**Satu alarm palsu, dicatat supaya tidak diulang:** pengukuran pertama menunjukkan kolom Lokasi
menyempit 373 → 368 px saat dossier dibuka, dan saya sempat menyimpulkan tabel batch menekan tabel
luar. Setelah `html { overflow-y: scroll }` dipasang di kedua bingkai, angkanya **identik**: selisih
itu scrollbar vertikal yang muncul di bingkai yang lebih tinggi, bukan efek tata letak.
`contain: inline-size` pada `.network-detail` tetap dipasang sebagai sabuk pengaman (isi batch
kelak tidak boleh menyumbang lebar), dengan komentar yang menyatakan itu — bukan sebagai perbaikan.

Tes: `tests/location-network-dossier.test.tsx` (14 butir: baris penuh + `colSpan` 3/4/5 + urutan
DOM + ketiadaan dossier saat tertutup + kepala `h3` + tombol tutup + `data-lead` + empat label angka
+ label sel batch + tiga kontrak CSS + dua penjaga lebar). Suite penuh **281 berkas / 3.019 lulus /
2 dilewati / 6 todo**; dua kegagalan tersisa milik alur **Recommendation Feed** yang sedang menulis
`app/page.tsx` (`TS2304: FEED_SCOPE_ACTION` di `app/page.tsx:2098`), bukan alur ini. `tsc` merah
karena berkas itu juga.

### L5 — Rencana alih & Limbah: satu keluarga bentuk — **SELESAI 30 Okt 2026**
- Kepala kedua kartu disamakan: judul + pil jumlah (`N pasangan`, `3 angka`) + satu kalimat
  keadaan; kaki satu baris (ambang 150 kg) tetap.
- Limbah: `FactList` → tiga angka sejajar (tercatat · dialihkan · tanpa mitra) dengan satuan
  dan jendela "30 hari terakhir"; "belum dicatat" tetap, bukan 0 kg.
- Rencana alih: kartu berlabel di ≤760 px; baris tujuan yang sedang dibuka ditandai teks
  ("sedang dibuka") bukan hanya latar.
- Berkas: `AllocationTable.tsx`, `LocationNetworkBoard.tsx`, `app/globals.css`,
  tes `tests/location-network-transfers.test.tsx`.

### L6 — Responsif, aksesibilitas, gerak — **SELESAI 30 Okt 2026**
- Target sentuh 44 px: pil komoditas, tombol baris, tombol tutup rincian, tombol "Coba lagi".
- Cincin fokus terlihat di semua kontrol; `prefers-reduced-motion` mematikan transisi baris.
- Ukur 360 / 760 / 1247 px: `scrollWidth === clientWidth` (gerbang §10.4 naik dari 390 ke 360),
  tidak ada teks < 12 px, tidak ada target < 44 px — diukur dari DOM hidup.
- Berkas: `app/globals.css`, `LocationNetworkBoard.module.css`, tes baru
  `tests/location-network-akses.test.ts`.

### L7 — Verifikasi penutup — **SELESAI 30 Okt 2026**
- `tsc` 0 · suite penuh hijau untuk lingkup ini · `next build` sukses (catat BUILD_ID).
- Pratinjau statis `_qa/preview/location-network.html` (360/760/1440 px) + laporan ukur
  `_qa/verifikasi-location-network-2026-10-29.md`.
- Berkas: dokumen + pratinjau; tidak ada perubahan kode selain perbaikan yang ditemukan
  pengukuran.

## 5. Gerbang selesai (terukur)

1. Satu filter, satu pil tanggal, 4 tujuan nav (≤5).
2. Setiap angka jaringan tetap muncul sekali (regex pada render statis).
3. Tidak ada paragraf > 120 karakter di dalam kartu.
4. `scrollWidth − clientWidth = 0` pada 360, 760, 1247 px — diukur, bukan disimpulkan.
5. Tidak ada target sentuh < 44 px dan tidak ada teks < 12 px pada 360 px.
6. `aria-expanded`/`aria-controls` benar; satu baris hanya punya satu tombol pembuka.
7. `tsc` 0 · vitest lingkup hijau · build sukses.

## 6. Risiko

- **Baris-detail di dalam tabel** (L4) menyentuh `location-table` bersama: tabel lain
  memakai kelas yang sama. Baris penuh harus memakai kolom `colSpan` yang dihitung, dan
  mode kartu harus tetap satu kartu per lokasi.
- `SupplyDemandPanel` dipakai juga di tab lain; perubahan angkanya harus lewat token, bukan
  gaya lokal.
- Sesi lain sedang menyunting tab Evidence/Today; berkas yang bertabrakan baru
  `components/*` milik Supplier — bukan halaman ini.
