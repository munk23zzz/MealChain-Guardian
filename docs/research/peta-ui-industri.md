# UI peta operasional — riset referensi industri & usul penyempurnaan (Langkah 7)

Status: **riset selesai (7a)**; **7b-1 dan 7b-2 dikerjakan & terverifikasi (17 Okt)** — hasil terukur di §8
dan §9. 7b-3 (butuh keputusan pemilik) belum dikerjakan.
Cakupan: kartu peta di tab Overview (MapLibre GL JS) — kontrol, legenda, cara mengelola lapisan, penyajian detail, dan aksesibilitas.
Metode: 6 pencarian web + 2 halaman dibaca langsung lewat browser (Axis Maps) + 3 kueri skill `ui-ux-pro-max`; 22 sumber terdaftar di ledger sitasi (`grounded-citations`), **14 kutipan verbatim** disimpan dengan pemeriksaan teks halaman.
Kejujuran sumber: kutipan bertanda *[excerpt backend]* berasal dari potongan teks halaman yang dikembalikan mesin pencari (bukan saya buka sendiri); dua sumber Axis Maps saya baca langsung di browser dan itu ditandai di ledger. Sumber [1] Esri gagal dibuka (403 Access Denied) — tidak dipakai untuk klaim apa pun.

---

## 1. Batasan yang perlu dibaca lebih dulu (hasil skill UI/UX)

Skill `ui-ux-pro-max` **tidak punya baris panduan bertema peta**. Diuji tiga kueri: `"map legend layer toggle"` → 0 hasil, `"map and detail panel side by side"` → 0 hasil, `"map overlaid controls on canvas"` → 2 hasil yang kebetulan cocok (Focus States, Auto-Rotating Content). Jadi: **panduan peta saya ambil dari sumber peta itu sendiri**, dan skill dipakai untuk aturan yang memang ada di katalognya:

- Prioritas 1 Accessibility: "Contrast 4.5:1, Alt text, Keyboard nav, Aria-labels" (anti-pola: "Icon-only buttons without labels").
- Prioritas 2 Touch & Interaction: "Min size 44×44px, 8px+ spacing" (anti-pola: "Reliance on hover only").
- Domain `chart`: "Use solid, dashed, and dotted line styles plus direct series labels; **never distinguish series by hue alone**."
- Domain `ux`: "Don't convey information by color alone … Use icons/text in addition to color" (severity High).
- `--stack nextjs`: "Reserve space for dynamic content" (anti-pola: "Content popping in", severity High) — berlaku untuk kanvas peta yang menunggu data.
- Kueri `--design-system` mengembalikan pola "Real-Time / Operations Landing" dengan satu butir yang langsung relevan: **"Label telemetry as live only when backed by a current source, with update time and stale state."** Ini sejalan dengan aturan jujur yang sudah kita pakai (kiriman "sudah tiba" tidak diberi sisa waktu).

---

## 2. Referensi yang saya pilih (dan kenapa itu)

| # | Sumber | Peran di keputusan |
|---|---|---|
| [21] [22] | Axis Maps — Cartography Guide: *Visual Hierarchy*, *Map interaction* | Prinsip inti: peta harus jadi fokus; tombol reset; tooltip ringkas vs panel tetap; penanda filter aktif; ponsel tanpa hover |
| [14] [15] | Map UI Patterns (*partial map*), ArcGIS Maps SDK (*application layouts*) | Tata letak peta + panel, kontrol mengambang, panel berukuran sesuai kepentingan |
| [16] | Admiralty Design System — *Find a location* | Pola peta+panel dua arah, target sentuh 44 px, kontras 4.5:1, daftar teks alternatif |
| [8] | Bathyl — *Designing Layer Toggles* | Aturan mengelola lapisan: checkbox additive, grup = satu unit, legenda selalu terlihat, metadata sumber/tanggal/keyakinan |
| [2] [4] | Google Maps — Controls (JS API), studi kasus modernisasi Google Maps | Taksonomi kontrol (Informational/Viewport/Visualization), kontrol harus elemen HTML asli |
| [13] [11] | NN/g — *Bottom Sheets*, liputan redesign Google Maps | Panel bawah nonmodal: detail tampil tanpa menutup peta |
| [17] [18] | ISOM 2000, USGS — *Topographic Map Symbols* | Konvensi garis: putus-putus = belum pasti / rencana / under construction |
| [5] [6] | W3C — *Accessibility in Digital Maps*, NSGIC/XR Navigation | Keyboard (SC 2.1.1), peta raster sulit diakses, daftar/tabel sebagai padanan |
| [19] [7] [9] | MapLibre ScaleControl, Mapbox *toggle layers*, mapbox-layer-control | Mekanika implementasi + legenda otomatis untuk layer garis/titik |

