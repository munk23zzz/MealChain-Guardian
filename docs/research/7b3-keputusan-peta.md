# Keputusan 7b-3 — riset & rekomendasi terapan pada MealChain Guardian

Status: **riset saja, belum ada yang diubah.** 17 Oktober 2026, ~11.10 WIB.
Lanjutan dari `docs/research/peta-ui-industri.md` (§6 daftar celah, §8 hasil 7b-1, §9 hasil 7b-2).
Sasarannya lima keputusan yang tersisa; untuk tiap keputusan di bawah: pertanyaan → bukti → pilihan →
**rekomendasi** → usaha → risiko → cara mengukur.

## 0. Ringkasan

| # | Pertanyaan | Rekomendasi | Usaha | Risiko |
|---|---|---|---|---|
| K1 | Kapan garis peta padat, kapan putus-putus? | **Padat = sudah/se­dang ditempuh; putus-putus = sisa perjalanan & perkiraan.** Satu arti saja di seluruh peta, sama dengan legenda. | 1 aturan style + 2 tes | garis terlihat "lebih berat" di peta terang |
| K2 | Peta perlu dilebarkan jadi kolom utama? | **Tidak.** Peta sudah 752 px vs kolom kanan 376 px (2,0×, 66,7% dari area). Jangan diubah. | 0 | — |
| K3 | Perlu daftar teks penanda di samping peta? | **Ya, tapi bukan tabel:** satu baris penanda ringkas di bawah kanvas + daftar khusus pembaca layar dari data yang sama. | 1 komponen + 2 tes | bisa disalahpahami sebagai "Rincian Pasokan per Lokasi" yang sudah dihapus |
| K4 | Popup jalur dipangkas? | **Jangan dipangkas lagi.** Isinya sudah 5 baris fakta. Cukup gabung 2 baris jam jadi 1. | 1 baris kode + 1 tes | — |
| K5 | Perlu seed kiriman "di jalan"? | **Ya — ini yang paling berdampak.** Tanpa kiriman berjalan, fitur "sisa perjalanan", tag "perkiraan", dan halaman Keputusan tidak bisa diperagakan. | seed backend + 1 tes | jam seed harus relatif, bukan tanggal mati |

Urutan kalau nanti dikerjakan: **K5 → K1 → K3 → K4**; K2 tidak dikerjakan.

## 1. Keadaan yang saya ukur hari ini (bukan ingatan)

