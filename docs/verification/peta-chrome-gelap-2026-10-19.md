# Chrome gelap di kartu peta (hapus latar putih) — 19 Okt 2026

## Permintaan

> "untuk design nya gua kurang suka, saya mau backgraund putih di hapus, lalu anda
> redesign menggunakan skill" — pemilik, 19 Okt 2026, memakai skill `ui-ux-pro-max`.

Lingkup dipilih pemilik saat ditanya: **peta saja** — semua putih di atas dan di
sekitar kanvas diganti panel gelap semi-transparan (glass); basemap OSM tetap
terang; halaman lain tidak berubah. Arah warna diserahkan ke saya.

## Dasar desain (skill `ui-ux-pro-max`, bukan selera)

| Aspek | Sumber | Keputusan |
|---|---|---|
| Gaya | `--domain style` → `glassmorphism` | Kaca gelap: `blur(14px)`, border 1px `rgba(255,255,255,.16)`, lapisan gelap 88–94% |
| Palet | `--domain color` → Financial Dashboard (gelap) | Latar `#0F1726` (`#020617`/`#0E1223` digeser sedikit agar biru OSM tidak terasa asing), teks `#F1F5F9`, muted `#C3CEDD`, border `#334155`, aksen `#22C55E` |
| Aksesibilitas | entri glassmorphism + palet, keduanya mensyaratkan kontras 4,5:1 & fokus terlihat | Semua pasangan diukur (tabel di bawah); cincin fokus `#93C5FD` 2px offset 2 |
| Makna tidak hanya warna | aturan chart/aksesibilitas | Sakelar nyala = aksen terisi **dan** `aria-pressed`/ikon tetap berbeda; legenda tetap memasangkan tanda dengan label teks |
| Gerak | `prefers-reduced-motion` | Transisi dimatikan saat diminta |
| Transparansi | di luar katalog (aturan umum) | `prefers-reduced-transparency: reduce` → kaca jadi pekat `#0F1726`; `forced-colors: active` → serahkan ke sistem |

Catatan jujur: kueri `--domain ux` untuk "map overlay legend control" **tidak
mengembalikan padanan** (katalog tidak punya baris UI peta) — sesuai kontrak skill,
aturan peta diambil dari `references/map-ui-patterns.md` (legenda terbaca tanpa
klik, jangan mengandalkan warna saja) dan katalog dipakai untuk aturan umum.

## Yang diubah

Berkas **baru** `frontend/app/map-console.css`, diimpor paling akhir di
`frontend/app/layout.tsx` (setelah `globals.css` dan `theme-ext.css`). Nol hunk di
`globals.css`/`SupplyMap.tsx` — keduanya sedang disunting sesi lain.

Permukaan yang dijadikan kaca gelap, semuanya dibatasi selektor `.map-card`:

1. piringan `.map-body` (kanvas + chrome) — `rgba(13,20,34,.88)` + blur 14px;
2. label pin `.map-pin-label` — `rgba(11,17,28,.90)`, teks `#F1F5F9`;
3. pil sakelar lapisan + tombol legenda, tombol reset, grup kontrol MapLibre,
   skala, atribusi — kaca pekat `rgba(9,14,25,.94)`;
4. chip saringan aktif, tombol "Rincian lapisan", pil pemilih kiriman;
5. popup peta + panahnya (keempat arah), tombol tutup;
6. legenda ringkas, baris "Penanda", tag rincian, catatan pemasok, petunjuk —
   teks `#F1F5F9`/`#C3CEDD` + rambut 1px `rgba(255,255,255,.08)` antar kelompok
   (di kertas putih jarak terbaca dari latar; di kaca tidak).

Tanda legenda **tidak diganti warna**: nada tetap sama dengan kanvas supaya makna
tidak bergeser; tiap tanda diberi halo 1px terang agar nada gelap (hijau rute
`#2E7D32`) tetap terbaca di atas piringan gelap.

## Kontras terukur (bukan perkiraan)