Ditolak/diabaikan: [1] Esri legend (403), [3] Navigation SDK & [10] layout customization (konteks navigasi berkendara, bukan dashboard), [12] (tutorial duplikat dari [7]), [20] (indeks dokumentasi, hanya cadangan).

---

## 3. Temuan per tema

### T1 — Peta harus jadi fokus, dan hierarki visual harus sengaja
> "Where your eye goes first when you look at the map is the element that has the highest level in the visual hierarchy—make sure that element is something important." [21]
> "If the map is the most important part of the story, it should be as large as possible." [21]
> "An easy, non-scientific way to evaluate visual hiearchy is a 'squint test.'" [21]

ArcGIS sependapat untuk aplikasi: "The map or scene should be be the focal point of the application as the primary content… Floating tools should be contextual and not block map interaction." [15] Ditambah mapuipatterns: "Build the app so that the map appears side by side with the content or work-flows." [14]

**Implikasi**: kartu peta kita 752 px dari 1440 px dan berbagi baris dengan kartu lain. Bukan salah, tapi kita belum pernah menguji "squint test" — dan peta bukan elemen yang paling menarik mata di halaman itu.

### T2 — Kontrol peta punya kategori, dan dua di antaranya belum kita punya
Studi kasus Google Maps membagi kontrol jadi tiga: "These controls fall into three categories: Informational, Viewport, and Visualization UI." [4] — Informational (kredit peta, **skala**), Viewport (tombol reset tampilan, indikator lokasi), Visualization (tombol lapisan). Kita punya Visualization (toggle lapisan) dan sebagian Informational (kredit), **tidak punya skala maupun tombol reset**.

> "it's easy to get lost, so it's generally a good idea to include some kind of reset button for reverting the map to its default extent." [22]
> "A ScaleControl control displays the ratio of a distance on the map to the corresponding distance on the ground." [19]

Juga dari [2], aturan yang kita patuhi sekarang dan harus tetap: "Always use native HTML elements for buttons… never repurpose a DIV as an interactive UI element." Pin di kanvas tidak bisa difokus keyboard — karena itu pemilih kiriman berbasis `<button>` adalah keputusan yang benar (dan sejalan dengan SC 2.1.1 [6]).

### T3 — Legenda: harus terlihat tanpa klik, satu kesatuan, dan menyebut asal data
> "Group layers by role, use radio (mutually exclusive) controls for basemaps and competing thematic layers, checkboxes for additive overlays, and pair each toggle with a legend and opacity control so users understand what they are seeing." [8]
> "…the active thematic legend is visible without extra clicks…" [8]
> "…and every layer exposes source, date, and confidence metadata." [8]

Tambahan: "Layers have legends added automatically if they are line, circle or fill with a single color." [9] — legenda kita (garis jalur + titik pemasok/lokasi) justru kasus termudah, tapi sekarang disembunyikan di balik tombol "Info map" setinggi 24 px.

### T4 — Mengelola lapisan: checkbox untuk yang menumpuk, grup = satu unit
> "A thematic layer that is really several MapLibre layers (fill + outline + labels) should toggle as a unit…" [8]
> "The interface uses setLayoutProperty to toggle the value for each layer's visibility property between visible and none." [7]

Kita sudah benar di dua hal: memakai `setLayoutProperty` (bukan add/remove) dan `aria-pressed` pada toggle. Yang belum: tidak ada penanda bahwa toggle "Pemasok (7)" dan "Jalur kiriman (1)" adalah dua lapisan additive yang boleh menyala bersama, dan tidak ada metadata sumber/umur data per lapisan.

### T5 — Detail: tooltip ringkas di peta, cerita panjang di panel
> "Floating tooltips appear next to the feature on the map… are best suited to relatively small amounts of information so that they don't grow huge and obscure everything. Fixed panels have dedicated space and are good for longer, more detailed information." [22]
> "A nonmodal bottom sheet shows details about a destination and navigation actions, while still allowing the user to pan and zoom around the map to see the context of the destination." [13]
> "Tapping for a fixed panel is going to be the best bet in most cases." [22] (ponsel tanpa hover)

Ini menjawab salah satu keputusan terbuka kita: **popup jalur boleh tetap ada**, asal isinya ringkas (nama pengirim, status, ETA) dan cerita panjangnya tetap di kartu kiriman. Yang jadi temuan adalah sebaliknya: popup kita sekarang berisi angka yang sama dengan kartu, jadi dua-duanya "panjang".

