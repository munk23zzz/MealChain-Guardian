# Chrome gelap di kartu peta (hapus latar putih) — 19 Okt 2026

> **Snapshot 19 Oktober 2026** — angka di dokumen ini hasil pengukuran saat itu, bukan keadaan sekarang. Keadaan terbaru: `docs/state-snapshot.md`.

## Permintaan

> "untuk design nya gua kurang suka, saya mau backgraund putih di hapus, lalu anda
> redesign menggunakan skill" — pemilik, 19 Okt 2026, memakai skill `ui-ux-pro-max`.
>
> "tolong warna nya di sesuaikan" — lanjutan, 19 Okt 2026.

Lingkup dipilih pemilik saat ditanya: **peta saja** — semua putih di atas dan di
sekitar kanvas diganti panel gelap semi-transparan (glass); basemap OSM tetap
terang; halaman lain tidak berubah. Arah warna mula-mula diserahkan ke saya, lalu
pemilik meminta penyesuaian.

## Dasar desain (skill `ui-ux-pro-max`, bukan selera)

| Aspek | Sumber | Keputusan |
|---|---|---|
| Gaya | `--domain style` → `glassmorphism` (pembanding: `dark-mode-oled`) | Kaca gelap: `blur(14px)`, hairline 1px, lapisan gelap 88–94% |
| Palet | token gelap milik app sendiri, **bukan palet kedua** | `--trust-bg #0F172A`, `--trust-line rgba(148,163,184,.32)`, `--trust-ink #E2E8F0`, `--trust-accent #7DD3FC` (§5.6 `docs/design.md`) + aksen brand `#1D4ED8` |
| Aksesibilitas | entri glassmorphism & palet mensyaratkan kontras 4,5:1 + fokus terlihat | Semua pasangan diukur; cincin fokus `#7DD3FC` 2px offset 2 |
| Makna tidak hanya warna | aturan aksesibilitas/chart | Sakelar nyala = ikon berganti (garis miring saat mati) + `aria-pressed`; legenda memasangkan tanda dengan label teks |
| Gerak | `prefers-reduced-motion` | Transisi dimatikan saat diminta |
| Transparansi | di luar katalog (aturan umum) | `prefers-reduced-transparency: reduce` → kaca pekat; `forced-colors: active` → serahkan ke sistem |

Catatan jujur: kueri `--domain ux "map overlay legend control"` **nol hasil**
(katalog tidak punya baris UI peta). Aturan peta diambil dari
`references/map-ui-patterns.md`; katalog dipakai untuk aturan umum.

### Koreksi warna (permintaan kedua)

Versi pertama memakai palet **Financial Dashboard** dari katalog: latar `#0F1726`
+ aksen hijau `#22C55E`. Itu masalah konsistensi: aplikasi ini sudah punya satu
bahasa gelap resmi (kartu kepercayaan, `--trust-*`) dengan aksen `#7DD3FC`,
sehingga piringan peta menjadi bahasa gelap **kedua**, dan hijau aksennya
bertabrakan dengan arti hijau di app ini (status aman / surplus).

Versi sekarang meminjam token itu apa adanya:

| Token peta | Nilai | Asal |
|---|---|---|
| `--map-glass` | `rgba(15,23,42,.88)` | `--trust-bg` |
| `--map-glass-deep` | `rgba(10,15,28,.94)` | turunan `--trust-bg` |
| `--map-hair` | `rgba(148,163,184,.32)` | `--trust-line` |
| `--map-text` | `#E2E8F0` | `--trust-ink` |
| `--map-text-muted` | `#AEBCCD` | di antara `--trust-ink` dan `--trust-ink-muted` |
| `--map-accent` | `#7DD3FC` | `--trust-accent` |
| `--map-accent-ink` | `#1E40AF` | keluarga aksen brand (`--accent #1D4ED8`) |
| status | `#4ADE80` / `#F87171` / `#FBBF24` | nada status terang di atas kaca |

`--map-accent-ink` dipakai `globals.css` sebagai warna **ikon sakelar yang nyala**
(`var(--map-accent-ink, #15803d)`). Tiga kandidat diuji pada empat ekstrem basemap
(putih / jalan `#F8F4E8` / hijau taman `#B5C9A8` / air `#AAD3DF`):

| Kandidat | putih | jalan | hijau | air | putusan |
|---|---|---|---|---|---|
| `#15803D` (hijau, nilai cadangan globals) | 5,02 | 4,56 | **2,84** | 3,13 | gagal 3:1 di hijau |
| `#1D4ED8` (accent brand) | 6,70 | 6,09 | 3,79 | 4,18 | lolos, tapi tipis |
| **`#1E40AF` (dipilih)** | **8,72** | **7,93** | **4,94** | **5,44** | lolos semua |

## Yang diubah

Berkas **baru** `frontend/app/map-console.css`, diimpor paling akhir di
`frontend/app/layout.tsx` (setelah `globals.css` dan `theme-ext.css`). Nol hunk di
`globals.css`/`SupplyMap.tsx` — keduanya sedang disunting sesi lain.

Permukaan yang dijadikan kaca gelap, semuanya dibatasi selektor `.map-card`:

1. piringan `.map-body` (kanvas + chrome) — `rgba(15,23,42,.88)` + blur 14px;
2. label pin `.map-pin-label` — `rgba(12,18,32,.90)`, teks `#E2E8F0`;
3. tombol reset, grup kontrol MapLibre, skala, atribusi — kaca pekat
   `rgba(10,15,28,.94)`;
4. chip saringan aktif, tombol "Rincian lapisan", pil pemilih kiriman (kaca + tint
   sky saat aktif);
