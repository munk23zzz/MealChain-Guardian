# Rencana desain halaman "Location Network" / "Pasokan & Kebutuhan"

Status: **Langkah 1–3 selesai** (29 Okt 2026; build terakhir Langkah 3 `YZRmCQjqXtfsWB-9rnFUA`).
Rencana ini tidak menyisakan langkah lain; yang tersisa hanya keputusan pemilik di §12.
Ruang lingkup: satu tab konsol (`location-network`), semua peran. Repo:
`E:\hackathon\HackathonAWS\mealchain-guardian` (frontend Next.js + backend FastAPI).
Dokumen acuan isi: `D:\Downloads\03-location-network-supply-demand.md` §3, §6.3, §6.5.

---

## 1. Tugas halaman ini, dalam satu kalimat

> Lokasi mana yang kurang, mana yang lebih, apa yang dialihkan, dan apa yang terbuang —
> dalam satu layar, tanpa penjelasan panjang.

Peran yang memakainya:

| Peran | Cakupan data | Yang paling ia butuhkan |
|---|---|---|
| `bgn_monitor` | semua lokasi SPPG | urutan lokasi terparah + rencana alih lintas wilayah |
| `sppg_head` | lokasi sendiri | selisih lokasi ini, batch mana yang harus segera dipakai, keputusan yang menunggu |
| `sppg_nutritionist` | lokasi sendiri | sama, dengan judul "Pasokan & Kebutuhan" |

Keputusan pemilik 29 Okt 2026 yang mengikat rencana ini: **Surplus & Limbah dilebur ke
halaman ini** ("siapa kekurangan, siapa berlebih, apa yang dialihkan, apa yang terbuang"
adalah satu pertanyaan). Karena itu rencana ini mencakup isi `SurplusBoard`, bukan hanya
tabel lokasi.

## 2. Keadaan sekarang (terukur, bukan dugaan)

Diukur di browser pada build `5HQf9LYaawBv5pstd_qPk`, 29 Okt 2026 02.5x WIB, komoditas `telur`:

| Peran | Kartu yang dirender | Baris filter komoditas | Paragraf > 120 karakter | Tinggi halaman |
|---|---|---|---|---|
| `bgn_monitor` (10 lokasi) | 3 — "Keadaan jaringan", "Lokasi", "Jakarta · telur" | 1 | 0 | 1352 px |
| `sppg_head` (Kepala Bandung) | 6 — tiga di atas + "Neraca hari ini", "Pencatatan limbah", "Rencana alokasi surplus" | 2 | 2 | 1664 px |

Temuan yang mengikutinya:

1. **Blok surplus/limbah/alokasi hanya untuk peran SPPG.** `SURPLUS_ROLES = {sppg_head,
   sppg_nutritionist}` (`app/page.tsx:205`). Akibatnya `bgn_monitor` — peran yang justru
   melihat 10 lokasi dan paling butuh rencana alih lintas wilayah — **tidak melihat rencana
   alih maupun limbah sama sekali**, padahal `GET /surplus/allocations` boleh dibaca semua
   peran terautentikasi (kontrak di `app/api/surplus.py`). Ini celah isi, bukan selera.