### T6 — Filter yang aktif harus kelihatan, dan legenda boleh sekaligus jadi kontrol
> "Combinations of active filters can get complicated, and moreover sometimes it's easy to become engrossed in a map and forget that you're looking at a restricted set of data, so it's good to include visual reminders." [22]
> "Filters don't always need to be built as separate menus and panels, but can be integrated with other parts of a well-designed UI. In the first example below, the choropleth legend is used for filtering data value categories." [22]
> "When a user selects a pin on the map, the panel should update. When they select a link or area of interest in the panel, the map should reflect that." [16]
> "Often, both sides are connected so that interactions on one side trigger the appropriate action or update on the other side, and vice versa." [14]

Arah C sudah memenuhi butir dua arah [16][14]. Yang belum: tidak ada pengingat visual di sekitar kanvas bahwa peta sedang menyaring satu kiriman (peringatan kita ada di catatan kartu, di bawah).

### T7 — Aksesibilitas peta: keyboard, daftar padanan, kontras, 44 px
> "All functionality of the content is operable through a keyboard interface without requiring specific timings for individual keystrokes…" [6]
> "Features can be presented through lists, tables, or menus." [6]
> "Ensure all actions available on the map (e.g. selecting a location) can also be done from the panel or sidebar" + "Ensure contrast between elements on the map meets a minimum contrast ratio of 4.5:1." + "Meet the minimum touch target size of 44x44px" [16]
> "Neither raster maps, nor maps that label extended features with a single point, fit this definition, and are extremely difficult to make accessible." [5]

**Temuan paling keras**: kontrol bawaan MapLibre yang kita pakai (zoom in/out, compass) berukuran **29×29 px**, dan toggle lapisan **26 px** tinggi, legenda/“Rincian lapisan” **24 px** — semuanya di bawah ambang 44 px [16] dan aturan skill (prioritas 2). Di 375 px, pil fokus kiriman sudah 44 px (kita pernah perbaiki), tapi kontrol peta tidak ikut.

### T8 — Konvensi garis: putus-putus berarti "belum pasti / belum jadi"
> "A road under construction may be shown with broken lines." [17]
> "Many features are shown by lines that may be straight, curved, solid, dashed, dotted, or in any combination." [18]

Artinya: memakai garis putus-putus untuk **semua** kiriman (termasuk yang sudah tiba) menyampaikan pesan yang salah — pembaca peta terlatih membacanya "rencana/belum pasti". Konvensi yang benar untuk kita: solid = ruas yang sudah ditempuh, putus-putus = sisa perjalanan/perkiraan. Ini juga menjawab keputusan terbuka #1.

---

## 4. Kondisi peta sekarang (terukur, bukan taksiran)

Dari `ui-audit/p0-inventaris.json` (Playwright, SPPG Head, Overview, seed default):

- 1440 px: kartu peta **752×528**, kanvas **750×458**; tinggi halaman 1896; luapan mendatar 0.
- 375 px: kartu **331×502**, kanvas **329×318**; luapan 0.
- **9 kontrol** di dalam kartu: zoom in, zoom out, compass (masing-masing **29×29**, `aria-label` Inggris bawaan MapLibre), toggle "Pemasok (7)" & "Jalur kiriman (1)" (**26 px**, `aria-pressed` benar), "Info map" (**24 px**, legenda terlipat), pil fokus "Semua (1)" + 1 kiriman (**22 px** @1440, **44 px** @375), "Rincian lapisan peta" (**24 px**).
- Teks kredit: **hanya** `© OpenStreetMap contributors` (diperiksa pada `.maplibregl-ctrl-attrib-inner`).
  Angka "−780 kg" yang ikut terbaca saat membacakan SELURUH kontainer peta adalah **label pin** Jakarta
  (`.map-pin-label`), bukan kredit peta — lihat koreksi C7 di §5. Skrip inventaris pertama saya membaca
  `innerText` kontainer, jadi angka itu tercampur; koreksinya diambil dari elemen attribution itu sendiri.
- Kelas lapisan yang ada: `map-overlay-toggles`, `map-legend-stack`/`-boxes`/`-line`, `map-layer-info`/`-tags`/`-panel`, `map-pin*`. Tidak ada `ScaleControl`, `fitBounds`, tombol reset, atau penanda filter aktif.

---

## 5. Celah → usul perubahan