Diukur di aplikasi berjalan: warna `getComputedStyle` tiap elemen, latar efektif
dihitung dengan mengomposit seluruh leluhur ber-alpha (piringan 88%) di atas dua
ekstrem basemap OSM — putih jalan `#FFFFFF` dan hijau taman `#B5C9A8`.

| Elemen | Warna teks | Latar efektif | Rasio | Ambang |
|---|---|---|---|---|
| Label pin | `#F1F5F9` | `rgba(11,17,28,.90)` | **13,3–14,5:1** | AA 4,5 |
| Legenda ringkas | `#F1F5F9` | piringan 88% | **12,16:1** | AA 4,5 |
| Baris penanda | `#F1F5F9` | piringan 88% | **12,16:1** | AA 4,5 |
| Judul legenda / tag rincian | `#C3CEDD` | piringan 88% | **8,37:1** | AA 4,5 |
| Tombol "Rincian lapisan" | `#C3CEDD` | `rgba(255,255,255,.06)` di atas piringan | **6,95:1** | AA 4,5 |
| Popup judul | `#F1F5F9` | `rgba(9,14,25,.94)` | **17,36:1** | AA 4,5 |
| Cincin fokus | `#93C5FD` | piringan 88% | **7,3:1** | 3:1 (non-teks) |

Angka dihitung ulang saat verifikasi (skrip inline di konsol), bukan disalin dari
perkiraan.

## Dua cacat yang ditemukan saat verifikasi

1. **Atribusi MapLibre tetap putih** (`rgba(255,255,255,.5)`). Sebabnya bukan
   kekhususan `.map-card .maplibregl-ctrl-attrib` (0,2,0) yang kalah dari
   `.maplibregl-ctrl.maplibregl-ctrl-attrib` (0,2,0) — seri, dan CSS MapLibre
   diinject lewat `page.css` **setelah** `layout.css`. Perbaikan: selektor ditulis
   `.map-card .maplibregl-ctrl.maplibregl-ctrl-attrib` (0,3,0).
2. **`.map-card` dipakai dua komponen.** Selain kartu peta, `StatusLocationList`
   juga memakai `section.map-card.card.status-location-list`. Karena itu semua
   aturan gelap saya bersarang di `.map-card .map-body`/`.map-gl`/…, dan subtree
   `.map-side` ditegaskan kembali terang (kalau suatu saat dihidupkan di dalam
   kartu peta, teks gelapnya tidak jatuh di atas kaca).

## Verifikasi

- Pemindaian latar putih di dalam kartu peta (semua elemen, alpha > 0,2, luminansi
  > 200, ukuran > 4×4 px): **0 sisa** (sebelum: 19 label putih + tombol reset +
  chip saringan + chip rincian + popup + grup kontrol).
- Geometri: piringan 947×766, tanpa baris yang melewati tepi, satu-satunya
  tumpang tindih adalah pil sakelar di atas kanvas (memang overlay).
- Teks terkecil di chrome peta: 12px (legenda) — di atas batas 12px skill.
- Portal `:3001` (dev kedua) dan `:3000` tetap 200; `:3010` Docker tidak tersentuh.

## Batas jujur

- Basemap OSM **tetap terang** sesuai pilihan pemilik. Kalau nanti ingin peta
  benar-benar gelap, itu pekerjaan lain (tile gelap + warna rute/pin di kanvas).
- Tema gelap hanya di dalam kartu peta. Header, sidebar, tabel, dan kartu lain
  tetap terang — kontras antara piringan gelap dan halaman terang adalah keputusan
  sadar, bukan kelalaian.
- `map-console.css` bergantung pada nama kelas di `globals.css` yang sedang
  disunting sesi lain; kalau mereka mengganti nama kelas, aturan ini perlu
  disesuaikan (dicatat di `TODO.md`).
- Cara membatalkan: hapus baris `import "./map-console.css";` di
  `app/layout.tsx` — seluruh perubahan hilang tanpa menyentuh berkas lain.