2. **Dua kepala di satu tab untuk peran SPPG.** Filter komoditas muncul dua kali (terukur
   `2`), dan keadaan jaringan dinyatakan dua kali dalam dua bentuk berbeda ("Keadaan
   jaringan" dengan kalimat, lalu "Neraca hari ini" dengan panah + tiga baris hitungan).
3. **Judul "Neraca hari ini"** padahal tanggal catatan bisa lebih tua dari hari ini
   (halaman ini sudah menulis "Data per 29 Okt 2026" di kepala).
4. **Paragraf penjelas panjang**: `SurplusBoard.tsx:181` (asal angka & cakupan peran) dan
   `:205` (ambang 150 kg), terukur 2 paragraf > 120 karakter.
5. Untuk `bgn_monitor` halaman sudah "rapi" tetapi **tidak lengkap**: kalimat ringkasan,
   tabel, rincian — tanpa "apa yang dialihkan" dan "apa yang terbuang".

## 3. Templat konsol yang wajib diikuti

Diambil dari tab yang sudah ada (`FoodSafetyBoard`, `AgentQualityBoard`, `Overview`).
Halaman ini **tidak** boleh punya sistem visual sendiri (sudah pernah terjadi: CSS modul
244 baris berisi grid/radius/warna sendiri).

| Lapis | Primitif | Catatan |
|---|---|---|
| Halaman | `section.board-page` | pembungkus setiap tab |
| Kepala | `PageHeader` + `page-header-pills` | judul, 1 kalimat, pil tanggal, pil jumlah |
| Filter | `commodity-filters.filter-card` + `commodity-pill` | **satu** baris untuk seluruh halaman |
| Bagian | `article.card` + `div.board-card-head` + `h2` | satu kartu satu pertanyaan |
| Tabel | `board-table-wrap` + `table.location-table` | angka rata kanan, `th scope="col"` |
| Keterangan | `p.evidence-note` | maksimal 1 baris, tanpa kata proses |
| Rincian | `article.card` di bawah tabel | bukan `<td>`, bukan popup |
| Tombol | `button`, `button-secondary`, `button-quiet` | target ≥ 32 px |
| Angka | `formatKg`/`formatBalanceGap` dari `lib/overview-format` | "—" untuk tak terbaca, 0 tanpa "kg" |

## 4. Peta data yang sudah ada (tidak ada endpoint baru yang dibutuhkan)

| Bagian halaman | Endpoint (sudah dipakai) | Field yang dipakai | Kesegaran |
|---|---|---|---|
| Neraca jaringan | `GET /balance/map` | `supply_kg`, `demand_kg`, `shortage_kg`, `surplus_kg`, `status`, `region`, `supply_state`, `demand_state`, `supply_recorded_at`, `demand_recorded_at`, `as_of` | per catatan |
| Tabel lokasi | `GET /balance/map` (baris yang sama) | idem + `region` | idem |
| Rincian satu lokasi | `GET /supply/{loc}/{com}`, `GET /demand/{loc}/{com}`, `GET /demand/forecast`, `GET /batches` | `quantity_kg`, `recorded_at`, `quantity_kg`+`needed_by`, `forecast_kg`/`method`/`confidence`, batch: `id`, `quantity_kg`, `safety_status`, `quarantine_status`, `usable_until` | per catatan |
| Rencana alih | `GET /surplus/allocations?commodity=…` | `from`, `to`, `kg`, `distance_km`, biaya tetap, `available`, `reason`, `min_surplus_kg` | dihitung server per permintaan |
| Limbah | `GET /waste/summary?days=30` | `recorded_kg`, `diverted_kg`, `unassigned_kg`, `window` | jendela 30 hari |
| Rekomendasi per lokasi | `GET /decisions` (sudah dimuat halaman) | `target_location_name`, `status` | daftar live |
| Batch hampir kedaluwarsa | `GET /batches` (sudah dimuat halaman) | `location`, `usable_until`, `safety_status`, `quarantine_status` | idem |

Semua angka yang direncanakan di bawah **berasal dari endpoint di atas**. Tidak ada angka
yang dihitung ulang di klien kecuali dua kolom tambahan di §6 (keduanya penjumlahan
sederhana dari data yang sudah dimuat, dan dihitung di modul murni yang diuji).

## 5. Susunan halaman final (5 blok, satu kolom)

```
┌ PageHeader ────────────────────────────────────────────────┐
│ Location Network                          [Data per 28 Okt]│
│ Siapa kurang, siapa lebih, apa yang dialihkan.  [10 lokasi] │
│ Komoditas: (telur) ayam beras wortel                        │
└─────────────────────────────────────────────────────────────┘
┌ 1. Neraca jaringan ────────────────────────────────────────┐
│ 8 lokasi kekurangan 968 kg; kelebihan 1.177 kg menutup      │
│ seluruhnya dan menyisakan 209 kg.                           │
│ [ 1.177 kg surplus ] ──────▶ [ 968 kg kekurangan ]          │
└─────────────────────────────────────────────────────────────┘
┌ 2. Lokasi ─────────────────────────────────────────────────┐
│ Lokasi     Wilayah        Selisih    Batch ≤7h  Rekomendasi │
│ Jakarta    DKI Jakarta    kurang 780       2         3       │
│ ... klik baris → rincian di kartu 3                          │
└─────────────────────────────────────────────────────────────┘
┌ 3. Jakarta · telur (muncul hanya saat baris dibuka) ───────┐
│ [Pasokan 300 kg][Kebutuhan 1.080 kg][Selisih 780][7 hari]   │
│ Batch: 3 batch · 2 lolos · 1 ditahan                        │
└─────────────────────────────────────────────────────────────┘
┌ 4. Rencana alih ───────────────────────────────────────────┐
│ Dari        Tujuan      Jumlah   Jarak    Biaya tetap       │
│ Bogor       Jakarta     400 kg   62 km    Rp …              │
│ (1 baris kaki: "Hanya surplus ≥ 150 kg per lokasi.")        │
└─────────────────────────────────────────────────────────────┘
┌ 5. Limbah · 30 hari terakhir ───────────────────────────────┐
│ Tercatat 0 kg · Dialihkan — · Tanpa mitra —                 │
└─────────────────────────────────────────────────────────────┘
```

Isi tiap blok:

1. **Neraca jaringan** — satu kalimat (`networkHeadline` yang sudah ada) + diagram aliran
   surplus → kekurangan (komponen `balance-flow` yang sudah dipakai `SurplusBoard`) + dua
   angka besar saja. Kalimat dan diagram **tidak mengulang angka yang sama dua kali**:
   kalimat menyebut jumlah lokasi dan sisa; diagram menyebut dua total.
2. **Lokasi** — tabel 5 kolom, urut terparah dulu (`sortBySeverity`). Kolom "Selisih"
   memakai `formatBalanceGap` (sudah menulis "kurang 780 kg"). Baris aktif ditandai ▸/▾ dan
   `aria-pressed`, rinciannya kartu di bawah tabel.
3. **Rincian lokasi** — 4 kartu (pasokan, kebutuhan, selisih, perkiraan 7 hari) + tabel
   batch seperti sekarang; hanya dirender saat ada baris aktif, dengan tombol "Tutup".
4. **Rencana alih** — tabel `Dari · Tujuan · Jumlah · Jarak · Biaya tetap`, urut dari
   selisih terbesar. Tujuan yang sedang dibuka di blok 2 ditandai (satu baris latar), supaya
   pembaca melihat "kekurangan Jakarta ditutup oleh Bogor" tanpa pindah kartu.
5. **Limbah** — tiga angka (`tercatat`, `dialihkan`, `tanpa mitra`) dengan jendela di judul.
   Bila server bilang belum ada data: "belum dicatat" — bukan 0 kg.

## 6. Yang DITAMBAHKAN (hanya dua, dan keduanya dari data yang sudah ada)

Keduanya menjawab "lalu apa?" pada baris yang sudah ada — bukan bagian baru.

**6.1 Kolom "Batch ≤7h"** — jumlah batch lokasi itu yang masa layaknya ≤ 7 hari dan tidak
ditahan. Sumber: `GET /batches` yang sudah dimuat halaman (`usable_until`, `safety_status`,
`quarantine_status`, `location`). Alasan penting: tabel sekarang menyebut "kurang 780 kg"
tanpa memberi tahu bahwa di lokasi yang sama ada stok yang akan kedaluwarsa minggu ini —
justru itu yang membuat rencana alih harus jalan cepat. Tampil `—` kalau batch lokasi itu
tidak terbaca, `0` hanya bila memang tidak ada.

**6.2 Kolom "Rekomendasi"** — jumlah keputusan terbuka (`proposed`, `pending_approval`,
`approved`, `verifier_flagged`, `review_only`) untuk lokasi itu. Sumber: `GET /decisions`
yang sudah dimuat untuk Jejak kepercayaan (`target_location_name`, `status`). Alasan penting:
halaman ini menjawab "siapa kurang"; pembaca perlu tahu apakah kekurangan itu **sudah** punya
usulan atau belum — dan bisa langsung pindah ke tab Recommendations. Angka 0 ditulis "—"
bila daftar keputusan belum termuat (agar tidak terbaca "tidak ada usulan").

Tidak ada tambahan lain. Yang sengaja **tidak** ditambahkan, dengan alasan:

| Tidak ditambahkan | Alasan |
|---|---|
| Peta & garis koridor | diputuskan pemilik 28 Okt 2026: halaman tanpa peta |
| Popup / dialog | rincian di kartu; popup pernah menutupi tabel batch |
| Grafik tren stok | sudah ada di Overview ("Pasokan per Lokasi") |
| Harga pasar per lokasi | ada di Overview "Harga pasar"; di sini hanya menambah kolom tanpa aksi |
| Rute pemasok (garis jalan) | dipakai halaman Pemasok & Keamanan Pangan |
| Perkiraan per wilayah / forecast agregat | server hanya menyediakan per lokasi×komoditas |
| Ekspor CSV / cetak | tidak diminta; menambah kontrol di kepala halaman |

## 7. Yang DIHAPUS (beserta alasannya)

| Dihapus | Alasan |
|---|---|
| Kartu "Neraca hari ini" (`SurplusBoard.tsx:120`) | mengulang angka kalimat ringkasan; judulnya juga keliru ("hari ini") |
| Tiga baris FactList "Lokasi surplus/kekurangan/seimbang" | hitungannya sudah tertulis di kalimat ringkasan |
| Filter komoditas di `SurplusBoard` | filter kedua untuk keadaan yang sama |
| Paragraf `:181` (cakupan & asal angka) | 3 baris teks proses; cakupan peran cukup ditulis sekali di kepala |
| Paragraf `:205` (ambang 150 kg) | jadi satu baris kaki tabel rencana |
| Teks "Bagian ini sengaja kosong: …" (`:196`) | diganti "belum dicatat" di nilai angka |
| Judul "Pencatatan limbah" sebagai kartu sendiri | digabung jadi blok 5 dengan 3 angka |

## 8. Aturan copy (mengikat)

1. **Satu kalimat per bagian.** Tidak ada paragraf penjelas di dalam kartu.
2. Tidak ada kata proses: "dihitung server", "mengikuti cakupan peta", "sengaja kosong".
3. Istilah tetap: **kurang / lebih / selisih**, bukan campur "shortage/surplus/kekurangan".
4. Angka: `formatKg` (ribuan titik, desimal koma, maks 2 desimal); jumlah 0 dicetak tanpa
   "kg"; data tak terbaca `—` **dengan** alasan singkat di kaki kartu bila perlu.
5. Label kolom pendek: ≤ 12 karakter ("Batch ≤7h", "Rekomendasi", "Biaya tetap").
6. Tanggal data ditulis sekali di kepala ("Data per 28 Okt 2026"), bukan di setiap kartu.

## 9. Keadaan khusus

| Keadaan | Perilaku |
|---|---|
| Memuat | skeleton 3 baris di tabel, kalimat kepala berbunyi "Memuat saldo lokasi…", tanpa kesimpulan |
| Kosong | "Belum ada lokasi untuk komoditas ini." (bukan "tidak ada kekurangan") |
| Gagal sebagian | kartu tetap tampil, catatan 1 baris di kaki kartu yang gagal ("Rencana alih tidak bisa dimuat") |
| Gagal total | satu kartu galat + "Coba lagi", tanpa angka apa pun |
| Cakupan 1 lokasi | pil kepala "1 lokasi" + catatan kaki di tabel, tanpa paragraf |
| Rencana kosong | alasan dari server (`reason`) diterjemahkan 1 baris; bila null → "Belum ada pasangan surplus → kekurangan." |

## 10. Kriteria selesai (terukur, bukan opini)

1. Halaman hanya punya **satu** filter komoditas dan **satu** pil tanggal.
2. Setiap angka jaringan muncul **sekali**: `1.177` (surplus), `968` (kekurangan), `209`
   (sisa) tidak boleh muncul dua kali di DOM. Diperiksa dengan render statis + hitungan regex.
3. Tidak ada elemen teks > 120 karakter di dalam kartu (paragraf) — diperiksa dengan tes.
4. `document.documentElement.scrollWidth === clientWidth` pada 1247 px dan 390 px.
5. Semua baris tabel dapat dibuka dengan keyboard; `aria-pressed` benar; rincian tidak
   pernah dirender dua kali.
6. `tsc` 0 · `next lint` 0 · vitest hijau · `npm run build` sukses (catat BUILD_ID).
7. Diukur di browser untuk dua peran (`bgn_monitor`, `sppg_head`) + nutritionist (judul).

## 11. Tahapan kerja (satu langkah per putaran, berhenti untuk persetujuan)

**Langkah 1 — satukan kerangka.** `LocationNetworkBoard` menjadi tuan rumah halaman:
kepala + filter tunggal + blok 1 (neraca) + blok 2 (tabel 5 kolom, dua kolom baru) + blok 3
(rincian). `SurplusBoard` dipecah: bagian neraca/limbah/rencana dipindah ke komponen anak
(`AllocationTable`, `WasteFacts`) dan dipasang sebagai blok 4–5 di dalam tuan rumah; kartu
"Neraca hari ini" + filter + tiga FactList dihapus. `page.tsx` berhenti merender
`SurplusBoard` utuh.

**Langkah 2 — tambahkan dua kolom** (§6) di `lib/location-network` sebagai fungsi murni
(`batchHampirKedaluwarsa`, `rekomendasiTerbuka`) + tes unit, lalu kolomnya.

**Langkah 3 — copy & keadaan.** Hapus paragraf, terapkan aturan §8, keadaan §9, lalu
gerbang §10 + tangkapan layar tiga peran.

Risiko kolaborasi: `app/page.tsx` dan `SurplusBoard.tsx` sedang disunting sesi lain
(terlihat dari hunk `merged-surplus` yang masuk 29 Okt). Langkah 1 harus dimulai dengan
membaca ulang kedua berkas itu, bukan dari ingatan dokumen ini.

---

## 12. Yang perlu keputusan pemilik sebelum Langkah 1

1. **Rencana alih & limbah untuk `bgn_monitor`.** Sekarang blok itu hanya dirender untuk
   `sppg_head`/`sppg_nutritionist`. Rencana ini mengusulkan blok 4–5 tampil untuk **semua
   peran**, karena server mengizinkannya dan justru peran nasional yang membutuhkan
   pasangan lintas wilayah. Kalau pemilik ingin tetap per-peran, sebutkan alasannya —
   rencana tidak akan mengubah gerbang peran itu.
2. **Kolom "Rekomendasi"** memakai daftar `GET /decisions` yang sudah dimuat halaman. Untuk
   `bgn_monitor` daftar itu berisi seluruh keputusan (31 terbuka pada snapshot ini); angka
   per lokasi dihitung dari `target_location_name`. Bila pemilik menilai angka ini terlalu
   ramai di tabel, alternatifnya: hanya tampilkan bila > 0.
3. **Nama menu.** **DIPUTUSKAN pemilik, 29 Okt 2026: tetap "Location Network".**
   Sidebar tidak diganti, judul halaman untuk peran non-nutritionist tetap mengikuti nama
   menu, dan yang menjelaskan isi baru adalah deskripsi halaman ("Siapa kekurangan, siapa
   kelebihan, apa yang dialihkan, dan apa yang terbuang"). Alasan: satu label yang stabil
   di sidebar lebih berharga daripada label yang lebih tepat tetapi membuat demo dan
   tangkapan layar juri berbeda antar-putaran. Peran nutritionist tetap melihat judul
   "Pasokan & Kebutuhan" — tidak diubah oleh keputusan ini.

---

## 13. Catatan pelaksanaan — Langkah 1 (29 Okt 2026)

Yang sudah ada di kode:

1. `LocationNetworkBoard` menjadi tuan rumah halaman: satu `PageHeader`, satu baris
   `commodity-filters`, lalu blok 1 (Keadaan jaringan), 2 (Lokasi), 3 (Rincian), 4 (Rencana
   alih), 5 (Limbah).
2. `components/AllocationTable.tsx` (baru) membaca `GET /surplus/allocations` — tidak pernah
   memasangkan lokasi sendiri. Kolomnya `Dari · Tujuan · Jumlah · Jarak · Biaya`, kaki satu
   baris menyebut ambang server. Baris yang tujuannya sedang dibuka ditandai `data-open`.
3. `SurplusBoard` tidak lagi dirender utuh dari `app/page.tsx` (kartu "Neraca hari ini",
   filter kedua, tiga FactList, dua paragraf > 120 karakter ikut hilang). Berkasnya masih
   ada untuk tes komponennya, bukan untuk halaman.
4. **Celah data yang ikut tertutup:** `useWasteSummary` dan `useSurplusPlan` dulu hanya
   hidup untuk `tab === "surplus"` — tab yang sudah tidak ada. Artinya blok surplus/limbah
   yang dilebur selalu kosong. Keduanya sekarang juga hidup untuk `tab === "location-network"`.
5. Rencana alih & limbah kini tampil untuk **semua peran** (keputusan pemilik), bukan hanya
   `sppg_head`/`sppg_nutritionist`.

Deviasi dari §5 (disengaja): **panah aliran surplus→kekurangan tidak dipakai.** Angka yang
sama sudah ada di kalimat ringkasan, jadi panah itu akan menjadi pengulangan visual yang
persis dikeluhkan pemilik. Blok 1 tetap satu kalimat + kelengkapan data bila ada isu.

Bukti terukur (BGN Monitor, 10 lokasi, komoditas telur, 1247 px): kartu = `Keadaan jaringan`,
`Lokasi`, `Jakarta · telur`, `Rencana alih`, `Limbah · 30 hari`; baris filter = 1; tabel
rencana = 1 baris (`Cianjur → Jakarta · 685 kg · 76 km · 0,8%`); limbah = `469,7 kg` tercatat
(64 peristiwa, 457,2 kg tanpa mitra), `12,5 kg` dialihkan (1 peristiwa); tinggi halaman
1742 px. Gerbang: `tsc` 0 · `next lint` 0 · vitest **213 berkas / 2.489 tes** · build
`ritoIHqRhgMCfG_oksSgY`.

## 14. Catatan pelaksanaan — Langkah 2 (29 Okt 2026)

Dua kolom tambahan di tabel lokasi, keduanya dari data yang sudah dimuat halaman:

| Kolom | Fungsi murni (`lib/location-network.ts`) | Aturan |
|---|---|---|
| Batch ≤7h | `hampirKedaluwarsa(batches, now, hari=7)` | hanya batch `safety_status=pass` dan **tidak** ditahan; tanggal tak terbaca tidak dihitung; batch yang sudah lewat masa layak tetap dihitung (paling mendesak) |
| Rekomendasi | `rekomendasiTerbuka(decisions)` | status `proposed`, `pending_approval`, `approved`, `verifier_flagged`, `review_only`; dikelompokkan per `target_location_name`; baris tanpa nama dilewati |

Kolom hanya **dipasang bila ada minimal satu baris bernilai > 0** (keputusan pemilik
29 Okt 2026: "bila di atas 0 saja"). Sel tanpa nilai menulis `—`, bukan `0`.

Bukti di browser (BGN Monitor, telur, 1247 px): kepala tabel `Lokasi · Wilayah · Selisih ·
Batch ≤7h · Rekomendasi`; Jakarta `kurang 780 kg · 1 · 16`; Bandung `kurang 138 kg · 4 · 10`;
Surabaya `kurang 12 kg · 4 · 7`; Semarang `kurang 8 kg · 3 · —`; `scrollWidth == clientWidth`.

Tes: 9 tes modul murni (ditahan/gagal/tanggal rusak/lewat waktu/spasi nama) + 4 tes kolom
(muncul saat ada isi, tidak muncul saat kosong, batch ditahan tidak memunculkannya, `—` untuk
baris tanpa nilai). Gerbang: `tsc` 0 · lint 0 · vitest **214 berkas / 2.502 tes** · build
`ubpvBA7URr_Dy82BlkAZE`.

## 15. Catatan pelaksanaan — Langkah 3 (29 Okt 2026)

Copy & keadaan dikerjakan sesuai §8 dan §9. Yang berubah:

| Butir | Sebelum | Sesudah |
|---|---|---|
| Kalimat kepala (§8.1, §8.3) | "Siapa kekurangan, siapa berlebih, dan isi catatan tiap lokasi." | "Siapa kekurangan, siapa kelebihan, apa yang dialihkan, dan apa yang terbuang." — satu kalimat, istilah sama dengan kartu ringkasan ("kelebihan"), tanpa isi yang tidak ada di halaman |
| Sumber kalimat | ditulis dua kali (`app/page.tsx` dan bawaan komponen), sempat berbeda | satu sumber: peran non-nutritionist memakai bawaan komponen, `page.tsx` hanya mengirim kalimat nutritionist |
| `title` menu | "…dan dari mana catatannya" | sama dengan kalimat kepala (provenance tidak lagi ditampilkan) |
| Memuat (§9) | `<p>Memuat…</p>` + pil "0 lokasi" | kepala tabel tetap, **tiga baris kerangka** (`skeleton skeleton-line`), pil jumlah disembunyikan |
| Gagal total (§9) | pil "0 lokasi" tetap tercetak | tidak ada angka sama sekali; hanya kartu galat + "Coba lagi" |
| Kosong (§9) | dua kalimat untuk satu keadaan ("Keadaan jaringan" + "Belum ada lokasi untuk komoditas ini.") | satu kalimat; kartu tabel tidak dirender |
| Cakupan 1 lokasi (§9) | tidak ada penanda | satu baris kaki "Akun ini hanya mencakup satu lokasi." |
| Catatan basi (§8.4) | "catatan > 24 jam" (tanpa jumlah) | "1 catatan lebih dari 24 jam" |
| Kaki rencana alih (§8.1) | dua kalimat, termasuk rumus biaya | "Hanya surplus ≥ 150 kg per lokasi."; rumus biaya pindah ke `title` judul kolom |
| Judul limbah (§5) | "Limbah · 30 hari" | "Limbah · 30 hari terakhir" |

Gerbang §10 yang kini diuji otomatis (`tests/location-network-langkah3.test.tsx`, 14 tes):
satu baris filter + satu pil tanggal, tidak ada `<p>` > 120 karakter, keadaan memuat/kosong/gagal,
catatan kaki cakupan, kaki rencana alih, judul limbah, kepala kolom Wilayah ikut tersembunyi,
petunjuk geser ada di tabel.

Di browser (dev :3010, 1247 px): BGN Monitor — 1 baris filter, pil `Data per 29 Okt 2026` +
`10 lokasi`, 5 kolom tabel, 0 paragraf > 120 karakter, `scrollWidth == clientWidth`;
SPPG Head & Nutritionist — 1 baris + catatan kaki cakupan, judul nutritionist "Pasokan &
Kebutuhan".

**§10.4 (390 px) diukur, bukan disimpulkan** — alat `_qa/ukur-viewport.cjs` (CDP + Edge
headless, memakai `ws` yang sudah ada di `frontend/node_modules`). Hasil: halaman tidak
bergulir ke samping (390/390), kepala tabel menjadi `Lokasi · Selisih · Batch ≤7h ·
Rekomendasi` (Wilayah hilang bersama selnya), sel sejajar, 0 paragraf > 120 karakter, tabel
lokasi masih perlu digeser di dalam kartunya (389 px isi vs 316 px wadah) dan kini memberi
petunjuk geser. Dua cacat ditemukan dari pengukuran itu dan diperbaiki: (a) `<th>` "Wilayah"
dulu tidak ikut disembunyikan sehingga SELURUH angka bergeser satu kolom; (b) tabel batch di
kartu rincian terpotong di tengah kata tanpa petunjuk — `ScrollHint` kini menerima
`kelasWadah` sehingga panel memakai pengukur yang sama.

Gerbang: `tsc` 0 · `next lint` 0 · vitest **217 berkas / 2.528 tes** · build
`YZRmCQjqXtfsWB-9rnFUA`.

**Sisa:** §12 (nama menu, angka kolom Rekomendasi) tetap keputusan pemilik. Keadaan
memuat/galat dibuktikan lewat render statis, tidak difoto di browser.