| # | Celah (bukti) | Referensi | Usul | Biaya/risiko |
|---|---|---|---|---|
| C1 | Kontrol peta 29 px, toggle 26 px, widget lipat 24 px | [16], skill prio 2 | Naikkan ke ≥44 px (padding CSS pada `maplibregl-ctrl-*` + tombol sendiri); jaga ikon tetap 18–20 px | Rendah; hanya CSS. Perlu cek ulang agar 3 tombol kontrol tidak menutupi peta di 375 px |
| C2 | ~~Legenda tersembunyi di balik "Info map"~~ **SELESAI 7b-2** | [8] | Tampilkan **baris legenda ringkas** (garis jalur + titik pemasok + titik SPPG) langsung di bawah kanvas; "Info map" tetap ada untuk rincian | Rendah |
| C3 | Tidak ada skala jarak | [4], [19] | Tambah `ScaleControl` (metric) | Sangat rendah (satu baris MapLibre) |
| C4 | Tidak ada cara kembali ke tampilan awal | [22] | Tombol "Kembalikan tampilan" yang memanggil `fitBounds` ke semua titik | Rendah; butuh simpan bounds awal |
| C5 | ~~Tiga widget lipat terpisah (toggle, legenda, rincian lapisan)~~ **SELESAI 7b-2** | [15], [8] | Satukan jadi **satu zona kontrol kiri-atas**: chip "Info map" masuk pil yang sama dengan sakelar lapisan (kanvas = SATU elemen mengapung), isinya turun ke bawah kanvas | Sedang; menyentuh struktur DOM peta |
| C6 | Garis dasar semua kiriman putus-putus | [17], [18] | Ruas sudah ditempuh **solid**; sisa perjalanan/perkiraan **putus-putus** | Sedang; ini keputusan produk (lihat §6) |
| C7 | ~~"−780 kg" menempel di baris attribution~~ — **BATAL setelah diukur** | [4] | Tidak ada yang perlu diubah: attribution memang hanya berisi kredit peta. Temuan awal SALAH karena skrip inventaris membaca `innerText` seluruh kontainer peta (label pin ikut terbaca). Pelajaran: ukur elemen yang dimaksud, jangan kontainernya. | — |
| C8 | ~~Tidak ada penanda "peta sedang menyaring 1 kiriman" di sekitar kanvas~~ **SELESAI 7b-2** | [22] | Chip kecil di atas kanvas: "Menyaring: Supplier A Cianjur → Jakarta · Lepas" (tombol `<button>`) | Rendah |
| C9 | ~~Di ponsel, geser peta bentrok dengan gulir halaman~~ **SELESAI 7b-2** | [20] (MapLibre punya contoh *cooperative gestures*), [22] | Cooperative gestures untuk perangkat sentuh utama saja: sekali sentuh = gulir halaman, dua jari = geser peta | Rendah |
| C10 | Pin hanya bisa dipakai lewat kanvas | [16], [5], [6] | Daftar teks bernama di panel (nama pemasok/lokasi + jarak) yang menyalakan sorotan yang sama seperti pil kiriman | Sedang |
| C11 | Kontras teks di atas peta belum diaudit | [16], skill prio 1 | Audit kontras panel putih di atas peta (target ≥4.5:1) | Rendah |
| C12 | Peta 752 px dari 1440 px | [21], [15] | Pertimbangkan peta jadi kolom utama di Overview (kartu lain di bawah/sampingnya) | Tinggi; mengubah tata letak halaman — **keputusan user** |

---

## 6. Usul urutan pengerjaan (7b) dan hal yang butuh keputusan Anda

> **Keputusan 7b-3 (garis, lebar peta, daftar penanda, popup, seed) sudah diriset terpisah:**
> lihat `docs/research/7b3-keputusan-peta.md` — lima keputusan, bukti terukur, dan rekomendasi
> terapan untuk MealChain Guardian. Dokumen ini tetap menjadi daftar celah risetnya.

**7b-1 — SELESAI 17 Okt 2026** (bukti terukur di §8): C1 target sentuh 44 px, C3 skala jarak,
C4 tombol "Tampilkan semua", C11 audit kontras (terendah 4,55:1 — lulus). C7 dibatalkan karena
tidak ada masalahnya. Semua angka diambil dengan `ukur-7b1.py` sebelum/sesudah, bukan dari CSS.

**7b-2 — SELESAI 17 Okt 2026** (bukti terukur di §9): C2 legenda terlihat tanpa klik, C5 satu zona kontrol
"Info peta", C8 penanda filter aktif, C9 cooperative gestures untuk perangkat sentuh.