Diukur pada app hidup (http://localhost:3010, peran SPPG Head, tab Overview) pukul ~11.05–11.15 WIB:

- **Pembagian kolom**: `.overview-split` = 1140 px; `grid-template-columns: 752px 376px`, `gap: 12px`.
  Kartu peta 752×554 (kanvas 752×460); kolom kanan 376×554 berisi **"Perlu keputusan" 4 butir**.
  Peta = 66,7% area split = **2,0× lebar kolom keputusan**; terhadap halaman 1440 px, kanvas = 52,2%.
- **Isi peta pada tampilan awal**: 1 pin lokasi (Jakarta) dengan aria-label
  "Jakarta — pasokan 314,2 kg, permintaan 1.080 kg, kurang 765,8 kg", + 1 garis jalur kiriman.
  **Lapisan pemasok MATI secara bawaan** (`useState(false)`), pin pemasok baru muncul pada zoom ≥ 6
  dan namanya pada zoom ≥ 8 — jadi 7 pemasok yang dihitung pil "Pemasok (7)" tidak tampak di layar.
- **Daftar teks lokasi di Overview DIMATIKAN** (`showStatusList={false}`); komponennya masih ada
  dan dipakai di tempat lain.
- **Pemilih kiriman** hanya berisi 2 pil: `Semua (1)` dan `Supplier A Cianjur → Jakarta · Sudah tiba 19.24`
  → **tidak ada satu pun kiriman yang sedang berjalan.**
- **Popup jalur** (dibuka dengan klik sungguhan pada garis): kotak 240×176 px, 165 huruf, 5 baris —
  judul, "Jalur jalan (OSRM): 110,4 km · ± 84 menit", "Berangkat: 8 Okt 2026 18.00 WIB",
  "Estimasi tiba: ± 19.24 WIB", "Layak dipakai s/d 7 Nov 2026".
- **Garis jalur digambar putus-putus** dan warnanya terbaca RGB(90,131,89) setelah bercampur peta
  (token `--status-safe` = #2E7D32).

Catatan kejujuran: sesi kerja lain sedang menulis ulang `app/page.tsx` (02:06) dan `SupplyMap.tsx` (07:17).
Angka di atas adalah keadaan pagi ini; kalau halaman berubah lagi, ukur ulang sebelum memutuskan.

## 2. K1 — Arti garis: padat vs putus-putus

**Pertanyaan.** Semua jalur kiriman sekarang digambar putus-putus. Apakah itu benar?

**Bukti.**
- Konvensi kartografi: garis untuk hal yang "tidak benar-benar ada" atau tidak selalu ada digambar
  putus-putus — penulisnya memakai garis putus-putus untuk batas wilayah dan sungai musiman.[1]
- Konvensi di domain lain justru **terbalik**: pada gambar rencana jalan, "Existing – Dashed Line /
  Proposed – Solid Line" (kutipan cuplikan pencarian; PDF-nya tidak bisa diambil mesin ini).[2]
  Artinya tidak ada satu aturan universal — yang wajib adalah **artinya dinyatakan di legenda dan
  dipakai konsisten**.
- Di aplikasi ini artinya sekarang **tidak konsisten**: legenda ringkas menulis "Jalur kiriman (jalan)"
  dengan contoh garis **putus-putus**, legenda sorotan menulis "Sisa perjalanan" = putus-putus,
  padahal layer dasar menggambar **semua** kiriman putus-putus — termasuk kiriman yang sudah tiba
  ("Sudah tiba 19.24"). Satu pola garis dipakai untuk dua arti yang berlawanan.
- Akibat yang terukur, bukan dugaan: dari **8 klik tepat di piksel garis, hanya 1 yang membuka popup.**
  Garis 3 px dengan pola putus-putus = separuh panjangnya bukan sasaran klik.

**Pilihan.**
(a) Biarkan semua putus-putus à legenda harus diganti jadi "Jalur kiriman (perkiraan)" — padahal
kiriman itu nyata dan sudah tiba.
(b) **Padat untuk bagian yang sudah ditempuh, putus-putus untuk sisa/perkiraan.**
(c) Hanya garis sorotan yang membedakan (keadaan sekarang) — kontradiktif.

**Rekomendasi: (b).** Satu arti di seluruh peta dan di legenda: padat = sudah/se­dang ditempuh,
putus-putus = belum ditempuh atau perkiraan. Ini juga membuat sasaran klik menerus, jadi popup lebih
mudah dibuka (7 dari 8 kegagalan klik di atas hilang dengan sendirinya).

**Usaha.** 1 perubahan aturan style layer dasar + menyesuaikan 2 tes yang membaca pola garis.
**Risiko.** Garis padat terasa lebih "berat" di peta terang → jaga lebar & opasitas seperti sekarang,
hanya pola garis yang berubah.
**Cara mengukur.** Ulangi uji klik 8 titik pada garis; target: 8/8 membuka popup. Potret 1440 & 375.

## 3. K2 — Apakah peta perlu jadi kolom utama?

**Pertanyaan.** Peta perlu dilebarkan (mis. 60–70% halaman) supaya terasa "peta dulu"?

**Bukti.**
- Peta **sudah** kolom utama: 752 px vs 376 px kolom keputusan = 2,0× (66,7% area split) — terukur di atas.
- Dokumentasi komponen peta dashboard: peta "memainkan peran sentral di banyak dashboard dan sering
  menjadi cara paling efektif menampilkan informasi geografis", tetapi juga "sebuah dashboard bisa berisi
  beberapa elemen peta, atau tidak sama sekali"[3] — yaitu ukuran peta mengikuti isi, bukan sebaliknya.

**Rekomendasi: tidak melebarkan.** Yang lebih berguna daripada menambah lebar:
(1) pastikan di 1280 px peta tidak menyusut di bawah ~620 px (ukur breakpoint),
(2) tambah tinggi kanvas hanya kalau ada isi baru (mis. daftar penanda pada K3),
(3) kalau demo butuh tampilan besar, jadikan itu **mode presentasi** terpisah — bukan layout bawaan.

**Usaha.** 0 untuk keputusan ini. **Risiko.** —.
**Cara mengukur.** Kalau nanti disentuh: lebar kanvas pada 1280/1440/1920 dan jumlah pin yang bertumpuk.

## 4. K3 — Padanan teks untuk isi peta

**Pertanyaan.** Perlu daftar teks penanda di samping peta (padanan untuk pembaca layar dan untuk
orang yang tidak bisa membaca peta)?

**Bukti.**
- Panduan aksesibilitas untuk gambar kompleks: deskripsi panjang sebaiknya "tersedia untuk semua orang"
  dan "ditampilkan sebagai bagian dari isi utama", bukan disembunyikan.[4]
- Keadaan sekarang: pin lokasi punya aria-label lengkap (lihat §1) tetapi penanda peta umumnya tidak
  masuk urutan Tab; **daftar teks lokasi dimatikan di Overview**; daftar pemasok tidak ada di halaman ini;
  nama kiriman hanya muncul di pil pemilih dan popup.
- Sudah ada preseden di aplikasi: baris legenda ringkas di bawah kanvas (7b-2) membuktikan pola
  "satu baris teks di bawah kanvas" diterima dan tidak menutupi peta.

**Pilihan.**
(a) Menghidupkan lagi daftar `Status Lokasi` — **bertabrakan** dengan perintah Anda "hapus Rincian
Pasokan per Lokasi", karena bentuknya tabel pasokan/kebutuhan/selisih.
(b) **Daftar penanda ringkas** di bawah kanvas: satu baris per penanda (nama · status · selisih),
tanpa kolom pasokan & kebutuhan — ini mengembalikan keterbacaan tanpa menghidupkan tabel yang dihapus.
(c) Hanya daftar khusus pembaca layar (tidak terlihat) + penanda bisa difokus.

**Rekomendasi: (b) + (c) sekaligus.** (b) memberi teks yang terlihat (berguna juga untuk juri yang
melihat dari jauh), (c) menutup celah aksesibilitas tanpa biaya tata letak. Keduanya dibangun dari
data yang sama dengan pin, jadi tidak mungkin berbeda isi.

**Usaha.** 1 komponen kecil + 2 tes (isi daftar = isi pin; daftar tetap ada saat lapisan berubah).
**Risiko.** Bisa disalahpahami sebagai kebangkitan tabel yang dihapus → beri judul "Penanda peta",
bukan "Status Lokasi", dan jangan tampilkan kolom pasokan/kebutuhan.
**Cara mengukur.** Jumlah baris = jumlah penanda; tinggi baris ≤ 2 baris teks @375; luapan 0 px.

## 5. K4 — Popup jalur: dipangkas atau tidak?

**Pertanyaan.** Popup jalur perlu dipangkas jadi lebih ringkas?

**Bukti.**
- Isi popup terukur: **5 baris, 165 huruf, kotak 240×176 px** — semuanya fakta yang dipakai untuk
  memutuskan (jalur & durasi, jam berangkat, estimasi tiba, masa layak). "Jarak lurus" dan "rasio jalan"
  sudah dibuang lebih dulu atas permintaan Anda.
- Panduan progressive disclosure: yang penting adalah "pembagian yang tepat antara tampilan awal dan
  tampilan sekunder", dan desain dengan lebih dari 2 tingkat biasanya justru sulit dipakai.[5]
- Perbedaan tooltip vs popover: tooltip = deskripsi pendek non-interaktif; popover = isi yang dibuka
  dengan klik.[6] Popup ini popover yang dibuka dengan klik → wajar memuat beberapa baris.

**Rekomendasi: jangan dipangkas lagi.** Cukup dua perbaikan kecil:
(i) gabungkan dua baris jam menjadi satu — "Berangkat 18.00 → tiba ± 19.24 WIB (8 Okt 2026)";
(ii) pastikan popup bisa ditutup dengan Escape (kalau belum) dan tetap terhubung ke tombol pemilih kiriman.
Menghapus baris "masa layak" akan menghilangkan satu-satunya alasan operasional di popup itu.

**Usaha.** 1 baris di `routePopupLines` + 1 tes. **Risiko.** —.
**Cara mengukur.** Jumlah baris popup 5 → 4; tinggi kotak turun ~20 px; isi tetap lengkap saat dicocokkan
dengan kartu kiriman.

## 6. K5 — Seed kiriman "di jalan" (paling berdampak)

**Pertanyaan.** Perlu menambah data demo kiriman yang sedang berjalan?

**Bukti terukur.** Pemilih kiriman hanya punya satu kiriman dan statusnya **"Sudah tiba 19.24"**.
Konsekuensinya:
- bagian garis yang belum ditempuh (putus-putus "sisa perjalanan") **tidak pernah bisa dilihat**;
- tag "perkiraan" pada ETA tidak pernah muncul;
- kartu kiriman (Arah A) dan papan kiriman (Arah B) hanya punya satu keadaan, jadi tidak ada yang bisa
  dibandingkan di depan juri;
- halaman "Perlu keputusan" punya 4 butir, tetapi tidak ada kiriman berjalan yang bisa dijadikan contoh
  alur keputusan dari peta → keputusan → bukti.

**Rekomendasi.** Tambah **2 kiriman seed di backend** (bukan mock di frontend, supaya data yang tampil
tetap berasal dari server):
1. satu **"di jalan"** dengan progres ~40% dan ETA hari ini — memperlihatkan garis padat + putus-putus
   sekaligus, dan tag "perkiraan" pada sisa waktu;
2. satu **"terlambat"** atau **"batal"** — memperlihatkan warna gagal, mutu kiriman gagal, dan keadaan
   kartu kiriman yang tidak "hijau semua".

**Usaha.** Seed backend + 1 tes (kiriman "di jalan" menghasilkan dua potong garis: padat & putus-putus).
**Risiko.** Jam seed harus relatif terhadap "hari ini", bukan tanggal mati — mekanisme "Segarkan ke hari
ini" sudah ada dan harus dipakai; kalau tidak, demo besok akan menampilkan kiriman yang "berangkat kemarin
tapi belum tiba".
**Cara mengukur.** Pemilih kiriman ≥ 3 pil dengan 3 keadaan berbeda; garis berpotong dua pada kiriman
"di jalan"; papan kiriman menampilkan minimal satu baris non-hijau.

## 7. Yang sengaja TIDAK saya ambil dari aplikasi peta lain

Ini bagian "mana yang terbaik **untuk MealChain Guardian**" — kemampuan yang umum ada di Google Maps/
Mapbox/dashboard GIS tetapi tidak cocok di sini:

| Kemampuan | Kenapa tidak diambil |
|---|---|
| Kotak pencarian lokasi (geocoder) | Cakupan data satu kota + radius 150 km; mencari tidak lebih cepat daripada menekan pin. |
| Ganti basemap | Menambah satu kontrol permanen, tidak menambah satu keputusan pun. |
| Alat ukur jarak manual | OSRM sudah memberi jarak & durasi resmi; alat ukur akan memunculkan angka kedua yang membingungkan. |
| Clustering penanda | 7 pemasok tidak perlu dikelompokkan; cluster justru menyembunyikan nama. |
| Peta layar penuh / mode presentasi | Berguna untuk panggung, tetapi harus jadi mode terpisah, bukan perilaku bawaan. |
| Legenda mengapung di atas kanvas | Sudah dipindah ke baris di bawah kanvas pada 7b-2 — jangan dikembalikan. |

## 8. Yang saya sarankan dikerjakan lebih dulu (kalau Anda setuju)

1. **K5** — dampak demo terbesar, risiko rendah, tidak menyentuh tata letak.
2. **K1** — satu aturan garis; sekaligus memperbaiki kontradiksi legenda dan keberhasilan klik popup.
3. **K3** — daftar penanda ringkas + padanan pembaca layar (hati-hati jangan jadi tabel yang dihapus).
4. **K4** — satu baris popup; kosmetik, bisa kapan saja.
5. **K2** — tidak dikerjakan.

Kalau Anda memilih subset lain, urutannya boleh berubah — tetapi K5 dan K1 saling menguatkan:
tanpa kiriman "di jalan", arti garis padat/putus-putus tetap tidak bisa diperagakan.

## 9. Hasil K5 setelah dikerjakan (terukur 17 Okt 2026, 12.15 WIB)

K5 disetujui dan dikerjakan lebih dulu (bukan K1) karena paling berdampak dan tidak menyentuh tata letak.
Seed Jakarta kini memperagakan **tiga keadaan perjalanan** sekaligus, semuanya komoditas `telur` dari tiga
pemasok berbeda — kalau komoditasnya berbeda, pemilih kiriman (yang disaring komoditas) hanya menampilkan
satu, dan itulah yang membuat percobaan pertama saya gagal.

| Yang diukur | Sebelum | Sesudah |
|---|---|---|
| Pil pemilih kiriman | `Semua (1)`, satu kiriman "Sudah tiba 19.24" | `Semua (3)` + Di jalan · Belum berangkat · Sudah tiba |
| Persentase jalur pada kartu | tidak pernah ada (semua kiriman sudah tiba) | `27% jalur`, `Tiba ± 13.18 WIB`, `110,4 km jalan`, `± 1 jam 24 menit` |
| `POST /demo/refresh` | **500** (`ForeignKeyViolationError` pada `menu_plans`) | **200** |

Dua cacat yang baru terlihat setelah dicoba di aplikasi hidup (bukan dari membaca kode):

1. `POST /demo/refresh` 500 — upsert `menu_plans` mengganti PK baris demo yang masih dirujuk
   `delivery_events`. Perbaikan: baris demo "diadopsi" (id dipertahankan), anak diarahkan ke id aktual.
2. Peta tidak ikut menyegar setelah refresh — `onDataChanged` hanya me-refetch keputusan. Perbaikan: ikut
   me-refetch data peta & jalur kiriman.

Pelajaran: dua dari tiga masalah di sini hanya muncul saat tombolnya benar-benar diklik. Membaca komponen
sudah memberi keyakinan yang salah.

## Sources

[1] https://www.esri.com/arcgis-blog/products/arcgis-pro/mapping/cartographic-conventions — Esri — Cartographic conventions (Heather Smith, 17 Jan 2024)
[2] http://prltap.org/eng/wp-content/uploads/2018/09/R.Sturgill-USTPE-Highway-Plans-101-FINAL.pdf — Highway Plans 101 (R. Sturgill, USTPE)
[3] https://doc.arcgis.com/en/dashboards/latest/get-started/map-element-and-tools.htm — ArcGIS Dashboards — Map element and tools
[4] https://www.w3.org/WAI/tutorials/images/complex — W3C WAI — Complex Images
[5] https://www.nngroup.com/articles/progressive-disclosure — NN/g — Progressive Disclosure (Nielsen, 2006)
[6] https://uxpatternsguide.com/compare/hover-card-vs-tooltip-vs-popover-vs-disclosure-details — UX Patterns Guide — Hover card vs Tooltip vs Popover vs Disclosure