5. popup peta + panahnya (keempat arah), tombol tutup;
6. legenda ringkas, baris "Penanda", tag rincian, catatan pemasok, petunjuk —
   teks `#E2E8F0`/`#AEBCCD` + rambut 1px `rgba(255,255,255,.08)` antar kelompok
   (di kertas putih jarak terbaca dari latar; di kaca tidak).

Pil sakelar lapisan **sengaja tanpa piringan**: sesi lain (commit `4400992`)
memindahkannya ke kiri-bawah dan menaruh ikon langsung di atas peta dengan halo
putih 1,5px. Aturan mereka berkekhususan 0-4-0 dan menang atas selektor 0-2-0 di
berkas ini — itu hasil yang diinginkan (tidak ada kotak putih, tidak ada piringan
gelap tambahan), jadi tidak dilawan.

Tanda legenda **tidak diganti warna**: nada tetap sama dengan kanvas supaya makna
tidak bergeser; tiap tanda diberi halo 1px terang agar nada gelap (hijau rute
`#2E7D32`) tetap terbaca di atas piringan gelap.

## Kontras terukur (bukan perkiraan)

Diukur di aplikasi berjalan: `getComputedStyle` tiap elemen, latar efektif dihitung
dengan mengomposit seluruh leluhur ber-alpha di atas dua ekstrem basemap (putih
murni dan hijau taman `#B5C9A8`).

| Elemen | Warna teks | Rasio | Ambang |
|---|---|---|---|
| Label pin | `#E2E8F0` di `rgba(12,18,32,.9)` | **14,76:1** | AA 4,5 |
| Legenda ringkas | `#E2E8F0` | **10,36:1** | AA 4,5 |
| Baris penanda | `#E2E8F0` | **10,36:1** | AA 4,5 |
| Judul legenda / tag rincian | `#AEBCCD` | **6,61:1** | AA 4,5 |
| Tombol "Rincian lapisan" | `#AEBCCD` | **5,50:1** | AA 4,5 |
| Popup judul | `#E2E8F0` di `rgba(10,15,28,.94)` | **17,36:1** | AA 4,5 |
| Ikon sakelar nyala | `#1E40AF` di atas peta | 4,94–8,72:1 | 3:1 non-teks |
| Cincin fokus | `#7DD3FC` | 7,6–8,5:1 | 3:1 non-teks |

## Tiga cacat yang ditemukan saat verifikasi

1. **Atribusi MapLibre tetap putih** (`rgba(255,255,255,.5)`). Bukan soal dua kelas
   yang kalah, tapi urutan: CSS MapLibre diinject lewat `page.css` **setelah**
   `layout.css` pada kekhususan seri (0-2-0 vs 0-2-0). Perbaikan: selektor ditulis
   `.map-card .maplibregl-ctrl.maplibregl-ctrl-attrib` (0-3-0).
2. **`.map-card` dipakai dua komponen.** Selain kartu peta, `StatusLocationList`
   juga memakai `section.map-card.card.status-location-list`. Karena itu semua
   aturan gelap bersarang di `.map-card .map-body`/`.map-gl`/…, dan subtree
   `.map-side` ditegaskan kembali terang.
3. **Pil sakelar berubah putih saat hover/fokus.** `globals.css` memberi
   `.map-card .map-overlay-toggles .map-layer-toggle:hover, :focus-visible` latar
   `rgba(255,255,255,.92)` pada 0-4-0 — mengalahkan selektor 0-2-0 saya, sehingga
   kotak putih muncul lagi saat kursor lewat atau Tab mendarat. Perbaikan: aturan
   hover/fokus ditulis pada kekhususan 0-4-0 dan **sesudah** milik mereka; terbukti
   di CSSOM (indeks 297 milik globals, 1377 milik berkas ini) sehingga kaca gelap
   yang menang. Diukur: fokus keyboard → `rgba(10,15,28,.94)` + outline
   `2px rgb(125,211,252)`.

## Verifikasi

- Pemindaian latar putih di dalam kartu peta (alpha > 0,2, luminansi > 200,
  ukuran > 4×4 px): **0 sisa** (sebelum: 19 label putih + tombol reset + chip
  saringan + chip rincian + popup + grup kontrol).
- Pemindaian permukaan terang (luminansi > 150, alpha > 0,05): hanya 4 elemen,
  semuanya lapisan putih 6% di atas kaca — bukan kartu putih.
- Geometri: piringan 947×766, tanpa baris melewati tepi; satu-satunya tumpang
  tindih adalah pil sakelar di atas kanvas (memang overlay).
- Teks chrome terendah 12px; `:focus-visible` aktif pada pil sakelar.
- `tsc --noEmit` 0, `next lint` 0. Vitest penuh 1317 lulus / 13 gagal — gagal di
  `tests/evidence-summary.test.ts` berasal dari suntingan `lib/evidence.ts` sesi
  lain (label "Persetujuan" tinggal 1 kemunculan, di HEAD 2), bukan dari CSS ini.
- Portal `:3001` (dev kedua) dan `:3000` tetap 200; `:3010` Docker tidak tersentuh.

## Batas jujur

- Basemap OSM **tetap terang** sesuai pilihan pemilik. Peta gelap penuh adalah
  pekerjaan lain (tile gelap + warna rute/pin di kanvas).
- Chrome gelap hanya di dalam kartu peta. Kontras piringan gelap vs halaman terang
  adalah keputusan sadar, bukan kelalaian.
- `map-console.css` bergantung pada nama kelas di `globals.css` milik sesi lain;
  kalau kelas diganti, aturan ini perlu disesuaikan (dicatat di `TODO.md` F13c).
- Cara membatalkan: hapus baris `import "./map-console.css";` di
  `app/layout.tsx` — seluruh perubahan hilang tanpa menyentuh berkas lain.