**7b-3 — menunggu keputusan Anda (jangan saya kerjakan sendiri)**
1. **C6 arti garis** — mengubah garis dasar jadi solid dan hanya sisa perjalanan yang putus-putus. Ini konvensi kartografi yang benar [17], tapi mengubah tampilan demo yang sudah Anda lihat. (Sekaligus menutup keputusan terbuka #1 dari laporan Arah C.)
2. **C12 lebar peta** — apakah peta naik jadi kolom utama di Overview.
3. **C10 daftar pin bernama** — apakah perlu daftar teks pemasok/lokasi di samping peta (padanan aksesibilitas), atau pil kiriman sudah cukup.
4. **Popup jalur** (keputusan terbuka #2): riset ini menyarankan popup **tetap ada tapi dipangkas** jadi ringkas [22][13] — bukan dihapus.
5. **Seed kiriman di jalan** (keputusan terbuka #3) tetap perlu agar putus-putus sisa perjalanan & tag "perkiraan" terlihat di demo.

---

## 7. Cara verifikasi yang akan dipakai di 7b
1. Ukur DOM (`getBoundingClientRect`) untuk setiap kontrol sebelum/sesudah — bukan menebak dari CSS.
2. Screenshot kartu peta utuh + elemen kontrol (seperti `p0-*` di `ui-audit/`), periksa dengan mata.
3. Logika baru (mis. hitung bounds, aturan sembunyikan/tampilkan) ditulis sebagai fungsi murni + tes unit lebih dulu.
4. Suite frontend penuh harus tetap 0 gagal; `tsc --noEmit` 0 error; `next lint` bersih.
5. Tidak ada build produksi (aturan repo — dev server hidup).

_Sumber lengkap dengan kutipan verbatim ada di blok Sources di bawah; ledger sitasi sesi ini menyimpan 22 sumber, 14 kutipan, 0 kutipan tanpa bukti teks._

## 8. Hasil 7b-1 — dikerjakan & terukur (17 Okt 2026)

**Yang berubah**

- `frontend/lib/map-view.ts` (**baru**, murni): `MAP_RESET_LABEL`, `MAP_RESET_ICON` (SVG inline, bukan emoji),
  dan `mapResetTitle(jumlahLokasi, adaJalur)` — judul tombol adalah **janji**, jadi dibuat fungsi murni + diuji.
- `frontend/components/SupplyMap.tsx`: kontrol skala `ScaleControl({ maxWidth: 88, unit: "metric" })` di
  kanan-bawah; kontrol buatan sendiri berupa **`<button>` asli** kelas `.map-reset-view` di grup kanan-atas
  (klik → `map.fitBounds(fitBoundsFor(lokasi, jalur))` — rumus yang SAMA dengan tampilan awal, bukan rumus kedua).
  Jalur ikut dikembalikan hanya kalau lapisannya sedang hidup.
- `frontend/app/globals.css`: gaya `.map-reset-view` + `.maplibregl-ctrl-scale`; di
  `@media (pointer: coarse), (max-width: 720px)`: grup MapLibre 29→44 px (ikon 20 px), tombol reset 44 px,
  `.map-layer-toggle` / `.map-legend-toggle` / `.map-layer-info-toggle` min-height 44 px.

**Angka sebelum → sesudah** (SPPG Head, tab Overview, seed default; diukur `ukur-7b1.py`, bukan dari CSS)

| Elemen | 1440 sebelum | 1440 sesudah | 375 sebelum | 375 sesudah |
|---|---|---|---|---|
| zoom / zoom out / kompas | 29×29 | 29×29 (desktop sengaja tetap ringkas) | 29×29 | **44×44** |
| toggle "Pemasok (7)" · "Jalur kiriman (1)" | 26 px | 26 px | 26 px | **44 px** |
| "Info map" · "Rincian lapisan peta" | 24 px | 24 px | 24 px | **44 px** |
| bilah skala jarak | tidak ada | **62×21 px · "30 km"** | tidak ada | **62×21 px · "30 km"** |
| tombol "Tampilkan semua" | tidak ada | **29×29 px** | tidak ada | **44×44 px** |
| luapan halaman | 0 px | 0 px | 0 px | 0 px |
| tumpang tindih antar kontrol | — | **tidak ada** | — | **tidak ada** |

Catatan penting soal komentar CSS: aturan `.map-layer-toggle` selama ini MENGAKU "target sentuh 44 px tetap
berlaku lewat aturan global", padahal tidak — `min-height` kelas menang atas `button { min-height: 44px }`,
sehingga chip itu tetap 26 px di 375 px. Klaim yang tidak benar di komentar sudah diganti dengan rujukan ke
blok media yang sekarang benar-benar menegakkannya.

**Audit kontras (C11)** — rasio dihitung dari warna hasil render, latar efektif ditelusuri ke leluhur pertama
yang punya latar: toggle lapisan 17,85 · label pin 17,85 · kredit peta 17,85 · pil fokus 7,89 ·
"Info map" 7,58 · "Rincian lapisan peta" 6,92 · tag bilah lapisan 4,55. **Terendah 4,55:1 → semuanya lulus 4,5:1**.
Label pin berada di atas ubin peta; angka itu berlaku untuk latarnya sendiri (putih 0,94 + garis tepi), bukan untuk
ubin di belakangnya — jadi tidak ada klaim kontras atas peta yang tidak bisa dibuktikan.

**Koreksi (C7)**: tidak ada perubahan. Attribution memang hanya berisi kredit peta; angka "−780 kg" yang membuat
saya menulis temuan itu adalah **label pin** yang ikut terbaca karena skrip inventaris membaca `innerText`
kontainer peta. Pelajaran metode: periksa elemen yang dimaksud, bukan kontainernya.

**Bug nyata yang hanya ketahuan karena diklik di browser (bukan dari tes unit).** Tombol
"Tampilkan semua" terlihat benar di tangkapan layar dan semua tes unit hijau, tetapi **tidak bisa diklik**:
sudut kontrol MapLibre (`.maplibregl-ctrl-top-right`) memakai `pointer-events: none` dan mewariskannya ke anak,
sedangkan kelas penyelamat `.maplibregl-ctrl { pointer-events: auto }` **tidak** diberikan MapLibre kepada
kontrol buatan sendiri. Bukti: `getComputedStyle(...).pointerEvents === "none"` dan Playwright menolak
mengklik dengan pesan "subtree intercepts pointer events". Perbaikan: satu baris `pointer-events: auto`
pada `.map-reset-view`, ditambah tes kontrak CSS (`tests/map-controls-css.test.ts`) yang menjaga baris itu
— karena kelas kesalahan ini tidak bisa ditangkap tes unit biasa. Pelajaran: kontrol baru wajib diuji
DENGAN KLIK di aplikasi hidup, bukan hanya diukur kotaknya.

**Bukti tombol bekerja (klik sungguhan di browser, `cek-reset-peta.py`).** Posisi layar pin diukur tiga kali:
awal `[614, 741]` → sesudah peta digeser + di-zoom `[201, 485]` → sesudah tombol diklik `[633, 731]`.
Selisih 29 px dari posisi awal bukan bug: peta otomatis membingkai ulang saat geometri jalur tiba dengan
margin 0,5° (agar kedua ujung kiriman terlihat), sedangkan tombol reset memakai rumus tampilan awal
(margin bawaan 1,6°) — dua-duanya "semua lokasi + jalur kiriman", hanya beda margin bingkai.
Tombol juga terbukti bisa difokus keyboard (`document.activeElement` = `map-reset-view`).

**Gerbang**: 16 tes baru — 6 murni (`tests/map-view.test.ts`) + 5 kontrak peta di `tests/supply-map-layer.test.tsx`
+ 5 kontrak CSS (`tests/map-controls-css.test.ts`)
(tiruan MapLibre diperluas: `ScaleControl`, pencatatan kontrol + pemanggilan `onAdd`, jejak `fitBounds`) —
semuanya hijau; `tsc` 0 error pada berkas pekerjaan ini; ESLint bersih.
Tangkapan bukti: `ui-audit/p1-peta-1440.png`, `ui-audit/p1-kanvas-1440.png`, `ui-audit/p1-kanvas-375.png`;
angka mentah: `ui-audit/p1-ukur.json`.

## 9. Hasil 7b-2 — dikerjakan & terukur (17 Okt 2026)

**Yang berubah**

- `frontend/lib/map-legend-compact.ts` (BARU, murni): `STATUS_LEGEND`, `compactLegendItems()`,
  `legendMarkClass()` — aturan isi baris legenda (status selalu ada; keterangan ikut sakelar lapisannya;
  urutan tetap status → jalur → pemasok).
- `frontend/lib/route-focus.ts`: `FOCUS_CLEAR_LABEL`, `focusFilterText()` — teks chip saringan, memakai
  `focusLabel` yang sama dengan pil pemilih & kartu (satu sumber nama, tidak dirangkai ulang).
- `frontend/lib/map-view.ts`: `mapCooperativeGestures()`, `MAP_GESTURE_HINT_MOBILE`, `MAP_GESTURE_HINT_DESKTOP`,
  `lokalkanPesanGesture()`.
- `frontend/components/SupplyMap.tsx`: baris legenda ringkas di bawah kanvas; chip "Info map" pindah ke pil
  kendali kiri-atas; isi legenda turun ke bawah kanvas (`.map-legend-detail`); chip saringan aktif di atas
  kanvas; `cooperativeGestures` dari media query; skala pindah ke kiri-bawah; pesan gestur MapLibre
  diganti bahasa Indonesia.
- `frontend/app/globals.css`: `.map-legend-compact`, `.map-filter*`, `.map-legend-detail` (panggung absolut
  `.map-legend-stack` dihapus), chip Info map di dalam pil, layar gestur dipergelap.

Catatan cara hitung: yang dihitung adalah elemen MILIK APLIKASI yang berposisi `absolute`/`fixed` di dalam
`.map-shell` dan beririsan dengan kanvas. Tombol "Tampilkan semua" dan bilah skala TIDAK ikut dihitung karena
keduanya hidup di dalam sudut kontrol MapLibre (`maplibregl-ctrl-*`) bersama tombol zoom — memang tempatnya,
dan itu bukan panel yang menutupi peta.

**Angka sebelum → sesudah** (`ukur-7b2.py`, `ukur-7b2-final.py`, `cek-c9-dua-jari.py` — semua di app hidup)

| Hal | Sebelum 7b-2 | Sesudah 7b-2 |
|---|---|---|
| Elemen kendali APLIKASI yang mengapung sendiri di kanvas @1440 | 2 (pil sakelar + chip "Info map") | **1 (pil kendali)** |
| Legenda terbaca tanpa satu klik | tidak — di balik chip | **ya**: baris 752×18 px @1440 · 331×40 px @375 (2 baris) · 4 tanda |
| Isi rincian "Info map" | mengapung kiri-bawah DI ATAS kanvas | **ikut alur DI BAWAH kanvas** (kartu 554→649 px saat dibuka; tinggi kanvas tetap 460 px) |
| Penanda saringan aktif | tidak ada | **chip** 752×28 px di ATAS kanvas: "Menyaring: Supplier A Cianjur → Jakarta" + tombol "Lepas" |
| Skala jarak | kanan-bawah 62×21 | **kiri-bawah** 62×21 (posisi bawaan MapLibre; alasan lama "sudut kiri-bawah dipakai legenda" gugur) |
| Luapan halaman | 0 | 0 di semua keadaan (tertutup, disaring, ponsel) |
| Gestur di ponsel | satu jari mencuri gulir halaman | **satu jari menggulir halaman** (scrollY 0 → 2579) dan **dua jari menggeser peta** (pin `160,186` → `10,36` = 300 px, halaman diam 1144 → 1144) |
| Pesan gestur MapLibre | Inggris, latar `rgba(0,0,0,.4)` (±2,8:1) | **Indonesia** ("Satu jari menggulir halaman · dua jari menggeser peta"), latar `rgba(15,23,42,.66)`, huruf 16 px |
| `cooperativeGestures` | tidak pernah menyala | menyala HANYA di perangkat sentuh (`pointer: coarse`); desktop tetap roda tetikus = zoom |

**Alur C8 diuji hidup, bukan cuma di unit tes**: pil "Supplier A Cianjur → Jakarta · Sudah tiba 19.24"
ditekan → chip "Menyaring: Supplier A Cianjur → Jakarta" muncul DI ATAS kanvas dan kartu tumbuh 554→590 px
→ tombol "Lepas" ditekan → chip hilang dan kartu kembali 554 px.

**Tiga keputusan yang saya ambil sendiri saat mengerjakan (riset tidak menentukannya)**

1. **Isi "Info map" tetap lengkap, tidak dipangkas.** Baris ringkas memuat tanda + nama; kotak Info map tetap
   memuat daftar nada + baris perjalanan. Duplikasi 3–5 butir itu disengaja: daftar singkat untuk makna
   sekejap, kotak untuk rincian (perjalanan, asal geometri). Memangkasnya akan mengubah makna kotak tanpa
   manfaat.
2. **Skala dipindah ke kiri-bawah.** Riset §5 C5 mengusulkan skala ikut zona kiri-atas, tetapi acuan
   industri menaruh skala di sudut bawah; setelah legenda turun dari kanvas, sudut kiri-bawah bebas — jadi
   dipakai posisi bawaan MapLibre, bukan zona atas.
3. **Gestur kooperatif TIDAK berlaku di desktop.** Mode MapLibre mengubah desktop juga (roda tetikus butuh
   Ctrl). Karena keluhan yang diperbaiki adalah gulir halaman di ponsel, mode ini diikat ke `pointer: coarse`
   saja supaya demo di laptop tidak berubah perilaku. Dijaga 3 tes kebijakan + 3 tes opsi peta.

**Gerbang**: 35 tes baru — 8 murni `tests/map-legend-compact.test.ts`, 3 `tests/route-focus.test.ts`,
6 `tests/map-view.test.ts` (kebijakan gestur + pesan Indonesia), 16 kontrak peta di
`tests/supply-map-layer.test.tsx` (C2 5, C5 3, C8 5, C9 3), 2 kontrak CSS di `tests/map-controls-css.test.ts`.
Satu tes 7b-1 **diubah dengan sengaja**: posisi kontrol skala (`bottom-right` → `bottom-left`) — perubahan
disengaja, bukan tes yang dipaksa hijau.
Tangkapan bukti: `ui-audit/p4-desktop.png`, `p4-desktop-disaring.png`, `p4-ponsel.png`,
`p4-c9-dua-jari.png`; angka mentah: `ui-audit/p4-ukur.json`, `p4-c9.json`.

## Sources

[1] https://www.esri.com/arcgis-blog/products/product/mapping/tips-for-legend-design — Esri - Tips for legend design (gagal dibuka: 403 Access Denied; tidak dipakai)
[2] https://developers.google.com/maps/articles/v322-controls-diff — Google Maps JS - Controls
[3] https://developers.google.com/maps/documentation/navigation/android-sdk/v2/controls — Google Maps Navigation SDK - Map UI controls
[4] https://sunnyparkdesign.com/uiux-google-maps-modernization.html — Google Maps Modernization - UX case study
[5] https://www.w3.org/2020/maps/supporting-material-uploads/position-statements/Brandon_Biggs-Smith-Kettlewell.pdf — W3C - Accessibility in Digital Maps (position paper)
[6] https://nsgic.org/wp-content/uploads/2025/10/Making-GIS-Data-Accessible-and-ADA-Compliant.pdf — NSGIC/XR Navigation - Making GIS Data Accessible
[7] https://docs.mapbox.com/mapbox-gl-js/example/toggle-layers — Mapbox GL JS - Show and hide layers
[8] https://www.bathyl.com/en/blog/designing-layer-toggles-for-earth-data — Bathyl - Designing Layer Toggles for Earth Data Maps
[9] https://github.com/reyemtm/mapbox-layer-control — mapbox-layer-control (layer control + legend)
[10] https://mapsplatform.google.com/resources/blog/unlocking-design-autonomy-announcing-the-layout-customization-framework-for-navigation-sdk — Google Maps Platform - Layout customization framework
[11] https://techyorker.com/google-maps-picks-up-a-long-overdue-design-update — Google Maps bottom-sheet redesign (map stays visible)
[12] https://docs.mapbox.com/help/tutorials/react-toggle-layers — Mapbox - Use checkboxes to toggle layers in React
[13] https://www.nngroup.com/articles/bottom-sheet — NN/g - Bottom Sheets: Definition and UX Guidelines
[14] https://mapuipatterns.com/partial-map — Map UI Patterns - Partial map
[15] https://developers.arcgis.com/javascript/latest/creating-app-layouts — ArcGIS Maps SDK JS - Mapping application layouts
[16] https://designsystem.admiralty.co.uk/patterns/find-a-location — Admiralty Design System - Find a location pattern
[17] http://demogmap.elte.hu/tajfutas/isom2000/booklet.pdf — ISOM 2000 - International Specification for Orienteering Maps
[18] https://pubs.usgs.gov/gip/TopographicMapSymbols/topomapsymbols.pdf — USGS - Topographic Map Symbols
[19] https://www.maplibre.org/maplibre-gl-js/docs/API/classes/ScaleControl — MapLibre GL JS - ScaleControl API
[20] https://maplibre.org/maplibre-gl-js/docs — MapLibre GL JS - docs index (examples incl. cooperative gestures)
[21] https://www.axismaps.com/guide/visual-hierarchy — Axis Maps Cartography Guide - Visual Hierarchy
[22] https://www.axismaps.com/guide/map-interaction — Axis Maps Cartography Guide - Map interaction
